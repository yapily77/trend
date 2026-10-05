"""
Sizing Sensitivity Scan: All 8 sizing methods x 2 markets x 3 strategies
Walk-forward: 3y expanding IS / 1y OOS, prior-close signal timing
Cost: 0.002% commission + 2 pip slippage
"""
import sys, os, json, warnings, time, inspect
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np
import pandas as pd
from scripts.bt.engine import Backtest
from scripts.bt.sizing import calculate_equal_volatility_size
from scripts.bt.indicators import calculate_atr
from scripts.bt.strategies import DonchianBreakout, KAMASlope
from scripts.bt.ma200 import MA200Crossover

# ── Data Loading ──────────────────────────────────────────────────────
START_DATE = "2000-08-30"

gj = pd.read_csv(".bt_cache/gold_jpy_daily_1971.csv", index_col=0, parse_dates=True)
gj = gj[gj.index >= START_DATE].sort_index()
for c in ["Open","High","Low","Close"]:
    gj[c] = pd.to_numeric(gj[c], errors="coerce")
gj = gj.dropna()

usd = pd.read_csv(".bt_cache/USDJPY=X_20000831_20260529.csv", index_col=0, parse_dates=True)
usd = usd[usd.index >= START_DATE].sort_index()
for c in ["Open","High","Low","Close"]:
    usd[c] = pd.to_numeric(usd[c], errors="coerce")
usd = usd.dropna()

MARKETS = {"Gold_JPY": gj, "USDJPY_X": usd}

# ── Strategy Factories ────────────────────────────────────────────────
STRATEGIES = {
    "Donchian20": lambda: DonchianBreakout(period=20),
    "MA200":      lambda: MA200Crossover(period=200),
    "KAMA10":     lambda: KAMASlope(period=10, fast=2, slow=30),
}

# ── 8 Sizing Methods ──────────────────────────────────────────────────
SIZING_METHODS = {
    "HK":   {"risk_pct": 0.0391,  "label": "Half-Kelly"},
    "QK":   {"risk_pct": 0.01953, "label": "Quarter-Kelly"},
    "EV5":  {"risk_pct": 0.05,    "label": "Equal-Vol 5%"},
    "EV10": {"risk_pct": 0.10,    "label": "Equal-Vol 10%"},
    "EV15": {"risk_pct": 0.15,    "label": "Equal-Vol 15%"},
    "F1":   {"risk_pct": 0.01,    "label": "Fixed 1%"},
    "HK2x": {"risk_pct": 0.0391,  "label": "Half-Kelly 2xLevCap", "leverage_cap": 2.0},
    "F2":   {"risk_pct": 0.02,    "label": "Fixed 2%"},
}

CAPITAL = 100_000
COMMISSION_PCT = 0.00002
SLIPPAGE_PIPS = 2.0
IS_YEARS = 3
OOS_YEARS = 1

