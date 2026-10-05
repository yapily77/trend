"""Full systematic backtest scan: 9 FX markets x 7 strategy candidates.

Walk-forward: 3-year expanding IS / 1-year OOS, prior-close signal timing.
Cost model: 0.002% commission + 2 pip slippage.
Sizing: Carver equal-vol = (capital * risk_pct) / (2 * ATR_14).
"""
import sys, json, os, warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.bt.indicators import calculate_atr, donchian_channel, adx, rolling_efficiency_ratio, calculate_kama
from scripts.bt.sizing import calculate_equal_volatility_size
from scripts.bt.ma200 import MA200Crossover

# ─── Cache paths ─────────────────────────────────────────────────
CACHE_DIR = "/tmp/bt_cache"
ALT_CACHE = "/home/yapilwsl/arthityap/trend/.bt_cache"
OUT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                        "scripts", "bt", "fx_walkforward_full_results.json")

# ─── Markets (9 FX pairs) ────────────────────────────────────────
MARKETS = ["USDJPY=X", "EURUSD=X", "GBPUSD=X", "AUDUSD=X", "NZDUSD=X",
           "USDCAD=X", "EURJPY=X", "GBPJPY=X", "AUDJPY=X"]

# Map each market to its cache file path
CACHE_FILE = {
    "USDJPY=X":  os.path.join(CACHE_DIR, "USDJPY=X_19950101_20260530.csv"),
    "EURUSD=X":  os.path.join(CACHE_DIR, "EURUSD=X_19950101_20260530.csv"),
    "GBPUSD=X":  os.path.join(CACHE_DIR, "GBPUSD=X_20050101_20260530.csv"),
    "AUDUSD=X":  os.path.join(CACHE_DIR, "AUDUSD=X_20050101_20260530.csv"),
    "NZDUSD=X":  os.path.join(ALT_CACHE, "NZDUSD_20000101_20260601.csv"),
    "USDCAD=X":  os.path.join(CACHE_DIR, "USDCAD=X_20050101_20260530.csv"),
    "EURJPY=X":  os.path.join(CACHE_DIR, "EURJPY=X_19950101_20260530.csv"),
    "GBPJPY=X":  os.path.join(CACHE_DIR, "GBPJPY=X_19950101_20260530.csv"),
    "AUDJPY=X":  os.path.join(CACHE_DIR, "AUDJPY=X_19950101_20260530.csv"),
}


