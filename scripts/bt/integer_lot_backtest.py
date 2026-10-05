"""INTEGER-LOT backtest for synthetic Gold/JPY on SGX.

Synthetic construction:
    gold_JPY = gold_USD × USDJPY   (JPY per troy ounce)
    Long gold/JPY = Long SGX gold futures (100 oz, USD-denominated)
                    + Long USD/JPY futures (USD 100,000 notional, JPY-quoted)
                    to neutralise the USD leg.

Derivation (product rule on gold_JPY = gold_USD × USDJPY):
    d(gold_JPY) = d(gold_USD) × USDJPY + gold_USD × d(USDJPY)

    Per N_G gold contracts (100 oz each):
      Gold USD-P&L  = N_G × 100 × d(gold_USD)
      FX JPY-P&L    = N_F × 100,000 × d(USDJPY)

    To cancel the d(USDJPY) term and replicate gold_JPY exposure exactly:
      N_F = N_G × 100 × gold_USD / 100,000        (hedge ratio, locked at entry)

    Synthetic JPY P&L = N_G × 100 × d(gold_JPY)    ✓  (ideal gold/JPY)

Integer-lot problem:
    - Gold: indivisible in 100-oz increments → N_G ∈ ℕ
    - USD/JPY: indivisible in USD 100k increments → N_F ∈ ℕ₀
    - Hedge ratio 100×gold_USD/100,000 is almost never integer → residual
      USD/JPY basis risk (small; accepted as cost of discrete lots)

Sizing formula (half-Kelly, ATR-based stop):
    capital_JPY     = capital_USD × USDJPY
    risk_JPY        = half_kelly × capital_JPY
    stop_JPY_per_oz = ATR_MULT × ATR(14) on gold_JPY
    risk_per_GC     = stop_JPY_per_oz × 100 oz
    N_G (raw)       = risk_JPY / risk_per_GC
    N_G (integer)   = max(1, round(N_G_raw))
    N_F (integer)   = max(0, round(N_G × 100 × gold_USD / 100,000))
    actual_risk     = N_G × risk_per_GC

Minimum capital for 1 lot (stop binds at half-Kelly):
    capital_min = (1 × stop_JPY_per_oz × 100) / (half_kelly × USDJPY)
    At current prices (gold_JPY≈¥726k, ATR≈¥10.4k, USDJPY≈159):
        capital_min ≈ ¥40M ≈ $250k
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np
import pandas as pd
from scripts.data.fred import build_gold, build_jpy_usd
from scripts.bt.reporting import export_trade_log
from scripts.bt.charts import plot_equity_curve
import json

# ── strategy constants ───────────────────────────────────────
HALF_KELLY   = 0.0781     # 7.81% target risk per trade
CAPITAL_USD  = 100_000.0  # base capital (USD)
ATR_PERIOD   = 14
ATR_MULT     = 3.0
MAX_LEVERAGE = 2.0         # total notional (gold + FX hedge) ≤ MAX_LEVERAGE × equity
COMMISSION   = 0.00002     # 2bp on notional (one-way)

# Contract specs (SGX / COMEX)
OZ_PER_GC      = 100       # troy oz per gold futures contract
USD_PER_UY     = 100_000  # USD notional per USD/JPY futures contract

# Lot-sizing modes
MODE_CONTINUOUS = 'continuous'
MODE_INTEGER_OZ = 'integer_oz'
MODE_SGX_LOTS   = 'sgx_lots'


# ═══════════════════════════════════════════════════════════
#  Integer-lot sizing functions
# ═══════════════════════════════════════════════════════════
def size_synthetic_gold_jpy_sgx(
    equity_JPY: float,
    gold_usd: float,
    usdjpy: float,
    atr_jpy_per_oz: float,
    half_kelly: float = HALF_KELLY,
    atr_mult: float = ATR_MULT,
    max_leverage: float = MAX_LEVERAGE,
) -> dict:
    """Compute integer SGX-lot sizing for a synthetic long gold/JPY position.

    Sizing uses RUNNING equity_JPY (not fixed capital) so risk scales
    with the portfolio — proper fractional-Kelly money management.

    Returns dict with N_G, N_F, risk figures, leverage, basis residual,
    and min_capital_for_1lot.
    """
    if atr_jpy_per_oz <= 0 or gold_usd <= 0 or usdjpy <= 0:
        raise ValueError("atr_jpy_per_oz, gold_usd, and usdjpy must be positive")

    cap_jpy = equity_JPY
    risk_JPY = half_kelly * cap_jpy
    stop_JPY_per_oz = atr_mult * atr_jpy_per_oz
    risk_per_GC = stop_JPY_per_oz * OZ_PER_GC          # JPY risk per 100-oz contract

    N_G_raw = risk_JPY / risk_per_GC                    # half-Kelly implied

    # Leverage cap (exact): total notional (gold + FX hedge) <= max_leverage * equity
    #   gold_notional = N_G * OZ_PER_GC * gold_usd * usdjpy
    #   fx_notional   ≈ N_G * OZ_PER_GC * gold_usd * usdjpy  (hedge ratio ≈ OZ_PER_GC*gold_USD/USD_PER_UY)
    #   total_notional ≈ 2 * N_G * OZ_PER_GC * gold_usd * usdjpy
    #   => N_G <= max_leverage * equity / (2 * OZ_PER_GC * gold_usd * usdjpy)
    total_notional_per_GC = 2.0 * OZ_PER_GC * gold_usd * usdjpy
    N_G_leverage = max(0, int(max_leverage * cap_jpy / total_notional_per_GC)) if total_notional_per_GC > 0 else 0
    N_G = min(N_G_raw, N_G_leverage)                    # respect BOTH constraints
    # Allow N_G=1 if (a) stop binds within half-Kelly AND (b) leverage OK
    if N_G == 0 and N_G_raw >= 1:
        # Check if 1 lot satisfies leverage
        one_lot_notional = 2.0 * OZ_PER_GC * gold_usd * usdjpy
        if one_lot_notional <= max_leverage * cap_jpy:
            N_G = 1
    if N_G < 1:
        N_G = 0                                        # cannot afford any lot

    hedge_ratio_exact = OZ_PER_GC * gold_usd / USD_PER_UY # ideal UY per GC
    N_F_exact = N_G * hedge_ratio_exact
    N_F = max(0, int(round(N_F_exact)))                 # integer USD/JPY contracts

    actual_risk_JPY = N_G * risk_per_GC
    actual_risk_pct = actual_risk_JPY / cap_jpy if cap_jpy > 0 else 0.0

    gold_notional_JPY = N_G * OZ_PER_GC * gold_usd * usdjpy
    fx_notional_JPY   = N_F * USD_PER_UY * usdjpy
    notional_JPY = gold_notional_JPY + fx_notional_JPY
    notional_USD = notional_JPY / usdjpy
    leverage = notional_JPY / cap_jpy if cap_jpy > 0 else 0.0

    # Residual USD exposure from rounding N_F (basis risk)
    ideal_fx_notional_USD = N_G * OZ_PER_GC * gold_usd
    basis_residual_USD = ideal_fx_notional_USD - N_F * USD_PER_UY

    # Minimum capital for which N_G = 1 satisfies half-Kelly (stop binds)
    min_capital_for_1lot = risk_per_GC / (half_kelly * usdjpy)

    return {
        'N_G': N_G,
        'N_F': N_F,
        'risk_JPY': risk_JPY,
        'stop_JPY_per_oz': stop_JPY_per_oz,
        'risk_per_GC': risk_per_GC,
        'actual_risk_JPY': actual_risk_JPY,
        'actual_risk_pct': actual_risk_pct,
        'notional_JPY': notional_JPY,
        'notional_USD': notional_USD,
        'leverage': leverage,
        'hedge_ratio_exact': hedge_ratio_exact,
        'basis_residual_USD': basis_residual_USD,
        'min_capital_for_1lot': min_capital_for_1lot,
    }


def size_integer_oz(
    equity_JPY: float,
    gold_jpy: float,
    atr_jpy_per_oz: float,
    half_kelly: float = HALF_KELLY,
    atr_mult: float = ATR_MULT,
    max_leverage: float = MAX_LEVERAGE,
    lot_size_oz: float = 1.0,
) -> dict:
    """Integer-oz sizing (IBKR USGOLD style, single leg, no FX hedge).

    Trades gold_JPY directly in integer-ounce increments.
    No USD/JPY hedge — residual FX exposure is accepted because
    gold_JPY already embeds the USDJPY rate.
    Uses running equity_JPY for proper fractional-Kelly sizing.
    """
    if atr_jpy_per_oz <= 0 or gold_jpy <= 0:
        raise ValueError("atr_jpy_per_oz and gold_jpy must be positive")

    risk_JPY = half_kelly * equity_JPY          # proportional to running equity
    stop_JPY_per_oz = atr_mult * atr_jpy_per_oz
    risk_per_lot = stop_JPY_per_oz * lot_size_oz

    raw_lots = risk_JPY / risk_per_lot if risk_per_lot > 0 else 0.0
    N_lots = max(1, int(round(raw_lots)))
    actual_risk_JPY = N_lots * risk_per_lot
    actual_risk_pct = actual_risk_JPY / risk_JPY if risk_JPY > 0 else 0.0

    notional_JPY = N_lots * lot_size_oz * gold_jpy
    # Approximate USD notional using implied USDJPY from the gold_JPY price
    usdjpy_implied = gold_jpy / (gold_jpy / 1.0)   # placeholder
    notional_USD = notional_JPY / usdjpy_implied if usdjpy_implied else 0.0

    return {
        'N_lots': N_lots,
        'lot_size_oz': lot_size_oz,
        'actual_risk_JPY': actual_risk_JPY,
        'actual_risk_pct': actual_risk_pct,
        'notional_JPY': notional_JPY,
        'notional_USD': notional_USD,
        'stop_JPY_per_oz': stop_JPY_per_oz,
    }


# ═══════════════════════════════════════════════════════════
#  Integer-lot backtest engine
# ═══════════════════════════════════════════════════════════
def run_integer_lot_backtest(
    gold_df: pd.DataFrame,
    usdjpy_series: pd.Series,
    capital_usd: float = CAPITAL_USD,
    half_kelly: float = HALF_KELLY,
    atr_period: int = ATR_PERIOD,
    atr_mult: float = ATR_MULT,
    max_leverage: float = MAX_LEVERAGE,
    mode: str = MODE_SGX_LOTS,
    lot_size_oz: float = 1.0,
    commission: float = COMMISSION,
) -> dict:
    """Run MA200 + half-Kelly + ATR-stop backtest with integer-lot sizing.

    All internal bookkeeping is in JPY. Equity is returned in USD.

    Parameters
    ----------
    gold_df : pd.DataFrame
        Columns: Open, High, Low, Close (gold_JPY, JPY per troy ounce).
    usdjpy_series : pd.Series
        Daily USDJPY (JPY per USD), aligned to gold_df index.
    mode : str
        'continuous' | 'integer_oz' | 'sgx_lots'.
    lot_size_oz : float
        Minimum lot size in troy oz (integer_oz mode only).

    Returns
    -------
    dict: metrics, equity_usd, trades, sizing_info, mode, signal.
    """
    close = gold_df['Close']
    ma = close.rolling(200).mean()
    sig = pd.Series(0.0, index=gold_df.index)
    sig[close > ma] = 1.0
    pos = sig.shift(1).fillna(0.0)
    atr_series = _atr(gold_df, atr_period)
    usdjpy = usdjpy_series.reindex(gold_df.index).ffill().bfill()

    n = len(gold_df)
    equity_usd = np.zeros(n)
    trades = []
    sizing_info = []

    # ── state (all JPY-denominated unless noted) ──
    cash_JPY = CAPITAL_USD * usdjpy.iloc[0]   # initial capital in JPY (running equity)
    N_G = 0                  # gold 100-oz contracts held
    N_F = 0                  # USD/JPY contracts held
    entry_price_JPY = 0.0    # gold_JPY per oz at entry (weighted)
    entry_USDJPY = 0.0       # USDJPY at entry (for cash conversion & hedge lock)
    active = False
    current_trade = None

    for i in range(n):
        c = close.iloc[i]                # gold_JPY per oz, current bar
        u = usdjpy.iloc[i]               # USDJPY, current bar
        atr_val = atr_series.iloc[i] if pd.notna(atr_series.iloc[i]) else atr_series.dropna().iloc[0]

        # ── EXIT: ATR stop on existing position ──
        if active and current_trade:
            stop_JPY = entry_price_JPY - atr_mult * atr_val   # stop in gold_JPY/oz
            if c <= stop_JPY:
                pnl_JPY = (c - entry_price_JPY) * OZ_PER_GC * N_G
                exit_USD = c / u
                pnl_USD = pnl_JPY / u
                comm_JPY = commission * abs(pnl_JPY / pnl_USD) * u
                cash_JPY += pnl_JPY - comm_JPY
                equity_usd[i] = cash_JPY / u
                trades.append({
                    'entry_date': current_trade['entry_date'],
                    'exit_date': gold_df.index[i],
                    'type': 'LONG',
                    'entry_price': current_trade['entry_price'],
                    'exit_price': c,
                    'size': N_G,
                    'N_F': N_F,
                    'pnl_JPY': pnl_JPY,
                    'pnl_USD': pnl_USD,
                    'exit_reason': 'STOP_LOSS',
                })
                active = False
                current_trade = None
                N_G = 0; N_F = 0
                cash_JPY = equity_usd[i] * u   # reset cash to realised equity (JPY)
                continue

        # ── ENTRY: MA200 signal goes long ──
        if not active:
            now_long = pos.iloc[i] > 0
            was_long = pos.iloc[i-1] > 0 if i > 0 else False
            if now_long and not was_long:
                entry_gold_USD = c / u * 1.0005      # 5bp slippage on entry
                entry_USDJPY = u
                entry_price_JPY = entry_gold_USD * entry_USDJPY

                # ── Integer-lot sizing (RUNNING equity_JPY, not fixed capital) ──
                if mode == MODE_SGX_LOTS:
                    sz = size_synthetic_gold_jpy_sgx(
                        cash_JPY, entry_gold_USD, entry_USDJPY,
                        atr_val, half_kelly, atr_mult, max_leverage)
                    N_G = sz['N_G']
                    N_F = sz['N_F']
                    actual_risk_pct = sz['actual_risk_pct']
                    notional_USD = sz['notional_USD']
                    leverage = sz['leverage']
                elif mode == MODE_INTEGER_OZ:
                    sz = size_integer_oz(
                        cash_JPY, c, atr_val,
                        half_kelly, atr_mult, max_leverage, lot_size_oz)
                    N_lots = sz['N_lots']
                    N_G = max(1, int(N_lots * lot_size_oz / OZ_PER_GC))
                    N_G = max(1, N_G)
                    N_F = 0   # no hedge in single-leg mode
                    actual_risk_pct = sz['actual_risk_pct']
                    notional_USD = sz['notional_USD']
                    leverage = max_leverage
                else:  # continuous
                    cap_JPY = cash_JPY              # RUNNING equity in JPY
                    risk_JPY = half_kelly * cap_JPY
                    N_G = max(1.0, risk_JPY / (atr_mult * atr_val * OZ_PER_GC))
                    N_F = N_G * OZ_PER_GC * entry_gold_USD / USD_PER_UY
                    actual_risk_pct = half_kelly
                    notional_USD = N_G * OZ_PER_GC * entry_gold_USD
                    leverage = notional_USD / (cash_JPY / entry_USDJPY) if cash_JPY > 0 else 0

                entry_notional_USD = N_G * OZ_PER_GC * entry_gold_USD + N_F * USD_PER_UY
                cash_JPY -= commission * entry_notional_USD * entry_USDJPY

                current_N_G = N_G
                current_N_F = N_F
                active = True
                current_trade = {
                    'entry_date': gold_df.index[i],
                    'type': 'LONG',
                    'entry_price': c,
                    'size': N_G,
                    'N_F': N_F,
                    'mode': mode,
                    'actual_risk_pct': actual_risk_pct,
                    'notional_USD': notional_USD,
                    'leverage': leverage,
                }
                sizing_info.append({
                    'entry_date': gold_df.index[i],
                    'gold_USD': entry_gold_USD,
                    'USDJPY': entry_USDJPY,
                    'gold_JPY': entry_price_JPY,
                    'N_G': N_G,
                    'N_F': N_F,
                    'atr': atr_val,
                    'stop_JPY_per_oz': atr_mult * atr_val,
                    'actual_risk_pct': actual_risk_pct,
                    'notional_USD': notional_USD,
                    'leverage': leverage,
                })
                continue

        # ── EXIT: MA200 signal going flat ──
        if active and current_trade:
            now_long = pos.iloc[i] > 0
            if not now_long:
                exit_gold_JPY = c * 0.9995
                pnl_JPY = (exit_gold_JPY - entry_price_JPY) * OZ_PER_GC * N_G
                exit_USD = exit_gold_JPY / u
                pnl_USD = pnl_JPY / u
                comm_JPY = commission * abs(pnl_JPY / pnl_USD) * u
                cash_JPY += pnl_JPY - comm_JPY
                equity_usd[i] = cash_JPY / u
                trades.append({
                    'entry_date': current_trade['entry_date'],
                    'exit_date': gold_df.index[i],
                    'type': 'LONG',
                    'entry_price': current_trade['entry_price'],
                    'exit_price': c,
                    'size': N_G,
                    'N_F': N_F,
                    'pnl_JPY': pnl_JPY,
                    'pnl_USD': pnl_USD,
                    'exit_reason': 'SIGNAL_EXIT',
                })
                active = False
                current_trade = None
                N_G = 0; N_F = 0
                cash_JPY = equity_usd[i] * u
                continue

        # ── Equity update (JPY → USD) ──
        if active:
            unrealized_JPY = (c - entry_price_JPY) * OZ_PER_GC * N_G
            fx_pnl_JPY = N_F * USD_PER_UY * (u - entry_USDJPY)
            equity_JPY = cash_JPY + unrealized_JPY + fx_pnl_JPY
            equity_usd[i] = equity_JPY / u
        else:
            equity_usd[i] = cash_JPY / u

    # Force close at end
    if active and current_trade:
        c = close.iloc[-1]
        u = usdjpy.iloc[-1]
        exit_gold_JPY = c * 0.9995
        pnl_JPY = (exit_gold_JPY - entry_price_JPY) * OZ_PER_GC * N_G
        exit_USD = exit_gold_JPY / u
        pnl_USD = pnl_JPY / u
        comm_JPY = commission * abs(pnl_JPY / pnl_USD) * u
        cash_JPY += pnl_JPY - comm_JPY
        equity_usd[-1] = cash_JPY / u
        trades.append({
            'entry_date': current_trade['entry_date'],
            'exit_date': gold_df.index[-1],
            'type': 'LONG',
            'entry_price': current_trade['entry_price'],
            'exit_price': c,
            'size': N_G,
            'N_F': N_F,
            'pnl_JPY': pnl_JPY,
            'pnl_USD': pnl_USD,
            'exit_reason': 'END_OF_DATA',
        })

    df = gold_df.copy()
    df['Equity_USD'] = equity_usd
    df['Daily_Return'] = df['Equity_USD'].pct_change().fillna(0.0)
    metrics = _metrics(df, trades, capital_usd, atr_period, atr_mult, max_leverage, mode)

    return {
        'metrics': metrics,
        'equity_usd': equity_usd,
        'trades': trades,
        'sizing_info': sizing_info,
        'mode': mode,
        'signal': sig,
    }


def _atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    """True Range and rolling average on gold_JPY."""
    d = df.copy()
    d['tr0'] = d['High'] - d['Low']
    d['tr1'] = abs(d['High'] - d['Close'].shift())
    d['tr2'] = abs(d['Low'] - d['Close'].shift())
    d['TR'] = d[['tr0', 'tr1', 'tr2']].max(axis=1)
    return d['TR'].rolling(period).mean()


def _metrics(df: pd.DataFrame, trades: list, capital_usd: float,
             atr_period: int, atr_mult: float, max_leverage: float,
             mode: str) -> dict:
    equity = df['Equity_USD']
    daily = df['Daily_Return']
    roll_max = equity.cummax()
    dd = (equity - roll_max) / roll_max
    max_dd = abs(float(dd.min())) if len(dd) > 0 else 0.0
    days = (equity.index[-1] - equity.index[0]).days / 365.25
    final = equity.iloc[-1]
    cagr = ((final / capital_usd) ** (1 / days) - 1) if (days > 0 and final > 0 and capital_usd > 0) else 0
    mean_d = daily.mean(); std_d = daily.std()
    sharpe = (mean_d / std_d) * np.sqrt(252) if std_d > 0 else 0

    pnls = [t.get('pnl_USD', 0) for t in trades]
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = abs(sum(p for p in pnls if p < 0))
    pf = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 1.0)
    wins = [p for p in pnls if p > 0]; losses = [p for p in pnls if p < 0]
    avg_win = np.mean(wins) if wins else 0
    avg_loss = abs(np.mean(losses)) if losses else 0
    stops = sum(1 for t in trades if t.get('exit_reason') == 'STOP_LOSS')
    signal_exits = sum(1 for t in trades if t.get('exit_reason') == 'SIGNAL_EXIT')
    end_exits = sum(1 for t in trades if t.get('exit_reason') == 'END_OF_DATA')
    total_notional = sum(t.get('size', 0) * OZ_PER_GC for t in trades)

    return {
        'CAGR': cagr, 'Max_Drawdown': max_dd, 'Sharpe': sharpe,
        'Profit_Factor': pf, 'Final_Value': final, 'Total_Trades': len(trades),
        'Win_Rate': len(wins) / len(trades) if trades else 0,
        'Avg_Win': avg_win, 'Avg_Loss': avg_loss, 'Payoff_Ratio': avg_win/avg_loss if avg_loss else 0,
        'Stop_Loss_Hits': stops, 'Signal_Exits': signal_exits, 'End_Exits': end_exits,
        'ATR_Period': atr_period, 'ATR_Mult': atr_mult, 'Max_Leverage': max_leverage,
        'Mode': mode,
        'Avg_Trade_Size_GC': total_notional / len(trades) if trades else 0,
    }


def run_mode_comparison(
    gold_df: pd.DataFrame,
    usdjpy_series: pd.Series,
    capital_usd: float = CAPITAL_USD,
    half_kelly: float = HALF_KELLY,
    atr_period: int = ATR_PERIOD,
    atr_mult: float = ATR_MULT,
    max_leverage: float = MAX_LEVERAGE,
) -> dict:
    """Run all three sizing modes and compare.

    Returns dict: {mode: result, 'comparison': {...}}.
    """
    results = {}
    for m in [MODE_CONTINUOUS, MODE_INTEGER_OZ, MODE_SGX_LOTS]:
        r = run_integer_lot_backtest(
            gold_df, usdjpy_series, capital_usd, half_kelly,
            atr_period, atr_mult, max_leverage, mode=m)
        results[m] = r
        m_ = r['metrics']
        print(f"  {m:>14s}: CAGR={m_['CAGR']:+.2%} | Sharpe={m_['Sharpe']:+.2f} | "
              f"MaxDD={m_['Max_Drawdown']:.2%} | Trades={m_['Total_Trades']} | "
              f"PF={m_['Profit_Factor']:.2f} | Final=${m_['Final_Value']:,.0f}")

    cont = results[MODE_CONTINUOUS]['metrics']
    sgx  = results[MODE_SGX_LOTS]['metrics']
    ioz  = results[MODE_INTEGER_OZ]['metrics']
    comparison = {
        'CAGR_drag_sgx_vs_cont': sgx['CAGR'] - cont['CAGR'],
        'CAGR_drag_ioz_vs_cont': ioz['CAGR'] - cont['CAGR'],
        'Sharpe_drag_sgx_vs_cont': sgx['Sharpe'] - cont['Sharpe'],
        'Sharpe_drag_ioz_vs_cont': ioz['Sharpe'] - cont['Sharpe'],
        'DD_increase_sgx': sgx['Max_Drawdown'] - cont['Max_Drawdown'],
        'DD_increase_ioz': ioz['Max_Drawdown'] - cont['Max_Drawdown'],
    }
    return {'results': results, 'comparison': comparison}


# ═══════════════════════════════════════════════════════════
#  Minimum-capital analysis
# ═══════════════════════════════════════════════════════════
def min_capital_report(
    gold_df: pd.DataFrame,
    usdjpy_series: pd.Series,
    atr_period: int = ATR_PERIOD,
    atr_mult: float = ATR_MULT,
    half_kelly: float = HALF_KELLY,
) -> dict:
    """Report minimum capital for 1-lot synthetic across history."""
    atr_series = _atr(gold_df, atr_period)
    usdjpy = usdjpy_series.reindex(gold_df.index).ffill().bfill()
    rows = []
    for i in range(len(gold_df)):
        c = gold_df['Close'].iloc[i]
        u = usdjpy.iloc[i]
        atr = atr_series.iloc[i] if pd.notna(atr_series.iloc[i]) else atr_series.dropna().iloc[0]
        gold_USD = c / u
        sz = size_synthetic_gold_jpy_sgx(
            1.0, gold_USD, u, atr, half_kelly, atr_mult, MAX_LEVERAGE)
        rows.append({
            'date': str(gold_df.index[i].date()),
            'gold_USD': round(gold_USD, 2),
            'USDJPY': round(u, 4),
            'gold_JPY': round(c, 0),
            'atr_JPY': round(atr, 0),
            'stop_JPY_per_oz': round(sz['stop_JPY_per_oz'], 0),
            'N_G': sz['N_G'],
            'N_F': sz['N_F'],
            'min_capital_USD': round(sz['min_capital_for_1lot'], 0),
            'actual_risk_pct': round(sz['actual_risk_pct'], 4),
            'leverage': round(sz['leverage'], 3),
            'hedge_ratio_exact': round(sz['hedge_ratio_exact'], 3),
            'basis_residual_USD': round(sz['basis_residual_USD'], 0),
        })
    df = pd.DataFrame(rows)
    latest = df.iloc[-1]
    print(f"\n=== Minimum capital for 1-lot synthetic gold/JPY (SGX) ===")
    print(f"  Latest ({df['date'].iloc[-1]}):")
    print(f"    gold_USD = ${latest['gold_USD']:,.2f}  USDJPY = {latest['USDJPY']:.2f}")
    print(f"    gold_JPY = ¥{latest['gold_JPY']:,.0f}/oz")
    print(f"    ATR(14)  = ¥{latest['atr_JPY']:,.0f}/oz")
    print(f"    3×ATR stop = ¥{latest['stop_JPY_per_oz']:,.0f}/oz")
    print(f"    Hedge ratio (ideal UY per GC) = {latest['hedge_ratio_exact']:.3f}")
    print(f"    Min capital for N_G=1 at half-Kelly = ${latest['min_capital_USD']:,.0f}")
    for cap in [50_000, 100_000, 250_000, 500_000]:
        row = df[df['min_capital_USD'] <= cap].iloc[-1] if any(df['min_capital_USD'] <= cap) else df.iloc[-1]
        print(f"    At ${cap:>6,}:  min_cap=${row['min_capital_USD']:,.0f}  "
              f"actual_risk={row['actual_risk_pct']*100:.1f}%  leverage={row['leverage']:.2f}x")
    return {'df': df, 'latest': latest.to_dict()}


# ═══════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════
if __name__ == '__main__':
    _ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    OUT  = os.path.join(_ROOT, 'GOLD', 'reports')
    CHARTS = os.path.join(_ROOT, 'GOLD', 'charts')
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(CHARTS, exist_ok=True)

    # ── Load data ──
    gold_jpy = pd.read_csv(os.path.join('.bt_cache', 'gold_jpy_daily_1971.csv'),
                           index_col=0, parse_dates=True).sort_index()
    usdjpy = pd.read_csv(os.path.join('.bt_cache', 'USDJPY_19710101_20260530.csv'),
                         index_col=0, parse_dates=True).sort_index()['USDJPY']
    gold_jpy = gold_jpy.loc['1971-01-04':'2026-05-29']

    print(f"Data: {gold_jpy.shape[0]} bars, "
          f"{gold_jpy.index[0].date()} → {gold_jpy.index[-1].date()}")
    print(f"  gold_JPY: ¥{gold_jpy['Close'].iloc[0]:,.0f} → ¥{gold_jpy['Close'].iloc[-1]:,.0f}")

    # ── Minimum capital report ──
    mc = min_capital_report(gold_jpy, usdjpy)

    # ── Mode comparison at $100K (base capital) ──
    print(f"\n=== Mode comparison: ${CAPITAL_USD:,.0f} capital ===")
    comp = run_mode_comparison(
        gold_jpy, usdjpy, CAPITAL_USD, HALF_KELLY, ATR_PERIOD, ATR_MULT, MAX_LEVERAGE)

    # ── SGX-lots backtest at $100K ──
    print(f"\n=== SGX-lots backtest (${CAPITAL_USD:,.0f}) ===")
    r_sgx = run_integer_lot_backtest(
        gold_jpy, usdjpy, CAPITAL_USD, HALF_KELLY, ATR_PERIOD, ATR_MULT, MAX_LEVERAGE,
        mode=MODE_SGX_LOTS)
    ms = r_sgx['metrics']
    print(f"  CAGR={ms['CAGR']:+.2%}  Sharpe={ms['Sharpe']:+.2f}  MaxDD={ms['Max_Drawdown']:.2%}")
    print(f"  Trades={ms['Total_Trades']}  WinRate={ms['Win_Rate']:.1%}  PF={ms['Profit_Factor']:.2f}")
    print(f"  Final=${ms['Final_Value']:,.0f}")

    # ── SGX-lots backtest at $250K and $500K ──
    for cap in [250_000.0, 500_000.0]:
        print(f"\n=== SGX-lots backtest (${cap:,.0f}) ===")
        r = run_integer_lot_backtest(
            gold_jpy, usdjpy, cap, HALF_KELLY, ATR_PERIOD, ATR_MULT, MAX_LEVERAGE,
            mode=MODE_SGX_LOTS)
        m = r['metrics']
        print(f"  CAGR={m['CAGR']:+.2%}  Sharpe={m['Sharpe']:+.2f}  MaxDD={m['Max_Drawdown']:.2%}")
        print(f"  Trades={m['Total_Trades']}  Final=${m['Final_Value']:,.0f}")
        if r['sizing_info']:
            s0 = r['sizing_info'][0]
            print(f"  First trade: N_G={s0['N_G']} N_F={s0['N_F']} "
                  f"risk={s0['actual_risk_pct']*100:.2f}% lev={s0['leverage']:.2f}x")

    # ── Save outputs ──
    with open(os.path.join(OUT, 'integer_lot_comparison.json'), 'w') as f:
        json.dump(comp, f, default=str, indent=2)

    with open(os.path.join(OUT, 'sgx_lot_backtest_results.json'), 'w') as f:
        json.dump(r_sgx, f, default=str, indent=2)

    export_trade_log(r_sgx['trades'], os.path.join(OUT, 'sgx_lot_trades.csv'))

    eq = pd.Series(r_sgx['equity_usd'], index=gold_jpy.index)
    plot_equity_curve(eq, 'XAU/JPY (SGX lots)', 'MA200 Half-Kelly + 3×ATR — Integer Lots',
                      os.path.join(CHARTS, 'integer_lot_equity.png'))

    print(f"\nSaved to GOLD/reports/ and GOLD/charts/")