# ── Leverage-Cap Backtest (overrides run() to cap position notional) ──
class LeverageCapBacktest(Backtest):
    """Backtest that caps position notional at leverage_cap * cash."""
    def __init__(self, df, strategy_instance, capital=100000, risk_pct=0.01,
                 slippage_pips=2.0, commission_pct=0.00002, ticker="USDJPY=X",
                 leverage_cap=None):
        super().__init__(df, strategy_instance, capital=capital, risk_pct=risk_pct,
                         slippage_pips=slippage_pips, commission_pct=commission_pct,
                         ticker=ticker)
        self.leverage_cap = leverage_cap

    def run(self, start_date=None, end_date=None):
        df = self.df.copy()
        if start_date is not None:
            df = df[df.index >= pd.to_datetime(start_date)]
        if end_date is not None:
            df = df[df.index <= pd.to_datetime(end_date)]
        if len(df) == 0:
            return self._empty_results()

        df['Signal'] = self.strategy.signals(df)
        df['ATR_14'] = calculate_atr(df, period=14)

        equity = np.zeros(len(df))
        cash = self.initial_capital
        position = 0.0
        entry_price = 0.0
        equity[0] = cash
        trades = []
        current_trade = None

        close_prices = df['Close'].values
        signals = df['Signal'].values
        atrs = df['ATR_14'].values
        dates = df.index
        lc = self.leverage_cap
        sv = self.slippage_pips * self.pip_value
        cv = self.commission_pct

        for i in range(len(df)):
            if i == 0:
                equity[i] = cash
                continue
            current_close = close_prices[i]
            prev_signal = signals[i-1]
            current_signal = signals[i]
            atr = atrs[i]
            if current_signal != prev_signal:
                if position != 0.0:
                    exit_slippage = sv
                    exit_price = current_close - exit_slippage if position > 0 else current_close + exit_slippage
                    pnl = (exit_price - entry_price) * position
                    commission = abs(position) * exit_price * cv
                    cash += pnl - commission
                    if current_trade:
                        current_trade['exit_date'] = dates[i]
                        current_trade['exit_price'] = exit_price
                        current_trade['pnl'] = pnl - commission
                        trades.append(current_trade)
                        current_trade = None
                    position = 0.0
                if current_signal != 0:
                    base_size = calculate_equal_volatility_size(cash, self.risk_pct, atr)
                    size_mult = abs(current_signal) if abs(current_signal) <= 1.0 else 1.0
                    position_size_units = base_size * max(size_mult, 0.25)
                    if lc is not None:
                        entry_price_for_cap = current_close + sv if current_signal > 0 else current_close - sv
                        if entry_price_for_cap > 0:
                            max_units = lc * cash / entry_price_for_cap
                            position_size_units = min(position_size_units, max_units)
                    if position_size_units > 0:
                        entry_slippage = sv
                        if current_signal > 0:
                            position = position_size_units
                            entry_price = current_close + entry_slippage
                        else:
                            position = -position_size_units
                            entry_price = current_close - entry_slippage
                        commission = abs(position) * entry_price * cv
                        cash -= commission
                        current_trade = {
                            'entry_date': dates[i],
                            'type': 'LONG' if current_signal > 0 else 'SHORT',
                            'entry_price': entry_price,
                            'size': position
                        }
            if position != 0.0:
                equity[i] = cash + (current_close - entry_price) * position
            else:
                equity[i] = cash

        if position != 0.0 and len(df) > 0:
            last_idx = len(df) - 1
            exit_price = close_prices[last_idx]
            pnl = (exit_price - entry_price) * position
            commission = abs(position) * exit_price * cv
            cash += pnl - commission
            if current_trade:
                current_trade['exit_date'] = dates[last_idx]
                current_trade['exit_price'] = exit_price
                current_trade['pnl'] = pnl - commission
                trades.append(current_trade)
            equity[last_idx] = cash

        df['Equity'] = equity
        df['Daily_Return'] = df['Equity'].pct_change().fillna(0.0)
        return self._calculate_metrics(df, trades)

# ── Backtest runner (chooses normal or leverage-cap variant) ───────────
def _make_backtest(df, strategy, ticker, risk_pct, leverage_cap=None):
    if leverage_cap is not None:
        return LeverageCapBacktest(df, strategy, capital=CAPITAL, risk_pct=risk_pct,
                                    slippage_pips=SLIPPAGE_PIPS,
                                    commission_pct=COMMISSION_PCT, ticker=ticker,
                                    leverage_cap=leverage_cap)
    return Backtest(df, strategy, capital=CAPITAL, risk_pct=risk_pct,
                    slippage_pips=SLIPPAGE_PIPS, commission_pct=COMMISSION_PCT,
                    ticker=ticker)

