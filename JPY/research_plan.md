# JPY Trend-Following Research — Strategy Plan

Bead: `trend-5ev` (P1, epic, research, USDJPY) — CLOSED

## Question
Does Tom DeMark Sequential make money on JPY (USDJPY=X)? And can we combine it
with Donchian 20 to improve the baseline?

## Known Results (reproduced and confirmed by re-run)

| Strategy | Sharpe | CAGR | Trades | Max DD | OOS Avg Sharpe | Folds >= 0.4 |
|---|---|---|---|---|---|---|
| Donchian 20 (baseline) | +0.34 | +1.88% | 137 | -32.71% | +0.03 | 11/27 |
| TD Seq Breakout | +0.10 | +0.38% | 87 | -19.40% | -0.05 | 1/27 |
| TD Counter-Trend | -0.12 | — | 1 | -41.54% | +0.01 | 1/27 |
| TD Combo | +0.15 | — | 1 | -24.81% | +0.00 | 1/27 |

## Verdict: TD Sequential does NOT make money on JPY as a standalone trend-following system
- Sharpe is 1/3 of Donchian 20 baseline and worse than cash after costs over 29.6 years ($111,940 vs $173,617 on $100k).
- Only 1 of 27 OOS folds passes the 0.4 Sharpe threshold — the edge is not robust.
- Counter-trend strategies produce essentially zero trades on daily JPY data.
- Fundamental issue: TD Sequential was designed for **weekly** charts as a counter-trend/exhaustion system. On daily JPY data, the 13-bar countdown almost never fires and the 9-bar setup rarely completes.

## Correlation Analysis (see `JPY/reports/jpy_correlation.json`)

### Signal correlation (daily, valid bars)
| | Donchian 20 | TD Breakout | TD CounterTrend | TD Combo |
|---|---|---|---|---|
| Donchian 20 | 1.000 | **0.400** | -0.036 | 0.036 |
| TD Breakout | 0.400 | 1.000 | -0.014 | 0.014 |
| TD CounterTrend | -0.036 | -0.014 | 1.000 | -0.999 |
| TD Combo | 0.036 | 0.014 | -0.999 | 1.000 |

**Key finding:** Donchian 20 and TD Breakout have only a **moderate signal correlation of 0.40** — they are NOT redundant. They agree on direction only 48% of the time, with 16% direct conflict (Donchian says long, TD says short or vice versa). This means combining them *could* reduce trades and cut losing positions, but it would also cut winning positions.

### Return correlation
| | Donchian 20 | TD Breakout | TD CounterTrend | TD Combo |
|---|---|---|---|---|
| Donchian 20 | 1.000 | **0.429** | -0.130 | 0.112 |
| TD Breakout | 0.429 | 1.000 | 0.170 | -0.210 |
| TD CounterTrend | -0.130 | 0.170 | 1.000 | -0.970 |
| TD Combo | 0.112 | -0.210 | -0.970 | 1.000 |

**Key finding:** Return correlation is **0.43** — modestly correlated, so combining would not create massive redundancy, but it also wouldn't provide strong diversification. Both strategies win/lose on some of the same trades.

### TDST filter effectiveness
- **50.1%** of TDST-valid long breakouts are aligned with TDST demand (price > demand).
- **47.1%** of TDST-valid short breakouts are aligned with TDST supply (price < supply).
- But TDST demand/supply levels only exist at setup completion bars (1,113 setups over 29.6 years).
- Result: a strict TDST-aligned Donchian hybrid would filter out **~95%** of breakouts and produce **negative Sharpe (-0.17)** — TDST is too restrictive as a filter on daily JPY data.
- A looser hybrid (forward-filled TDST) keeps 22% of breakouts (1,648 signals), Sharpe **-0.17**, DD -23.72% — **worse than both baselines**.

### TD setup statistics
- Buy setups completed (9): **663** over 29.6 years (~22/year)
- Sell setups completed (9): **450** (~15/year)
- Buy countdowns completed (13): **26** (~0.9/year) — countdowns almost never fire
- Sell countdowns completed (13): **0** — never fires on an upward-trending JPY pair
- 1,113 total setups, but only **87 TD Seq Breakout trades** (out of 7,634 Donchian signals)

### Conclusion on combining
- Donchian 20 and TD Breakout have **moderate correlation (0.40 signal / 0.43 return)** — not redundant, not complementary enough to expect a big win from combination.
- The strict TDST filter is **too restrictive**: it keeps only 4.5% of breakouts and produces negative Sharpe.
- The loose TDST filter is **too loose and too slow** (forward-filled TDST only updates at setup completion): it keeps 22% of breakouts but **worsens** Sharpe from +0.34 to -0.17.
- **TD Sequential does NOT meaningfully improve Donchian 20 on daily JPY data.** The setup concept is sound, but on daily data it fires too infrequently and the TDST levels are too coarse to filter breakouts effectively.
- **Recommended next step:** Test on **weekly data** where TD Sequential was originally designed, or relax the countdown to a wider window (30+ bars) and test the TD 9-Count as a lightweight trend filter rather than a standalone signal.

## Planned fixes to investigate
- [ ] Weekly data: TD Sequential was designed for weekly charts — test there
- [ ] Relax countdown window to 30 bars — see if more signals fire with better quality
- [ ] TD 9-Count (setup only) as a lightweight trend filter — check if 9-bar momentum adds value
- [ ] Hybrid Donchian 20 + TDST with forward-fill and lookback window (not point-in-time)
- [ ] Multiple JPY pairs (EURJPY, GBPJPY, AUDJPY) — TD might work better on cross-pairs
- [ ] Try TD Sequential on weekly USDJPY chart (different regime entirely)

## Validation Rules
- Reject if OOS Sharpe < 0.4 → TD Seq fails (1/27 folds)
- Reject if max DD > 30% → TD Seq passes (-19.40%), Donchian 20 fails (-32.71%)
- Reject if significant IS→OOS drop → both show decline

## Data
- Source: yfinance (`USDJPY=X`, 1995-01-01 to 2026-05-30)
- Cost model: 2 pip slippage, 0.002% commission
- Validation: 3-year expanding IS / 1-year OOS walk-forward

## Output
- Scripts: `JPY/run_jpy.py`, `JPY/correlation.py`
- Reports: `JPY/reports/` (md, json, csv)
- Charts: `JPY/charts/` (png)
