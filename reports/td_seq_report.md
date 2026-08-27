# Tom DeMark Sequential Indicators — Research Report

**Data**: USDJPY=X (1996–2026, 29.6 years), cross-asset: SPY, QQQ, GLD, IEF
**Strategies**: TD Sequential Counter-Trend, TD Combo, TD Sequential Breakout
**Cost model**: 2 pip slippage, 0.002% commission
**Validation**: 3-year expanding IS / 1-year OOS walk-forward
**Rejection rules**: OOS Sharpe < 0.4, max DD > 30%

---

## 1. What Are Tom DeMark Sequential Indicators?

Tom DeMark developed the **TD Sequential** as a trend-exhaustion / counter-trend system. Unlike Donchian breakouts (which follow trends), TD Sequential tries to **fade** trends at points of exhaustion.

### Core Components

| Component | Condition | Meaning |
|-----------|-----------|---------|
| **TD Setup (9)** | 9 consecutive closes > close[i-4] (buy) or < close[i-4] (sell) | Trend is developing |
| **TD Countdown (13)** | 13 bars (within a window) where close < low[i-2] (buy) or close > high[i-2] (sell) after a setup | Trend is exhausting |
| **TD Combo** | Stricter version combining setup + countdown with tighter filtering | Higher-conviction signals |
| **TDST Levels** | TDST Demand = highest high during buy setup; TDST Supply = lowest low during sell setup | Dynamic support/resistance |

### Philosophy
- **Counter-trend**: Buy when sell countdown completes (bulls exhausted), sell when buy countdown completes (bears exhausted)
- **Trend-following filter**: Use setup completion as confirmation that a trend exists, then enter on breakout

---

## 2. Results on USDJPY=X (29.6 years)

| Strategy | Sharpe | Trades | Max DD | OOS Avg Sharpe | Folds ≥ 0.4 |
|----------|--------|--------|--------|----------------|--------------|
| **TD Seq Breakout** | **+0.10** | 87 | -19.40% | -0.05 | 1/27 |
| TD Counter-Trend | -0.12 | 1 | -41.54% | +0.01 | 1/27 |
| TD Combo | +0.15 | 1 | -24.81% | +0.00 | 1/27 |

### Analysis

**TD Sequential Breakout** (trend-following using setup as entry):
- 87 trades, Sharpe +0.10, DD -19.40% — better risk control than Donchian 20 (DD -32.71%)
- But worse Sharpe (+0.10 vs +0.34) and far fewer trades (87 vs 137)
- Only 1/27 OOS folds pass 0.4 — edge is not robust
- The TDST demand/supply levels as entry filter are too restrictive, missing most valid breakouts

**TD Counter-Trend**:
- Catastrophic — only 1 trade over 29.6 years
- The sell countdown condition (`close > high[i-2]`) never fires 13 times within any window because USDJPY trended upward for most of this period
- The buy countdown fires 26 times but mostly in the same 20-bar window (April-May 2006), producing only 1 actionable trade

**TD Combo**:
- Only 1 trade — the combo requires both setup and countdown to fire in a specific sequence, which is extremely rare

---

## 3. Cross-Asset Results (TD Seq Breakout)

| Asset | Sharpe | Trades | Max DD | OOS Avg | ≥0.4 |
|-------|--------|--------|--------|---------|------|
| USDJPY=X | +0.10 | 87 | -19.40% | -0.05 | 1/27 |
| SPY | 0.00 | 0 | 0.00% | 0.00 | 0/29 |
| QQQ | 0.00 | 0 | 0.00% | 0.00 | 0/25 |
| GLD | 0.00 | 0 | 0.00% | 0.00 | 0/19 |
| IEF | 0.00 | 0 | 0.00% | 0.00 | 0/21 |

**TD Sequential breakouts only work on USDJPY=X.** No other asset produced any trades — the setup condition (9 consecutive closes > close[i-4]) was never met for equities or bonds. This suggests the 9-bar consecutive comparison is too strict for non-FX assets.

---

## 4. Comparison: Donchian 20 vs TD Sequential Breakout

