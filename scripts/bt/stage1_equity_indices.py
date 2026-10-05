"""Stage 1: Equity index backtests with MA200 Half-Kelly + 3xATR baseline.

Tests indices NOT fully validated with the gold/JPY baseline strategy:
  - Nikkei 225 (^N225)      : MA200 baseline + MA200 exit discipline
  - OCBC (O39.SI)           : MA200 baseline + MA200 exit discipline
  - SPY                     : MA200 baseline (consistency check)
  - QQQ                     : MA200 baseline (consistency check)
  - KOSPI 200 (^KS11)       : MA200 baseline + Donchian20
  - Hang Seng (^HSI)        : MA200 baseline + Donchian20
  - DAX (^GDAXI)            : MA200 baseline + Donchian20

Strategies:
  MA200_HK_ATR   -- Long when Close > 200 SMA; Half-Kelly sizing (0.0781); 3xATR stop; prior-close timing
  MA200_EXIT     -- Same as MA200_HK_ATR but only take long when MA200 slope > 0 (trend regime filter)
  Donchian20_HK_ATR -- Long when Close > 20-day high; Half-Kelly sizing; 3xATR stop; prior-close timing

Walk-forward: 3-year expanding IS, 1-year OOS.
Output: .bt_cache/stage1_equity_indices.json
"""
import os, json, traceback
import numpy as np
import pandas as pd
import yfinance as yf

from scripts.bt.indicators import calculate_atr, donchian_channel
from scripts.bt.sizing import calculate_equal_volatility_size

# ---- Paths ----
ROOT = "/home/yapilwsl/arthityap/trend"
CACHE_DIR = os.path.join(ROOT, ".bt_cache")
OUT_PATH = os.path.join(CACHE_DIR, "stage1_equity_indices.json")
os.makedirs(CACHE_DIR, exist_ok=True)

# ---- Parameters ----
START = "2016-01-01"
END   = "2026-06-01"
HALF_KELLY = 0.0781        # f*/2
CAPITAL    = 100_000.0
ATR_PERIOD = 14
ATR_MULT   = 3.0           # stop width = ATR_MULT * ATR(14)
COMMISSION = 0.00002       # 0.002% one-way
SLIPPAGE   = 0.0005        # 0.05% one-way
MA_PERIOD  = 200
DONCHIAN_PERIOD = 20
SLOPE_LOOKBACK = 20        # bars used to measure MA200 slope for exit discipline
IS_YEARS = 3
OOS_YEARS = 1

INDEX_TICKERS = {
    "N225":  "^N225",
    "O39.SI": "O39.SI",
    "SPY":   "SPY",
    "QQQ":   "QQQ",
    "KS11":  "^KS11",
    "HSI":   "^HSI",
    "GDAXI": "^GDAXI",
}
STRATEGY_LABELS = ["MA200_HK_ATR", "MA200_EXIT", "Donchian20_HK_ATR"]


# ---- Data helpers ----
def fetch(ticker: str) -> pd.DataFrame:
    """Fetch raw OHLCV from yfinance, flatten MultiIndex, return DataFrame indexed by Date."""
    df = yf.download(ticker, start=START, end=END, progress=False, auto_adjust=False)
    if df.empty:
        raise ValueError("No data for " + ticker)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.sort_index()
    keep = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    return df[keep]


# ---- Signal generators (prior-close safe) ----
def signals_ma200(close: pd.Series, period: int = MA_PERIOD) -> pd.Series:
    ma = close.rolling(period).mean()
    sig = pd.Series(0.0, index=close.index)
    sig[close > ma] = 1.0
    return sig


def signals_ma200_exit(close: pd.Series, period: int = MA_PERIOD, slope_lb: int = SLOPE_LOOKBACK) -> pd.Series:
    """MA200 long only when MA slope is positive (trending regime)."""
    ma = close.rolling(period).mean()
    slope = ma / ma.shift(slope_lb) - 1.0
    sig = pd.Series(0.0, index=close.index)
    sig[(close > ma) & (slope > 0)] = 1.0
    return sig


def signals_donchian20(df: pd.DataFrame) -> pd.Series:
    ch = donchian_channel(df, period=DONCHIAN_PERIOD)
    upper = ch["upper"].shift(1)
    lower = ch["lower"].shift(1)
    close = df["Close"]
    sig = pd.Series(0.0, index=close.index)
    sig[close > upper] = 1.0
    sig[close < lower] = -1.0
    return sig


