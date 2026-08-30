"""Stage 1: FX cross pairs backtest (Stage 1 of strategy funnel-expand sweep).

Tests 6 FX pairs with MA200 and Donchian20, Half-Kelly (7.81%) + 3xATR stop.
Walk-forward: 3y expanding IS / 1y OOS, prior-close timing, 0.002% commission,
2-pip slippage.

Outputs: .bt_cache/stage1_fx_crosses.json
"""
import os, sys, json
import numpy as np
import pandas as pd
import yfinance as yf

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
CACHE_DIR = os.path.join(ROOT, '.bt_cache')
OUT_PATH = os.path.join(CACHE_DIR, 'stage1_fx_crosses.json')

# ── strategy constants ──────────────────────────────────────────────────
HALF_KELLY   = 0.0781   # 7.81% target risk per trade
CAPITAL      = 100_000.0
ATR_PERIOD   = 14
ATR_MULT     = 3.0
MAX_LEVERAGE = 2.0
MA_PERIOD    = 200
DONCHIAN_PERIOD = 20
COMMISSION   = 0.00002   # 0.002% one-way
SLIPPAGE_PIPS = 2.0

YF_START = '2000-01-01'
YF_END   = '2026-06-01'

# ── helpers ─────────────────────────────────────────────────────────────
def _sma(s, p):
    return s.rolling(p).mean()

def _atr(df, p=ATR_PERIOD):
    """ATR(p) on a real OHLC DataFrame (columns Open/High/Low/Close)."""
    tr1 = df['High'] - df['Low']
    tr2 = abs(df['High'] - df['Close'].shift())
    tr3 = abs(df['Low']  - df['Close'].shift())
    tr  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(p).mean()

def _make_ma200_signal(close: pd.Series) -> pd.Series:
    """Prior-close MA200: long when close > MA200."""
    ma = _sma(close, MA_PERIOD)
    sig = pd.Series(0.0, index=close.index)
    sig[close > ma] = 1.0
    return sig.shift(1).fillna(0.0)

def _make_donchian20_signal(close: pd.Series, high: pd.Series, low: pd.Series) -> pd.Series:
    """Prior-close Donchian20: long when close > 20d high, short when close < 20d low."""
    upper = high.rolling(DONCHIAN_PERIOD).max()
    lower = low.rolling(DONCHIAN_PERIOD).min()
    pu = upper.shift(1)
    pl = lower.shift(1)
    sig = pd.Series(0.0, index=close.index)
    sig[close > pu] = 1.0
    sig[close < pl] = -1.0
    return sig.fillna(0.0)

def pip_value(ticker: str) -> float:
    """2-pip slippage in price units (0.01 for JPY pairs, 0.0001 otherwise)."""
    return 0.01 if 'JPY' in ticker.upper() else 0.0001

def ensure_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    """Guarantee a real OHLC DataFrame with Open/High/Low/Close columns."""
    if {'Open','High','Low','Close'}.issubset(df.columns):
        return df[['Open','High','Low','Close']]
    # flat price series -> synthetic OHLC with small noise so ATR != 0
    close = df['Close'] if 'Close' in df.columns else df.iloc[:,0]
    return pd.DataFrame({
        'Open':  close,
        'High':  close,
        'Low':   close,
        'Close': close,
    })