# ── Walk-forward runner ───────────────────────────────────────────────
def run_walk_forward(df, strategy, ticker, risk_pct, leverage_cap=None):
    start_date = df.index[0]
    end_date = df.index[-1]
    is_sharpes = []
    oos_sharpes = []
    oos_sharpe_min = np.inf
    n_folds_passing_04 = 0
    n_folds_total = 0
    current_is_end = start_date + pd.DateOffset(years=IS_YEARS)

    while current_is_end < end_date:
        current_oos_end = current_is_end + pd.DateOffset(years=OOS_YEARS)
        if current_oos_end > end_date:
            current_oos_end = end_date
        n_folds_total += 1

        # IS
        is_df = df.loc[:current_is_end]
        res_is = _make_backtest(is_df, strategy, ticker, risk_pct, leverage_cap).run()
        if res_is and "metrics" in res_is:
            is_sharpes.append(res_is["metrics"]["Sharpe"])

        # OOS
        oos_df = df.loc[current_is_end:current_oos_end]
        if len(oos_df) < 20:
            current_is_end = current_is_end + pd.DateOffset(years=1)
            continue
        res_oos = _make_backtest(oos_df, strategy, ticker, risk_pct, leverage_cap).run()
        if res_oos and "metrics" in res_oos:
            s = res_oos["metrics"]["Sharpe"]
            oos_sharpes.append(s)
            if s < oos_sharpe_min:
                oos_sharpe_min = s
            if s >= 0.4:
                n_folds_passing_04 += 1

        current_is_end = current_is_end + pd.DateOffset(years=1)

    if not oos_sharpes:
        return None
    avg_oos = float(np.mean(oos_sharpes))
    pct_passing = n_folds_passing_04 / n_folds_total if n_folds_total > 0 else 0.0
    return {
        "avg_oos_sharpe": avg_oos,
        "min_oos_sharpe": float(np.min(oos_sharpes)),
        "n_folds_passing_04": n_folds_passing_04,
        "n_folds_total": n_folds_total,
        "pct_passing": pct_passing,
        "is_sharpes": is_sharpes,
        "oos_sharpes": oos_sharpes,
    }

# ── Full-sample metrics ───────────────────────────────────────────────
def compute_full_metrics(df, strategy, ticker, risk_pct, leverage_cap=None):
    bt = _make_backtest(df, strategy, ticker, risk_pct, leverage_cap)
    res = bt.run()
    if res is None or "metrics" not in res:
        return None
    m = res["metrics"]
    return {
        "cagr": m["CAGR"],
        "sharpe": m["Sharpe"],
        "maxdd": m["Max_Drawdown"],
        "profit_factor": m["Profit_Factor"],
        "total_trades": m["Total_Trades"],
    }

# ── Filtering ─────────────────────────────────────────────────────────
def passes_filter(full_metrics, wf_metrics):
    if full_metrics is None or wf_metrics is None:
        return False
    if wf_metrics["avg_oos_sharpe"] < 0.4:
        return False
    if full_metrics["maxdd"] > 0.50:
        return False
    if wf_metrics["is_sharpes"] and wf_metrics["oos_sharpes"]:
        if float(np.mean(wf_metrics["is_sharpes"])) - wf_metrics["avg_oos_sharpe"] > 0.30:
            return False
    if full_metrics["profit_factor"] < 1.5:
        return False
    if full_metrics["total_trades"] < 30:
        return False
    if wf_metrics["pct_passing"] < 0.50:
        return False
    return True

def _fail_reason(full_metrics, wf_metrics):
    reasons = []
    if wf_metrics["avg_oos_sharpe"] < 0.4: reasons.append("oos_sharpe<0.4")
    if full_metrics["maxdd"] > 0.50: reasons.append("maxdd>0.50")
    if wf_metrics["is_sharpes"] and wf_metrics["oos_sharpes"]:
        if float(np.mean(wf_metrics["is_sharpes"])) - wf_metrics["avg_oos_sharpe"] > 0.30:
            reasons.append("sharpe_drop>0.30")
    if full_metrics["profit_factor"] < 1.5: reasons.append("pf<1.5")
    if full_metrics["total_trades"] < 30: reasons.append("trades<30")
    if wf_metrics["pct_passing"] < 0.50: reasons.append("pct_passing<0.50")
    return "; ".join(reasons) if reasons else "unknown"