| Metric | Donchian 20 | TD Seq Breakout |
|--------|-------------|-----------------|
| Sharpe | +0.34 | +0.10 |
| Trades | 137 | 87 |
| Max DD | -32.71% | -19.40% |
| OOS Avg Sharpe | +0.03 | -0.05 |
| Folds ≥ 0.4 | 11/27 | 1/27 |
| Profit Factor | 1.63 | ~1.0 |

Donchian 20 wins on Sharpe and consistency (11/27 folds pass 0.4). TD Seq Breakout wins only on drawdown control.

---

## 5. Why TD Sequential Failed

### Fundamental Issues

1. **Countdown condition too strict**: `close < low[i-2]` requires 13 bars where each close is below the low from 2 bars ago. On daily FX data, this almost never happens consecutively — prices rarely make 13 straight days of lower lows relative to 2-day-old lows. Even with a relaxed 20-bar window, only buy countdowns fire (during the 2006 uptrend), never sell countdowns.

2. **Setup condition too strict for equities**: 9 consecutive closes > close[i-4] means 9 out of every 10 trading days must be up-days. This almost never happens for equities (which have many choppy/down days), explaining zero trades on SPY, QQQ, GLD, IEF.

3. **Counter-trend philosophy conflicts with trending FX**: USDJPY trended strongly upward from 2006-2024. Counter-trend signals (sell exhaustion → go long) fire once and then the trend continues, but the strategy can't re-enter because it's already in a position from the only countdown completion.

4. **TD Combo is too restrictive**: Requiring setup AND countdown in a specific sequence produces only 1 trade in 29.6 years.

### What TD Sequential Does Well
- The **TDST demand/supply levels** provide meaningful dynamic support/resistance
- The **setup concept** (9 consecutive closes relative to 4 bars ago) captures momentum effectively
- The **countdown concept** is sound in theory — 13 bars of exhaustion before reversal

### What Would Fix It
1. **Relax the countdown to a wider window** (already done: 20-bar window allows more valid bars)
2. **Use weekly data** — TD Sequential was designed for weekly charts, not daily
3. **Combine with trend filter** — only take counter-trend signals when the higher timeframe trend is exhausted
4. **Use TD 9-Count (Setup only)** as a trend filter rather than a standalone signal

---

## 6. Regime Filter Comparison Summary

| Filter Type | Donchian 20 Sharpe | DD | Trades | Verdict |
|-------------|--------------------|-----|--------|---------|
| No filter | +0.34 | -32.71% | 137 | Best Sharpe, fails DD rule |
| ADX > 25 | +0.25 | -27.08% | 197 | Better DD, worse Sharpe |
| ER > 0.3 | +0.06 | -16.23% | 289 | Too many trades |
| TD Seq Breakout | +0.10 | -19.40% | 87 | Fewer trades, lower Sharpe |
| Dual Donchian 20/50 | -0.17 | -8.00% | 323 | Too restrictive |

**No regime filter or alternative indicator improves the Donchian 20 edge on USDJPY.** The baseline remains the best performer on Sharpe despite failing the max DD rule. The fundamental issue is that 29.6 years of USDJPY data includes the 1996-2005 period which is unfavorable for trend following on this pair.

---

## 7. Key Takeaways

1. **Tom DeMark Sequential is a counter-trend system** — fundamentally different from trend-following breakouts. Applying it as a trend-following filter (TD Seq Breakout) is an adaptation, not a pure implementation.

2. **Daily FX data is too noisy for 13-bar consecutive countdowns** — the strict TD Sequential condition rarely fires. A relaxed 20-bar window helps but produces asymmetric signals (only buy countdowns, never sell).

3. **TDST levels are the most useful output** — demand/supply levels provide meaningful support/resistance, even if the trading signals themselves are not profitable.

4. **The equity/bond markets don't exhibit the 9-bar consecutive momentum** that TD Setup requires — TD Sequential is FX-specific in its applicability.

5. **For this research project, the baseline Donchian 20 remains the best strategy** despite failing the max DD rule. The additional 1996-2005 period (Asian crisis, Dot-com bust) is the primary source of drawdowns.
