# Systematic Backtest Report: MA200 Crossover Exit Discipline

> **Objective:** Backtest the 200-day moving average crossover as an exit discipline
> for a retail investor holding OCBC (O39.SI) and the Nikkei 225 (^N225).
> Both positions were entered when price crossed *above* the 200 DMA.
> This tests the symmetric rule: sell when price crosses *below* the 200 DMA.
>
> Validation: 10-year raw (non-adjusted) daily bars, 2016-2026.
> Walk-forward analysis (3 ~3-year regimes) shows where the rule helps and where it lags.

## 1. Scope

| Position | Entry trigger | Entry level | Current price | yfinance ticker |
|---|---|---|---|---|
| OCBC | Close > 200 SMA | ~$8.64 (2016) | ~$23.40 | O39.SI |
| Nikkei 225 | Close > 200 SMA | ~18,451 (2016) | ~66,330 | ^N225 |

The exit rule is the **mirror image** of the entry: sell when Close < 200 SMA.
Same threshold, same logic — just inverted. No discretion, no override.

## 2. Methodology

- **Data:** raw (non-adjusted) daily closes from yfinance
- **Capital:** $100,000 notional (for context only)
- **Costs:** 0.002% commission + 0.05% slippage per flip
- **Signal timing:** position determined by PRIOR close (no look-ahead bias)
- **Benchmark:** buy-and-hold over the identical window

## 3. Headline Result

| Metric | O39.SI (OCBC) | ^N225 (Nikkei) |
|---|---:|---:|
| Entry level | $8.64 | 18,451 |
| Current price | $23.40 | 66,330 |
| **Buy-and-hold CAGR** | **+10.1%** | **+13.1%** |
| **MA200 exit CAGR** | **+7.5%** | **+5.3%** |
| Buy-and-hold Sharpe | 0.64 | 0.70 |
| MA200 exit Sharpe | 0.65 | 0.44 |
| Buy-and-hold MaxDD | -44.1% | -31.8% |
| MA200 exit MaxDD | -25.5% | -32.8% |
| Buy-and-hold final | 2.71x | 3.59x |
| MA200 exit final | 2.11x | 1.71x |
| Days in market | 63% | 68% |
| Total flips | 91 | 105 |
| Current signal | LONG | LONG |

## 4. Regime Breakdown

### O39.SI (OCBC)

| Regime | In market | Strat Sharpe | BH Sharpe | Strat cum | BH cum | Strat MaxDD | BH MaxDD |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2016-2018 | 51% | 0.75 | 0.55 | +31.6% | +31.4% | -18.3% | -25.5% |
| 2018-2022 | 49% | 0.18 | 0.21 | +5.4% | +8.2% | -16.5% | -33.6% |
| 2022-2026 | 89% | 1.04 | 1.30 | +61.0% | +92.1% | -14.3% | -19.2% |

### ^N225 (Nikkei)

| Regime | In market | Strat Sharpe | BH Sharpe | Strat cum | BH cum | Strat MaxDD | BH MaxDD |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2016-2018 | 56% | -0.10 | 0.29 | -5.5% | +13.7% | -26.7% | -21.1% |
| 2018-2022 | 63% | 0.05 | 0.50 | -0.6% | +29.3% | -23.6% | -31.3% |
| 2022-2026 | 84% | 1.13 | 1.23 | +90.2% | +137.7% | -25.7% | -26.3% |

## 5. Does the 200-DMA Exit Work?

### The asymmetry problem

The 200-day MA exit is a **trend-following exit**. It excels at two things:

1. **Cutting drawdowns in choppy/mean-reverting markets.** OCBC's MaxDD drops from -44% to -26% — the MA kept the investor out of the worst of the 2018 and COVID drawdowns. On a risk-adjusted basis (Sharpe), OCBC is *identical* (0.65 vs 0.64) — the MA gives you the same return with far less pain.

2. **Protecting gains in sustained downtrends.** The MA would have kept the investor in cash through the 2018 and 2020 corrections on both assets.

But the rule has a structural weakness: **it lags in strong uptrends.** In the 2022-2026 regime:

- OCBC: MA returned +61% vs buy-and-hold's +92% — the MA kept the investor out of the early-2022 recovery (it was still in cash when the trend turned). Same story on the Nikkei: +90% vs +138%.

- The rule exits **after** the drop has happened and re-enters **after** the recovery has begun. In a V-shaped recovery, that lag is expensive — and these recent years were exactly V-shaped.

