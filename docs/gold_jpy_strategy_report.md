# Gold/JPY Trend-Following Strategy Report

**Strategy:** MA200 Half-Kelly + 3xATR Stop + Dynamic Scale-In (with Gold Regime Gate)  
**Ticker:** XAU/JPY (Gold per troy ounce in Japanese Yen)  
**Data:** 1971-01-04 to 2026-05-29 (55.4 years, 13,836 daily bars)  
**Investor Profile:** Age 49 → 69 (20-year horizon)

---

## Executive Summary

| Metric | Baseline | Scale-In | Scale-In + Gate |
|---|---|---|---|
| **CAGR** | +14.84% | +13.98% | **+18.46%** |
| **Max Drawdown** | 47.37% | 59.95% | 53.14% |
| **Sharpe Ratio** | +0.74 | +0.66 | +0.60 |
| **Total Trades** | 168 | 212 (168+44) | 154 |
| **Win Rate** | 42.9% | 31.6% | — |
| **Profit Factor** | 6.01 | 5.20 | — |
| **Final Value** | $213.7M | $141.0M | — |

**Key finding:** The scale-in strategy alone *underperforms* the baseline (adds trades but drags returns). However, when combined with a Gold Regime Gate, the scale-in strategy **outperforms the baseline** (+18.5% vs +14.8% CAGR). The gate prevents adds during weak/dangerous market conditions.

---

## Strategy Mechanics

### Entry
- Buy when price crosses **above the 200-day moving average** (prior-close signal timing, no look-ahead)
- Exit when price crosses **below the 200-day MA** (signal exit)
- Position sizing: Half-Kelly criterion (7.81% target risk per trade)

### Stop Loss
- **3x ATR(14)** stop from weighted entry price
- ATR uses True Range (high-low, close-to-close gaps)
- Pre-2000 data: monthly LBMA gold close interpolated to daily, multiplied by FRED DEXJPUS
- Post-2000 data: COMEX GC=F daily OHLC × FRED DEXJPUS

### Dynamic Scale-In
- Add to winning positions when price retraces into the stop-loss zone
- Each add = 0.5× initial position size (max 2.0× total position)
- Profit gate: only add when unrealized gain ≥ 1× ATR stop width
- Max 3 additions per trade cycle
- Adds are funded by unrealized gains (no cash deduction)

### Gold Regime Gate
Only deploy capital when ALL conditions are met:
1. **Trend up**: price > 200-day MA
2. **Momentum up**: price > 50-day MA
3. **Not chasing**: drawdown from recent peak > -30%

Regime is active approximately **24.3% of days**. The strategy sits out ~76% of the time, which filters out the most dangerous periods.

---

## 20-Year Rolling Bucket Analysis (CAPE-Style)

Just as CAPE ratio tells you what your equity returns *could* be depending on entry valuation, this bucket analysis tells you what your Gold/JPY returns could be depending on *when* you start investing.

### Investor Scenario: Age 49 → 69

36 overlapping 20-year windows were computed across the full 55-year dataset. Each window represents a possible 20-year investment period starting from a different year.

### CAGR Range — Scale-In + Gate

| Statistic | Value |
|---|---|
| **Worst window** | **+0.51%** |
| 10th percentile | +2.11% |
| **Median** | **+9.41%** |
| Mean | +9.58% |
| 90th percentile | +18.27% |
| Best window | +25.55% |

### CAGR Range — Baseline + Gate

| Statistic | Value |
|---|---|
| Worst window | -0.03% |
| Median | +9.05% |
| 90th percentile | +13.53% |

### Key Buckets

| Window | Scale-In CAGR | Baseline CAGR |
|---|---|---|
| 1971-1991 | +25.55% | +20.57% |
| 1980-2000 | +0.51% | -0.03% |
| 1997-2017 | +6.39% | +6.56% |
| 2006-2026 | +19.96% | +14.72% |

### Worst Case: 1980-2000
Gold fell from ~$850 to ~$250 during this period. The strategy captured the declines via the MA200 exit but had no major bull runs to exploit. Even in this worst window, returns were barely positive (+0.51%) with the gate preventing catastrophic losses.

