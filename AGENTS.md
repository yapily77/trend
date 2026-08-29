# Project Instructions for AI Agents

This file provides instructions and context for AI coding agents working on this project.

## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Session Completion

This protocol applies when ending a Beads implementation workflow. It is subordinate to explicit user, repository, and orchestrator instructions.

1. **File issues for remaining work** - Create beads for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Handle git/sync by active profile**:
   ```bash
   # Conservative/minimal/default: report status and proposed commands; wait for approval.
   git status

   # Team-maintainer opt-in only, unless current instructions forbid it:
   git pull --rebase
   git push
   git status
   ```
5. **Hand off** - Summarize changes, validation, issue status, and any blocked sync/commit/push step

**Critical rules:**
- Explicit user or orchestrator instructions override this Beads block.
- Do not commit or push without clear authority from the active profile or the current user request.
- If a required sync or push is blocked, stop and report the exact command and error.
## Build & Test

_Add your build and test commands here_

```bash
# Example:
# npm install
# npm test
```

## Architecture Overview

This project is a **systematic trend-following backtesting framework** for retail investors.

### Core Modules
- `scripts/bt/data.py` — DataFeed: yfinance-backed OHLCV with local caching
- `scripts/bt/indicators.py` — Technical indicators (KAMA, Donchian, ADX, ER, ATR, TD Sequential)
- `scripts/bt/strategies.py` — Strategy ABC + implementations (KAMA slope, Donchian breakout, TDSequential)
- `scripts/bt/engine.py` — Backtest engine with walk-forward validation, Carver sizing
- `scripts/bt/sizing.py` — Position sizing (equal volatility, adaptive)
- `scripts/bt/allocator.py` — Capital allocation
- `scripts/bt/charts.py` — Equity curve plotting
- `scripts/bt/reporting.py` — Markdown report generation
- `scripts/bt/ma200.py` — **200-day MA crossover strategy** (entry + exit discipline)
- `scripts/bt/ma200_backtest.py` — 10-year backtest + walk-forward for MA200
- `scripts/bt/ma200_exit.py` — Regime breakdown + symmetric exit analysis
- `scripts/bt/cape_analysis.py` — CAPE ratio (US S&P 500 only) + 200-DMA integrated decision matrix

### Reports
- `reports/ma200_exit_report.md` — MA200 exit discipline analysis for OCBC and Nikkei
- `reports/cape_analysis.md` — CAPE ratio analysis (US CAPE, global risk proxy) and integrated exit framework
- `reports/backtest_report_ideas.md` — Citi institutional trade ideas backtest
- `reports/backtest_results.json`, `reports/backtest_folds.json`, `reports/backtest_summary.csv` — Raw metrics
- `reports/donchian20_*` — Per-strategy equity curves, trade logs, Markdown reports

### Key Findings
- Trend following works best on **FX** (USD/JPY) and **cyclical commodities**; it lags on secular uptrends (SPY, GLD, GC=F)
- The 200-DMA MA200 exit discipline reduces MaxDD significantly on mean-reverting stocks (OCBC: -44% → -26%) but lags on indices in bull runs (Nikkei: CAGR 13% → 5%)
- CAPE = 33 (Aug 2026, US S&P 500) is ~2× the long-run mean of 16.5 — historically predicts ~0% real 10y forward returns
- **CAPE is US-only** (Multpl S&P 500 Shiller CAPE). It is a global equity-valuation proxy, NOT a Japan valuation metric. Do not use it to time the Nikkei directly.
- CAPE is a position-sizing input, not a timing signal
- For a 49-year-old investor: the 200-DMA is the hard exit trigger; CAPE informs how much equity to hold beyond the trend signal
- For the Nikkei specifically: use the 200-DMA as the primary trigger; consider ATR trailing stop as an alternative; US CAPE is a secondary global-risk overlay only

### Conventions & Patterns
- All agent reasoning, tool call arguments, commit messages, and explanations must be in English
- Chinese characters are strictly reserved for BaZi metaphysics entities (Stems, Branches, Ten Gods, Trigrams, Hexagrams, Solar Terms)
- Backtest methodology: raw (non-adjusted) closes, prior-close signal timing (no look-ahead), realistic costs (0.002% commission + 0.05% slippage), walk-forward with expanding in-sample window
- yfinance tickers: O39.SI (OCBC), ^N225 (Nikkei 225), USDJPY=X, SPY, ^GSPC, CL=F, GC=F, DX-Y.NYB
- CAPE ticker: US S&P 500 Shiller CAPE (Multpl) — NOT a Japan CAPE. No Japan CAPE available via public APIs.
