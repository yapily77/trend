"""S&P 500 AMA (KAMA) trend-following research — weekly ^GSPC.

Tests AMA / KAMA crossover on weekly S&P 500 bars.
Weekly amplifies trends and cuts whipsaws versus daily.

Walk-forward: 3-year expanding IS / 1-year OOS, reject if
OOS Sharpe < 0.4, max DD > 30%.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd
from scripts.bt.engine import Backtest
from scripts.bt.strategies import Strategy, DonchianBreakout
from scripts.bt.reporting import generate_markdown_report, export_trade_log
from scripts.bt.charts import plot_equity_curve
from scripts.bt.indicators import calculate_kama
import json, os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reports')
CHARTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'charts')
os.makedirs(OUT, exist_ok=True)
os.makedirs(CHARTS, exist_ok=True)

_cached = '/tmp/bt_cache/^GSPC_weekly_19950101_20260530.csv'
if os.path.exists(_cached):
    df = pd.read_csv(_cached, index_col=0, parse_dates=True)
else:
    raise FileNotFoundError("Run US/scripts/fetch_sp500_weekly.py first")

print(f"Data: {df.index[0].date()} to {df.index[-1].date()}, {len(df)} bars")


class AMATrend(Strategy):
    """AMA / KAMA crossover trend-following strategy."""
    def __init__(self, period: int = 30, fast: int = 2, slow: int = 30):
        self.period = period
        self.fast = fast
        self.slow = slow

    def signals(self, df: pd.DataFrame) -> pd.Series:
        close = df['Close']
        kama = calculate_kama(close, period=self.period, fast=self.fast, slow=self.slow)
        signals = pd.Series(0.0, index=df.index, dtype=float)
        signals[close > kama] = 1.0
        signals[close < kama] = -1.0
        return signals


results = {}
for sname, strat in [('AMA30', AMATrend(period=30, fast=2, slow=30)),
                     ('AMA10', AMATrend(period=10, fast=2, slow=30)),
                     ('Donchian20', DonchianBreakout(period=20))]:
    print(f"\n=== {sname} ===")
    bt = Backtest(df=df, strategy_instance=strat, capital=100000.0, risk_pct=0.01,
                  slippage_pips=2.0, ticker='^GSPC')
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
    fname = os.path.join(OUT, f'sp500w_{sname.lower()}_folds.json')
    with open(fname, 'w') as f:
        json.dump(folds, f, default=str)
    generate_markdown_report(m, folds, '^GSPC (weekly)', sname,
                             os.path.join(OUT, f'sp500w_{sname.lower()}_report.md'))
    export_trade_log(r['trades'], os.path.join(OUT, f'sp500w_{sname.lower()}_trades.csv'))
    plot_equity_curve(r['equity'], r['drawdown'], '^GSPC (weekly)', sname,
                      os.path.join(CHARTS, f'sp500w_{sname.lower()}_equity.png'))

with open(os.path.join(OUT, 'sp500w_ama_results.json'), 'w') as f:
    json.dump(results, f, indent=2, default=str)

print("\n=== Summary ===")
print(json.dumps(results, indent=2, default=str))
print("\nAll weekly S&P 500 reports saved to US/reports/ and US/charts/")
