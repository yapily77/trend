import pandas as pd
import numpy as np
from typing import List, Dict, Any

class EnsemblePortfolio:
    """
    Naive robust ensembling layer to combine multiple trading strategies' signals.
    Supports:
    1. Equal Weighting (1/N allocation of capital)
    2. Inverse Volatility Weighting (Equal Risk Contribution)
    Strictly forbids parameter optimization or curve-fitting.
    """
    def __init__(self, backtest_results: List[Dict[str, Any]], initial_capital: float = 100000.0):
        self.results = backtest_results
        self.initial_capital = initial_capital
        
    def combine_equal_weighted(self) -> Dict[str, Any]:
        """Combines strategies by allocating equal capital (1/N) to each."""
        if not self.results:
            return self._empty_portfolio()
            
        # Get common datetime index from all equity curves
        common_index = self.results[0]['equity'].index
        for res in self.results[1:]:
            common_index = common_index.intersection(res['equity'].index)
            
        if len(common_index) == 0:
            raise ValueError("No overlapping timeline for strategy ensembling.")
            
        n_strategies = len(self.results)
        portfolio_equity = pd.Series(0.0, index=common_index)
        
        # Naive 1/N allocation: each strategy gets 1/N of the starting capital, and we track its performance.
        for res in self.results:
            equity_slice = res['equity'].reindex(common_index)
            # Normalize to starting allocation
            norm_factor = (self.initial_capital / n_strategies) / equity_slice.iloc[0]
            portfolio_equity += equity_slice * norm_factor
            
        return self._calculate_portfolio_metrics(portfolio_equity)
        
    def combine_inverse_volatility(self, lookback_periods: int = 60) -> Dict[str, Any]:
        """
        Combines strategies using naive Inverse Volatility Weighting.
        The weights are inversely proportional to the rolling standard deviation of daily returns.
        """
        if not self.results:
            return self._empty_portfolio()
            
        common_index = self.results[0]['equity'].index
        for res in self.results[1:]:
            common_index = common_index.intersection(res['equity'].index)
            
        if len(common_index) == 0:
            raise ValueError("No overlapping timeline for strategy ensembling.")
            
        n_strategies = len(self.results)
        
        # Calculate daily returns for each strategy
        returns_df = pd.DataFrame(index=common_index)
        for i, res in enumerate(self.results):
            returns_df[f'strat_{i}'] = res['equity'].reindex(common_index).pct_change().fillna(0.0)
            
        # Calculate strategy standard deviations over the whole period (or rolling, but to avoid param tuning we do static inverse volatility)
        vols = returns_df.std()
        # Avoid division by zero
        vols = vols.replace(0.0, 1.0)
        inv_vols = 1.0 / vols
        weights = inv_vols / inv_vols.sum()
        
        portfolio_equity = pd.Series(0.0, index=common_index)
        for i, res in enumerate(self.results):
            equity_slice = res['equity'].reindex(common_index)
            norm_factor = (self.initial_capital * weights[f'strat_{i}']) / equity_slice.iloc[0]
            portfolio_equity += equity_slice * norm_factor
            
        return self._calculate_portfolio_metrics(portfolio_equity)

    def _calculate_portfolio_metrics(self, equity: pd.Series) -> Dict[str, Any]:
        daily_returns = equity.pct_change().fillna(0.0)
        roll_max = equity.cummax()
        drawdown = (equity - roll_max) / roll_max
        max_dd = drawdown.min()
        
        days = (equity.index[-1] - equity.index[0]).days
        years = days / 365.25 if days > 0 else 1.0
        final_value = equity.iloc[-1]
        cagr = (final_value / self.initial_capital) ** (1.0 / years) - 1.0 if final_value > 0 and years > 0 else 0.0
        
        mean_return = daily_returns.mean()
        std_return = daily_returns.std()
        sharpe = (mean_return / std_return) * np.sqrt(252) if std_return > 0 else 0.0
        
        metrics = {
            'CAGR': cagr,
            'Max_Drawdown': max_dd,
            'Sharpe': sharpe,
            'Final_Value': final_value,
        }
        
        return {
            'metrics': metrics,
            'equity': equity,
            'drawdown': drawdown
        }

    def _empty_portfolio(self) -> Dict[str, Any]:
        dates = [pd.Timestamp.now()]
        equity = pd.Series([self.initial_capital], index=dates)
        return {
            'metrics': {
                'CAGR': 0.0,
                'Max_Drawdown': 0.0,
                'Sharpe': 0.0,
                'Final_Value': self.initial_capital
            },
            'equity': equity,
            'drawdown': pd.Series([0.0], index=dates)
        }
