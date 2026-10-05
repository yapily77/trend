"""Stage 1: Strategy Parameter Mutation Sweep

Tests systematic parameter variations of canonical strategies on the strongest
underlying markets (gold_jpy, USDJPY, CL=F).

For each mutation x market combo:
  - 3-year expanding IS / 1-year OOS walk-forward
  - Prior-close signal timing
  - Metrics: CAGR, Sharpe, MaxDD, Total Trades, OOS Sharpe, OOS MaxDD, PF, Win Rate

Output: /home/yapilwsl/arthityap/trend/.bt_cache/stage1_mutations.json
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np
import pandas as pd
import json

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.bt_cache')
OUT_PATH = os.path.join(CACHE_DIR, 'stage1_mutations.json')

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_gold_jpy():
    return pd.read_csv(os.path.join(CACHE_DIR, 'gold_jpy_daily_1971.csv'),
                        index_col=0, parse_dates=True).sort_index()

def load_usdjpy():
    df = pd.read_csv(os.path.join(CACHE_DIR, 'USDJPY_19710101_20260530.csv'),
                      index_col=0, parse_dates=True).sort_index()
    df.columns = ['Close']
    return df

def load_clf():
    df = pd.read_csv(os.path.join(CACHE_DIR, 'CL_F_19710101_20260530.csv'),
                      index_col=0, parse_dates=True).sort_index()
    df.columns = ['Close']
    return df

MARKETS = {'gold_jpy': load_gold_jpy, 'usdjpy': load_usdjpy, 'clf': load_clf}

# ---------------------------------------------------------------------------
# Indicators
# ---------------------------------------------------------------------------
def calc_atr_ohlc(df, period=14):
    high, low, close = df['High'], df['Low'], df['Close']
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def calc_atr_close(series, period=14):
    return series.diff().abs().rolling(period).mean()

def get_atr(df, market, period=14):
    if market == 'gold_jpy':
        return calc_atr_ohlc(df, period)
    return calc_atr_close(df['Close'], period)

# ---------------------------------------------------------------------------
# Strategy signal generators  (accept DataFrame, return Series of 0/1/-1)
# ---------------------------------------------------------------------------
def sig_ma200(df, period):
    close = df['Close']
    ma = close.rolling(period).mean()
    s = pd.Series(0.0, index=close.index)
    s[close > ma] = 1.0
    return s

def sig_donchian(df, period):
    close, high, low = df['Close'], df['High'], df['Low']
    upper = high.rolling(period).max()
    lower = low.rolling(period).min()
    s = pd.Series(0, index=close.index)
    for i in range(len(close)):
        c = close.iloc[i]
        u = upper.iloc[i] if pd.notna(upper.iloc[i]) else np.nan
        l = lower.iloc[i] if pd.notna(lower.iloc[i]) else np.nan
        if pd.isna(u) or pd.isna(l):
            continue
        if c > u:
            s.iloc[i] = 1
        elif c < l:
            s.iloc[i] = -1
    return s

def sig_kama(df, period, fast, slow):
    close = df['Close']
    direction = close.abs().diff(period)
    volatility = close.diff().abs().rolling(window=period).sum()
    er = direction / volatility.replace(0, np.nan)
    fast_ema = 2.0 / (fast + 1)
    slow_ema = 2.0 / (slow + 1)
    sc = (er * (fast_ema - slow_ema) + slow_ema) ** 2
    arr = close.values
    kama = np.full(len(arr), np.nan)
    if len(arr) > period:
        kama[period - 1] = arr[period - 1]
        for i in range(period, len(arr)):
            alpha = float(sc.iloc[i]) if hasattr(sc, 'iloc') else float(sc[i])
            alpha = max(0.0, min(1.0, alpha))
            kama[i] = kama[i - 1] + alpha * (arr[i] - kama[i - 1])
    kama_s = pd.Series(kama, index=close.index)
    s = pd.Series(0.0, index=close.index)
    s[kama_s.diff() > 0] = 1.0
    s[kama_s.diff() < 0] = -1.0
    return s

# ---------------------------------------------------------------------------
# Backtest engine: prior-close timing, optional ATR stop
# ---------------------------------------------------------------------------
def backtest_one(df, signal_s, capital, risk_per_trade,
                 atr_mult=None, is_fx=True, commission_pct=0.00002,
                 slippage_pips=2.0, commodity_slippage_pct=0.0005,
                 max_leverage=2.0):
    """
    Run a single backtest with prior-close signal timing.
    position[i] = signal[i-1].
    Half-Kelly sizing: units = (risk_per_trade * capital) / (2 * ATR_14).
    Position capped so notional <= max_leverage * capital.
    Optional hard ATR stop: close at entry_price - atr_mult*atr (long).
    """
    close = df['Close'].values.astype(float)
    if 'High' in df.columns and 'Low' in df.columns:
        high, low = df['High'].values, df['Low'].values
        tr1 = high - low
        tr2 = np.abs(high - np.concatenate([[close[0]], close[:-1]]))
        tr3 = np.abs(low - np.concatenate([[close[0]], close[:-1]]))
        tr = np.maximum(np.maximum(tr1, tr2), tr3)
        atr_raw = pd.Series(tr).rolling(14).mean().values
    else:
        atr_raw = pd.Series(np.abs(np.diff(close, prepend=close[0]))).rolling(14).mean().values
    atr = atr_raw.astype(float)
    # Floor: prevent explosive position sizes when ATR is near zero
    # (e.g., pegged FX years, interpolated monthly bars with zero TR).
    # Caps effective leverage at ~3.9x regardless of market.
    # Fill NaN ATR (first 14 bars) with first valid value
    atr_valid = atr[~np.isnan(atr)]
    atr_fill = atr_valid[0] if len(atr_valid) > 0 else 1.0
    atr = np.where(np.isnan(atr), atr_fill, atr)
    # Floor: prevent explosive position sizes when ATR is near zero
    atr = np.maximum(atr, 0.01 * close)
    sig = signal_s.values.astype(float)
    n = len(close)

    # Fill NaN ATR
    atr_valid = atr[~np.isnan(atr)]
    atr_fill = atr_valid[0] if len(atr_valid) > 0 else 1.0
    atr = np.where(np.isnan(atr), atr_fill, atr)
    atr = np.maximum(atr, 1e-6)

    equity = np.zeros(n)
    cash = float(capital)
    position = 0.0
    entry_price = 0.0
    trades = []
    cur_trade = None

    for i in range(n):
        c = close[i]
        a = atr[i]
        s = sig[i]

        # ---- EXIT: ATR stop (hard) ----
        if position != 0.0 and atr_mult is not None and cur_trade is not None:
            stop_dist = atr_mult * a
            if position > 0 and c <= entry_price - stop_dist:
                pnl = (c - entry_price) * position
                comm = abs(position) * c * commission_pct
                slip = slippage_pips * 0.01 * abs(position) if is_fx \
                       else c * commodity_slippage_pct * abs(position)
                cash += pnl - comm - slip
                trades.append(dict(entry_date=cur_trade['entry_date'],
                                   exit_date=i, exit_reason='STOP_LOSS',
                                   pnl=pnl, size=abs(position)))
                cur_trade = None; position = 0.0; entry_price = 0.0

        # ---- EXIT: opposite / flat signal ----
        if position != 0.0 and cur_trade is not None:
            flat_exit = (s == 0 and position != 0)
            opposite_exit = (position > 0 and s < 0) or (position < 0 and s > 0)
            if flat_exit or opposite_exit:
                exit_p = c
                comm = abs(position) * exit_p * commission_pct
                slip = slippage_pips * 0.01 * abs(position) if is_fx \
                       else exit_p * commodity_slippage_pct * abs(position)
                pnl = (exit_p - entry_price) * position - comm - slip
                cash += pnl
                trades.append(dict(entry_date=cur_trade['entry_date'],
                                   exit_date=i, exit_reason='SIGNAL_EXIT',
                                   pnl=pnl, size=abs(position)))
                cur_trade = None; position = 0.0; entry_price = 0.0

        # ---- ENTRY ----
        if position == 0.0 and cur_trade is None and s != 0:
            # Entry at current bar (signal fired on prior close)
            if s > 0:
                entry_price = c * (1 + (slippage_pips * 0.01 if is_fx else commodity_slippage_pct))
                pos_dir = 1.0
            else:
                entry_price = c * (1 - (slippage_pips * 0.01 if is_fx else commodity_slippage_pct))
                pos_dir = -1.0

            # Half-Kelly sizing: units = (risk * capital) / (2 * ATR)
            denom = 2.0 * a
            units_raw = (risk_per_trade * capital) / denom * pos_dir
            # Cap notional at max_leverage * capital
            max_units = (max_leverage * capital) / c
            units = max(-max_units, min(max_units, units_raw))
            comm = abs(units) * entry_price * commission_pct
            cash -= comm
            position = units
            cur_trade = dict(entry_date=i, type='LONG' if s > 0 else 'SHORT',
                             entry_price=entry_price, size=abs(units))

        # Equity
        if position != 0.0:
            equity[i] = cash + (c - entry_price) * position
        else:
            equity[i] = cash

    # Force close at end
    if position != 0.0 and cur_trade is not None:
        c = close[-1]
        comm = abs(position) * c * commission_pct
        slip = slippage_pips * 0.01 * abs(position) if is_fx \
               else c * commodity_slippage_pct * abs(position)
        pnl = (c - entry_price) * position - comm - slip
        cash += pnl
        trades.append(dict(entry_date=cur_trade['entry_date'],
                           exit_date=n - 1, exit_reason='END_OF_DATA',
                           pnl=pnl, size=abs(position)))

    # Metrics
    eq = pd.Series(equity)
    daily = eq.pct_change().fillna(0.0)
    roll_max = eq.cummax()
    max_dd = abs(float((eq / roll_max - 1).min()))
    days = n / 252.0
    final = eq.iloc[-1]
    cagr = ((final / capital) ** (1.0 / days) - 1.0) if final > 0 and days > 0 else 0.0
    mean_r = daily.mean(); std_r = daily.std()
    sharpe = (mean_r / std_r) * np.sqrt(252) if std_r > 0 else 0.0

    pnls = [t['pnl'] for t in trades]
    gp = sum(p for p in pnls if p > 0)
    gl = abs(sum(p for p in pnls if p < 0))
    pf = gp / gl if gl > 0 else (gp if gp > 0 else 1.0)
    wins = sum(1 for p in pnls if p > 0)
    wr = wins / len(pnls) if pnls else 0.0

    return dict(CAGR=cagr, Sharpe=sharpe, MaxDD=max_dd, Profit_Factor=pf,
                Win_Rate=wr, Total_Trades=len(trades), Final_Value=final), trades


def walk_forward(df, signal_fn, capital, risk_per_trade,
                 atr_mult=None, is_fx=True, commission_pct=0.00002,
                 slippage_pips=2.0, commodity_slippage_pct=0.0005,
                 is_years=3, oos_years=1):
    """3-year expanding IS / 1-year OOS walk-forward.
    signal_fn(df) -> signal Series.
    """
    close = df['Close']
    n = len(close)
    min_bars = (is_years + oos_years) * 252
    if n < min_bars:
        return []

    folds = []
    is_end = is_years * 252
    fold_num = 0

    while is_end + oos_years * 252 <= n:
        # IS window [0 : is_end)
        is_df = df.iloc[:is_end]
        is_sig = signal_fn(is_df)
        im, _ = backtest_one(is_df, is_sig, capital, risk_per_trade,
                             atr_mult=atr_mult, is_fx=is_fx,
                             commission_pct=commission_pct, slippage_pips=slippage_pips,
                             commodity_slippage_pct=commodity_slippage_pct,
                             max_leverage=2.0)

        # OOS window [is_end : is_end + oos_years)
        oos_end = is_end + oos_years * 252
        oos_df = df.iloc[is_end:oos_end]
        oos_sig = signal_fn(oos_df)
        om, _ = backtest_one(oos_df, oos_sig, capital, risk_per_trade,
                             atr_mult=atr_mult, is_fx=is_fx,
                             commission_pct=commission_pct, slippage_pips=slippage_pips,
                             commodity_slippage_pct=commodity_slippage_pct,
                             max_leverage=2.0)

        folds.append(dict(is_metrics=im, oos_metrics=om,
                          oos_sharpe=om['Sharpe'], oos_maxdd=om['MaxDD'],
                          oos_cagr=om['CAGR'], oos_trades=om['Total_Trades']))
        fold_num += 1
        is_end += oos_years * 252

    return folds


# ---------------------------------------------------------------------------
# Mutation definitions
# ---------------------------------------------------------------------------
def build_mutations():
    muts = []
    # MA200: 50, 100, 200, 300 on all three markets (baseline risk 0.0781)
    for mkt in ['gold_jpy', 'usdjpy', 'clf']:
        for p in [50, 100, 200, 300]:
            muts.append(dict(market=mkt, strategy='MA200', mutation=f'ma_period_{p}',
                             kind='ma200', period=p, atr_mult=None, risk=0.0781))
    # Donchian: 10,15,20,30,50 on gold_jpy, USDJPY
    for mkt in ['gold_jpy', 'usdjpy']:
        for p in [10, 15, 20, 30, 50]:
            muts.append(dict(market=mkt, strategy='Donchian', mutation=f'donchian_period_{p}',
                             kind='donchian', period=p, atr_mult=None, risk=0.0781))
    # KAMA: (10,2,30), (20,2,60), (5,2,20), (10,3,50) on gold_jpy, USDJPY
    for mkt in ['gold_jpy', 'usdjpy']:
        for p, f, s in [(10,2,30),(20,2,60),(5,2,20),(10,3,50)]:
            muts.append(dict(market=mkt, strategy='KAMA', mutation=f'kama_{p}_{f}_{s}',
                             kind='kama', period=p, fast=f, slow=s, atr_mult=None, risk=0.0781))
    # ATR stop mult: 1.5,2.0,3.0,4.0,5.0 on gold_jpy, USDJPY (MA200 + ATR stop, period=200)
    for mkt in ['gold_jpy', 'usdjpy']:
        for am in [1.5, 2.0, 3.0, 4.0, 5.0]:
            muts.append(dict(market=mkt, strategy='MA200_ATR', mutation=f'atr_mult_{am}',
                             kind='ma200_atr', period=200, atr_mult=am, risk=0.0781))
    # Risk per trade: 0.0391, 0.0781, 0.15625 on gold_jpy, USDJPY (MA200 period=200)
    for mkt in ['gold_jpy', 'usdjpy']:
        for r in [0.0391, 0.0781, 0.15625]:
            muts.append(dict(market=mkt, strategy='MA200', mutation=f'risk_{r}',
                             kind='ma200', period=200, atr_mult=None, risk=r))
    return muts


def make_signal_fn(mut):
    """Return fn(df) -> signal Series."""
    kind = mut['kind']
    if kind == 'ma200':
        p = mut['period']
        return lambda df: sig_ma200(df, p)
    elif kind == 'donchian':
        p = mut['period']
        return lambda df: sig_donchian(df, p)
    elif kind == 'kama':
        p, f, s = mut['period'], mut['fast'], mut['slow']
        return lambda df: sig_kama(df, p, f, s)
    elif kind == 'ma200_atr':
        p = mut['period']
        return lambda df: sig_ma200(df, p)
    raise ValueError(kind)


def run_mutation(mut):
    """Run full-history IS + walk-forward for one mutation."""
    mkt = mut['market']
    df = MARKETS[mkt]()
    signal_fn = make_signal_fn(mut)
    capital = 100000.0
    risk = mut['risk']
    atr_mult = mut['atr_mult']
    is_fx = (mkt == 'usdjpy')

    # Full-history IS
    is_sig = signal_fn(df)
    im, _ = backtest_one(df, is_sig, capital, risk,
                         atr_mult=atr_mult, is_fx=is_fx, max_leverage=2.0)

    # Walk-forward
    folds = walk_forward(df, signal_fn, capital, risk,
                         atr_mult=atr_mult, is_fx=is_fx)

    if folds:
        avg_oos_sharpe = float(np.mean([f['oos_sharpe'] for f in folds]))
        avg_oos_maxdd = float(np.mean([f['oos_maxdd'] for f in folds]))
        avg_oos_cagr = float(np.mean([f['oos_cagr'] for f in folds]))
        n_folds = len(folds)
    else:
        avg_oos_sharpe = 0.0
        avg_oos_maxdd = 0.0
        avg_oos_cagr = 0.0
        n_folds = 0

    passes = (avg_oos_sharpe >= 0.4 and avg_oos_maxdd <= 0.30)

    return dict(
        market=mkt, strategy=mut['strategy'], mutation=mut['mutation'],
        is_sharpe=round(im['Sharpe'], 4),
        oos_sharpe=round(avg_oos_sharpe, 4),
        cagr=round(im['CAGR'], 4),
        maxdd=round(im['MaxDD'], 4),
        trades=im['Total_Trades'],
        pf=round(im['Profit_Factor'], 4),
        win_rate=round(im['Win_Rate'], 4),
        oos_maxdd=round(avg_oos_maxdd, 4),
        avg_oos_cagr=round(avg_oos_cagr, 4),
        n_folds=n_folds,
        passes_gate=passes,
    )


def main():
    muts = build_mutations()
    print(f"Total mutations to run: {len(muts)}")
    results = []

    for idx, mut in enumerate(muts):
        r = run_mutation(mut)
        results.append(r)
        status = 'PASS' if r['passes_gate'] else 'FAIL'
        print(f"[{idx+1}/{len(muts)}] {r['market']:8s} {r['strategy']:10s} {r['mutation']:18s} | "
              f"IS {r['is_sharpe']:+.2f} OOS {r['oos_sharpe']:+.2f} | "
              f"CAGR {r['cagr']:+.1%} MD {r['maxdd']:.1%} | "
              f"T{r['trades']:>4d} PF {r['pf']:.2f} | {status}")

    with open(OUT_PATH, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved {len(results)} results to {OUT_PATH}")

    # Summary table
    print("\n" + "=" * 130)
    print(f"{'Market':8s} | {'Strategy':10s} | {'Mutation':18s} | {'CAGR':>7s} | {'Sharpe':>6s} | {'MaxDD':>7s} | {'Trades':>5s} | {'PF':>5s} | {'Win%':>5s} | {'OOS Sharpe':>10s} | {'OOS MaxDD':>9s} | {'Pass?':>5s}")
    print("-" * 130)
    for r in results:
        print(f"{r['market']:8s} | {r['strategy']:10s} | {r['mutation']:18s} | "
              f"{r['cagr']:>+6.1%} | {r['is_sharpe']:>+.2f} | {r['maxdd']:>6.1%} | "
              f"{r['trades']:>5d} | {r['pf']:>5.2f} | {r['win_rate']:>5.1%} | "
              f"{r['oos_sharpe']:>+.9f} | {r['oos_maxdd']:>8.1%} | {'PASS' if r['passes_gate'] else 'FAIL':>5s}")
    print("=" * 130)

    n_pass = sum(1 for r in results if r['passes_gate'])
    print(f"\nMutations passing gate: {n_pass}/{len(results)} ({100*n_pass/len(results):.1f}%)")
    print("\n--- PASSING mutations ---")
    for r in results:
        if r['passes_gate']:
            print(f"  {r['market']}/{r['strategy']}/{r['mutation']}: "
                  f"IS {r['is_sharpe']:+.2f} OOS {r['oos_sharpe']:+.2f} "
                  f"CAGR {r['cagr']:+.1%} MD {r['maxdd']:.1%} "
                  f"OOS MD {r['oos_maxdd']:.1%}")


if __name__ == '__main__':
    main()
