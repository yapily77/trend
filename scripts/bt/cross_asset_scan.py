"""Stage 1: Cross-asset backtest scan — 7 strategy candidates × 6 markets.

Markets:  SPY, QQQ, ^N225, GLD, IEF, GC=F
Strategies:
  1. Donchian breakout (period 10)              — signal-flat exit  (engine.py)
  2. Donchian breakout (period 20) + 3xATR TS   — trailing stop   (custom)
  3. MA200 crossover + 3xATR trailing stop      — trailing stop   (custom)
  4. KAMA slope (period 10)                     — signal-flat exit  (engine.py)
  5. Donchian 20 with ADX>25 filter             — signal-flat exit  (engine.py)
  6. Donchian 20 with ER>0.3 filter             — signal-flat exit  (engine.py)
  7. MA200 crossover + Half-Kelly sizing        — signal-flat exit  (custom WF)

Methodology: 3-year expanding IS / 1-year OOS walk-forward, prior-close timing,
Carver equal-vol sizing, 0.002% commission + 2-pip slippage.

Output: .bt_cache/cross_asset_scan.json  {passing: [...], summary: [...]}
"""
import os, json, traceback
from math import floor
import numpy as np
import pandas as pd
import yfinance as yf

import sys
sys.path.insert(0, "/home/yapilwsl/arthityap/trend")
from scripts.bt.engine import Backtest
from scripts.bt.indicators import calculate_atr, donchian_channel, adx, rolling_efficiency_ratio
from scripts.bt.strategies import DonchianBreakout, DonchianBreakoutWithFilter, DonchianBreakoutWithER, KAMASlope
from scripts.bt.sizing import calculate_equal_volatility_size

# ---- Paths ----
ROOT = "/home/yapilwsl/arthityap/trend"
CACHE_DIR = os.path.join(ROOT, ".bt_cache")
OUT_PATH = os.path.join(CACHE_DIR, "cross_asset_scan.json")
os.makedirs(CACHE_DIR, exist_ok=True)

# ---- Parameters (as specified) ----
START = "2016-01-01"
END   = "2026-06-01"
CAPITAL    = 100_000.0
RISK_PCT   = 0.01          # Carver risk pct (strategies 1-6)
HALF_KILLY = 0.0391        # f*/2  (strategy 7: MA200 + Half-Kelly)
ATR_PERIOD = 14
ATR_MULT   = 3.0           # trailing stop width
COMMISSION = 0.00002       # 0.002% one-way
SLIPPAGE_PIPS = 2.0        # 2 pip slippage
PIP_VALUE_NONFX = 0.01     # meaningful "pip" size for indices/gold (not JPY)
MA_PERIOD  = 200
ADX_THRESHOLD = 25.0
ER_THRESHOLD  = 0.3
IS_YEARS = 3
OOS_YEARS = 1

MARKETS = {
    "SPY":   "SPY",
    "QQQ":   "QQQ",
    "^N225": "^N225",
    "GLD":   "GLD",
    "IEF":   "IEF",
    "GC=F":  "GC=F",
}

# Strategy metadata
STRATEGIES = [
    # name,            label,        trailing,  use_engine, risk_pct_override
    ("donchian10",     "Donchian10",  False,    True,       None),
    ("donchian20",     "Donchian20",  True,     False,    None),
    ("ma200",          "MA200",       True,     False,    None),
    ("kama10",         "KAMA10",      False,    True,       None),
    ("donchian20_adx", "Donchian20_ADX", False,  True,     None),
    ("donchian20_er",  "Donchian20_ER", False,  True,     None),
    ("ma200_hk",       "MA200_HK",    False,    False,    HALF_KILLY),
]


# ---- Data loader ----
def _load_df(ticker: str) -> pd.DataFrame:
    import glob as _glob
    files = _glob.glob(os.path.join(CACHE_DIR, f"{ticker}_*.csv"))
    if files:
        return pd.read_csv(files[0], index_col="Date", parse_dates=True).sort_index()
    df = yf.download(ticker, start=START, end=END, progress=False, auto_adjust=False)
    if df.empty:
        raise ValueError("No data for " + ticker)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.sort_index()[[c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]]