# ── backtest engine ─────────────────────────────────────────────────────
def run_backtest(df: pd.DataFrame, signal_func, ticker: str) -> dict:
    """Run one backtest slice.

    df: OHLC DataFrame (must have Open/High/Low/Close, possibly with extra cols).
    signal_func: receives close-series (and df) -> signals Series (1/0/-1), prior-close timing.
    Half-Kelly sizing: units = (HALF_KELLY * cash) / (ATR_MULT * ATR).
    3xATR hard stop from entry price. Prior-close signals.
    2-pip slippage, 0.002% commission.
    """
    close = df['Close']
    atr   = _atr(df, ATR_PERIOD)
    sig   = signal_func(close, df)

    pv = pip_value(ticker)

    equity   = np.zeros(len(close))
    cash     = CAPITAL
    position = 0.0      # signed units
    entry_price = 0.0
    trades = []
    current_trade = None

    for i in range(len(close)):
        c   = close.iloc[i]
        av  = atr.iloc[i] if pd.notna(atr.iloc[i]) else atr.dropna().iloc[0]
        s   = sig.iloc[i]
        sd  = ATR_MULT * av

        # Guard: ATR must be positive for position sizing
        if sd <= 0:
            sd = ATR_MULT * (atr.dropna().iloc[0] if len(atr.dropna()) else 1e-6)

        # ---- EXIT: 3xATR stop ----
        if position > 0 and current_trade and c <= entry_price - sd:
            slippage = 2.0 * pv
            exit_px  = c - slippage
            pnl      = (exit_px - entry_price) * position
            commission = abs(position) * exit_px * COMMISSION
            cash    += pnl - commission
            trades.append({
                'entry_date': current_trade['entry_date'],
                'exit_date': close.index[i],
                'type': 'LONG', 'entry_price': entry_price,
                'exit_price': exit_px, 'size': position,
                'pnl': pnl - commission, 'exit_reason': 'STOP_LOSS',
            })
            position = 0.0; entry_price = 0.0; current_trade = None

        # ---- EXIT: signal -> flat (MA200 cross-down or Donchian flip) ----
        if position > 0 and current_trade and s <= 0:
            slippage = 2.0 * pv
            exit_px  = c - slippage
            pnl      = (exit_px - entry_price) * position
            commission = abs(position) * exit_px * COMMISSION
            cash    += pnl - commission
            trades.append({
                'entry_date': current_trade['entry_date'],
                'exit_date': close.index[i],
                'type': 'LONG', 'entry_price': entry_price,
                'exit_price': exit_px, 'size': position,
                'pnl': pnl - commission, 'exit_reason': 'SIGNAL_EXIT',
            })
            position = 0.0; entry_price = 0.0; current_trade = None

        if position < 0 and current_trade and s >= 0:
            slippage = 2.0 * pv
            exit_px  = c + slippage
            pnl      = (entry_price - exit_px) * abs(position)
            commission = abs(position) * exit_px * COMMISSION
            cash    += pnl - commission
            trades.append({
                'entry_date': current_trade['entry_date'],
                'exit_date': close.index[i],
                'type': 'SHORT', 'entry_price': entry_price,
                'exit_price': exit_px, 'size': position,
                'pnl': pnl - commission, 'exit_reason': 'SIGNAL_EXIT',
            })
            position = 0.0; entry_price = 0.0; current_trade = None

        # ---- ENTRY ----
        if position == 0.0 and s > 0:
            entry_price = c + 2.0 * pv     # 2-pip additive slippage on long entry
            risk_dollars = HALF_KELLY * cash
            raw_units  = risk_dollars / sd if sd > 0 else 0.0
            max_units  = (MAX_LEVERAGE * cash) / entry_price if entry_price > 0 else 0.0
            position   = min(raw_units, max_units)
            commission  = position * entry_price * COMMISSION
            cash       -= commission
            current_trade = {
                'entry_date': close.index[i], 'type': 'LONG',
                'entry_price': entry_price, 'size': position,
            }

        if position == 0.0 and s < 0:
            entry_price = c - 2.0 * pv     # 2-pip additive slippage on short entry
            risk_dollars = HALF_KELLY * cash
            raw_units  = risk_dollars / sd if sd > 0 else 0.0
            max_units  = (MAX_LEVERAGE * cash) / abs(entry_price) if entry_price != 0 else 0.0
            position   = -min(raw_units, max_units)
            commission  = abs(position) * abs(entry_price) * COMMISSION
            cash       -= commission
            current_trade = {
                'entry_date': close.index[i], 'type': 'SHORT',
                'entry_price': entry_price, 'size': position,
            }

        # ---- equity ----
        if position != 0.0:
            equity[i] = cash + (c - entry_price) * position
        else:
            equity[i] = cash

    # force close at end
    if position != 0.0 and len(close) > 0:
        c = close.iloc[-1]
        slippage = 2.0 * pv
        if position > 0:
            exit_px = c - slippage; pnl = (exit_px - entry_price) * position
        else:
            exit_px = c + slippage; pnl = (entry_price - exit_px) * abs(position)
        commission = abs(position) * exit_px * COMMISSION
        cash      += pnl - commission
        trades.append({
            'entry_date': current_trade['entry_date'],
            'exit_date': close.index[-1],
            'type': current_trade['type'],
            'entry_price': entry_price, 'exit_price': exit_px,
            'size': position, 'pnl': pnl - commission, 'exit_reason': 'END_OF_DATA',
        })
        position = 0.0

    # ---- metrics ----
    eq = pd.Series(equity, index=close.index)
    dr = eq.pct_change().fillna(0.0)
    roll_max = eq.cummax()
    dd = np.where(roll_max > 0, (eq - roll_max) / roll_max, 0.0)
    max_dd = float(abs(np.min(dd))) if len(dd) > 0 else 0.0
    days   = (eq.index[-1] - eq.index[0]).days / 365.25
    final  = float(eq.iloc[-1])
    cagr   = ((final / CAPITAL) ** (1 / days) - 1) if (days > 0 and final > 0 and CAPITAL > 0) else 0.0
    mean_d = dr.mean(); std_d = dr.std()
    sharpe = (mean_d / std_d) * np.sqrt(252) if std_d > 0 else 0.0
    pnls   = [t['pnl'] for t in trades]
    gp     = sum(p for p in pnls if p > 0)
    gl     = abs(sum(p for p in pnls if p < 0))
    pf     = gp / gl if gl > 0 else (gp if gp > 0 else 1.0)
    wins   = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    win_rate = len(wins) / len(trades) if trades else 0.0

    return {
        'cagr': cagr, 'sharpe': sharpe, 'maxdd': max_dd,
        'pf': pf, 'win_rate': win_rate, 'trades': len(trades),
        'final': final,
    }


