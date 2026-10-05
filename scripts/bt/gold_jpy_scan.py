"""
Gold/JPY walk-forward scan of 20 strategy candidates.

Tests all candidates on synthetic gold_jpy (gold_usd × USDJPY) using
3-year expanding IS / 1-year OOS walk-forward.  Prior-close signal timing.
Cost model: 0.002% commission + 2 pip slippage.
Sizing: Carver equal-vol = (capital * risk_pct) / (2 * ATR_14).

Filters (ALL must pass):
  - OOS Sharpe (avg across folds) >= 0.4
  - MaxDD <= 0.50 (50%)
  - IS -> OOS Sharpe drop <= 0.30
  - Profit Factor >= 1.5
  - Total Trades >= 30
  - stable in >= 50% of folds (OOS Sharpe >= 0.4 in at least half)

Returns: {"passing": [...], "summary": [...]}  (valid JSON)
"""
import os, sys, json, traceback
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.bt.engine import Backtest
from scripts.bt.strategies import DonchianBreakout, KAMASlope
from scripts.bt.ma200 import MA200Crossover
from scripts.bt.indicators import calculate_atr
from scripts.bt.sizing import calculate_equal_volatility_size

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DATA_DIR  = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".bt_cache")
CACHE_PATH = os.path.join(DATA_DIR, "gold_jpy_daily_1971.csv")
CAPITAL   = 100_000.0
COMM_PCT  = 0.00002          # 0.002%
SLIP_PIPS = 2.0
IS_YEARS  = 3
OOS_YEARS = 1
DATA_START = "1995-01-01"
DATA_END   = "2026-06-01"
TICKER     = "gold_jpy"