# ---- Signal functions: return prior-close-safe Series (sig[i] based on data through i-1).
#     No extra .shift(1) here — _trailing_backtest applies its own single .shift(1).
#     For engine.py strategies, the engine's native prev_signal=signals[i-1] provides
#     prior-close timing, so signals must NOT be pre-shifted.
# ----
def make_sig_flat(name: str, df: pd.DataFrame) -> pd.Series:
    """Signal-flat prior-close-safe signals for engine.py strategies.
    Engine.py uses prev_signal=signals[i-1] internally → prior-close timing.
    So sig[i] may use data up to bar i (engine shifts for timing)."""
    close = df["Close"]
    if name == "donchian10":
        return DonchianBreakout(period=10).signals(df)   # internally shift(1)
    elif name == "kama10":
        kama = calculate_kama(close, period=10, fast=2, slow=30)
        s = pd.Series(0.0, index=close.index)
        s[kama.diff() > 0] = 1.0; s[kama.diff() < 0] = -1.0
        return s
    elif name == "donchian20_adx":
        return DonchianBreakoutWithFilter(period=20, adx_threshold=ADX_THRESHOLD).signals(df)
    elif name == "donchian20_er":
        return DonchianBreakoutWithER(period=20, er_threshold=ER_THRESHOLD).signals(df)
    elif name == "ma200_hk":
        ma = close.rolling(MA_PERIOD).mean()
        s = pd.Series(0.0, index=close.index)
        s[close > ma] = 1.0
        return s
    raise ValueError(name)


def make_sig_trailing(name: str, df: pd.DataFrame) -> pd.Series:
    """Signal for trailing-stop custom backtest.
    Returns raw signals: sig[i] uses data through bar i.
    _trailing_backtest applies the single .shift(1) for prior-close timing (sig[i]→pos[i+1]).
    """
    close = df["Close"]
    if name == "donchian20":
        ch = donchian_channel(df, period=20)
        s = pd.Series(0.0, index=close.index)
        # Prior-close breakout: current close vs previous bar's channel boundary.
        # _trailing_backtest applies the single .shift(1) for prior-close timing.
        s[close > ch["upper"].shift(1)] = 1.0
        s[close < ch["lower"].shift(1)] = -1.0
        return s
    elif name == "ma200":
        ma = close.rolling(MA_PERIOD).mean()
        s = pd.Series(0.0, index=close.index)
        # Raw close vs MA; _trailing_backtest shifts once for prior-close timing.
        s[close > ma] = 1.0
        return s
    raise ValueError(name)


