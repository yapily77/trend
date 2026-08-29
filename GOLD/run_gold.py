"""Gold trend-following research — run from trend/ root.
Loads GC=F (COMEX Gold Futures), runs Donchian 20 baseline + regime filters,
3-year expanding IS / 1-year OOS walk-forward.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')

from scripts.bt.data import DataFeed
from scripts.bt.strategies import DonchianBreakout, DonchianBreakoutWithFilter, KAMASlope
from scripts.bt.engine import Backtest
from scripts.bt.reporting import generate_markdown_report, export_trade_log
from scripts.bt.charts import plot_equity_curve
from scripts.data.fred import build_gold
import json, os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reports')
CHARTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'charts')
os.makedirs(OUT, exist_ok=True)
os.makedirs(CHARTS, exist_ok=True)

# Gold from GC=F (COMEX futures). First available bar ~2000-08-30.
GOLD_START = '2000-08-30'
GOLD_END   = '2026-05-30'

# Build a locally-cached daily gold series from FRED (yfinance fallback).
gold_df = build_gold(start=GOLD_START, end=GOLD_END)
gold_df = gold_df[['GOLD']].rename(columns={'GOLD': 'Close'})
# DataFeed expects OHLCV; synthesize OHLC from Close for compatibility.
gold_df['Open'] = gold_df['Close']
gold_df['High'] = gold_df['Close']
gold_df['Low'] = gold_df['Close']
gold_df['Volume'] = 0

print(f"Gold data loaded: {gold_df.shape[0]} rows, {gold_df.index[0].date()} to {gold_df.index[-1].date()}")

# ---- Strategy run helper ----
def run(name, strat, ticker='GC=F'):
    print(f"\n=== {name} ===")
    bt = Backtest(df=gold_df, strategy_instance=strat, capital=100000.0, risk_pct=0.01,
                  slippage_pips=2.0, ticker=ticker)
    r = bt.run()
    folds = bt.run_walk_forward(is_years=3, oos_years=1)
    m = r['metrics']
    oos = [f['oos_metrics']['Sharpe'] for f in folds]
    out = {
        'sharpe': m['Sharpe'], 'cagr': m['CAGR'], 'trades': m['Total_Trades'],
        'maxdd': m['Max_Drawdown'], 'profit_factor': m['Profit_Factor'],
        'final_value': m['Final_Value'],
        'avg_oos': sum(oos)/len(oos), 'min_oos': min(oos), 'max_oos': max(oos),
        'folds_geq_4': sum(1 for s in oos if s>=0.4), 'total_folds': len(oos),
        'n_folds_pass': sum(1 for s in oos if s>=0.4),
    }
    print(f"  Sharpe={m['Sharpe']:+.2f}, CAGR={m['CAGR']:+.2%}, Trades={m['Total_Trades']}, DD={m['Max_Drawdown']:.2%}")
    print(f"  OOS avg Sharpe={sum(oos)/len(oos):+.2f}, min={min(oos):+.2f}, >=0.4 in {sum(1 for s in oos if s>=0.4)}/{len(oos)}")
    with open(os.path.join(OUT, f'gold_{name.lower().replace(" ","_")}_folds.json'), 'w') as f:
        json.dump(folds, f, default=str)
    generate_markdown_report(m, folds, ticker, name,
                             os.path.join(OUT, f'gold_{name.lower().replace(" ","_")}_report.md'))
    export_trade_log(r['trades'], os.path.join(OUT, f'gold_{name.lower().replace(" ","_")}_trades.csv'))
    plot_equity_curve(r['equity'], r['drawdown'], ticker, name,
                      os.path.join(CHARTS, f'gold_{name.lower().replace(" ","_")}_equity.png'))
    return out

results = {}
results['Donchian20'] = run('Donchian 20', DonchianBreakout(period=20))
results['Donchian20_ADX25'] = run('Donchian 20 ADX25', DonchianBreakoutWithFilter(period=20, adx_threshold=25.0))
results['Donchian20_KAMA10'] = run('Donchian 20 KAMA10', DonchianBreakout(period=20))

with open(os.path.join(OUT, 'gold_results.json'), 'w') as f:
    json.dump(results, f, indent=2, default=str)

print("\n=== Gold Summary ===")
print(json.dumps(results, indent=2, default=str))
print("\nAll gold reports saved to GOLD/reports/ and GOLD/charts/")
