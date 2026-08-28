# JPY Trend-Following Research

Bead: `trend-5ev` (P1, epic, research, USDJPY)

## Status
planned — work begins now

## Context
Previous LLM session left off with **partial TD Sequential analysis** on USDJPY=X (1996-2026, 29.6 years).
The prior run had: data download, strategy implementation, backtesting, and walk-forward validation —
but never concluded whether TD Sequential can make money on JPY.

## Known Results (TD Seq Breakout on USDJPY=X)
- Sharpe +0.10, 87 trades, DD -19.40%, OOS avg Sharpe -0.05, 1/27 folds >= 0.4
- Donchian 20 baseline: Sharpe +0.34, 137 trades, DD -32.71%, 11/27 folds >= 0.4
- TD Seq counter-trend: -0.12 Sharpe, 1 trade (sell countdown never fires)
- TD Combo: +0.15 Sharpe, 1 trade (too restrictive)
- TD Seq Breakout only works on USDJPY=X; zero trades on SPY/QQQ/GLD/IEF

## Validation Rules
- 2 pip slippage mandatory, 0.002% commission
- Canonical parameters only — no optimization
- 3-year expanding IS / 1-year OOS walk-forward
- Reject if OOS Sharpe < 0.4, max DD > 30%, or significant IS→OOS drop

## Work Items
- [ ] Design JPY strategy research plan
- [ ] Re-run TD Sequential on USDJPY=X with corrected logic
- [ ] Compare TD Seq vs Donchian 20 baseline on USDJPY=X
- [ ] Cross-asset scan (SPY, QQQ, GLD, IEF, EURUSD, GBPUSD, AUDUSD, USDCAD)
- [ ] Equity charts + trade logs + markdown reports
- [ ] Conclusion: does TD Sequential make money on JPY?

## Data
- Source: yfinance (`USDJPY=X`, 1995-01-01 to 2026-05-30)
- Existing scripts: `scripts/bt/` (engine, indicators, strategies, data, reporting, charts, sizing, allocator)
- Strategy classes in `scripts/bt/strategies.py`: `TDSequentialCounterTrend`, `TDComboStrategy`, `TDSequentialBreakout`
- Indicators in `scripts/bt/indicators.py`: `td_setup`, `td_buy_setup`, `td_sell_setup`, `td_buy_countdown`, `td_sell_countdown`, `td_combo`, `td_st_demand`, `td_st_supply`

## Output
- Reports: `JPY/reports/` (md + json + csv)
- Charts: `JPY/charts/` (png)
- Trade logs: `JPY/reports/` (csv)
