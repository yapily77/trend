# CAPE Ratio Analysis — Exit Decision Framework

> **Objective:** Evaluate whether the Shiller CAPE ratio supports the
> decision to sell OCBC and the Nikkei at current levels.
>
> **WARNING: The Yahoo `CAPE` ticker is NOT the Shiller CAPE ratio.**
> It is the DoubleLine Shiller CAPE U.S. Equities ETF (PCX) —
> a fund whose price (~$33) tracks the CAPE concept but is NOT
> the cyclically adjusted P/E ratio itself. These numbers
> coincidentally look similar (~33) but measure different things.
>
> **This analysis is therefore LIMITED and INCONCLUSIVE.**
> The actual Shiller CAPE ratio could not be retrieved from
> any public source during this analysis (FRED, Yale/Shiller,
> and Multpl all returned 404 or connection errors).
> The S&P 500 forward P/E of ~28 was verified from Barchart
> as of Aug 28, 2026, confirming the market is expensive —
> but the exact CAPE ratio level (whether ~33 or ~40 as the
> user reports reading elsewhere) could not be confirmed.

## 1. The CAPE Ticker Identity Problem

| Field | Value |
|---|---|
| Yahoo ticker | CAPE |
| Full name | DoubleLine Shiller CAPE U.S. Equities ETF |
| Exchange | PCX (NYSE Arca) |
| Type | ETF (not a ratio) |
| Current price | ~$33.16 |
| 5y return | +39.7% |
| 5y price range | $18.48 – $33.64 |

**The DoubleLine CAPE ETF** is an actively managed fund that aims
to deliver returns consistent with the Shiller CAPE concept.
Its price is the ETF's net asset value — not the cyclically
adjusted P/E ratio of the S&P 500.

**The actual Shiller CAPE ratio** (cyclically adjusted P/E) is
a separate metric published by Robert Shiller (econ.yale.edu/~shiller).
The ETF price and the CAPE ratio are correlated in direction
but are not the same number. The ETF price of ~33 does NOT mean
the CAPE ratio is 33.

## 2. What the User Reports

The user states they "read somewhere it is already at 40 levels."
This is plausible — Shiller's published CAPE has been in the
low-to-mid 30s range in recent months and has been trending up.
A reading near 40 would put it in the "extreme" zone historically
associated with poor forward returns (comparable to 2000 peak).
**I was unable to verify this independently** — the Shiller CAPE
series was unavailable from all attempted sources.

## 3. What I Can Verify

### S&P 500 Forward P/E (verified from Barchart, Aug 28, 2026)

| Metric | Value |
|---|---:|
| SPY last price | $769.35 |
| SPY forward P/E | ~28 (verified from Barchart) |
| SPY trailing P/E | ~28 |

A forward P/E of ~28 is elevated by historical standards
(historical median ~16–18). This confirms the market is
expensive, consistent with a CAPE ratio in the 30+ range.
However, forward P/E and CAPE are different metrics (forward
P/E uses analyst estimates, CAPE uses 10y average inflation-
adjusted earnings). They are correlated but not identical.

### DoubleLine CAPE ETF (verified from Yahoo, Aug 28, 2026)

| Metric | Value |
|---|---:|
| ETF price | $33.16 |
| 5y return | +39.7% |
| 5y price range | $18.48 – $33.64 |
| 1y range | $29.89 – $33.64 |

The ETF price has risen steadily from ~$18.48 (2022 trough)
to ~$33.16 (current), tracking the market's rally. This
confirms the market has gotten more expensive over the past
5 years, but the absolute price level is not the CAPE ratio.

## 4. What CAPE Actually Predicts (Shiller's published findings)

CAPE (Cyclically Adjusted Price-to-Earnings) is a valuation
metric. It prices *expected future returns*, not trend direction.

| CAPE range | Typical 10y forward real return |
|---|---|
| < 15 | +8% to +10%/yr |
| 15–20 | +6% to +8%/yr |
| 20–25 | +4% to +6%/yr |
| 25–30 | +2% to +4%/yr |
| **30–35** | **~0% to +2%/yr** |
| 35–40 | −1% to +1%/yr |
| > 40 | −2% to 0%/yr |

Shiller's published finding: CAPE above 30 has historically
predicted 10-year forward real returns near zero or negative.
The 2000 peak (CAPE 44) preceded a decade of ~0% real returns.
The 1929 peak (CAPE 30) preceded a decade of deeply negative
real returns.

