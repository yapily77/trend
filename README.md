# Trend Following Research

## Overview
Systematic trend-following strategy research using walk-forward backtesting with
realistic cost models (2 pip slippage, 0.002% commission).

## Project Structure

```
trend/
├── scripts/
│   └── bt/                  # Backtesting engine (copied from parent project)
│       ├── __init__.py
│       ├── data.py          # DataFeed — yfinance-based OHLCV fetcher with caching
│       ├── engine.py        # Backtest — simulation engine + walk-forward validation
│       ├── indicators.py    # KAMA, Donchian, ATR, ROC
│       ├── strategies.py    # Strategy base class, DonchianBreakout, KAMASlope
│       ├── sizing.py        # Equal-volatility position sizing (Carver method)
│       ├── charts.py        # Equity curve + drawdown plotting
│       ├── reporting.py     # Markdown report + CSV trade log generation
│       └── allocator.py     # EnsemblePortfolio (1/N + inverse vol weighting)
├── charts/                  # Generated equity curve charts
│   ├── donchian20_equity.png
│   ├── donchian20_ief_equity.png
│   ├── kama10_equity.png
│   └── ensemble_equity.png
├── reports/                 # Generated reports and trade logs
│   ├── donchian20_report.md
│   ├── donchian20_trades.csv
│   ├── donchian20_ief_report.md
│   ├── kama10_report.md
│   ├── kama10_trades.csv
│   └── ensemble_metrics.json
├── cross_asset_results.json # Cross-asset backtest summary
├── run_cross_asset.py       # Script to run multi-asset backtest
└── generate_reports.py      # Script to generate all reports + charts
```

## Quick Start

```bash
# Run cross-asset trend-following backtest on 10 markets
python3 run_cross_asset.py

# Generate all reports and charts
python3 generate_reports.py
```

## Strategies

### DonchianBreakout (period=20)
Classic channel breakout — go long when price breaks above 20-day high, short below 20-day low.
The purest trend-following strategy.

### KAMASlope (period=10, fast=2, slow=30)
Kaufman's Adaptive Moving Average slope — adaptive to market noise vs trend.

## Cross-Asset Results (Donchian 20, 2005-2026)

| Ticker   | Sharpe | CAGR   | Trades | OOS Avg Sharpe |
|----------|--------|--------|--------|----------------|
| USDJPY=X | +0.29  | +1.56% | 95     | +0.33          |
| IEF      | +0.25  | +1.47% | 134    | +0.03          |
| GLD      | +0.20  | +1.26% | 141    | -0.04          |
| QQQ      | +0.11  | +0.48% | 126    | +0.23          |
| ^NDX     | +0.07  | +0.25% | 130    | +0.15          |
| SPY      | +0.04  | +0.06% | 131    | +0.23          |
| ^GSPC    | +0.03  | -0.02% | 131    | +0.23          |
| EURUSD=X | +0.03  | -0.02% | 99     | -0.01          |
| VNQ      | +0.02  | -0.05% | 122    | -0.26          |
| ^DJI     | -0.09  | -0.76% | 137    | -0.04          |

## Key Findings
- **Best market**: USDJPY=X — the trend-following edge is strongest in FX
- **Best strategy**: Donchian 20 outperforms KAMA 10/2/30 on every asset
- **Equities show weak trend signals**: SPY/^GSPC have positive OOS Sharpe but low full-run Sharpe due to long drawdown periods
- **Bonds (IEF)**: Moderate performer with lower trade frequency
- **KAMA underperforms**: Too many trades (771 vs 95) with higher churn costs
- **Walk-forward OOS Sharpe < 0.4 threshold** on most assets → strategies need refinement

## Validation Rules (from quant-strategy skill)
- 2 pip slippage mandatory
- Canonical parameters only — no optimization
- 3-year expanding IS / 1-year OOS walk-forward
- Reject if OOS Sharpe < 0.4, max DD > 30%, or significant IS→OOS drop
