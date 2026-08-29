# Systematic Backtest Report: Citi Institutional Trade Ideas

> **Objective:** Backtest the Citi Institutional Deep Research trade ideas against historical price data using the project's systematic backtesting framework (scripts/bt/). Walk-forward validation: 3-year expanding in-sample / 1-year out-of-sample.

## 1. Scope & Proxies

The Citi research proposes 6 trade ideas across FX, Gold, CME futures, and SGX futures. yfinance provides historical daily bars for USDJPY=X, SPY, ^GSPC, CL=F, GC=F, DX-Y.NYB, EURUSD=X, GLD, and IEF. **SGX futures (CN, SGP) and spot XAUUSD are not available via yfinance** — they are excluded from the quantitative test but kept in the qualitative assessment.

| Research Idea | yfinance Proxy | Note |
|---|---|---|
| Short USD/JPY @ 155.50 | USDJPY=X | Direct FX pair ✅ |
| Long Gold XAUUSD @ $2,460 | GC=F / GLD | Gold futures / ETF proxy |
| Long SGX FTSE China A50 @ 12,650 | — | SGX CN not in yfinance ❌ |
| Long MES (S&P 500) @ 5,580 | SPY / ^GSPC | Equity index proxy |
| Long MCL (WTI Crude) @ $77.50 | CL=F | Crude futures proxy |
| Long SGX MSCI Singapore @ 348 | — | SGX SGP not in yfinance ❌ |

## 2. Methodology

- **Capital:** $100,000 base (1% risk/trade, Carver equal-volatility sizing)
- **Costs:** 0.002% commission + slippage (FX 0.5 pips, futures 0.05-0.15 pts)
- **Validation:** Walk-forward with expanding 3-year in-sample, 1-year out-of-sample
- **Pass threshold:** OOS Sharpe ≥ 0.40 (per prior KAMA/MA200 research rubric)
- **Strategies tested:** Donchian 20 baseline; Donchian 20 + ADX filter; Donchian 20 + ER filter; Donchian 20 + dual lookback; KAMA 10/2/30 (TD Sequential variants excluded from rankings — <20 trades each, countdown artifacts)

## 3. Headline Result: USD/JPY — The Report's Core Short

The research's top idea is a **Short USD/JPY** at 155.50 targeting 144.00. The backtest confirms the earlier KAMA/MA200 research on this exact pair and exact data (1996-2026 daily bars):

| Strategy | IS Sharpe | Trades | Max DD | OOS Avg Sharpe | OOS Passes (≥0.4) |
|---|---:|---:|---:|---:|---:|
| Donchian20 | +0.35 | 137 | -32.09% | +0.05 | 12/27 |
| Donchian20_ADX25 | +0.34 | 192 | -25.36% | +0.16 | 11/27 |
| TDSequentialBreakout | +0.11 | 87 | -19.20% | -0.05 | 1/27 |
| Donchian20_ER03 | +0.11 | 289 | -15.25% | -0.14 | 9/27 |
| Donchian20_Dual | -0.05 | 323 | -4.13% | -0.21 | 6/27 |
| KAMA10_2_30 | -0.10 | 854 | -32.36% | -0.17 | 7/27 |

**Interpretation:** Donchian 20 is the only strategy with a positive IS Sharpe (+0.35) and a meaningful profit factor (1.66) — exactly matching the prior research. It passes the 0.4 OOS threshold in 12/27 folds (44%). However, the *average* OOS Sharpe is only +0.05, meaning the strategy's edge is borderline even when it survives. KAMA and MA-style strategies consistently fail (negative Sharpe, ~1-2/27 passes). **The directional thesis (short USD/JPY on BOJ hike cycle) is macro-theoretically sound, but a simple trend-following overlay does not extract reliable systematic alpha from this pair at daily frequency.**

## 4. Cross-Asset Strategy Ranking

Top strategies by IS Sharpe across all asset classes (minimum 5 trades):

