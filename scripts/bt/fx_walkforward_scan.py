"""
Systematic walk-forward scan of FX strategy candidates.

Tests 7 strategy families across 9 FX pairs using 3-year expanding IS /
1-year OOS walk-forward.  Prior-close signal timing.  Cost model:
0.002% commission + 2 pip slippage.  Sizing: Carver equal-vol
= (capital * risk_pct) / (2 * ATR_14).

Filters (all must pass):
  - OOS Sharpe (avg across folds) >= 0.4
  - MaxDD <= 0.50 (50%)
  - IS -> OOS Sharpe drop <= 0.30
  - Profit Factor >= 1.5
  - Total Trades >= 30
  - stable in >= 50% of walk-forward folds (OOS Sharpe >= 0.4)

Returns: {"passing": [...], "summary": [...]}
"""
import os, sys, json, math
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np
import pandas as pd

from scripts.bt.engine import Backtest
from scripts.bt.strategies import (
    DonchianBreakout,
    KAMASlope,
)
from scripts.bt.ma200 import MA200Crossover
from scripts.bt.indicators import calculate_atr
from scripts.bt.sizing import calculate_equal_volatility_size

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CACHE_DIR = "/tmp/bt_cache"
CAPITAL = 100000.0
COMMISSION_PCT = 0.00002      # 0.002%
SLIPPAGE_PIPS = 2.0           # 2 pip slippage
IS_YEARS = 3
OOS_YEARS = 1
DATA_START = "1995-01-01"
DATA_END = "2026-06-01"

FX_TICKERS = [
    "USDJPY=X", "EURUSD=X", "GBPUSD=X", "AUDUSD=X", "NZDUSD=X",
    "USDCAD=X", "EURJPY=X", "GBPJPY=X", "AUDJPY=X",
]

# ---------------------------------------------------------------------------
# Strategy definitions
#    (label, factory, risk_pct, exit_mode, exit_param)
#    exit_mode: "signal_flat" | "trailing_3xatr" | "ma200_3xatr"
# ---------------------------------------------------------------------------
STRATEGY_DEFS = [
    # 1. Donchian breakout (period 10, 20, 50, 100, 200) - signal-flat exit
    ("DONCHIAN_10_SF",   lambda: DonchianBreakout(period=10),                       0.01, "signal_flat", None),
    ("DONCHIAN_20_SF",   lambda: DonchianBreakout(period=20),                       0.01, "signal_flat", None),
    ("DONCHIAN_50_SF",   lambda: DonchianBreakout(period=50),                       0.01, "signal_flat", None),
    ("DONCHIAN_100_SF",  lambda: DonchianBreakout(period=100),                      0.01, "signal_flat", None),
    ("DONCHIAN_200_SF",  lambda: DonchianBreakout(period=200),                      0.01, "signal_flat", None),
    # 2. Donchian breakout (period 20) - 3x ATR(14) trailing stop
    ("DONCHIAN_20_3XATR", lambda: DonchianBreakout(period=20), 0.01, "trailing_3xatr", 3.0),
    # 3. MA200 crossover (close > MA200 long, < MA200 flat) - 3x ATR stop
    ("MA200_3XATR",  lambda: MA200Crossover(period=200), 0.01, "ma200_3xatr", 3.0),
    # 4. KAMA slope (period 10, 20, 30) - signal-flat exit
    ("KAMA_10_SF",  lambda: KAMASlope(period=10, fast=2, slow=30), 0.01, "signal_flat", None),
    ("KAMA_20_SF",  lambda: KAMASlope(period=20, fast=2, slow=30), 0.01, "signal_flat", None),
    ("KAMA_30_SF",  lambda: KAMASlope(period=30, fast=2, slow=30), 0.01, "signal_flat", None),
    # 5. Donchian 20 with ADX>25 filter
    ("DONCHIAN_20_ADX25", lambda: DonchianBreakout(period=20, adx_filter=True, adx_threshold=25.0), 0.01, "signal_flat", None),
    # 6. Donchian 20 with ER>0.3 filter
    ("DONCHIAN_20_ER03", lambda: DonchianBreakout(period=20, er_filter=True, er_threshold=0.3), 0.01, "signal_flat", None),
    # 7. MA200 + Half-Kelly (risk_pct=0.0391, 0.0781, 0.15625) - signal-flat
    ("MA200_HK_0391",  lambda: MA200Crossover(period=200), 0.0391,  "signal_flat", None),
    ("MA200_HK_0781",  lambda: MA200Crossover(period=200), 0.0781,  "signal_flat", None),
    ("MA200_HK_15625", lambda: MA200Crossover(period=200), 0.15625, "signal_flat", None),
]


