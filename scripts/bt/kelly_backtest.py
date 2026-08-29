"""Half-Kelly + ATR-based stop backtest on MA200 signal — GOLD/JPY.

Sizing (proper synthesis):
  Kelly f* = (p*b - q) / b. Half-Kelly = f*/2 = 7.81% target risk.
  Stop width = ATR_MULT * ATR(ATR_PERIOD) (price terms, adaptive to noise).
  Position units = (risk_fraction * capital) / stop_width.
  Leverage cap: notional = position * entry_price <= max_leverage * capital.
    -> when stop is tight, the cap reduces risk below half-Kelly (safety).
    -> when stop is wide, Kelly binds and risk approaches half-Kelly.

Gold/JPY = gold_USD (USD/oz) x USDJPY (JPY/USD).
Data starts 1971-01-04:
  - 1971-2000: monthly LBMA gold close (World Bank Pink Sheet) interpolated to daily,
    multiplied by FRED DEXJPUS daily USDJPY. OHLC = close (no intraday range).
  - 2000-2026: COMEX GC=F daily OHLC (yfinance) multiplied by FRED DEXJPUS.
  - ATR uses True Range (high-low, close-to-close gaps). Pre-2000 bars have zero
    intraday range but nonzero close-to-close TR, so ATR is still defined.
Exit: MA200 cross-down (signal -> 0) OR ATR stop from entry, whichever first.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np
import pandas as pd
from scripts.data.fred import build_gold, build_jpy_usd
from scripts.bt.reporting import generate_markdown_report, export_trade_log
from scripts.bt.charts import plot_equity_curve
import json

# ── half-Kelly constants ──
HALF_KELLY = 0.0781   # 7.81% target risk per trade
CAPITAL = 100000.0

# ── ATR-based stop draft params ──
ATR_PERIOD = 14
ATR_MULT = 3.0        # draft multiplier; tune to change risk per trade
MAX_LEVERAGE = 1.0    # cap notional at this x capital (1 = fully funded)


_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.bt_cache')

def _load_extended_gold_jpy() -> pd.DataFrame | None:
    """Load the pre-built extended gold/JPY cache if it exists and is fresh."""
    p = os.path.join(_CACHE_DIR, 'gold_jpy_daily_1971.csv')
    if os.path.exists(p):
        df = pd.read_csv(p, index_col=0, parse_dates=True)
        if not df.empty and 'Open' in df.columns:
            return df.sort_index()
    return None

def build_gold_jpy(start='1971-01-04', end='2026-05-30') -> pd.DataFrame:
    """Build gold/JPY (JPY per troy ounce) from 1971 to present.

    Two regimes are combined:
      - 1971-01 to 2000-08-29: monthly LBMA gold close (World Bank Pink Sheet,
        1833+) interpolated linearly to daily, multiplied by FRED DEXJPUS.
        OHLC = close (no intraday range); ATR still defined via close-to-close
        true range.
      - 2000-08-30 to end: COMEX GC=F daily OHLC (yfinance) multiplied by
        FRED DEXJPUS daily close.
    Gold/JPY = gold_USD_per_oz * USDJPY (JPY per USD).
    """
    cached = _load_extended_gold_jpy()
    if cached is not None:
        cached = cached.loc[start:end].copy()
        if not cached.empty:
            return cached.sort_index()

    # --- 1) Monthly gold -> daily interpolation (1971+) ---
    gold_m = pd.read_csv(
        os.path.join(_CACHE_DIR, 'gold_monthly_1833.csv'),
        index_col=0, parse_dates=True,
    )
    gold_m = gold_m.loc['1971-01':].copy()
    gold_d = gold_m.resample('D').interpolate(method='linear').ffill().bfill()
    gold_d.columns = ['Close']
    gold_d['Open'] = gold_d['Close']
    gold_d['High'] = gold_d['Close']
    gold_d['Low'] = gold_d['Close']

    # --- 2) Daily USDJPY from FRED ---
    jpy = build_jpy_usd(start='1971-01-01', end='2026-05-30')
    usdjpy = jpy['USDJPY']  # JPY per USD

    # --- 3) Pre-2000: interpolated monthly gold * USDJPY ---
    pre = gold_d.loc[:'2000-08-29'].copy()
    pre['USDJPY'] = usdjpy.loc[:'2000-08-29']
    pre['Open']  = pre['Open']  * pre['USDJPY']
    pre['High']  = pre['High']  * pre['USDJPY']
    pre['Low']   = pre['Low']   * pre['USDJPY']
    pre['Close'] = pre['Close'] * pre['USDJPY']
    pre = pre[['Open', 'High', 'Low', 'Close']]

    # --- 4) Post-2000: actual GC=F OHLC * USDJPY ---
    gc_ohlc = _ohlc_from_yfinance('GC=F', '2000-08-30', '2026-06-01')
    post = gc_ohlc.loc['2000-08-30':].copy()
    post['USDJPY'] = usdjpy.loc['2000-08-30':]
    post['Open']  = post['Open']  * post['USDJPY']
    post['High']  = post['High']  * post['USDJPY']
    post['Low']   = post['Low']   * post['USDJPY']
    post['Close'] = post['Close'] * post['USDJPY']
    post = post[['Open', 'High', 'Low', 'Close']]

    # --- 5) Combine ---
    gj = pd.concat([pre, post]).dropna()
    gj = gj.sort_index()

    # Cache for reuse
    gj.to_csv(os.path.join(_CACHE_DIR, 'gold_jpy_daily_1971.csv'))

    return gj

def _ohlc_from_yfinance(symbol: str, start: str, end: str) -> pd.DataFrame:
    """Download OHLC from yfinance, return DataFrame with Open/High/Low/Close."""
    import yfinance as yf
    df = yf.download(symbol, start=start, end=end, progress=False,
                     auto_adjust=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[['Open', 'High', 'Low', 'Close']].copy()
    df.columns = ['Open', 'High', 'Low', 'Close']
    df = df.apply(pd.to_numeric, errors='coerce').dropna()
    df.index = pd.to_datetime(df.index)
    return df.sort_index()


def atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    """True Range and its rolling average (pandas-native)."""
    d = df.copy()
    d['tr0'] = d['High'] - d['Low']
    d['tr1'] = abs(d['High'] - d['Close'].shift())
    d['tr2'] = abs(d['Low'] - d['Close'].shift())
    d['TR'] = d[['tr0', 'tr1', 'tr2']].max(axis=1)
    return d['TR'].rolling(period).mean()


def _cap_position(position: float, entry_price: float, current_equity: float,
                  max_leverage: float) -> float:
    """Cap position so notional <= max_leverage * current_equity. Return capped units."""
    max_notional = max_leverage * current_equity
    max_units = max_notional / entry_price if entry_price > 0 else position
    return min(position, max_units)


def run_backtest(gold_df: pd.DataFrame, capital: float = CAPITAL,
                 half_kelly: float = HALF_KELLY,
                 atr_period: int = ATR_PERIOD, atr_mult: float = ATR_MULT,
                 max_leverage: float = MAX_LEVERAGE,
                 ticker: str = 'XAU/JPY') -> dict:
    """Run MA200 + half-Kelly + ATR stop backtest on gold/JPY.

    Exit rules (checked each bar in priority order):
      1. ATR stop: close <= entry_price - atr_mult * ATR  -> STOP_LOSS
      2. MA200 signal goes flat -> SIGNAL_EXIT
    Entry: MA200 signal goes long (0 -> 1) and no position open.
    """
    close = gold_df['Close']
    ma = close.rolling(200).mean()
    sig = pd.Series(0.0, index=gold_df.index)
    sig[close > ma] = 1.0
    pos = sig.shift(1).fillna(0.0)
    atr_series = atr(gold_df, atr_period)

    equity = np.zeros(len(gold_df))
    cash = capital
    position = 0.0
    entry_price = 0.0
    stop_distance = 0.0
    trades = []
    current_trade = None

    for i in range(len(gold_df)):
        c = close.iloc[i]
        atr_val = atr_series.iloc[i] if pd.notna(atr_series.iloc[i]) else atr_series.dropna().iloc[0]

        # Check ATR stop on existing position
        if position > 0 and current_trade:
            adverse = entry_price - c
            if adverse >= stop_distance:
                pnl = (c - entry_price) * position
                commission = abs(position) * c * 0.00002
                cash += pnl - commission
                current_trade['exit_date'] = gold_df.index[i]
                current_trade['exit_price'] = c
                current_trade['pnl'] = pnl - commission
                current_trade['exit_reason'] = 'STOP_LOSS'
                trades.append(current_trade)
                current_trade = None
                position = 0.0
                entry_price = 0.0
                stop_distance = 0.0

        if position == 0.0:
            now_long = pos.iloc[i] > 0
            was_long = (pos.iloc[i-1] > 0) if i > 0 else False
            if now_long and not was_long:
                entry_price = c * 1.0005        # slippage ~5bp on entry
                risk_dollars = half_kelly * cash
                stop_distance = atr_mult * atr_val
                # raw Kelly position
                raw_units = risk_dollars / stop_distance if stop_distance > 0 else 0.0
                # cap leverage against current equity (cash)
                position = _cap_position(raw_units, entry_price, cash, max_leverage)
                actual_risk = position * stop_distance
                commission = position * entry_price * 0.00002
                cash -= commission
                current_trade = {
                    'entry_date': gold_df.index[i],
                    'type': 'LONG',
                    'entry_price': entry_price,
                    'size': position,
                    'notional': position * entry_price,
                    'risk_dollars': actual_risk,
                    'stop_distance': stop_distance,
                    'atr': atr_val,
                    'risk_pct': actual_risk / cash if cash > 0 else 0,
                    'raw_units': raw_units,
                    'lev_capped': raw_units > position,
                }
        else:
            pass

        # Close on MA200 signal going flat
        if position > 0 and current_trade:
            now_long = pos.iloc[i] > 0
            if not now_long:
                exit_price = c * 0.9995
                pnl = (exit_price - entry_price) * position
                commission = abs(position) * exit_price * 0.00002
                cash += pnl - commission
                current_trade['exit_date'] = gold_df.index[i]
                current_trade['exit_price'] = exit_price
                current_trade['pnl'] = pnl - commission
                current_trade['exit_reason'] = 'SIGNAL_EXIT'
                trades.append(current_trade)
                current_trade = None
                position = 0.0
                entry_price = 0.0
                stop_distance = 0.0

        if position > 0:
            equity[i] = cash + (c - entry_price) * position
        else:
            equity[i] = cash

    # Force close at end
    if position > 0 and current_trade:
        c = close.iloc[-1]
        exit_price = c * 0.9995
        pnl = (exit_price - entry_price) * position
        commission = abs(position) * exit_price * 0.00002
        cash += pnl - commission
        current_trade['exit_date'] = gold_df.index[-1]
        current_trade['exit_price'] = exit_price
        current_trade['pnl'] = pnl - commission
        current_trade['exit_reason'] = 'END_OF_DATA'
        trades.append(current_trade)
        equity[-1] = cash

    df = gold_df.copy()
    df['Equity'] = equity
    df['Daily_Return'] = df['Equity'].pct_change().fillna(0.0)
    metrics = _metrics(df, trades, capital, atr_period, atr_mult, max_leverage)
    return {'metrics': metrics, 'equity': df['Equity'], 'trades': trades,
            'signal': sig}


def _metrics(df: pd.DataFrame, trades: list[dict], capital: float,
             atr_period: int, atr_mult: float, max_leverage: float) -> dict:
    equity = df['Equity']
    daily = df['Daily_Return']
    roll_max = equity.cummax()
    dd = (equity - roll_max) / roll_max
    max_dd = dd.min()
    days = (equity.index[-1] - equity.index[0]).days / 365.25
    final = equity.iloc[-1]
    cagr = (final / capital) ** (1 / days) - 1 if days > 0 else 0
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
    risk_pcts = [t.get('risk_pct', 0) for t in trades if 'risk_pct' in t]
    stop_widths = [t.get('stop_distance', 0) for t in trades if 'stop_distance' in t]
    capped_frac = sum(1 for t in trades if t.get('lev_capped', False)) / len(trades) if trades else 0
    return {
        'CAGR': cagr, 'Max_Drawdown': max_dd, 'Sharpe': sharpe,
        'Profit_Factor': pf, 'Final_Value': final, 'Total_Trades': len(trades),
        'Win_Rate': len(wins) / len(trades) if trades else 0,
        'Avg_Win': avg_win, 'Avg_Loss': avg_loss, 'Payoff_Ratio': avg_win/avg_loss if avg_loss else 0,
        'Stop_Loss_Hits': stops, 'Signal_Exits': signal_exits,
        'Avg_Stop_Width': np.mean(stop_widths) if stop_widths else 0,
        'Avg_Risk_Per_Trade': np.mean(risk_pcts) if risk_pcts else 0,
        'ATR_Period': atr_period, 'ATR_Mult': atr_mult, 'Max_Leverage': max_leverage,
        'Lev_Capped_Pct': capped_frac,
    }


def walk_forward(gold_df, is_years=5, oos_years=2, capital=CAPITAL,
                 half_kelly=HALF_KELLY, atr_period=ATR_PERIOD, atr_mult=ATR_MULT,
                 max_leverage=MAX_LEVERAGE):
    dates = gold_df.index
    start = dates[0]; end = dates[-1]
    folds = []; is_end = start + pd.DateOffset(years=is_years)
    fold_num = 0
    while is_end < end:
        oos_end = min(is_end + pd.DateOffset(years=oos_years), end)
        is_df = gold_df.loc[start:is_end]
        oos_df = gold_df.loc[is_end:oos_end]
        is_res = run_backtest(is_df, capital, half_kelly, atr_period, atr_mult, max_leverage)
        oos_res = run_backtest(oos_df, capital, half_kelly, atr_period, atr_mult, max_leverage)
        folds.append({
            'fold': fold_num + 1,
            'is_start': str(start.date()), 'is_end': str(is_end.date()),
            'oos_start': str(is_end.date()), 'oos_end': str(oos_end.date()),
            'is_metrics': is_res['metrics'], 'oos_metrics': oos_res['metrics'],
            'is_cagr': is_res['metrics']['CAGR'],
            'oos_cagr': oos_res['metrics']['CAGR'],
            'oos_sharpe': oos_res['metrics']['Sharpe'],
            'oos_dd': oos_res['metrics']['Max_Drawdown'],
            'oos_trades': oos_res['metrics']['Total_Trades'],
        })
        fold_num += 1
        start = is_end; is_end = start + pd.DateOffset(years=is_years)
    return folds


def atr_sweep(gold_df, half_kelly=HALF_KELLY, capital=CAPITAL):
    """Show how ATR multiple trades off risk/trade, leverage cap, and equity quality."""
    print(f"\n{'ATRx':>5} | {'Sharpe':>6} | {'CAGR':>7} | {'DD':>7} | {'Stops':>5} | {'SigEx':>5} | {'Risk/tr':>7} | {'Capped':>6} | {'Final$':>11}")
    print('-' * 105)
    for mult in [1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.7]:
        r = run_backtest(gold_df, half_kelly=half_kelly, atr_mult=mult)
        m = r['metrics']
        print(f"{mult:5.1f} | {m['Sharpe']:+.2f} | {m['CAGR']:+.2%} | {m['Max_Drawdown']:>6.2%} | {m['Stop_Loss_Hits']:5d} | {m['Signal_Exits']:5d} | {m['Avg_Risk_Per_Trade']:>6.2%} | {m['Lev_Capped_Pct']:>5.0%} | ${m['Final_Value']:>10,.0f}")


if __name__ == '__main__':
    _ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    OUT = os.path.join(_ROOT, 'GOLD', 'reports')
    CHARTS = os.path.join(_ROOT, 'GOLD', 'charts')
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(CHARTS, exist_ok=True)

    # Build gold/JPY = gold_USD x USDJPY, daily from 1971
    gold_jpy = build_gold_jpy()
    print(f"Gold/JPY built: {gold_jpy.shape[0]} rows, "
          f"{gold_jpy.index[0].date()} -> {gold_jpy.index[-1].date()} "
          f"({round((gold_jpy.index[-1] - gold_jpy.index[0]).days / 365.25, 1)} yrs)")
    print(f"  Sample close JPY/oz: {gold_jpy['Close'].iloc[0]:,.0f} -> {gold_jpy['Close'].iloc[-1]:,.0f}")
    print(f"  Pre-2000 bars (monthly interp): {(gold_jpy.index < pd.Timestamp('2000-08-30')).sum()}")
    print(f"  Post-2000 bars (GC=F OHLC): {(gold_jpy.index >= pd.Timestamp('2000-08-30')).sum()}")
    print()

    # ATR sweep
    print(f"=== MA200 + Half-Kelly (7.8%) + ATR({ATR_PERIOD}) sweep, 1x leverage cap ===")
    atr_sweep(gold_jpy)

    # Draft run: ATR(14), 3x, 1x leverage
    print(f"\n=== DRAFT: MA200 + Half-Kelly (7.8%) + {ATR_MULT}xATR({ATR_PERIOD}) Stop ===")
    r = run_backtest(gold_jpy)
    m = r['metrics']
    print(f"  Sharpe={m['Sharpe']:+.2f}  CAGR={m['CAGR']:+.2%}  Trades={m['Total_Trades']}  DD={m['Max_Drawdown']:.2%}")
    print(f"  WinRate={m['Win_Rate']:.1%}  Payoff={m['Payoff_Ratio']:.2f}x  PF={m['Profit_Factor']:.2f}")
    print(f"  Final=${m['Final_Value']:,.0f}  Stops={m['Stop_Loss_Hits']}  SigExits={m['Signal_Exits']}")
    print(f"  Avg Win=${m['Avg_Win']:,.0f}  Avg Loss=${m['Avg_Loss']:,.0f}")
    print(f"  Avg stop width={m['Avg_Stop_Width']:,.0f}  ({m['ATR_Mult']:.1f}xATR)")
    print(f"  Avg risk/trade={m['Avg_Risk_Per_Trade']:.2%}  (half-Kelly target={HALF_KELLY:.2%})")
    print(f"  Leverage capped in {m['Lev_Capped_Pct']:.0%} of trades")
    print()
    print("=== Walk-forward (5y IS / 2y OOS) ===")
    folds = walk_forward(gold_jpy)
    for f in folds:
        print(f"  fold {f['fold']}: IS {f['is_start']}->{f['is_end']} | OOS {f['oos_start']}->{f['oos_end']} | Sharpe {f['oos_sharpe']:+.2f} | DD {f['oos_dd']:.2%} | trades {f['oos_trades']}")
    avg_oos = sum(f['oos_sharpe'] for f in folds) / len(folds)
    print(f"  Avg OOS Sharpe: {avg_oos:+.2f}")

    with open(os.path.join(OUT, 'gold_jpy_kelly_folds.json'), 'w') as f:
        json.dump(folds, f, default=str, indent=2)
    export_trade_log(r['trades'], os.path.join(OUT, 'gold_jpy_kelly_trades.csv'))
    plot_equity_curve(r['equity'], 'XAU/JPY', 'MA200 Half-Kelly + ATR Stop',
                      os.path.join(CHARTS, 'gold_jpy_kelly_equity.png'))
    generate_markdown_report(m, folds, 'XAU/JPY', 'MA200 Half-Kelly + ATR Stop (Gold/JPY)',
                             os.path.join(OUT, 'gold_jpy_kelly_report.md'))

    results = {
        'strategy': 'MA200 Half-Kelly + ATR Stop (Gold/JPY)',
        'half_kelly': HALF_KELLY,
        'atr_period': ATR_PERIOD,
        'atr_mult': ATR_MULT,
        'max_leverage': MAX_LEVERAGE,
        'metrics': m,
        'folds': folds,
    }
    with open(os.path.join(OUT, 'gold_jpy_kelly_results.json'), 'w') as f:
        json.dump(results, f, default=str, indent=2)
    print("\nSaved to GOLD/reports/ and GOLD/charts/")