# ---- Custom trailing-stop backtest (prior-close, 3×ATR stop) ----
def _trailing_backtest(df: pd.DataFrame, sig: pd.Series, capital: float,
                       risk_pct: float, commission: float,
                       slippage_pips: float, pip_value: float,
                       contract_size: float = 1.0,
                       min_contracts: int = 1,
                       max_leverage: float = 2.0) -> dict:
    """Backtest with 3×ATR trailing stop. Prior-close timing: sig[i] → position at bar i+1."""
    close = df["Close"].copy()
    atr = calculate_atr(df, period=ATR_PERIOD)
    sig = sig.reindex(close.index).fillna(0.0)  # prior-close-safe; already shifted by make_sig_trailing

    equity = np.full(len(df), np.nan)
    cash = capital
    position = 0.0
    entry_price = 0.0
    atr_at_entry = 0.0
    stop_level = 0.0
    trades = []
    equity[0] = cash
    prev_sig = sig.iloc[0]  # initialize with first signal for comparison

    for i in range(1, len(df)):
        c = close.iloc[i]
        a = atr.iloc[i] if not np.isnan(atr.iloc[i]) else 0.0
        s = sig.iloc[i]
        prev_pos = position
        stop_triggered = False

        # --- 1. Check trailing stop first ---
        if position != 0.0 and a > 0:
            stop_width = ATR_MULT * a
            if position > 0 and c <= stop_level:
                stop_triggered = True
            elif position < 0 and c >= stop_level:
                stop_triggered = True

        if stop_triggered:
            exit_slip = slippage_pips * pip_value
            exit_price = (c - exit_slip) if position > 0 else (c + exit_slip)
            pnl = (exit_price - entry_price) * position
            commission_cost = abs(position) * exit_price * commission
            cash += pnl - commission_cost
            trades.append({
                "type": "STOP", "date": str(df.index[i].date()),
                "entry": entry_price, "exit": exit_price,
                "pnl": pnl - commission_cost, "size": position, "atr": a,
            })
            position = 0.0; entry_price = 0.0; atr_at_entry = 0.0; stop_level = 0.0

        # --- 1b. Dynamic leverage cap: close if notional > max_leverage * cash ---
        #     After a LEV exit, skip reopening if cash is too depleted to support
        #     even 1 contract at max_leverage (prevents infinite LEVERAGE loop).
        elif position != 0.0 and a > 0 and max_leverage > 0:
            notional = abs(position) * c
            if notional > max_leverage * cash:
                exit_slip = slippage_pips * pip_value
                exit_price = (c - exit_slip) if position > 0 else (c + exit_slip)
                pnl = (exit_price - entry_price) * position
                commission_cost = abs(position) * exit_price * commission
                cash += pnl - commission_cost
                trades.append({
                    "type": "LEVERAGE", "date": str(df.index[i].date()),
                    "entry": entry_price, "exit": exit_price,
                    "pnl": pnl - commission_cost, "size": position, "atr": a,
                })
                position = 0.0; entry_price = 0.0; atr_at_entry = 0.0; stop_level = 0.0
                # Guard: skip reopening if cash too depleted for 1 contract at max_leverage
                if cash <= 0 or (contract_size * c) / max_leverage > cash:
                    prev_sig = s
                    continue

        # --- 2. Signal change / flip (only if still in position) ---
        elif s != prev_sig and position != 0.0:
            exit_slip = slippage_pips * pip_value
            exit_price = (c - exit_slip) if position > 0 else (c + exit_slip)
            pnl = (exit_price - entry_price) * position
            commission_cost = abs(position) * exit_price * commission
            cash += pnl - commission_cost
            trades.append({
                "type": "EXIT", "date": str(df.index[i].date()),
                "entry": entry_price, "exit": exit_price,
                "pnl": pnl - commission_cost, "size": position, "atr": atr_at_entry,
            })
            position = 0.0; entry_price = 0.0; atr_at_entry = 0.0; stop_level = 0.0

            if s > 0 and a > 0:
                units = calculate_equal_volatility_size(cash, risk_pct, a)
                max_units = (2.0 * cash) / c
                units = min(units, max_units)
                units = max(floor(units / contract_size), min_contracts) * contract_size
                if units > 0:
                    position = units; entry_price = c + slippage_pips * pip_value
                    atr_at_entry = a
                    stop_level = entry_price - ATR_MULT * a
                    cash -= abs(position) * entry_price * commission
            elif s < 0 and a > 0:
                units = calculate_equal_volatility_size(cash, risk_pct, a)
                max_units = (2.0 * cash) / c
                units = min(units, max_units)
                units = max(floor(units / contract_size), min_contracts) * contract_size
                if units > 0:
                    position = -units; entry_price = c - slippage_pips * pip_value
                    atr_at_entry = a
                    stop_level = entry_price + ATR_MULT * a
                    cash -= abs(position) * entry_price * commission

        # --- 3. Open new position (flat → signal) ---
        elif position == 0.0 and s != 0.0 and a > 0:
            units = calculate_equal_volatility_size(cash, risk_pct, a)
            max_units = (2.0 * cash) / c
            units = min(units, max_units)
            units = max(floor(units / contract_size), min_contracts) * contract_size
            if units > 0:
                position = units if s > 0 else -units
                entry_price = (c + slippage_pips * pip_value) if s > 0 else (c - slippage_pips * pip_value)
                atr_at_entry = a
                stop_level = (entry_price - ATR_MULT * a) if s > 0 else (entry_price + ATR_MULT * a)
                cash -= abs(position) * entry_price * commission

        # --- Equity ---
        equity[i] = cash + (c - entry_price) * position if position != 0.0 else cash
        prev_sig = s  # update for next iteration

    # Force close at end
    if position != 0.0:
        c = close.iloc[-1]
        exit_slip = slippage_pips * pip_value
        exit_price = (c - exit_slip) if position > 0 else (c + exit_slip)
        pnl = (exit_price - entry_price) * position
        cash += pnl - abs(position) * exit_price * commission
        trades.append({
            "type": "EXIT", "date": str(df.index[-1].date()),
            "entry": entry_price, "exit": exit_price,
            "pnl": pnl - abs(position) * exit_price * commission,
            "size": position, "atr": atr_at_entry,
        })
        equity[-1] = cash

    equity = pd.Series(equity, index=df.index).ffill().fillna(capital)
    return _calc_metrics(equity, trades, df.index)


