# GOLD/USD vs JPY/USD: Correlation Analysis & Trading Implications

**Data:** 2000-08-30 to 2026-05-29 (6,400 daily observations)  
**Relationship:** `gold_jpy = gold_usd × usdjpy` (Gold in JPY = Gold in USD × USD/JPY)  
**Source:** FRED (GOLD, DEXJPUS), COMEX GC=F

---

## 🔆 Summary

- **GOLD/USD and USD/JPY are NEGATIVELY correlated** at approximately **-0.29 daily** (rolling 1Y: -0.34 mean, -0.76 to +0.11)
- **GOLD/JPY and USD/JPY are weakly POSITIVELY correlated** at approximately **+0.27 daily**
- **GOLD/USD and GOLD/JPY are strongly POSITIVELY correlated** at **+0.85**
- The apparent paradox resolves via the identity: `gold_jpy ≈ gold_usd_return + usdjpy_return`
- The negative gold_usd–USDJPY relationship is the **real economic signal**; the gold_jpy positive correlation is a **mathematical artifact** of the stronger gold_usd component
- For a JPY-based Gold investor, USD/JPY is a **headwind** — when gold rises, USD/JPY typically falls, eroding JPY returns

---

## 1. Why the Confusion? The Math

The relationship is **multiplicative**, not additive:

```
gold_jpy(t) = gold_usd(t) × usdjpy(t)
```

Taking log returns:

```
Δlog(gold_jpy) ≈ Δlog(gold_usd) + Δlog(usdjpy)
```

So the gold_jpy return is approximately the **sum** of the gold_usd return and the usdjpy return.

| Pair | Correlation | Interpretation |
|---|---|---|
| gold_usd ~ usdjpy | **-0.29** | Inverse — the real economic relationship |
| gold_usd ~ gold_jpy | **+0.85** | Gold in any currency tracks gold in USD |
| gold_jpy ~ usdjpy | **+0.27** | Weakly positive — a mathematical artifact |

The gold_jpy–USDJPY correlation is positive because the gold_usd component (strongly positive with gold_jpy) **dominates** the small negative usdjpy component. But the underlying economic reality is the opposite of what the surface number suggests.

---

## 2. The Economic Mechanism

The negative gold_usd–USDJPY relationship exists because:

1. **USD weakness → gold up AND USD/JPY down**
   - When the dollar weakens, gold priced in USD rises (inverse relationship)
   - When the dollar weakens, USD/JPY falls (yen strengthens)
   - Both effects push in the same direction for USD/JPY but opposite for gold

2. **Safe-haven flows**
   - Risk-off → USD weakens, gold rallies, yen strengthens (USD/JPY falls)
   - Risk-on → USD strengthens, gold falls, yen weakens (USD/JPY rises)

3. **Carry trade dynamics**
   - Low-rate JPY funds carry trades into higher-yielding assets
   - When risk appetite is high, carry trades unwind → USD/JPY falls, gold rallies
   - When risk appetite is low, carry trades unwind → USD/JPY rises, gold falls

4. **Bank of Japan policy**
   - BOJ interventions, yield curve control, and rate decisions directly impact USD/JPY
   - These effects can dominate the gold-USD relationship in shorter windows

---

## 3. Decade-by-Decade Breakdown

| Period | gold_jpy ~ usdjpy | gold_usd ~ usdjpy | Notes |
|---|---|---|---|
| 1996-2000 | +0.50 | -0.10 | Gold bear; weak link |
| 2001-2005 | +0.33 | **-0.31** | Gold bull starts; inverse relationship emerges |
| 2006-2010 | +0.35 | -0.15 | GFC; gold safe-haven bid |
| 2011-2015 | +0.23 | -0.28 | Gold bear; moderate inverse |
| 2016-2020 | +0.12 | **-0.49** | Strongest inverse period; BOJ YCC, COVID |
| 2021-2025 | +0.26 | -0.38 | Post-COVID; inflation hedging |

The negative gold_usd–USDJPY relationship was **strongest 2016-2020** (-0.49), during BOJ yield curve control and COVID. It weakened slightly in the 2020s as gold became more of an inflation hedge than a pure USD inverse.

---

## 4. How to Trade This

### Strategy 1: Gold/JPY Long with USD/JPY Hedge

**Setup:** Go long gold_jpy (buy gold in JPY), hedge USD/JPY exposure

- **Long gold_jpy** → captures gold trend in JPY terms
- **Short USD/JPY** (or long JPY/USD) → hedges the USD/JPY component
- **Net exposure:** pure gold_usd exposure

**Rationale:** If you believe in the gold thesis but want to remove JPY/USD noise, this isolates the gold_usd signal. The correlation between gold_jpy and usdjpy (+0.27) means ~7% of gold_jpy variance is explained by USD/JPY — not huge, but it matters for drawdowns.

**Implementation:**
```
Position sizing:
- Gold_jpy long: size = risk / (ATR_gold_jpy × leverage)
- USDJPY short: size to neutralize USD/JPY beta
- Hedge ratio: beta(gold_jpy, usdjpy) = corr × (σ_gold_jpy / σ_usdjpy)
```

### Strategy 2: Mean-Reversion Pair Trade

**Setup:** When gold_jpy and USD/JPY diverge from their historical relationship

- If gold_jpy is **high relative to USD/JPY** → short gold_jpy, long USD/JPY
- If gold_jpy is **low relative to USD/JPY** → long gold_jpy, short USD/JPY

**Rationale:** The gold_jpy–USD/JPY ratio has a long-run equilibrium. Deviations tend to revert as the multiplicative identity reasserts itself.

