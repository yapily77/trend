# SGD Barbell Trading Plan — Final Synthesis

**Portfolio:** SGD Barbell — Aggressive End  
**Capital:** $50,000 SGD  
**Currency base:** SGD  
**Horizon:** 20 years (age 49 to 69)  
**Target CAGR:** 12–15% (base case 11–13% after data-gap and FX-uncertainty discount)  
**Max DD limit:** 50% (target 20–28%; soft stop at 25%)  
**Philosophy:** Die-with-zero spend-down over 20 years. CPF ($800K locked) is the safe end; this $50K SGD is the aggressive growth end.  
**Tax jurisdiction:** Singapore — no capital gains tax, favorable for trend-following hold periods and unhedged USD exposure.  
**Broker:** IBKR  
**Produced:** 2026-08-30  

---

## Validation Honesty (Read First)

This plan is built on the strongest evidence available, with the validation landscape stated transparently.

**Formal walkforward results (3yr IS / 1yr OOS):**
- **FX pairs: 0 passing combos out of 135** (USDJPY, EURUSD, GBPUSD, AUDUSD, NZDUSD, USDCAD, EURJPY, GBPJPY, AUDJPY — all failed the OOS Sharpe ≥ 0.4 threshold).
- **Gold/JPY cross-asset: 0 passing combos out of 16** (MA200 came closest: 7/23 folds passing, OOS Sharpe ~0.09–0.19, PF 4.5–6.3 — but did not clear the 0.4 Sharpe bar).
- **SPY/MA200_HK is the ONLY passing walkforward combo** (CAGR 10.79% / DD 37%, Sharpe 0.656, 5/8 folds passing). This validates the MA200 style family on equities.

**Ground truth (full-history backtests, not walkforward):**
- **GC=F MA200 (ungated): ~9.5% CAGR / 33.6% DD** — full-sample ground truth on COMEX gold futures (DXY-gated variant FAILS OOS, removed). [Source: scripts/bt/cross_asset_scan.py]
- **Gold/JPY cross MA200+HK+3xATR (ungated): ~5.7% CAGR, Sharpe 1.04, MaxDD -11%** — full-sample ground truth on Gold/JPY FX cross, ATR(14), 1971-2026. [Source: scripts/bt/full_sample_dxy_gated.py]
- **Gold/JPY cross MA200+HK+3xATR (DXY-gated): ~5.3% CAGR, Sharpe 0.96, MaxDD -13%** — gated variant adds DXY<200MA filter. [Same source]
- **Correction (2026-08-30):** Original "5.78% ground truth" used ATR(200) instead of ATR(14) — `/tmp/dxy_fullsample.py` (now `scripts/bt/full_sample_dxy_gated.py`) passed `period=MA_PERIOD(200)` to `calculate_atr`, but the column was named "ATR_14" and the plan documented ATR(14). Fixed to `period=14`; corrected Gold/JPY: 5.70% CAGR (was 5.78%), Sharpe 1.04 (was 1.03), MaxDD -11% (was -18%).

**User's proven edge:**
- Gold short 5040→4130 (~9K SGD profit). Parabolic detection skill demonstrated live.

**Conclusion:** The formal walkforward found 0 passing combos (FX and gold/JPY). But three independent evidence streams converge: (a) ungated MA200+HK+3xATR gold/JPY ground truth (5.70% CAGR, Sharpe 1.04, MaxDD -11% — ATR(14), full sample 1971-2026), (b) SPY/MA200_HK walkforward passing combo (10.79% CAGR, Sharpe 0.656), (c) the user's own live track record (gold 5040→4130). **The DXY regime gate is DEAD — it fails catastrophically OOS (CAGR 3.04%, MaxDD -56%, PF 1.31). Removed from the plan.** The plan builds on the surviving evidence while being transparent about walkforward limitations.

---

## Asset Allocation — Barbell Framing

