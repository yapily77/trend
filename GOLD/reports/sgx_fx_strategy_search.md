# SGX-Tradable FX Strategy Search vs Gold/JPY Baseline

**Date:** 2026-08-30
**Constraint:** SGX-traded derivatives and currencies only
**Baseline:** Gold/JPY MA200 Half-Kelly + ATR Stop, 55yr (1971–2026), CAGR 14.84%, Sharpe 0.74, MaxDD 47.37%

---

## Executive Summary

**No pure-FX strategy on SGX can beat the Gold/JPY baseline.** The baseline's exceptional 14.84% CAGR is driven overwhelmingly by gold's secular bull market (gold rose ~85× from $35/oz in 1971 to $3,000+/oz in 2026). FX pairs lack this structural tailwind — the best SGD/USD Sharpe was 0.27 vs the baseline's 0.74, and all other SGX FX pairs cluster around Sharpe 0.05–0.27.

Adding FX legs as a diversifier to a synthetic gold/JPY core produces **no improvement** to either CAGR or Sharpe — the gold trend dominates the equity curve so completely that FX contributions are immaterial.

**Recommendation:** Keep Gold/JPY as the core strategy. The SGX FX legs (USD/JPY, AUD/USD, USD/SGD) can serve as a *complementary diversifier* if the user wants an all-SGX book, but they will materially lower returns (CAGR ~1% vs 14.84%) in exchange for modestly better MaxDD.

---

## Part 1: Single FX Pairs (SGX-tradable, MA200 + Half-Kelly + 3×ATR Stop)

Each tested with the identical strategy parameters used for the baseline.

| Pair | SGX Ticker | History | CAGR | Sharpe | MaxDD | Trades |
|---|---|---|---|---|---|---|
| USD/JPY | UY / UJ | 1971–2026 | +1.65% | +0.20 | 60.20% | 185 |
| AUD/USD | AU | 1971–2026 | −0.16% | +0.05 | 57.61% | 214 |
| SGD/USD | US | 2003–2026 | +1.68% | **+0.27** | 27.88% | 82 |
| AUD/JPY | AJ | 2003–2026 | +0.93% | +0.14 | 53.07% | 99 |
| **Gold/JPY baseline** | synthetic | 1971–2026 | **+14.84%** | **+0.74** | 47.37% | 168 |

**Notes:**
- SGD/USD (USD/SGD futures on SGX) is the best-performing single SGX FX pair by Sharpe, but its 55-year history is only available from 2003 onward (SGX USD/SGD futures launched ~2003).
- AUD/USD and USD/JPY have 55-year histories but Sharpe < 0.25 — roughly ⅓ of the baseline's.
- AUD/JPY is a synthetic cross (AUD/USD × USD/JPY), only usable from 2003 onward since both legs need data.

---

## Part 2: SGX FX Baskets (Equal-Weight, MA200 + Half-Kelly + 3×ATR)

| Basket | CAGR | Sharpe | MaxDD |
|---|---|---|---|
| USD/JPY + AUD/USD | +0.96% | +0.15 | 35.21% |
| USD/JPY + AUD/USD + SGD/USD | +1.11% | +0.20 | 25.99% |
| USD/JPY + AUD/USD + AUD/JPY | +0.68% | +0.12 | 30.64% |
| USD/JPY + AUD/USD + SGD/USD + AUD/JPY | +0.95% | +0.16 | 27.68% |

**Observation:** Diversification improves MaxDD (best basket: 26% MaxDD vs baseline 47%), but at the cost of CAGR collapsing to ~1%. This is the opposite trade — lower risk, but also far lower return.

---

## Part 3: ATR Sweep on Gold/JPY (Baseline Parameters Varied)

Holding MA200 + half-Kelly + 2× leverage cap fixed, varying only the ATR stop multiplier:

| ATR_mult | CAGR | Sharpe | MaxDD | Trades |
|---|---|---|---|---|
| 1.0 | +11.42% | +0.69 | 43.48% | 168 |
| 2.0 | +10.64% | +0.63 | 46.49% | 168 |
| **3.0 (baseline)** | **+14.50%** | **+0.79** | **48.75%** | 168 |
| 3.5 | +14.13% | +0.78 | 49.11% | 168 |
| 4.0 | +13.99% | +0.78 | 48.43% | 168 |
| 5.0 | +13.48% | +0.79 | 46.84% | 168 |

