"""200-day MA crossover EXIT discipline for a retail investor's existing positions.

Entry logic (already taken): go long when Close > 200-day SMA.
Exit logic (this module): sell when Close < 200-day SMA.
Symmetric. No discretion. The same 200-DMA is the entry AND the exit.

Benchmarks the rule against buy-and-hold on raw (non-adjusted) closes,
and breaks the 10-year window into three ~3-year regimes so the user
can see where it helps and where it lags.
"""
import pandas as pd
import numpy as np
import yfinance as yf


def fetch(ticker: str, start: str = '2016-01-01', end: str = '2026-06-01') -> pd.DataFrame:
    df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def backtest(ticker: str, period: int = 200,
             start: str = '2016-01-01', end: str = '2026-06-01',
             commission_pct: float = 0.00002,
             slippage_pct: float = 0.0005) -> dict:
    """Long/flat MA200: buy when Close > MA, sell when Close < MA.

    Signals use PRIOR close to avoid look-ahead bias.
    Returns dict with metrics, equity series, and trade log.
    """
    df = fetch(ticker, start, end)
    close = df['Close']
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]

    ma = close.rolling(period).mean()
    sig = pd.Series(0.0, index=df.index)
    sig[close > ma] = 1.0

    # prior-close position (no look-ahead)
    pos = sig.shift(1).fillna(0.0)
    ret = close.pct_change().fillna(0.0)
    strat_ret = ret * pos
    strat_ret.iloc[0] = 0.0

    # costs on flip days
    flip = pos.diff().fillna(0.0).abs()
    cost = flip * (commission_pct + slippage_pct)
    net_ret = strat_ret - cost

    bh = (1 + ret).cumprod()
    st = (1 + net_ret).cumprod()

    days = (df.index[-1] - df.index[0]).days / 365.25
    bh_cagr = (bh.iloc[-1] / bh.iloc[0]) ** (1 / days) - 1
    st_cagr = (st.iloc[-1] / st.iloc[0]) ** (1 / days) - 1

    def sharpe(r):
        r = r.dropna()
        return 0.0 if r.std() == 0 else (r.mean() / r.std()) * np.sqrt(252)

    def max_dd(eq):
        return float((eq / eq.cummax() - 1).min())

    trades = []
    for i in range(1, len(df)):
        now_long = pos.iloc[i] > 0
        was_long = pos.iloc[i - 1] > 0
        if now_long != was_long:
            trades.append({
                'type': ('SELL' if was_long else 'BUY'),
                'date': str(df.index[i].date()),
                'price': float(close.iloc[i]),
            })

    metrics = {
        'ticker': ticker,
        'period': period,
        'years': round(days, 1),
        'first_close': float(close.iloc[0]),
        'last_close': float(close.iloc[-1]),
        'ma200': float(ma.iloc[-1]),
        'last_signal': 'LONG' if sig.iloc[-1] > 0 else 'FLAT',
        'BH_CAGR': bh_cagr,
        'Strat_CAGR': st_cagr,
        'BH_Sharpe': sharpe(ret),
        'Strat_Sharpe': sharpe(net_ret),
        'BH_MaxDD': max_dd(bh),
        'Strat_MaxDD': max_dd(st),
        'BH_Final_x': float(bh.iloc[-1]),
        'Strat_Final_x': float(st.iloc[-1]),
        'total_flips': int(flip.sum()),
        'in_market_pct': round(pos.mean() * 100, 1),
        'trades': trades,
    }
    return {'metrics': metrics, 'equity': st, 'bh_equity': bh, 'signal': sig}


def regime_analysis(ticker: str) -> list[dict]:
    """Three ~3-year regime breakdown using full-sample MA, prior-close signals."""
    df = fetch(ticker)
    close = df['Close']
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    ma = close.rolling(200).mean()
    sig = pd.Series(0.0, index=df.index)
    sig[close > ma] = 1.0
    pos = sig.shift(1).fillna(0.0)
    ret = close.pct_change().fillna(0.0)
    strat_ret = ret * pos

    n = len(df)
    boundaries = [(0, n // 3), (n // 3, 2 * n // 3), (2 * n // 3, n)]
    labels = ['2016-2018', '2018-2022', '2022-2026']
    rows = []
    for (s, e), lab in zip(boundaries, labels):
        r = strat_ret.iloc[s:e]
        bh_r = ret.iloc[s:e]
        bh = (1 + bh_r).cumprod()
        st = (1 + r).cumprod()

        def sharpe(x):
            x = x.dropna()
            return 0.0 if x.std() == 0 else (x.mean() / x.std()) * np.sqrt(252)

        days = (df.index[e - 1] - df.index[s]).days / 365.25
        rows.append({
            'regime': lab,
            'years': round(days, 1),
            'in_market_pct': round(pos.iloc[s:e].mean() * 100, 0),
            'strat_sharpe': sharpe(r),
            'bh_sharpe': sharpe(bh_r),
            'strat_cum': st.iloc[-1] / st.iloc[0] - 1,
            'bh_cum': bh.iloc[-1] / bh.iloc[0] - 1,
            'strat_maxdd': (st / st.cummax() - 1).min(),
            'bh_maxdd': (bh / bh.cummax() - 1).min(),
        })
    return rows


if __name__ == '__main__':
    print("=" * 70)
    print("200-DAY MA EXIT DISCIPLINE — 10-YEAR RAW-PRICE BACKTEST")
    print("Rule: BUY when Close > 200 SMA (already taken).")
    print("      SELL when Close < 200 SMA (this analysis).")
    print("=" * 70)

    for t in ['O39.SI', '^N225']:
        r = backtest(t)
        m = r['metrics']
        print(f"\n### {t} ###")
        print(f"  Entry level (first close) : {m['first_close']:.2f}")
        print(f"  Current price             : {m['last_close']:.2f}")
        print(f"  200-day MA                : {m['ma200']:.2f}  ({m['last_signal']})")
        print(f"  Buy-and-hold              : {m['BH_Final_x']:.2f}x  CAGR {m['BH_CAGR']*100:.1f}%  Sharpe {m['BH_Sharpe']:.2f}  MaxDD {m['BH_MaxDD']*100:.1f}%")
        print(f"  MA200 exit discipline     : {m['Strat_Final_x']:.2f}x  CAGR {m['Strat_CAGR']*100:.1f}%  Sharpe {m['Strat_Sharpe']:.2f}  MaxDD {m['Strat_MaxDD']*100:.1f}%")
        print(f"  In market                 : {m['in_market_pct']:.0f}%  |  Flips: {m['total_flips']} (~1 every {int(m['years']*252/m['total_flips'])} days)")

        print(f"\n  Regime breakdown:")
        for reg in regime_analysis(t):
            print(f"    {reg['regime']} ({reg['years']:.0f} yr): in mkt {reg['in_market_pct']:.0f}%")
            print(f"      Strat Sharpe {reg['strat_sharpe']:.2f} vs BH {reg['bh_sharpe']:.2f}")
            print(f"      Strat {reg['strat_cum']:+.1%} vs BH {reg['bh_cum']:+.1%}")
            print(f"      Strat MaxDD {reg['strat_maxdd']*100:.1f}% vs BH {reg['bh_maxdd']*100:.1f}%")
        print(f"\n  Last 4 trades: {m['trades'][-4:]}")
        print()
