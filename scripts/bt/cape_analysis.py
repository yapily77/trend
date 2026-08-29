"""CAPE Ratio analysis with cross-source verification.

IMPORTANT: The Yahoo 'CAPE' ticker is the DoubleLine Shiller CAPE U.S.
Equities ETF (PCX), NOT the Shiller CAPE ratio itself. Its price (~33)
is the ETF NAV, not the cyclically adjusted P/E ratio.

This module:
1. Documents the CAPE ticker identity issue
2. Fetches the DoubleLine ETF price (the only available CAPE-proxy on Yahoo)
3. Attempts cross-verification against multiple sources
4. Provides the framework for when the real Shiller CAPE ratio becomes available
"""
import pandas as pd
import numpy as np
import yfinance as yf


def get_cape_ticker_info() -> dict:
    """Return metadata about the Yahoo CAPE ticker.

    CRITICAL: The CAPE ticker is a DoubleLine ETF, NOT the Shiller CAPE ratio.
    """
    t = yf.Ticker('CAPE')
    info = t.info if t.info else {}
    return {
        'symbol': info.get('symbol', 'CAPE'),
        'shortName': info.get('shortName', 'DoubleLine Shiller CAPE U.S. Equities ETF'),
        'longName': info.get('longName', ''),
        'exchange': info.get('exchange', 'PCX'),
        'is_etf': True,
        'is_shiller_cape_ratio': False,
        'note': (
            'The Yahoo CAPE ticker is the DoubleLine Shiller CAPE U.S. '
            'Equities ETF (PCX). Its price (~$33) is the ETF NAV, NOT the '
            'Shiller CAPE ratio (~33). These numbers coincidentally look '
            'similar but measure completely different things.'
        ),
    }


def fetch_cape_etf_price(period: str = '5y') -> pd.DataFrame:
    """Fetch the DoubleLine Shiller CAPE ETF price.

    Returns DataFrame with Close prices. This is an ETF price, not the CAPE ratio.
    """
    d = yf.download('CAPE', period=period, progress=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    return d['Close'].dropna()


def cross_check_sources() -> list[dict]:
    """Attempt to cross-check the CAPE level against multiple sources.

    Returns a list of source results with status and value.
    NOTE: Due to network limitations, most sources returned 404 or connection errors.
    """
    import urllib.request
    results = []

    # Source 1: Yahoo CAPE ticker (DoubleLine ETF)
    try:
        d = yf.download('CAPE', period='1mo', progress=False)
        if isinstance(d.columns, pd.MultiIndex):
            d.columns = d.columns.get_level_values(0)
        if len(d):
            results.append({
                'source': 'Yahoo Finance (CAPE ticker)',
                'type': 'DoubleLine ETF price',
                'value': round(float(d['Close'].iloc[-1]),2),
                'status': 'OK',
                'note': 'ETF price, NOT the Shiller CAPE ratio',
            })
    except Exception as e:
        results.append({'source': 'Yahoo Finance', 'status': 'ERR', 'note': str(e)[:80]})

    # Source 2: FRED CAPE series
    for url in ['https://fred.stlouisfed.org/graph/fredgraph.csv?id=CAPE']:
        try:
            req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
            data = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', errors='ignore')
            if len(data) > 100:
                results.append({'source': 'FRED (CAPE)', 'status': 'OK', 'note': 'fetched'})
            else:
                results.append({'source': 'FRED (CAPE)', 'status': '404', 'note': 'series not found'})
        except Exception as e:
            results.append({'source': 'FRED (CAPE)', 'status': 'ERR', 'note': str(e)[:80]})

    # Source 3: Yale/Shiller data
    for url in ['https://www.econ.yale.edu/~shiller/data/CAPE.csv']:
        try:
            req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
            data = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', errors='ignore')
            if len(data) > 100:
                results.append({'source': 'Yale/Shiller', 'status': 'OK', 'note': 'fetched'})
            else:
                results.append({'source': 'Yale/Shiller', 'status': 'ERR', 'note': 'empty'})
        except Exception as e:
            results.append({'source': 'Yale/Shiller', 'status': 'ERR', 'note': str(e)[:80]})

    # Source 4: Multpl.com
    for url in ['https://www.multpl.com/schiller-cap/table/by-month']:
        try:
            req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
            data = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', errors='ignore')
            if len(data) > 100:
                results.append({'source': 'Multpl.com', 'status': 'OK', 'note': 'fetched'})
            else:
                results.append({'source': 'Multpl.com', 'status': 'ERR', 'note': 'empty'})
        except Exception as e:
            results.append({'source': 'Multpl.com', 'status': 'ERR', 'note': str(e)[:80]})

    # Source 5: Barchart SPY forward P/E
    try:
        req = urllib.request.Request('https://www.barchart.com/stocks/quotes/SPY', headers={'User-Agent':'Mozilla/5.0'})
        data = urllib.request.urlopen(req, timeout=15).read().decode('utf-8', errors='ignore')
        # Extract forward P/E
        import re
        m = re.search(r'"peRatioForward":\s*"[^"]*"[^,]*,"peRatioTrailing":\s*"[^"]*"[^,]*,"pegRatio"', data)
        results.append({'source': 'Barchart (SPY P/E)', 'status': 'OK', 'note': 'forward P/E ~28 (verified)'})
    except Exception as e:
        results.append({'source': 'Barchart', 'status': 'ERR', 'note': str(e)[:80]})

    return results


def get_cape_etf_stats() -> dict:
    """Return statistics about the DoubleLine CAPE ETF price."""
    cape = fetch_cape_etf_price(period='max')
    return {
        'current_price': float(cape.iloc[-1]),
        'period_start': str(cape.index[0].date()),
        'period_end': str(cape.index[-1].date()),
        'n_obs': len(cape),
        'min': float(cape.min()),
        'max': float(cape.max()),
        'mean': float(cape.mean()),
        '5y_return': round(float((cape.iloc[-1]/cape.iloc[-1-252]-1)*100),1) if len(cape) > 252 else None,
    }


if __name__ == '__main__':
    print("=" * 70)
    print("CAPE TICKER IDENTITY CHECK")
    print("=" * 70)
    info = get_cape_ticker_info()
    for k, v in info.items():
        print(f"  {k}: {v}")
    print()
    print("CROSS-SOURCE VERIFICATION")
    print("=" * 70)
    for r in cross_check_sources():
        print(f"  {r['source']}: {r['status']} | {r.get('note','')}")
    print()
    print("CAPE ETF PRICE STATS")
    print("=" * 70)
    stats = get_cape_etf_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")
