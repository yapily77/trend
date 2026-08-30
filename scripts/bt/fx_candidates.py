"""FX candidate strategy backtests vs gold/JPY baseline.

Each FX pair is tested with the SAME strategy as the baseline:
  - Signal: MA200 trend filter (long when close > MA200)
  - Stop:  3x ATR(14) from entry
  - Sizing: half-Kelly (7.81%) with 2x leverage cap
  - Exit: MA200 cross-down OR ATR stop, whichever first

Tests:
  1. USD/JPY  (1971+, the strongest trend-following FX pair)
  2. GBP/USD  (1971+)
  3. AUD/USD  (1971+)
  4. NZD/USD  (1971+)
  5. EUR/USD  (1999+)
  6. DXY      (1971+, broad dollar trend)
  7. G10 basket: equal-weight USD/JPY + GBP/USD + AUD/USD + NZD/USD

Comparison baseline: Gold/JPY, 55yr, CAGR 14.84%, Sharpe 0.74, MaxDD 47.37%
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np
import pandas as pd
from scripts.data.fred import get_series, build_jpy_usd
from scripts.bt.indicators import calculate_atr, _sma
from scripts.bt.charts import plot_equity_curve

# ── strategy constants (same as baseline) ──
HALF_KELLY = 0.0781
CAPITAL = 100000.0
ATR_PERIOD = 14
ATR_MULT = 3.0
MAX_LEVERAGE = 2.0
MA_PERIOD = 200
COMMISSION = 0.00002  # 1 bp round-turn for FX spot / futures
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'GOLD', 'reports')
CHARTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'GOLD', 'charts')
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.bt_cache')

os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(CHARTS_DIR, exist_ok=True)

# ── FX pair metadata ──
# FRED series: most are "foreign currency per USD" -> invert to get "USD per foreign currency" trading pair
# We treat each as a price series in the natural trading unit and compute returns.
FX_PAIRS = {
    'USDJPY': {'fred': 'DEXJPUS',  'invert': False, 'history': '1971+'},
    'GBPUSD': {'fred': 'DEXUSUK',  'invert': True,  'history': '1971+'},
    'AUDUSD': {'fred': 'DEXUSAL',  'invert': True,  'history': '1971+'},
    'NZDUSD': {'fred': 'DEXUSNZ',  'invert': True,  'history': '1971+'},
    'EURUSD': {'fred': 'DEXUSEU',  'invert': False, 'history': '1999+'},
    'CADUSD': {'fred': None,       'yf': 'CADUSD=X','history': '2003+'},
    'CHFUSD': {'fred': None,       'yf': 'CHFUSD=X','history': '2003+'},
    'SGDUSD': {'fred': None,       'yf': 'SGDUSD=X','history': '2003+'},
    'DXY':    {'fred': None,       'yf': 'DX-Y.NYB','history': '1971+'},
}


def load_pair(name: str) -> pd.Series | None:
    """Load an FX pair price series from cache CSV. Returns price in natural trading unit."""
    cache = None
    # Try date-stamped cache files; FX was saved via FRED (1970 prefix) or yfinance (1971 prefix).
    for suffix in ['19700101_20260601.csv', '19710101_20260601.csv', '19710101_20260530.csv',
                   '20030101_20260601.csv']:
        c = os.path.join(CACHE_DIR, f'{name}_{suffix}')
        if os.path.exists(c):
            cache = c; break
    # DXY is saved under its yfinance ticker name
    if cache is None and name == 'DXY':
        for suffix in ['19710101_20260530.csv', '19710101_20260601.csv']:
            c = os.path.join(CACHE_DIR, f'DX-Y_NYB_{suffix}')
            if os.path.exists(c):
                cache = c; break
    if cache is None:
        print(f"  {name}: no cache file")
        return None
    df = pd.read_csv(cache, index_col=0, parse_dates=True)
    price = df.iloc[:, 0]
    price = pd.to_numeric(price, errors='coerce').dropna()
    price.index = pd.to_datetime(price.index)
    price = price.sort_index()
    # For pairs quoted as "foreign per USD" (e.g. DEXUSAL = AUD per USD),
    # invert to get "USD per foreign" so we trade USD-buying-the-currency.
    # The return is the same either way; this keeps units consistent.
    if FX_PAIRS[name].get('invert'):
        price = 1.0 / price
    return price


def _make_signals(close: pd.Series, ma_period: int = MA_PERIOD) -> pd.Series:
    """MA200 signal, prior-close timing (no look-ahead)."""
    ma = close.rolling(ma_period).mean()
    sig = pd.Series(0.0, index=close.index)
    sig[close > ma] = 1.0
    return sig.shift(1).fillna(0.0)


def run_backtest(price: pd.Series, name: str) -> dict:
    """Run MA200 + half-Kelly + 3xATR stop backtest on a price series.
    Returns metrics dict."""
    # Build synthetic OHLC for ATR (use close for O/H/L; TR reduces to |close-to-close|)
    ohlc = pd.DataFrame({
        'Open': price, 'High': price, 'Low': price, 'Close': price
    })
    atr = calculate_atr(ohlc, period=ATR_PERIOD)
    sig = _make_signals(price)

    equity = np.zeros(len(price))
    cash = CAPITAL
    position = 0.0          # units held (positive = long)
    entry_price = 0.0
    current_trade = None
    trade_peak = 0.0
    trades = []
    last_reason = ''

    for i in range(len(price)):
        c = price.iloc[i]
        atr_val = atr.iloc[i] if pd.notna(atr.iloc[i]) else atr.dropna().iloc[0]
        s = sig.iloc[i]
        stop_dist = ATR_MULT * atr_val

        # EXIT: ATR stop
        if position > 0 and current_trade:
            weighted_entry = entry_price
            current_stop = weighted_entry - stop_dist
            if c <= current_stop:
                pnl = (c - weighted_entry) * position
                commission = abs(position) * c * COMMISSION
                cash += pnl - commission
                trades.append({
                    'entry_date': current_trade['entry_date'],
                    'exit_date': price.index[i],
                    'type': 'LONG', 'entry_price': entry_price, 'exit_price': c,
                    'size': position, 'pnl': pnl - commission,
                    'exit_reason': 'STOP_LOSS',
                })
                position = 0.0; entry_price = 0.0; current_trade = None; trade_peak = 0.0
                last_reason = 'STOP_LOSS'

        # ENTRY: MA200 cross from 0 -> 1
        if position == 0.0:
            now_long = s > 0
            was_long = (sig.iloc[i-1] > 0) if i > 0 else False
            if now_long and not was_long:
                entry_price = c * 1.0005  # 5bp slippage
                risk_dollars = HALF_KELLY * cash
                raw_units = risk_dollars / stop_dist if stop_dist > 0 else 0.0
                max_units = (MAX_LEVERAGE * cash) / entry_price if entry_price > 0 else 0.0
                position = min(raw_units, max_units)
                commission = position * entry_price * COMMISSION
                cash -= commission
                current_trade = {
                    'entry_date': price.index[i],
                    'type': 'LONG', 'entry_price': entry_price, 'size': position,
                }
                trade_peak = c

        # EXIT: MA200 signal goes flat
        if position > 0 and current_trade:
            now_long = s > 0
            if not now_long:
                exit_price = c * 0.9995
                pnl = (exit_price - entry_price) * position
                commission = abs(position) * exit_price * COMMISSION
                cash += pnl - commission
                trades.append({
                    'entry_date': current_trade['entry_date'],
                    'exit_date': price.index[i],
                    'type': 'LONG', 'entry_price': entry_price, 'exit_price': exit_price,
                    'size': position, 'pnl': pnl - commission,
                    'exit_reason': 'SIGNAL_EXIT',
                })
                position = 0.0; entry_price = 0.0; current_trade = None; trade_peak = 0.0
                last_reason = 'SIGNAL_EXIT'

        if position > 0:
            equity[i] = cash + (c - entry_price) * position
        else:
            equity[i] = cash

    # Force close at end
    if position > 0:
        c = price.iloc[-1]
        exit_price = c * 0.9995
        pnl = (exit_price - entry_price) * position
        commission = abs(position) * exit_price * COMMISSION
        cash += pnl - commission
        trades.append({
            'entry_date': current_trade['entry_date'], 'exit_date': price.index[-1],
            'type': 'LONG', 'entry_price': entry_price, 'exit_price': exit_price,
            'size': position, 'pnl': pnl - commission, 'exit_reason': 'END_OF_DATA',
        })

    # Metrics
    equity_s = pd.Series(equity, index=price.index)
    daily = equity_s.pct_change().fillna(0.0)
    roll_max = equity_s.cummax()
    dd = np.where(roll_max > 0, (equity_s - roll_max) / roll_max, 0.0)
    max_dd = abs(float(np.min(dd))) if len(dd) > 0 else 0.0
    days = (equity_s.index[-1] - equity_s.index[0]).days / 365.25
    final = equity_s.iloc[-1]
    cagr = ((final / CAPITAL) ** (1 / days) - 1) if (days > 0 and final > 0 and CAPITAL > 0) else 0
    mean_d = daily.mean(); std_d = daily.std()
    sharpe = (mean_d / std_d) * np.sqrt(252) if std_d > 0 else 0
    pnls = [t['pnl'] for t in trades]
    gp = sum(p for p in pnls if p > 0); gl = abs(sum(p for p in pnls if p < 0))
    pf = gp / gl if gl > 0 else (gp if gp > 0 else 1.0)
    wins = [p for p in pnls if p > 0]; losses = [p for p in pnls if p < 0]
    aw = np.mean(wins) if wins else 0; al = abs(np.mean(losses)) if losses else 0
    stops = sum(1 for t in trades if t.get('exit_reason') == 'STOP_LOSS')
    sig_exits = sum(1 for t in trades if t.get('exit_reason') == 'SIGNAL_EXIT')

    # Walk-forward (5y IS / 2y OOS)
    folds = _walk_forward(price, atr, sig, trades if False else None)

    return {
        'name': name,
        'n_bars': len(price),
        'start': str(price.index[0].date()),
        'end': str(price.index[-1].date()),
        'CAGR': cagr, 'Max_Drawdown': max_dd, 'Sharpe': sharpe,
        'Profit_Factor': pf, 'Final_Value': final,
        'Total_Trades': len(trades),
        'Win_Rate': len(wins) / len(trades) if trades else 0,
        'Avg_Win': aw, 'Avg_Loss': al, 'Payoff_Ratio': aw/al if al else 0,
        'Stop_Loss_Hits': stops, 'Signal_Exits': sig_exits,
        'folds': folds,
        'avg_oos_sharpe': (sum(f['oos_sharpe'] for f in folds) / len(folds)) if folds else 0,
        'equity': equity,
    }


def _walk_forward(price: pd.Series, atr: pd.Series, sig: pd.Series,
                  _ignored, is_years: int = 5, oos_years: int = 2) -> list:
    """Walk-forward validation on a single price series."""
    dates = price.index
    start = dates[0]; end = dates[-1]
    folds = []; is_end = start + pd.DateOffset(years=is_years); fold_num = 0
    while is_end < end:
        oos_end = min(is_end + pd.DateOffset(years=oos_years), end)
        is_df = price.loc[start:is_end]; oos_df = price.loc[is_end:oos_end]
        is_atr = atr.loc[start:is_end]; oos_atr = atr.loc[is_end:oos_end]
        is_sig = sig.loc[start:is_end]; oos_sig = sig.loc[is_end:oos_end]
        try:
            # Reuse run logic inline via a helper
            is_res = _run_slice(is_df, is_atr, is_sig)
            oos_res = _run_slice(oos_df, oos_atr, oos_sig)
            folds.append({
                'fold': fold_num + 1,
                'is_start': str(start.date()), 'is_end': str(is_end.date()),
                'oos_start': str(is_end.date()), 'oos_end': str(oos_end.date()),
                'is_cagr': is_res['CAGR'], 'is_sharpe': is_res['Sharpe'],
                'oos_cagr': oos_res['CAGR'], 'oos_sharpe': oos_res['Sharpe'],
                'oos_dd': oos_res['Max_Drawdown'], 'oos_trades': oos_res['Total_Trades'],
            })
        except Exception as e:
            print(f"    fold {fold_num+1} failed: {e}")
        fold_num += 1
        start = is_end; is_end = start + pd.DateOffset(years=is_years)
    return folds


def _run_slice(price: pd.Series, atr: pd.Series, sig: pd.Series) -> dict:
    """Run the strategy on a slice and return metrics."""
    position = 0.0; entry_price = 0.0; cash = CAPITAL
    equity = np.zeros(len(price)); trades_n = 0; wins_n = 0; losses_n = 0; wins_pnl = 0.0; losses_pnl = 0.0
    for i in range(len(price)):
        c = price.iloc[i]
        atr_val = atr.iloc[i] if pd.notna(atr.iloc[i]) else atr.dropna().iloc[0]
        s = sig.iloc[i]; stop_dist = ATR_MULT * atr_val
        if position > 0 and c <= entry_price - stop_dist:
            pnl = (c - entry_price) * position; commission = abs(position) * c * COMMISSION
            cash += pnl - commission; trades_n += 1
            if pnl > 0: wins_n += 1; wins_pnl += pnl
            else: losses_n += 1; losses_pnl += abs(pnl)
            position = 0.0; entry_price = 0.0
        if position == 0.0 and s > 0 and not (sig.iloc[i-1] > 0 if i > 0 else False):
            entry_price = c * 1.0005; risk_dollars = HALF_KELLY * cash
            raw_units = risk_dollars / stop_dist if stop_dist > 0 else 0.0
            position = min(raw_units, (MAX_LEVERAGE * cash) / entry_price)
            cash -= position * entry_price * COMMISSION
        elif position > 0 and s <= 0:
            pnl = (c - entry_price) * position; commission = abs(position) * c * COMMISSION
            cash += pnl - commission; trades_n += 1
            if pnl > 0: wins_n += 1; wins_pnl += pnl
            else: losses_n += 1; losses_pnl += abs(pnl)
            position = 0.0; entry_price = 0.0
        if position > 0: equity[i] = cash + (c - entry_price) * position
        else: equity[i] = cash
    final = equity[-1]; days = (price.index[-1] - price.index[0]).days / 365.25
    cagr = ((final / CAPITAL) ** (1 / days) - 1) if days > 0 and final > 0 else 0
    daily = pd.Series(equity, index=price.index).pct_change().fillna(0.0)
    std = daily.std()
    sharpe = (daily.mean() / std) * np.sqrt(252) if std > 0 else 0
    roll_max = pd.Series(equity, index=price.index).cummax()
    dd = (pd.Series(equity, index=price.index) - roll_max) / roll_max
    max_dd = abs(float(dd.min())) if len(dd) > 0 else 0
    pf = wins_pnl / losses_pnl if losses_pnl > 0 else (wins_pnl if wins_pnl > 0 else 1.0)
    wr = (wins_n / trades_n) if trades_n > 0 else 0
    return {'CAGR': cagr, 'Sharpe': sharpe, 'Max_Drawdown': max_dd,
            'Profit_Factor': pf, 'Total_Trades': trades_n,
            'Win_Rate': wr, 'Final_Value': final}


def build_g10_basket() -> pd.Series:
    """Equal-weight trend basket: USDJPY + GBPUSD + AUDUSD + NZDUSD (all 1971+)."""
    prices = []
    for name in ['USDJPY', 'GBPUSD', 'AUDUSD', 'NZDUSD']:
        p = load_pair(name)
        if p is not None:
            prices.append(p.rename(name))
    df = pd.concat(prices, axis=1).dropna()
    # Equal-weight log-return combination
    log_rets = np.log(df / df.shift(1)).dropna()
    basket_ret = log_rets.mean(axis=1)
    # Reconstruct a price index
    basket = np.exp(basket_ret.cumsum())
    return basket


# ── MAIN ──
if __name__ == '__main__':
    print("=" * 70)
    print("FX CANDIDATE STRATEGY BACKTEST vs Gold/JPY Baseline")
    print("Strategy: MA200 + Half-Kelly(7.81%) + 3xATR stop | 1971-2026")
    print("Baseline : Gold/JPY  CAGR=14.84% Sharpe=0.74 MaxDD=47.37%")
    print("=" * 70)

    results = {}

    # Single pairs
    for name in ['USDJPY', 'GBPUSD', 'AUDUSD', 'NZDUSD', 'EURUSD', 'DXY']:
        print(f"\n--- {name} ({FX_PAIRS[name]['history']}) ---")
        price = load_pair(name)
        if price is None or len(price) < 252:
            print(f"  Skipped: insufficient data")
            continue
        r = run_backtest(price, name)
        results[name] = {k: v for k, v in r.items() if k != 'equity'}
        print(f"  CAGR={r['CAGR']:+.2%} | Sharpe={r['Sharpe']:+.2f} | MaxDD={r['Max_Drawdown']:.2%}")
        print(f"  Trades={r['Total_Trades']} | WR={r['Win_Rate']:.1%} | PF={r['Profit_Factor']:.2f}")
        print(f"  OOS avg Sharpe={r['avg_oos_sharpe']:+.2f} | bars={r['n_bars']} ({r['start']}->{r['end']})")

    # G10 basket
    print(f"\n--- G10 BASKET (USDJPY+GBPUSD+AUDUSD+NZDUSD, equal-weight) ---")
    basket = build_g10_basket()
    r_basket = run_backtest(basket, 'G10_BASKET')
    results['G10_BASKET'] = {k: v for k, v in r_basket.items() if k != 'equity'}
    print(f"  CAGR={r_basket['CAGR']:+.2%} | Sharpe={r_basket['Sharpe']:+.2f} | MaxDD={r_basket['Max_Drawdown']:.2%}")
    print(f"  Trades={r_basket['Total_Trades']} | WR={r_basket['Win_Rate']:.1%} | PF={r_basket['Profit_Factor']:.2f}")
    print(f"  OOS avg Sharpe={r_basket['avg_oos_sharpe']:+.2f} | bars={r_basket['n_bars']} ({r_basket['start']}->{r_basket['end']})")

    # Attempt additional short-history pairs
    for name in ['CADUSD', 'CHFUSD', 'SGDUSD']:
        print(f"\n--- {name} ({FX_PAIRS[name]['history']}) ---")
        price = load_pair(name)
        if price is None or len(price) < 252:
            print(f"  Skipped: insufficient data")
            continue
        r = run_backtest(price, name)
        results[name] = {k: v for k, v in r.items() if k != 'equity'}
        print(f"  CAGR={r['CAGR']:+.2%} | Sharpe={r['Sharpe']:+.2f} | MaxDD={r['Max_Drawdown']:.2%}")
        print(f"  Trades={r['Total_Trades']} | WR={r['Win_Rate']:.1%} | PF={r['Profit_Factor']:.2f}")
        print(f"  OOS avg Sharpe={r['avg_oos_sharpe']:+.2f} | bars={r['n_bars']} ({r['start']}->{r['end']})")

    # Summary vs baseline
    baseline = {'CAGR': 0.1484, 'Sharpe': 0.74, 'Max_Drawdown': 0.4737, 'Total_Trades': 168}
    print("\n" + "=" * 70)
    print("SUMMARY vs BASELINE (Gold/JPY: CAGR 14.84% | Sharpe 0.74 | MaxDD 47.37%)")
    print("=" * 70)
    print(f"{'Strategy':<16} {'CAGR':>8} {'Sharpe':>7} {'MaxDD':>8} {'Trades':>6} {'OOS S':>7} {'History':>8}")
    print("-" * 70)
    for name in ['USDJPY', 'GBPUSD', 'AUDUSD', 'NZDUSD', 'EURUSD', 'DXY', 'G10_BASKET', 'CADUSD', 'CHFUSD', 'SGDUSD']:
        if name in results:
            r = results[name]
            ofs = r['avg_oos_sharpe']
            print(f"{name:<16} {r['CAGR']:>+8.2%} {r['Sharpe']:>+7.2f} {r['Max_Drawdown']:>8.2%} {r['Total_Trades']:>6} {ofs:>+7.2f} {r['n_bars']:>4}yr")
    print("-" * 70)
    print(f"{'BASELINE':<16} {baseline['CAGR']:>+8.2%} {baseline['Sharpe']:>+7.2f} {baseline['Max_Drawdown']:>8.2%} {baseline['Total_Trades']:>6} {'n/a':>7} {'55yr':>8}")

    # Save
    results_json = {k: {kk: vv for kk, vv in v.items() if kk != 'equity'} for k, v in results.items()}
    results_json['baseline'] = baseline
    results_json['strategy'] = 'MA200 Half-Kelly + ATR Stop (FX candidates)'
    results_json['params'] = {'half_kelly': HALF_KELLY, 'atr_period': ATR_PERIOD,
                              'atr_mult': ATR_MULT, 'max_leverage': MAX_LEVERAGE,
                              'ma_period': MA_PERIOD, 'commission': COMMISSION}
    with open(os.path.join(OUT_DIR, 'fx_candidate_results.json'), 'w') as f:
        json.dump(results_json, f, default=str, indent=2)
    print(f"\nSaved: GOLD/reports/fx_candidate_results.json")

    # Plot top candidates
    for name in ['USDJPY', 'GBPUSD', 'AUDUSD', 'NZDUSD', 'G10_BASKET', 'EURUSD', 'DXY']:
        if name in results and 'equity' in results[name]:
            eq = pd.Series(results[name]['equity'], index=price.index if name != 'G10_BASKET' else basket.index)
            plot_equity_curve(eq, name, f'MA200 HK+ATR {name}',
                              os.path.join(CHARTS_DIR, f'fx_{name.lower()}_equity.png'))
    print("Saved equity charts to GOLD/charts/")