# ─── Load data helper ────────────────────────────────────────────
def load_data(ticker: str) -> pd.DataFrame:
    path = CACHE_FILE[ticker]
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    # Normalize columns to Date, Open, High, Low, Close (some files have Close,High,Low,Open,Volume)
    cols = list(df.columns)
    if "Open" not in cols and "Close" in cols:
        # Format: Date,Close,High,Low,Open,Volume
        df = df.rename(columns={"Close": "Close", "High": "High", "Low": "Low", "Open": "Open"})
    elif "Open" in cols and "Close" not in cols:
        # Format: Date,Open,High,Low,Close
        pass
    # Drop Volume column if present
    df = df.drop(columns=[c for c in ["Volume", "Adj Close"] if c in df.columns])
    # Ensure column types
    for c in ["Open", "High", "Low", "Close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.sort_index()
    return df.dropna(subset=["Close", "High", "Low"])


# ─── Strategy signal classes ─────────────────────────────────────

class DonchianSignalFlat:
    """Donchian breakout, signal-flat exit."""
    def __init__(self, period: int):
        self.period = period
    def signals(self, df: pd.DataFrame) -> pd.Series:
        ch = donchian_channel(df, period=self.period)
        upper = ch['upper'].shift(1)
        lower = ch['lower'].shift(1)
        close = df['Close']
        sig = pd.Series(0.0, index=df.index)
        pos = 0
        for i in range(len(df)):
            u = upper.iloc[i]
            l = lower.iloc[i]
            if pd.isna(u) or pd.isna(l):
                sig.iloc[i] = 0.0
                continue
            if close.iloc[i] > u:
                pos = 1
            elif close.iloc[i] < l:
                pos = -1
            sig.iloc[i] = float(pos)
        return sig


class DonchianTrailingStop:
    """Donchian breakout (period 20) with 3x ATR(14) trailing stop."""
    def __init__(self, period: int = 20, atr_mult: float = 3.0):
        self.period = period
        self.atr_mult = atr_mult
    def signals(self, df: pd.DataFrame) -> pd.Series:
        ch = donchian_channel(df, period=self.period)
        upper = ch['upper'].shift(1)
        lower = ch['lower'].shift(1)
        close = df['Close']
        atr = calculate_atr(df, period=14)
        sig = pd.Series(0.0, index=df.index)
        pos = 0
        entry_price = 0.0
        trailing_stop = 0.0
        highest_high = 0.0
        lowest_low = 0.0
        for i in range(len(df)):
            u = upper.iloc[i]
            l = lower.iloc[i]
            a = atr.iloc[i] if pd.notna(atr.iloc[i]) else 0.0
            if a <= 0:
                a = 1e-6
            if pd.isna(u) or pd.isna(l):
                sig.iloc[i] = 0.0
                continue
            if pos == 0:
                if close.iloc[i] > u:
                    pos = 1
                    entry_price = close.iloc[i]
                    trailing_stop = close.iloc[i] - self.atr_mult * a
                    highest_high = close.iloc[i]
                    sig.iloc[i] = 1.0
                elif close.iloc[i] < l:
                    pos = -1
                    entry_price = close.iloc[i]
                    trailing_stop = close.iloc[i] + self.atr_mult * a
                    lowest_low = close.iloc[i]
                    sig.iloc[i] = -1.0
            elif pos == 1:
                highest_high = max(highest_high, close.iloc[i])
                trailing_stop = max(trailing_stop, highest_high - self.atr_mult * a)
                if close.iloc[i] < trailing_stop:
                    pos = 0
                    sig.iloc[i] = 0.0
            elif pos == -1:
                lowest_low = min(lowest_low, close.iloc[i])
                trailing_stop = min(trailing_stop, lowest_low + self.atr_mult * a)
                if close.iloc[i] > trailing_stop:
                    pos = 0
                    sig.iloc[i] = 0.0
        return sig


class MA200SignalFlat:
    """MA200 crossover: long when Close > MA200, flat otherwise."""
    def __init__(self, period: int = 200):
        self.period = period
    def signals(self, df: pd.DataFrame) -> pd.Series:
        close = df['Close']
        ma = close.rolling(self.period).mean()
        sig = pd.Series(0.0, index=df.index)
        sig[close > ma] = 1.0
        return sig


class MA200TrailingStop:
    """MA200 crossover with 3x ATR(14) trailing stop."""
    def __init__(self, period: int = 200, atr_mult: float = 3.0):
        self.period = period
        self.atr_mult = atr_mult
    def signals(self, df: pd.DataFrame) -> pd.Series:
        close = df['Close']
        ma = close.rolling(self.period).mean()
        atr = calculate_atr(df, period=14)
        sig = pd.Series(0.0, index=df.index)
        pos = 0
        entry_price = 0.0
        trailing_stop = 0.0
        highest_high = 0.0
        lowest_low = 0.0
        for i in range(len(df)):
            if pd.isna(ma.iloc[i]):
                sig.iloc[i] = 0.0
                continue
            a = atr.iloc[i] if pd.notna(atr.iloc[i]) and atr.iloc[i] > 0 else 1e-6
            if close.iloc[i] > ma.iloc[i]:
                if pos == 0:
                    pos = 1
                    entry_price = close.iloc[i]
                    trailing_stop = close.iloc[i] - self.atr_mult * a
                    highest_high = close.iloc[i]
                    sig.iloc[i] = 1.0
                elif pos == 1:
                    highest_high = max(highest_high, close.iloc[i])
                    if a > 0:
                        trailing_stop = max(trailing_stop, highest_high - self.atr_mult * a)
                    if close.iloc[i] < trailing_stop:
                        pos = 0
                        sig.iloc[i] = 0.0
            else:
                pos = 0
                sig.iloc[i] = 0.0
        return sig


class DonchianADXFilter:
    """Donchian breakout (period 20) with ADX > 25 filter."""
    def __init__(self, period: int = 20, adx_threshold: float = 25.0):
        self.period = period
        self.adx_threshold = adx_threshold
    def signals(self, df: pd.DataFrame) -> pd.Series:
        ch = donchian_channel(df, period=self.period)
        upper = ch['upper'].shift(1)
        lower = ch['lower'].shift(1)
        close = df['Close']
        adx_vals = adx(df)
        sig = pd.Series(0.0, index=df.index)
        pos = 0
        for i in range(len(df)):
            u = upper.iloc[i]
            l = lower.iloc[i]
            adx_v = adx_vals.iloc[i] if pd.notna(adx_vals.iloc[i]) else np.nan
            if pd.isna(u) or pd.isna(l):
                sig.iloc[i] = 0.0
                continue
            if close.iloc[i] > u:
                pos = 1
            elif close.iloc[i] < l:
                pos = -1
            if pos != 0 and pd.notna(adx_v) and adx_v < self.adx_threshold:
                pos = 0
            sig.iloc[i] = float(pos)
        return sig


class DonchianERFilter:
    """Donchian breakout (period 20) with Efficiency Ratio > 0.3 filter."""
    def __init__(self, period: int = 20, er_threshold: float = 0.3):
        self.period = period
        self.er_threshold = er_threshold
    def signals(self, df: pd.DataFrame) -> pd.Series:
        ch = donchian_channel(df, period=self.period)
        upper = ch['upper'].shift(1)
        lower = ch['lower'].shift(1)
        close = df['Close']
        er = rolling_efficiency_ratio(close, period=10)
        sig = pd.Series(0.0, index=df.index)
        pos = 0
        for i in range(len(df)):
            u = upper.iloc[i]
            l = lower.iloc[i]
            er_v = er.iloc[i] if pd.notna(er.iloc[i]) else np.nan
            if pd.isna(u) or pd.isna(l):
                sig.iloc[i] = 0.0
                continue
            if close.iloc[i] > u:
                pos = 1
            elif close.iloc[i] < l:
                pos = -1
            if pos != 0 and pd.notna(er_v) and er_v < self.er_threshold:
                pos = 0
            sig.iloc[i] = float(pos)
        return sig


# ─── Backtest engine (inline, supports trailing stop) ────────────

def _empty_metrics():
    return {'CAGR': 0.0, 'Max_Drawdown': 0.0, 'Sharpe': 0.0,
            'Profit_Factor': 1.0, 'Final_Value': 100000.0, 'Total_Trades': 0}


def run_backtest(df, strategy, capital=100000.0, risk_pct=0.01,
                 slippage_pips=2.0, commission_pct=0.00002,
                 use_trailing_stop=False, trailing_atr_mult=3.0,
                 half_kelly_risk_pct=None, ticker="USDJPY=X"):
    """Run a full backtest with Carver equal-vol sizing.
    If half_kelly_risk_pct is set, use that as the risk_pct for sizing (Kelly-based).
    Returns (metrics dict, trades list, n_folds_trades_check).
    """
    if len(df) < 30:
        return _empty_metrics(), [], 0

    effective_risk = half_kelly_risk_pct if half_kelly_risk_pct is not None else risk_pct

    pip_value = 0.01 if "JPY" in ticker.upper() else 1.0

    close = df['Close'].values
    high = df['High'].values
    low = df['Low'].values
    atr_arr = calculate_atr(df, period=14).values
    atr_arr = np.where((atr_arr != atr_arr) | (atr_arr <= 0), 1e-6, atr_arr)

    signals = strategy.signals(df).values.astype(float)

    equity = np.zeros(len(df))
    cash = capital
    position = 0.0
    entry_price = 0.0
    trades = []
    current_trade = None
    trailing_stop = 0.0
    highest_high_since_entry = 0.0
    lowest_low_since_entry = 0.0
    equity[0] = cash
    n_trades_check = 0

    for i in range(1, len(df)):
        current_close = close[i]
        prev_signal = signals[i - 1]
        current_signal = signals[i]
        atr = atr_arr[i]

        pos_changed = (current_signal != prev_signal)

        if position != 0.0:
            if position > 0:
                highest_high_since_entry = max(highest_high_since_entry, high[i])
                if use_trailing_stop:
                    trailing_stop = max(trailing_stop, highest_high_since_entry - trailing_atr_mult * atr)
                if use_trailing_stop and current_close < trailing_stop:
                    pos_changed = True
            else:
                lowest_low_since_entry = min(lowest_low_since_entry, low[i])
                if use_trailing_stop:
                    trailing_stop = min(trailing_stop, lowest_low_since_entry + trailing_atr_mult * atr)
                if use_trailing_stop and current_close > trailing_stop:
                    pos_changed = True

        if pos_changed and position != 0.0:
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

        if current_signal != 0 and position == 0:
            base_size = calculate_equal_volatility_size(cash, effective_risk, atr)
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

        if position != 0.0:
            current_pnl = (current_close - entry_price) * position
            equity[i] = cash + current_pnl
        else:
            equity[i] = cash

    # Force close
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

    # Metrics
    equity_series = pd.Series(equity)
    daily_returns = equity_series.pct_change().fillna(0.0)
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
        'CAGR': cagr, 'Max_Drawdown': max_dd, 'Sharpe': sharpe,
        'Profit_Factor': profit_factor, 'Final_Value': final_value,
        'Total_Trades': len(trades)
    }
    return metrics, trades, len(trades)


