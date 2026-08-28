import pandas as pd
import numpy as np
from typing import Any
from .indicators import calculate_atr
from .sizing import calculate_equal_volatility_size

class Backtest:
    """
    Core execution engine for systematic trading strategies.
    Simulates trading with capital allocation, realistic cost model, and walk-forward validation.
    """
    def __init__(
        self,
        df: pd.DataFrame,
        strategy_instance: Any,
        capital: float = 100000.0,
        risk_pct: float = 0.01,
        slippage_pips: float = 2.0,
        commission_pct: float = 0.00002, # 0.002% IBKR approx or similar
        ticker: str = "USDJPY=X"
    ):
        self.df = df.copy()
        self.strategy = strategy_instance
        self.initial_capital = capital
        self.risk_pct = risk_pct
        self.slippage_pips = slippage_pips
        self.commission_pct = commission_pct
        self.ticker = ticker
        
        # Determine pip size (standard FX pip logic: 0.01 for JPY pairs, 0.0001 otherwise)
        if "JPY" in ticker.upper() or "JPY" in df.columns or (isinstance(ticker, str) and "JPY" in ticker):
            self.pip_value = 0.01
        else:
            self.pip_value = 0.0001
            
        # Calculate ATR for position sizing
        self.df['ATR_14'] = calculate_atr(self.df, period=14)
        
    def run(self, start_date: Any = None, end_date: Any = None) -> dict:
        """Runs the backtest simulation over a specified date window."""
        df = self.df
        if start_date is not None:
            df = df[df.index >= pd.to_datetime(start_date)]
        if end_date is not None:
            df = df[df.index <= pd.to_datetime(end_date)]
            
        if len(df) == 0:
            return self._empty_results()
            
        # Generate signals
        df['Signal'] = self.strategy.signals(df)
        
        # Simulation arrays
        equity = np.zeros(len(df))
        cash = self.initial_capital
        position = 0.0 # shares/units held
        entry_price = 0.0
        
        equity[0] = cash
        trades = [] # Log of trades: (entry_date, exit_date, type, entry_price, exit_price, pnl, size)
        
        current_trade = None
        
        close_prices = df['Close'].values
        signals = df['Signal'].values
        atrs = df['ATR_14'].values
        dates = df.index
        
        for i in range(len(df)):
            if i == 0:
                equity[i] = cash
                continue
                
            current_close = close_prices[i]
            prev_signal = signals[i-1]
            current_signal = signals[i]
            atr = atrs[i]
            
            # Check for signal change (trade execution)
            if current_signal != prev_signal:
                # 1. Close existing position if any
                if position != 0.0:
                    # Apply slippage (slippage hurts: add for buy/long entry, subtract for sell/short entry;
                    # for exit: subtract for long exit, add for short exit)
                    exit_slippage = self.slippage_pips * self.pip_value
                    if position > 0: # Exiting Long
                        exit_price = current_close - exit_slippage
                    else: # Exiting Short
                        exit_price = current_close + exit_slippage
                        
                    pnl = (exit_price - entry_price) * position
                    commission = abs(position) * exit_price * self.commission_pct
                    cash += pnl - commission
                    
                    if current_trade:
                        current_trade['exit_date'] = dates[i]
                        current_trade['exit_price'] = exit_price
                        current_trade['pnl'] = pnl - commission
                        trades.append(current_trade)
                        current_trade = None
                        
                    position = 0.0
                
                # 2. Open new position if signal is not flat (0)
                if current_signal != 0:
                    base_size = calculate_equal_volatility_size(cash, self.risk_pct, atr)
                    # Adaptive sizing: scale by signal magnitude when the strategy provides one
                    size_mult = abs(current_signal) if abs(current_signal) <= 1.0 else 1.0
                    position_size_units = base_size * max(size_mult, 0.25)

                    if position_size_units > 0:
                        entry_slippage = self.slippage_pips * self.pip_value
                        if current_signal > 0: # Enter Long
                            position = position_size_units
                            entry_price = current_close + entry_slippage
                        else: # Enter Short
                            position = -position_size_units
                            entry_price = current_close - entry_slippage
                            
                        commission = abs(position) * entry_price * self.commission_pct
                        cash -= commission # pay commission upfront
                        
                        current_trade = {
                            'entry_date': dates[i],
                            'type': 'LONG' if current_signal > 0 else 'SHORT',
                            'entry_price': entry_price,
                            'size': position
                        }
            
            # Calculate daily equity
            if position != 0.0:
                current_pnl = (current_close - entry_price) * position
                equity[i] = cash + current_pnl
            else:
                equity[i] = cash
                
        # Force close any open position at the very end of backtest for reporting
        if position != 0.0 and len(df) > 0:
            last_idx = len(df) - 1
            exit_price = close_prices[last_idx]
            pnl = (exit_price - entry_price) * position
            commission = abs(position) * exit_price * self.commission_pct
            cash += pnl - commission
            if current_trade:
                current_trade['exit_date'] = dates[last_idx]
                current_trade['exit_price'] = exit_price
                current_trade['pnl'] = pnl - commission
                trades.append(current_trade)
            equity[last_idx] = cash
            
        # Compile results
        df['Equity'] = equity
        df['Daily_Return'] = df['Equity'].pct_change().fillna(0.0)
        
        return self._calculate_metrics(df, trades)
        
    def run_walk_forward(self, is_years: int = 3, oos_years: int = 1) -> list[dict]:
        """
        Executes Walk-Forward validation with an expanding In-Sample window.
        Returns metrics for each walk-forward fold.
        """
        dates = self.df.index
        if len(dates) == 0:
            return []
            
        start_date = dates[0]
        end_date = dates[-1]
        
        folds = []
        current_is_end = start_date + pd.DateOffset(years=is_years)
        
        while current_is_end < end_date:
            current_oos_end = current_is_end + pd.DateOffset(years=oos_years)
            if current_oos_end > end_date:
                current_oos_end = end_date
                
            # Expanding IS window: start_date to current_is_end
            is_results = self.run(start_date, current_is_end)
            # OOS window: current_is_end to current_oos_end
            oos_results = self.run(current_is_end, current_oos_end)
            
            folds.append({
                'fold_num': len(folds) + 1,
                'is_start': start_date,
                'is_end': current_is_end,
                'oos_start': current_is_end,
                'oos_end': current_oos_end,
                'is_metrics': is_results['metrics'],
                'oos_metrics': oos_results['metrics']
            })
            
            # Advance the IS end window by the OOS period
            current_is_end = current_is_end + pd.DateOffset(years=oos_years)
            
        return folds

    def _calculate_metrics(self, df: pd.DataFrame, trades: list[dict]) -> dict:
        equity = df['Equity']
        daily_returns = df['Daily_Return']
        
        # Calculate max drawdown
        roll_max = equity.cummax()
        drawdown = (equity - roll_max) / roll_max
        max_dd = drawdown.min()
        
        # Calculate CAGR
        days = (equity.index[-1] - equity.index[0]).days
        years = days / 365.25 if days > 0 else 1.0
        final_value = equity.iloc[-1]
        cagr = (final_value / self.initial_capital) ** (1.0 / years) - 1.0 if final_value > 0 and years > 0 else 0.0
        
        # Calculate Sharpe Ratio (annualized, assuming 252 trading days)
        mean_return = daily_returns.mean()
        std_return = daily_returns.std()
        sharpe = (mean_return / std_return) * np.sqrt(252) if std_return > 0 else 0.0
        
        # Calculate Profit Factor
        pnls = [t['pnl'] for t in trades]
        gross_profits = sum(p for p in pnls if p > 0)
        gross_losses = abs(sum(p for p in pnls if p < 0))
        profit_factor = gross_profits / gross_losses if gross_losses > 0 else (gross_profits if gross_profits > 0 else 1.0)
        
        metrics = {
            'CAGR': cagr,
            'Max_Drawdown': max_dd,
            'Sharpe': sharpe,
            'Profit_Factor': profit_factor,
            'Final_Value': final_value,
            'Total_Trades': len(trades)
        }
        
        return {
            'metrics': metrics,
            'equity': equity,
            'trades': trades,
            'drawdown': drawdown
        }
        
    def _empty_results(self) -> dict:
        return {
            'metrics': {
                'CAGR': 0.0,
                'Max_Drawdown': 0.0,
                'Sharpe': 0.0,
                'Profit_Factor': 1.0,
                'Final_Value': self.initial_capital,
                'Total_Trades': 0
            },
            'equity': pd.Series([self.initial_capital], index=[self.df.index[0] if len(self.df) > 0 else pd.Timestamp.now()]),
            'trades': [],
            'drawdown': pd.Series([0.0], index=[self.df.index[0] if len(self.df) > 0 else pd.Timestamp.now()])
        }