# ===================================================================
# Helper: load cached FX data
# ===================================================================
def _find_ticker_file(ticker: str) -> str | None:
    """Find the cached CSV file for a ticker.
    Prefers /tmp/bt_cache (yfinance '=X' format, earliest start).
    Falls back to .bt_cache (project cache, OHLC files only).
    """
    proj_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    proj_cache = os.path.join(proj_root, ".bt_cache")
    candidates = []
    # Search /tmp/bt_cache: files named TICKER_YYYYMMDD_YYYYMMDD.csv
    prefix = f"{ticker}_"
    for fname in os.listdir(CACHE_DIR):
        if fname.startswith(prefix) and fname.endswith(".csv"):
            fpath = os.path.join(CACHE_DIR, fname)
            parts = fname[len(prefix):].split("_")
            if len(parts) >= 2:
                try:
                    start = parts[0]
                    candidates.append((start, fpath, True))
                except ValueError:
                    continue
    # Search .bt_cache fallback (OHLC files only)
    base_ticker = ticker.replace("=X", "")
    if os.path.isdir(proj_cache):
        for fname in os.listdir(proj_cache):
            if fname.startswith(base_ticker) and fname.endswith(".csv"):
                fpath = os.path.join(proj_cache, fname)
                try:
                    rest = fname[len(base_ticker):].lstrip("_")
                    start = rest.split("_")[0]
                    # Only use files with OHLC (4+ columns)
                    with open(fpath) as f:
                        ncols = len(f.readline().split(","))
                    if ncols >= 4:
                        candidates.append((start, fpath, False))
                except Exception:
                    continue
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def load_ticker(ticker: str) -> pd.DataFrame | None:
    fpath = _find_ticker_file(ticker)
    if fpath is None:
        return None
    df = pd.read_csv(fpath, index_col=0, parse_dates=True)
    if df.empty:
        return None
    cols = list(df.columns)
    # Some .bt_cache files have ticker as the value column name, not "Close"
    if "Close" not in cols:
        if len(cols) == 2:
            # Single-column file: Date, TICKER -> rename to Close
            df = df.rename(columns={cols[1]: "Close"})
        else:
            return None
    df = df.sort_index()
    # Ensure required columns exist; fill missing with Close
    if "High" not in df.columns or df["High"].isna().all():
        df["High"] = df["Close"]
    if "Low" not in df.columns or df["Low"].isna().all():
        df["Low"] = df["Close"]
    if "Open" not in df.columns or df["Open"].isna().all():
        df["Open"] = df["Close"]
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df["High"] = pd.to_numeric(df["High"], errors="coerce")
    df["Low"] = pd.to_numeric(df["Low"], errors="coerce")
    df["Open"] = pd.to_numeric(df["Open"], errors="coerce")
    df = df[(df.index >= pd.Timestamp(DATA_START)) & (df.index <= pd.Timestamp(DATA_END))]
    if len(df) < 252 * 5:
        return None
    return df


# ===================================================================
# Walk-forward for signal-flat strategies (use engine.run_walk_forward)
# ===================================================================
def walkforward_signal_flat(bt: Backtest) -> dict | None:
    folds = bt.run_walk_forward(is_years=IS_YEARS, oos_years=OOS_YEARS)
    if not folds:
        return None

    oos_s = [f["oos_metrics"].get("Sharpe", 0.0) for f in folds]
    is_s = [f["is_metrics"].get("Sharpe", 0.0) for f in folds]
    n_passing = sum(1 for v in oos_s if v >= 0.4)
    n_folds = len(folds)
    full = bt.run()

    return {
        "OOS_Sharpe_avg": float(np.mean(oos_s)) if oos_s else 0.0,
        "OOS_Sharpe_min": float(min(oos_s)) if oos_s else 0.0,
        "IS_Sharpe_avg": float(np.mean(is_s)) if is_s else 0.0,
        "n_folds_passing_0.4": n_passing,
        "n_folds": n_folds,
        "frac_passing": n_passing / n_folds if n_folds else 0.0,
        "Max_Drawdown": full["metrics"]["Max_Drawdown"],
        "Profit_Factor": full["metrics"]["Profit_Factor"],
        "Total_Trades": full["metrics"]["Total_Trades"],
        "folds": [
            {
                "fold": f["fold_num"],
                "is_start": str(f["is_start"].date()),
                "is_end": str(f["is_end"].date()),
                "oos_start": str(f["oos_start"].date()),
                "oos_end": str(f["oos_end"].date()),
                "is_sharpe": f["is_metrics"].get("Sharpe", 0.0),
                "oos_sharpe": f["oos_metrics"].get("Sharpe", 0.0),
                "oos_trades": f["oos_metrics"].get("Total_Trades", 0),
            }
            for f in folds
        ],
    }


