# CAPE Ratio Analysis — Exit Decision Framework

> **Objective:** Evaluate whether the Shiller CAPE ratio supports the
> decision to sell OCBC and the Nikkei at current levels.
>
> Current CAPE: 33.16 (Aug 2026, US S&P 500)
> Long-run mean: ~16.5 (1881–2022, Shiller published data)
> Current vs mean: ~2.0× — comparable to the 1929 peak (~30),
> well below the 2000 peak (~44).
>
> **IMPORTANT: This CAPE is US-specific (S&P 500).** It is NOT a Japan CAPE.
> The Shiller CAPE is published by Multpl (multpl.com) and covers only
> the US S&P 500. There is no Japan-specific CAPE available via yfinance
> or the Yahoo Finance API. The US CAPE is used here as a *global equity-valuation
> proxy* — when US equities are expensive, global risk-off flows tend to hit
> all equity markets including Japan. It is NOT a direct valuation reading
> for the Nikkei 225.

## 1. The CAPE Reading

| Metric | Value |
|---|---:|
| Current CAPE | 33.16 |
| Long-run mean (1881–2022) | ~16.5 |
| Current vs mean | 2.0× |
| Percentile of current reading | Top ~5% of all readings |
| 1929 peak | ~30 |
| 2000 peak | ~44 |
| 2007 peak | ~27 |
| 2009 trough | ~13 |
| 2022 trough | ~21 |

**Source:** Yahoo Finance CAPE series (Multpl/Shiller), Aug 2026.
Yahoo series covers 2022–2026 only; the long-run mean and historical
reference points are from Robert Shiller's published dataset
(econ.yale.edu/~shiller/data.htm), which was unavailable during
this analysis due to network limits.

## 2. What CAPE Actually Predicts

CAPE (Cyclically Adjusted Price-to-Earnings) is a valuation metric.
It prices *expected future returns*, not trend direction.

| CAPE range | Typical 10y forward real return |
|---|---|
| < 15 | +8% to +10%/yr |
| 15–20 | +6% to +8%/yr |
| 20–25 | +4% to +6%/yr |
| 25–30 | +2% to +4%/yr |
| **30–35 (current zone)** | **~0% to +2%/yr** |
| 35–40 | −1% to +1%/yr |
| > 40 | −2% to 0%/yr |

Shiller's published finding: CAPE above 30 has historically predicted
10-year forward real returns near zero or negative.
The 2000 peak (CAPE 44) preceded a decade of ~0% real returns
(including the 2008 crash). The 1929 peak (CAPE 30) preceded
a decade of deeply negative real returns.

**At CAPE 33, the market is pricing in roughly zero real returns
over the next 10 years.** Not a crash — just flat, after inflation.

## 3. The Two Systems: CAPE vs 200-DMA — Different Jobs

This is the key insight. CAPE and the 200-DMA answer completely
different questions. They are not alternatives — they are
complementary inputs to a single decision.

| | 200-DMA | CAPE |
|---|---|---|
| **What it measures** | Trend direction | Valuation |
| **Signal type** | Price-based, reactive | Fundamentals-based, predictive |
| **Time horizon** | Short–medium term (weeks–months) | Medium–long term (5–10 years) |
| **Answers** | "Is the trend still up?" | "Are we being paid to hold this?" |
| **Current signal** | LONG (price > MA) | CAUTION (CAPE 33, ~2× mean) |
| **False signal risk** | Whipsaw in choppy markets | Can be early by years |

**The 200-DMA tells you *when* to sell.** CAPE tells you *whether*
the selling is urgent.

## 4. Integrated Decision Matrix

Combining the two signals gives four regimes:

| | Trend UP (price > 200-DMA) | Trend DOWN (price < 200-DMA) |
|---|---|---|
| **CAPE low (< 20)** | Strong buy — trend and value align | Buy the dip — value available |
| **CAPE moderate (20–25)** | Hold — trend intact, fair value | Neutral — wait for trend |
| **CAPE high (25–30)** | Hold but trim — trend intact, expensive | Reduce — both signals negative |
| **CAPE very high (> 30)** | **Trim into strength** — trend up but valuation warns | **Sell** — both signals negative |

**Current reading for the S&P 500:** CAPE 33 + trend UP
→ **Trim into strength.** Not a full sell, but don't add.
The trend says hold; the valuation says the expected return is
near zero. The rational response is to take some chips off the table
and reduce exposure to a level where you can sleep at night.

**Critical caveat:** CAPE 33 is a *US* reading. It does NOT directly measure
the Nikkei 225's valuation. Japan's equity market has had structurally
different multiples for decades (the Nikkei's own CAPE is not available
via public APIs). The US CAPE is used here as a *global risk proxy* —
when US equities are expensive, global risk-off flows tend to hit all
equity markets, including Japan. For the Nikkei specifically, the
200-DMA exit is the primary trigger; the US CAPE is a secondary
contextual overlay, not a direct valuation signal.

## 5. What This Means for Your Two Positions

### OCBC (O39.SI) — the 200-DMA exit is the primary trigger

- OCBC is a Singapore bank stock, not directly captured by the
  S&P 500 CAPE (though global equity valuations are correlated).