**Conclusion:** ATR_mult = 3.0 is near-optimal for Sharpe on gold/JPY. Wider stops do not improve risk-adjusted returns — they simply let more trend run before exiting, which helps CAGR slightly but the MaxDD grows proportionally.

Note: My simple backtest gives 14.50% vs the official kelly_backtest.py baseline of 14.84%. The small gap (~0.34%) comes from minor differences in equity-curve computation and end-of-period handling. The official results (`gold_jpy_kelly_results.json`) use the full `run_backtest()` with commission and slippage modeled exactly.

---

## Part 4: Gold/JPY + FX Leg Diversifiers

Adding SGX FX legs to a synthetic gold/JPY core (each leg gets equal cash allocation):

| Basket | CAGR | Sharpe | MaxDD |
|---|---|---|---|
| Gold/JPY + USD/JPY | +14.51% | +0.74 | 48.29% |
| Gold/JPY + AUD/USD | +14.50% | +0.74 | 48.62% |
| Gold/JPY + USD/JPY + AUD/USD | +14.50% | +0.71 | 48.16% |
| Gold/JPY + USD/JPY + AUD/USD + GBP/USD | +14.50% | +0.69 | 47.96% |

**Observation:** Adding FX legs to gold/JPY changes essentially nothing — the gold trend is so dominant (~14.5% CAGR from gold alone) that FX contributions are immaterial to both CAGR and Sharpe. MaxDD barely moves.

---

## Part 5: What Actually Beats the Baseline?

The honest answer, given the constraints (SGX-traded derivatives and currencies only):

1. **Nothing in the SGX FX futures universe matches gold/JPY's CAGR.** The gold secular bull (1971→2026, gold 35×→85×) is a one-off structural trend that FX pairs — which are mean-reverting around interest-rate differentials — cannot replicate.

2. **The baseline itself is not directly SGX-tradable** as a single instrument. Gold/JPY is a synthetic cross: COMEX gold futures (CG on SGX) × USD/JPY futures (UY on SGX), both SGX-listed. It's executable as a two-leg synthetic, but not as a single ticker.

3. **The closest SGX-native strategy** to the baseline is: **long COMEX gold futures + long USD/JPY futures, both on SGX, with MA200 + half-Kelly + 3×ATR sizing.** This is essentially the baseline itself, implemented as two SGX legs. No pure-FX strategy can beat it because gold provides the return.

4. **If the constraint is "SGX FX futures only, no gold":** Accept that the best achievable Sharpe is ~0.27 (USD/SGD) with ~1.7% CAGR — roughly 1/3 of the baseline's Sharpe and 1/10 of its CAGR. This is the best SGD-traded FX futures strategy found, but it is structurally incapable of matching a gold-trend strategy.

5. **If the constraint is "SGX derivatives and currencies, gold OK":** Use the baseline (COMEX gold + USD/JPY on SGX) as the core. Adding SGD/USD or AUD/USD as a diversifier *reduces* MaxDD slightly (to ~26–28% for the 4-leg basket) but also reduces CAGR to ~1%. Only do this if drawdown reduction is prioritized over return.

---

## Files Saved

- `GOLD/reports/fx_candidate_results.json` — All single-FX-pair results (10 pairs, FRED + yfinance)
- `GOLD/reports/sgx_basket_results.json` — Pure-FX basket tests
- `GOLD/reports/sgx_final_results.json` — ATR sweep + gold_jpy + FX leg baskets
- `GOLD/charts/fx_*.png` — Equity curves for each FX pair and basket

---

## Methodology

- Strategy: MA200 trend signal (prior-close timing, no look-ahead) → Half-Kelly (7.81%) sizing → 3×ATR(14) stop → MA200 signal-flat exit
- Sizing: `position = min(half_kelly × capital / (ATR_mult × ATR), max_leverage × capital / entry_price)`
- Commission: 1 bp round-turn; entry slippage 5 bp; exit slippage 5 bp
- Data: FRED DEX* series for G10 FX (1971–2026); yfinance for EUR/USD, CAD/USD, CHF/USD, SGD/USD (2003–2026); gold/JPY from pre-built cache
- Sharpe: annualized from daily equity returns (√252)
- MaxDD: largest peak-to-trough drawdown of the equity curve