# ===================================================================
# Helper: pip_value from ticker (same logic as engine.Backtest.__init__)
# ===================================================================
def _pip_value(ticker: str) -> float:
    t = ticker.upper()
    if "JPY" in t:
        return 0.01
    return 0.0001


# ===================================================================
# Custom walk-forward / slice for trailing-stop strategies.
# Prior-close signal timing: signal[i] determines position held on bar i.
# Trailing stop: for longs, stop = max_close_since_entry - atr_mult*ATR.
#   Exit when close <= stop.
# ===================================================================
def _slice_trailing(close, sig, atr, capital, risk_pct, atr_mult,
                    ticker, commission_pct, slippage_pips, dates):
    """Run one slice with 3x-ATR trailing stop.  Returns metrics dict."""
    pip_value = _pip_value(ticker)
    n = len(close)
    equity = np.zeros(n)
    cash = capital
    position = 0.0          # units (positive=long)
    entry_price = 0.0
    peak_close = 0.0        # highest close since entry (for long)
    trades = []
    trade_pnl = []
    daily_ret = np.zeros(n)

    for i in range(n):
        c = close[i]
        s = sig[i]
        atr_val = atr[i]
        if pd.isna(atr_val) or atr_val <= 0:
            atr_val = 1.0

        # --- EXIT: trailing stop (long only here; FX trends up so shorts rare) ---
        if position > 0:
            stop_level = peak_close - atr_mult * atr_val
            if c <= stop_level:
                slippage = slippage_pips * pip_value
                exit_price = c - slippage
                pnl = (exit_price - entry_price) * position
                commission = abs(position) * exit_price * commission_pct
                cash += pnl - commission
                trades.append(1)
                trade_pnl.append(pnl - commission)
                position = 0.0
                entry_price = 0.0
                peak_close = 0.0

        # --- ENTRY (prior-close timing: signal[i] implies entry at bar i close) ---
        if position == 0.0:
            now_long = s > 0
            prev_long = (sig[i - 1] > 0) if i > 0 else False
            if now_long and not prev_long:
                slippage = slippage_pips * pip_value
                entry_price = c + slippage          # pay slippage on long entry
                base_size = calculate_equal_volatility_size(capital, risk_pct, atr_val)
                position = base_size * max(1.0, 0.25)
                commission = abs(position) * entry_price * commission_pct
                cash -= commission
                peak_close = c

        # --- EXIT: signal goes flat ---
        if position > 0 and s <= 0:
            slippage = slippage_pips * pip_value
            exit_price = c - slippage
            pnl = (exit_price - entry_price) * position
            commission = abs(position) * exit_price * commission_pct
            cash += pnl - commission
            trades.append(1)
            trade_pnl.append(pnl - commission)
            position = 0.0
            entry_price = 0.0
            peak_close = 0.0

        # Update trailing peak
        if position > 0:
            peak_close = max(peak_close, c)
            equity[i] = cash + (c - entry_price) * position
        else:
            equity[i] = cash

        if i > 0:
            daily_ret[i] = (equity[i] / equity[i - 1]) - 1.0

    # Force close at end
    if position != 0.0 and n > 0:
        c = close[-1]
        slippage = slippage_pips * pip_value
        exit_price = c - slippage
        pnl = (exit_price - entry_price) * position
        commission = abs(position) * exit_price * commission_pct
        cash += pnl - commission
        trades.append(1)
        trade_pnl.append(pnl - commission)
        equity[-1] = cash
        position = 0.0

    # ---- Metrics ----
    eq = pd.Series(equity)
    dr = pd.Series(daily_ret)
    rm = eq.cummax()
    dd = (eq - rm) / rm
    max_dd = float(dd.min())
    days = (dates[-1] - dates[0]).days / 365.25
    final = eq.iloc[-1]
    cagr = (final / capital) ** (1.0 / days) - 1 if days > 0 and final > 0 else 0.0
    ms = dr.mean()
    ss = dr.std()
    sharpe = (ms / ss) * np.sqrt(252) if ss > 0 else 0.0
    gp = sum(p for p in trade_pnl if p > 0)
    gl = abs(sum(p for p in trade_pnl if p < 0))
    pf = gp / gl if gl > 0 else (gp if gp > 0 else 1.0)
    return {"CAGR": cagr, "Sharpe": sharpe, "Max_Drawdown": max_dd,
            "Profit_Factor": pf, "Total_Trades": len(trades)}


