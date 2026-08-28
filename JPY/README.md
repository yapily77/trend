# JPY Trend-Following Research

Bead: `trend-5ev` (P1, epic, research, USDJPY) — CLOSED

## Status
**Complete.** Research concluded.

## Verdict
**TD Sequential does NOT make money on JPY as a standalone trend-following system.**
- TD Seq Breakout: Sharpe +0.10 vs Donchian 20 baseline +0.34
- Only 1/27 OOS folds pass the 0.4 Sharpe threshold
- Counter-trend strategies (Counter-Trend, Combo) produce ~0 trades on daily JPY data

## Correlation Analysis (NEW — see `JPY/reports/jpy_correlation.json`)
- Donchian 20 and TD Breakout signal correlation: **0.40** (moderate, not redundant)
- Donchian 20 and TD Breakout return correlation: **0.43** (moderate)
- They agree on direction only 48% of the time with 16% direct conflict
- TDST filter is too restrictive: keeps only 4.5% of breakouts, Sharpe -0.17
- Loose TDST filter (forward-filled): keeps 22% of breakouts, Sharpe **worsens** to -0.17
- **TD Sequential does NOT improve Donchian 20 on daily JPY data**

## Why combining fails
Donchian 20 and TD Breakout have moderate correlation (0.40 signal / 0.43 return). They are neither redundant enough to stack bets nor complementary enough to expect a big win. The TDST filter is too coarse on daily data — it keeps only 4.5% of breakouts and produces negative Sharpe. The TD 13-bar countdown almost never fires on daily JPY because prices rarely make 13 straight days of lower lows relative to 2-day-old lows.

## Recommended next step
Test on **weekly data** where TD Sequential was originally designed, or relax the countdown to a wider window (30+ bars) and test the TD 9-Count as a lightweight trend filter rather than a standalone signal.

## Validation Rules
- 2 pip slippage mandatory, 0.002% commission
- Canonical parameters only — no optimization
- 3-year expanding IS / 1-year OOS walk-forward
- Reject if OOS Sharpe < 0.4, max DD > 30%

## Output
- Scripts: `JPY/run_jpy.py`, `JPY/correlation.py`
- Reports: `JPY/reports/` (md, json, csv)
- Charts: `JPY/charts/` (png)
- Research plan: `JPY/research_plan.md`
