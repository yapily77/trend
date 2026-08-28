import sys, os
sys.path.insert(0, '/home/yapilwsl/arthityap/trend')
import pandas as pd
from scripts.bt.data import DataFeed

feed = DataFeed()
# yfinance weekly via auto resample is unreliable, so fetch daily and resample
df = feed.get_data('^GSPC', start='1995-01-01', end='2026-05-30')
dfw = df.resample('W-FRI').agg({
    'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
}).dropna()
print(f"Weekly: {dfw.index[0].date()} to {dfw.index[-1].date()}, {len(dfw)} bars")
dfw.to_csv('/tmp/bt_cache/^GSPC_weekly_19950101_20260530.csv')
print("cached weekly")