def walk_forward(df: pd.DataFrame, signal_func, ticker: str,
                 is_years: int = 3, oos_years: int = 1) -> dict:
    """Expanding IS / 1y OOS walk-forward."""
    dates = df.index
    start = dates[0]
    end   = dates[-1]
    folds = []
    is_end = start + pd.DateOffset(years=is_years)
    fold_num = 0
    while is_end < end:
        oos_end = min(is_end + pd.DateOffset(years=oos_years), end)
        is_df = df.loc[start:is_end]
        oos_df = df.loc[is_end:oos_end]
        try:
            is_m = run_backtest(is_df, signal_func, ticker)
            oos_m = run_backtest(oos_df, signal_func, ticker)
            folds.append({
                'fold': fold_num + 1,
                'is_start': str(start.date()), 'is_end': str(is_end.date()),
                'oos_start': str(is_end.date()), 'oos_end': str(oos_end.date()),
                'is_cagr': is_m['cagr'], 'is_sharpe': is_m['sharpe'],
                'is_maxdd': is_m['maxdd'], 'is_trades': is_m['trades'],
                'oos_cagr': oos_m['cagr'], 'oos_sharpe': oos_m['sharpe'],
                'oos_maxdd': oos_m['maxdd'], 'oos_trades': oos_m['trades'],
                'oos_pf': oos_m['pf'], 'oos_win_rate': oos_m['win_rate'],
            })
        except Exception as e:
            print(f"  fold {fold_num+1} FAILED: {e}")
        fold_num += 1
        start = is_end
        is_end = start + pd.DateOffset(years=is_years)

    out = {
        'folds': folds,
        'oos_sharpe_avg': float(np.mean([f['oos_sharpe'] for f in folds])) if folds else 0.0,
        'oos_maxdd_avg': float(np.mean([f['oos_maxdd'] for f in folds])) if folds else 0.0,
        'n_folds': len(folds),
    }
    return out


# ── data loading ────────────────────────────────────────────────────────
YF_TICKERS = {
    'EURJPY': 'EURJPY=X',
    'GBPJPY': 'GBPJPY=X',
    'AUDJPY': 'AUDJPY=X',
    'USDCHF': 'USDCHF=X',
    'NZDUSD': 'NZDUSD=X',
    'USDCAD': 'USDCAD=X',
}

def fetch_yfinance(ticker_key: str) -> pd.DataFrame | None:
    """Fetch real OHLC from yfinance, cache locally."""
    sym = YF_TICKERS[ticker_key]
    cache_file = os.path.join(CACHE_DIR, f"{ticker_key}_{YF_START.replace('-', '')}_{YF_END.replace('-', '')}.csv")
    if os.path.exists(cache_file):
        try:
            df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
            if not df.empty and {'Open','High','Low','Close'}.issubset(df.columns):
                return df.sort_index()
        except Exception:
            pass
    print(f"    downloading {sym} from yfinance ...")
    try:
        df = yf.download(sym, start=YF_START, end=YF_END, progress=False, auto_adjust=False)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[['Open','High','Low','Close']].copy()
        df.columns = ['Open','High','Low','Close']
        df = df.apply(pd.to_numeric, errors='coerce').dropna()
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        df.to_csv(cache_file)
        return df
    except Exception as e:
        print(f"    yfinance download failed for {sym}: {e}")
        return None


def get_pair_data(pair: str) -> pd.DataFrame | None:
    """Return OHLC DataFrame for the pair, real bars preferred."""
    pair = pair.upper()
    df = fetch_yfinance(pair)
    if df is not None and len(df) > 252:
        return df.sort_index()
    return None


PAIRS = ['EURJPY', 'GBPJPY', 'AUDJPY', 'USDCHF', 'NZDUSD', 'USDCAD']

