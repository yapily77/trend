"""
Full-sample (1971-2026) MA200 + Half-Kelly + 3xATR on Gold/JPY with DXY regime gate.

Strategy rules:
  - Base signal: Gold/JPY Close > MA200 (200-period SMA) -> 1 (long), else 0 (flat)
  - DXY gate:  multiply base by 1 only when DXY < DXY_200MA (200-period), else 0.
              Long ONLY when BOTH gold above its MA200 AND DXY below its MA200MA.
  - Half-Kelly position sizing: risk_pct = 0.0781
  - 3xATR trailing stop: once in a long position, exit when Close falls 3*ATR(14)
                         below the highest high since entry.
  - Prior-close timing: signal computed at close of day t, executed at open of day t+1
  - Commission: 0.00002 (0.002%), slippage: 2 pips, pip_value = 0.01 (JPY pair)
  - Capital: $100,000

Runs BOTH gated and ungated (MA200-only) for comparison.
Results saved to /home/yapilwsl/arthityap/trend/.bt_cache/full_sample_dxy_gated.json
"""
import os
import sys
import json
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = "/home/yapilwsl/arthityap/trend"
CACHE_DIR = os.path.join(BASE_DIR, ".bt_cache")
GOLD_PATH = os.path.join(CACHE_DIR, "gold_jpy_daily_1971.csv")
DXY_PATH  = os.path.join(CACHE_DIR, "DXY_19710101_20260601.csv")
OUT_PATH  = os.path.join(CACHE_DIR, "full_sample_dxy_gated.json")

sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))
from bt.indicators import calculate_atr
from bt.sizing import calculate_equal_volatility_size

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CAPITAL      = 100_000.0
RISK_PCT     = 0.0781        # Half-Kelly
SLIP_PIPS    = 2.0
COMM_PCT     = 0.00002
ATR_MULT     = 3.0
MA_PERIOD    = 200
TICKER       = "gold_jpy"

# ---------------------------------------------------------------------------
# Load & align data
# ---------------------------------------------------------------------------
gold = pd.read_csv(GOLD_PATH, index_col=0, parse_dates=True).sort_index()
dxy  = pd.read_csv(DXY_PATH,  index_col=0, parse_dates=True).sort_index()

for c in ("Open", "High", "Low", "Close"):
    gold[c] = pd.to_numeric(gold[c], errors="coerce")
dxy["DXY"] = pd.to_numeric(dxy["DXY"], errors="coerce")

# Reindex DXY to gold's date range (forward-fill so we keep gold trading days even when DXY missing)
dxy = dxy.reindex(gold.index).ffill().bfill()

print(f"Gold rows: {len(gold)}  {gold.index[0].date()} -> {gold.index[-1].date()}")
print(f"DXY  rows: {len(dxy)}  {dxy.index[0].date()} -> {dxy.index[-1].date()}")
print(f"Any NaN gold: {gold[['Close']].isna().sum().values[0]}  NaN DXY: {dxy['DXY'].isna().sum()}")

# ---------------------------------------------------------------------------
# Precompute indicators
# ---------------------------------------------------------------------------
gold["MA200"]     = gold["Close"].rolling(MA_PERIOD).mean()
gold["ATR_14"]    = calculate_atr(gold, period=14)   # FIXED: was period=MA_PERIOD(200)
dxy["DXY_200MA"]  = dxy["DXY"].rolling(MA_PERIOD).mean()

# ---------------------------------------------------------------------------
# Build signal series (aligned to gold index)
# ---------------------------------------------------------------------------
base_sig = pd.Series(0.0, index=gold.index)
base_sig[gold["Close"] > gold["MA200"]] = 1.0

# DXY gate: 1 when DXY < DXY_200MA else 0
dxy_gate = pd.Series(0.0, index=gold.index)
dxy_gate[dxy["DXY"] < dxy["DXY_200MA"]] = 1.0

# Combined gated signal (multiplication)
gated_sig = base_sig * dxy_gate

# Prior-close timing: shift by 1 so signal from close of day t is used on day t+1
base_sig_shifted = base_sig.shift(1)
gated_sig_shifted = gated_sig.shift(1)