def walkforward_trailing_stop(df, strategy, atr_mult, risk_pct, ticker):
    """Walk-forward with 3x-ATR trailing stop."""
    signals = strategy.signals(df)
    atr_vals = df["ATR_14"].values
    close_vals = df["Close"].values
    sig_vals = signals.values
    dates = df.index

    start_date = dates[0]
    end_date = dates[-1]
    folds = []
    cur_is_end = start_date + pd.DateOffset(years=IS_YEARS)
    fold_idx = 0
    fold_starts = []

    while cur_is_end < end_date:
        oos_end = min(cur_is_end + pd.DateOffset(years=OOS_YEARS), end_date)
        fold_starts.append(start_date)

        # IS slice
        is_m = (dates >= start_date) & (dates < cur_is_end)
        is_res = _slice_trailing(
            close_vals[is_m], sig_vals[is_m], atr_vals[is_m],
            CAPITAL, risk_pct, atr_mult,
            ticker, COMMISSION_PCT, SLIPPAGE_PIPS,
            dates[is_m]) if is_m.sum() > 0 else None

        # OOS slice
        oos_m = (dates >= cur_is_end) & (dates <= oos_end)
        oos_res = _slice_trailing(
            close_vals[oos_m], sig_vals[oos_m], atr_vals[oos_m],
            CAPITAL, risk_pct, atr_mult,
            ticker, COMMISSION_PCT, SLIPPAGE_PIPS,
            dates[oos_m]) if oos_m.sum() > 0 else None

        if is_res and oos_res:
            folds.append({"is_metrics": is_res, "oos_metrics": oos_res})

        start_date = cur_is_end
        cur_is_end = cur_is_end + pd.DateOffset(years=OOS_YEARS)
        fold_idx += 1

    n_folds = len(folds)
    if n_folds == 0:
        return None

    oos_s = [f["oos_metrics"]["Sharpe"] for f in folds]
    is_s = [f["is_metrics"]["Sharpe"] for f in folds]
    n_passing = sum(1 for v in oos_s if v >= 0.4)

    # Build fold date info
    fold_dates = []
    cur = df.index[0]
    for i in range(n_folds):
        is_s_d = cur
        is_e_d = cur + pd.DateOffset(years=IS_YEARS)
        oos_s_d = cur
        oos_e_d = min(cur + pd.DateOffset(years=OOS_YEARS), end_date)
        fold_dates.append({
            "fold": i + 1,
            "is_start": str(is_s_d.date()),
            "is_end": str(is_e_d.date()),
            "oos_start": str(oos_s_d.date()),
            "oos_end": str(oos_e_d.date()),
        })
        cur = cur + pd.DateOffset(years=OOS_YEARS)

    return {
        "OOS_Sharpe_avg": float(np.mean(oos_s)) if oos_s else 0.0,
        "OOS_Sharpe_min": float(min(oos_s)) if oos_s else 0.0,
        "IS_Sharpe_avg": float(np.mean(is_s)) if is_s else 0.0,
        "n_folds_passing_0.4": n_passing,
        "n_folds": n_folds,
        "frac_passing": n_passing / n_folds if n_folds else 0.0,
        "Max_Drawdown": 0.0,  # filled later from full run
        "Profit_Factor": 0.0,
        "Total_Trades": 0,
        "folds": [
            {
                "fold": fd["fold"],
                "is_start": fd["is_start"],
                "is_end": fd["is_end"],
                "oos_start": fd["oos_start"],
                "oos_end": fd["oos_end"],
                "is_sharpe": f["is_metrics"]["Sharpe"],
                "oos_sharpe": f["oos_metrics"]["Sharpe"],
                "oos_trades": f["oos_metrics"]["Total_Trades"],
            }
            for fd, f in zip(fold_dates, folds)
        ],
    }


