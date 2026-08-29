#!/usr/bin/env python3
"""
Backtest the SG Trader / Citi Institutional Research trade ideas.

Tests the research council's headline strategies across asset classes
available via yfinance (USDJPY=X, SPY, ^GSPC, CL=F, GC=F, DX-Y.NYB,
EURUSD=X, GLD, IEF). Walk-forward validation: 3yr expanding IS / 1yr OOS.

The report's core ideas:
  1. Short USD/JPY  @ 155.50, T 144.00, SL 159.20
  2. Long Gold      @ $2,460,   T $2,720,  SL $2,380
  3. Long SGX CN    @ 12,650,   T 14,800,  SL 11,900
  4. Long MES       @ 5,580,    T 6,050,   SL 5,420
  5. Long MCL       @ $77.50,   T $89.00,  SL $73.20
  6. Long SGP       @ 348,      T 388,     SL 335

yfinance proxies:  USDJPY=X (FX), SPY/^GSPC (MES), CL=F (MCL),
                   GC=F (Gold), GLD/IEF (cross-asset), DX-Y.NYB (USD).
SGX futures (CN, SGP) and spot XAUUSD are not available via yfinance.
"""
from scripts.bt.data import DataFeed
from scripts.bt.strategies import (
    DonchianBreakout, DonchianBreakoutWithFilter,
    DonchianBreakoutWithER, DonchianBreakoutDual,
    KAMASlope, KAMAAdaptivePositionSizing,
    TDSequentialCounterTrend, TDComboStrategy, TDSequentialBreakout,
)
from scripts.bt.engine import Backtest
from scripts.bt.reporting import generate_markdown_report, export_trade_log
from scripts.bt.charts import plot_equity_curve
import json
import os

REPORTS_DIR = os.path.join(os.path.dirname(__file__), 'reports')
os.makedirs(REPORTS_DIR, exist_ok=True)

feed = DataFeed()

# --- Asset classes to test (yfinance tickers) ---
TICKERS = ['USDJPY=X', 'SPY', '^GSPC', 'CL=F', 'GC=F', 'DX-Y.NYB', 'EURUSD=X', 'GLD', 'IEF']

# --- Strategies to benchmark ---
STRATEGIES = {
    'Donchian20': DonchianBreakout(period=20),
    'Donchian20_ADX25': DonchianBreakoutWithFilter(period=20, adx_threshold=25),
    'Donchian20_ER03': DonchianBreakoutWithER(period=20, er_threshold=0.3),
    'Donchian20_Dual': DonchianBreakoutDual(period_fast=20, period_slow=50),
    'KAMA10_2_30': KAMASlope(period=10, fast=2, slow=30),
    'TDSeqCounter': TDSequentialCounterTrend(),
    'TDCombo': TDComboStrategy(),
    'TDSequentialBreakout': TDSequentialBreakout(),
}

# Some tickers (FX) need smaller slippage; others need larger.
# USDJPY / EURUSD / DX-Y.NYB = FX (pip = 0.01 for JPY, 0.0001 otherwise).
# CL=F / GC=F / SPY = futures/equities.
TICKER_SLIPPAGE = {
    'USDJPY=X': 0.5,   # yen pair, tight
    'EURUSD=X': 0.5,
    'DX-Y.NYB': 0.5,
    'CL=F': 0.10,      # crude, points
    'GC=F': 0.15,      # gold, points
    'SPY': 0.05,
    '^GSPC': 0.5,
    'GLD': 0.10,
    'IEF': 0.10,
}
TICKER_COMMISSION = {
    'USDJPY=X': 0.00002,
    'EURUSD=X': 0.00002,
    'DX-Y.NYB': 0.00002,
    'CL=F': 0.0002,
    'GC=F': 0.0002,
    'SPY': 0.0002,
    '^GSPC': 0.0002,
    'GLD': 0.0002,
    'IEF': 0.0002,
}

CAPITAL = 100_000.0
RISK_PCT = 0.01  # 1% per trade (matches research risk discipline)