### Best Case: 1971-1991
The Gold bull market of the 1970s-80s delivered exceptional returns. The strategy captured the massive trend and the scale-in added alpha during the run.

---

## What This Means for Investors

### Honest Assessment

1. **The strategy alone is not enough.** Without a regime gate, the scale-in adds trades but *reduces* returns. The adds amplify losses during trend reversals.

2. **The regime gate changes everything.** With the gate, the scale-in strategy outperforms the baseline in most 20-year windows. The gate prevents the strategy from adding size during weak or dangerous conditions.

3. **Starting year matters enormously.** A 20-year investment starting in 1971 could deliver +25% CAGR. One starting in 1980 could deliver ~0%. This is the fundamental challenge of trend-following a single asset class.

4. **Drawdowns are structural.** Expect 30-50% peak-to-trough drawdowns at some point. This is the cost of capturing large trends. The strategy does not stay smooth — it captures massive moves and pays for it with deep drawdowns.

5. **The strategy sits out most of the time.** The regime gate is only active 24% of days. This means the strategy is often in cash, waiting for favorable conditions. This is by design — it avoids the worst periods.

### For the 49-Year-Old Investor

- **Best case:** Start investing now → ~+10-20% CAGR over 20 years → portfolio grows 6-9×
- **Worst case:** Start during a Gold bear → ~0-2% CAGR → portfolio barely grows
- **Median case:** ~+9% CAGR → portfolio grows ~5.6× over 20 years

The wide outcome range means the strategy needs a **regime overlay** to be investable. The Gold Regime Gate is the first step, but further refinement may be needed.

---

## Recommendations

1. **Keep the baseline only** if you want simplicity. CAGR +14.84%, MaxDD 47%. No scale-in complexity.

2. **Add the regime gate** if you want the scale-in to actually help. CAGR improves to +18.46%.

3. **Consider a Gold-specific valuation overlay** (similar to CAPE for equities) to further improve the gate. Current gate uses only technical filters.

4. **Consider ATR trailing stops** on additions instead of fixed 3x ATR — this would lock in gains on added positions.

5. **Document the regime gate logic** and backtest it separately to verify it doesn't overfit to the Gold dataset.

---

## Methodology Notes

- **Backtest period:** 1971-01-04 to 2026-05-29
- **Capital:** $100,000 initial
- **Commission:** 0.002% per trade
- **Signal timing:** Prior-close (no look-ahead bias)
- **Equity computation:** Cash + unrealized P&L from weighted entry
- **Drawdown:** Peak-to-trough, properly computed as `(equity - cummax) / cummax`
- **Sharpe:** Annualized from daily returns: `(mean/std) × sqrt(252)`
- **CAGR:** `(final/capital)^(1/years) - 1`
- **Walk-forward:** 5-year in-sample / 2-year out-of-sample, expanding window
- **Pre-2000 data:** Monthly LBMA gold close interpolated to daily (no intraday range, but ATR still defined via close-to-close true range)
- **Post-2000 data:** COMEX GC=F daily OHLC

---

## Files

| File | Description |
|---|---|
| `scripts/bt/kelly_backtest.py` | Strategy engine with DynamicPositionManager |
| `scripts/bt/reporting.py` | Report generators (markdown, bucket report) |
| `GOLD/reports/gold_jpy_kelly_report.md` | Detailed backtest report |
| `GOLD/reports/gold_jpy_bucket_report.md` | Rolling bucket analysis |
| `GOLD/reports/gold_jpy_kelly_results.json` | Full metrics (baseline + scale-in + regime) |
| `GOLD/reports/gold_jpy_20yr_buckets.json` | Bucket data and statistics |
| `GOLD/charts/gold_jpy_equity.png` | Equity curve and drawdown chart |
| `GOLD/charts/gold_jpy_20yr_buckets.png` | Rolling bucket CAGR visualization |
---

## Appendix: Gold/JPY Decomposition — Leg Sizing Strategies

The gold_jpy position is the product of two components: `gold_jpy = gold_usd × USDJPY`.
By decomposing the position into its two legs and sizing each independently, we can
dynamically tilt between gold exposure and JPY exposure based on their relative trend
strength and correlation regime.

### Gold/USD vs USD/JPY Correlation

