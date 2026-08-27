import os
import pandas as pd
import yfinance as yf

class DataFeed:
    """Uses yfinance to fetch OHLCV data with basic local caching."""
    def __init__(self, cache_dir="/tmp/bt_cache", min_years: float = 20.0):
        self.cache_dir = cache_dir
        self.min_years = min_years
        os.makedirs(self.cache_dir, exist_ok=True)

    def get_data(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        cache_file = os.path.join(self.cache_dir, f"{ticker}_{start.replace('-', '')}_{end.replace('-', '')}.csv")
        if os.path.exists(cache_file):
            try:
                df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
                if not df.empty:
                    return df
            except Exception:
                pass

        df = yf.download(ticker, start=start, end=end)
        if df.empty:
            raise ValueError(f"No data returned for ticker {ticker} from {start} to {end}")

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        start_date = df.index[0]
        end_date = df.index[-1]
        years = (end_date - start_date).days / 365.25
        if years < self.min_years:
            raise ValueError(
                f"Insufficient historical data: {ticker} has {years:.2f} years "
                f"({start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}), "
                f"less than the required {self.min_years} years."
            )

        df.to_csv(cache_file)
        return df