def run_ticker(ticker: str):
    """Run all strategies on a single ticker; return (full_results, folds_map)."""
    print(f"\n{'='*70}")
    print(f"  {ticker}")
    print(f"{'='*70}")
    try:
        df = feed.get_data(ticker, start='1995-01-01', end='2026-05-30')
    except Exception as e:
        print(f"  DATA ERROR: {e}")
        return None, None
    print(f"  Data: {df.shape[0]} rows, {df.index[0].date()} to {df.index[-1].date()}")

    full = {}
    folds_map = {}
    for sname, strat in STRATEGIES.items():
        try:
            sl = TICKER_SLIPPAGE.get(ticker, 2.0)
            co = TICKER_COMMISSION.get(ticker, 0.00002)
            bt = Backtest(df=df, strategy_instance=strat, capital=CAPITAL,
                          risk_pct=RISK_PCT, slippage_pips=sl,
                          commission_pct=co, ticker=ticker)
            res = bt.run()
            folds = bt.run_walk_forward(is_years=3, oos_years=1)
            m = res['metrics']
            oos = [f['oos_metrics']['Sharpe'] for f in folds]
            full[sname] = {
                'sharpe': m['Sharpe'], 'cagr': m['CAGR'],
                'trades': m['Total_Trades'], 'maxdd': m['Max_Drawdown'],
                'profit_factor': m['Profit_Factor'],
                'final_value': m['Final_Value'],
                'avg_oos': sum(oos)/len(oos) if oos else 0,
                'min_oos': min(oos) if oos else 0,
                'max_oos': max(oos) if oos else 0,
                'folds_geq_04': sum(1 for s in oos if s >= 0.4),
                'n_folds': len(oos),
            }
            folds_map[sname] = folds
            # Save per-strategy artifacts for the two best-ticker combos
            if ticker in ('USDJPY=X', '^GSPC', 'SPY', 'CL=F', 'GC=F') and sname in ('Donchian20', 'Donchian20_ADX25', 'Donchian20_ER03'):
                fname = f"{ticker.replace('^','')}_{sname}"
                generate_markdown_report(m, folds, ticker, sname,
                                         f'{REPORTS_DIR}/{fname}_report.md')
                export_trade_log(res['trades'], f'{REPORTS_DIR}/{fname}_trades.csv')
                plot_equity_curve(res['equity'], res['drawdown'], ticker, sname,
                                  f'{REPORTS_DIR}/{fname}_equity.png')
            print(f"  {sname:22s}: Sharpe={m['Sharpe']:+.2f}, Trades={m['Total_Trades']:3d}, "
                  f"DD={m['Max_Drawdown']:.2%}, OOS avg={sum(oos)/len(oos):+.2f} ({sum(1 for s in oos if s>=0.4)}/{len(oos)} >=0.4)")
        except Exception as e:
            print(f"  {sname:22s}: ERROR - {str(e)[:70]}")
            full[sname] = {'sharpe': 0, 'cagr': 0, 'trades': 0, 'maxdd': 0,
                           'profit_factor': 1, 'final_value': CAPITAL,
                           'avg_oos': 0, 'min_oos': 0, 'max_oos': 0,
                           'folds_geq_04': 0, 'n_folds': 0}
            folds_map[sname] = []

    return full, folds_map


