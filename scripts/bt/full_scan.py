"""Full systematic backtest scan: 9 markets x 7 strategy candidates.

Walk-forward: 3-year expanding IS / 1-year OOS, prior-close signal timing.
Cost model: 0.002% commission + 2 pip slippage.
Sizing: Carver equal-vol = (capital * risk_pct) / (2 * ATR_14).
"""
import sys, json, os, warnings
warnings.filterwarnings("ignore")
# Add project root to path so scripts.bt.* imports work
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _project_root)

import pandas as pd
import numpy as np

from scripts.bt.indicators import calculate_atr, donchian_channel, adx, rolling_efficiency_ratio
from scripts.bt.sizing import calculate_equal_volatility_size
from scripts.bt.ma200 import MA200Crossover

# ─── Cache / output paths ──────────────────────────────────────────────
CACHE_DIR = "/tmp/bt_cache"
OUT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "full_scan_results.json")

# ─── Markets ───────────────────────────────────────────────────────────
MARKETS = ["SPY", "QQQ", "^N225", "GLD", "IEF", "GC=F", "CL=F", "O39.SI", "VNQ"]

# Map each market to the cache filename (matches cached CSV stem)
TICKER_MAP = {m: m for m in MARKETS}

# ─── Strategy definitions ──────────────────────────────────────────────
# Each entry: (label, strategy_class_or_instance_factory, param_label)
# The factory receives (market, risk_pct) and returns a configured object.
# For the TrailingStop variants we define classes inline below.

# ─── Strategy classes (signal generation only) ─────────────────────────

class DonchianSignalFlat:
    """Donchian breakout, signal-flat exit."""
    def __init__(self, period):
        self.period = period
    def signals(self, df):
        ch = donchian_channel(df, period=self.period)
        upper = ch['upper'].shift(1)
        lower = ch['lower'].shift(1)
        close = df['Close']
        sig = pd.Series(0, index=df.index)
        pos = 0
        for i in range(len(df)):
            u = upper.iloc[i]
            l = lower.iloc[i]
            if pd.isna(u) or pd.isna(l):
                sig.iloc[i] = 0
                continue
            if close.iloc[i] > u:
                pos = 1
            elif close.iloc[i] < l:
                pos = -1
            sig.iloc[i] = pos
        return sig

class DonchianTrailingStop:
    """Donchian breakout (period 20) with 3x ATR(14) trailing stop."""
    def __init__(self, period=20, atr_mult=3.0):
        self.period = period
        self.atr_mult = atr_mult
    def signals(self, df):
        ch = donchian_channel(df, period=self.period)
        upper = ch['upper'].shift(1)
        lower = ch['lower'].shift(1)
        close = df['Close']
        atr = calculate_atr(df, period=14)
        sig = pd.Series(0, index=df.index)
        pos = 0
        entry_price = 0.0
        trailing_stop = 0.0
        for i in range(len(df)):
            u = upper.iloc[i]
            l = lower.iloc[i]
            a = atr.iloc[i]
            if pd.isna(u) or pd.isna(l) or pd.isna(a) or a <= 0:
                sig.iloc[i] = 0
                continue
            if pos == 0:
                if close.iloc[i] > u:
                    pos = 1
                    entry_price = close.iloc[i]
                    trailing_stop = close.iloc[i] - self.atr_mult * a
                    sig.iloc[i] = 1
                elif close.iloc[i] < l:
                    pos = -1
                    entry_price = close.iloc[i]
                    trailing_stop = close.iloc[i] + self.atr_mult * a
                    sig.iloc[i] = -1
            elif pos == 1:
                trailing_stop = max(trailing_stop, close.iloc[i] - self.atr_mult * a)
                if close.iloc[i] < trailing_stop:
                    pos = 0
                    sig.iloc[i] = 0
                elif close.iloc[i] > u:
                    # Add to position logic not needed; keep flat if already long
                    pass
            elif pos == -1:
                trailing_stop = min(trailing_stop, close.iloc[i] + self.atr_mult * a)
                if close.iloc[i] > trailing_stop:
                    pos = 0
                    sig.iloc[i] = 0
                elif close.iloc[i] < l:
                    pass
        return sig

