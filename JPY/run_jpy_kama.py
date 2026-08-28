"""JPY KAMA research — run KAMA Slope + KAMA Adaptive Position Sizing vs Donchian 20,
3-year expanding IS / 1-year OOS walk-forward on USDJPY=X."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')

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
df = feed.get_data('USDJPY=X', start='1995-01-01', end='2026-05-30')
print(f"Data loaded: {df.shape[0]} rows, {df.index[0].date()} to {df.index[-1].date()}")

results = {}
for sname, strat in [('Donchian20', DonchianBreakout(period=20)),
                     ('KAMA_Slope', KAMASlope(period=10, fast=2, slow=30)),
                     ('KAMA_AdaptiveSize', KAMAAdaptivePositionSizing(period=10, fast=2, slow=30))]:
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

with open(os.path.join(OUT, 'jpy_results.json'), 'w') as f:
    json.dump(results, f, indent=2, default=str)

print("\n=== Summary ===")
print(json.dumps(results, indent=2, default=str))
print("\nAll JPY KAMA reports saved to JPY/reports/ and JPY/charts/")