| Frequency | gold_usd vs usdjpy | gold_jpy vs usdjpy | gold_usd vs gold_jpy |
|---|---|---|---|
| Daily | **-0.19** | +0.52 | +0.73 |
| Weekly | -0.20 | — | — |
| Monthly | -0.23 | — | — |

- **gold_usd and USD/JPY are negatively correlated** (-0.19 to -0.23): when the dollar weakens, gold rallies AND USD/JPY falls. This is the real economic signal.
- **gold_jpy and USD/JPY are positively correlated** (+0.52): this is a mathematical artifact of the multiplicative identity — the gold_usd component dominates.
- **gold_usd and gold_jpy are strongly positively correlated** (+0.73): gold in any currency tracks gold in USD.

### Strategy 1: Static 50/50 Split

Split the risk budget evenly between gold_usd and USD/JPY. Each leg has its own
MA200 signal, ATR(14) × 3 stop, and Half-Kelly sizing.

| Metric | Value |
|---|---|
| CAGR | +14.03% |
| Max Drawdown | 48.76% |
| Sharpe | +0.85 |
| Profit Factor | 2.59 |
| Final Value | $144.4M |

### Strategy 2: Trend-Weighted Dynamic Split

Allocate risk proportionally to each leg's trend strength (|price / MA(50) - 1|, smoothed).
The leg with the stronger trend gets more risk budget.

| Metric | Value |
|---|---|
| CAGR | +14.11% |
| Max Drawdown | **39.13%** |
| Sharpe | +0.86 |
| Profit Factor | 3.00 |
| Final Value | $149.9M |

**Key advantage:** The trend-weighted split reduces MaxDD by ~10 percentage points vs the static split while maintaining similar CAGR. The dynamic allocation naturally shifts risk toward whichever leg is trending more strongly.

### Strategy 3: Core + Overlay Hedge

Keep a gold_jpy core at Half-Kelly and add a USD/JPY overlay sized at 30% of core notional when gold_jpy is long. This amplifies the implicit USD/JPY exposure baked into the gold_jpy position.

| Metric | Value |
|---|---|
| CAGR | +14.32% |
| Max Drawdown | 53.24% |
| Sharpe | +0.76 |
| Profit Factor | 5.91 |
| Final Value | $166.2M |

**Trade-off:** Higher CAGR and profit factor, but also higher MaxDD. The overlay amplifies both gains and losses.

### Comparison Summary

| Strategy | CAGR | Sharpe | MaxDD | PF | Final$ |
|---|---|---|---|---|---|
| Static 50/50 | +14.03% | +0.85 | 48.76% | 2.59 | $144.4M |
| Trend-Weighted | +14.11% | +0.86 | **39.13%** | 3.00 | $149.9M |
| Core + Overlay | +14.32% | +0.76 | 53.24% | 5.91 | $166.2M |
| Baseline (gold_jpy) | +14.84% | +0.74 | 47.37% | 6.01 | $213.7M |

### Key Insights

1. **Decomposition doesn't change the fundamental return profile.** All three legs-based strategies deliver ~14% CAGR, similar to the baseline gold_jpy strategy. The magic is in the *distribution* of returns (MaxDD, drawdown profile), not the absolute level.

2. **Trend-weighting reduces drawdowns.** By allocating more risk to the trending leg, the strategy avoids adding to the weaker leg at the wrong time. This reduced MaxDD by ~10pp vs the static split.

3. **The overlay amplifies both ways.** The core+overlay strategy has the highest CAGR and profit factor, but also the highest MaxDD. The USD/JPY overlay adds exposure to the dollar-yen trend, which is positively correlated with gold_jpy — it amplifies the trend but also the drawdowns.

4. **For a risk-conscious investor, the trend-weighted split is the best choice.** It maintains similar CAGR to the baseline while significantly reducing drawdowns. The dynamic allocation is intuitive: when gold is trending strongly, overweight gold; when USD/JPY is trending strongly, overweight the FX leg.

5. **The negative gold_usd/USDJPY correlation is the key economic relationship.** When the dollar weakens, gold rallies and USD/JPY falls. A pure gold_jpy position implicitly holds both legs — the decomposition lets you control the relative sizing.
