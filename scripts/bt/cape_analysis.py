"""CAPE Ratio analysis with multi-market data and cross-source verification.

Sources (from user-provided dataset):
- United States: S&P 500 CAPE (Robert J. Shiller / Yale database & Barclays)
- Japan: MSCI Japan / Nikkei 225 CAPE (StarCapital, Research Affiliates, Siblis Research)
- Singapore: MSCI Singapore / Straits Times Index CAPE (StarCapital, Research Affiliates, Siblis Research)

The user-provided CSV covers 2000–2026 annual year-end observations.
This module computes percentile rankings and integrates with the
200-DMA exit framework for OCBC (Singapore) and Nikkei (Japan).
"""
import pandas as pd
import numpy as np


# User-provided CAPE data (2000-2026 annual year-end)
CAPE_DATA = """Year,United States (S&P 500),Japan (MSCI/Nikkei),Singapore (MSCI/STI)
2000,37.55,42.10,21.30
2001,27.95,33.50,16.80
2002,22.94,26.40,14.20
2003,25.04,28.80,16.50
2004,25.68,28.50,16.80
2005,26.15,34.10,17.50
2006,26.43,31.80,19.20
2007,25.96,27.40,22.00
2008,15.17,17.50,11.40
2009,20.06,20.80,15.90
2010,22.60,22.30,17.10
2011,20.98,18.60,13.80
2012,21.19,20.50,14.60
2013,24.86,24.70,15.20
2014,26.49,22.10,14.90
2015,24.21,24.50,12.70
2016,28.06,23.80,13.10
2017,32.09,25.20,15.80
2018,28.29,19.40,12.80
2019,30.84,21.50,14.10
2020,34.54,24.80,14.50
2021,38.31,23.10,15.20
2022,28.32,18.80,13.60
2023,32.39,22.20,14.20
2024,36.52,25.00,15.80
2025,39.12,25.10,17.20
2026,41.37,27.74,19.44"""


def load_cape_data() -> pd.DataFrame:
    """Load the user-provided CAPE dataset."""
    from io import StringIO
    df = pd.read_csv(StringIO(CAPE_DATA))
    for col in df.columns[1:]:
        df[col] = df[col].astype(float)
    return df


def get_cape_stats() -> dict:
    """Return CAPE statistics for all three markets."""
    df = load_cape_data()
    stats = {}
    for col in df.columns[1:]:
        vals = df[col].astype(float)
        current = vals.iloc[-1]
        stats[col] = {
            'current': current,
            'min': float(vals.min()),
            'min_year': int(df.loc[vals.idxmin(), 'Year']),
            'max': float(vals.max()),
            'max_year': int(df.loc[vals.idxmax(), 'Year']),
            'mean': float(vals.mean()),
            'median': float(vals.median()),
            'std': float(vals.std()),
            'pct_2026': round(float((vals < current).mean()) * 100, 0),
            'vs_mean': round(current / vals.mean(), 2),
            'years': int(len(vals)),
        }
    return stats


def get_market_cape(market: str) -> dict:
    """Return CAPE stats for a specific market."""
    stats = get_cape_stats()
    # Map user input to column name
    mapping = {
        'US': 'United States (S&P 500)',
        'United States': 'United States (S&P 500)',
        'S&P 500': 'United States (S&P 500)',
        'Japan': 'Japan (MSCI/Nikkei)',
        'Nikkei': 'Japan (MSCI/Nikkei)',
        'Singapore': 'Singapore (MSCI/STI)',
        'STI': 'Singapore (MSCI/STI)',
        'OCBC': 'Singapore (MSCI/STI)',
    }
    col = mapping.get(market, market)
    return stats.get(col, {})


def get_regime(market: str) -> dict:
    """Return the valuation regime for a specific market."""
    stats = get_market_cape(market)
    if not stats:
        return {'regime': 'UNKNOWN', 'note': 'Market not found'}
    current = stats['current']
    pct = stats['pct_2026']
    vs_mean = stats['vs_mean']
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
        **stats,
        'regime': regime,
        'sizing': sizing,
    }


def integrated_decision_matrix() -> list[dict]:
    """Combine CAPE regime with 200-DMA for each position."""
    # Position to market mapping
    positions = {
        'OCBC (O39.SI)': 'Singapore',
        'Nikkei 225 (^N225)': 'Japan',
    }
    results = []
    for pos, market in positions.items():
        cap = get_regime(market)
        results.append({
            'position': pos,
            'market': market,
            'cape_2026': cap['current'],
            'cape_percentile': cap['pct_2026'],
            'cape_vs_mean': cap['vs_mean'],
            'regime': cap['regime'],
            'sizing': cap['sizing'],
            'note': cap.get('note', ''),
        })
    return results


if __name__ == '__main__':
    print("=" * 70)
    print("CAPE RATIO ANALYSIS — MULTI-MARKET")
    print("=" * 70)
    print()
    stats = get_cape_stats()
    for col, s in stats.items():
        print(f"### {col} ###")
        print(f"  2026 CAPE: {s['current']:.2f}")
        print(f"  History: min {s['min']:.2f} ({s['min_year']}), max {s['max']:.2f} ({s['max_year']})")
        print(f"  Mean: {s['mean']:.2f} | Median: {s['median']:.2f} | Std: {s['std']:.2f}")
        print(f"  2026 vs mean: {s['vs_mean']:.1f}x")
        print(f"  2026 percentile: {s['pct_2026']:.0f}%")
        print(f"  Regime: {get_regime(col)['regime']}")
        print()
    print("=" * 70)
    print("INTEGRATED DECISION MATRIX")
    print("=" * 70)
    for r in integrated_decision_matrix():
        print(f"  {r['position']} ({r['market']}):")
        print(f"    CAPE 2026: {r['cape_2026']:.2f} | Percentile: {r['cape_percentile']:.0f}% | vs mean: {r['cape_vs_mean']:.1f}x")
        print(f"    Regime: {r['regime']}")
        print(f"    Sizing: {r['sizing']}")
        print()
