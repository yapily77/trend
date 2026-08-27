# Trend Research — Reports Index

## Strategy Reports
- `donchian20_baseline_report.md` — Donchian 20 on USDJPY=X (29.6yr)
- `donchian20_adx25_report.md` — Donchian 20 + ADX > 25 filter
- `td_seq_breakout_report.md` — TD Sequential Breakout on USDJPY=X

## Metrics JSON
- `summary.json` — Donchian 20 + KAMA 10 summary (29.6yr)
- `ensemble_metrics.json` — Ensemble (EW + inverse vol) results
- `main_results.json` — All Donchian 20 variants on USDJPY=X
- `cross_asset.json` — Cross-asset Donchian 20 comparison
- `td_seq_results.json` — TD Sequential strategy results
- `filter_test_results.json` — Filter comparison across assets (deprecated)

## Folds JSON (walk-forward)
- `donchian20_baseline_folds.json` — 27-fold walk-forward
- `donchian20_adx25_folds.json` — 27-fold walk-forward (ADX variant)
- `td_seq_breakout_folds.json` — 27-fold walk-forward (TD Seq)
- `kama10_folds.json` — 27-fold walk-forward (KAMA)

## Trade Logs (CSV)
- `donchian20_baseline_trades.csv` — 137 trades
- `donchian20_adx25_trades.csv` — 197 trades
- `td_seq_breakout_trades.csv` — 87 trades
- `kama10_trades.csv` — 1110 trades

## Charts (PNG)
- `donchian20_baseline_equity.png`
- `donchian20_adx25_equity.png`
- `donchian20_ief_equity.png`
- `kama10_equity.png`
- `ensemble_equity.png`
- `td_seq_breakout_equity.png`

## Research Notes
- `RESEARCH_SUMMARY.md` — Complete research summary with regime filter analysis
- `cross_asset_results.json` — Cross-asset scan results (21yr, deprecated)

## How to Run
```bash
cd trend/
python3 final_all.py          # Full backtest suite
python3 scripts/bt/engine.py  # Individual backtest
```

## Rules
- **Data**: min_years=25 (yfinance caps FX at ~29.6yr)
- **Cost**: 2 pip slippage, 0.002% commission
- **Validation**: 3yr IS / 1yr OOS walk-forward
- **Rejection**: OOS Sharpe < 0.4 OR max DD > 30%
- **No parameter optimization**