def make_sig_func(strat_name: str, df: pd.DataFrame):
    """Return a callable that produces a prior-close-safe signal series.
    The callable accepts either a close-Series or a DataFrame (for Donchian).
    """
    if strat_name == "MA200_HK_ATR":
        def sig_func(series_or_df):
            c = series_or_df["Close"] if isinstance(series_or_df, pd.DataFrame) else series_or_df
            return signals_ma200(c)
        return sig_func
    elif strat_name == "MA200_EXIT":
        def sig_func(series_or_df):
            c = series_or_df["Close"] if isinstance(series_or_df, pd.DataFrame) else series_or_df
            return signals_ma200_exit(c)
        return sig_func
    elif strat_name == "Donchian20_HK_ATR":
        def sig_func(series_or_df):
            if isinstance(series_or_df, pd.DataFrame):
                d = series_or_df
            else:
                d = df[["High", "Low", "Close"]].loc[series_or_df.index]
            return signals_donchian20(d)
        return sig_func
    raise ValueError(strat_name)


# ---- Backtest engine (standalone, Half-Kelly + 3xATR stop, prior-close) ----
def _run_backtest(df: pd.DataFrame, sig: pd.Series) -> dict:
    """Full-history backtest with Half-Kelly sizing and 3xATR stop.

    Position sizing:  units = (HALF_KELLY * CAPITAL) / (ATR_MULT * ATR_14)
    Stop:             ATR_MULT * ATR_14 from entry price (long only)
    Prior-close timing: signal generated at bar i determines action at bar i+1
    Commission & slippage applied on entry and exit.
    """
    close = df["Close"].copy()
    atr = calculate_atr(df, period=ATR_PERIOD)
    sig = sig.reindex(close.index).fillna(0.0)
    pos = sig.shift(1).fillna(0.0)   # prior-close timing

    equity = np.full(len(df), np.nan)
    cash = CAPITAL
    position = 0.0
    entry_price = 0.0
    atr_at_entry = 0.0
    trades = []
    equity[0] = cash

    for i in range(1, len(df)):
        c = close.iloc[i]
        a = atr.iloc[i] if not np.isnan(atr.iloc[i]) else 0.0
        prev_pos = pos.iloc[i - 1]
        curr_pos = pos.iloc[i]

        # --- Check stop-loss first (regardless of signal change) ---
        if position != 0.0 and a > 0:
            stop_width = ATR_MULT * a
            if position > 0 and c <= entry_price - stop_width:
                exit_slip = c * SLIPPAGE
                pnl = (c - exit_slip - entry_price) * position
                commission = abs(position) * c * COMMISSION
                cash += pnl - commission
                trades.append({
                    "type": "STOP", "date": str(df.index[i].date()),
                    "entry": entry_price, "exit": c, "pnl": pnl - commission,
                    "size": position, "atr": a,
                })
                position = 0.0
                entry_price = 0.0
                atr_at_entry = 0.0

        # --- Signal change / flip ---
        if curr_pos != prev_pos:
            # Close existing
            if position != 0.0:
                exit_slip = c * SLIPPAGE
                pnl = (c - exit_slip - entry_price) * position
                commission = abs(position) * c * COMMISSION
                cash += pnl - commission
                trades.append({
                    "type": "EXIT", "date": str(df.index[i].date()),
                    "entry": entry_price, "exit": c, "pnl": pnl - commission,
                    "size": position, "atr": atr_at_entry,
                })
                position = 0.0
                entry_price = 0.0
                atr_at_entry = 0.0

            # Open new
            if curr_pos > 0 and a > 0:
                stop_width = ATR_MULT * a
                units = (HALF_KELLY * CAPITAL) / stop_width
                # Leverage cap: notional <= 2x capital
                max_units = (2.0 * CAPITAL) / c
                units = min(units, max_units)
                if units > 0:
                    position = units
                    entry_price = c + c * SLIPPAGE
                    atr_at_entry = a
                    commission = units * entry_price * COMMISSION
                    cash -= commission

        # Mark equity
        if position != 0.0:
            equity[i] = cash + (c - entry_price) * position
        else:
            equity[i] = cash

    # Force close at end
    if position != 0.0:
        c = close.iloc[-1]
        exit_slip = c * SLIPPAGE
        pnl = (c - exit_slip - entry_price) * position
        commission = abs(position) * c * COMMISSION
        cash += pnl - commission
        trades.append({
            "type": "EXIT", "date": str(df.index[-1].date()),
            "entry": entry_price, "exit": c, "pnl": pnl - commission,
            "size": position, "atr": atr_at_entry,
        })
        equity[-1] = cash

    # Fill NaNs
    equity = pd.Series(equity, index=df.index).ffill().fillna(CAPITAL)

    return _metrics(equity, trades, df.index)