class MA200SignalFlat:
    """MA200 crossover: long when Close > MA200, flat otherwise."""
    def __init__(self, period=200):
        self.period = period
    def signals(self, df):
        close = df['Close']
        ma = close.rolling(self.period).mean()
        sig = pd.Series(0, index=df.index)
        sig[close > ma] = 1.0
        return sig

class MA200TrailingStop:
    """MA200 crossover with 3x ATR(14) trailing stop."""
    def __init__(self, period=200, atr_mult=3.0):
        self.period = period
        self.atr_mult = atr_mult
    def signals(self, df):
        close = df['Close']
        ma = close.rolling(self.period).mean()
        atr = calculate_atr(df, period=14)
        sig = pd.Series(0, index=df.index)
        pos = 0
        entry_price = 0.0
        trailing_stop = 0.0
        for i in range(len(df)):
            if pd.isna(ma.iloc[i]):
                sig.iloc[i] = 0
                continue
            a = atr.iloc[i] if pd.notna(atr.iloc[i]) and atr.iloc[i] > 0 else 0.0
            if close.iloc[i] > ma.iloc[i]:
                if pos == 0:
                    pos = 1
                    entry_price = close.iloc[i]
                    trailing_stop = close.iloc[i] - self.atr_mult * a if a > 0 else float('inf')
                elif pos == 1:
                    if a > 0:
                        trailing_stop = max(trailing_stop, close.iloc[i] - self.atr_mult * a)
                    if close.iloc[i] < trailing_stop:
                        pos = 0
                        sig.iloc[i] = 0
            else:
                pos = 0
                sig.iloc[i] = 0
        return sig

class DonchianADXFilter:
    """Donchian breakout (period 20) with ADX > 25 filter."""
    def __init__(self, period=20, adx_threshold=25.0):
        self.period = period
        self.adx_threshold = adx_threshold
    def signals(self, df):
        ch = donchian_channel(df, period=self.period)
        upper = ch['upper'].shift(1)
        lower = ch['lower'].shift(1)
        close = df['Close']
        adx_vals = adx(df)
        sig = pd.Series(0, index=df.index)
        pos = 0
        for i in range(len(df)):
            u = upper.iloc[i]
            l = lower.iloc[i]
            adx_v = adx_vals.iloc[i] if pd.notna(adx_vals.iloc[i]) else np.nan
            if pd.isna(u) or pd.isna(l):
                sig.iloc[i] = 0
                continue
            if close.iloc[i] > u:
                pos = 1
            elif close.iloc[i] < l:
                pos = -1
            if pos != 0 and pd.notna(adx_v) and adx_v < self.adx_threshold:
                pos = 0
            sig.iloc[i] = pos
        return sig

class DonchianERFilter:
    """Donchian breakout (period 20) with Efficiency Ratio > 0.3 filter."""
    def __init__(self, period=20, er_threshold=0.3):
        self.period = period
        self.er_threshold = er_threshold
    def signals(self, df):
        ch = donchian_channel(df, period=self.period)
        upper = ch['upper'].shift(1)
        lower = ch['lower'].shift(1)
        close = df['Close']
        er = rolling_efficiency_ratio(close, period=10)
        sig = pd.Series(0, index=df.index)
        pos = 0
        for i in range(len(df)):
            u = upper.iloc[i]
            l = lower.iloc[i]
            er_v = er.iloc[i] if pd.notna(er.iloc[i]) else np.nan
            if pd.isna(u) or pd.isna(l):
                sig.iloc[i] = 0
                continue
            if close.iloc[i] > u:
                pos = 1
            elif close.iloc[i] < l:
                pos = -1
            if pos != 0 and pd.notna(er_v) and er_v < self.er_threshold:
                pos = 0
            sig.iloc[i] = pos
        return sig