n_valid = int(MA_PERIOD)  # first MA_PERIOD rows have NaN MA200 -> signal stays 0
print(f"\nBase signal long days (pre-shift): {(base_sig == 1).sum()}")
print(f"Gated signal long days (pre-shift): {(gated_sig == 1).sum()}")
print(f"Days where gated < base (DXY filter removed): {((base_sig == 1) & (dxy_gate == 0)).sum()}")

# ---------------------------------------------------------------------------
# Simulation loop (pure pandas/numpy)
#
#  Exit logic (trailing stop): once in a long position, exit when Close falls
#  3*ATR(14) below the highest high SINCE ENTRY.
#  This is a bar-close stop evaluated at each bar (intra-bar not considered).
# ---------------------------------------------------------------------------
def simulate(close_vals, high_vals, atr_vals, sig_vals, dates,
             capital=CAPITAL, risk_pct=RISK_PCT, atr_mult=ATR_MULT,
             slip_pips=SLIP_PIPS, comm_pct=COMM_PCT, pip_val=0.01):
    """Pure-pandas/numpy simulation.

    Trailing stop: once long, exit when Close falls 3*ATR(14) below the
    highest HIGH since entry.
    Prior-close timing: signal from close of day t governs entry/exit on day t+1.
    """
    n = len(close_vals)
    equity = np.zeros(n)
    cash   = capital
    position = 0.0
    entry_price = 0.0
    peak_high = 0.0       # highest HIGH since entry (for trailing stop)
    trades = []           # count of trades
    trade_pnl = []

    for i in range(n):
        c = close_vals[i]
        h = high_vals[i]
        s = sig_vals[i]
        av = atr_vals[i]
        if pd.isna(av) or av <= 0:
            av = 1.0

        # ---------- EXIT: trailing stop hit (long only) ----------
        if position > 0:
            stop = peak_high - atr_mult * av
            if c <= stop:
                slip = slip_pips * pip_val
                exit_price = c - slip
                pnl = (exit_price - entry_price) * position
                comm = abs(position) * exit_price * comm_pct
                cash += pnl - comm
                trades.append(1)
                trade_pnl.append(pnl - comm)
                position = 0.0
                entry_price = 0.0
                peak_high = 0.0

        # ---------- ENTRY (prior-close timing) ----------
        if position == 0.0:
            now_long = s > 0
            prev_long = (sig_vals[i - 1] > 0) if i > 0 else False
            if now_long and not prev_long:
                slip = slip_pips * pip_val
                entry_price = c + slip
                base_size = calculate_equal_volatility_size(capital, risk_pct, av)
                position = base_size
                comm = abs(position) * entry_price * comm_pct
                cash -= comm
                peak_high = h   # seed peak with entry bar's HIGH

        # ---------- EXIT: signal goes flat ----------
        if position > 0 and s <= 0:
            slip = slip_pips * pip_val
            exit_price = c - slip
            pnl = (exit_price - entry_price) * position
            comm = abs(position) * exit_price * comm_pct
            cash += pnl - comm
            trades.append(1)
            trade_pnl.append(pnl - comm)
            position = 0.0
            entry_price = 0.0
            peak_high = 0.0

        # ---------- Update peak & equity ----------
        if position > 0:
            peak_high = max(peak_high, h)
            equity[i] = cash + (c - entry_price) * position
        else:
            equity[i] = cash

    # Force close at end
    if position != 0.0 and n > 0:
        c = close_vals[-1]
        slip = slip_pips * pip_val
        exit_price = c - slip
        pnl = (exit_price - entry_price) * position
        comm = abs(position) * exit_price * comm_pct
        cash += pnl - comm
        trades.append(1)
        trade_pnl.append(pnl - comm)
        equity[-1] = cash
        position = 0.0

    eq = pd.Series(equity, index=dates)
    rm = eq.cummax()
    dd = (eq - rm) / rm
    max_dd = float(dd.min())

    days = (dates[-1] - dates[0]).days / 365.25
    final = float(eq.iloc[-1])
    cagr = (final / capital) ** (1.0 / days) - 1.0 if final > 0 and days > 0 else 0.0

    daily_ret = eq.pct_change().fillna(0.0)
    ms = daily_ret.mean()
    ss = daily_ret.std()
    sharpe = (ms / ss) * np.sqrt(252) if ss > 0 else 0.0

    gp = sum(p for p in trade_pnl if p > 0)
    gl = abs(sum(p for p in trade_pnl if p < 0))
    pf = gp / gl if gl > 0 else (gp if gp > 0 else 1.0)

    return {
        "CAGR": cagr, "Sharpe": sharpe, "Max_Drawdown": max_dd,
        "Profit_Factor": pf, "Total_Trades": len(trades),
        "Final_Value": final, "equity": eq, "daily_ret": daily_ret,
        "trades": trades, "trade_pnl": trade_pnl,
    }


