# Trend Following Research — Agent Context

## Project Overview
Systematic trend-following strategy research using walk-forward backtesting with
realistic cost models (2 pip slippage, 0.002% commission).

## Architecture
- `scripts/bt/` — Backtesting engine (engine, data, indicators, strategies, sizing, charts, reporting, allocator)
- `scripts/bt/indicators.py` — Technical indicators including Tom DeMark Sequential (td_setup, td_countdown, td_combo, td_st_demand, td_st_supply)
- `scripts/bt/strategies.py` — Strategy classes: DonchianBreakout, KAMASlope, KAMAAdaptivePositionSizing, TDSequentialCounterTrend, TDComboStrategy, TDSequentialBreakout
- `scripts/bt/engine.py` — Backtest simulation + walk-forward validation
- `JPY/` — Focused USDJPY=X research (TD Sequential vs Donchian 20)
- `JPY/run_jpy.py` — Run both Donchian 20 and TD Seq Breakout on USDJPY=X
- `JPY/correlation.py` — Signal/return correlation, trade overlap, TDST filter effectiveness, hybrid simulation
- `JPY/run_jpy_kama.py` — Run KAMA Slope + KAMA Adaptive Position Sizing vs Donchian 20
- `JPY/run_jpy_weekly.py` — Run KAMA variants + Donchian 20 on weekly USDJPY=X
- `JPY/run_jpy_ma200.py` — Run MA200 trend-following vs Donchian 20 on USDJPY=X daily
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
### Daily (29.6 years, ~7634 bars)
- Donchian 20: Sharpe +0.34, 137 trades, DD -32.71%, OOS avg Sharpe +0.03, 11/27 folds pass 0.4
- TD Seq Breakout: Sharpe +0.10, 87 trades, DD -19.40%, OOS avg Sharpe -0.05, 1/27 folds pass 0.4
- KAMA Slope: Sharpe -0.18, 854 trades, DD -38.48%, OOS avg Sharpe -0.26 (fails validation)
- KAMA Adaptive Size: Sharpe -1.10, 7129 trades, DD -55.28%, OOS avg Sharpe -1.30 (much worse)
- Donchian 20 + TD Breakout signal correlation: 0.40 (moderate, not redundant)
- TDST filter: keeps only 4.5% of breakouts, produces negative Sharpe (-0.17)

### Weekly (30 years, 1542 bars)
- Donchian 20 Weekly: Sharpe +0.17, 35 trades, DD -14.95%, OOS avg Sharpe -0.29, 8/27 folds pass 0.4
- KAMA Slope Weekly: Sharpe +0.08, 164 trades, DD -11.19%, OOS avg Sharpe -0.20, 10/27 folds pass 0.4
- KAMA Adaptive Size Weekly: Sharpe -0.48, 1440 trades, DD -7.50%, OOS avg Sharpe -0.80, 5/27 folds pass 0.4

### MA200 trend-following (daily, 29.6 years)
- MA200 Trend: Sharpe -0.02, 269 trades, DD -34.37%, OOS avg Sharpe -0.01, 10/27 folds pass 0.4
- Buy USD/sell JPY when Close > MA200, reverse when Close < MA200.
- **Fails validation** — roughly 2x the trades of Donchian 20 with no edge (Sharpe ~0, worse than Donchian).
- Suggests USDJPY does not exhibit a persistent 200-day trend; the visual impression of trend is not exploitable after costs.

### Key findings
- **No strategy passes walk-forward validation** on USDJPY=X at any frequency tested.
- Donchian 20 is the only strategy with a positive IS Sharpe (+0.34) and a decent profit factor (1.63).
- Weekly dramatically cuts drawdowns (14.95% vs 32.71%) but also cuts Sharpe (0.17 vs 0.34) and trades (35 vs 137).
- KAMA Slope IS Sharpe improves on weekly (+0.08 vs -0.18) but still fails OOS validation.
- KAMA Adaptive Position Sizing fails at BOTH frequencies — adaptive sizing amplifies losses in a noise-dominated regime.
- MA200 crossover produces 269 trades (~2x Donchian) with ~0 Sharpe — too many whipsaws on a mean-reverting pair.
- Weekly has fewer but larger bars; the 20-period Donchian is a 20-week (~100 trading day) lookback — much slower regime detection.
- **Verdict: No robust edge found on USDJPY=X at daily or weekly frequency.** The adaptive sizing concept (KAMA ER as regime gauge) does not translate to a profitable sizing rule on JPY.
- Recommended next step: relax Donchian period to ~10 on weekly, or test multiple JPY cross-pairs where trends may be stronger.

## Quick Start
```bash
cd trend/
python3 JPY/run_jpy.py               # TD Seq vs Donchian 20 on USDJPY=X daily
python3 JPY/correlation.py           # Correlation analysis
python3 JPY/run_jpy_kama.py          # KAMA variants vs Donchian 20 daily
python3 JPY/run_jpy_weekly.py        # KAMA variants + Donchian 20 on USDJPY=X weekly
python3 JPY/run_jpy_ma200.py          # MA200 trend-following vs Donchian 20 on USDJPY=X daily
```