def _metrics(equity: pd.Series, trades: list, index) -> dict:
    eq = equity.dropna()
    if len(eq) < 2:
        return _empty_metrics()

    roll_max = eq.cummax()
    max_dd = float((eq / roll_max - 1.0).min())

    days = (eq.index[-1] - eq.index[0]).days
    years = max(days / 365.25, 1e-6)
    cagr = float((eq.iloc[-1] / eq.iloc[0]) ** (1.0 / years) - 1.0) if eq.iloc[0] > 0 else 0.0

    daily_ret = eq.pct_change().dropna()
    sharpe = float((daily_ret.mean() / daily_ret.std()) * np.sqrt(252)) if daily_ret.std() > 0 else 0.0

    pnls = [t["pnl"] for t in trades]
    gp = sum(p for p in pnls if p > 0)
    gl = abs(sum(p for p in pnls if p < 0))
    pf = gp / gl if gl > 0 else (gp if gp > 0 else 1.0)
    wins = sum(1 for p in pnls if p > 0)
    win_rate = wins / len(trades) if trades else 0.0

    return {
        "cagr": cagr,
        "sharpe": sharpe,
        "maxdd": max_dd,
        "trades": len(trades),
        "pf": pf,
        "win_rate": win_rate,
        "final": float(eq.iloc[-1]),
    }


def _empty_metrics():
    return {"cagr": 0.0, "sharpe": 0.0, "maxdd": 0.0, "trades": 0, "pf": 1.0, "win_rate": 0.0, "final": CAPITAL}


# ---- Walk-forward (3-year expanding IS, 1-year OOS) ----
def run_walk_forward(df: pd.DataFrame, sig_func) -> dict:
    """Walk-forward validation. Returns IS/OOS metrics per fold plus averages."""
    dates = df.index
    start = dates[0]
    end = dates[-1]
    folds = []
    is_end = start + pd.DateOffset(years=IS_YEARS)
    fold_num = 0

    while is_end < end:
        oos_end = min(is_end + pd.DateOffset(years=OOS_YEARS), end)
        if (oos_end - is_end).days < 30:
            break

        is_df = df.loc[:is_end]
        oos_df = df.loc[is_end:oos_end]

        if len(is_df) < MA_PERIOD + 10 or len(oos_df) < 10:
            break

        is_sig = sig_func(is_df)
        oos_sig = sig_func(oos_df)

        is_res = _run_backtest(is_df, is_sig)
        oos_res = _run_backtest(oos_df, oos_sig)

        folds.append({
            "fold": fold_num + 1,
            "is_start": str(is_df.index[0].date()),
            "is_end": str(is_df.index[-1].date()),
            "oos_start": str(oos_df.index[0].date()),
            "oos_end": str(oos_df.index[-1].date()),
            "is": is_res,
            "oos": oos_res,
        })
        fold_num += 1
        is_end = is_end + pd.DateOffset(years=OOS_YEARS)

    if not folds:
        return {"folds": [], "avg_is": _empty_metrics(), "avg_oos": _empty_metrics()}

    keys = ["cagr", "sharpe", "maxdd", "trades", "pf", "win_rate"]
    def _avg(fold_key, metric_key):
        vals = [f[fold_key][metric_key] for f in folds]
        return float(np.mean(vals)) if vals else 0.0

    return {
        "folds": folds,
        "avg_is": {k: _avg("is", k) for k in keys},
        "avg_oos": {k: _avg("oos", k) for k in keys},
        "n_folds": len(folds),
    }