# ===================================================================
# Full-run trailing-stop backtest (for overall MaxDD / PF / trades)
# ===================================================================
def full_run_trailing(df, strategy, atr_mult, risk_pct, ticker):
    """Single full backtest with trailing stop -> overall metrics."""
    pip_value = _pip_value(ticker)
    signals = strategy.signals(df)
    atr_vals = df["ATR_14"].values
    close_vals = df["Close"].values
    sig_vals = signals.values
    dates = df.index

    n = len(df)
    equity = np.zeros(n)
    cash = CAPITAL
    position = 0.0
    entry_price = 0.0
    peak_close = 0.0
    trades = []
    trade_pnl = []
    daily_ret = np.zeros(n)

    for i in range(n):
        c = close_vals[i]
        s = sig_vals[i]
        atr_val = atr_vals[i]
        if pd.isna(atr_val) or atr_val <= 0:
            atr_val = 1.0

        if position > 0:
            stop_level = peak_close - atr_mult * atr_val
            if c <= stop_level:
                slippage = SLIPPAGE_PIPS * pip_value
                exit_price = c - slippage
                pnl = (exit_price - entry_price) * position
                commission = abs(position) * exit_price * COMMISSION_PCT
                cash += pnl - commission
                trades.append(1); trade_pnl.append(pnl - commission)
                position = 0.0; entry_price = 0.0; peak_close = 0.0

        if position == 0.0:
            now_long = s > 0
            prev_long = (sig_vals[i - 1] > 0) if i > 0 else False
            if now_long and not prev_long:
                slippage = SLIPPAGE_PIPS * pip_value
                entry_price = c + slippage
                base_size = calculate_equal_volatility_size(CAPITAL, risk_pct, atr_val)
                position = base_size * max(1.0, 0.25)
                commission = abs(position) * entry_price * COMMISSION_PCT
                cash -= commission
                peak_close = c

        if position > 0 and s <= 0:
            slippage = SLIPPAGE_PIPS * pip_value
            exit_price = c - slippage
            pnl = (exit_price - entry_price) * position
            commission = abs(position) * exit_price * COMMISSION_PCT
            cash += pnl - commission
            trades.append(1); trade_pnl.append(pnl - commission)
            position = 0.0; entry_price = 0.0; peak_close = 0.0

        if position > 0:
            peak_close = max(peak_close, c)
            equity[i] = cash + (c - entry_price) * position
        else:
            equity[i] = cash
        if i > 0:
            daily_ret[i] = (equity[i] / equity[i - 1]) - 1.0

    if position != 0.0 and n > 0:
        c = close_vals[-1]
        slippage = SLIPPAGE_PIPS * pip_value
        exit_price = c - slippage
        pnl = (exit_price - entry_price) * position
        commission = abs(position) * exit_price * COMMISSION_PCT
        cash += pnl - commission
        trades.append(1); trade_pnl.append(pnl - commission)
        equity[-1] = cash

    eq = pd.Series(equity)
    rm = eq.cummax()
    dd = (eq - rm) / rm
    max_dd = float(dd.min())
    days = (dates[-1] - dates[0]).days / 365.25
    final = eq.iloc[-1]
    cagr = (final / CAPITAL) ** (1.0 / days) - 1 if days > 0 and final > 0 else 0.0
    ms = daily_ret.mean()
    ss = daily_ret.std()
    sharpe = (ms / ss) * np.sqrt(252) if ss > 0 else 0.0
    gp = sum(p for p in trade_pnl if p > 0)
    gl = abs(sum(p for p in trade_pnl if p < 0))
    pf = gp / gl if gl > 0 else (gp if gp > 0 else 1.0)
    return {"CAGR": cagr, "Sharpe": sharpe, "Max_Drawdown": max_dd,
            "Profit_Factor": pf, "Total_Trades": len(trades)}


