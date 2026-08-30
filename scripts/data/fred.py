"""FRED-based data downloader via fredapi (bypasses Cloudflare WAF).

Provides long-history daily series:
  - JPY/USD  (FRED DEXJPUS, 1971-present)
  - Gold     (FRED GOLDPMGBD228NLBM, 1968-present)

Falls back to yfinance if fredapi is unavailable or the key fails.
API key is read from fred_api_key.txt (gitignored) or the FRED_API_KEY env var.
"""
import os
import io
import json
import pandas as pd

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '.bt_cache')

FRED_SERIES = {
    "USDJPY": "DEXJPUS",   # Japanese Yen to One U.S. Dollar (Daily)
    "GOLD":  "GOLDPMGBD228NLBM",  # Gold Fixing Price (3PM London), USD/oz
    "EURUSD": "DEXUSEU",  # Euro to One U.S. Dollar
    "GBPUSD": "DEXUSUK",  # British Pound to One U.S. Dollar
    "AUDUSD": "DEXUSAL",  # Australian Dollar to One U.S. Dollar
    "CADUSD": "DEXUSCA",  # Canadian Dollar to One U.S. Dollar
    "NZDUSD": "DEXUSNZ",  # New Zealand Dollar to One U.S. Dollar
    "CHFUSD": "DEXUSCH",  # Swiss Franc to One U.S. Dollar
    "SGDUSD": "DEXSPAG",  # Singapore Dollar to One U.S. Dollar
}

YF_TICKERS = {
    "USDJPY": "JPY=X",
    "GOLD":   "GC=F",   # COMEX Gold Futures, daily
}


def _load_api_key():
    """Read FRED API key from file or env var."""
    key = os.environ.get("FRED_API_KEY", "").strip()
    if key:
        return key
    here = os.path.dirname(os.path.abspath(__file__))
    for candidate in [
        os.path.join(here, "fred_api_key.txt"),
        os.path.join(here, "..", "fred_api_key.txt"),
        os.path.join(os.path.expanduser("~"), ".fred_api_key.txt"),
    ]:
        p = os.path.normpath(candidate)
        if os.path.exists(p):
            with open(p) as f:
                key = f.read().strip()
            if key:
                return key
    return None


def _ensure_cache_dir():
    d = os.path.normpath(CACHE_DIR)
    os.makedirs(d, exist_ok=True)
    return d


def _cache_path(ticker: str, start: str, end: str) -> str:
    return os.path.join(_ensure_cache_dir(), f"{ticker}_{start.replace('-', '')}_{end.replace('-', '')}.csv")


def _load_cached(ticker: str, start: str, end: str):
    p = _cache_path(ticker, start, end)
    if os.path.exists(p):
        try:
            df = pd.read_csv(p, index_col=0, parse_dates=True)
            if not df.empty:
                return df
        except Exception:
            pass
    return None


def _save_cached(ticker: str, start: str, end: str, df: pd.DataFrame):
    p = _cache_path(ticker, start, end)
    df.to_csv(p)


def download_fred(series_id: str, ticker_name: str, start: str = '1970-01-01',
                  end: str = '2026-06-01') -> pd.DataFrame:
    """Download from FRED via fredapi. Returns DataFrame indexed by Date
    with a single column named the ticker symbol."""
    import fredapi
    key = _load_api_key()
    if not key:
        raise RuntimeError(
            "No FRED API key found. Set FRED_API_KEY env var, or create "
            "scripts/data/fred_api_key.txt (gitignored), or ~/.fred_api_key.txt"
        )
    fred = fredapi.Fred(api_key=key)
    raw = fred.get_series(series_id, observation_start=start, observation_end=end)
    df = raw.reset_index()
    df.columns = ["Date", ticker_name]
    df["Date"] = pd.to_datetime(df["Date"])
    df[ticker_name] = pd.to_numeric(df[ticker_name], errors="coerce")
    df = df.dropna().sort_values("Date").reset_index(drop=True)
    df = df.set_index("Date")
    return df


def _yf_fallback(ticker_name: str, start: str = '1970-01-01',
                 end: str = '2026-06-01') -> pd.DataFrame:
    import yfinance as yf
    symbol = YF_TICKERS[ticker_name]
    df = yf.download(symbol, start=start, end=end, progress=False, auto_adjust=False)
    if df.empty:
        raise ValueError(f"No data for {ticker_name} / {symbol}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Close"]].rename(columns={"Close": ticker_name})
    df = df.reset_index()
    df.columns = ["Date", ticker_name]
    df["Date"] = pd.to_datetime(df["Date"])
    df[ticker_name] = pd.to_numeric(df[ticker_name], errors="coerce")
    df = df.dropna().sort_values("Date").reset_index(drop=True)
    df = df.set_index("Date")
    return df


def get_series(ticker_name: str, start: str = '1970-01-01',
               end: str = '2026-06-01', force_refresh: bool = False) -> pd.DataFrame:
    """Return a DataFrame indexed by Date with one column (the ticker symbol).
    Tries FRED first, then yfinance fallback. Uses a local CSV cache."""
    cached = _load_cached(ticker_name, start, end) if not force_refresh else None
    if cached is not None:
        return cached

    series_id = FRED_SERIES[ticker_name]
    try:
        df = download_fred(series_id, ticker_name, start, end)
    except Exception as e:
        print(f"FRED download failed for {ticker_name}: {e} — falling back to yfinance")
        df = _yf_fallback(ticker_name, start, end)

    _save_cached(ticker_name, start, end, df)
    return df


def build_jpy_usd(start: str = '1970-01-01', end: str = '2026-06-01',
                  force_refresh: bool = False) -> pd.DataFrame:
    """Return USDJPY daily with a JPY_USD column (inverse)."""
    df = get_series("USDJPY", start, end, force_refresh)
    df["JPY_USD"] = 1.0 / df["USDJPY"]
    return df


def build_gold(start: str = '1968-01-01', end: str = '2026-06-01',
               force_refresh: bool = False) -> pd.DataFrame:
    """Return Gold USD/oz daily."""
    return get_series("GOLD", start, end, force_refresh)


if __name__ == "__main__":
    for name, fn in [("USDJPY", build_jpy_usd), ("GOLD", build_gold)]:
        df = fn()
        print(f"{name}: {df.shape[0]} rows, {df.index[0].date()} -> {df.index[-1].date()}")
        print(df.tail(3))
        print()
