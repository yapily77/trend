from scripts.bt.data import DataFeed
from scripts.bt.strategies import DonchianBreakout, KAMASlope
from scripts.bt.engine import Backtest
from scripts.bt.reporting import generate_markdown_report, export_trade_log
from scripts.bt.charts import plot_equity_curve
import json
import matplotlib.pyplot as plt

feed = DataFeed()

# === 1. Donchian 20 on USDJPY=X (best performer) ===
print("Generating Donchian 20 reports...")
df = feed.get_data('USDJPY=X', start='2005-01-01', end='2026-05-30')
strat = DonchianBreakout(period=20)
bt = Backtest(df=df, strategy_instance=strat, capital=100000.0, risk_pct=0.01, slippage_pips=2.0, ticker='USDJPY=X')
results = bt.run()
folds = bt.run_walk_forward(is_years=3, oos_years=1)
generate_markdown_report(results['metrics'], folds, 'USDJPY=X', 'DonchianBreakout20', 'reports/donchian20_report.md')
export_trade_log(results['trades'], 'reports/donchian20_trades.csv')
plot_equity_curve(results['equity'], results['drawdown'], 'USDJPY=X', 'DonchianBreakout20', 'charts/donchian20_equity.png')
with open('reports/donchian20_folds.json', 'w') as f:
    json.dump(folds, f, default=str)

# === 2. Donchian 20 on IEF (bond trend) ===
print("Generating Donchian 20 IEF reports...")
df2 = feed.get_data('IEF', start='2005-01-01', end='2026-05-30')
bt2 = Backtest(df=df2, strategy_instance=DonchianBreakout(period=20), capital=100000.0, risk_pct=0.01, slippage_pips=2.0, ticker='IEF')
results2 = bt2.run()
folds2 = bt2.run_walk_forward(is_years=3, oos_years=1)
generate_markdown_report(results2['metrics'], folds2, 'IEF', 'DonchianBreakout20_IEF', 'reports/donchian20_ief_report.md')
export_trade_log(results2['trades'], 'reports/donchian20_ief_trades.csv')
plot_equity_curve(results2['equity'], results2['drawdown'], 'IEF', 'DonchianBreakout20_IEF', 'charts/donchian20_ief_equity.png')

# === 3. KAMA 10/2/30 on USDJPY=X ===
print("Generating KAMA reports...")
strat3 = KAMASlope(period=10, fast=2, slow=30)
bt3 = Backtest(df=df, strategy_instance=strat3, capital=100000.0, risk_pct=0.01, slippage_pips=2.0, ticker='USDJPY=X')
results3 = bt3.run()
folds3 = bt3.run_walk_forward(is_years=3, oos_years=1)
generate_markdown_report(results3['metrics'], folds3, 'USDJPY=X', 'KAMASlope10_2_30', 'reports/kama10_report.md')
export_trade_log(results3['trades'], 'reports/kama10_trades.csv')
plot_equity_curve(results3['equity'], results3['drawdown'], 'USDJPY=X', 'KAMASlope10_2_30', 'charts/kama10_equity.png')

# === 4. Ensemble: Donchian + KAMA on USDJPY=X ===
print("Generating ensemble...")
from scripts.bt.allocator import EnsemblePortfolio
bt_donchian = Backtest(df=df, strategy_instance=DonchianBreakout(period=20), capital=100000.0, risk_pct=0.01, slippage_pips=2.0, ticker='USDJPY=X')
bt_kama = Backtest(df=df, strategy_instance=strat3, capital=100000.0, risk_pct=0.01, slippage_pips=2.0, ticker='USDJPY=X')
r_donchian = bt_donchian.run()
r_kama = bt_kama.run()
ensemble = EnsemblePortfolio([r_donchian, r_kama], initial_capital=100000.0)
port_eq = ensemble.combine_equal_weighted()
port_iv = ensemble.combine_inverse_volatility()

# Save ensemble metrics
import pandas as pd
ensemble_metrics = {
    'equal_weight': {
        'CAGR': (port_eq['metrics']['Final_Value']/100000.0)**(1/((port_eq['equity'].index[-1]-port_eq['equity'].index[0]).days/365.25))-1,
        'Max_Drawdown': port_eq['metrics']['Max_Drawdown'],
        'Sharpe': port_eq['metrics']['Sharpe'],
        'Final_Value': port_eq['metrics']['Final_Value']
    },
    'inverse_volatility': {
        'CAGR': (port_iv['metrics']['Final_Value']/100000.0)**(1/((port_iv['equity'].index[-1]-port_iv['equity'].index[0]).days/365.25))-1,
        'Max_Drawdown': port_iv['metrics']['Max_Drawdown'],
        'Sharpe': port_iv['metrics']['Sharpe'],
        'Final_Value': port_iv['metrics']['Final_Value']
    }
}

with open('reports/ensemble_metrics.json', 'w') as f:
    json.dump(ensemble_metrics, f, indent=2, default=str)

# Plot ensemble equity curves
fig, ax = plt.subplots(1, 1, figsize=(12, 6))
ax.plot(r_donchian['equity'].index, r_donchian['equity'].values, label='Donchian 20', lw=1.5)
ax.plot(r_kama['equity'].index, r_kama['equity'].values, label='KAMA 10/2/30', lw=1.5)
ax.plot(port_eq['equity'].index, port_eq['equity'].values, label='Equal Weight Ensemble', lw=2)
ax.plot(port_iv['equity'].index, port_iv['equity'].values, label='Inverse Vol Ensemble', lw=2)
ax.set_title('Ensemble: Donchian 20 + KAMA 10/2/30 on USDJPY=X')
ax.set_ylabel('Portfolio Value ($)')
ax.legend()
ax.grid(True)
plt.tight_layout()
plt.savefig('charts/ensemble_equity.png', dpi=300)
plt.close()

print("\nAll reports generated!")
print(json.dumps(ensemble_metrics, indent=2, default=str))