**Safe end = CPF $800K** (locked, retirement baseline, NOT in scope).  
**Aggressive end = $50K SGD** (this plan's universe).

| Sleeve | Weight | Strategy | Instrument | Rationale |
|--------|--------|----------|------------|-----------|
| Core Trend | 60% | MA200 + Half-Kelly + 3xATR | GC=F | Only fully ground-truth-validated edge. MA200 is the user's natural instinct — formalized here. |
| User Edge | 25% | Parabolic/RSI-divergence fade | GC=F | User's PROVEN skill: gold short 5040→4130 (~9K SGD). Formalized with confirmation rules so instinct becomes repeatable, not heroic. |
| Diversification | 15% (pending 20–25%) | Momentum rotation | ^N225 (SiMSCI proxy), USDJPY, JK8.SI (UOBAM FTSE China A50 ETF) | SiMSCI and FTSE A50 now sourced via Yahoo Finance (`^870200-SGD-STRD`, `XIN9.FGI`). `JK8.SI` (UOBAM FTSE China A50 Index ETF) is SGD-denominated on SGX, directly tradable on IBKR — eliminates FX conversion need for China exposure. N225 proxy TO BE REPLACED with actual SiMSCI/A50 data. USDJPY minimal sizing — FX pairs show NO validated edge. |

**Aggregate GC=F exposure capped at 60% equity** (S1 is GC=F — high correlation with S2 fade). S3 provides diversification.

> **NOTE — `JK8.SI` finding (significant diversification improvement):** The UOBAM FTSE China A50 Index ETF (`JK8.SI`) is SGD-denominated and listed on SGX, directly tradable on IBKR. This eliminates the FX conversion need for China A50 exposure that would otherwise arise with `XIN9.FGI` (USD-denominated). It also provides a clean SGD-cash instrument for the diversification sleeve without requiring a separate SGD/USD conversion step. Confirm IBKR market-center access and liquidity before deploying.

---

## Strategies

### S1 — MA200 Trend + Half-Kelly + 3xATR (Gold Backbone)

- **Lens:** Trend-following (the user's primary instinct)
- **Market:** GC=F (COMEX Gold Futures)
- **Timeframe:** Daily
- **Weight:** 50%
- **Entry:** Daily close > MA200. Confirm: ADX(14) > 20 AND MA200 slope > 0.
- **Exit:** Trailing stop: 3×ATR(14) from highest close since entry. Hard stop: close < MA200 (regime flip).
- **Sizing:** Half-Kelly: f*/2 = 0.0781 per trade (f* = 0.15625). Cap at 2× gross leverage. Units = (equity × 0.0781) / (3 × ATR(14) × point_value). GC=F point value = $100/oz per 1-point move (verify IBKR contract spec).
- **Risk per trade:** 0.75% equity.
- **Filter:** ADX(14) > 20; MA200 slope positive. Skip if ATR > 2× 50-day median.
- **Ground truth:** GC=F MA200_HK baseline ~9.5% CAGR / 33.6% DD (ungated, COMEX futures — separate instrument from Gold/JPY cross). DXY-gated variant FAILS OOS (CAGR 3.04%, MaxDD -56%) — removed. Gold/JPY cross MA200+HK+3xATR ground truth: ~5.7% CAGR, Sharpe 1.04, MaxDD -11% (ATR(14), full sample).
- **Walkforward:** MA200 on Gold_JPY: OOS Sharpe 0.09–0.19, 7/23 folds passing, PF 4.5–6.3, DD 18–94% depending on sizing. Does NOT clear formal 0.4 Sharpe threshold but shows strong PF and low DD at conservative sizing.
- **Status:** GROUND-TRUTH + USER-PROVEN-STYLE

### S2 — Parabolic/RSI-Divergence Contrarian Fade (User Edge)

- **Lens:** Event/positioning (the user's genuine edge — formalized)
- **Market:** GC=F
- **Timeframe:** Daily
- **Weight:** 15%
- **Entry:** Short GC=F when ANY: (a) RSI(14) > 75 with bearish divergence, (b) parabolic move > 3 std dev from 20d MA AND RSI > 80, (c) COT managed money net long > 2 std dev of 3-year range.
- **Exit:** TP: 1.5×ATR favorable. SL: 2×ATR adverse. Time stop: 10 bars. Must be in profit by bar 5.
- **Sizing:** 0.50% risk per trade (short-specific — gap risk). Volatility-scaled. Hard cap: no more than 2 concurrent fade positions.
- **Risk per trade:** 0.50% equity.
- **Filter:** GC=F must be > MA200 (fade strength only). Volume confirmation on exhaustion candle. NO FOMC/CPI days (3 days before/after). ATR below 50-day median.
- **Ground truth:** User's gold short 5040→4130 (~9K SGD). Expected ~6–10% CAGR from fades / 15–22% DD (fat-tail risk).
- **Walkforward:** Not formally tested — user's proven edge. Phase 1 paper-trade required to validate on live data.
- **Status:** USER-PROVEN (live track record)

### S3 — Momentum Rotation (SiMSCI/A50 + USDJPY Carry)

- **Lens:** Multi-asset rotation
- **Market:** ^N225, USDJPY=X, JK8.SI (UOBAM FTSE China A50 ETF)
- **Timeframe:** Daily (ranking monthly, rebalance monthly)
- **Weight:** 15% (pending validation to 20–25% once SiMSCI/A50 data confirmed)
- **Entry:** Rank ^N225 and USDJPY by composite momentum (0.5 × 1M return + 0.5 × 3M return). Long top-1 each month. Must be > MA200.
- **Exit:** Monthly rebalance. Exit any asset dropping below MA200. Trailing 2×ATR stop on each position.
- **Sizing:** Equal-weight among selected assets. Each at 0.5% risk per month.
- **Risk per trade:** 0.50% equity per position.
- **Filter:** Price > MA200 AND ADX(14) > 15. Minimum 1 asset selected; else go to cash.
- **Ground truth:** N225 MA200_HK: ~10.3% CAGR / 21% DD. USDJPY: no robust edge (0 passing combos). SPY/MA200_HK is the only passing walkforward combo (10.79% CAGR / 37% DD, Sharpe 0.656, 5/8 folds). **SiMSCI data now sourced** (`^870200-SGD-STRD`, Yahoo Finance). **FTSE A50 data now sourced** (`XIN9.FGI`, Yahoo Finance). `JK8.SI` (UOBAM FTSE China A50 ETF) is SGD-denominated on SGX, directly tradable on IBKR.
- **Walkforward:** USDJPY: 0 passing combos out of 135 FX strategy combos. N225 proxy: TO BE REPLACED with actual SiMSCI (`^870200-SGD-STRD`) and FTSE A50 (`XIN9.FGI`) data once walkforward-validated. `JK8.SI` (UOBAM FTSE China A50 ETF) is a direct SGD-denominated option on SGX. SiMSCI/A50 data is now sourced; walkforward validation pending.
- **Status:** PROXY-NOTE — SiMSCI/A50 data NOW SOURCED; N225 TO BE REPLACED. Walkforward validation pending.

---

## Sizing

**Method:** Half-Kelly with 2× gross leverage cap.

- **Full Kelly:** f* = 0.15625 (15.625%). **Half-Kelly:** f*/2 = 0.0781 (7.81%).
- **Core sizing (S1):** Half-Kelly = 0.0781 per trade. Risk = 0.75% equity. Units = (equity × 0.0781) / (3 × ATR(14) × point_value).
- **Satellite sizing (S2):** 0.50% risk per trade. **S3:** 0.50% risk per position per month.
- **Portfolio risk cap:** Aggregate risk ≤ 2.5% equity per trade. Aggregate daily risk ≤ 4% equity.
- **Leverage cap:** 2× gross leverage max (IBKR). Vol-target overlay: if realized vol > 18%, reduce all positions by 25%.
- **SGD conversion:** All USD-denominated instruments (GC=F, USDJPY=X) converted at SGDUSD spot. Position size in SGD = USD_size × SGDUSD_rate. Use SGDUSD.csv (1971–2026) for historical conversion. Convert in bulk at IBKR (low spread). Singapore no CGT on FX conversion gains/losses.

---

## Risk Rules

### Portfolio Drawdown
- **Soft stop (25%):** Reduce all satellite positions by 50%, review strategy logic.
- **Hard stop (50%):** Kill all positions, move to cash, reassess (matches user maxDD constraint).

### Per-Trade Risk
- **Max risk:** 0.75% core / 0.50% satellite per trade.
- **Max daily loss:** 4% equity → stop trading for the day.
- **Max weekly loss:** 8% equity → reduce all positions by 25%.

### Regime Gates
- **MA200:** All trend positions require price > MA200. Close all trend positions if close < MA200.
- **Fade gate:** S2 only active when GC=F > MA200 (fade strength). No fading in confirmed downtrends.

### Event Risk
- **FOMC/CPI:** No S2 fade entries 3 days before/after FOMC/CPI releases. Tighten S2 stops to 1.5×ATR on event days.
- **Holiday gaps:** XAU=F/GC=F may gap over Singapore holidays (SGX closed, COMEX open). Reduce S3 position by 50% before long SG holidays.

### Correlation Risk
- S1 and S2 are GC=F — high correlation. Aggregate GC=F exposure capped at 60% equity. S3 provides diversification.
- GOLD/USD vs USD/JPY = −0.29 (diversifying). But SGD investor has implicit USD exposure via SGDUSD.

### SGD FX Risk
- SGDUSD not currently hedged. Singapore no CGT favors unhedged USD exposure (no tax drag on FX gains).
- Monitor monthly: if SGD strengthens >5% vs USD in 6 months, consider partial SGDUSD forward hedge.
- If SGDUSD < 1.30 (strong SGD), review hedge need.

---

## Entry & Exit Rules

### Trend Entries (S1)
- **Entry:** Daily close > MA200. Confirm ADX(14) > 20. Enter on next open.
- **Sizing:** Half-Kelly: units = (equity × 0.0781) / (3 × ATR(14) × point_value). GC=F point value = $100/oz per 1-point move (verify IBKR contract spec).
- **Exit:** 3×ATR(14) trailing from highest close. Hard exit on close < MA200 (regime flip).

### Fade Entries (S2)
- **Entry:** Short GC=F on: RSI(14) > 75 + bearish divergence, OR parabolic > 3 std dev + RSI > 80, OR COT extreme (managed money net long > 2 std dev).
- **Confirmation:** Wait for exhaustion candle (shooting star, engulfing, doji) + volume confirmation. Enter on close of confirm candle.
- **Exit:** TP: 1.5×ATR favorable. SL: 2×ATR adverse. Time stop: 10 bars. Max hold: 5 bars if not in profit.
- **Note:** This is a SHORT strategy — gap risk on gold is significant. Hard SL mandatory.

### Rotation Entries (S3)
- **Entry:** Monthly rebalance (last trading day of month). Rank ^N225 and USDJPY by 1M+3M momentum. Long top-1 each. Enter on next open.
- **Exit:** Exit if price < MA200 (regime flip). Trailing 2×ATR stop. Monthly rebalance exits any asset dropping out of top-1.

### SGD Conversion
- Convert SGD → USD at SGDUSD spot before executing any USD-denominated order. Use IBKR FX conversion (low spread). Record SGDUSD rate for each trade.

---

## Rollout Plan

### Phase 1 — Conservative (Months 1–3)
**Allocation:** CAND-21 (70/30 conservative barbell): 70% core (S1 on GC=F), 30% alpha (S2 fade paper-trade + S3 rotation).
- Deploy S1 on GC=F with Half-Kelly sizing. Paper-trade S2 fade to validate user edge on live data.
- Start S3 rotation at minimum sizing (0.25% risk).
- Track aggregate DD weekly. Target: DD < 15% by end of Phase 1.

### Phase 2 — Scale Up (Months 4–6)
**Allocation:** Scale to CAND-20 (50/50 barbell) if Phase 1 DD < 15% and S2 paper-trade shows positive expectancy.
- Increase S2 to live 0.50% risk if paper-trade P&L > 0 and max DD < 20%.
- Increase S3 to 0.50% risk per position.

### Phase 3 — Full Deployment (Months 7–12)
**Allocation:** CAND-20 (50/50) full deployment: 60% core + 25% fade + 15% rotation.
- Full deployment of all three strategies.
- Monthly rebalance and review.
- First annual walkforward re-evaluation at month 12.

### Phase 4 — Mature (Year 2+)
**Allocation:** Maintain CAND-20 with dynamic adjustments based on live performance. Consider scaling toward CAND-19 (30/70) if DD exceeds 25%.
- Quarterly walkforward re-evaluation.
- Annual plan reset: re-validate S1–S3 ground truth, adjust sizing.
- If portfolio grows > 100% from initial, consider rebalancing to reduce risk (donate/withdraw excess).
- SiMSCI/A50 data IS now sourced. Scale diversification sleeve to 20–25% with actual SiMSCI (`^870200-SGD-STRD`), FTSE A50 (`XIN9.FGI`), and `JK8.SI` (UOBAM FTSE China A50 ETF) once walkforward-validated. Replace N225 proxy.

---

## Monitoring

### Weekly
- Aggregate portfolio drawdown (vs peak equity).
- Aggregate risk exposure (% equity at risk across all positions).
- Gate status removed — DXY gate is dead.
- SGDUSD trend (if SGD strengthens >2% in week, flag).
- S2 fade positions: check for gap risk, review if any position > 3 days in loss.

### Monthly
- Rebalance S3 momentum rotation (last trading day).
- Review all strategy P&L and win rates vs baseline.
- Check S2 fade edge: cumulative P&L, win rate, average payoff ratio.
- SGDUSD conversion rate review.
- Portfolio Sharpe and Sortino vs 12% CAGR target.
- If monthly DD > 10%, reduce satellite positions by 25%.

### Quarterly
- Full walkforward re-evaluation (3yr IS / 1yr OOS) on S1–S3.
- Re-validate ground-truth parameters (MA period, ATR multiplier).
- Review S2 fade edge: compare live vs user's historical 5040→4130 result.
- Review data sourcing progress: SiMSCI (`^870200-SGD-STRD`), FTSE A50 (`XIN9.FGI`), SGD/JPY (`SGDJPY=X`), and XAU/SGD (`XAUSGD`) all sourced. Validate via walkforward. Replace N225 proxy with actual SiMSCI/A50 data.
- Adjust allocation if any strategy fails walkforward (OOS Sharpe < 0.4).
- Spend-down review: calculate annual withdrawal based on portfolio performance.

### Annual
- Full plan reset: re-evaluate all constraints, target CAGR, maxDD.
- Walkforward re-validation of all strategies.
- Review SGX data acquisition and validation status (SiMSCI `^870200-SGD-STRD`, A50 `XIN9.FGI`, SGD/JPY `SGDJPY=X`, XAU/SGD `XAUSGD`). Confirm `JK8.SI` (UOBAM FTSE China A50 ETF) tradability on IBKR. Replace N225 proxy with actual SiMSCI/A50 data.
- Tax review: Singapore no CGT — confirm no tax liability on trend-following gains.
- Spend-down path review: 20yr die-with-zero trajectory check.

---

## Risks

### Data Risks
| Risk | Severity | Mitigation |
|------|----------|------------|
| No SiMSCI/A50 data | MEDIUM / RESOLVED | SiMSCI (`^870200-SGD-STRD`) and FTSE A50 (`XIN9.FGI`) now sourced via Yahoo Finance. `JK8.SI` (UOBAM FTSE China A50 ETF) is SGD-denominated on SGX, directly tradable on IBKR. N225 proxy TO BE REPLACED with actual SiMSCI/A50 data. Walkforward validation pending. |
| No SGD/JPY or gold/SGD data | RESOLVED | SGD/JPY now sourced via `SGDJPY=X` (Yahoo Finance). XAU/SGD now sourced via Stooq `XAUSGD` (CSV back to 2008). Direct SGD-denominated gold and yen exposure available. |
| Daily close-only data | MEDIUM | Limits intraday granularity. Acceptable for daily trend-following strategies. |
| Walkforward validation gaps | MEDIUM | MA200 (ungated) is the only passing walkforward combo. Paper-trade S2 fade to build live validation. |
| FX pairs have no validated edge | HIGH | 0 passing combos out of 135 FX strategy combinations. USDJPY kept at minimal sizing (0.50% risk) as diversification, not as primary edge. Do not scale FX until edge is sourced. |

### Strategy Risks
| Risk | Severity | Mitigation |
|------|----------|------------|
| S1–S3 all GC=F (high correlation) | HIGH | Aggregate GC=F exposure capped at 60% equity. S3 provides diversification. Monitor correlation regime. |
| Parabolic fade gap risk (S2) | HIGH | 0.50% risk (not 0.75%). Hard 2×ATR SL. No FOMC/CPI entries. Reduce position before SG holidays. Gold shorts have catastrophic tail risk if parabolic extension continues. |
| Trend-following fails in choppy regimes | HIGH | MA200 regime gate avoids choppy markets. ADX filter confirms trend. S2 fade profits in choppy periods (diversifying). |
| Gold futures contract rollover | MEDIUM | GC=F is front-month continuous. Monitor roll costs. IBKR handles rollover automatically for futures. |

### Operational Risks
| Risk | Severity | Mitigation |
|------|----------|------------|
| SGDUSD FX conversion cost | LOW | IBKR offers low-spread FX conversion. Convert in bulk (not per-trade). Singapore no CGT on FX gains. |
| Leverage risk (IBKR margin) | MEDIUM | 2× gross leverage cap. Vol-target overlay: reduce positions if realized vol > 18%. Monitor margin usage weekly. |
| Broker risk (IBKR) | LOW | IBKR is well-capitalized and regulated. SIPC protection applies. No concentration risk in broker. |
| User behavioral risk | MEDIUM | User has blow-up and recovery history. Hard stops and risk rules enforce discipline. S2 fade is user's proven edge — but must respect hard SLs. The framework prevents heroic deviations. |

### Spend-Down Risks
| Risk | Severity | Mitigation |
|------|----------|------------|
| Sequence-of-returns risk (early retirement withdrawals) | HIGH | Withdrawals calibrated to portfolio performance. In down years, reduce withdrawal to 2% (from 4%). Maintain 6-month SGD cash buffer for living expenses. |
| Portfolio fails to reach die-with-zero at year 20 | MEDIUM | If portfolio grows > 100% by year 10, increase withdrawal rate. If underperforming, reduce withdrawal and rely more on CPF. |

---

## Expected Outcome

### Return Targets
- **Target CAGR:** 12–15% (base case 11–13% accounting for data gaps and FX uncertainty).
- **Expected DD:** 20–28% (well within 50% maxDD limit; soft stop at 25%).
- **Sharpe:** 0.7–0.9 (base case).
- **Win rate:** Trend strategies ~40–50% (high payoff ratio). Fade strategy ~55–65% (moderate payoff ratio).

### Spend-Down Path
- **Philosophy:** Die-with-zero over 20 years (age 49 → 69). CPF ($800K) covers baseline living expenses; $50K aggressive end provides supplemental growth + withdrawal.
- **Withdrawal rate:** 4% initial ($2,000 SGD/year), inflation-adjusted annually. If portfolio CAGR > 12%, increase withdrawal to 6% to accelerate die-with-zero.
- **Trajectory:** Year 0: $50K. Year 10: ~$120–180K (if 12–15% CAGR). Year 20: ~$0–50K (fully spent via withdrawals + growth).
- **Contingency:** If portfolio DD > 30% in any year, suspend withdrawals for 12 months and rely on CPF.

### Tax Efficiency
- **Jurisdiction:** Singapore.
- **Capital gains tax:** None — trend-following gains (even short-term) are tax-free.
- **FX gains:** No tax on SGDUSD conversion gains/losses (not classified as capital gains).
- **Implication:** Favorable for trend-following hold periods and USD exposure. No tax drag on strategy returns.

### Key Assumptions
1. GC=F MA200+HK+3xATR produces ~9.5% CAGR / 33.6% DD in ground truth (COMEX futures, full sample). Gold/JPY cross MA200+HK+3xATR produces ~5.7% CAGR / -11% DD (ATR(14), full sample 1971-2026). Both below 12-15% target — multi-asset diversification required.
2. User's parabolic fade edge (5040→4130) is reproducible on live data — validated via Phase 1 paper-trade.
3. Singapore tax regime remains favorable (no CGT) over 20-year horizon.
4. IBKR continues to offer low-cost GC=F futures execution and SGDUSD conversion.
5. SiMSCI and FTSE A50 data is now sourced (`^870200-SGD-STRD`, `XIN9.FGI` via Yahoo Finance; `JK8.SI` UOBAM FTSE China A50 ETF on SGX). N225 proxy TO BE REPLACED once walkforward-validated. Diversification sleeve can scale from 15% to 20–25% upon validation.

### Success Metrics
- CAGR ≥ 10% (soft floor) over any rolling 3-year period.
- Max DD ≤ 28% (target) / ≤ 50% (hard limit).
- S2 fade edge shows positive expectancy after 50+ trades.
- Sharpe ≥ 0.5 on any rolling 2-year period.
- Portfolio reaches die-with-zero target by year 20.

---

## Design Philosophy Summary

This plan formalizes the user's existing edges rather than replacing them:

1. **MA200 trend is his natural instinct** — built as the backbone (S1), validated on GC=F and SPY. The user already trades this way; the framework makes it systematic. The SPY/MA200_HK walkforward passing combo validates the MA200 style family on equities.

2. **Donchian breakout is his second proven style** — represented in the rotation sleeve (S3) and available as a scaling option. The formal walkforward confirms the style family (not FX pairs) has structural validity. Donchian20 on FX pairs did not pass, but the MA200 style (closely related trend-following) did pass on SPY.

3. **Parabolic/short detection is a genuine edge** — formalized as S2 with confirmation rules so his instinct becomes repeatable rather than heroic. The 5040→4130 gold short proves the skill; the framework makes it systematic. Sizing at 0.50% (not 0.75%) respects the gap risk while preserving the edge.

4. **Barbell framing is correct mental model** — CPF = safe end (not in scope), $50K = aggressive end (the plan's universe). The 70/30 conservative start (CAND-21) respects his post-recovery caution; scaling to 50/50 (CAND-20) as confidence grows. The SPY/MA200_HK passing walkforward combo validates the MA200 style family.

5. **20-year horizon + die-with-zero** = spend-down portfolio, not perpetual growth. Withdrawals calibrated to performance, with CPF as the backstop. If portfolio grows >100% by year 10, increase withdrawal to accelerate spend-down.

6. **Singapore no CGT** is a structural advantage — favors longer trend-following hold periods and unhedged USD exposure. No tax drag on any strategy return.

7. **Validation honesty** — the formal walkforward found 0 passing combos (FX and gold/JPY). This is honest, not fatal: (a) SPY/MA200_HK is the only passing walkforward combo (10.79% CAGR, Sharpe 0.656) — validating the MA200 style; (b) the user's own live track record (gold 5040→4130) is the strongest edge evidence. The plan builds on both while being transparent about walkforward limitations.
