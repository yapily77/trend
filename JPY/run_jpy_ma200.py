"""JPY MA200 trend-following research — daily USDJPY=X.

Tests a simple 200-day moving average crossover rule:
  - Long (1) when Close > MA200  (USD strong / JPY weak)
  - Short (-1) when Close < MA200 (USD weak / JPY strong)
  - Flat (0) until MA200 has 200 valid bars.

Compared against Donchian 20 baseline on the same data.
3-year expanding IS / 1-year OOS walk-forward.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')

import pandas as pd
from scripts.bt.data import DataFeed
from scripts.bt.strategies import Strategy, DonchianBreakout
from scripts.bt.engine import Backtest
from scripts.bt.reporting import generate_markdown_report, export_trade_log
from scripts.bt.charts import plot_equity_curve
import json, os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reports')
CHARTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'charts')
os.makedirs(OUT, exist_ok=True)
os.makedirs(CHARTS, exist_ok=True)

# Load cached daily data from /tmp so this script does not depend on
# a fresh yfinance call. Data is the same as run_jpy.py uses.
_cached = '/tmp/bt_cache/USDJPY=X_19950101_20260530.csv'
if os.path.exists(_cached):
    df = pd.read_csv(_cached, index_col=0, parse_dates=True)
else:
    feed = DataFeed()
    df = feed.get_data('USDJPY=X', start='1995-01-01', end='2026-05-30')

print(f"Data loaded: {df.shape[0]} rows, {df.index[0].date()} to {df.index[-1].date()}")


class MA200Trend(Strategy):
    """
    200-day Moving Average trend-following strategy.
    Long (1) when Close > MA200, Short (-1) when Close < MA200.
    Flat (0) until MA200 has 200 valid bars.
    """
    def __init__(self, period: int = 200):
        self.period = period

    def signals(self, df: pd.DataFrame) -> pd.Series:
        close = df['Close']
        ma = close.rolling(window=self.period).mean()
        signals = pd.Series(0, index=df.index, dtype=float)
        signals[close > ma] = 1.0
        signals[close < ma] = -1.0
        return signals


results = {}
for sname, strat in [('Donchian20', DonchianBreakout(period=20)),
                     ('MA200_Trend', MA200Trend(period=200))]:
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
    fname = os.path.join(OUT, f'jpy_{sname.lower()}_folds.json')
    with open(fname, 'w') as f:
        json.dump(folds, f, default=str)
    generate_markdown_report(m, folds, 'USDJPY=X', sname,
                             os.path.join(OUT, f'jpy_{sname.lower()}_report.md'))
    export_trade_log(r['trades'], os.path.join(OUT, f'jpy_{sname.lower()}_trades.csv'))
    plot_equity_curve(r['equity'], r['drawdown'], 'USDJPY=X', sname,
                      os.path.join(CHARTS, f'jpy_{sname.lower()}_equity.png'))

with open(os.path.join(OUT, 'jpy_ma200_results.json'), 'w') as f:
    json.dump(results, f, indent=2, default=str)

print("\n=== Summary ===")
print(json.dumps(results, indent=2, default=str))
print("\nAll MA200 reports saved to JPY/reports/ and JPY/charts/")
