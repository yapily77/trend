import sys, os
sys.path.insert(0, '/home/yapilwsl/arthityap/trend')
import pandas as pd
from scripts.bt.data import DataFeed

feed = DataFeed()
df = feed.get_data('^GSPC', start='1995-01-01', end='2026-05-30')
print(df.shape)
print(df.index[0], df.index[-1])
print(df.columns.tolist())
df.to_csv('/tmp/bt_cache/^GSPC_19950101_20260530.csv')
print("cached")
