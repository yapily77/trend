from scripts.bt.data import DataFeed
from scripts.bt.strategies import DonchianBreakout, KAMASlope
from scripts.bt.engine import Backtest
from scripts.bt.reporting import generate_markdown_report, export_trade_log
from scripts.bt.charts import plot_equity_curve
import json

feed = DataFeed()

# ===== Donchian 20 on USDJPY=X =====
print("=== Donchian 20 on USDJPY=X ===")
df = feed.get_data('USDJPY=X', start='1995-01-01', end='2026-05-30')
print(f"Data: {df.shape[0]} rows, {df.index[0].date()} to {df.index[-1].date()}")

strat = DonchianBreakout(period=20)
bt = Backtest(df=df, strategy_instance=strat, capital=100000.0, risk_pct=0.01, slippage_pips=2.0, ticker='USDJPY=X')
results = bt.run()
folds = bt.run_walk_forward(is_years=3, oos_years=1)

generate_markdown_report(results['metrics'], folds, 'USDJPY=X', 'DonchianBreakout20', 'reports/donchian20_report.md')
export_trade_log(results['trades'], 'reports/donchian20_trades.csv')
plot_equity_curve(results['equity'], results['drawdown'], 'USDJPY=X', 'DonchianBreakout20', 'charts/donchian20_equity.png')
with open('reports/donchian20_folds.json', 'w') as f:
    json.dump(folds, f, default=str)

# ===== KAMA 10/2/30 on USDJPY=X =====
print("\n=== KAMA 10/2/30 on USDJPY=X ===")
strat3 = KAMASlope(period=10, fast=2, slow=30)
bt3 = Backtest(df=df, strategy_instance=strat3, capital=100000.0, risk_pct=0.01, slippage_pips=2.0, ticker='USDJPY=X')
results3 = bt3.run()
folds3 = bt3.run_walk_forward(is_years=3, oos_years=1)

generate_markdown_report(results3['metrics'], folds3, 'USDJPY=X', 'KAMASlope10_2_30', 'reports/kama10_report.md')
export_trade_log(results3['trades'], 'reports/kama10_trades.csv')
plot_equity_curve(results3['equity'], results3['drawdown'], 'USDJPY=X', 'KAMASlope10_2_30', 'charts/kama10_equity.png')
with open('reports/kama10_folds.json', 'w') as f:
    json.dump(folds3, f, default=str)

# ===== Summary =====
m = results['metrics']
m3 = results3['metrics']
print(f"\n{'='*60}")
print(f"FINAL RESULTS (29.6yr history, 1996-2026)")
print(f"{'='*60}")
print(f"\nDonchian 20:    Sharpe={m['Sharpe']:+.2f}, CAGR={m['CAGR']:+.2%}, Trades={m['Total_Trades']}, DD={m['Max_Drawdown']:.2%}")
print(f"KAMA 10/2/30:    Sharpe={m3['Sharpe']:+.2f}, CAGR={m3['CAGR']:+.2%}, Trades={m3['Total_Trades']}, DD={m3['Max_Drawdown']:.2%}")

oos_d = [f['oos_metrics']['Sharpe'] for f in folds]
oos_k = [f['oos_metrics']['Sharpe'] for f in folds3]
print(f"\nWalk-Forward OOS Sharpe:")
print(f"  Donchian 20: avg={sum(oos_d)/len(oos_d):+.2f}, min={min(oos_d):+.2f}, >=0.4 in {sum(1 for s in oos_d if s>=0.4)}/{len(oos_d)} folds")
print(f"  KAMA 10:     avg={sum(oos_k)/len(oos_k):+.2f}, min={min(oos_k):+.2f}, >=0.4 in {sum(1 for s in oos_k if s>=0.4)}/{len(oos_k)} folds")

with open('reports/summary.json', 'w') as f:
    json.dump({
        'donchian20': {'sharpe': m['Sharpe'], 'cagr': m['CAGR'], 'trades': m['Total_Trades'], 'maxdd': m['Max_Drawdown'], 'avg_oos': sum(oos_d)/len(oos_d)},
        'kama10': {'sharpe': m3['Sharpe'], 'cagr': m3['CAGR'], 'trades': m3['Total_Trades'], 'maxdd': m3['Max_Drawdown'], 'avg_oos': sum(oos_k)/len(oos_k)},
        'history_years': (df.index[-1] - df.index[0]).days / 365.25
    }, f, indent=2, default=str)

print("\nAll reports saved to reports/ and charts/")