# ---- Main ----
def main():
    all_results = []
    summary_rows = []

    for idx_name, ticker in INDEX_TICKERS.items():
        print("\n" + "=" * 70)
        print("Fetching " + idx_name + " (" + ticker + ") ...")
        try:
            df = fetch(ticker)
        except Exception as e:
            print("  ERROR fetching " + ticker + ": " + str(e))
            continue
        print("  rows=%d  date_range=%s..%s" % (len(df), df.index[0].date(), df.index[-1].date()))

        for strat_name in STRATEGY_LABELS:
            print("  --- " + strat_name + " ---", end=" ")
            try:
                sig_func = make_sig_func(strat_name, df)

                # Full-history backtest
                full_sig = sig_func(df)
                full_res = _run_backtest(df, full_sig)

                # Walk-forward
                wf = run_walk_forward(df, sig_func)

                record = {
                    "index": idx_name,
                    "ticker": ticker,
                    "strategy": strat_name,
                    "cagr": full_res["cagr"],
                    "sharpe": full_res["sharpe"],
                    "maxdd": full_res["maxdd"],
                    "trades": full_res["trades"],
                    "pf": full_res["pf"],
                    "win_rate": full_res["win_rate"],
                    "oos_sharpe": wf["avg_oos"]["sharpe"],
                    "oos_maxdd": wf["avg_oos"]["maxdd"],
                    "oos_cagr": wf["avg_oos"]["cagr"],
                    "is_sharpe": wf["avg_is"]["sharpe"],
                    "n_folds": wf["n_folds"],
                    "folds": [
                        {
                            "fold": f["fold"],
                            "is_start": f["is_start"],
                            "is_end": f["is_end"],
                            "oos_start": f["oos_start"],
                            "oos_end": f["oos_end"],
                            "is_cagr": f["is"]["cagr"],
                            "is_sharpe": f["is"]["sharpe"],
                            "is_maxdd": f["is"]["maxdd"],
                            "is_trades": f["is"]["trades"],
                            "oos_cagr": f["oos"]["cagr"],
                            "oos_sharpe": f["oos"]["sharpe"],
                            "oos_maxdd": f["oos"]["maxdd"],
                            "oos_trades": f["oos"]["trades"],
                        }
                        for f in wf["folds"]
                    ],
                }
                all_results.append(record)

                # worst-case OOS MaxDD across folds (more conservative than average)
                oos_maxdd_folds = [f["oos"]["maxdd"] for f in wf["folds"] if f["oos"]["maxdd"] < 0]
                worst_oos_maxdd = float(min(oos_maxdd_folds)) if oos_maxdd_folds else 0.0
                summary_rows.append({
                    "Index": idx_name,
                    "Strategy": strat_name,
                    "CAGR": "%.1f%%" % (full_res["cagr"] * 100),
                    "Sharpe": "%.2f" % full_res["sharpe"],
                    "MaxDD": "%.1f%%" % (full_res["maxdd"] * 100),
                    "Trades": str(full_res["trades"]),
                    "PF": "%.2f" % full_res["pf"],
                    "WinRate": "%.0f%%" % (full_res["win_rate"] * 100),
                    "OOS_Sharp": "%.2f" % wf["avg_oos"]["sharpe"],
                    "OOS_MaxDD": "%.1f%%" % (wf["avg_oos"]["maxdd"] * 100),
                    "Worst_OOS_MaxDD": "%.1f%%" % (worst_oos_maxdd * 100),
                })
                print("CAGR=%.1f%% Sharpe=%.2f MaxDD=%.1f%% Trades=%d | OOS Sharpe=%.2f" % (
                    full_res["cagr"] * 100, full_res["sharpe"], full_res["maxdd"] * 100,
                    full_res["trades"], wf["avg_oos"]["sharpe"]))
            except Exception as e:
                print("ERROR: " + str(e))
                traceback.print_exc()

    # Save JSON
    with open(OUT_PATH, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print("\nSaved %d results to %s" % (len(all_results), OUT_PATH))

    # Print summary table
    print("\n" + "=" * 118)
    print("STAGE 1 EQUITY INDICES -- SUMMARY TABLE")
    print("=" * 118)
    header = "%-7s %-17s %7s %6s %7s %6s %5s %6s %9s %9s %10s" % (
        "Index", "Strategy", "CAGR", "Sharpe", "MaxDD", "Trades", "PF", "Win%", "OOS_Sharpe", "OOS_MaxDD", "Worst_OOS_DD")
    print(header)
    print("-" * 118)
    for r in summary_rows:
        print("%-7s %-17s %7s %6s %7s %6s %5s %6s %9s %9s %10s" % (
            r["Index"], r["Strategy"], r["CAGR"], r["Sharpe"], r["MaxDD"],
            r["Trades"], r["PF"], r["WinRate"], r["OOS_Sharp"], r["OOS_MaxDD"], r["Worst_OOS_MaxDD"]))
    print("=" * 118)

    # Per-index averages for quick comparison
    print("\nPer-index strategy averages (full-history Sharpe):")
    idx_groups = {}
    for r in all_results:
        idx_groups.setdefault(r["index"], []).append(r)
    for idx in INDEX_TICKERS:
        if idx not in idx_groups:
            continue
        rows = idx_groups[idx]
        avgs = {}
        for k in ["cagr", "sharpe", "maxdd", "pf"]:
            avgs[k] = float(np.mean([x[k] for x in rows]))
        print("  %s: avg Sharpe=%.2f  avg CAGR=%.1f%%  avg MaxDD=%.1f%%  avg PF=%.2f" % (
            idx, avgs["sharpe"], avgs["cagr"] * 100, avgs["maxdd"] * 100, avgs["pf"]))


if __name__ == "__main__":
    main()
