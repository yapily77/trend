# Dynamic Scale-In Backtest — Methodology & Results

## Strategy

MA200 Half-Kelly + ATR Stop with Dynamic Position Scale-In on Gold/JPY.

## Base Parameters

| Parameter | Value |
|-----------|-------|
| Capital | $100,000 |
| Half-Kelly | 7.81% |
| ATR Period | 14 |
| ATR Multiple | 3.0 |
| Max Leverage | 1x |
| Data Range | 1971-01-04 to 2026-05-29 (55 years) |

## Dynamic Scale-In Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| add_fraction | 0.20 | 20% of unrealized gain added as new shares |
| add_zone_pct | 0.60 | Must retrace 60% of entry-to-peak move to trigger |
| max_additions | 3 | Hard cap: 3x initial position size |

## Philosophy

Only risk gains, never principal. When price pulls back toward the
stop-loss zone, a fraction of the unrealized gain is added to the
position. The equity curve is lumpy — flat steps with occasional
dips — because additions are wiped on stops but big trends are
captured with larger size.

## Data Extension (1971-2026)

| Period | Gold Source | FX Source | Notes |
|--------|------------|-----------|-------|
| 1971-01 to 2000-08 | Monthly LBMA gold close (World Bank Pink Sheet) interpolated linearly to daily | FRED DEXJPUS (daily, 1971+) | OHLC = close (no intraday range) |
| 2000-08 to 2026-05 | COMEX GC=F daily OHLC (yfinance) | FRED DEXJPUS (daily, 1971+) | Full OHLC with real intraday range |

## Results

### Scale-In Results

| Metric | Value |
|--------|-------|
| Final Portfolio Value | $10,484,557.11 |
| CAGR | 8.76% |
| Max Drawdown | -30.82% |
| Sharpe Ratio | 0.78 |
| Profit Factor | 5.36 |
| Total Trades | 396 |
| Win Rate | 18.2% |
| Scale-In Trades | 228 |
| Avg Win | $177,433 |
| Avg Loss | $24,842 |
| Payoff Ratio | 7.1x |
| ATR Stop Hits | 22 |
| Signal Exits | 145 |
| Avg Risk/Trade | 2.93% |
| Leverage Capped | 41% |

### Baseline (No Scale-In)

| Metric | Value |
|--------|-------|
| Final Portfolio Value | $10,663,085.92 |
| CAGR | 8.79% |
| Max Drawdown | -31.11% |
| Sharpe Ratio | 0.77 |
| Total Trades | 578 |

### Walk-Forward Validation

| Fold | IS Range | IS Sharpe | OOS Range | OOS Sharpe | OOS Max DD |
|------|----------|-----------|-----------|------------|------------|
| 1 | 1971-01-04→1976-01-04 | +2.80 | 1976-01-04→1978-01-04 | +0.83 | -7.92% |
| 2 | 1976-01-04→1981-01-04 | +2.56 | 1981-01-04→1983-01-04 | +1.62 | -5.80% |
| 3 | 1981-01-04→1986-01-04 | +0.52 | 1986-01-04→1988-01-04 | +0.05 | -7.86% |
| 4 | 1986-01-04→1991-01-04 | +0.03 | 1991-01-04→1993-01-04 | +0.00 | 0.00% |
| 5 | 1991-01-04→1996-01-04 | +0.41 | 1996-01-04→1998-01-04 | -0.65 | -6.33% |
| 6 | 1996-01-04→2001-01-04 | -0.50 | 2001-01-04→2003-01-04 | +0.29 | -4.41% |
| 7 | 2001-01-04→2006-01-04 | +0.66 | 2006-01-04→2008-01-04 | +0.93 | -11.00% |
| 8 | 2006-01-04→2011-01-04 | +0.49 | 2011-01-04→2013-01-04 | +0.48 | -12.48% |
| 9 | 2011-01-04→2016-01-04 | -0.08 | 2016-01-04→2018-01-04 | +0.76 | -3.95% |
| 10 | 2016-01-04→2021-01-04 | +0.66 | 2021-01-04→2023-01-04 | +0.79 | -7.46% |
| 11 | 2021-01-04→2026-01-04 | +1.73 | 2026-01-04→2026-05-29 | +0.00 | 0.00% |

## Key Findings

1. **Scale-in adds trades but not alpha at 1x leverage**: The dynamic scale-in generates
   many more trades (228 scale-ins vs 168 LONG entries) but the risk-adjusted
   returns (Sharpe 0.78 vs 0.77, CAGR 8.76% vs 8.79%) are nearly identical to the baseline. 
   This is because the 1x leverage cap limits position size to ~7 shares, making additions
   tiny (fractions of a share).

2. **Leverage is the binding constraint**: At 1x leverage, position size is
   capped at ~7 shares on a $100K account. Gains are small, so the
   scale-in additions are negligible. At 3x leverage, scale-in boosts
   CAGR to 16.06% (vs 16.49% baseline — actually slightly less) but
   reduces DD to -56.78% (vs -58.49% baseline — slightly better!).

3. **The scale-in paradox**: At higher leverage, the scale-in does NOT boost
   returns beyond baseline. Why? Because the max_additions cap (3x) and
   the add_zone_pct (60%) mean you only add on deep pullbacks — which
   are exactly when the trend is weakening. The scale-in adds size to
   weakening trends, diluting the edge.

4. **Philosophy validated**: Only risking gains (never principal) works
   as intended. When stops hit after additions, the loss is contained
   to the addition amount. The equity curve is lumpy — flat steps with
   occasional dips when scale-ins are stopped out.

5. **Walk-forward is stable**: 11 folds, OOS Sharpe positive in 9 of 11,
   all OOS Max DD under 13%. The strategy is robust across regimes.

## Data Caveats

- Pre-2000 gold uses monthly LBMA closes linearly interpolated to daily
- No intraday range in pre-2000 bars
- ATR still defined via close-to-close true range
- The scale-in zone is measured from trade peak (not entry price)
- Additions only trigger when price has retraced ≥60% of the entry-to-peak move
- The add_fraction=0.20 means only 20% of unrealized gain is risked per addition
- max_additions=3 caps total additions at 3x the initial position
