"""Standalone backtest harness for the 200-day MA crossover strategy.

Uses raw (non-adjusted) closes so the entry/exit prices are real
tradeable levels — exactly what the investor cares about.
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
    """Run long/flat MA200 backtest on raw closes.

    Returns dict with metrics, equity series, and trade log.
    """
    df = fetch(ticker, start, end)
    close = df['Close']
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]

    ma = close.rolling(period).mean()
    sig = pd.Series(0.0, index=df.index)
    sig[close > ma] = 1.0

    # position from PRIOR close (no look-ahead)
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

    # trade log: buy/sell pairs
    trades = []
    for i in range(1, len(df)):
        now_long = pos.iloc[i] > 0
        was_long = pos.iloc[i - 1] > 0
        if now_long != was_long:
            if was_long:
                trades.append({
                    'type': 'SELL', 'date': str(df.index[i].date()),
                    'price': float(close.iloc[i]),
                })
            else:
                trades.append({
                    'type': 'BUY', 'date': str(df.index[i].date()),
                    'price': float(close.iloc[i]),
                })

    ntrades = int(flip.sum())
    in_market_pct = pos.mean() * 100
    n_flips = int(pos.diff().abs().sum())

    metrics = {
        'ticker': ticker,
        'period': period,
        'start': str(df.index[0].date()),
        'end': str(df.index[-1].date()),
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
        'total_flips': n_flips,
        'in_market_pct': round(in_market_pct, 1),
        'trades': trades,
    }
    return {'metrics': metrics, 'equity': st, 'bh_equity': bh, 'signal': sig}


def walk_forward(ticker: str, is_years: int = 5, oos_years: int = 2,
                 period: int = 200) -> list[dict]:
    """Walk-forward validation (expanding IS, rolling OOS)."""
    df = fetch(ticker)
    close = df['Close']
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    dates = df.index
    folds = []
    start = dates[0]
    end = dates[-1]
    is_end = start + pd.DateOffset(years=is_years)
    fold_num = 0
    while is_end < end:
        oos_end = min(is_end + pd.DateOffset(years=oos_years), end)
        is_df = df.loc[start:is_end]
        oos_df = df.loc[is_end:oos_end]
        # retrain MA on IS, apply to OOS
        is_close = is_df['Close']
        if isinstance(is_close, pd.DataFrame): is_close = is_close.iloc[:, 0]
        ma_is = is_close.rolling(period).mean()
        sig_is = pd.Series(0.0, index=is_df.index)
        sig_is[is_close > ma_is] = 1.0
        # apply same rule to OOS using OOS-only MA
        oos_close = oos_df['Close']
        if isinstance(oos_close, pd.DataFrame): oos_close = oos_close.iloc[:, 0]
        ma_oos = oos_close.rolling(period).mean()
        sig_oos = pd.Series(0.0, index=oos_df.index)
        sig_oos[oos_close > ma_oos] = 1.0
        pos_oos = sig_oos.shift(1).fillna(0.0)
        oos_ret = oos_close.pct_change().fillna(0.0)
        strat_ret = oos_ret * pos_oos
        bh = (1 + oos_ret).cumprod()
        st = (1 + strat_ret).cumprod()
        def sharpe(r):
            r = r.dropna()
            return 0.0 if r.std() == 0 else (r.mean()/r.std())*np.sqrt(252)
        fold_num += 1
        folds.append({
            'fold': fold_num,
            'is_start': str(is_start.date()) if False else str(start.date()),
            'is_end': str(is_end.date()),
            'oos_start': str(is_end.date()),
            'oos_end': str(oos_end.date()),
            'oos_sharpe': sharpe(strat_ret),
            'oos_bh_cagr': (bh.iloc[-1]/bh.iloc[0])**(1/((oos_end-is_end).days/365.25))-1 if bh.iloc[0] else 0,
            'oos_strat_cagr': (st.iloc[-1]/st.iloc[0])**(1/((oos_end-is_end).days/365.25))-1 if st.iloc[0] else 0,
            'oos_bh_dd': float((bh/bh.cummax()-1).min()),
            'oos_strat_dd': float((st/st.cummax()-1).min()),
        })
        is_start = is_end
        is_end = is_start + pd.DateOffset(years=is_years)
        start = is_start
    return folds


if __name__ == '__main__':
    for t in ['O39.SI', '^N225']:
        r = backtest(t)
        m = r['metrics']
        print(f"=== {m['ticker']} (MA{m['period']}, {m['years']} yrs) ===")
        print(f"  first close {m['first_close']:.2f} | last close {m['last_close']:.2f} | MA200 {m['ma200']:.2f}")
        print(f"  last signal: {m['last_signal']}")
        print(f"  BH CAGR {m['BH_CAGR']*100:.1f}% | Strat CAGR {m['Strat_CAGR']*100:.1f}%")
        print(f"  BH Sharpe {m['BH_Sharpe']:.2f} | Strat Sharpe {m['Strat_Sharpe']:.2f}")
        print(f"  BH MaxDD {m['BH_MaxDD']*100:.1f}% | Strat MaxDD {m['Strat_MaxDD']*100:.1f}%")
        print(f"  BH final {m['BH_Final_x']:.2f}x | Strat final {m['Strat_Final_x']:.2f}x")
        print(f"  flips {m['total_flips']} | in market {m['in_market_pct']:.0f}%")
        print(f"  last 3 trades: {m['trades'][-3:]}")
        print()