def main():
    all_results = {}      # ticker -> {strategy: metrics}
    all_folds = {}        # ticker -> {strategy: folds}

    for t in TICKERS:
        full, folds = run_ticker(t)
        if full is not None:
            all_results[t] = full
            all_folds[t] = folds

    # ---- Summary tables ----
    print("\n" + "="*90)
    print("  CROSS-ASSET STRATEGY BENCHMARK SUMMARY")
    print("="*90)
    print(f"\n  {'Ticker':12s} {'Strategy':22s} {'Sharpe':>7s} {'CAGR':>8s} {'Trades':>6s} {'MaxDD':>7s} "
          f"{'PF':>5s} {'OOS avg':>7s} {'>=0.4':>5s}")
    print("  " + "-"*88)
    summary_rows = []
    for t in TICKERS:
        for sname in STRATEGIES:
            r = all_results[t][sname]
            print(f"  {t:12s} {sname:22s} {r['sharpe']:+.2f}   {r['cagr']:+.2%}   {r['trades']:3d}   "
                  f"{r['maxdd']:5.1%}  {r['profit_factor']:5.2f} {r['avg_oos']:+.2f}   {r['folds_geq_04']}/{r['n_folds']}")
            summary_rows.append({
                'ticker': t, 'strategy': sname,
                **{k: v for k, v in r.items() if k not in ('n_folds',)}
            })

    # ---- Walk-forward pass-rate by ticker ----
    print("\n  === WALK-FORWARD PASS RATE (OOS Sharpe >= 0.4) ===")
    print(f"  {'Ticker':12s} {'Strategy':22s} {'Passes':>6s} {'Folds':>5s} {'Rate':>6s}")
    for t in TICKERS:
        for sname in STRATEGIES:
            r = all_results[t][sname]
            rate = r['folds_geq_04'] / r['n_folds'] if r['n_folds'] else 0
            print(f"  {t:12s} {sname:22s} {r['folds_geq_04']:2d}/{r['n_folds']:<2d}   {rate:5.0%}")

    # ---- Save full JSON ----
    json.dump(all_results, open(f'{REPORTS_DIR}/backtest_results.json', 'w'), indent=2, default=str)
    json.dump({t: {s: [{'fold_num': i+1, **{k: (v.get(k) if isinstance(v, dict) else v) for k in v}} for i, v in enumerate(folds[s])]}
                 for t, folds in all_folds.items() for s in folds},
              open(f'{REPORTS_DIR}/backtest_folds.json', 'w'), indent=2, default=str)

    # ---- Key findings ----
    print("\n" + "="*90)
    print("  KEY FINDINGS")
    print("="*90)
    # Best Sharpe combos
    scored = [(t, s, r['sharpe'], r['avg_oos'], r['folds_geq_04'], r['n_folds'])
              for t in all_results for s, r in all_results[t].items() if r['n_folds'] > 0]
    scored.sort(key=lambda x: x[2], reverse=True)
    print("\n  Top 10 by IS Sharpe:")
    for t, s, sh, oos, passes, n in scored[:10]:
        print(f"    {t:12s} {s:22s} Sharpe={sh:+.2f}  OOS avg={oos:+.2f}  passes={passes}/{n}")

    # USDJPY short-side insight: does trend-following short work?
    print("\n  USDJPY=X specific (the report's headline SHORT USD/JPY idea):")
    if 'USDJPY=X' in all_results:
        for s, r in all_results['USDJPY=X'].items():
            print(f"    {s:22s}: Sharpe={r['sharpe']:+.2f}, Trades={r['trades']}, OOS avg={r['avg_oos']:+.2f}, >=0.4: {r['folds_geq_04']}/{r['n_folds']}")

    # Gold proxy
    print("\n  Gold proxies (GC=F, GLD) — the report's LONG GOLD idea:")
    for t in ('GC=F', 'GLD'):
        if t in all_results:
            best = max(all_results[t].items(), key=lambda x: x[1]['sharpe'])
            print(f"    {t}: best={best[0]} Sharpe={best[1]['sharpe']:+.2f} OOS avg={best[1]['avg_oos']:+.2f}")

    # Equity index
    print("\n  Equity index proxies (SPY, ^GSPC) — the report's LONG MES idea:")
    for t in ('SPY', '^GSPC'):
        if t in all_results:
            best = max(all_results[t].items(), key=lambda x: x[1]['sharpe'])
            print(f"    {t}: best={best[0]} Sharpe={best[1]['sharpe']:+.2f} OOS avg={best[1]['avg_oos']:+.2f}")

    # Crude
    print("\n  Crude proxy (CL=F) — the report's LONG MCL idea:")
    if 'CL=F' in all_results:
        for s, r in all_results['CL=F'].items():
            print(f"    {s:22s}: Sharpe={r['sharpe']:+.2f}, Trades={r['trades']}, OOS avg={r['avg_oos']:+.2f}")

    # Save summary CSV for quick reference
    import csv
    with open(f'{REPORTS_DIR}/backtest_summary.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['ticker','strategy','sharpe','cagr','trades','maxdd','profit_factor','final_value','avg_oos','min_oos','max_oos','folds_geq_04','n_folds'])
        for t in all_results:
            for s, r in all_results[t].items():
                w.writerow([t, s, r['sharpe'], r['cagr'], r['trades'], r['maxdd'],
                            r['profit_factor'], r['final_value'], r['avg_oos'],
                            r['min_oos'], r['max_oos'], r['folds_geq_04'], r['n_folds']])

    print(f"\n  Saved: {REPORTS_DIR}/backtest_results.json")
    print(f"  Saved: {REPORTS_DIR}/backtest_folds.json")
    print(f"  Saved: {REPORTS_DIR}/backtest_summary.csv")

if __name__ == '__main__':
    main()
