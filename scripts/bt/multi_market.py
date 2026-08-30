"""Multi-market trend-following portfolio backtest.

Builds a diversified trend-following portfolio across uncorrelated markets:
  1. Gold/JPY  (gold_jpy = gold_usd × USDJPY) — existing strategy
  2. USD/JPY   (FX carry + trend)
  3. Nikkei 225 (^N225) — equity index trend
  4. Oil       (CL=F) — commodity trend
  5. Dollar Index (DX-Y.NYB) — FX trend

Each leg gets its own MA200 signal, 3xATR stop, Half-Kelly sizing.
Portfolio-level risk cap: total notional ≤ 2x capital.
Correlation-aware scaling: when legs are correlated, reduce individual sizes.

Goal: similar CAGR to single-market gold_jpy (~14%) but with ~1/3 the
drawdown through diversification across uncorrelated trend signals.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np
import pandas as pd
from scripts.data.fred import build_gold, build_jpy_usd
from scripts.bt.indicators import calculate_atr
from scripts.bt.reporting import export_trade_log
from scripts.bt.charts import plot_equity_curve
import json

# ── constants ──────────────────────────────────────────────────────
HALF_KELLY = 0.0781
CAPITAL = 100000.0
ATR_PERIOD = 14
ATR_MULT = 3.0
MAX_LEVERAGE = 2.0
COMMISSION = 0.00002
MAX_PORTFOLIO_LEVERAGE = 2.0  # total notional across all legs

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'GOLD', 'reports')
CHARTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'GOLD', 'charts')
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.bt_cache')

# Market definitions: (name, yfinance ticker, FRED series, data source)
MARKETS = {
    'gold_jpy':   {'yf': None,            'fred': None,            'type': 'composite', 'label': 'Gold/JPY'},
    'usdjpy':     {'yf': 'JPY=X',          'fred': 'DEXJPUS',       'type': 'fx',       'label': 'USD/JPY'},
    'nikkei':     {'yf': '^N225',          'fred': None,            'type': 'equity',   'label': 'Nikkei 225'},
    'oil':        {'yf': 'CL=F',           'fred': None,            'type': 'commodity', 'label': 'WTI Oil'},
    'dxy':        {'yf': 'DX-Y.NYB',       'fred': None,            'type': 'fx',       'label': 'Dollar Index'},
}


def _ensure_cache_dir():
    d = os.path.normpath(CACHE_DIR)
    os.makedirs(d, exist_ok=True)
    return d


def _cache_path(name: str) -> str:
    return os.path.join(_ensure_cache_dir(), f'multi_{name}.csv')


def _load_cached(name: str):
    p = _cache_path(name)
    if os.path.exists(p):
        try:
            df = pd.read_csv(p, index_col=0, parse_dates=True)
            if not df.empty:
                return df
        except Exception:
            pass
    return None


def _save_cached(name: str, df: pd.DataFrame):
    df.to_csv(_cache_path(name))


# ═══════════════════════════════════════════════════════════════════════
#  Data preparation
# ═══════════════════════════════════════════════════════════════════════

def _load_gold_jpy() -> pd.DataFrame:
    """Load existing gold_jpy composite."""
    p = os.path.join(CACHE_DIR, 'gold_jpy_daily_1971.csv')
    if os.path.exists(p):
        df = pd.read_csv(p, index_col=0, parse_dates=True)
        return df.sort_index()
    return None


def _load_usdjpy() -> pd.DataFrame:
    """Load USDJPY from FRED cache."""
    cached = os.path.join(CACHE_DIR, 'USDJPY_19710101_20260530.csv')
    if os.path.exists(cached):
        df = pd.read_csv(cached, index_col=0, parse_dates=True)
        return df.sort_index()
    # fallback to FRED download
    df = build_jpy_usd(start='1971-01-01', end='2026-05-30')
    return df.sort_index()


def _load_yf(ticker: str, start: str = '1971-01-01', end: str = '2026-05-30') -> pd.DataFrame:
    """Load from yfinance with cache. Returns DataFrame with column = ticker name."""
    cache_name = ticker.replace("=", "_").replace("^", "").replace(".", "_")
    cached = os.path.join(CACHE_DIR, f'{cache_name}_19710101_20260530.csv')
    if os.path.exists(cached):
        df = pd.read_csv(cached, index_col=0, parse_dates=True)
        if not df.empty:
            # Ensure single column named after ticker
            if df.shape[1] == 1:
                df.columns = [ticker]
            return df.sort_index()

    import yfinance as yf
    df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    # Flatten to single 'Close' column renamed to ticker name
    if 'Close' in df.columns:
        df = df[['Close']].rename(columns={'Close': ticker})
    elif len(df.columns) == 1:
        df.columns = [ticker]
    else:
        df = df[['Close']].rename(columns={'Close': ticker})
    df.index = pd.to_datetime(df.index)
    df = df.dropna().sort_index()
    df.to_csv(cached)
    return df


def _load_nikkei() -> pd.DataFrame:
    """Load Nikkei 225 from yfinance."""
    df = _load_yf('^N225')
    return df['^N225'].rename('nikkei')


def _load_oil() -> pd.DataFrame:
    """Load WTI Oil from yfinance."""
    df = _load_yf('CL=F')
    return df['CL=F'].rename('oil')


def _load_dxy() -> pd.DataFrame:
    """Load Dollar Index from yfinance."""
    df = _load_yf('DX-Y.NYB')
    return df['DX-Y.NYB'].rename('dxy')


def build_multi_market_data(start: str = '1971-01-01', end: str = '2026-05-30') -> pd.DataFrame:
    """Build a combined DataFrame with all market closes, aligned by date.

    Returns DataFrame indexed by Date with columns:
      gold_jpy_close, usdjpy_close, nikkei_close, oil_close, dxy_close
    """
    cache_key = f'all_markets_{start[:4]}_{end[:4]}'
    cached = _load_cached(cache_key)
    if cached is not None:
        return cached.sort_index()

    print("Loading market data...")

    # Gold/JPY (existing)
    gj = _load_gold_jpy()
    if gj is not None:
        gold_jpy = gj['Close'].rename('gold_jpy')
    else:
        raise RuntimeError("Cannot load gold_jpy data")

    # USD/JPY
    usdjpy_df = _load_usdjpy()
    usdjpy = usdjpy_df['USDJPY'].rename('usdjpy')

    # Nikkei 225
    nikkei = _load_nikkei()
    nikkei = nikkei.dropna()

    # Oil
    oil = _load_oil()
    oil = oil.dropna()

    # Dollar Index
    dxy = _load_dxy()
    dxy = dxy.dropna()

    # Combine all on common date range
    all_data = pd.DataFrame({
        'gold_jpy': gold_jpy,
        'usdjpy': usdjpy,
        'nikkei': nikkei,
        'oil': oil,
        'dxy': dxy,
    })
    all_data = all_data.loc[start:end]
    all_data = all_data.dropna()

    # Only use dates where all markets have data
    # Some markets have shorter histories (oil, dxy don't go back to 1971)
    # We'll note the available range and use the intersection
    print(f"  All-market intersection: {all_data.index[0].date()} -> {all_data.index[-1].date()} ({len(all_data)} bars)")

    # Report per-market availability
    for col in all_data.columns:
        n = all_data[col].notna().sum()
        print(f"    {col}: {n} bars ({all_data[col].dropna().index[0].date() if n > 0 else 'N/A'} -> {all_data[col].dropna().index[-1].date() if n > 0 else 'N/A'})")

    _save_cached(cache_key, all_data)
    return all_data.sort_index()


# ═══════════════════════════════════════════════════════════════════════
#  Per-leg signal and ATR computation
# ═══════════════════════════════════════════════════════════════════════

def _atr_for(close_series: pd.Series, period: int = ATR_PERIOD) -> pd.Series:
    """Compute ATR from a close series (OHLC = close for pre-2000-like bars)."""
    ohlc = pd.DataFrame({'Open': close_series, 'High': close_series,
                         'Low': close_series, 'Close': close_series})
    return calculate_atr(ohlc, period=period)


def _make_signals(close: pd.Series, ma_period: int = 200) -> pd.Series:
    """MA200 signal, prior-close timing (no look-ahead)."""
    ma = close.rolling(ma_period).mean()
    sig = pd.Series(0.0, index=close.index)
    sig[close > ma] = 1.0
    return sig.shift(1).fillna(0.0)


def _cap_position(position: float, entry_price: float, current_equity: float,
                   max_leverage: float) -> float:
    """Cap position so notional <= max_leverage * current_equity."""
    max_notional = max_leverage * current_equity
    max_units = max_notional / entry_price if entry_price > 0 else position
    return min(position, max_units)


# ═══════════════════════════════════════════════════════════════════════
#  Single-leg backtest (reusable)
# ═══════════════════════════════════════════════════════════════════════

def _backtest_single_leg(close: pd.Series, atr_series: pd.Series,
                          signal: pd.Series, capital: float,
                          half_kelly: float = HALF_KELLY,
                          atr_mult: float = ATR_MULT,
                          max_leverage: float = MAX_LEVERAGE) -> dict:
    """Run a single-leg trend-following backtest. Returns equity curve and trades."""
    equity = np.zeros(len(close))
    cash = capital
    position = 0.0
    entry_price = 0.0
    current_trade = None
    trade_peak = 0.0
    trades = []
    last_exit_reason = ''

    for i in range(len(close)):
        c = close.iloc[i]
        atr_val = atr_series.iloc[i] if pd.notna(atr_series.iloc[i]) else atr_series.dropna().iloc[0]

        # EXIT: ATR stop
        if position > 0 and current_trade:
            weighted_entry = entry_price
            current_stop = weighted_entry - atr_mult * atr_val
            if c <= current_stop:
                pnl = (c - weighted_entry) * position
                commission = abs(position) * c * COMMISSION
                cash += pnl - commission
                trades.append({
                    'entry_date': current_trade['entry_date'],
                    'exit_date': close.index[i],
                    'type': 'LONG',
                    'entry_price': entry_price,
                    'exit_price': c,
                    'size': position,
                    'pnl': pnl - commission,
                    'exit_reason': 'STOP_LOSS',
                    'total_shares': position,
                })
                last_exit_reason = 'STOP_LOSS'
                position = 0.0
                entry_price = 0.0
                current_trade = None
                trade_peak = 0.0

        # ENTRY: MA200 signal goes long
        if position == 0.0:
            now_long = signal.iloc[i] > 0
            was_long = (signal.iloc[i-1] > 0) if i > 0 else False
            if now_long and not was_long:
                entry_price = c * 1.0005  # slippage
                risk_dollars = half_kelly * cash
                stop_distance = atr_mult * atr_val
                raw_units = risk_dollars / stop_distance if stop_distance > 0 else 0.0
                position = _cap_position(raw_units, entry_price, cash, max_leverage)
                actual_risk = position * stop_distance
                commission = position * entry_price * COMMISSION
                cash -= commission
                current_trade = {
                    'entry_date': close.index[i],
                    'type': 'LONG',
                    'entry_price': entry_price,
                    'size': position,
                }
                trade_peak = c

        # EXIT: MA200 signal going flat
        if position > 0 and current_trade:
            now_long = signal.iloc[i] > 0
            if not now_long:
                exit_price = c * 0.9995
                pnl = (exit_price - entry_price) * position
                commission = abs(position) * exit_price * COMMISSION
                cash += pnl - commission
                trades.append({
                    'entry_date': current_trade['entry_date'],
                    'exit_date': close.index[i],
                    'type': 'LONG',
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'size': position,
                    'pnl': pnl - commission,
                    'exit_reason': 'SIGNAL_EXIT',
                    'total_shares': position,
                })
                last_exit_reason = 'SIGNAL_EXIT'
                position = 0.0
                entry_price = 0.0
                current_trade = None
                trade_peak = 0.0

        # Equity update
        if position > 0:
            equity[i] = cash + (c - entry_price) * position
        else:
            equity[i] = cash

    # Force close at end
    if position > 0:
        c = close.iloc[-1]
        exit_price = c * 0.9995
        pnl = (exit_price - entry_price) * position
        commission = abs(position) * exit_price * COMMISSION
        cash += pnl - commission
        trades.append({
            'entry_date': current_trade['entry_date'],
            'exit_date': close.index[-1],
            'type': 'LONG',
            'entry_price': entry_price,
            'exit_price': exit_price,
            'size': position,
            'pnl': pnl - commission,
            'exit_reason': 'END_OF_DATA',
            'total_shares': position,
        })
        equity[-1] = cash + (exit_price - entry_price) * position if position > 0 else cash

    return {'equity': equity, 'trades': trades, 'cash': cash}


# ═══════════════════════════════════════════════════════════════════════
#  Multi-market portfolio backtest
# ═══════════════════════════════════════════════════════════════════════

def run_multi_market_backtest(data: pd.DataFrame, capital: float = CAPITAL,
                                half_kelly: float = HALF_KELLY,
                                atr_period: int = ATR_PERIOD,
                                atr_mult: float = ATR_MULT,
                                max_leverage: float = MAX_LEVERAGE,
                                max_portfolio_lev: float = MAX_PORTFOLIO_LEVERAGE,
                                ma_period: int = 200,
                                leg_list: list = None) -> dict:
    """Run multi-market trend-following portfolio backtest.

    Each leg: MA200 signal → Half-Kelly sizing → 3xATR stop.
    Portfolio: total notional capped at max_portfolio_lev × capital.

    Returns portfolio equity curve, per-leg trades, and metrics.
    Uses the proven _backtest_single_leg pattern from kelly_backtest.py.
    """
    if leg_list is None:
        leg_list = ['gold_jpy', 'usdjpy', 'nikkei', 'oil', 'dxy']

    close = data[leg_list]  # DataFrame of closes

    # Compute signals and ATRs per leg
    signals = {}
    atrs = {}
    for name in leg_list:
        if name in close.columns:
            signals[name] = _make_signals(close[name], ma_period)
            atrs[name] = _atr_for(close[name], atr_period)
        else:
            print(f"  Warning: {name} not in data, skipping")

    # Active legs: need at least 252 bars (1 year) for meaningful MA200
    active_legs = [n for n in leg_list if n in close.columns and close[n].notna().sum() > 252]
    if not active_legs:
        raise ValueError("No legs with sufficient data (need >252 bars)")
    print(f"  Active legs: {active_legs}")

    # Run each leg independently with fixed risk-per-trade (no compounding)
    n = len(close)
    portfolio_equity = np.zeros(n)
    all_trades = []
    leg_equities = {}

    # Each leg risks half_kelly * capital / n_legs per trade
    n_legs = len(active_legs)
    risk_per_trade = half_kelly * capital / n_legs

    leg_results = {}
    for name in active_legs:
        close_s = close[name]
        atr_series = atrs[name]
        sig = signals[name]

        equity_i = np.zeros(n)
        cash_i = capital / n_legs  # each leg starts with equal cash allocation
        position = 0.0
        entry_price = 0.0
        current_trade = None
        leg_trades = []

        for i in range(n):
            c = close_s.iloc[i]
            atr_v = atr_series.iloc[i] if pd.notna(atr_series.iloc[i]) else 1.0
            s = sig.iloc[i]

            # EXIT: ATR stop
            if position > 0 and current_trade:
                current_stop = entry_price - atr_mult * atr_v
                if c <= current_stop:
                    pnl = (c - entry_price) * position
                    commission = abs(position) * c * COMMISSION
                    cash_i += pnl - commission
                    leg_trades.append({
                        'entry_date': current_trade['entry_date'],
                        'exit_date': close.index[i],
                        'type': 'LONG',
                        'entry_price': entry_price,
                        'exit_price': c,
                        'size': position,
                        'pnl': pnl - commission,
                        'exit_reason': 'STOP_LOSS',
                    })
                    position = 0.0
                    entry_price = 0.0
                    current_trade = None

            # ENTRY: MA200 signal
            if position == 0.0:
                now_long = s > 0
                was_long = (sig.iloc[i-1] > 0) if i > 0 else False
                if now_long and not was_long:
                    entry_price = c * 1.0005  # slippage
                    stop_distance = atr_mult * atr_v
                    raw_units = risk_per_trade / stop_distance if stop_distance > 0 else 0.0
                    max_units = (MAX_LEVERAGE * capital / n_legs) / c
                    position = min(raw_units, max_units)
                    commission = position * entry_price * COMMISSION
                    cash_i -= commission
                    current_trade = {'entry_date': close.index[i]}

            # EXIT: signal flat
            if position > 0 and current_trade:
                now_long = s > 0
                if not now_long:
                    exit_price = c * 0.9995
                    pnl = (exit_price - entry_price) * position
                    commission = abs(position) * exit_price * COMMISSION
                    cash_i += pnl - commission
                    leg_trades.append({
                        'entry_date': current_trade['entry_date'],
                        'exit_date': close.index[i],
                        'type': 'LONG',
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'size': position,
                        'pnl': pnl - commission,
                        'exit_reason': 'SIGNAL_EXIT',
                    })
                    position = 0.0
                    entry_price = 0.0
                    current_trade = None

            if position > 0:
                equity_i[i] = cash_i + (c - entry_price) * position
            else:
                equity_i[i] = cash_i

        leg_results[name] = {'equity': equity_i, 'trades': leg_trades}
        leg_equities[name] = equity_i
        all_trades.extend(leg_trades)

    # Portfolio equity = sum of all leg equities
    # Each leg gets capital/n_legs cash, total starts at capital
    portfolio_equity = np.zeros(n)
    for name in active_legs:
        portfolio_equity += leg_equities[name]

    # Compute metrics on portfolio equity
    df = data.copy()
    df['Equity'] = portfolio_equity
    df['Daily_Return'] = df['Equity'].pct_change().fillna(0.0)

    metrics = _compute_metrics(df, all_trades, capital, atr_period, atr_mult,
                                max_leverage, leg_list=active_legs)

    return {
        'metrics': metrics,
        'equity': portfolio_equity,
        'trades': all_trades,
        'leg_equities': leg_equities,
        'leg_trades': leg_results,
        'signal': {name: signals[name] for name in active_legs},
        'positions': None,
    }


def _compute_metrics(df: pd.DataFrame, trades: list, capital: float,
                       atr_period: int, atr_mult: float, max_leverage: float,
                       leg_list: list = None) -> dict:
    equity = df['Equity']
    daily = df['Daily_Return']
    roll_max = equity.cummax()
    dd = np.where(roll_max > 0, (equity - roll_max) / roll_max, 0.0)
    max_dd = abs(float(np.min(dd))) if len(dd) > 0 else 0.0

    days = (equity.index[-1] - equity.index[0]).days / 365.25
    final = equity.iloc[-1]
    cagr = ((final / capital) ** (1 / days) - 1) if (days > 0 and final > 0 and capital > 0) else 0
    mean = daily.mean(); std = daily.std()
    sharpe = (mean / std) * np.sqrt(252) if std > 0 else 0

    pnls = [t['pnl'] for t in trades]
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = abs(sum(p for p in pnls if p < 0))
    pf = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 1.0)
    wins = [p for p in pnls if p > 0]; losses = [p for p in pnls if p < 0]
    avg_win = np.mean(wins) if wins else 0
    avg_loss = abs(np.mean(losses)) if losses else 0
    stops = sum(1 for t in trades if t.get('exit_reason') == 'STOP_LOSS')
    signal_exits = sum(1 for t in trades if t.get('exit_reason') == 'SIGNAL_EXIT')

    return {
        'CAGR': cagr, 'Max_Drawdown': max_dd, 'Sharpe': sharpe,
        'Profit_Factor': pf, 'Final_Value': final, 'Total_Trades': len(trades),
        'Win_Rate': len(wins) / len(trades) if trades else 0,
        'Avg_Win': avg_win, 'Avg_Loss': avg_loss, 'Payoff_Ratio': avg_win/avg_loss if avg_loss else 0,
        'Stop_Loss_Hits': stops, 'Signal_Exits': signal_exits,
        'ATR_Period': atr_period, 'ATR_Mult': atr_mult,
        'Num_Legs': len(leg_list) if leg_list else 0,
        'Legs': leg_list,
    }


def walk_forward_multi(data: pd.DataFrame, is_years: int = 5, oos_years: int = 2,
                         capital: float = CAPITAL, half_kelly: float = HALF_KELLY,
                         leg_list: list = None, **kwargs) -> list:
    """Walk-forward validation for multi-market portfolio."""
    dates = data.index
    start = dates[0]; end = dates[-1]
    folds = []; is_end = start + pd.DateOffset(years=is_years)
    fold_num = 0

    while is_end < end:
        oos_end = min(is_end + pd.DateOffset(years=oos_years), end)
        is_df = data.loc[start:is_end]
        oos_df = data.loc[is_end:oos_end]

        try:
            is_res = run_multi_market_backtest(is_df, capital, half_kelly, leg_list=leg_list, **kwargs)
            oos_res = run_multi_market_backtest(oos_df, capital, half_kelly, leg_list=leg_list, **kwargs)
        except Exception as e:
            print(f"  Fold {fold_num+1} failed: {e}")
            fold_num += 1
            start = is_end; is_end = start + pd.DateOffset(years=is_years)
            continue

        folds.append({
            'fold': fold_num + 1,
            'is_start': str(start.date()), 'is_end': str(is_end.date()),
            'oos_start': str(is_end.date()), 'oos_end': str(oos_end.date()),
            'is_cagr': is_res['metrics']['CAGR'],
            'oos_cagr': oos_res['metrics']['CAGR'],
            'oos_sharpe': oos_res['metrics']['Sharpe'],
            'oos_dd': oos_res['metrics']['Max_Drawdown'],
            'oos_trades': oos_res['metrics']['Total_Trades'],
        })
        fold_num += 1
        start = is_end; is_end = start + pd.DateOffset(years=is_years)

    return folds


# ═══════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    _ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    OUT = os.path.join(_ROOT, 'GOLD', 'reports')
    CHARTS = os.path.join(_ROOT, 'GOLD', 'charts')
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(CHARTS, exist_ok=True)

    # Build data
    data = build_multi_market_data()

    # Run single-market gold_jpy for comparison
    print(f"\n=== BASELINE: Single-market gold_jpy ===")
    from scripts.bt.kelly_backtest import run_backtest
    gj = pd.read_csv(os.path.join(CACHE_DIR, 'gold_jpy_daily_1971.csv'), index_col=0, parse_dates=True)
    gj = gj.sort_index().loc['1971-01-04':'2026-05-29']
    r_gj = run_backtest(gj, add_fraction=0.5, add_zone_pct=0.6, max_additions=3)
    m_gj = r_gj['metrics']
    print(f"  Gold/JPY: CAGR={m_gj['CAGR']:+.2%} | Sharpe={m_gj['Sharpe']:+.2f} | MaxDD={m_gj['Max_Drawdown']:.2%} | Trades={m_gj['Total_Trades']}")

    # Run multi-market portfolio (full history)
    print(f"\n=== MULTI-MARKET PORTFOLIO ===")
    r_mm = run_multi_market_backtest(data)
    m_mm = r_mm['metrics']
    print(f"  Multi-market: CAGR={m_mm['CAGR']:+.2%} | Sharpe={m_mm['Sharpe']:+.2f} | MaxDD={m_mm['Max_Drawdown']:.2%} | Trades={m_mm['Total_Trades']}")

    # Per-leg breakdown
    n_legs_mm = len(r_mm['metrics'].get('Legs', ['gold_jpy', 'usdjpy', 'nikkei', 'oil', 'dxy']))
    for name, eq in r_mm['leg_equities'].items():
        eq_series = pd.Series(eq, index=data.index)
        leg_start = CAPITAL / n_legs_mm
        cagr = ((eq_series.iloc[-1] / leg_start) ** (1 / ((eq_series.index[-1] - eq_series.index[0]).days / 365.25)) - 1) if eq_series.iloc[-1] > 0 else 0
        dd = abs((eq_series - eq_series.cummax()) / eq_series.cummax()).min()
        print(f"    {name}: CAGR={cagr:+.2%} | MaxDD={dd:.2%} | final={eq_series.iloc[-1]:.0f} | start={leg_start:.0f} | std={eq_series.std():.0f}")

    # Walk-forward
    print(f"\n=== Walk-forward (5y IS / 2y OOS) ===")
    folds = walk_forward_multi(data)
    for f in folds:
        print(f"  fold {f['fold']}: IS {f['is_start']}->{f['is_end']} | OOS Sharpe {f['oos_sharpe']:+.2f} | DD {f['oos_dd']:.2%} | trades {f['oos_trades']}")
    if folds:
        avg_oos = sum(f['oos_sharpe'] for f in folds) / len(folds)
        print(f"  Avg OOS Sharpe: {avg_oos:+.2f}")

    # Save results
    results = {
        'strategy': 'Multi-Market Trend-Following Portfolio',
        'legs': m_mm.get('Legs', []),
        'metrics': m_mm,
        'single_market_gold_jpy': m_gj,
        'folds': folds,
    }
    with open(os.path.join(OUT, 'multi_market_results.json'), 'w') as f:
        json.dump(results, f, default=str, indent=2)

    # Save leg equities
    leg_eq_df = pd.DataFrame(r_mm['leg_equities'])
    leg_eq_df.to_csv(os.path.join(OUT, 'multi_market_leg_equities.csv'))

    # Export trades
    export_trade_log(r_mm['trades'], os.path.join(OUT, 'multi_market_trades.csv'))

    # Plot portfolio equity curve
    port_series = pd.Series(r_mm['equity'], index=data.index)
    plot_equity_curve(port_series, 'Multi-Market', 'Multi-Market Trend-Following Portfolio',
                       os.path.join(CHARTS, 'multi_market_equity.png'))

    # Save per-leg equity charts
    for name, eq in r_mm['leg_equities'].items():
        eq_series = pd.Series(eq, index=data.index)
        if eq_series.std() > 0:
            plot_equity_curve(eq_series, name, f'{name} Leg Equity',
                              os.path.join(CHARTS, f'{name}_equity.png'))

    print(f"\nSaved to GOLD/reports/ and GOLD/charts/")
    print(f"  multi_market_results.json")
    print(f"  multi_market_leg_equities.csv")
    print(f"  multi_market_trades.csv")
    print(f"  multi_market_equity.png")