# ─── Walk-forward runner ─────────────────────────────────────────

def run_walk_forward(df, strategy, capital=100000.0, risk_pct=0.01,
                     slippage_pips=2.0, commission_pct=0.00002,
                     use_trailing_stop=False, trailing_atr_mult=3.0,
                     half_kelly_risk_pct=None, is_years=3, oos_years=1,
                     ticker="USDJPY=X"):
    dates = df.index
    if len(dates) < is_years * 252:
        return []
    folds = []
    start_date = dates[0]
    current_is_end = start_date + pd.DateOffset(years=is_years)
    while current_is_end < dates[-1]:
        current_oos_end = min(current_is_end + pd.DateOffset(years=oos_years), dates[-1])
        is_mask = (df.index >= start_date) & (df.index < current_is_end)
        oos_mask = (df.index >= current_is_end) & (df.index <= current_oos_end)
        df_is = df[is_mask]
        df_oos = df[oos_mask]
        if len(df_is) < 100 or len(df_oos) < 20:
            current_is_end = current_is_end + pd.DateOffset(years=oos_years)
            continue
        is_metrics, _, is_trades = run_backtest(df_is, strategy, capital, risk_pct,
                                                  slippage_pips, commission_pct,
                                                  use_trailing_stop, trailing_atr_mult,
                                                  half_kelly_risk_pct, ticker)
        oos_metrics, _, oos_trades = run_backtest(df_oos, strategy, capital, risk_pct,
                                                     slippage_pips, commission_pct,
                                                     use_trailing_stop, trailing_atr_mult,
                                                     half_kelly_risk_pct, ticker)
        folds.append({'is_metrics': is_metrics, 'oos_metrics': oos_metrics,
                      'is_trades': is_trades, 'oos_trades': oos_trades})
        current_is_end = current_is_end + pd.DateOffset(years=oos_years)
    return folds