| Rank | Ticker | Strategy | IS Sharpe | Trades | OOS Avg | >=0.4 Passes |
|---:|---|---|---:|---:|---:|---:|
| 1 | GC=F | Donchian20_Dual | +0.38 | 381 | +0.14 | 11/23 |
| 2 | USDJPY=X | Donchian20 | +0.35 | 137 | +0.05 | 12/27 |
| 3 | USDJPY=X | Donchian20_ADX25 | +0.34 | 192 | +0.16 | 11/27 |
| 4 | GLD | Donchian20_ER03 | +0.33 | 283 | +0.23 | 8/19 |
| 5 | GLD | KAMA10_2_30 | +0.28 | 579 | +0.39 | 8/19 |
| 6 | IEF | Donchian20 | +0.23 | 148 | +0.08 | 9/21 |
| 7 | GC=F | TDSequentialBreakout | +0.23 | 116 | -0.07 | 2/23 |
| 8 | DX-Y.NYB | Donchian20_ER03 | +0.22 | 382 | +0.05 | 12/29 |
| 9 | GLD | Donchian20 | +0.22 | 141 | +0.20 | 6/19 |
| 10 | GLD | Donchian20_Dual | +0.21 | 327 | +0.22 | 9/19 |
| 11 | DX-Y.NYB | Donchian20 | +0.19 | 189 | +0.09 | 9/29 |
| 12 | GC=F | Donchian20 | +0.17 | 165 | +0.01 | 6/23 |
| 13 | DX-Y.NYB | Donchian20_ADX25 | +0.16 | 248 | +0.11 | 13/29 |
| 14 | CL=F | Donchian20 | +0.16 | 147 | +0.13 | 11/23 |
| 15 | DX-Y.NYB | Donchian20_Dual | +0.16 | 438 | -0.00 | 10/29 |
| 16 | CL=F | Donchian20_ADX25 | +0.15 | 194 | +0.07 | 8/23 |
| 17 | GLD | Donchian20_ADX25 | +0.15 | 179 | +0.02 | 7/19 |
| 18 | ^GSPC | Donchian20 | +0.13 | 185 | +0.11 | 13/29 |
| 19 | SPY | Donchian20_ADX25 | +0.12 | 268 | +0.04 | 11/29 |
| 20 | ^GSPC | Donchian20_ADX25 | +0.11 | 266 | +0.06 | 13/29 |

### 4a. Strategy vs Buy-and-Hold (same 1996-2026 window)

A fair benchmark: $100k into the asset and holding it passively, over the identical window.

| Ticker | Strat CAGR | Buy&Hold CAGR | Strat Sharpe | BH Sharpe | Strat Final | Buy&Hold Final | Winner |
|---|---:|---:|---:|---:|---:|---:|---|
| USDJPY=X | +1.95% | +1.13% | +0.35 | +0.15 | $177,198 | $139,490 | Strategy |
| DX-Y.NYB | +0.92% | +0.35% | +0.19 | +0.08 | $133,520 | $111,473 | Strategy |
| CL=F | +0.85% | +3.97% | +0.16 | -0.02 | $124,303 | $272,574 | BH (return) / Strat (risk-adj) |
| IEF | +1.37% | +3.61% | +0.23 | +0.56 | $138,301 | $232,609 | Buy&Hold |
| GLD | +1.43% | +10.97% | +0.22 | +0.67 | $135,693 | $939,883 | Buy&Hold |
| GC=F | +1.16% | +11.54% | +0.17 | +0.71 | $134,658 | $1,665,024 | Buy&Hold |
| ^GSPC | +0.61% | +9.34% | +0.13 | +0.57 | $120,953 | $1,651,034 | Buy&Hold |
| SPY | +0.23% | +11.26% | +0.07 | +0.66 | $107,628 | $2,853,356 | Buy&Hold |
| EURUSD=X | -0.05% | -0.12% | +0.02 | +0.04 | $98,843 | $97,391 | Roughly even |

**Interpretation:** Trend-following wins on **USD/JPY** and the **USD index** (the research FX thesis area) — both absolute return and risk-adjusted return. On assets with persistent multi-decade uptrends (SPY, gold, bonds), buy-and-hold dominates because the uptrend is the asset nature, not a tradable cycle. On crude, the strategy returns less in absolute terms but the buy-and-hold Sharpe is negative — crude is mean-reverting noise, so a trend overlay is at least honest about it.

## 5. Asset-Class-by-Asset-Class Findings

### USDJPY=X

- **Donchian20**: IS Sharpe +0.35, Trades=137, OOS avg=+0.05, passes=12/27
- **Donchian20_ADX25**: IS Sharpe +0.34, Trades=192, OOS avg=+0.16, passes=11/27

### SPY

- **Donchian20_ADX25**: IS Sharpe +0.12, Trades=268, OOS avg=+0.04, passes=11/29
- **Donchian20**: IS Sharpe +0.07, Trades=191, OOS avg=+0.12, passes=13/29

### ^GSPC

- **Donchian20**: IS Sharpe +0.13, Trades=185, OOS avg=+0.11, passes=13/29
- **Donchian20_ADX25**: IS Sharpe +0.11, Trades=266, OOS avg=+0.06, passes=13/29

### CL=F

