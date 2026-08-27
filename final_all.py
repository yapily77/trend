from scripts.bt.data import DataFeed
from scripts.bt.strategies import DonchianBreakout, DonchianBreakoutWithFilter, DonchianBreakoutWithER, DonchianBreakoutDual
from scripts.bt.engine import Backtest
from scripts.bt.reporting import generate_markdown_report, export_trade_log
from scripts.bt.charts import plot_equity_curve
import json

feed = DataFeed()

# === Main results: USDJPY=X (best performer) ===
print("=== Donchian 20 variants on USDJPY=X ===")
df = feed.get_data('USDJPY=X', start='1995-01-01', end='2026-05-30')

variants = {
    'baseline': DonchianBreakout(period=20),
    'adx25': DonchianBreakoutWithFilter(period=20, adx_threshold=25),
    'er03': DonchianBreakoutWithER(period=20, er_threshold=0.3),
    'dual2050': DonchianBreakoutDual(period_fast=20, period_slow=50),
}

main_results = {}
for vname, strat in variants.items():
    bt = Backtest(df=df, strategy_instance=strat, capital=100000.0, risk_pct=0.01, slippage_pips=2.0, ticker='USDJPY=X')
    r = bt.run()
    folds = bt.run_walk_forward(is_years=3, oos_years=1)
    m = r['metrics']
    oos = [f['oos_metrics']['Sharpe'] for f in folds]
    main_results[vname] = {
        'sharpe': m['Sharpe'], 'cagr': m['CAGR'], 'trades': m['Total_Trades'],
        'maxdd': m['Max_Drawdown'], 'profit_factor': m['Profit_Factor'],
        'final_value': m['Final_Value'], 'avg_oos': sum(oos)/len(oos),
        'min_oos': min(oos), 'max_oos': max(oos), 'folds_geq_4': sum(1 for s in oos if s>=0.4)
    }
    print(f"  {vname:10s}: Sharpe={m['Sharpe']:+.2f}, Trades={m['Total_Trades']:3d}, DD={m['Max_Drawdown']:.2%}, OOS avg={sum(oos)/len(oos):+.2f}")
    
    # Generate reports for baseline and ADX variants
    if vname in ('baseline', 'adx25'):
        fname = f'donchian20_{vname}'
        generate_markdown_report(m, folds, 'USDJPY=X', f'Donchian20_{vname}', f'reports/{fname}_report.md')
        export_trade_log(r['trades'], f'reports/{fname}_trades.csv')
        plot_equity_curve(r['equity'], r['drawdown'], 'USDJPY=X', f'Donchian20_{vname}', f'charts/{fname}_equity.png')
        with open(f'reports/{fname}_folds.json', 'w') as f:
            json.dump(folds, f, default=str)

# === Cross-asset comparison ===
print("\n=== Cross-Asset Donchian 20 ===")
assets = ['USDJPY=X', 'SPY', 'QQQ', 'GLD', 'IEF']
cross = {}
for asset in assets:
    try:
        adf = feed.get_data(asset, start='1995-01-01', end='2026-05-30')
        bt = Backtest(df=adf, strategy_instance=DonchianBreakout(period=20), capital=100000.0, risk_pct=0.01, slippage_pips=2.0, ticker=asset)
        r = bt.run()
        folds = bt.run_walk_forward(is_years=3, oos_years=1)
        oos = [f['oos_metrics']['Sharpe'] for f in folds]
        cross[asset] = {
            'sharpe': r['metrics']['Sharpe'], 'cagr': r['metrics']['CAGR'],
            'trades': r['metrics']['Total_Trades'], 'maxdd': r['metrics']['Max_Drawdown'],
            'avg_oos': round(sum(oos)/len(oos), 3), 'folds_geq_4': sum(1 for s in oos if s>=0.4),
            'total_folds': len(oos)
        }
        print(f"  {asset:12s}: Sharpe={r['metrics']['Sharpe']:+.2f}, Trades={r['metrics']['Total_Trades']:3d}, DD={r['metrics']['Max_Drawdown']:.2%}")
    except Exception as e:
        print(f"  {asset:12s}: ERROR - {str(e)[:60]}")

# === Save all ===
with open('reports/main_results.json', 'w') as f:
    json.dump(main_results, f, indent=2, default=str)
with open('reports/cross_asset.json', 'w') as f:
    json.dump(cross, f, indent=2, default=str)

print("\n=== Summary ===")
print(json.dumps(main_results, indent=2, default=str))
print("\nCross-asset:", json.dumps(cross, indent=2, default=str))
print("\nAll reports saved!")