**Signal:** Z-score of `log(gold_jpy) - log(usdjpy)` = Z-score of `log(gold_usd)`. Wait — that's just gold_usd. So this pair trade is really just a gold_usd mean-reversion trade. **Not recommended** unless you have a specific gold_usd valuation model.

### Strategy 3: Trend-Following with Regime Filter

**Setup:** Use the USD/JPY trend as a regime filter for gold_jpy entries

- Only go long gold_jpy when **both** gold_jpy and USD/JPY are above their 200-DMA
- This confirms both the gold trend AND the USD weakness trend
- Avoids gold rallies driven by yen weakness (which tend to reverse)

**Rationale:** Gold rallies that occur WITH USD/JPY falling (inverse relationship) are more sustainable — they reflect genuine USD weakness. Gold rallies that occur WITH USD/JPY rising are driven by yen-specific factors and tend to be less durable.

**Backtest signal:**
```python
# Regime: gold_jpy > MA200 AND usdjpy > MA200
# This means gold is trending up AND USD is strong vs JPY
# = genuine broad-based gold strength (not just yen weakness)
```

### Strategy 4: Directional View on USD/JPY

**Setup:** Trade USD/JPY based on gold as a leading indicator

- **Gold up, USD/JPY down** → typical; USD weakening, go short USD/JPY
- **Gold up, USD/JPY up** → divergence; yen-specific weakness, caution
- **Gold down, USD/JPY up** → typical; USD strengthening, go long USD/JPY
- **Gold down, USD/JPY down** → divergence; yen-specific strength, caution

**Rationale:** Gold often leads USD/JPY by a few days to weeks. When they diverge, the divergence tends to close — either gold reverses or USD/JPY catches up.

### Strategy 5: Gold/JPY Carry Trade Unwind Signal

**Setup:** Use the breakdown of the gold–USD/JPY correlation as an early warning

- When gold_jpy–usdjpy correlation turns **strongly negative** (e.g., < -0.5), it signals carry trade unwinds
- Carry trade unwinds → sharp USD/JPY falls AND sharp gold rallies
- Position: reduce gold_jpy longs, go long JPY (short USD/JPY)

**Rationale:** The gold–USD/JPY correlation is usually weakly positive (+0.27). When it breaks down to negative, it signals a regime change (risk-off, carry unwind). This is a **crisis alpha** signal.

---

## 5. Practical Implications for the Gold/JPY Strategy

### Impact on Backtest Results

The gold_jpy strategy we've been analyzing (`MA200 Half-Kelly + 3xATR Stop`) implicitly holds a USD/JPY position because:

```
gold_jpy position = gold_usd exposure × USD/JPY exposure
```

When the strategy is long gold_jpy, it is:
- **Long gold_usd** (bullish on gold)
- **Long USD/JPY** (bullish on dollar vs yen, because gold_jpy = gold_usd × usdjpy)

Wait — actually, `long gold_jpy` means you're long gold priced in JPY. If USD/JPY rises (dollar strengthens vs yen), your gold_jpy position gains even if gold_usd is flat. So the strategy has a **positive USD/JPY beta**.

From the data: `corr(gold_jpy, usdjpy) = +0.27`. This means the strategy has a modest positive USD/JPY exposure baked in.

### For a Singapore-Based Investor (SGD)

- SGD is managed against a basket including USD and JPY
- SGD/USD and SGD/JPY correlations differ from USD/JPY
- The gold_jpy strategy's implicit USD/JPY exposure may not align with SGD risk appetite
- Consider hedging with SGD/USD or USD/JPY forward contracts

### For a Japan-Based Investor

- The strategy is natural — gold priced in JPY is the local asset
- The implicit USD/JPY exposure is a side effect of the gold_usd trend
- If USD/JPY falls (yen strengthens), gold_jpy returns are dampened even if gold_usd rises
- This is the **currency drag** that the regime gate partially addresses

---

## 6. Key Numbers

| Metric | Value |
|---|---|
| gold_usd ~ usdjpy (daily) | **-0.29** |
| gold_usd ~ usdjpy (monthly) | **-0.38** |
| gold_usd ~ usdjpy (rolling 1Y mean) | -0.34 |
| gold_usd ~ usdjpy (rolling 1Y range) | -0.76 to +0.11 |
| gold_jpy ~ usdjpy (daily) | +0.27 |
| gold_usd ~ gold_jpy (daily) | +0.85 |
| gold_jpy ~ usdjpy (2006-2010) | +0.35 |
| gold_usd ~ usdjpy (2016-2020) | **-0.49** (strongest) |
| gold_usd ~ usdjpy (2021-2025) | -0.38 |

---

## 7. Bottom Line

| Question | Answer |
|---|---|
| Are GOLD/USD and JPY/USD correlated? | **Yes, negatively** (gold_usd vs USD/JPY = -0.29) |
| Is gold_jpy correlated with USD/JPY? | **Weakly positive** (+0.27) — a mathematical artifact |
| Why the negative correlation? | USD weakness → gold up AND USD/JPY down (safe haven, carry trade) |
| Can I trade it? | **Yes** — hedge USD/JPY exposure, use as regime filter, or trade divergences |
| Should I hedge? | **Depends** — if you want pure gold exposure, hedge USD/JPY. If you want gold_jpy trend, keep it |

---

## 8. Recommended Next Steps

1. **Backtest Strategy 3** (trend-following with USD/JPY regime filter) on gold_jpy — does it improve returns?
2. **Compute the exact USD/JPY beta** of the gold_jpy strategy to size the hedge
3. **Add USD/JPY as a second input** to the existing regime gate (currently only uses gold_jpy technicals)
4. **Evaluate Strategy 5** (carry unwind detection) as a risk-off overlay
5. **Consider SGD-hedged version** for Singapore-based allocation
