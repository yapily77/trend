"""JPY KAMA research — weekly USDJPY=X.

Reuses the same engine and the same three strategies (Donchian 20,
KAMA Slope, KAMA Adaptive Position Sizing) on weekly-resampled data,
where TD Sequential was originally designed and KAMA's adaptive
smoothing may better capture trend regimes.

3-year expanding IS / 1-year OOS walk-forward.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')

import pandas as pd
import yfinance as yf
from scripts.bt.data import DataFeed
from scripts.bt.strategies import DonchianBreakout, KAMASlope, KAMAAdaptivePositionSizing
from scripts.bt.engine import Backtest
from scripts.bt.reporting import generate_markdown_report, export_trade_log
from scripts.bt.charts import plot_equity_curve
import json, os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reports')
CHARTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'charts')
os.makedirs(OUT, exist_ok=True)
os.makedirs(CHARTS, exist_ok=True)

feed = DataFeed()
# Weekly data: fetch directly and cache under a weekly-specific key
# so it does not collide with the daily cache.
cache_key = 'USDJPY=X_weekly_19950101_20260530'
cache_file = os.path.join(feed.cache_dir, f"{cache_key}.csv")
if os.path.exists(cache_file):
    df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
    print(f"Weekly data loaded from cache: {df.shape[0]} rows")
else:
    df = yf.download('USDJPY=X', start='1995-01-01', end='2026-05-30', interval='1wk')
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[['Close', 'High', 'Low']].dropna()
    df.to_csv(cache_file)
    print(f"Weekly data downloaded and cached: {df.shape[0]} rows")
print(f"Weekly data: {df.index[0].date()} to {df.index[-1].date()}")

results = {}
for sname, strat in [('Donchian20_Weekly', DonchianBreakout(period=20)),
                     ('KAMA_Slope_Weekly', KAMASlope(period=10, fast=2, slow=30)),
                     ('KAMA_AdaptiveSize_Weekly', KAMAAdaptivePositionSizing(period=10, fast=2, slow=30))]:
    print(f"\n=== {sname} ===")
    bt = Backtest(df=df, strategy_instance=strat, capital=100000.0, risk_pct=0.01,
                  slippage_pips=2.0, ticker='USDJPY=X')
    r = bt.run()
    folds = bt.run_walk_forward(is_years=3, oos_years=1)
    m = r['metrics']
    oos = [f['oos_metrics']['Sharpe'] for f in folds]
    results[sname] = {
        'sharpe': m['Sharpe'], 'cagr': m['CAGR'], 'trades': m['Total_Trades'],
        'maxdd': m['Max_Drawdown'], 'profit_factor': m['Profit_Factor'],
        'final_value': m['Final_Value'], 'avg_oos': sum(oos)/len(oos),
        'min_oos': min(oos), 'max_oos': max(oos), 'folds_geq_4': sum(1 for s in oos if s>=0.4),
        'total_folds': len(oos), 'n_folds_pass': sum(1 for s in oos if s>=0.4)
    }
    print(f"  Sharpe={m['Sharpe']:+.2f}, CAGR={m['CAGR']:+.2%}, Trades={m['Total_Trades']}, DD={m['Max_Drawdown']:.2%}")
    print(f"  OOS avg Sharpe={sum(oos)/len(oos):+.2f}, min={min(oos):+.2f}, >=0.4 in {sum(1 for s in oos if s>=0.4)}/{len(oos)}")
    fname = os.path.join(OUT, f'jpy_weekly_{sname.lower()}_folds.json')
    with open(fname, 'w') as f:
        json.dump(folds, f, default=str)
    generate_markdown_report(m, folds, 'USDJPY=X (weekly)', sname,
                             os.path.join(OUT, f'jpy_weekly_{sname.lower()}_report.md'))
    export_trade_log(r['trades'], os.path.join(OUT, f'jpy_weekly_{sname.lower()}_trades.csv'))
    plot_equity_curve(r['equity'], r['drawdown'], 'USDJPY=X (weekly)', sname,
                      os.path.join(CHARTS, f'jpy_weekly_{sname.lower()}_equity.png'))

with open(os.path.join(OUT, 'jpy_weekly_results.json'), 'w') as f:
    json.dump(results, f, indent=2, default=str)

print("\n=== Weekly Summary ===")
print(json.dumps(results, indent=2, default=str))
print("\nAll weekly JPY KAMA reports saved to JPY/reports/ and JPY/charts/")
