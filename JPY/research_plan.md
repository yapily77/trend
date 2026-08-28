# JPY Trend-Following Research — Strategy Plan

Bead: `trend-5ev` (P1, epic, research, USDJPY)

## Question
Does Tom DeMark Sequential make money on JPY (USDJPY=X)?

## Known Results (reproduced and confirmed by re-run)

| Strategy | Sharpe | CAGR | Trades | Max DD | OOS Avg Sharpe | Folds >= 0.4 |
|---|---|---|---|---|---|---|
| Donchian 20 (baseline) | +0.34 | +1.88% | 137 | -32.71% | +0.03 | 11/27 |
| TD Seq Breakout | +0.10 | +0.38% | 87 | -19.40% | -0.05 | 1/27 |
| TD Counter-Trend | -0.12 | — | 1 | -41.54% | +0.01 | 1/27 |
| TD Combo | +0.15 | — | 1 | -24.81% | +0.00 | 1/27 |

## Verdict
**No — TD Sequential does NOT make money on JPY as a trend-following system.**
- Sharpe is 1/3 of the Donchian 20 baseline and worse than cash after costs over 29.6 years ($111,940 vs $173,617 on $100k).
- Only 1 of 27 OOS folds passes the 0.4 Sharpe threshold — the edge is not robust.
- The counter-trend strategies (Counter-Trend, Combo) produce essentially zero trades on daily JPY data.
- The fundamental issue: TD Sequential was designed for **weekly** charts as a counter-trend/exhaustion system. On daily JPY data:
  - The 13-bar consecutive countdown (`close < low[i-2]`) almost never fires — prices rarely make 13 straight days of lower lows relative to 2-day-old lows.
  - The 9-bar consecutive setup (`close > close[i-4]`) rarely completes on JPY because the pair trends in waves with many choppy pullbacks.
  - TDST demand/supply levels are meaningful as S/R, but the breakout entry filter is too restrictive, missing most valid breakouts.

## Work Items
- [x] Reproduce TD Sequential backtest on USDJPY=X (1996-2026) — `JPY/run_jpy.py`
- [x] Compare TD Seq vs Donchian 20 baseline on USDJPY=X — see `JPY/reports/`
- [x] Walk-forward validation (3yr IS / 1yr OOS) — see `JPY/reports/jpy_*_folds.json`
- [ ] Investigate fixes to TD Sequential on JPY (research only):
  - [ ] Weekly data: TD Sequential was designed for weekly charts
  - [ ] Relax countdown window (already done: 20-bar window; try 30-bar)
  - [ ] Use TD 9-Count (setup only) as a trend filter, not standalone signal
  - [ ] Combine TDST levels with Donchian breakout (hybrid)
  - [ ] Try TD Sequential on multiple JPY pairs (EURJPY, GBPJPY, AUDJPY)
- [ ] Document findings and conclusion

## Rejection Rules
- Reject if OOS Sharpe < 0.4 → TD Seq fails (1/27 folds)
- Reject if max DD > 30% → TD Seq passes (-19.40%), Donchian 20 fails (-32.71%)
- Reject if significant IS→OOS drop → both show decline

## Data
- Source: yfinance (`USDJPY=X`, 1995-01-01 to 2026-05-30)
- Cost model: 2 pip slippage, 0.002% commission
- Validation: 3-year expanding IS / 1-year OOS walk-forward

## Output
- Scripts: `JPY/run_jpy.py`
- Reports: `JPY/reports/` (md, json, csv)
- Charts: `JPY/charts/` (png)
- Fold JSONs: `JPY/reports/jpy_donchian20_folds.json`, `JPY/reports/jpy_td_seq_breakout_folds.json`
- Trade logs: `JPY/reports/jpy_donchian20_trades.csv`, `JPY/reports/jpy_td_seq_breakout_trades.csv`