def _calc_metrics(equity: pd.Series, trades: list, index) -> dict:
    eq = equity.dropna()
    if len(eq) < 2:
        return {"cagr": 0.0, "sharpe": 0.0, "maxdd": 0.0, "trades": 0, "pf": 1.0, "final": CAPITAL}
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
    return {"cagr": cagr, "sharpe": sharpe, "maxdd": max_dd, "trades": len(trades), "pf": pf, "final": float(eq.iloc[-1])}


# ---- Walk-forward: engine.py strategies (signal-flat) ----
def run_wf_engine(ticker: str, name: str) -> dict:
    df = _load_df(ticker)
    # DonchianBreakout and filter variants internally apply shift(1) to the channel.
    # With signal_shift=0 the engine uses signals[i] directly → correct prior-close timing.
    # KAMA and MA200 do NOT internally shift → need signal_shift=1 for prior-close timing.
    shift_map = {
        "donchian10": 0, "kama10": 1,
        "donchian20_adx": 0, "donchian20_er": 0,
    }
    strat_map = {
        "donchian10": DonchianBreakout(period=10),
        "kama10": KAMASlope(period=10),
        "donchian20_adx": DonchianBreakoutWithFilter(period=20, adx_threshold=ADX_THRESHOLD),
        "donchian20_er": DonchianBreakoutWithER(period=20, er_threshold=ER_THRESHOLD),
    }
    inst = strat_map[name]
    sig_shift = shift_map[name]
    bt = Backtest(df, inst, capital=CAPITAL, risk_pct=RISK_PCT,
                  slippage_pips=SLIPPAGE_PIPS, commission_pct=COMMISSION, ticker=ticker,
                  signal_shift=sig_shift)
    bt.pip_value = PIP_VALUE_NONFX  # meaningful 2-pip slippage for indices/gold
    folds = bt.run_walk_forward(is_years=IS_YEARS, oos_years=OOS_YEARS)

    if not folds:
        return {"folds": [], "n_folds": 0, "avg_oos_sharpe": 0.0, "min_oos_sharpe": 0.0,
                "avg_oos_maxdd": 0.0, "is_sharpe": 0.0, "n_folds_passing": 0,
                "full_cagr": 0.0, "full_sharpe": 0.0, "full_maxdd": 0.0,
                "full_trades": 0, "full_pf": 1.0}

    oos_s = [f["oos_metrics"]["Sharpe"] for f in folds]
    oos_m = [f["oos_metrics"]["Max_Drawdown"] for f in folds]
    is_s = [f["is_metrics"]["Sharpe"] for f in folds]
    full = bt.run()["metrics"]
    # Normalize fold structure to match trailing format expected by main() loop
    normalized_folds = []
    for i, f in enumerate(folds):
        nf = {
            "fold": i + 1,
            "is_start": f["is_start"], "is_end": f["is_end"],
            "oos_start": f["oos_start"], "oos_end": f["oos_end"],
            "is": {"sharpe": float(f["is_metrics"]["Sharpe"]),
                    "maxdd": float(f["is_metrics"]["Max_Drawdown"])},
            "oos": {"sharpe": float(f["oos_metrics"]["Sharpe"]),
                     "maxdd": float(f["oos_metrics"]["Max_Drawdown"])},
        }
        normalized_folds.append(nf)
    folds = normalized_folds
    return {
        "folds": folds, "n_folds": len(folds),
        "avg_oos_sharpe": float(np.mean(oos_s)), "min_oos_sharpe": float(np.min(oos_s)),
        "avg_oos_maxdd": float(np.mean(oos_m)), "is_sharpe": float(is_s[0]),
        "n_folds_passing": int(sum(1 for s in oos_s if s >= 0.4)),
        "full_cagr": float(full["CAGR"]), "full_sharpe": float(full["Sharpe"]),
        "full_maxdd": float(full["Max_Drawdown"]), "full_trades": int(full["Total_Trades"]),
        "full_pf": float(full["Profit_Factor"]),
    }


