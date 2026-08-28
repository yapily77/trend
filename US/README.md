# S&P 500 Trend-Following Research — Daily ^GSPC

Tests whether trend-following strategies work on the S&P 500 (compared to
the FX-focused JPY research).

## Data
- Source: yfinance (`^GSPC`, 1995-01-03 to 2026-05-29, cached at
  `/tmp/bt_cache/^GSPC_19950101_20260530.csv`)
- Cost model: 2 pip slippage, 0.002% commission
- Validation: 3-year expanding IS / 1-year OOS walk-forward

## Scripts
- `US/scripts/fetch_sp500.py` — Fetch and cache ^GSPC daily data
- `US/run_sp500_ama.py` — AMA (KAMA) crossover vs Donchian 20 baseline

## Results (daily, 30 years)

| Strategy | Sharpe | CAGR | Trades | DD | OOS avg Sharpe | Pass 0.4 |
|---|---|---|---|---|---|---|
| AMA30 | -0.27 | -2.10% | 629 | -60.68% | -0.22 | 8/29 |
| AMA10 | -0.47 | -3.56% | 1061 | -69.88% | -0.68 | 4/29 |
| Donchian 20 (ref) | +0.14 | +0.70% | 185 | -21.26% | +0.12 | 13/29 |

## Key takeaway
Trends exist in equities, but the AMA/KAMA crossover still cannot capture
them robustly. AMA30 lost ~49% and AMA10 lost ~69% of capital over 30 years.
Donchian 20 remains the only strategy with positive IS Sharpe (+0.14) and
the lowest drawdown (-21.26%), but its Sharpe is much lower than on FX (+0.34
on USDJPY).

See `US/reports/` for fold JSONs, trade logs, and markdown reports.
See `US/charts/` for equity curves.

## Weekly S&P 500 (1995-2026, 1639 bars)

| Strategy | Sharpe | CAGR | Trades | DD | OOS avg Sharpe | Pass 0.4 |
|---|---|---|---|---|---|---|
| AMA30 | +0.07 | +0.05% | 128 | -13.85% | +0.44 | 12/29 |
| AMA10 | +0.01 | -0.03% | 184 | -11.08% | +0.26 | 13/29 |
| Donchian 20 (ref) | **+0.70** | **+0.91%** | 33 | **-11.79%** | **+0.59** | **15/29** |

Weekly transforms the picture. Donchian 20 on weekly bars has a **strong IS Sharpe (+0.70)**, **lowest drawdown (-11.79%)**, and **PF 1.95** — $100k → $132k. AMA also turns slightly positive (AMA30 +0.07 Sharpe, 12/29 folds pass).

**Key takeaway:** Weekly is where trend-following actually works on equities. The 20-bar weekly Donchian is a ~100-trading-day lookback — slow enough to ride real trends and avoid daily noise. AMA/KAMA benefit similarly but Donchian 20 is still the clear winner.

## Honest Assessment
Daily Donchian 20 on ^GSPC: +0.70% CAGR — barely beats cash after costs.
Weekly Donchian 20 is the only strategy across all assets tested
that looks genuinely profitable: +0.91% CAGR, PF 1.95, -11.8% DD,
15/29 OOS folds pass the 0.4 threshold. Still modest in absolute
terms, but no other approach comes close on any asset class.