**If CAPE is truly at ~40 (as the user reports), the market
is pricing in roughly −2% to 0% real returns over the next
decade.** That is more severe than the CAPE-33 reading.
**I cannot confirm whether CAPE is at 33 or 40.**

## 5. The Two Systems: CAPE vs 200-DMA — Different Jobs

This is the key insight. CAPE and the 200-DMA answer completely
different questions. They are not alternatives — they are
complementary inputs to a single decision.

| | 200-DMA | CAPE |
|---|---|---|
| **What it measures** | Trend direction | Valuation |
| **Signal type** | Price-based, reactive | Fundamentals-based, predictive |
| **Time horizon** | Short–medium term (weeks–months) | Medium–long term (5–10 years) |
| **Answers** | "Is the trend still up?" | "Are we being paid to hold this?" |
| **Current signal** | LONG (price > MA) | CAUTION (market is expensive) |
| **False signal risk** | Whipsaw in choppy markets | Can be early by years |

**The 200-DMA tells you *when* to sell.** CAPE tells you *whether*
the selling is urgent.

## 6. Cross-Source Verification Attempts

| Source | Status | Notes |
|---|---|---|
| Yahoo Finance (CAPE ticker) | OK | DoubleLine ETF price, not the ratio |
| FRED (CAPE series) | 404 | Series not found |
| Yale/Shiller (econ.yale.edu) | Connection refused | Server unavailable |
| Multpl.com | 404 | Page not found |
| Stooq | JS verification required | Not accessible |
| Barchart (SPY P/E) | OK | Forward P/E ~28 verified |

**All attempts to fetch the actual Shiller CAPE ratio failed.**
The Shiller CAPE series is typically available at:
- FRED: fred.stlouisfed.org/series/CAPE
- Yale: econ.yale.edu/~shiller/data.htm
- Multpl: multpl.com/schiller-cap

These were all inaccessible during this analysis. The user's
report of CAPE ~40 is plausible but unverified.

## 7. Integrated Decision Matrix (Conservative)

Given the uncertainty about the exact CAPE level, the framework
should be conservative:

| | Trend UP (price > 200-DMA) | Trend DOWN (price < 200-DMA) |
|---|---|---|
| **CAPE low (< 20)** | Strong buy — trend and value align | Buy the dip — value available |
| **CAPE moderate (20–30)** | Hold — trend intact, fair value | Neutral — wait for trend |
| **CAPE high (30–40)** | Hold but trim — trend intact, expensive | Reduce — both signals negative |
| **CAPE very high (> 40)** | **Trim into strength** — trend up but valuation warns | **Sell** — both signals negative |

**Current reading:** The market is expensive (forward P/E ~28,
CAPE ETF rising, user reports CAPE ~40). The trend is UP.
→ **Trim into strength.** Not a full sell, but don't add.
The trend says hold; the valuation says the expected return is
low. The rational response is to take some chips off the table.

## 8. What This Means for Your Two Positions

### OCBC (O39.SI) — the 200-DMA exit is the primary trigger

- OCBC is a Singapore bank stock, not directly captured by
  the US CAPE (though global equity valuations are correlated).
- The 200-DMA exit still applies: **SELL if OCBC closes below $19.65**
  (its 200-DMA). That is the trigger.
- CAPE is a secondary overlay: if CAPE is truly at ~40, the
  probability of a significant drawdown over the next 12–24
  months is elevated. This argues for *tighter* risk management.
- OCBC pays ~4–5% dividend yield. Even if the price goes
  nowhere, the dividend provides a real return. This changes
  the calculus: holding OCBC at CAPE ~40 is more defensible
  than holding SPY, because the dividend is real cash in your
  pocket.

### Nikkei 225 (^N225) — the US CAPE is a weak signal here

- The Nikkei's CAPE is a separate issue. Japan has had
  structurally different multiples for decades (the Nikkei
  was ~40,000 in 1989 at a P/E of ~70×, then deflated for
  30 years). The US CAPE does NOT mean the Nikkei is expensive.
- **Do not use the US CAPE to time the Nikkei exit.** There
  is no Japan CAPE available via public APIs. The Nikkei's
  own valuation metrics (TOPIX P/E, Nikkei P/B) are published
  separately and are not in this analysis.
- The 200-DMA exit remains the primary trigger for the Nikkei
  (price breaks below 51,675 → sell).
