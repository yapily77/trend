"""Gold/JPY decomposition backtest: split gold_jpy into gold_usd + USD/JPY legs.

Core idea:
    gold_jpy = gold_usd × USDJPY
    Δlog(gold_jpy) ≈ Δlog(gold_usd) + Δlog(USDJPY)

Instead of one undifferentiated gold_jpy position, size each leg independently
and dynamically reallocate between them based on trend strength and correlation
regime.

Three strategies compared:
    1. static_50_50   — fixed 50/50 allocation between the two legs
    2. trend_weighted — dynamic allocation weighted by each leg's trend strength
    3. core_plus_overlay — gold_jpy core + USD/JPY hedge overlay
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np
import pandas as pd
from scripts.data.fred import build_gold, build_jpy_usd
from scripts.bt.indicators import calculate_atr
from scripts.bt.reporting import export_trade_log
from scripts.bt.charts import plot_equity_curve
import json

# ── constants ──────────────────────────────────────────────────────────────
HALF_KELLY = 0.0781
CAPITAL = 100_000.0
ATR_PERIOD = 14
ATR_MULT = 3.0
MAX_LEVERAGE = 2.0
COMMISSION = 0.00002

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'GOLD', 'reports')
CHARTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'GOLD', 'charts')
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.bt_cache')


# ═══════════════════════════════════════════════════════════════════════════
#  Data preparation
# ═══════════════════════════════════════════════════════════════════════════

def build_components() -> pd.DataFrame:
    cached = os.path.join(CACHE_DIR, 'gold_components_daily.csv')
    if os.path.exists(cached):
        df = pd.read_csv(cached, index_col=0, parse_dates=True)
        return df.sort_index()

    gj = pd.read_csv(os.path.join(CACHE_DIR, 'gold_jpy_daily_1971.csv'), index_col=0, parse_dates=True)
    gold_usd_raw = build_gold(start='1971-01-01', end='2026-05-30')
    usdjpy_df = build_jpy_usd(start='1971-01-01', end='2026-05-30')

    df = pd.DataFrame(index=gj.index)
    df['gold_jpy'] = gj['Close']
    df['usdjpy'] = usdjpy_df['USDJPY']
    df['gold_usd'] = gold_usd_raw['GOLD']

    pre = df.index < pd.Timestamp('2000-08-30')
    df.loc[pre, 'gold_usd'] = df.loc[pre, 'gold_jpy'] / df.loc[pre, 'usdjpy']

    df = df.dropna().sort_index()
    df.to_csv(cached)
    return df


def _atr_for(close):
    """Compute ATR from a close series (OHLC = close for pre-2000)."""
    ohlc = pd.DataFrame({'Open': close, 'High': close, 'Low': close, 'Close': close})
    return calculate_atr(ohlc, period=ATR_PERIOD)


def _make_signals(close, ma_period=200):
    ma = close.rolling(ma_period).mean()
    sig = pd.Series(0.0, index=close.index)
    sig[close > ma] = 1.0
    return sig.shift(1).fillna(0.0)


def _cap_position(position, entry_price, current_equity, max_leverage):
    max_notional = max_leverage * current_equity
    return min(position, max_notional / entry_price) if entry_price > 0 else position


def _metrics(df, trades, capital):
    equity = df['Equity']
    daily = df['Daily_Return']
    roll_max = equity.cummax()
    dd = (equity - roll_max) / roll_max
    max_dd = abs(dd.min())
    days = (equity.index[-1] - equity.index[0]).days / 365.25
    final = equity.iloc[-1]
    cagr = ((final / capital) ** (1 / days) - 1) if days > 0 and final > 0 and capital > 0 else 0
    mean = daily.mean(); std = daily.std()
    sharpe = (mean / std) * np.sqrt(252) if std > 0 else 0
    pnls = [t.get('pnl', 0) for t in trades]
    gp = sum(p for p in pnls if p > 0); gl = abs(sum(p for p in pnls if p < 0))
    pf = gp / gl if gl > 0 else (gp if gp > 0 else 1.0)
    wins = [p for p in pnls if p > 0]; losses = [p for p in pnls if p < 0]
    avg_win = np.mean(wins) if wins else 0
    avg_loss = abs(np.mean(losses)) if losses else 0
    return {
        'CAGR': cagr, 'Max_Drawdown': max_dd, 'Sharpe': sharpe,
        'Profit_Factor': pf, 'Final_Value': final, 'Total_Trades': len(trades),
        'Win_Rate': len(wins) / len(trades) if trades else 0,
        'Avg_Win': avg_win, 'Avg_Loss': avg_loss,
        'Payoff_Ratio': avg_win / avg_loss if avg_loss else 0,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Strategy 1: STATIC SPLIT (50/50)


# ═══════════════════════════════════════════════════════════════════════════
#  Strategy 1: STATIC SPLIT (50/50)
# ═══════════════════════════════════════════════════════════════════════════

def run_static_split(df, split_ratio=0.5):
    """Split risk budget 50/50 between gold_usd and USD/JPY legs.

    Each leg gets half the risk dollars, sized independently with its own
    ATR-based stop and MA200 signal.
    """
    gold_usd = df['gold_usd']; usdjpy = df['usdjpy']
    g_sig = _make_signals(gold_usd); f_sig = _make_signals(usdjpy)
    g_atr = _atr_for(gold_usd); f_atr = _atr_for(usdjpy)
    g_atr = g_atr.fillna(g_atr.dropna().iloc[0]) if len(g_atr.dropna()) > 0 else g_atr
    f_atr = f_atr.fillna(f_atr.dropna().iloc[0]) if len(f_atr.dropna()) > 0 else f_atr

    equity = np.zeros(len(gold_usd)); cash = CAPITAL
    g_sh = 0.0; g_ep = 0.0; f_sh = 0.0; f_ep = 0.0
    trades = []

    for i in range(len(gold_usd)):
        c_g = gold_usd.iloc[i]; c_f = usdjpy.iloc[i]
        g_atr_v = g_atr.iloc[i] if pd.notna(g_atr.iloc[i]) else g_atr.dropna().iloc[0]
        f_atr_v = f_atr.iloc[i] if pd.notna(f_atr.iloc[i]) else f_atr.dropna().iloc[0]
        g_now = g_sig.iloc[i] > 0; f_now = f_sig.iloc[i] > 0
        g_was = (g_sig.iloc[i-1] > 0) if i > 0 else False
        f_was = (f_sig.iloc[i-1] > 0) if i > 0 else False

        # EXIT gold (ATR stop)
        if g_sh > 0 and c_g <= g_ep - ATR_MULT * g_atr_v:
            pnl = (c_g - g_ep) * g_sh; comm = abs(g_sh) * c_g * COMMISSION
            cash += pnl - comm
            trades.append({'entry_date': gold_usd.index[i], 'exit_date': gold_usd.index[i],
                           'type': 'GOLD_EXIT', 'entry_price': g_ep, 'exit_price': c_g,
                           'size': g_sh, 'pnl': pnl - comm, 'exit_reason': 'STOP_LOSS', 'ticker': 'GOLD/USD'})
            g_sh = 0.0; g_ep = 0.0
        # EXIT gold (signal)
        if g_sh > 0 and not g_now and g_was:
            pnl = (c_g * 0.9995 - g_ep) * g_sh; comm = abs(g_sh) * c_g * 0.9995 * COMMISSION
            cash += pnl - comm
            trades.append({'entry_date': gold_usd.index[i], 'exit_date': gold_usd.index[i],
                           'type': 'GOLD_EXIT', 'entry_price': g_ep, 'exit_price': c_g * 0.9995,
                           'size': g_sh, 'pnl': pnl - comm, 'exit_reason': 'SIGNAL_EXIT', 'ticker': 'GOLD/USD'})
            g_sh = 0.0; g_ep = 0.0
        # EXIT fx (ATR stop)
        if f_sh > 0 and c_f <= f_ep - ATR_MULT * f_atr_v:
            pnl = (c_f - f_ep) * f_sh; comm = abs(f_sh) * c_f * COMMISSION
            cash += pnl - comm
            trades.append({'entry_date': usdjpy.index[i], 'exit_date': usdjpy.index[i],
                           'type': 'FX_EXIT', 'entry_price': f_ep, 'exit_price': c_f,
                           'size': f_sh, 'pnl': pnl - comm, 'exit_reason': 'STOP_LOSS', 'ticker': 'USD/JPY'})
            f_sh = 0.0; f_ep = 0.0
        # EXIT fx (signal)
        if f_sh > 0 and not f_now and f_was:
            pnl = (c_f * 0.9995 - f_ep) * f_sh; comm = abs(f_sh) * c_f * 0.9995 * COMMISSION
            cash += pnl - comm
            trades.append({'entry_date': usdjpy.index[i], 'exit_date': usdjpy.index[i],
                           'type': 'FX_EXIT', 'entry_price': f_ep, 'exit_price': c_f * 0.9995,
                           'size': f_sh, 'pnl': pnl - comm, 'exit_reason': 'SIGNAL_EXIT', 'ticker': 'USD/JPY'})
            f_sh = 0.0; f_ep = 0.0

        # ENTRY gold
        if g_sh == 0.0 and g_now and not g_was:
            raw = (HALF_KELLY * cash * split_ratio) / (ATR_MULT * g_atr_v) if g_atr_v > 0 else 0
            g_sh = _cap_position(raw, c_g, cash, MAX_LEVERAGE)
            g_ep = c_g * 1.0005
            trades.append({'entry_date': gold_usd.index[i], 'type': 'GOLD_ENTRY',
                           'entry_price': g_ep, 'size': g_sh, 'notional': g_sh * g_ep,
                           'exit_reason': 'ENTRY', 'ticker': 'GOLD/USD'})
            cash -= g_sh * g_ep * COMMISSION
        # ENTRY fx
        if f_sh == 0.0 and f_now and not f_was:
            raw = (HALF_KELLY * cash * (1 - split_ratio)) / (ATR_MULT * f_atr_v) if f_atr_v > 0 else 0
            f_sh = _cap_position(raw, c_f, cash, MAX_LEVERAGE)
            f_ep = c_f * 1.0005
            trades.append({'entry_date': usdjpy.index[i], 'type': 'FX_ENTRY',
                           'entry_price': f_ep, 'size': f_sh, 'notional': f_sh * f_ep,
                           'exit_reason': 'ENTRY', 'ticker': 'USD/JPY'})
            cash -= f_sh * f_ep * COMMISSION

        g_pnl = (c_g - g_ep) * g_sh if g_sh > 0 else 0.0
        f_pnl = (c_f - f_ep) * f_sh if f_sh > 0 else 0.0
        equity[i] = cash + g_pnl + f_pnl

    # Force close
    for tk, sh, ep, cs in [('GOLD/USD', g_sh, g_ep, gold_usd), ('USD/JPY', f_sh, f_ep, usdjpy)]:
        if sh > 0:
            c = cs.iloc[-1]; pnl = (c * 0.9995 - ep) * sh; comm = abs(sh) * c * 0.9995 * COMMISSION
            cash += pnl - comm
            trades.append({'entry_date': cs.index[-1], 'exit_date': cs.index[-1],
                           'type': tk + '_EXIT', 'entry_price': ep, 'exit_price': c * 0.9995,
                           'size': sh, 'pnl': pnl - comm, 'exit_reason': 'END_OF_DATA', 'ticker': tk})

    df_out = pd.DataFrame(index=gold_usd.index)
    df_out['Close'] = gold_usd; df_out['Equity'] = equity
    df_out['Daily_Return'] = df_out['Equity'].pct_change().fillna(0.0)
    return {'metrics': _metrics(df_out, trades, CAPITAL), 'equity': df_out['Equity'],
            'trades': trades, 'signal': g_sig}


# ═══════════════════════════════════════════════════════════════════════════
#  Strategy 2: TREND-WEIGHTED DYNAMIC SPLIT
# ═══════════════════════════════════════════════════════════════════════════

def run_trend_weighted_split(df):
    """Dynamic allocation: weight each leg by its trend strength.

    Trend strength = |price / MA(50) - 1|, smoothed over 20 days.
    Leg with stronger trend gets more risk budget.
    """
    gold_usd = df['gold_usd']; usdjpy = df['usdjpy']
    g_strength = (gold_usd / gold_usd.rolling(50).mean() - 1).abs().rolling(20).mean().fillna(0)
    f_strength = (usdjpy / usdjpy.rolling(50).mean() - 1).abs().rolling(20).mean().fillna(0)
    total = g_strength + f_strength
    g_weight = pd.Series(np.where(total > 0, g_strength / total, 0.5), index=gold_usd.index)

    g_sig = _make_signals(gold_usd); f_sig = _make_signals(usdjpy)
    g_atr = _atr_for(gold_usd).fillna(_atr_for(gold_usd).dropna().iloc[0])
    f_atr = _atr_for(usdjpy).fillna(_atr_for(usdjpy).dropna().iloc[0])

    equity = np.zeros(len(gold_usd)); cash = CAPITAL
    g_sh = 0.0; g_ep = 0.0; f_sh = 0.0; f_ep = 0.0
    trades = []

    for i in range(len(gold_usd)):
        c_g = gold_usd.iloc[i]; c_f = usdjpy.iloc[i]
        g_atr_v = g_atr.iloc[i] if pd.notna(g_atr.iloc[i]) else g_atr.dropna().iloc[0]
        f_atr_v = f_atr.iloc[i] if pd.notna(f_atr.iloc[i]) else f_atr.dropna().iloc[0]
        g_now = g_sig.iloc[i] > 0; f_now = f_sig.iloc[i] > 0
        g_was = (g_sig.iloc[i-1] > 0) if i > 0 else False
        f_was = (f_sig.iloc[i-1] > 0) if i > 0 else False

        w_g = float(g_weight.iloc[i]) if not pd.isna(g_weight.iloc[i]) else 0.5
        w_f = 1 - w_g

        # EXIT gold
        if g_sh > 0 and (c_g <= g_ep - ATR_MULT * g_atr_v or (not g_now and g_was)):
            reason = 'STOP_LOSS' if c_g <= g_ep - ATR_MULT * g_atr_v else 'SIGNAL_EXIT'
            pnl = (c_g - g_ep) * g_sh if reason == 'STOP_LOSS' else (c_g * 0.9995 - g_ep) * g_sh
            comm = abs(g_sh) * (c_g if reason == 'STOP_LOSS' else c_g * 0.9995) * COMMISSION
            cash += pnl - comm
            trades.append({'entry_date': gold_usd.index[i], 'exit_date': gold_usd.index[i],
                           'type': 'GOLD_EXIT', 'entry_price': g_ep,
                           'exit_price': c_g if reason == 'STOP_LOSS' else c_g * 0.9995,
                           'size': g_sh, 'pnl': pnl - comm, 'exit_reason': reason, 'ticker': 'GOLD/USD'})
            g_sh = 0.0; g_ep = 0.0
        # EXIT fx
        if f_sh > 0 and (c_f <= f_ep - ATR_MULT * f_atr_v or (not f_now and f_was)):
            reason = 'STOP_LOSS' if c_f <= f_ep - ATR_MULT * f_atr_v else 'SIGNAL_EXIT'
            pnl = (c_f - f_ep) * f_sh if reason == 'STOP_LOSS' else (c_f * 0.9995 - f_ep) * f_sh
            comm = abs(f_sh) * (c_f if reason == 'STOP_LOSS' else c_f * 0.9995) * COMMISSION
            cash += pnl - comm
            trades.append({'entry_date': usdjpy.index[i], 'exit_date': usdjpy.index[i],
                           'type': 'FX_EXIT', 'entry_price': f_ep,
                           'exit_price': c_f if reason == 'STOP_LOSS' else c_f * 0.9995,
                           'size': f_sh, 'pnl': pnl - comm, 'exit_reason': reason, 'ticker': 'USD/JPY'})
            f_sh = 0.0; f_ep = 0.0

        # ENTRY gold
        if g_sh == 0.0 and g_now and not g_was:
            raw = (HALF_KELLY * cash * w_g) / (ATR_MULT * g_atr_v) if g_atr_v > 0 else 0
            g_sh = _cap_position(raw, c_g, cash, MAX_LEVERAGE)
            g_ep = c_g * 1.0005
            trades.append({'entry_date': gold_usd.index[i], 'type': 'GOLD_ENTRY',
                           'entry_price': g_ep, 'size': g_sh, 'notional': g_sh * g_ep,
                           'exit_reason': 'ENTRY', 'ticker': 'GOLD/USD'})
            cash -= g_sh * g_ep * COMMISSION
        # ENTRY fx
        if f_sh == 0.0 and f_now and not f_was:
            raw = (HALF_KELLY * cash * w_f) / (ATR_MULT * f_atr_v) if f_atr_v > 0 else 0
            f_sh = _cap_position(raw, c_f, cash, MAX_LEVERAGE)
            f_ep = c_f * 1.0005
            trades.append({'entry_date': usdjpy.index[i], 'type': 'FX_ENTRY',
                           'entry_price': f_ep, 'size': f_sh, 'notional': f_sh * f_ep,
                           'exit_reason': 'ENTRY', 'ticker': 'USD/JPY'})
            cash -= f_sh * f_ep * COMMISSION

        g_pnl = (c_g - g_ep) * g_sh if g_sh > 0 else 0.0
        f_pnl = (c_f - f_ep) * f_sh if f_sh > 0 else 0.0
        equity[i] = cash + g_pnl + f_pnl

    for tk, sh, ep, cs in [('GOLD/USD', g_sh, g_ep, gold_usd), ('USD/JPY', f_sh, f_ep, usdjpy)]:
        if sh > 0:
            c = cs.iloc[-1]; pnl = (c * 0.9995 - ep) * sh; comm = abs(sh) * c * 0.9995 * COMMISSION
            cash += pnl - comm
            trades.append({'entry_date': cs.index[-1], 'exit_date': cs.index[-1],
                           'type': tk + '_EXIT', 'entry_price': ep, 'exit_price': c * 0.9995,
                           'size': sh, 'pnl': pnl - comm, 'exit_reason': 'END_OF_DATA', 'ticker': tk})

    df_out = pd.DataFrame(index=gold_usd.index)
    df_out['Close'] = gold_usd; df_out['Equity'] = equity
    df_out['Daily_Return'] = df_out['Equity'].pct_change().fillna(0.0)
    return {'metrics': _metrics(df_out, trades, CAPITAL), 'equity': df_out['Equity'],
            'trades': trades, 'signal': g_sig}


# ═══════════════════════════════════════════════════════════════════════════
#  Strategy 3: GOLD_JPY CORE + USD/JPY HEDGE OVERLAY
# ═══════════════════════════════════════════════════════════════════════════

def run_core_plus_overlay(df, hedge_ratio=0.3):
    """Gold_jpy core at Half-Kelly + USD/JPY overlay sized by hedge_ratio × core notional."""
    gold_jpy = df['gold_jpy']; usdjpy = df['usdjpy']
    gj_sig = _make_signals(gold_jpy); fx_sig = _make_signals(usdjpy)
    gj_atr = _atr_for(gold_jpy).fillna(_atr_for(gold_jpy).dropna().iloc[0])
    fx_atr = _atr_for(usdjpy).fillna(_atr_for(usdjpy).dropna().iloc[0])

    equity = np.zeros(len(gold_jpy)); cash = CAPITAL
    gj_sh = 0.0; gj_ep = 0.0; fx_sh = 0.0; fx_ep = 0.0
    trades = []

    for i in range(len(gold_jpy)):
        c_gj = gold_jpy.iloc[i]; c_fx = usdjpy.iloc[i]
        gj_atr_v = gj_atr.iloc[i] if pd.notna(gj_atr.iloc[i]) else gj_atr.dropna().iloc[0]
        fx_atr_v = fx_atr.iloc[i] if pd.notna(fx_atr.iloc[i]) else fx_atr.dropna().iloc[0]
        g_now = gj_sig.iloc[i] > 0; f_now = fx_sig.iloc[i] > 0
        g_was = (gj_sig.iloc[i-1] > 0) if i > 0 else False
        f_was = (fx_sig.iloc[i-1] > 0) if i > 0 else False

        # EXIT gold_jpy
        if gj_sh > 0 and (c_gj <= gj_ep - ATR_MULT * gj_atr_v or (not g_now and g_was)):
            reason = 'STOP_LOSS' if c_gj <= gj_ep - ATR_MULT * gj_atr_v else 'SIGNAL_EXIT'
            pnl = (c_gj - gj_ep) * gj_sh if reason == 'STOP_LOSS' else (c_gj * 0.9995 - gj_ep) * gj_sh
            comm = abs(gj_sh) * (c_gj if reason == 'STOP_LOSS' else c_gj * 0.9995) * COMMISSION
            cash += pnl - comm
            trades.append({'entry_date': gold_jpy.index[i], 'exit_date': gold_jpy.index[i],
                           'type': 'GOLD_EXIT', 'entry_price': gj_ep,
                           'exit_price': c_gj if reason == 'STOP_LOSS' else c_gj * 0.9995,
                           'size': gj_sh, 'pnl': pnl - comm, 'exit_reason': reason, 'ticker': 'GOLD/JPY'})
            gj_sh = 0.0; gj_ep = 0.0
        # EXIT fx overlay
        if fx_sh > 0 and (c_fx <= fx_ep - ATR_MULT * fx_atr_v or (not f_now and f_was)):
            reason = 'STOP_LOSS' if c_fx <= fx_ep - ATR_MULT * fx_atr_v else 'SIGNAL_EXIT'
            pnl = (c_fx - fx_ep) * fx_sh if reason == 'STOP_LOSS' else (c_fx * 0.9995 - fx_ep) * fx_sh
            comm = abs(fx_sh) * (c_fx if reason == 'STOP_LOSS' else c_fx * 0.9995) * COMMISSION
            cash += pnl - comm
            trades.append({'entry_date': usdjpy.index[i], 'exit_date': usdjpy.index[i],
                           'type': 'FX_EXIT', 'entry_price': fx_ep,
                           'exit_price': c_fx if reason == 'STOP_LOSS' else c_fx * 0.9995,
                           'size': fx_sh, 'pnl': pnl - comm, 'exit_reason': reason, 'ticker': 'USD/JPY'})
            fx_sh = 0.0; fx_ep = 0.0

        # ENTRY gold_jpy core
        if gj_sh == 0.0 and g_now and not g_was:
            raw = (HALF_KELLY * cash) / (ATR_MULT * gj_atr_v) if gj_atr_v > 0 else 0
            gj_sh = _cap_position(raw, c_gj, cash, MAX_LEVERAGE)
            gj_ep = c_gj * 1.0005
            trades.append({'entry_date': gold_jpy.index[i], 'type': 'GOLD_ENTRY',
                           'entry_price': gj_ep, 'size': gj_sh, 'notional': gj_sh * gj_ep,
                           'exit_reason': 'ENTRY', 'ticker': 'GOLD/JPY'})
            cash -= gj_sh * gj_ep * COMMISSION
        # ENTRY fx overlay (when gold_jpy is long, overlay sized by hedge_ratio)
        if fx_sh == 0.0 and g_now and not g_was and gj_sh > 0:
            overlay_notional = hedge_ratio * (gj_sh * gj_ep)
            raw = overlay_notional / c_fx
            fx_sh = _cap_position(raw, c_fx, cash, MAX_LEVERAGE)
            fx_ep = c_fx * 1.0005
            trades.append({'entry_date': usdjpy.index[i], 'type': 'FX_ENTRY',
                           'entry_price': fx_ep, 'size': fx_sh, 'notional': fx_sh * fx_ep,
                           'exit_reason': 'ENTRY', 'ticker': 'USD/JPY'})
            cash -= fx_sh * fx_ep * COMMISSION

        gj_pnl = (c_gj - gj_ep) * gj_sh if gj_sh > 0 else 0.0
        fx_pnl = (c_fx - fx_ep) * fx_sh if fx_sh > 0 else 0.0
        equity[i] = cash + gj_pnl + fx_pnl

    for tk, sh, ep, cs in [('GOLD/JPY', gj_sh, gj_ep, gold_jpy), ('USD/JPY', fx_sh, fx_ep, usdjpy)]:
        if sh > 0:
            c = cs.iloc[-1]; pnl = (c * 0.9995 - ep) * sh; comm = abs(sh) * c * 0.9995 * COMMISSION
            cash += pnl - comm
            trades.append({'entry_date': cs.index[-1], 'exit_date': cs.index[-1],
                           'type': tk + '_EXIT', 'entry_price': ep, 'exit_price': c * 0.9995,
                           'size': sh, 'pnl': pnl - comm, 'exit_reason': 'END_OF_DATA', 'ticker': tk})

    df_out = pd.DataFrame(index=gold_jpy.index)
    df_out['Close'] = gold_jpy; df_out['Equity'] = equity
    df_out['Daily_Return'] = df_out['Equity'].pct_change().fillna(0.0)
    return {'metrics': _metrics(df_out, trades, CAPITAL), 'equity': df_out['Equity'],
            'trades': trades, 'signal': gj_sig}


# ═══════════════════════════════════════════════════════════════════════════
#  Walk-forward wrapper
# ═══════════════════════════════════════════════════════════════════════════

def walk_forward(df, strategy_fn, is_years=5, oos_years=2):
    dates = df.index; start = dates[0]; end = dates[-1]
    folds = []; is_end = start + pd.DateOffset(years=is_years); fold_num = 0
    while is_end < end:
        oos_end = min(is_end + pd.DateOffset(years=oos_years), end)
        is_df = df.loc[start:is_end]; oos_df = df.loc[is_end:oos_end]
        is_res = strategy_fn(is_df); oos_res = strategy_fn(oos_df)
        folds.append({
            'fold': fold_num + 1,
            'is_start': str(start.date()), 'is_end': str(is_end.date()),
            'oos_start': str(is_end.date()), 'oos_end': str(oos_end.date()),
            'is_metrics': is_res['metrics'], 'oos_metrics': oos_res['metrics'],
            'is_cagr': is_res['metrics']['CAGR'], 'oos_cagr': oos_res['metrics']['CAGR'],
            'oos_sharpe': oos_res['metrics']['Sharpe'], 'oos_dd': oos_res['metrics']['Max_Drawdown'],
            'oos_trades': oos_res['metrics']['Total_Trades'],
        })
        fold_num += 1; start = is_end; is_end = start + pd.DateOffset(years=is_years)
    return folds


# ═══════════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(CHARTS_DIR, exist_ok=True)

    df = build_components()
    print(f"Components loaded: {df.shape[0]} bars, "
          f"{df.index[0].date()} → {df.index[-1].date()}")
    print(f"  gold_usd: {df['gold_usd'].iloc[0]:.2f} → {df['gold_usd'].iloc[-1]:.2f}")
    print(f"  usdjpy:   {df['usdjpy'].iloc[0]:.2f} → {df['usdjpy'].iloc[-1]:.2f}")
    print(f"  gold_jpy: {df['gold_jpy'].iloc[0]:,.0f} → {df['gold_jpy'].iloc[-1]:,.0f}\n")

    strategies = {
        'static_50_50':     lambda d: run_static_split(d, split_ratio=0.5),
        'trend_weighted':   lambda d: run_trend_weighted_split(d),
        'core_plus_overlay': lambda d: run_core_plus_overlay(d, hedge_ratio=0.3),
    }

    results = {}
    for name, fn in strategies.items():
        print(f"=== {name} ===")
        res = fn(df)
        m = res['metrics']
        print(f"  Sharpe={m['Sharpe']:+.2f}  CAGR={m['CAGR']:+.2%}  "
              f"MaxDD={m['Max_Drawdown']:.2%}  Trades={m['Total_Trades']}")
        print(f"  WinRate={m['Win_Rate']:.1%}  Payoff={m['Payoff_Ratio']:.2f}x  PF={m['Profit_Factor']:.2f}")
        print(f"  Final=${m['Final_Value']:,.0f}\n")
        results[name] = res

    # Walk-forward
    print("=== Walk-Forward (5y IS / 2y OOS) ===")
    wf_results = {}
    for name, fn in strategies.items():
        wf = walk_forward(df, fn)
        avg_sh = np.mean([f['oos_sharpe'] for f in wf])
        avg_dd = np.mean([f['oos_dd'] for f in wf])
        print(f"  {name}: avg OOS Sharpe={avg_sh:+.2f}, avg OOS DD={avg_dd:.2%}, folds={len(wf)}")
        wf_results[name] = wf

    # Save outputs
    for name, res in results.items():
        export_trade_log(res['trades'], os.path.join(OUT_DIR, f'{name}_trades.csv'))
        plot_equity_curve(res['equity'], name.upper(), f'Decomposition: {name}',
                          os.path.join(CHARTS_DIR, f'{name}_equity.png'))
        with open(os.path.join(OUT_DIR, f'{name}_results.json'), 'w') as f:
            json.dump(res['metrics'], f, default=str, indent=2)

    with open(os.path.join(OUT_DIR, 'decomposition_walkforward.json'), 'w') as f:
        json.dump(wf_results, f, default=str, indent=2)

    # Summary
    print("\n" + "=" * 75)
    print("COMPARISON SUMMARY")
    print("=" * 75)
    print(f"{'Strategy':<22} {'CAGR':>8} {'Sharpe':>7} {'MaxDD':>8} {'PF':>6} {'Final$':>14}")
    print("-" * 75)
    for name, res in results.items():
        m = res['metrics']
        print(f"{name:<22} {m['CAGR']:>+7.2%} {m['Sharpe']:>+7.2f} {m['Max_Drawdown']:>7.2%} {m['Profit_Factor']:>6.2f} ${m['Final_Value']:>13,.0f}")
    print("-" * 75)

    # Correlation
    df_ret = df.pct_change().dropna()
    corr_data = {
        'gold_usd_vs_usdjpy_daily': float(df_ret['gold_usd'].corr(df_ret['usdjpy'])),
        'gold_usd_vs_usdjpy_weekly': float(
            df_ret['gold_usd'].resample('W-FRI').last().pct_change().dropna()
            .corr(df_ret['usdjpy'].resample('W-FRI').last().pct_change().dropna())),
        'gold_usd_vs_usdjpy_monthly': float(
            df_ret['gold_usd'].resample('ME').last().pct_change().dropna()
            .corr(df_ret['usdjpy'].resample('ME').last().pct_change().dropna())),
        'gold_jpy_vs_usdjpy_daily': float(df_ret['gold_jpy'].corr(df_ret['usdjpy'])),
        'gold_usd_vs_gold_jpy_daily': float(df_ret['gold_usd'].corr(df_ret['gold_jpy'])),
    }
    with open(os.path.join(OUT_DIR, 'decomposition_correlation.json'), 'w') as f:
        json.dump(corr_data, f, default=str, indent=2)

    print("\nAll results saved to GOLD/reports/ and GOLD/charts/")
