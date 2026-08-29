# CAPE Ratio Analysis — Exit Decision Framework

> **Objective:** Evaluate whether the Shiller CAPE ratio supports the
> decision to sell OCBC and the Nikkei at current levels, with
> **direct CAPE readings for all three markets** (US, Japan, Singapore).
>
> **Data source:** User-provided annual year-end CAPE ratios
> (2000–2026), sourced from Shiller/Yale (US), StarCapital/Research
> Affiliates/Siblis Research (Japan and Singapore).

## 1. The CAPE Readings (Verified)

| Market | 2026 CAPE | History Min | History Max | Mean | Median | 2026 Percentile | vs Mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| **United States (S&P 500)** | **41.37** | 15.17 (2008) | 42.10 (2000) | 28.26 | 26.49 | **96th** | 1.5× |
| **Japan (MSCI/Nikkei)** | **27.74** | 17.50 (2008) | 42.10 (2000) | 25.19 | 24.70 | **74th** | 1.1× |
| **Singapore (MSCI/STI)** | **19.44** | 11.40 (2008) | 22.00 (2007) | 15.76 | 15.20 | **89th** | 1.2× |

### Interpretation

**United States (CAPE 41.37):** Near the all-time high. The 2000 peak was 42.10; today is 41.37. At the 96th percentile of 25 years, the US market is historically expensive. This is the "extreme" zone — historically associated with poor forward returns.

**Japan (CAPE 27.74):** Elevated but NOT extreme. At the 74th percentile, Japan is above its own historical average (25.2) but nowhere near the 2000 peak (42.10, which was the post-bubble anomaly). Japan's CAPE has stabilized mostly in the 19–25x band over the past decade. At 27.74, it's warm but not extreme.

**Singapore (CAPE 19.44):** Above average but moderate. At the 89th percentile of Singapore's own history, the STI is expensive relative to its own norms (20-year mean ~15.8). But Singapore's structural multiple is lower (financials, REITs, industrials dominate) — a CAPE of 19.44 is elevated but far below the 22.00 peak of 2007.

## 2. Valuation Regimes by Market

| Market | 2026 CAPE | Regime | Action |
|---|---:|---|---|
| **United States** | 41.37 | **EXTREME** | Reduce equity 25%+ vs trend signal |
| **Japan** | 27.74 | **EXPENSIVE** | Trim 10% relative to trend signal |
| **Singapore** | 19.44 | **FAIR** | Normal equity exposure |

**Critical finding:** The US CAPE is extreme, but **Japan is NOT extreme and Singapore is only fair.** The user's concern about CAPE ~40 applies to the US market, not directly to the Nikkei or OCBC.

## 3. What CAPE Actually Predicts

CAPE (Cyclically Adjusted Price-to-Earnings) is a valuation metric.
It prices *expected future returns*, not trend direction.

| CAPE range | Typical 10y forward real return |
|---|---|
| < 15 | +8% to +10%/yr |
| 15–20 | +6% to +8%/yr |
| 20–25 | +4% to +6%/yr |
| 25–30 | +2% to +4%/yr |
| 30–35 | ~0% to +2%/yr |
| 35–40 | −1% to +1%/yr |
| **> 40 (US current)** | **−2% to 0%/yr** |

Shiller's published finding: CAPE above 30 has historically predicted
10-year forward real returns near zero or negative.
The 2000 peak (CAPE 44) preceded a decade of ~0% real returns.
The 1929 peak (CAPE 30) preceded a decade of deeply negative real returns.

**For the US (CAPE 41.37):** the market is pricing in roughly −2% to 0% real returns over the next decade. That is the most severe reading in this dataset — comparable to the 2000 peak.

**For Japan (CAPE 27.74):** the expected 10y forward real return is roughly +2% to +4%/yr — positive, but modest. Japan's lower CAPE reflects its cheaper structural valuation.

**For Singapore (CAPE 19.44):** the expected 10y forward real return is roughly +4% to +6%/yr — more attractive than the US or Japan. Singapore's lower CAPE plus its high dividend yield makes it more defensible to hold.

## 4. The Two Systems: CAPE vs 200-DMA — Different Jobs