# ---- Walk-forward: trailing-stop strategies (custom) ----
def run_wf_trailing(ticker: str, name: str, contract_size: float = 1.0,
                      min_contracts: int = 1, max_leverage: float = 2.0) -> dict:
    df = _load_df(ticker)
    dates = df.index
    start = dates[0]; end = dates[-1]
    folds = []; fold_num = 0
    is_end = start + pd.DateOffset(years=IS_YEARS)
    sig_func = lambda d: make_sig_trailing(name, d)

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
        pv = PIP_VALUE_NONFX
        is_res = _trailing_backtest(is_df, is_sig, CAPITAL, RISK_PCT, COMMISSION, SLIPPAGE_PIPS, pv, contract_size, min_contracts, max_leverage)
        oos_res = _trailing_backtest(oos_df, oos_sig, CAPITAL, RISK_PCT, COMMISSION, SLIPPAGE_PIPS, pv, contract_size, min_contracts, max_leverage)
        folds.append({
            "fold": fold_num + 1, "is_start": str(is_df.index[0].date()),
            "is_end": str(is_df.index[-1].date()),
            "oos_start": str(oos_df.index[0].date()), "oos_end": str(oos_df.index[-1].date()),
            "is": is_res, "oos": oos_res,
        })
        fold_num += 1; is_end = is_end + pd.DateOffset(years=OOS_YEARS)

    if not folds:
        return {"folds": [], "n_folds": 0, "avg_oos_sharpe": 0.0, "min_oos_sharpe": 0.0,
                "avg_oos_maxdd": 0.0, "is_sharpe": 0.0, "n_folds_passing": 0,
                "full_cagr": 0.0, "full_sharpe": 0.0, "full_maxdd": 0.0,
                "full_trades": 0, "full_pf": 1.0}

    oos_s = [f["oos"]["sharpe"] for f in folds]
    oos_m = [f["oos"]["maxdd"] for f in folds]
    is_s = [f["is"]["sharpe"] for f in folds]
    full = _trailing_backtest(df, sig_func(df), CAPITAL, RISK_PCT, COMMISSION, SLIPPAGE_PIPS, PIP_VALUE_NONFX, contract_size, min_contracts, max_leverage)
    return {
        "folds": folds, "n_folds": len(folds),
        "avg_oos_sharpe": float(np.mean(oos_s)), "min_oos_sharpe": float(np.min(oos_s)),
        "avg_oos_maxdd": float(np.mean(oos_m)), "is_sharpe": float(is_s[0]),
        "n_folds_passing": int(sum(1 for s in oos_s if s >= 0.4)),
        "full_cagr": full["cagr"], "full_sharpe": full["sharpe"],
        "full_maxdd": full["maxdd"], "full_trades": full["trades"], "full_pf": full["pf"],
    }