# ── Main scan ─────────────────────────────────────────────────────────
def run_scan():
    all_results = []
    summary = []
    total = len(MARKETS) * len(STRATEGIES) * len(SIZING_METHODS)
    idx = 0
    t0 = time.time()

    for mkt_name, df in MARKETS.items():
        for strat_name, strat_fn in STRATEGIES.items():
            strategy = strat_fn()
            for meth_code, meth in SIZING_METHODS.items():
                idx += 1
                risk_pct = meth["risk_pct"]
                lc = meth.get("leverage_cap")
                ticker = "GOLDJPY" if mkt_name == "Gold_JPY" else "USDJPY=X"
                label = meth["label"]
                print(f"[{idx}/{total}] {mkt_name}|{strat_name}|{label}", flush=True)

                fm = compute_full_metrics(df, strategy, ticker, risk_pct, lc)
                wm = run_walk_forward(df, strategy, ticker, risk_pct, lc)

                is_avg = float(np.mean(wm["is_sharpes"])) if wm and wm["is_sharpes"] else None
                drop = (is_avg - wm["avg_oos_sharpe"]) if (is_avg is not None and wm) else None

                result = {
                    "market": mkt_name,
                    "strategy": strat_name,
                    "sizing_method": label,
                    "sizing_code": meth_code,
                    "risk_pct": risk_pct,
                    "leverage_cap": lc,
                    "cagr": round(fm["cagr"], 6) if fm else None,
                    "sharpe": round(fm["sharpe"], 4) if fm else None,
                    "maxdd": round(fm["maxdd"], 4) if fm else None,
                    "profit_factor": round(fm["profit_factor"], 4) if fm else None,
                    "total_trades": fm["total_trades"] if fm else None,
                    "oos_sharpe_avg": round(wm["avg_oos_sharpe"], 4) if wm else None,
                    "oos_sharpe_min": round(wm["min_oos_sharpe"], 4) if wm else None,
                    "n_folds_passing_04": wm["n_folds_passing_04"] if wm else None,
                    "n_folds_total": wm["n_folds_total"] if wm else None,
                    "pct_passing": round(wm["pct_passing"], 4) if wm else None,
                    "avg_is_sharpe": round(is_avg, 4) if is_avg is not None else None,
                    "is_oos_sharpe_drop": round(drop, 4) if drop is not None else None,
                }
                result["passes"] = passes_filter(fm, wm)
                all_results.append(result)

                summary.append({
                    "market": mkt_name,
                    "strategy": strat_name,
                    "sizing_method": label,
                    "sizing_code": meth_code,
                    "passes": result["passes"],
                    "fail_reason": _fail_reason(fm, wm) if not result["passes"] else None,
                    "oos_sharpe_avg": result["oos_sharpe_avg"],
                    "maxdd": result["maxdd"],
                    "profit_factor": result["profit_factor"],
                    "total_trades": result["total_trades"],
                    "n_folds_passing_04": result["n_folds_passing_04"],
                    "n_folds_total": result["n_folds_total"],
                })

    elapsed = time.time() - t0
    print(f"\nScan complete: {total} combos in {elapsed:.1f}s")

    passing = [r for r in all_results if r["passes"]]
    # Clean passing: only keep required fields
    keep = {"market","strategy","sizing_method","sizing_code","risk_pct","leverage_cap",
            "cagr","sharpe","maxdd","profit_factor","total_trades",
            "oos_sharpe_avg","oos_sharpe_min","n_folds_passing_04","n_folds_total",
            "pct_passing","avg_is_sharpe","is_oos_sharpe_drop"}
    passing_clean = [{k: v for k, v in r.items() if k in keep} for r in passing]

    # Clean summary
    summary_clean = []
    for s in summary:
        s_clean = {k: v for k, v in s.items() if k not in ("passes",)}
        summary_clean.append(s_clean)

    return {"passing": passing_clean, "summary": summary_clean}

if __name__ == "__main__":
    results = run_scan()
    out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "scripts", "bt", "sizing_scan_results.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nPassing combos: {len(results['passing'])}")
    print(f"Total combos tested: {len(results['summary'])}")
    print(json.dumps(results, indent=2)[:5000])