# ─── Strategy definitions ────────────────────────────────────────
# (label, factory, use_trailing_stop, trailing_mult, risk_pct_override)
# risk_pct_override is used for Half-Kelly sizing (passed directly as risk_pct)

STRATEGY_DEFS = []
# 1. Donchian breakout (period 10, 20, 50) - signal-flat exit
for p in [10, 20, 50]:
    STRATEGY_DEFS.append((f"Donchian-{p}-flat", lambda period=p: DonchianSignalFlat(period), False, None, None))
# 2. Donchian breakout (period 20) - 3x ATR(14) trailing stop
STRATEGY_DEFS.append(("Donchian-20-trailing3x", lambda: DonchianTrailingStop(period=20, atr_mult=3.0), True, 3.0, None))
# 3. MA200 crossover (close > MA200 long, < MA200 flat) - 3x ATR stop
STRATEGY_DEFS.append(("MA200-3xATR", lambda: MA200TrailingStop(period=200, atr_mult=3.0), True, 3.0, None))
# 4. KAMA slope (period 10, 20) - signal-flat exit
for p in [10, 20]:
    STRATEGY_DEFS.append((f"KAMA-{p}-flat", lambda period=p: DonchianSignalFlat.__new__(DonchianSignalFlat), False, None, None))
# 5. Donchian 20 with ADX>25 filter
STRATEGY_DEFS.append(("Donchian-20-ADX25", lambda: DonchianADXFilter(period=20, adx_threshold=25.0), False, None, None))
# 6. Donchian 20 with ER>0.3 filter
STRATEGY_DEFS.append(("Donchian-20-ER03", lambda: DonchianERFilter(period=20, er_threshold=0.3), False, None, None))
# 7. MA200 + Half-Kelly (risk_pct=0.0391, 0.0781)
for rp in [0.0391, 0.0781]:
    STRATEGY_DEFS.append((f"MA200-HalfKelly-rp{rp}", lambda rp=rp: MA200Crossover(period=200), False, None, rp))