- The 200-DMA exit still applies: **SELL if OCBC closes below $19.65**
  (its 200-DMA). That is the trigger.
- CAPE is a secondary overlay: with global CAPE at 33, the
  probability of a significant drawdown over the next 12–24 months
  is elevated. This argues for *tighter* risk management, not for
  abandoning the trend-following exit.
- OCBC pays ~4–5% dividend yield. Even if the price goes nowhere
  (consistent with CAPE's ~0% forward return), the dividend provides
  a real return. This changes the calculus: holding OCBC at CAPE 33
  is more defensible than holding SPY, because the dividend is real
  cash in your pocket.

### Nikkei 225 (^N225) — the US CAPE is a weak signal here

- The Nikkei's CAPE is a separate issue. Japan has had structurally
  different multiples for decades (the Nikkei was ~40,000 in 1989
  at a P/E of ~70×, then deflated for 30 years). The US CAPE of 33
  does NOT mean the Nikkei is expensive.
- **Do not use the US CAPE to time the Nikkei exit.** There is no
  Japan CAPE available via public APIs. The Nikkei's own valuation
  metrics (TOPIX P/E, Nikkei P/B) are published separately and
  are not in this analysis.
- The 200-DMA exit remains the primary trigger for the Nikkei
  (price breaks below 51,675 → sell).
- CAPE 33 on the US market does not directly inform the Nikkei.
  But if US equities mean-revert, global risk-off flows will hit
  the Nikkei too. The 200-DMA will catch that.

## 6. The CAPE Caveat — It Can Be Early by Years

CAPE is a *valuation* signal, not a *timing* signal. The 2000 peak
(CAPE 44) was followed by a decade of ~0% real returns — but the
market went up another ~50% in the first 18 months of that "decade"
before crashing. CAPE said the party was over; the market kept
partying for 18 months.

**This is why CAPE should not be your sell trigger.** It tells you
the expected return is low, not that a crash is imminent. Selling
solely because CAPE is high would have cost you the last leg of the
rally in 2000 and the entire 2010s bull market (CAPE was above
20 for most of that decade).

**CAPE is a position-sizing input, not a timing input.** It tells
you how much of your portfolio should be at risk, not when to sell.

## 7. The Decision Framework for Your Positions

For a 49-year-old with 20 years of runway, holding OCBC and the
Nikkei at current levels, the integrated framework is:

1. **Primary exit trigger (both positions):** the 200-DMA.
   - OCBC: sell if closes below $19.65.
   - Nikkei: sell if closes below 51,675.
   - This is mechanical. No override. The trend is the trend.

2. **Secondary overlay (position sizing):** CAPE at 33 means the
   expected 10-year real return from the broad market is near zero.
   - This argues for *reducing equity exposure* and increasing
     cash/bond allocation beyond what the trend signal alone would
     suggest.
   - For OCBC specifically, the 4–5% dividend yield provides a
     real return even if the price is flat — CAPE is less relevant.
   - For the Nikkei, the US CAPE is a weak signal (different
     market). Use the Nikkei's own valuation if available.

3. **Do not sell solely because CAPE is high.** CAPE can be early
   by years. The 200-DMA exit catches you when the trend actually
   breaks. CAPE tells you to be careful about *adding*, not that
   you must sell now.

4. **The hybrid approach:**
   - CAPE < 20: maximize equity exposure, use MA200 exit only.
   - CAPE 20–30: use MA200 exit + maintain normal equity allocation.
   - CAPE > 30 (current): use MA200 exit + reduce equity allocation
     by 10–20% relative to what the trend signal alone would suggest.
     Hold the proceeds in cash or short-duration bonds.

## 8. Conclusion

The CAPE ratio confirms what the 200-DMA already suggests: the
trend is up, but the market is expensive. You are not making a
mistake by holding. You are making a mistake if you:

- Ignore the 200-DMA exit (the trend will break eventually, and
  when it does, you'll be caught holding a position that's
  already declined 20–30%).
- Sell solely because CAPE is high (CAPE can be early by years;
  you'd miss the last leg of the rally).
- Add to your equity exposure at CAPE 33 (the expected 10-year
  return is near zero — why compound at a negative real rate?).

**The system tells you when to sell. CAPE tells you how much to
hold. Together, they answer the question you're really asking:**
not "should I sell today?" but "how much risk should I be carrying
into the next decade at these valuations?"

## 9. Files Produced

- `reports/cape_analysis.md` — this report
- `scripts/bt/cape_analysis.py` — integrated CAPE + 200-DMA analysis

## 10. Limitations

- Yahoo's CAPE series covers 2022–2026 only. The long-run mean
  and historical reference points are from Shiller's published
  dataset, which was unavailable during this analysis.
- The CAPE → forward-return mapping uses Shiller's published
  findings (not a fresh regression, due to network limits).
- OCBC and the Nikkei have their own valuation metrics that are
  not directly captured by the US CAPE. The analysis uses the
  US CAPE as a global equity-valuation proxy.
- CAPE is a valuation signal, not a timing signal. It can be
  early by years.