# ===================================================================
# Main scan
# ===================================================================
def run_scan():
    all_passing = []
    summary = []

    for ticker in FX_TICKERS:
        df = load_ticker(ticker)
        if df is None:
            print(f"[SKIP] {ticker}: no data")
            continue

        print(f"\n{'='*65}")
        print(f"Market: {ticker}  |  rows={len(df)}  |  {df.index[0].date()} -> {df.index[-1].date()}")
        print(f"{'='*65}")

        # Precompute ATR column so engine can use it
        df["ATR_14"] = calculate_atr(df, period=14)

        for label, factory, risk_pct, exit_mode, exit_param in STRATEGY_DEFS:
            try:
                strat = factory()
            except Exception as e:
                print(f"  [ERR] {label}: factory: {e}")
                continue

            try:
                bt = Backtest(df, strat, capital=CAPITAL, risk_pct=risk_pct,
                              slippage_pips=SLIPPAGE_PIPS,
                              commission_pct=COMMISSION_PCT, ticker=ticker)

                if exit_mode == "signal_flat":
                    wf = walkforward_signal_flat(bt)
                    if wf is None:
                        continue
                    full_metrics = bt.run()["metrics"]
                    max_dd = full_metrics["Max_Drawdown"]
                    pf = full_metrics["Profit_Factor"]
                    n_trades = full_metrics["Total_Trades"]
                    cagr = full_metrics["CAGR"]
                    sharpe = full_metrics["Sharpe"]
                elif exit_mode in ("trailing_3xatr", "ma200_3xatr"):
                    wf = walkforward_trailing_stop(df, strat, exit_param, risk_pct, ticker)
                    if wf is None:
                        continue
                    full = full_run_trailing(df, strat, exit_param, risk_pct, ticker)
                    max_dd = full["Max_Drawdown"]
                    pf = full["Profit_Factor"]
                    n_trades = full["Total_Trades"]
                    cagr = full["CAGR"]
                    sharpe = full["Sharpe"]
                else:
                    continue

                # Evaluate filters
                oos_sa = wf["OOS_Sharpe_avg"]
                oos_sm = wf["OOS_Sharpe_min"]
                is_sa = wf["IS_Sharpe_avg"]
                sharpe_drop = is_sa - oos_sa
                frac = wf["frac_passing"]

                passes = (
                    oos_sa >= 0.4 and
                    max_dd <= 0.50 and
                    sharpe_drop <= 0.30 and
                    pf >= 1.5 and
                    n_trades >= 30 and
                    frac >= 0.50
                )

                record = {
                    "market": ticker,
                    "strategy": label,
                    "CAGR": round(cagr, 6),
                    "Sharpe": round(sharpe, 6),
                    "Max_Drawdown": round(max_dd, 6),
                    "Profit_Factor": round(pf, 6),
                    "Total_Trades": n_trades,
                    "OOS_Sharpe_avg": round(oos_sa, 6),
                    "OOS_Sharpe_min": round(oos_sm, 6),
                    "IS_Sharpe_avg": round(is_sa, 6),
                    "sharpe_drop": round(sharpe_drop, 6),
                    "n_folds_passing_0.4": wf["n_folds_passing_0.4"],
                    "n_folds": wf["n_folds"],
                    "frac_passing": round(frac, 4),
                    "risk_pct": risk_pct,
                    "exit_mode": exit_mode,
                    "exit_param": exit_param,
                    "folds": wf["folds"],
                }

                summary.append({
                    "market": ticker,
                    "strategy": label,
                    "CAGR": round(cagr, 4),
                    "OOS_Sharpe_avg": round(oos_sa, 4),
                    "OOS_Sharpe_min": round(oos_sm, 4),
                    "IS_Sharpe": round(is_sa, 4),
                    "sharpe_drop": round(sharpe_drop, 4),
                    "Max_Drawdown": round(max_dd, 4),
                    "Profit_Factor": round(pf, 4),
                    "Total_Trades": n_trades,
                    "n_folds_passing_0.4": wf["n_folds_passing_0.4"],
                    "n_folds": wf["n_folds"],
                    "frac_passing": round(frac, 4),
                    "PASS": passes,
                    "folds": wf["folds"],
                })

                if passes:
                    all_passing.append(record)
                    print(f"  [PASS] {label:20s} | OOS_S={oos_sa:.3f} | MaxDD={max_dd:.2%} | "
                          f"PF={pf:.2f} | Trades={n_trades} | frac={frac:.1%}")
                else:
                    reasons = []
                    if oos_sa < 0.4: reasons.append(f"OOS_S={oos_sa:.3f}")
                    if max_dd > 0.50: reasons.append(f"MaxDD={max_dd:.2%}")
                    if sharpe_drop > 0.30: reasons.append(f"drop={sharpe_drop:.3f}")
                    if pf < 1.5: reasons.append(f"PF={pf:.2f}")
                    if n_trades < 30: reasons.append(f"Trades={n_trades}")
                    if frac < 0.50: reasons.append(f"frac={frac:.1%}")
                    print(f"  [FAIL] {label:20s} | {'; '.join(reasons)}")

            except Exception as e:
                print(f"  [ERR] {label}: {e}")
                traceback.print_exc()
                continue

    return {"passing": all_passing, "summary": summary}


if __name__ == "__main__":
    results = run_scan()
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "fx_walkforward_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n{'='*65}")
    print(f"Done.  Passing: {len(results['passing'])}  |  Total combos: {len(results['summary'])}")
    print(f"Saved: {out_path}")