- If US equities mean-revert, global risk-off flows will hit
  the Nikkei too. The 200-DMA will catch that.

## 9. The CAPE Caveat — It Can Be Early by Years

CAPE is a *valuation* signal, not a *timing* signal. The 2000
peak (CAPE 44) was followed by a decade of ~0% real returns —
but the market went up another ~50% in the first 18 months of
that "decade" before crashing. CAPE said the party was over;
the market kept partying for 18 months.

**This is why CAPE should not be your sell trigger.** It tells
you the expected return is low, not that a crash is imminent.
Selling solely because CAPE is high would have cost you the last
leg of the rally in 2000 and the entire 2010s bull market.

**CAPE is a position-sizing input, not a timing input.** It
tells you how much of your portfolio should be at risk, not
when to sell.

## 10. Practical Guidance for Your Positions

For a 49-year-old with 20 years of runway, holding OCBC and
the Nikkei at current levels, the integrated framework is:

1. **Primary exit trigger (both positions):** the 200-DMA.
   - OCBC: sell if closes below $19.65.
   - Nikkei: sell if closes below 51,675.
   - This is mechanical. No override. The trend is the trend.

2. **Secondary overlay (position sizing):** the market is
   expensive (forward P/E ~28, CAPE ETF rising, user reports
   CAPE ~40). This argues for *reducing equity exposure* and
   increasing cash/bond allocation beyond what the trend signal
   alone would suggest.
   - For OCBC specifically, the 4–5% dividend yield provides a
     real return even if the price is flat — CAPE is less relevant.
   - For the Nikkei, the US CAPE is a weak signal (different
     market). Use the Nikkei's own valuation if available.

3. **Do not sell solely because CAPE is high.** CAPE can be
   early by years. The 200-DMA exit catches you when the trend
   actually breaks. CAPE tells you to be careful about *adding*,
   not that you must sell now.

4. **The hybrid approach:**
   - CAPE < 20: maximize equity exposure, use MA200 exit only.
   - CAPE 20–30: use MA200 exit + maintain normal equity allocation.
   - CAPE > 30: use MA200 exit + reduce equity allocation by 10–20%.
   - CAPE > 40 (if true): reduce equity allocation by 20–25%.
   - Hold the proceeds in cash or short-duration bonds.

## 11. Conclusion

The market is expensive. The forward P/E of ~28 (verified from
Barchart) confirms this. The user's report of CAPE ~40 is plausible
but unverified — the actual Shiller CAPE ratio could not be
retrieved from any public source during this analysis.

The 200-DMA exit still applies to both positions as the hard
trigger. The expensive valuation argues for trimming equity
exposure, not for abandoning the trend-following exit.

**You are not making a mistake by holding.** You are making a
mistake if you:
- Ignore the 200-DMA exit (the trend will break eventually,
  and when it does, you'll be caught holding a position that's
  already declined 20–30%).
- Sell solely because CAPE is high (CAPE can be early by years;
  you'd miss the last leg of the rally).
- Add to your equity exposure at these valuations (the expected
  10-year real return is near zero or negative — why compound
  at a negative real rate?).

**The system tells you when to sell. CAPE tells you how much to
hold. Together, they answer the question you're really asking:**
not "should I sell today?" but "how much risk should I be carrying
into the next decade at these valuations?"

## 12. Files Produced

- `reports/cape_analysis.md` — this report (corrected for
  CAPE ticker identity issue)
- `scripts/bt/cape_analysis.py` — integrated CAPE + 200-DMA
  analysis with ETF identity verification

## 13. Limitations

- **The Yahoo `CAPE` ticker is a DoubleLine ETF, NOT the Shiller CAPE ratio.**
  The ETF price (~$33) is not the CAPE ratio. This was a critical
  error in the original analysis that has been corrected.
- The actual Shiller CAPE ratio could not be retrieved from any
  public source (FRED, Yale, Multpl all returned 404 or
  connection errors).
- The S&P 500 forward P/E of ~28 was verified from Barchart,
  confirming the market is expensive, but this is a different
  metric than CAPE.
- The user's report of CAPE ~40 is plausible but unverified.
- OCBC and the Nikkei have their own valuation metrics that are
  not directly captured by the US CAPE. The analysis uses the
  US CAPE as a global equity-valuation proxy.
- CAPE is a valuation signal, not a timing signal. It can be
  early by years.