# ---- Walk-forward: MA200 + Half-Kelly (strategy 7) ----
def run_wf_hk(ticker: str, contract_size: float = 1.0,
                 min_contracts: int = 1, max_leverage: float = 2.0) -> dict:
    df = _load_df(ticker)
    dates = df.index
    start = dates[0]; end = dates[-1]
    folds = []; fold_num = 0
    is_end = start + pd.DateOffset(years=IS_YEARS)
    sig_func = lambda d: make_sig_trailing("ma200", d)

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
        pv = PIP_VALUE_NONFX
        is_res = _trailing_backtest(is_df, is_sig, CAPITAL, HALF_KILLY, COMMISSION, SLIPPAGE_PIPS, pv, contract_size, min_contracts, max_leverage)
        oos_res = _trailing_backtest(oos_df, oos_sig, CAPITAL, HALF_KILLY, COMMISSION, SLIPPAGE_PIPS, pv, contract_size, min_contracts, max_leverage)
        folds.append({
            "fold": fold_num + 1, "is_start": str(is_df.index[0].date()),
            "is_end": str(is_df.index[-1].date()),
            "oos_start": str(oos_df.index[0].date()), "oos_end": str(oos_df.index[-1].date()),
            "is": is_res, "oos": oos_res,
        })
        fold_num += 1; is_end = is_end + pd.DateOffset(years=OOS_YEARS)

    if not folds:
        return {"folds": [], "n_folds": 0, "avg_oos_sharpe": 0.0, "min_oos_sharpe": 0.0,
                "avg_oos_maxdd": 0.0, "is_sharpe": 0.0, "n_folds_passing": 0,
                "full_cagr": 0.0, "full_sharpe": 0.0, "full_maxdd": 0.0,
                "full_trades": 0, "full_pf": 1.0}

    oos_s = [f["oos"]["sharpe"] for f in folds]
    oos_m = [f["oos"]["maxdd"] for f in folds]
    is_s = [f["is"]["sharpe"] for f in folds]
    full = _trailing_backtest(df, sig_func(df), CAPITAL, HALF_KILLY, COMMISSION, SLIPPAGE_PIPS, PIP_VALUE_NONFX, contract_size, min_contracts, max_leverage)
    return {
        "folds": folds, "n_folds": len(folds),
        "avg_oos_sharpe": float(np.mean(oos_s)), "min_oos_sharpe": float(np.min(oos_s)),
        "avg_oos_maxdd": float(np.mean(oos_m)), "is_sharpe": float(is_s[0]),
        "n_folds_passing": int(sum(1 for s in oos_s if s >= 0.4)),
        "full_cagr": full["cagr"], "full_sharpe": full["sharpe"],
        "full_maxdd": full["maxdd"], "full_trades": full["trades"], "full_pf": full["pf"],
    }