class KAMASlope:
    """KAMA slope (period 10/20/30), signal-flat exit."""
    def __init__(self, period):
        self.period = period
    def signals(self, df):
        from scripts.bt.indicators import calculate_kama
        close = df['Close']
        kama = calculate_kama(close, period=self.period, fast=2, slow=30)
        kama_diff = kama.diff()
        sig = pd.Series(0, index=df.index)
        sig[kama_diff > 0] = 1
        sig[kama_diff < 0] = -1
        return sig

# ─── Backtest engine (inline) ──────────────────────────────────────────
# Mirrors the engine.py logic but supports trailing-stop strategies directly
# and proper prior-close signal timing.

def run_backtest(df, strategy, capital=100000.0, risk_pct=0.01,
                 slippage_pips=2.0, commission_pct=0.00002,
                 use_trailing_stop=False, trailing_atr_mult=3.0,
                 ticker="SPY"):
    """Run a full backtest. Returns (metrics dict, trades list)."""
    if len(df) < 30:
        return _empty_metrics(), []

    pip_value = 0.01 if "JPY" in ticker.upper() else 1.0

    # Compute indicators
    close = df['Close'].values
    high = df['High'].values
    low = df['Low'].values
    atr_arr = calculate_atr(df, period=14).values
    # Guard: replace NaN/zero ATR with a small positive value to avoid division by zero
    atr_arr = np.where((atr_arr != atr_arr) | (atr_arr <= 0), 1e-6, atr_arr)

    # Generate signals
    signals = strategy.signals(df).values.astype(float)

    equity = np.zeros(len(df))
    cash = capital
    position = 0.0
    entry_price = 0.0
    trades = []
    current_trade = None

    # For trailing stop tracking
    trailing_stop = 0.0
    highest_high_since_entry = 0.0
    lowest_low_since_entry = 0.0

    equity[0] = cash

    for i in range(1, len(df)):
        current_close = close[i]
        prev_signal = signals[i - 1]
        current_signal = signals[i]
        atr = atr_arr[i] if i < len(atr_arr) else 0.0
        if atr != atr:  # NaN check
            atr = 0.0

        # Check for signal change OR trailing stop trigger
        pos_changed = (current_signal != prev_signal)

        if position != 0.0:
            # Update trailing stop based on current bar's high/low
            if position > 0:
                highest_high_since_entry = max(highest_high_since_entry, high[i])
                if use_trailing_stop:
                    trailing_stop = max(trailing_stop, highest_high_since_entry - trailing_atr_mult * atr)
                # Check if trailing stop triggered
                if use_trailing_stop and current_close < trailing_stop:
                    pos_changed = True
            else:
                lowest_low_since_entry = min(lowest_low_since_entry, low[i])
                if use_trailing_stop:
                    trailing_stop = min(trailing_stop, lowest_low_since_entry + trailing_atr_mult * atr)
                if use_trailing_stop and current_close > trailing_stop:
                    pos_changed = True

        if pos_changed and position != 0.0:
            # Exit position
            exit_slippage = slippage_pips * pip_value
            if position > 0:
                exit_price = current_close - exit_slippage
            else:
                exit_price = current_close + exit_slippage
            pnl = (exit_price - entry_price) * position
            commission = abs(position) * exit_price * commission_pct
            cash += pnl - commission
            if current_trade:
                current_trade['exit_date'] = i
                current_trade['exit_price'] = exit_price
                current_trade['pnl'] = pnl - commission
                trades.append(current_trade)
                current_trade = None
            position = 0.0
            trailing_stop = 0.0
            highest_high_since_entry = 0.0
            lowest_low_since_entry = 0.0

        # Open new position
        if current_signal != 0 and position == 0:
            base_size = calculate_equal_volatility_size(cash, risk_pct, atr)
            size_mult = abs(current_signal) if abs(current_signal) <= 1.0 else 1.0
            position_size = base_size * max(size_mult, 0.25)
            if position_size > 0:
                entry_slippage = slippage_pips * pip_value
                if current_signal > 0:
                    position = position_size
                    entry_price = current_close + entry_slippage
                    highest_high_since_entry = current_close
                    if use_trailing_stop:
                        trailing_stop = current_close - trailing_atr_mult * atr
                else:
                    position = -position_size
                    entry_price = current_close + entry_slippage
                    lowest_low_since_entry = current_close
                    if use_trailing_stop:
                        trailing_stop = current_close + trailing_atr_mult * atr
                commission = abs(position) * entry_price * commission_pct
                cash -= commission
                current_trade = {
                    'entry_date': i,
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

    # Force close at end
    if position != 0.0 and len(df) > 0:
        last_idx = len(df) - 1
        exit_price = close[last_idx]
        exit_slippage = slippage_pips * pip_value
        if position > 0:
            exit_price = exit_price - exit_slippage
        else:
            exit_price = exit_price + exit_slippage
        pnl = (exit_price - entry_price) * position
        commission = abs(position) * exit_price * commission_pct
        cash += pnl - commission
        if current_trade:
            current_trade['exit_date'] = last_idx
            current_trade['exit_price'] = exit_price
            current_trade['pnl'] = pnl - commission
            trades.append(current_trade)
        equity[last_idx] = cash

    # Compute metrics
    equity_series = pd.Series(equity)
    daily_returns = pd.Series(equity).pct_change().fillna(0.0)

    roll_max = equity_series.cummax()
    drawdown = (equity_series - roll_max) / roll_max
    max_dd = float(drawdown.min())

    days = (df.index[-1] - df.index[0]).days
    years = days / 365.25 if days > 0 else 1.0
    final_value = equity_series.iloc[-1]
    cagr = float((final_value / capital) ** (1.0 / years) - 1.0) if final_value > 0 and years > 0 else 0.0

    mean_ret = float(daily_returns.mean())
    std_ret = float(daily_returns.std())
    sharpe = float((mean_ret / std_ret) * np.sqrt(252)) if std_ret > 0 else 0.0

    pnls = [t['pnl'] for t in trades]
    gross_profits = sum(p for p in pnls if p > 0)
    gross_losses = abs(sum(p for p in pnls if p < 0))
    profit_factor = float(gross_profits / gross_losses) if gross_losses > 0 else (float(gross_profits) if gross_profits > 0 else 1.0)

    metrics = {
        'CAGR': cagr,
        'Max_Drawdown': max_dd,
        'Sharpe': sharpe,
        'Profit_Factor': profit_factor,
        'Final_Value': final_value,
        'Total_Trades': len(trades)
    }
    return metrics, trades


def _empty_metrics():
    return {
        'CAGR': 0.0, 'Max_Drawdown': 0.0, 'Sharpe': 0.0,
        'Profit_Factor': 1.0, 'Final_Value': 100000.0, 'Total_Trades': 0
    }


# ─── Walk-forward runner ───────────────────────────────────────────────

def run_walk_forward(df, strategy, capital=100000.0, risk_pct=0.01,
                     slippage_pips=2.0, commission_pct=0.00002,
                     use_trailing_stop=False, trailing_atr_mult=3.0,
                     is_years=3, oos_years=1, ticker="SPY"):
    """Run walk-forward with expanding IS window."""
    dates = df.index
    if len(dates) < is_years * 252:
        return []

    folds = []
    start_date = dates[0]
    end_date = dates[-1]

    current_is_end = start_date + pd.DateOffset(years=is_years)
    while current_is_end < end_date:
        current_oos_end = min(current_is_end + pd.DateOffset(years=oos_years), end_date)

        is_mask = (df.index >= start_date) & (df.index < current_is_end)
        oos_mask = (df.index >= current_is_end) & (df.index <= current_oos_end)

        df_is = df[is_mask]
        df_oos = df[oos_mask]

        if len(df_is) < 100 or len(df_oos) < 20:
            current_is_end = current_is_end + pd.DateOffset(years=oos_years)
            continue

        # IS metrics
        is_metrics, _ = run_backtest(df_is, strategy, capital, risk_pct,
                                      slippage_pips, commission_pct,
                                      use_trailing_stop, trailing_atr_mult, ticker)
        # OOS metrics
        oos_metrics, _ = run_backtest(df_oos, strategy, capital, risk_pct,
                                       slippage_pips, commission_pct,
                                       use_trailing_stop, trailing_atr_mult, ticker)

        folds.append({
            'is_metrics': is_metrics,
            'oos_metrics': oos_metrics
        })

        current_is_end = current_is_end + pd.DateOffset(years=oos_years)

    return folds


# ─── Main scan ─────────────────────────────────────────────────────────

def main():
    all_passing = []
    all_summary = []

    for market in MARKETS:
        # Find any cache file for this market
        candidates = sorted([f for f in os.listdir(CACHE_DIR)
                             if f.startswith(market) and f.endswith('.csv') and 'weekly' not in f.lower()])
        if not candidates:
            print(f"SKIP {market}: no cache file")
            continue
        fpath = os.path.join(CACHE_DIR, candidates[0])

        df = pd.read_csv(fpath, index_col=0, parse_dates=True)
        ticker_str = market

        print(f"\n{'='*60}")
        print(f"MARKET: {market} ({len(df)} bars, {df.index[0].date()} to {df.index[-1].date()})")
        print(f"{'='*60}")

        # Define strategy candidates
        strategy_defs = []

        # 1. Donchian breakout (period 10, 20, 50, 100, 200) - signal-flat exit
        for p in [10, 20, 50, 100, 200]:
            strategy_defs.append((f"Donchian-{p}-flat", DonchianSignalFlat(p), None, None, None))

        # 2. Donchian breakout (period 20) - 3x ATR(14) trailing stop
        strategy_defs.append(("Donchian-20-trailing3x", DonchianTrailingStop(period=20, atr_mult=3.0), True, 3.0, None))

        # 3. MA200 crossover (close > MA200 long, < MA200 flat) - 3x ATR stop
        strategy_defs.append(("MA200-3xATR", MA200TrailingStop(period=200, atr_mult=3.0), True, 3.0, None))

        # 4. KAMA slope (period 10, 20, 30) - signal-flat exit
        for p in [10, 20, 30]:
            strategy_defs.append((f"KAMA-{p}-flat", KAMASlope(p), None, None, None))

        # 5. Donchian 20 with ADX>25 filter
        strategy_defs.append(("Donchian-20-ADX25", DonchianADXFilter(period=20, adx_threshold=25.0), None, None, None))

        # 6. Donchian 20 with ER>0.3 filter
        strategy_defs.append(("Donchian-20-ER03", DonchianERFilter(period=20, er_threshold=0.3), None, None, None))

        # 7. MA200 + Half-Kelly (risk_pct=0.0391, 0.0781, 0.15625)
        for rp in [0.0391, 0.0781, 0.15625]:
            strategy_defs.append((f"MA200-HalfKelly-rp{rp}", MA200Crossover(period=200), True, 3.0, rp))

        for label, strat, use_ts, ts_mult, risk_pct in strategy_defs:
            effective_risk = risk_pct if risk_pct is not None else 0.01
            use_trailing = use_ts if use_ts is not None else False
            tmult = ts_mult if ts_mult is not None else 3.0

            try:
                folds = run_walk_forward(df, strat, capital=100000.0, risk_pct=effective_risk,
                                         slippage_pips=2.0, commission_pct=0.00002,
                                         use_trailing_stop=use_trailing,
                                         trailing_atr_mult=tmult,
                                         is_years=3, oos_years=1, ticker=ticker_str)
            except Exception as e:
                print(f"  ERR {label}: {e}")
                continue

            if len(folds) < 2:
                continue

            oos_sharpes = [f['oos_metrics']['Sharpe'] for f in folds]
            is_sharpes = [f['is_metrics']['Sharpe'] for f in folds]
            oos_cagrs = [f['oos_metrics']['CAGR'] for f in folds]
            oos_dds = [f['oos_metrics']['Max_Drawdown'] for f in folds]
            oos_pf = [f['oos_metrics']['Profit_Factor'] for f in folds]
            oos_trades = [f['oos_metrics']['Total_Trades'] for f in folds]
            avg_oos_sharpe = float(np.mean(oos_sharpes))
            min_oos_sharpe = float(np.min(oos_sharpes))
            n_passing = sum(1 for s in oos_sharpes if s >= 0.4)
            n_folds = len(folds)
            pct_passing = n_passing / n_folds if n_folds > 0 else 0.0

            # IS->OOS Sharpe drop (using avg IS vs avg OOS)
            avg_is_sharpe = float(np.mean(is_sharpes))
            sharpe_drop = avg_is_sharpe - avg_oos_sharpe

            # Worst MaxDD across OOS folds (most negative)
            worst_oos_maxdd = float(min(oos_dds)) if oos_dds else 0.0  # min = most negative

            # Aggregate metrics from full backtest on entire dataset
            full_metrics, _ = run_backtest(df, strat, capital=100000.0, risk_pct=effective_risk,
                                            slippage_pips=2.0, commission_pct=0.00002,
                                            use_trailing_stop=use_trailing,
                                            trailing_atr_mult=tmult, ticker=ticker_str)

            # Filter uses full-sample metrics for robustness
            full_cagr = full_metrics['CAGR']
            full_sharpe = full_metrics['Sharpe']
            full_maxdd = full_metrics['Max_Drawdown']
            full_pf = full_metrics['Profit_Factor']
            full_trades = full_metrics['Total_Trades']

            # Apply filters
            passes = True
            reasons = []
            if avg_oos_sharpe < 0.4:
                passes = False; reasons.append(f"OOS_Sharpe {avg_oos_sharpe:.3f}<0.4")
            if full_maxdd > 0.50:
                passes = False; reasons.append(f"MaxDD {full_maxdd:.3f}>0.50")
            if sharpe_drop > 0.30:
                passes = False; reasons.append(f"Sharpe drop {sharpe_drop:.3f}>0.30")
            if full_pf < 1.5:
                passes = False; reasons.append(f"PF {full_pf:.3f}<1.5")
            if full_trades < 30:
                passes = False; reasons.append(f"Total_Trades {full_trades}<30")
            if pct_passing < 0.50:
                passes = False; reasons.append(f"Stable {pct_passing:.1%}<50%")

            result = {
                'market': market,
                'strategy': label,
                'CAGR': round(full_cagr, 6),
                'Sharpe': round(full_sharpe, 4),
                'MaxDD': round(full_maxdd, 4),
                'Profit_Factor': round(full_pf, 4),
                'Total_Trades': int(full_trades),
                'OOS_Sharpe_avg': round(avg_oos_sharpe, 4),
                'OOS_Sharpe_min': round(min_oos_sharpe, 4),
                'OOS_Sharpe_max': round(float(np.max(oos_sharpes)), 4),
                'n_folds': n_folds,
                'n_folds_passing_0.4': n_passing,
                'pct_folds_passing': round(pct_passing, 3),
                'IS_Sharpe_avg': round(avg_is_sharpe, 4),
                'IS_OOS_Sharpe_drop': round(sharpe_drop, 4),
                'OOS_MaxDD_worst': round(worst_oos_maxdd, 4),
                'OOS_Profit_Factor_avg': round(float(np.mean(oos_pf)), 4),
                'OOS_Trades_avg': int(np.mean(oos_trades)),
                'pass': passes,
                'reasons': reasons if not passes else []
            }

            all_summary.append(result)

            if passes:
                all_passing.append(result)
                print(f"  PASS: {label} | OOS_Sharpe={avg_oos_sharpe:.3f} | MaxDD={full_maxdd:.3f} | PF={full_pf:.2f} | Trades={full_trades} | Stable={pct_passing:.0%}")

    # Save results
    output = {'passing': all_passing, 'summary': all_summary}
    with open(OUT_PATH, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n{'='*60}")
    print(f"RESULTS: {len(all_passing)} passing out of {len(all_summary)} combos tested")
    print(f"Output saved to: {OUT_PATH}")
    print(f"{'='*60}")

    return output


if __name__ == "__main__":
    main()
