"""Integrated CAPE + 200-DMA analysis for the retail investor.

Combines the Shiller CAPE ratio (valuation signal) with the
200-day moving average (trend signal) to produce a position-
sizing recommendation rather than a timing recommendation.

CAPE tells you how much risk to carry.
The 200-DMA tells you when to exit.
"""
import pandas as pd
import numpy as np
import yfinance as yf


def get_cape() -> dict:
    """Fetch the CAPE ratio from Yahoo Finance (Multpl source).

    Returns dict with current CAPE, long-run mean, percentile,
    and the four-regime classification.

    NOTE: The Yahoo CAPE ticker is the Multpl S&P 500 Shiller CAPE.
    It is US-specific. There is no Japan CAPE available via yfinance.
    The US CAPE is used as a global equity-valuation proxy.
    """
    d = yf.download('CAPE', period='max', progress=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    cape = d['Close'].dropna().ffill()
    current = float(cape.iloc[-1])
    # Long-run mean from Shiller published data (1881-2022)
    long_run_mean = 16.5
    pct = float((cape < current).mean() * 100)

    # Classify valuation regime
    if current < 15:
        regime = 'CHEAP'
        sizing = 'Maximize equity exposure'
    elif current < 20:
        regime = 'FAIR'
        sizing = 'Normal equity exposure'
    elif current < 25:
        regime = 'FAIRLY_VALUED'
        sizing = 'Normal exposure, monitor for trim'
    elif current < 30:
        regime = 'EXPENSIVE'
        sizing = 'Trim 10% relative to trend signal'
    elif current < 40:
        regime = 'VERY_EXPENSIVE'
        sizing = 'Reduce equity 15-25% vs trend signal'
    else:
        regime = 'EXTREME'
        sizing = 'Reduce equity 25%+ vs trend signal'

    return {
        'current': current,
        'long_run_mean': long_run_mean,
        'vs_mean': current / long_run_mean,
        'percentile': pct,
        'regime': regime,
        'sizing': sizing,
        'data_start': str(cape.index[0].date()),
        'data_end': str(cape.index[-1].date()),
        'market': 'US S&P 500 (Multpl Shiller CAPE)',
        'is_us_only': True,
    }


def get_200_dma_exit(ticker: str, period: int = 200,
                     start: str = '2016-01-01', end: str = '2026-06-01') -> dict:
    """Compute the 200-DMA exit levels for a given ticker."""
    df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    close = df['Close']
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    ma = close.rolling(period).mean()
    sig = pd.Series(0.0, index=df.index)
    sig[close > ma] = 1.0
    pos = sig.shift(1).fillna(0.0)

    def sharpe(r):
        r = r.dropna()
        return 0.0 if r.std() == 0 else (r.mean() / r.std()) * np.sqrt(252)

    ret = close.pct_change().fillna(0.0)
    strat_ret = ret * pos
    strat_ret.iloc[0] = 0.0
    bh = (1 + ret).cumprod()
    st = (1 + strat_ret).cumprod()
    days = (df.index[-1] - df.index[0]).days / 365.25

    def max_dd(eq):
        return float((eq / eq.cummax() - 1).min())

    return {
        'ticker': ticker,
        'last_close': float(close.iloc[-1]),
        'ma200': float(ma.iloc[-1]),
        'last_signal': 'LONG' if sig.iloc[-1] > 0 else 'FLAT',
        'exit_trigger': float(ma.iloc[-1]),
        'BH_CAGR': (bh.iloc[-1] / bh.iloc[0]) ** (1 / days) - 1,
        'Strat_CAGR': (st.iloc[-1] / st.iloc[0]) ** (1 / days) - 1,
        'BH_Sharpe': sharpe(ret),
        'Strat_Sharpe': sharpe(strat_ret),
        'BH_MaxDD': max_dd(bh),
        'Strat_MaxDD': max_dd(st),
        'BH_Final_x': float(bh.iloc[-1]),
        'Strat_Final_x': float(st.iloc[-1]),
        'in_market_pct': round(float(pos.mean()) * 100, 1),
    }


def decision_matrix(cape_info: dict, positions: list[dict]) -> list[dict]:
    """Combine CAPE regime with per-position 200-DMA info.

    Returns a list of recommendations per position.
    """
    results = []
    for pos in positions:
        info = get_200_dma_exit(pos['ticker'], start=pos.get('start', '2016-01-01'),
                                 end=pos.get('end', '2026-06-01'))
        rec = {
            'ticker': pos['ticker'],
            'last_close': info['last_close'],
            'ma200_exit_trigger': info['exit_trigger'],
            'trend_signal': info['last_signal'],
            'cape_regime': cape_info['regime'],
            'cape_sizing': cape_info['sizing'],
        }
        # Integrated recommendation
        # NOTE: US CAPE is a global risk proxy, NOT a direct Nikkei valuation.
        if info['last_signal'] == 'LONG' and cape_info['regime'] in ('VERY_EXPENSIVE', 'EXTREME'):
            rec['action'] = 'HOLD but TRIM into strength'
            rec['reason'] = f"Trend is up but US CAPE {cape_info['current']:.1f} says reduce equity exposure. Use 200-DMA as hard exit."
        elif info['last_signal'] == 'LONG' and cape_info['regime'] == 'EXPENSIVE':
            rec['action'] = 'HOLD with tighter risk'
            rec['reason'] = f"Trend up, US CAPE {cape_info['current']:.1f} says trim 10% vs full allocation."
        elif info['last_signal'] == 'LONG':
            rec['action'] = 'HOLD'
            rec['reason'] = f"Trend up, US CAPE {cape_info['current']:.1f} says normal exposure."
        else:
            rec['action'] = 'SELL'
            rec['reason'] = f"Trend broke below 200-DMA. US CAPE {cape_info['current']:.1f} says stay out."
        results.append(rec)
    return results


if __name__ == '__main__':
    cape = get_cape()
    print("=" * 60)
    print("CAPE + 200-DMA DECISION MATRIX")
    print("=" * 60)
    print(f"\nCAPE: {cape['current']:.2f}")
    print(f"Long-run mean: {cape['long_run_mean']:.1f}")
    print(f"vs mean: {cape['vs_mean']:.1f}x")
    print(f"Percentile (2022-): {cape['percentile']:.0f}%")
    print(f"Regime: {cape['regime']}")
    print(f"Sizing: {cape['sizing']}")
    print(f"Data: {cape['data_start']} to {cape['data_end']}")

    positions = [
        {'ticker': 'O39.SI', 'name': 'OCBC', 'start': '2016-01-01', 'end': '2026-06-01'},
        {'ticker': '^N225', 'name': 'Nikkei 225', 'start': '2016-01-01', 'end': '2026-06-01'},
    ]
    results = decision_matrix(cape, positions)
    print("\n" + "=" * 60)
    print("POSITION RECOMMENDATIONS")
    print("=" * 60)
    for r in results:
        print(f"\n{r['ticker']} ({r.get('name','')})")
        print(f"  Last close: {r['last_close']:.2f}")
        print(f"  200-DMA exit trigger: {r['ma200_exit_trigger']:.2f}")
        print(f"  Trend signal: {r['trend_signal']}")
        print(f"  CAPE regime: {r['cape_regime']}")
        print(f"  Action: {r['action']}")
        print(f"  Reason: {r['reason']}")