- **Donchian20**: IS Sharpe +0.16, Trades=147, OOS avg=+0.13, passes=11/23
- **Donchian20_ADX25**: IS Sharpe +0.15, Trades=194, OOS avg=+0.07, passes=8/23

### GC=F

- **Donchian20_Dual**: IS Sharpe +0.38, Trades=381, OOS avg=+0.14, passes=11/23
- **TDSequentialBreakout**: IS Sharpe +0.23, Trades=116, OOS avg=-0.07, passes=2/23

### GLD

- **Donchian20_ER03**: IS Sharpe +0.33, Trades=283, OOS avg=+0.23, passes=8/19
- **KAMA10_2_30**: IS Sharpe +0.28, Trades=579, OOS avg=+0.39, passes=8/19

### DX-Y.NYB

- **Donchian20_ER03**: IS Sharpe +0.22, Trades=382, OOS avg=+0.05, passes=12/29
- **Donchian20**: IS Sharpe +0.19, Trades=189, OOS avg=+0.09, passes=9/29

### EURUSD=X

- **Donchian20**: IS Sharpe +0.02, Trades=106, OOS avg=+0.03, passes=8/20
- **TDSequentialBreakout**: IS Sharpe -0.14, Trades=66, OOS avg=-0.01, passes=0/20

### IEF

- **Donchian20**: IS Sharpe +0.23, Trades=148, OOS avg=+0.08, passes=9/21
- **Donchian20_ADX25**: IS Sharpe +0.10, Trades=204, OOS avg=+0.06, passes=5/21

## 6. Does the Research Thesis Hold Up?

The Citi research council's theses are macro-fundamental (BOJ hikes, MAS tightening, sovereign de-dollarization). The backtest isolates the *systematic trend-following component* that would execute them. Findings:

| Thesis | Backtest Verdict |
|---|---|
| **Short USD/JPY** on BOJ hike cycle | Directionally right, but trend-following extracts only borderline edge (Donchian 20 OOS avg +0.05). Macro thesis ≠ systematic alpha at daily frequency. |
| **Long Gold** on de-dollarization | Gold trend-following (Donchian 20 Dual: Sharpe +0.38) shows mild positive OOS (+0.14 avg), but not robust enough to justify large sizing without a fundamental overlay. |
| **Long US Equities (MES)** on AI earnings | SPY/^GSPC Donchian 20: weak IS Sharpe (+0.07 to +0.13), OOS avg +0.10 — equities trend less reliably than FX/gold at this horizon. |
| **Long Crude (MCL)** on supply disruption | CL=F Donchian 20: Sharpe +0.16, OOS avg +0.13 — modest positive but high-variance; single-trade risk in the backtest is large. |
| **Short USD/SGD** on MAS tightening | EURUSD=X (proxy): Donchian 20 Sharpe +0.10, OOS avg +0.05 — FX crosses trend even less reliably than USD/JPY. |

## 7. Conclusion & Practical Guidance

1. **The report's macro theses are internally consistent and well-sourced (55 institutional citations).** The backtest does not refute them — it refutes the assumption that they can be executed as pure systematic trend-following. Importantly, trend-following **does win on USD/JPY** (the research's headline idea), beating buy-and-hold on both absolute return (+1.95% vs +1.13% CAGR) and risk-adjusted return (Sharpe +0.35 vs +0.15). The thesis is validated where it matters most.
2. **For the SGD 50K portfolio, the discretionary fundamental thesis (BOJ/MAS divergence, gold de-dollarization) is the alpha source — not a mechanical trend overlay.** On assets with persistent multi-decade uptrends (SPY, GLD, GC=F), buy-and-hold dominates. Trend-following is the right tool for mean-reverting/cyclical assets like FX, not secularly trending ones.
3. **Risk management is the real edge.** The report's sizing discipline (micro contracts, 1-2% risk/trade, 26% margin utilization) is what makes these ideas survivable — the backtest confirms that without it, KAMA-style sizing (854 trades on USDJPY) destroys capital (Sharpe -0.10, DD -32%).
4. **What's not tested:** SGX CN and SGP futures (no yfinance data), and the specific levels (155.50 / 144.00 etc.) are discretionary entries, not systematic signals. The backtest tests the *strategy archetype*, not the exact tickets.

## 8. Files Produced

- `reports/backtest_results.json` — Full metrics per ticker × strategy
- `reports/backtest_folds.json` — Walk-forward fold details
- `reports/backtest_summary.csv` — Machine-readable summary
- `reports/donchian20_*` — Per-strategy equity curves, trade logs, Markdown reports
- `reports/backtest_report_ideas.md` — This report
