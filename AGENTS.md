# Trend Following Research — Agent Context

## Project Overview
Systematic trend-following strategy research using walk-forward backtesting with
realistic cost models (2 pip slippage, 0.002% commission).

## Architecture
- `scripts/bt/` — Backtesting engine (engine, data, indicators, strategies, sizing, charts, reporting, allocator)
- `scripts/bt/indicators.py` — Technical indicators including Tom DeMark Sequential (td_setup, td_countdown, td_combo, td_st_demand, td_st_supply)
- `scripts/bt/strategies.py` — Strategy classes: DonchianBreakout, KAMASlope, TDSequentialCounterTrend, TDComboStrategy, TDSequentialBreakout
- `scripts/bt/engine.py` — Backtest simulation + walk-forward validation
- `JPY/` — Focused USDJPY=X research (TD Sequential vs Donchian 20)
- `JPY/run_jpy.py` — Run both Donchian 20 and TD Seq Breakout on USDJPY=X
- `JPY/correlation.py` — Signal/return correlation, trade overlap, TDST filter effectiveness, hybrid simulation
- `JPY/reports/` — Fold JSONs, trade logs, results, correlation JSON
- `JPY/charts/` — Equity curve PNGs

## Beads Issue Tracker (bd)
This project uses `bd` (beads) for issue tracking. Run `bd prime` for full workflow context.
- Database: local Dolt (embedded), no remote configured
- Issues: `bd list`, `bd show <id>`, `bd create`, `bd update`, `bd close`
- All task tracking goes through `bd`, not TodoWrite/TaskCreate

## Validation Rules
- 2 pip slippage mandatory, 0.002% commission
- Canonical parameters only — no optimization
- 3-year expanding IS / 1-year OOS walk-forward
- Reject if OOS Sharpe < 0.4, max DD > 30%, or significant IS→OOS drop

## Known Results (USDJPY=X, 1996-2026)
- Donchian 20: Sharpe +0.34, 137 trades, DD -32.71%, OOS avg Sharpe +0.03, 11/27 folds pass 0.4
- TD Seq Breakout: Sharpe +0.10, 87 trades, DD -19.40%, OOS avg Sharpe -0.05, 1/27 folds pass 0.4
- KAMA Slope: Sharpe -0.18, 854 trades, DD -38.48%, OOS avg Sharpe -0.26 (fails validation)
- KAMA Adaptive Size: Sharpe -1.10, 7129 trades, DD -55.28%, OOS avg Sharpe -1.30 (much worse)
- Donchian 20 + TD Breakout signal correlation: 0.40 (moderate, not redundant)
- Donchian 20 + TD Breakout return correlation: 0.43
- TDST filter: keeps only 4.5% of breakouts, produces negative Sharpe (-0.17)
- Verdict: TD Sequential does NOT make money on JPY as standalone trend-following; does NOT improve Donchian 20 as a filter on daily data
- KAMA (Kaufman's Adaptive MA) does NOT make money on JPY daily data; adaptive sizing made it much worse
- Recommended next step: test on weekly data (TD Sequential was designed for weekly charts)

## Quick Start
```bash
cd trend/
python3 JPY/run_jpy.py          # Run TD Seq vs Donchian 20 on USDJPY=X
python3 JPY/correlation.py      # Run correlation analysis
```