# Need to fix KAMA slope class - use a proper class
class KAMASlope:
    def __init__(self, period):
        self.period = period
    def signals(self, df):
        close = df['Close']
        kama = calculate_kama(close, period=self.period, fast=2, slow=30)
        kama_diff = kama.diff()
        sig = pd.Series(0.0, index=df.index)
        sig[kama_diff > 0] = 1.0
        sig[kama_diff < 0] = -1.0
        return sig

# Rebuild KAMA entries properly
STRATEGY_DEFS = []
for p in [10, 20, 50]:
    STRATEGY_DEFS.append((f"Donchian-{p}-flat", lambda period=p: DonchianSignalFlat(period), False, None, None))
STRATEGY_DEFS.append(("Donchian-20-trailing3x", lambda: DonchianTrailingStop(period=20, atr_mult=3.0), True, 3.0, None))
STRATEGY_DEFS.append(("MA200-3xATR", lambda: MA200Crossover(period=200), False, None, None))
for p in [10, 20]:
    STRATEGY_DEFS.append((f"KAMA-{p}-flat", lambda period=p: KAMASlope(period), False, None, None))
STRATEGY_DEFS.append(("Donchian-20-ADX25", lambda: DonchianADXFilter(period=20, adx_threshold=25.0), False, None, None))
STRATEGY_DEFS.append(("Donchian-20-ER03", lambda: DonchianERFilter(period=20, er_threshold=0.3), False, None, None))
for rp in [0.0391, 0.0781]:
    STRATEGY_DEFS.append((f"MA200-HalfKelly-rp{rp}", lambda rp=rp: MA200Crossover(period=200), False, None, rp))


