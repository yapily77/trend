from scripts.bt.data import DataFeed
from scripts.bt.strategies import DonchianBreakout, KAMASlope
from scripts.bt.engine import Backtest
from scripts.bt.reporting import generate_markdown_report, export_trade_log
from scripts.bt.charts import plot_equity_curve
import json

feed = DataFeed()
tickers = ['USDJPY=X', 'SPY', 'QQQ', '^GSPC', '^DJI', '^NDX', 'IEF', 'GLD', 'EURUSD=X', 'VNQ']
results_all = {}

for t in tickers:
    try:
        df = feed.get_data(t, start='2005-01-01', end='2026-05-30')
        strat = DonchianBreakout(period=20)
        bt = Backtest(df=df, strategy_instance=strat, capital=100000.0, risk_pct=0.01, slippage_pips=2.0, ticker=t)
        results = bt.run()
        folds = bt.run_walk_forward(is_years=3, oos_years=1)
        
        # For multi-asset, also try KAMA on select ones
        if t in ['USDJPY=X', 'SPY', 'GLD']:
            strat2 = KAMASlope(period=10, fast=2, slow=30)
            bt2 = Backtest(df=df, strategy_instance=strat2, capital=100000.0, risk_pct=0.01, slippage_pips=2.0, ticker=t)
            results2 = bt2.run()
            folds2 = bt2.run_walk_forward(is_years=3, oos_years=1)
            results_all[f"{t}_KAMA"] = {
                'sharpe': results2['metrics']['Sharpe'],
                'cagr': results2['metrics']['CAGR'],
                'maxdd': results2['metrics']['Max_Drawdown'],
                'trades': results2['metrics']['Total_Trades'],
                'final': results2['metrics']['Final_Value'],
                'oos_sharpes': [f['oos_metrics']['Sharpe'] for f in folds2],
                'avg_oos': sum(f['oos_metrics']['Sharpe'] for f in folds2)/len(folds2)
            }
        
        results_all[t] = {
            'sharpe': results['metrics']['Sharpe'],
            'cagr': results['metrics']['CAGR'],
            'maxdd': results['metrics']['Max_Drawdown'],
            'trades': results['metrics']['Total_Trades'],
            'final': results['metrics']['Final_Value'],
            'oos_sharpes': [f['oos_metrics']['Sharpe'] for f in folds],
            'avg_oos': sum(f['oos_metrics']['Sharpe'] for f in folds)/len(folds)
        }
        print(f"  {t:15s}: Sharpe={results['metrics']['Sharpe']:+.2f}, Trades={results['metrics']['Total_Trades']:3d}, OOS avg={results_all[t]['avg_oos']:+.2f}")
    except Exception as e:
        print(f"  {t:15s}: ERROR - {str(e)[:80]}")

with open('cross_asset_results.json', 'w') as f:
    json.dump(results_all, f, indent=2, default=str)

# Print ranked by Sharpe
print("\n=== Ranked by Full-Run Sharpe (Donchian 20) ===")
for k, v in sorted(results_all.items(), key=lambda x: x[1]['sharpe'], reverse=True):
    if '_KAMA' not in k:
        print(f"  {k:15s}: Sharpe={v['sharpe']:+.2f}, CAGR={v['cagr']:+.2%}, Trades={v['trades']:3d}, OOS avg={v['avg_oos']:+.2f}")

# Save for report generation
with open('cross_asset_results.json', 'w') as f:
    json.dump(results_all, f, indent=2, default=str)
print("\nSaved cross_asset_results.json")