# ---- Main ----
def main():
    all_results = []
    summary_rows = []

    for idx_name, ticker in MARKETS.items():
        print(f"\n{'='*70}\nFetching {idx_name} ({ticker})...")
        try:
            df = _load_df(ticker)
        except Exception as e:
            print(f"  ERROR fetching {ticker}: {e}")
            continue
        print(f"  rows={len(df)}  {df.index[0].date()}..{df.index[-1].date()}")

        for sname, slabel, is_trailing, use_engine, rp_override in STRATEGIES:
            print(f"  --- {slabel} ---", end=" ")
            try:
                risk_pct = rp_override if rp_override is not None else RISK_PCT

                if use_engine:
                    wf = run_wf_engine(ticker, sname)
                    full = {
                        "cagr": wf["full_cagr"], "sharpe": wf["full_sharpe"],
                        "maxdd": wf["full_maxdd"], "trades": wf["full_trades"],
                        "pf": wf["full_pf"],
                    }
                elif sname == "ma200_hk":
                    wf = run_wf_hk(ticker, contract_size=100.0 if ticker == "GC=F" else 1.0,
                                   min_contracts=1 if ticker == "GC=F" else 1,
                                   max_leverage=2.0)
                    full = {
                        "cagr": wf["full_cagr"], "sharpe": wf["full_sharpe"],
                        "maxdd": wf["full_maxdd"], "trades": wf["full_trades"],
                        "pf": wf["full_pf"],
                    }
                else:
                    wf = run_wf_trailing(ticker, sname,
                                         contract_size=100.0 if ticker == "GC=F" else 1.0,
                                         min_contracts=1 if ticker == "GC=F" else 1,
                                         max_leverage=2.0)
                    full = {
                        "cagr": wf["full_cagr"], "sharpe": wf["full_sharpe"],
                        "maxdd": wf["full_maxdd"], "trades": wf["full_trades"],
                        "pf": wf["full_pf"],
                    }

                oos_sa = wf["avg_oos_sharpe"]; oos_sm = wf["avg_oos_maxdd"]
                oos_sn = wf["min_oos_sharpe"]; is_s = wf["is_sharpe"]
                drop = is_s - oos_sa
                nfp = wf["n_folds_passing"]; nf = wf["n_folds"]
                min_pass = max(1, int(np.ceil(nf * 0.5)))
                passes = (
                    oos_sa >= 0.4 and oos_sm <= 0.50 and drop <= 0.30
                    and full["pf"] >= 1.5 and full["trades"] >= 30 and nfp >= min_pass
                )

                record = {
                    "market": idx_name, "ticker": ticker, "strategy": slabel,
                    "CAGR": round(full["cagr"] * 100, 2),
                    "Sharpe": round(full["sharpe"], 3),
                    "MaxDD": round(full["maxdd"] * 100, 2),
                    "Total_Trades": full["trades"],
                    "Profit_Factor": round(full["pf"], 3),
                    "OOS_Sharpe_avg": round(oos_sa, 3),
                    "OOS_Sharpe_min": round(oos_sn, 3),
                    "OOS_MaxDD": round(oos_sm * 100, 2),
                    "IS_Sharpe": round(is_s, 3),
                    "IS_OOS_Sharpe_drop": round(drop, 3),
                    "n_folds": nf,
                    "n_folds_passing_0.4": nfp,
                    "passes": passes,
                    "folds": [
                        {
                            "fold": f["fold"], "is_start": f["is_start"], "is_end": f["is_end"],
                            "oos_start": f["oos_start"], "oos_end": f["oos_end"],
                            "IS_sharpe": round(f["is"]["sharpe"], 3),
                            "OOS_sharpe": round(f["oos"]["sharpe"], 3),
                            "OOS_maxdd": round(f["oos"]["maxdd"] * 100, 2),
                        }
                        for f in wf["folds"]
                    ],
                }
                all_results.append(record)

                summary_rows.append({
                    "market": idx_name, "ticker": ticker, "strategy": slabel,
                    "CAGR": "%.1f%%" % (full["cagr"] * 100),
                    "Sharpe": "%.2f" % full["sharpe"],
                    "MaxDD": "%.1f%%" % (full["maxdd"] * 100),
                    "Trades": str(full["trades"]), "PF": "%.2f" % full["pf"],
                    "OOS_Sharpe_avg": "%.2f" % oos_sa, "OOS_Sharpe_min": "%.2f" % oos_sn,
                    "IS_OOS_drop": "%.2f" % drop,
                    "n_folds": nf, "n_pass": nfp, "passes": passes,
                })
                print("CAGR=%.1f%% Sharpe=%.2f MaxDD=%.1f%% Trades=%d PF=%.2f | OOS_Sharpe=%.2f min=%.2f drop=%.2f nPass=%d/%d passes=%s" % (
                    full["cagr"] * 100, full["sharpe"], full["maxdd"] * 100,
                    full["trades"], full["pf"], oos_sa, oos_sn, drop, nfp, nf, passes))
            except Exception as e:
                print(f"ERROR: {e}")
                traceback.print_exc()

    passing = [r for r in all_results if r["passes"]]
    output = {"passing": passing, "summary": all_results}
    with open(OUT_PATH, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nSaved {len(all_results)} results to {OUT_PATH}")
    print(f"Passing: {len(passing)} / {len(all_results)}")

    print("\n" + "=" * 140)
    print("CROSS-ASSET STRATEGY SCAN — SUMMARY")
    print("=" * 140)
    print("%-6s %-5s %-7s %6s %6s %7s %5s %5s %8s %8s %5s %5s %4s" % (
        "Market", "Ticker", "Strategy", "CAGR", "Sharpe", "MaxDD", "Trd", "PF", "OOS_Sharpe", "OOS_min", "nFld", "nPass", "?"))
    print("-" * 140)
    for r in summary_rows:
        print("%-6s %-5s %-7s %6s %6s %7s %5s %5s %8s %8s %5d %5d %4s" % (
            r["market"], r["ticker"], r["strategy"],
            r["CAGR"], r["Sharpe"], r["MaxDD"], r["Trades"], r["PF"],
            r["OOS_Sharpe_avg"], r["OOS_Sharpe_min"], r["n_folds"], r["n_pass"], "YES" if r["passes"] else "no"))
    print("=" * 140)
    if passing:
        print("\nPASSING COMBINATIONS:")
        for p in passing:
            print(f"  {p['market']} ({p['ticker']}) — {p['strategy']}: "
                  f"OOS_Sharpe={p['OOS_Sharpe_avg']:.2f}, MaxDD={p['OOS_MaxDD']:.1f}%, "
                  f"PF={p['Profit_Factor']:.2f}, Trades={p['Total_Trades']}, "
                  f"nPass={p['n_folds_passing_0.4']}/{p['n_folds']}")
    else:
        print("\nNo combinations passed all filters.")


if __name__ == "__main__":
    main()