def main():
    all_passing = []
    all_summary = []
    total_combos = 0

    for market in MARKETS:
        fpath = CACHE_FILE[market]
        if not os.path.exists(fpath):
            print(f"SKIP {market}: cache file not found at {fpath}")
            continue
        df = load_data(market)
        print(f"\n{'='*60}")
        print(f"MARKET: {market} ({len(df)} bars, {df.index[0].date()} to {df.index[-1].date()})")
        print(f"{'='*60}")

        for label, strat_factory, use_ts, ts_mult, risk_override in STRATEGY_DEFS:
            strat = strat_factory()
            effective_risk = risk_override if risk_override is not None else 0.01
            use_trailing = use_ts if use_ts is not None else False
            tmult = ts_mult if ts_mult is not None else 3.0
            total_combos += 1

            try:
                folds = run_walk_forward(df, strat, capital=100000.0, risk_pct=effective_risk,
                                         slippage_pips=2.0, commission_pct=0.00002,
                                         use_trailing_stop=use_trailing,
                                         trailing_atr_mult=tmult,
                                         half_kelly_risk_pct=risk_override,
                                         is_years=3, oos_years=1, ticker=market)
            except Exception as e:
                print(f"  ERR {label}: {e}")
                continue

            if len(folds) < 2:
                continue

            oos_sharpes = [f['oos_metrics']['Sharpe'] for f in folds]
            is_sharpes = [f['is_metrics']['Sharpe'] for f in folds]
            oos_trades = [f['oos_trades'] for f in folds]
            oos_dds = [f['oos_metrics']['Max_Drawdown'] for f in folds]
            oos_pf = [f['oos_metrics']['Profit_Factor'] for f in folds]
            avg_oos_sharpe = float(np.mean(oos_sharpes))
            min_oos_sharpe = float(np.min(oos_sharpes))
            max_oos_sharpe = float(np.max(oos_sharpes))
            n_folds = len(folds)
            n_passing = sum(1 for s in oos_sharpes if s >= 0.4)
            pct_passing = n_passing / n_folds if n_folds > 0 else 0.0
            avg_is_sharpe = float(np.mean(is_sharpes))
            sharpe_drop = avg_is_sharpe - avg_oos_sharpe
            worst_oos_maxdd = float(min(oos_dds)) if oos_dds else 0.0
            min_oos_trades = min(oos_trades) if oos_trades else 0

            # Full-sample metrics
            full_metrics, _, _ = run_backtest(df, strat, capital=100000.0, risk_pct=effective_risk,
                                               slippage_pips=2.0, commission_pct=0.00002,
                                               use_trailing_stop=use_trailing,
                                               trailing_atr_mult=tmult,
                                               half_kelly_risk_pct=risk_override, ticker=market)

            passes = True
            reasons = []
            if min_oos_trades < 30:
                passes = False; reasons.append(f"OOS_trades {min_oos_trades}<30")
            if avg_oos_sharpe < 0.4:
                passes = False; reasons.append(f"OOS_Sharpe {avg_oos_sharpe:.3f}<0.4")
            if full_metrics['Max_Drawdown'] > 0.50:
                passes = False; reasons.append(f"MaxDD {full_metrics['Max_Drawdown']:.3f}>0.50")
            if sharpe_drop > 0.30:
                passes = False; reasons.append(f"Sharpe drop {sharpe_drop:.3f}>0.30")
            if full_metrics['Profit_Factor'] < 1.5:
                passes = False; reasons.append(f"PF {full_metrics['Profit_Factor']:.3f}<1.5")
            if full_metrics['Total_Trades'] < 30:
                passes = False; reasons.append(f"Total_Trades {full_metrics['Total_Trades']}<30")
            if pct_passing < 0.50:
                passes = False; reasons.append(f"Stable {pct_passing:.1%}<50%")

            result = {
                'market': market,
                'strategy': label,
                'CAGR': round(full_metrics['CAGR'], 6),
                'Sharpe': round(full_metrics['Sharpe'], 4),
                'MaxDD': round(full_metrics['Max_Drawdown'], 4),
                'Profit_Factor': round(full_metrics['Profit_Factor'], 4),
                'Total_Trades': int(full_metrics['Total_Trades']),
                'OOS_Sharpe_avg': round(avg_oos_sharpe, 4),
                'OOS_Sharpe_min': round(min_oos_sharpe, 4),
                'OOS_Sharpe_max': round(max_oos_sharpe, 4),
                'n_folds': n_folds,
                'n_folds_passing_0.4': int(n_passing),
                'pct_folds_passing': round(pct_passing, 3),
                'IS_Sharpe_avg': round(avg_is_sharpe, 4),
                'IS_OOS_Sharpe_drop': round(sharpe_drop, 4),
                'OOS_MaxDD_worst': round(worst_oos_maxdd, 4),
                'OOS_Min_Trades': int(min_oos_trades),
                'pass': passes,
                'reasons': reasons if not passes else []
            }
            all_summary.append(result)
            if passes:
                all_passing.append(result)
                print(f"  PASS: {label} | OOS_Sharpe={avg_oos_sharpe:.3f} | MaxDD={full_metrics['Max_Drawdown']:.3f} | PF={full_metrics['Profit_Factor']:.2f} | Trades={full_metrics['Total_Trades']} | Stable={pct_passing:.0%}")
            else:
                print(f"  FAIL: {label} | {'; '.join(reasons)}")

    output = {'passing': all_passing, 'summary': all_summary}
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n{'='*60}")
    print(f"RESULTS: {len(all_passing)} passing out of {total_combos} combos tested")
    print(f"Output saved to: {OUT_PATH}")
    print(f"{'='*60}")
    return output


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2))