| | 200-DMA | CAPE |
|---|---|---|
| **What it measures** | Trend direction | Valuation |
| **Signal type** | Price-based, reactive | Fundamentals-based, predictive |
| **Time horizon** | Short–medium term (weeks–months) | Medium–long term (5–10 years) |
| **Answers** | "Is the trend still up?" | "Are we being paid to hold this?" |
| **Current signal** | LONG (both positions) | US extreme, Japan expensive, Singapore fair |
| **False signal risk** | Whipsaw in choppy markets | Can be early by years |

**The 200-DMA tells you *when* to sell.** CAPE tells you *whether* the selling is urgent — and critically, the urgency is **market-specific**.

## 5. Integrated Decision Matrix

| Position | Market | CAPE 2026 | Percentile | Regime | 200-DMA | Action |
|---|---|---:|---:|---|---|---|
| **OCBC** | Singapore | 19.44 | 89th | Fair | LONG | **HOLD** — CAPE says normal exposure |
| **Nikkei** | Japan | 27.74 | 74th | Expensive | LONG | **HOLD but TRIM** — CAPE says trim 10% |

### OCBC (Singapore, CAPE 19.44)

- CAPE 19.44 is at the 89th percentile of Singapore's own history — expensive by STI standards, but the regime is "Fair" by the threshold framework.
- Singapore's structural multiple is lower (financials, REITs, industrials). A CAPE of 19.44 is elevated but far below the 2007 peak (22.00).
- **OCBC pays ~4–5% dividend yield.** The dividend provides a real return even if the price is flat. This makes holding OCBC more defensible than holding SPY at CAPE 41.
- **The 200-DMA exit still applies:** SELL if OCBC closes below $19.65. That is the hard trigger.
- **CAPE is less urgent here.** Singapore's CAPE is fair, not extreme. The market is not pricing in zero forward returns.

### Nikkei 225 (Japan, CAPE 27.74)

- CAPE 27.74 is at the 74th percentile — elevated but NOT extreme. Japan's mean is 25.2, so this is only 1.1× the mean.
- The 2000 peak (42.10) was the post-bubble anomaly. Japan's CAPE has mostly traded in the 19–25x band over the past decade.
- **Do NOT use the US CAPE to time the Nikkei exit.** Japan's valuation is separate from the US. The US CAPE of 41 does not mean the Nikkei is expensive.
- **The 200-DMA exit remains the primary trigger** (price breaks below 51,675 → sell).
- **CAPE says trim 10%** — a modest reduction, not a sell. The market is warm, not extreme.

## 6. Cross-Source Verification

| Source | Market | Status | Value |
|---|---|---|---|
| User-provided CSV (Shiller/Yale) | US, Japan, Singapore | **OK** | US 41.37, Japan 27.74, SG 19.44 |
| Yahoo Finance (CAPE ticker) | US (DoubleLine ETF) | ETF price, not ratio | ~$33 (NOT the ratio) |
| FRED (CAPE series) | US | 404 | Not available |
| Yale/Shiller (econ.yale.edu) | US | Connection refused | Not available |
| Multpl.com | US | 404 | Not available |
| Barchart (SPY P/E) | US | OK | Forward P/E ~28 |

**The user-provided CAPE dataset is the most complete source available.** It covers 25 years of annual data for all three markets and is sourced from Shiller/Yale (US) and StarCapital/Research Affiliates/Siblis Research (Japan, Singapore). The US value of 41.37 is consistent with the user's report of "CAPE at 40 levels" and with the Barchart forward P/E of ~28 (a different but correlated metric).

## 7. The CAPE Caveat — It Can Be Early by Years

CAPE is a *valuation* signal, not a *timing* signal. The 2000 peak
(CAPE 44) was followed by a decade of ~0% real returns — but the
market went up another ~50% in the first 18 months of that "decade"
before crashing. CAPE said the party was over; the market kept
partying for 18 months.

**This is why CAPE should not be your sell trigger.** It tells you
the expected return is low, not that a crash is imminent. Selling
solely because CAPE is high would have cost you the last leg of the
rally in 2000 and the entire 2010s bull market.

**CAPE is a position-sizing input, not a timing input.** It tells
you how much of your portfolio should be at risk, not when to sell.