# ── main ────────────────────────────────────────────────────────────────
def main():
    all_results = []
    all_dates = []

    for pair in PAIRS:
        df = get_pair_data(pair)
        if df is None or len(df) < 252:
            print(f"SKIP {pair}: insufficient data")
            continue
        all_dates.append(df.index[0]); all_dates.append(df.index[-1])
        print(f"\n{'='*64}")
        print(f"  {pair}  ({df.index[0].date()} -> {df.index[-1].date()}, {len(df):,} bars)")
        print(f"{'='*64}")

        for strategy in ['MA200', 'Donchian20']:
            if strategy == 'MA200':
                def sig_ma200(close, df_):
                    return _make_ma200_signal(close)
                sig_fn = sig_ma200
            else:
                def sig_dc20(close, df_):
                    return _make_donchian20_signal(close, df_['High'], df_['Low'])
                sig_fn = sig_dc20

            # Full-history (reference)
            full = run_backtest(df, sig_fn, pair)
            # Walk-forward
            wf = walk_forward(df, sig_fn, pair)

            row = {
                'pair': pair,
                'strategy': strategy,
                'period': 'daily',
                'cagr': round(full['cagr'], 6),
                'sharpe': round(full['sharpe'], 4),
                'maxdd': round(full['maxdd'], 6),
                'trades': full['trades'],
                'pf': round(full['pf'], 4),
                'win_rate': round(full['win_rate'], 4),
                'oos_sharpe': round(wf['oos_sharpe_avg'], 4),
                'oos_maxdd': round(wf['oos_maxdd_avg'], 6),
                'oos_trades_avg': round(float(np.mean([f['oos_trades'] for f in wf['folds']])) if wf['folds'] else 0.0, 1),
                'n_folds': wf['n_folds'],
                'folds': wf['folds'],
            }
            all_results.append(row)
            print(f"  {strategy:<12s} | CAGR {full['cagr']:+8.2%} | Sharpe {full['sharpe']:+.2f} | "
                  f"MaxDD {full['maxdd']:.2%} | Trades {full['trades']:4d} | "
                  f"PF {full['pf']:.2f} | WR {full['win_rate']:.1%}")
            print(f"  {'':12s} | OOS Sharpe {wf['oos_sharpe_avg']:+.2f} | OOS MaxDD {wf['oos_maxdd_avg']:.2%} | "
                  f"folds {wf['n_folds']}")

    # Add metadata
    output = {
        'metadata': {
            'stage': 'Stage 1: FX Cross Pairs Funnel Expand',
            'strategy': 'MA200 / Donchian20 + Half-Kelly(7.81%) + 3xATR(14) Stop',
            'data_source': 'yfinance (OHLC daily)',
            'data_range': f"{min(all_dates).date()} to {max(all_dates).date()}",
            'params': {
                'half_kelly': HALF_KELLY, 'atr_period': ATR_PERIOD, 'atr_mult': ATR_MULT,
                'max_leverage': MAX_LEVERAGE, 'ma_period': MA_PERIOD, 'donchian_period': DONCHIAN_PERIOD,
                'commission_pct': COMMISSION, 'slippage_pips': SLIPPAGE_PIPS,
                'timing': 'prior-close', 'stop': '3xATR from entry', 'sizing': 'Half-Kelly (0.0781 risk)'
            },
            'walk_forward': '3y expanding IS / 1y OOS, IS advances by 1y each fold',
            'baseline': 'Gold/JPY CAGR=+14.84% Sharpe=0.74 MaxDD=47.37%'
        },
        'results': all_results
    }
    # save
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(OUT_PATH, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nSaved {len(all_results)} results to {OUT_PATH}")

    # summary table
    print(f"\n{'='*76}")
    print(f"{'Stage 1 FX Cross Pairs - Summary':^76}")
    print(f"{'Strategy: MA200 / Donchian20 | Half-Kelly(7.81%) | 3xATR Stop':^76}")
    print(f"{'Walk-forward: 3y expanding IS / 1y OOS | prior-close | 0.002% comm | 2-pip slip':^76}")
    print(f"{'='*76}")
    print(f"{'Pair':<8} {'Strategy':<12} {'CAGR':>8} {'Sharpe':>7} {'MaxDD':>8} {'Trades':>6} {'OOS S':>7} {'OOS MDD':>8}")
    print("-" * 76)
    for r in output['results']:
        print(f"{r['pair']:<8} {r['strategy']:<12} {r['cagr']:>+8.2%} {r['sharpe']:>+7.2f} "
              f"{r['maxdd']:>8.2%} {r['trades']:>6d} {r['oos_sharpe']:>+7.2f} {r['oos_maxdd']:>8.2%}")
    print("-" * 76)
    print(f"\nBaseline: Gold/JPY  CAGR=+14.84%  Sharpe=0.74  MaxDD=47.37%")

if __name__ == '__main__':
    main()