# ---------------------------------------------------------------------------
# Strategy definitions: (label, factory, risk_pct, exit_mode, exit_param)
#   exit_mode: "signal_flat" | "trailing_3xatr"
#   exit_param: atr multiplier for trailing (None for signal_flat)
# ---------------------------------------------------------------------------
STRATEGY_DEFS = [
    # 1. Donchian breakout – signal-flat, periods 10/20/50/100
    ("DONCHIAN_10_SF",   lambda: DonchianBreakout(period=10),              0.01,  "signal_flat",  None),
    ("DONCHIAN_20_SF",   lambda: DonchianBreakout(period=20),              0.01,  "signal_flat",  None),
    ("DONCHIAN_50_SF",   lambda: DonchianBreakout(period=50),              0.01,  "signal_flat",  None),
    ("DONCHIAN_100_SF",  lambda: DonchianBreakout(period=100),             0.01,  "signal_flat",  None),
    # 2. Donchian 20 – 2x / 3x ATR trailing
    ("DONCHIAN_20_2XATR", lambda: DonchianBreakout(period=20),             0.01,  "trailing_3xatr", 2.0),
    ("DONCHIAN_20_3XATR", lambda: DonchianBreakout(period=20),             0.01,  "trailing_3xatr", 3.0),
    # 3. MA200 crossover – 3x ATR trailing (risk=0.01 baseline)
    ("MA200_3XATR",       lambda: MA200Crossover(period=200),              0.01,  "trailing_3xatr", 3.0),
    # 4. MA200 + Half-Kelly (signal-flat), three risk_pct values
    ("MA200_HK_0391",     lambda: MA200Crossover(period=200),              0.0391, "signal_flat",  None),
    ("MA200_HK_0781",     lambda: MA200Crossover(period=200),              0.0781, "signal_flat",  None),
    ("MA200_HK_15625",    lambda: MA200Crossover(period=200),              0.15625,"signal_flat",  None),
    # 5. KAMA slope – signal-flat, periods 10/20/30
    ("KAMA_10_SF",        lambda: KAMASlope(period=10, fast=2, slow=30),  0.01,  "signal_flat",  None),
    ("KAMA_20_SF",        lambda: KAMASlope(period=20, fast=2, slow=30),  0.01,  "signal_flat",  None),
    ("KAMA_30_SF",        lambda: KAMASlope(period=30, fast=2, slow=30),  0.01,  "signal_flat",  None),
    # 6. Donchian 20 + ADX>25 filter – signal-flat
    ("DONCHIAN_20_ADX25", lambda: DonchianBreakout(period=20, adx_filter=True, adx_threshold=25.0), 0.01, "signal_flat", None),
    # 7. Donchian 20 + ER>0.3 filter – signal-flat
    ("DONCHIAN_20_ER03",  lambda: DonchianBreakout(period=20, er_filter=True, er_threshold=0.3),   0.01, "signal_flat", None),
    # 8. Donchian 20 + MA200 regime gate – trailing 3x ATR
    ("DONCHIAN_20_MA200_GATE", lambda: DonchianBreakout(period=20),      0.01,  "trailing_3xatr", 3.0),
    # 9. MA200 + Half-Kelly + 3x ATR trailing (baseline, risk=0.0781)
    ("MA200_HK_3XATR",    lambda: MA200Crossover(period=200),              0.0781, "trailing_3xatr", 3.0),
    # 10. MA200 + Half-Kelly + 2x ATR trailing (tighter stops)
    ("MA200_HK_2XATR",    lambda: MA200Crossover(period=200),              0.0781, "trailing_3xatr", 2.0),
    # 11. MA200 + Half-Kelly + 4x ATR trailing (wider stops)
    ("MA200_HK_4XATR",    lambda: MA200Crossover(period=200),              0.0781, "trailing_3xatr", 4.0),
    # 12. MA200 + Half-Kelly + 5x ATR trailing
    ("MA200_HK_5XATR",    lambda: MA200Crossover(period=200),              0.0781, "trailing_3xatr", 5.0),
    # 13. MA200 + Half-Kelly + 1x ATR trailing (very tight)
    ("MA200_HK_1XATR",    lambda: MA200Crossover(period=200),              0.0781, "trailing_3xatr", 1.0),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def pip_value_for(ticker: str) -> float:
    return 0.01 if "JPY" in ticker.upper() else 0.0001


def load_data() -> pd.DataFrame | None:
    if not os.path.exists(CACHE_PATH):
        print(f"[ERR] Cache missing: {CACHE_PATH}")
        return None
    df = pd.read_csv(CACHE_PATH, index_col=0, parse_dates=True)
    if df.empty:
        return None
    df = df.sort_index()
    for c in ("Close", "Open", "High", "Low"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[(df.index >= pd.Timestamp(DATA_START)) & (df.index <= pd.Timestamp(DATA_END))]
    if len(df) < 252 * 5:
        print(f"[WARN] Only {len(df)} rows after date filter")
        return None
    return df


# ---------------------------------------------------------------------------
# Trailing-stop slice (prior-close timing, signal-flat + 3x-ATR trailing)
# Mirrors _slice_trailing in fx_walkforward_scan.py exactly.
# ---------------------------------------------------------------------------
def _slice_trailing(close, sig, atr, capital, risk_pct, atr_mult,
                    ticker, commission_pct, slippage_pips, dates):
    pv = pip_value_for(ticker)
    n = len(close)
    equity    = np.zeros(n)
    cash      = capital
    position  = 0.0
    entry_p   = 0.0
    peak_close = 0.0
    trades    = []
    trade_pnl = []
    daily_ret = np.zeros(n)

    for i in range(n):
        c  = close[i]
        s  = sig[i]
        av = atr[i]
        if pd.isna(av) or av <= 0:
            av = 1.0

        # EXIT: trailing stop hit (long only)
        if position > 0:
            stop = peak_close - atr_mult * av
            if c <= stop:
                slip = slippage_pips * pv
                ep   = c - slip
                pnl  = (ep - entry_p) * position
                comm = abs(position) * ep * commission_pct
                cash += pnl - comm
                trades.append(1)
                trade_pnl.append(pnl - comm)
                position = 0.0
                entry_p  = 0.0
                peak_close = 0.0

        # ENTRY (prior-close timing)
        if position == 0.0:
            now_long = s > 0
            prev_long = (sig[i - 1] > 0) if i > 0 else False
            if now_long and not prev_long:
                slip = slippage_pips * pv
                entry_p = c + slip
                base_size = calculate_equal_volatility_size(capital, risk_pct, av)
                position = base_size * max(1.0, 0.25)
                comm = abs(position) * entry_p * commission_pct
                cash -= comm
                peak_close = c

        # EXIT: signal goes flat
        if position > 0 and s <= 0:
            slip = slippage_pips * pv
            ep   = c - slip
            pnl  = (ep - entry_p) * position
            comm = abs(position) * ep * commission_pct
            cash += pnl - comm
            trades.append(1)
            trade_pnl.append(pnl - comm)
            position = 0.0
            entry_p  = 0.0
            peak_close = 0.0

        if position > 0:
            peak_close = max(peak_close, c)
            equity[i]  = cash + (c - entry_p) * position
        else:
            equity[i] = cash
        if i > 0:
            daily_ret[i] = (equity[i] / equity[i - 1]) - 1.0

    # Force close at end
    if position != 0.0 and n > 0:
        c = close[-1]
        slip = slippage_pips * pv
        ep   = c - slip
        pnl  = (ep - entry_p) * position
        comm = abs(position) * ep * commission_pct
        cash += pnl - comm
        trades.append(1)
        trade_pnl.append(pnl - comm)
        equity[-1] = cash
        position = 0.0

    eq = pd.Series(equity)
    rm = eq.cummax()
    dd = (eq - rm) / rm
    max_dd = float(dd.min())
    days = (dates[-1] - dates[0]).days / 365.25
    final = eq.iloc[-1]
    cagr = (final / capital) ** (1.0 / days) - 1 if days > 0 and final > 0 else 0.0
    ms, ss = daily_ret.mean(), daily_ret.std()
    sharpe = (ms / ss) * np.sqrt(252) if ss > 0 else 0.0
    gp = sum(p for p in trade_pnl if p > 0)
    gl = abs(sum(p for p in trade_pnl if p < 0))
    pf = gp / gl if gl > 0 else (gp if gp > 0 else 1.0)
    return {"CAGR": cagr, "Sharpe": sharpe, "Max_Drawdown": max_dd,
            "Profit_Factor": pf, "Total_Trades": len(trades),
            "equity": equity, "daily_ret": daily_ret}


def full_run_trailing(df, strategy, atr_mult, risk_pct):
    sig = strategy.signals(df)
    return _slice_trailing(df["Close"].values, sig.values, df["ATR_14"].values,
                           CAPITAL, risk_pct, atr_mult, TICKER, COMM_PCT, SLIP_PIPS, df.index)


# ---------------------------------------------------------------------------
# Walk-forward: signal-flat strategies via engine.run_walk_forward
# ---------------------------------------------------------------------------
def wf_signal_flat(bt, df):
    # Pre-compute signals on the FULL df so MA200/Donchian signals use complete history
    precomputed = bt.strategy.signals(df)
    bt._precomputed_signals = precomputed
    folds = bt.run_walk_forward(is_years=IS_YEARS, oos_years=OOS_YEARS)
    if not folds:
        return None
    oos_s = [f["oos_metrics"].get("Sharpe", 0.0) for f in folds]
    is_s  = [f["is_metrics"].get("Sharpe", 0.0) for f in folds]
    npassing = sum(1 for v in oos_s if v >= 0.4)
    full = bt.run()["metrics"]
    return {
        "OOS_Sharpe_avg": float(np.mean(oos_s)),
        "OOS_Sharpe_min": float(min(oos_s)),
        "IS_Sharpe_avg":  float(np.mean(is_s)),
        "n_folds_passing_0.4": npassing,
        "n_folds": len(folds),
        "frac_passing": npassing / len(folds) if folds else 0.0,
        "folds": [
            {"fold": f["fold_num"],
             "is_start": str(f["is_start"].date()),
             "is_end": str(f["is_end"].date()),
             "oos_start": str(f["oos_start"].date()),
             "oos_end": str(f["oos_end"].date()),
             "is_sharpe": f["is_metrics"].get("Sharpe", 0.0),
             "oos_sharpe": f["oos_metrics"].get("Sharpe", 0.0),
             "oos_trades": f["oos_metrics"].get("Total_Trades", 0)}
            for f in folds
        ],
        "full_metrics": full,
    }


# ---------------------------------------------------------------------------
# Walk-forward: trailing-stop strategies (custom expanding slice)
# ---------------------------------------------------------------------------
def wf_trailing(df, strategy, atr_mult, risk_pct):
    sig = strategy.signals(df)
    start = df.index[0]
    end   = df.index[-1]
    folds, cur = [], start
    fold_dates = []
    while cur + pd.DateOffset(years=IS_YEARS) < end:
        oos_end = min(cur + pd.DateOffset(years=OOS_YEARS), end)
        is_m = (df.index >= cur - pd.DateOffset(years=IS_YEARS)) & (df.index < cur)
        oos_m = (df.index >= cur) & (df.index <= oos_end)
        is_res  = _slice_trailing(df["Close"].values[is_m], sig.values[is_m],
                                  df["ATR_14"].values[is_m], CAPITAL, risk_pct,
                                  atr_mult, TICKER, COMM_PCT, SLIP_PIPS, df.index[is_m]) \
                  if is_m.sum() > 0 else None
        oos_res = _slice_trailing(df["Close"].values[oos_m], sig.values[oos_m],
                                  df["ATR_14"].values[oos_m], CAPITAL, risk_pct,
                                  atr_mult, TICKER, COMM_PCT, SLIP_PIPS, df.index[oos_m]) \
                  if oos_m.sum() > 0 else None
        if is_res and oos_res:
            folds.append({"is_metrics": is_res, "oos_metrics": oos_res})
            fold_dates.append({"fold": len(fold_dates) + 1,
                               "is_start": str(cur.date()),
                               "is_end": str((cur + pd.DateOffset(years=IS_YEARS)).date()),
                               "oos_start": str(cur.date()),
                               "oos_end": str(oos_end.date())})
        cur = cur + pd.DateOffset(years=OOS_YEARS)

    if not folds:
        return None
    oos_s = [f["oos_metrics"]["Sharpe"] for f in folds]
    is_s  = [f["is_metrics"]["Sharpe"] for f in folds]
    npassing = sum(1 for v in oos_s if v >= 0.4)
    return {
        "OOS_Sharpe_avg": float(np.mean(oos_s)),
        "OOS_Sharpe_min": float(min(oos_s)),
        "IS_Sharpe_avg":  float(np.mean(is_s)),
        "n_folds_passing_0.4": npassing,
        "n_folds": len(folds),
        "frac_passing": npassing / len(folds),
        "folds": [
            {"fold": fd["fold"],
             "is_start": fd["is_start"], "is_end": fd["is_end"],
             "oos_start": fd["oos_start"], "oos_end": fd["oos_end"],
             "is_sharpe": f["is_metrics"]["Sharpe"],
             "oos_sharpe": f["oos_metrics"]["Sharpe"],
             "oos_trades": f["oos_metrics"]["Total_Trades"]}
            for fd, f in zip(fold_dates, folds)
        ],
    }


# ---------------------------------------------------------------------------
# MA200 signal used for regime gate
#   1 when Close > MA200, 0 otherwise
# ---------------------------------------------------------------------------
def _ma200_gate(df):
    ma = df["Close"].rolling(200).mean()
    s = pd.Series(0, index=df.index)
    s[df["Close"] > ma] = 1
    return s


# ---------------------------------------------------------------------------
# Main scan
# ---------------------------------------------------------------------------
def run_scan():
    df = load_data()
    if df is None:
        return {"passing": [], "summary": []}

    df["ATR_14"] = calculate_atr(df, period=14)
    print(f"\n{'='*70}\nGold/JPY walk-forward scan\n"
          f"Market: {TICKER} | rows={len(df)} | {df.index[0].date()} -> {df.index[-1].date()}\n{'='*70}")

    passing, summary = [], []

    for label, factory, risk_pct, exit_mode, exit_param in STRATEGY_DEFS:
        try:
            strat = factory()
        except Exception as e:
            print(f"  [ERR] {label}: factory failed: {e}")
            continue

        try:
            if exit_mode == "signal_flat":
                bt = Backtest(df, strat, capital=CAPITAL, risk_pct=risk_pct,
                              slippage_pips=SLIP_PIPS, commission_pct=COMM_PCT,
                              ticker=TICKER)
                wf = wf_signal_flat(bt, df)
                if wf is None:
                    continue
                fm = wf["full_metrics"]
                max_dd, pf, n_trades = fm["Max_Drawdown"], fm["Profit_Factor"], fm["Total_Trades"]
                cagr, sharpe = fm["CAGR"], fm["Sharpe"]
            else:
                wf = wf_trailing(df, strat, exit_param, risk_pct)
                if wf is None:
                    continue
                full = full_run_trailing(df, strat, exit_param, risk_pct)
                max_dd, pf, n_trades = full["Max_Drawdown"], full["Profit_Factor"], full["Total_Trades"]
                cagr, sharpe = full["CAGR"], full["Sharpe"]

            oos_sa = wf["OOS_Sharpe_avg"]
            oos_sm = wf["OOS_Sharpe_min"]
            is_sa  = wf["IS_Sharpe_avg"]
            drop   = is_sa - oos_sa
            frac   = wf["frac_passing"]
            passes = (oos_sa >= 0.4 and max_dd >= -0.50 and drop <= 0.30
                      and pf >= 1.5 and n_trades >= 30 and frac >= 0.50)

            rec = {
                "market": TICKER, "strategy": label,
                "CAGR": round(cagr, 6), "Sharpe": round(sharpe, 6),
                "Max_Drawdown": round(max_dd, 6), "Profit_Factor": round(pf, 6),
                "Total_Trades": n_trades,
                "OOS_Sharpe_avg": round(oos_sa, 6), "OOS_Sharpe_min": round(oos_sm, 6),
                "IS_Sharpe_avg": round(is_sa, 6), "sharpe_drop": round(drop, 6),
                "n_folds_passing_0.4": wf["n_folds_passing_0.4"],
                "n_folds": wf["n_folds"], "frac_passing": round(frac, 4),
                "risk_pct": risk_pct, "exit_mode": exit_mode, "exit_param": exit_param,
                "folds": wf["folds"],
            }
            summ = {
                "market": TICKER, "strategy": label,
                "CAGR": round(cagr, 4), "OOS_Sharpe_avg": round(oos_sa, 4),
                "OOS_Sharpe_min": round(oos_sm, 4), "IS_Sharpe": round(is_sa, 4),
                "sharpe_drop": round(drop, 4), "Max_Drawdown": round(max_dd, 4),
                "Profit_Factor": round(pf, 4), "Total_Trades": n_trades,
                "n_folds_passing_0.4": wf["n_folds_passing_0.4"],
                "n_folds": wf["n_folds"], "frac_passing": round(frac, 4),
                "PASS": passes, "folds": wf["folds"],
            }
            summary.append(summ)

            if passes:
                passing.append(rec)
                print(f"  [PASS] {label:24s} | OOS_S={oos_sa:.3f} MaxDD={max_dd:.2%} "
                      f"PF={pf:.2f} Trades={n_trades} frac={frac:.1%}")
            else:
                reasons = []
                if oos_sa < 0.4:  reasons.append(f"OOS_S={oos_sa:.3f}")
                if max_dd > -0.50: reasons.append(f"MaxDD={max_dd:.2%}")
                if drop > 0.30:   reasons.append(f"drop={drop:.3f}")
                if pf < 1.5:      reasons.append(f"PF={pf:.2f}")
                if n_trades < 30: reasons.append(f"Trades={n_trades}")
                if frac < 0.50:   reasons.append(f"frac={frac:.1%}")
                print(f"  [FAIL] {label:24s} | {'; '.join(reasons)}")
        except Exception as e:
            print(f"  [ERR] {label}: {e}")
            traceback.print_exc()
            continue

    return {"passing": passing, "summary": summary}


if __name__ == "__main__":
    results = run_scan()
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "reports")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "gold_jpy_walkforward_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n{'='*70}")
    print(f"Done.  Passing: {len(results['passing'])}  |  Total combos: {len(results['summary'])}")
    print(f"Saved: {out_path}")