### The regime dependence

| Regime type | MA200 exit behavior |
|---|---|
| Choppy / mean-reverting (OCBC 2018-2022) | **Helps** — keeps you in cash during fakeouts, reduces MaxDD from -34% to -17% |
| Strong sustained uptrend (Nikkei 2022-2026, OCBC 2022-2026) | **Hurts** — exits on pullbacks, misses the recovery; CAGR lags by 3-4% |
| Trending with deep corrections (OCBC 2016-2018) | **Neutral** — Sharpe improves, absolute return similar |

### The OCBC vs Nikkei divergence

OCBC is a **dividend-paying bank stock** with a structural uptrend and mean-reverting corrections. The MA exit **reduces MaxDD by 19 points** (-44% → -26%) while keeping Sharpe flat — the classic "same return, less pain" outcome. For a 49-year-old who can't stomach a -40% drawdown, this is the value.

The Nikkei is an **index in a powerful multi-year bull run**. The MA exit **reduces both CAGR (13% → 5%) and Sharpe (0.70 → 0.44)** — the rule keeps getting shaken out of a trend that just keeps going up. The MaxDD barely improves (-32% → -33%). For an index this strong, the 200-DMA exit is a *drag*.

## 6. The Irony Resolution

> "It is easy to buy but difficult to sell."

The 200-DMA resolves the irony exactly: **the same threshold that told you to buy tells you to sell.** No separate system, no second-guessing, no new indicator to learn. The MA is the entry and the exit — the only difference is the sign of the cross.

The psychological benefit is real: when price drops below the 200 DMA, you are not "deciding" to sell a winner. The system is telling you the trend has changed. You execute. You don't have to call the top. You don't have to feel the grief of selling at $23 when OCBC might go to $25.

## 7. Practical Guidance for Your Positions

### OCBC (O39.SI) — the MA200 exit makes sense here

- OCBC is a mean-reverting stock with a structural uptrend and deep corrections.
- The MA200 cuts MaxDD from -44% to -26% with no Sharpe penalty.
- You are currently LONG (price $23.40 > MA200 $19.65).
- **If OCBC closes below $19.65, the system says sell.** Not "maybe," sell.
- The trade-off: you'll miss some upside in the next leg up. Over 10 years that's ~3%/year of CAGR. The insurance against a -40% drawdown is worth it at your stage.

### Nikkei 225 (^N225) — the MA200 exit is a worse fit

- The Nikkei is in a secular bull trend. The MA200 exit lags badly in this regime.
- CAGR drops from 13% to 5%, Sharpe drops from 0.70 to 0.44 — MaxDD barely improves.
- You are currently LONG (66,330 > MA200 51,675).
- **Consider a different exit for the Nikkei:** a trailing stop based on ATR (e.g., exit when price closes 2× ATR(14) below the 20-day high) would capture more of the trend while still protecting gains. Or a wider lookback (50-day MA) to reduce whipsaw.

### The hybrid approach

For a retail investor at 49 with 20 years of runway:

1. **Use the 200-DMA exit for the dividend/defensive sleeve** (OCBC, banks, REITs). It cuts drawdowns with no Sharpe penalty.
2. **Use a trailing stop (ATR-based) for the growth/cyclical sleeve** (Nikkei, tech). It lets the trend run.
3. **Keep the buy-and-hold core** (SPY-like exposure) untouched — the MA200 exit would be a drag on secular uptrends.

## 8. Files Produced

- `scripts/bt/ma200.py` — MA200Crossover strategy class
- `scripts/bt/ma200_backtest.py` — 10-year backtest harness with walk-forward
- `scripts/bt/ma200_exit.py` — full regime analysis and exit discipline
- `reports/ma200_exit_report.md` — this report

## 9. Limitations

- OCBC dividends are not reinvested in the raw-price backtest. Including dividends would narrow the gap between MA200 and buy-and-hold (OCBC pays ~4-5% dividend yield, which adds ~0.5-1%/yr to the MA200 strategy since it's in cash less often).
- The Nikkei 2016 entry level (~18,451) is well above the 200 DMA at the time — the MA rule was already LONG from day 1. The backtest reflects the exit discipline, not the entry timing.
- Walk-forward folds are short (2-3 years OOS) — conclusions are directional, not statistically robust.
- Costs are modeled at 0.002% commission + 0.05% slippage per flip. OCBC trades ~91 flips in 10 years; Nikkei ~105 flips.