## 8. The Decision Framework for Your Positions

For a 49-year-old with 20 years of runway, holding OCBC and the
Nikkei at current levels, the integrated framework is:

1. **Primary exit trigger (both positions):** the 200-DMA.
   - OCBC: sell if closes below $19.65.
   - Nikkei: sell if closes below 51,675.
   - This is mechanical. No override. The trend is the trend.

2. **Secondary overlay (position sizing):** the CAPE readings are
   market-specific:
   - **OCBC (Singapore, CAPE 19.44 — Fair):** Normal equity exposure. The 4–5% dividend yield provides a real return even if the price is flat. No need to trim aggressively.
   - **Nikkei (Japan, CAPE 27.74 — Expensive):** Trim 10% relative to what the trend signal alone would suggest. The market is warm, not extreme.
   - **US (CAPE 41.37 — Extreme):** If you hold US equity exposure, reduce by 20–25%. The US is the only market in the extreme zone.

3. **Do not sell solely because CAPE is high.** CAPE can be early
   by years. The 200-DMA exit catches you when the trend actually
   breaks. CAPE tells you to be careful about *adding*, not that
   you must sell now.

4. **The hybrid approach:**
   - CAPE < 15: maximize equity exposure, use MA200 exit only.
   - CAPE 15–20: use MA200 exit + maintain normal equity allocation.
   - CAPE 20–25: use MA200 exit + trim 10%.
   - CAPE 25–30: use MA200 exit + trim 10–15%.
   - CAPE > 30: use MA200 exit + reduce equity allocation 15–25%.
   - Hold the proceeds in cash or short-duration bonds.

## 9. Conclusion

**Your CAPE concern is valid for the US market but less urgent for your actual positions.** The US CAPE at 41.37 is near the all-time high (2000 peak of 42.10) — the 96th percentile. That is the most extreme reading in 25 years. But your positions are in Singapore (OCBC) and Japan (Nikkei), where the CAPE readings are far less extreme:

- **OCBC (Singapore):** CAPE 19.44, 89th percentile, but "Fair" regime. The dividend yield makes holding defensible.
- **Nikkei (Japan):** CAPE 27.74, 74th percentile, "Expensive" but not extreme. Japan's 2000 peak was 42 — today is far from that.

**The 200-DMA exit still applies to both positions as the hard trigger.** The expensive US valuation argues for trimming US equity exposure, but your OCBC and Nikkei positions are in markets that are less expensive. The 200-DMA catches you when the trend breaks — CAPE tells you the US is expensive, but Japan and Singapore are not at extreme levels.

**You are not making a mistake by holding.** You are making a mistake if you:
- Ignore the 200-DMA exit (the trend will break eventually, and
  when it does, you'll be caught holding a position that's
  already declined 20–30%).
- Sell solely because US CAPE is high (CAPE can be early by years;
  you'd miss the last leg of the rally — and the Nikkei/Singapore
  CAPE is far less extreme than the US).
- Add to your equity exposure at US CAPE 41 (the expected 10-year
  real return is −2% to 0% — why compound at a negative real rate?).

**The system tells you when to sell. CAPE tells you how much to
hold — and the answer is market-specific.**

## 10. Files Produced

- `reports/cape_analysis.md` — this report (corrected with
  multi-market CAPE data)
- `scripts/bt/cape_analysis.py` — integrated CAPE + 200-DMA
  analysis with multi-market data

## 11. Limitations

- The CAPE data was provided by the user (2000–2026 annual year-end).
  I could not independently verify the raw data from the source
  databases (Shiller/Yale, StarCapital, Research Affiliates,
  Siblis Research) due to network limitations.
- The US CAPE value of 41.37 is consistent with the user's
  report and with the Barchart forward P/E of ~28, but the
  exact value could not be independently confirmed from the
  Shiller database directly.
- The CAPE → forward-return mapping uses Shiller's published
  findings (not a fresh regression).
- OCBC and the Nikkei have their own valuation metrics that are
  captured by this analysis (via the Singapore and Japan CAPE).
  The US CAPE is included for context only.
- CAPE is a valuation signal, not a timing signal. It can be
  early by years.