# ---------------------------------------------------------------------------
# Run BOTH scenarios
# ---------------------------------------------------------------------------
close  = gold["Close"].values
highs  = gold["High"].values
atr    = gold["ATR_14"].values
dates  = gold.index

# Ungated: MA200 only (signal_shift=1 already applied in shifted series)
print("\n--- UNGATED (MA200 only, no DXY filter) ---")
ungated = simulate(close, highs, atr, base_sig_shifted.values, dates)
print(f"CAGR={ungated['CAGR']:.4%}  Sharpe={ungated['Sharpe']:.3f}  "
      f"MaxDD={ungated['Max_Drawdown']:.2%}  PF={ungated['Profit_Factor']:.2f}  "
      f"Trades={ungated['Total_Trades']}  Final={ungated['Final_Value']:,.0f}")

# Gated: MA200 AND DXY < DXY_200MA
print("\n--- GATED (MA200 + DXY<200MA, Half-Kelly, 3xATR trailing) ---")
gated = simulate(close, highs, atr, gated_sig_shifted.values, dates)
print(f"CAGR={gated['CAGR']:.4%}  Sharpe={gated['Sharpe']:.3f}  "
      f"MaxDD={gated['Max_Drawdown']:.2%}  PF={gated['Profit_Factor']:.2f}  "
      f"Trades={gated['Total_Trades']}  Final={gated['Final_Value']:,.0f}")

# ---------------------------------------------------------------------------
# Save results
# ---------------------------------------------------------------------------
out = {
    "gated": {
        "cagr": round(gated["CAGR"], 6),
        "sharpe": round(gated["Sharpe"], 6),
        "maxdd": round(gated["Max_Drawdown"], 6),
        "profit_factor": round(gated["Profit_Factor"], 6),
        "total_trades": gated["Total_Trades"],
        "final_value": round(gated["Final_Value"], 2),
        "is_full_sample": True,
        "description": "MA200 + DXY<200MA gate + Half-Kelly(0.0781) + 3xATR trailing stop, prior-close timing, full sample 1971-2026",
    },
    "ungated": {
        "cagr": round(ungated["CAGR"], 6),
        "sharpe": round(ungated["Sharpe"], 6),
        "maxdd": round(ungated["Max_Drawdown"], 6),
        "profit_factor": round(ungated["Profit_Factor"], 6),
        "total_trades": ungated["Total_Trades"],
        "final_value": round(ungated["Final_Value"], 2),
        "is_full_sample": True,
        "description": "MA200 only (no DXY filter), Half-Kelly(0.0781) + 3xATR trailing stop, prior-close timing, full sample 1971-2026",
    },
    "config": {
        "capital": CAPITAL, "risk_pct": RISK_PCT, "slip_pips": SLIP_PIPS,
        "commission_pct": COMM_PCT, "atr_mult": ATR_MULT, "ma_period": MA_PERIOD,
        "pip_value": 0.01, "ticker": TICKER, "signal_shift": 1,
        "date_range": [str(dates[0].date()), str(dates[-1].date())],
        "n_bars": int(len(dates)),
    },
}

with open(OUT_PATH, "w") as f:
    json.dump(out, f, indent=2)
print(f"\nSaved results to {OUT_PATH}")
