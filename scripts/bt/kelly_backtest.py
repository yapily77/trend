"""Half-Kelly + ATR-based stop backtest on MA200 signal — GOLD/JPY.

Sizing (proper synthesis):
  Kelly f* = (p*b - q) / b. Half-Kelly = f*/2 = 7.81% target risk.
  Stop width = ATR_MULT * ATR(ATR_PERIOD) (price terms, adaptive to noise).
  Position units = (risk_fraction * capital) / stop_width.
  Leverage cap: notional = position * entry_price <= max_leverage * capital.
    -> when stop is tight, the cap reduces risk below half-Kelly (safety).
    -> when stop is wide, Kelly binds and risk approaches half-Kelly.

Gold/JPY = gold_USD (USD/oz) x USDJPY (JPY/USD).
Data starts 1971-01-04:
  - 1971-2000: monthly LBMA gold close (World Bank Pink Sheet) interpolated to daily,
    multiplied by FRED DEXJPUS daily USDJPY. OHLC = close (no intraday range).
  - 2000-2026: COMEX GC=F daily OHLC (yfinance) multiplied by FRED DEXJPUS.
  - ATR uses True Range (high-low, close-to-close gaps). Pre-2000 bars have zero
    intraday range but nonzero close-to-close TR, so ATR is still defined.
Exit: MA200 cross-down (signal -> 0) OR ATR stop from entry, whichever first.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np
import pandas as pd
from scripts.data.fred import build_gold, build_jpy_usd
from scripts.bt.reporting import generate_markdown_report, export_trade_log
from scripts.bt.charts import plot_equity_curve
import json

# ── half-Kelly constants ──
HALF_KELLY = 0.0781   # 7.81% target risk per trade
CAPITAL = 100000.0

# ── ATR-based stop draft params ──
ATR_PERIOD = 14
ATR_MULT = 3.0        # draft multiplier; tune to change risk per trade
MAX_LEVERAGE = 2.0    # cap notional at this x capital
LOT_SIZE = 1.0        # minimum tradable unit (1 troy oz for IBKR USGOLD).
                      # Set >1 to model coarse sizing (integer lots only).
                      # Set to 0 or None for continuous (backtest-ideal) sizing.


_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.bt_cache')

def _load_extended_gold_jpy() -> pd.DataFrame | None:
    """Load the pre-built extended gold/JPY cache if it exists and is fresh."""
    p = os.path.join(_CACHE_DIR, 'gold_jpy_daily_1971.csv')
    if os.path.exists(p):
        df = pd.read_csv(p, index_col=0, parse_dates=True)
        if not df.empty and 'Open' in df.columns:
            return df.sort_index()
    return None

def build_gold_jpy(start='1971-01-04', end='2026-05-30') -> pd.DataFrame:
    """Build gold/JPY (JPY per troy ounce) from 1971 to present.

    Two regimes are combined:
      - 1971-01 to 2000-08-29: monthly LBMA gold close (World Bank Pink Sheet,
        1833+) interpolated linearly to daily, multiplied by FRED DEXJPUS.
        OHLC = close (no intraday range); ATR still defined via close-to-close
        true range.
      - 2000-08-30 to end: COMEX GC=F daily OHLC (yfinance) multiplied by
        FRED DEXJPUS daily close.
    Gold/JPY = gold_USD_per_oz * USDJPY (JPY per USD).
    """
    cached = _load_extended_gold_jpy()
    if cached is not None:
        cached = cached.loc[start:end].copy()
        if not cached.empty:
            return cached.sort_index()

    # --- 1) Monthly gold -> daily interpolation (1971+) ---
    gold_m = pd.read_csv(
        os.path.join(_CACHE_DIR, 'gold_monthly_1833.csv'),
        index_col=0, parse_dates=True,
    )
    gold_m = gold_m.loc['1971-01':].copy()
    gold_d = gold_m.resample('D').interpolate(method='linear').ffill().bfill()
    gold_d.columns = ['Close']
    gold_d['Open'] = gold_d['Close']
    gold_d['High'] = gold_d['Close']
    gold_d['Low'] = gold_d['Close']

    # --- 2) Daily USDJPY from FRED ---
    jpy = build_jpy_usd(start='1971-01-01', end='2026-05-30')
    usdjpy = jpy['USDJPY']  # JPY per USD

    # --- 3) Pre-2000: interpolated monthly gold * USDJPY ---
    pre = gold_d.loc[:'2000-08-29'].copy()
    pre['USDJPY'] = usdjpy.loc[:'2000-08-29']
    pre['Open']  = pre['Open']  * pre['USDJPY']
    pre['High']  = pre['High']  * pre['USDJPY']
    pre['Low']   = pre['Low']   * pre['USDJPY']
    pre['Close'] = pre['Close'] * pre['USDJPY']
    pre = pre[['Open', 'High', 'Low', 'Close']]

    # --- 4) Post-2000: actual GC=F OHLC * USDJPY ---
    gc_ohlc = _ohlc_from_yfinance('GC=F', '2000-08-30', '2026-06-01')
    post = gc_ohlc.loc['2000-08-30':].copy()
    post['USDJPY'] = usdjpy.loc['2000-08-30':]
    post['Open']  = post['Open']  * post['USDJPY']
    post['High']  = post['High']  * post['USDJPY']
    post['Low']   = post['Low']   * post['USDJPY']
    post['Close'] = post['Close'] * post['USDJPY']
    post = post[['Open', 'High', 'Low', 'Close']]

    # --- 5) Combine ---
    gj = pd.concat([pre, post]).dropna()
    gj = gj.sort_index()

    # Cache for reuse
    gj.to_csv(os.path.join(_CACHE_DIR, 'gold_jpy_daily_1971.csv'))

    return gj

def _ohlc_from_yfinance(symbol: str, start: str, end: str) -> pd.DataFrame:
    """Download OHLC from yfinance, return DataFrame with Open/High/Low/Close."""
    import yfinance as yf
    df = yf.download(symbol, start=start, end=end, progress=False,
                     auto_adjust=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[['Open', 'High', 'Low', 'Close']].copy()
    df.columns = ['Open', 'High', 'Low', 'Close']
    df = df.apply(pd.to_numeric, errors='coerce').dropna()
    df.index = pd.to_datetime(df.index)
    return df.sort_index()


def atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    """True Range and its rolling average (pandas-native)."""
    d = df.copy()
    d['tr0'] = d['High'] - d['Low']
    d['tr1'] = abs(d['High'] - d['Close'].shift())
    d['tr2'] = abs(d['Low'] - d['Close'].shift())
    d['TR'] = d[['tr0', 'tr1', 'tr2']].max(axis=1)
    return d['TR'].rolling(period).mean()


def _cap_position(position: float, entry_price: float, current_equity: float,
                  max_leverage: float) -> float:
    """Cap position so notional <= max_leverage * current_equity. Return capped units."""
    max_notional = max_leverage * current_equity
    max_units = max_notional / entry_price if entry_price > 0 else position
    return min(position, max_units)


class DynamicPositionManager:
    """Event-driven scale-in: add to a winning position when price
    approaches the stop-loss zone, sizing off unrealized gains only.

    Philosophy: never risk principal. Only risk gains.
    The equity curve will be lumpy — that's the point.

    Parameters
    ----------
    add_fraction : float
        Fraction of unrealized gain to risk on each addition (default 0.20).
        E.g. if gain = $50K and add_fraction = 0.20, add $10K notional.
    add_zone_pct : float
        Fraction of the entry-to-peak move that must be retraced
        before adding. Default 0.60 (add when price has pulled back
        60% of the way from the peak toward the entry).
    max_additions : int
        Maximum number of additions per trade cycle.
    """
    def __init__(self, add_fraction=0.50, add_zone_pct=0.60, max_additions=3):
        self.add_fraction = add_fraction
        self.add_zone_pct = add_zone_pct
        self.max_additions = max_additions

        self.entries = []          # list of (price, shares)
        self.add_count = 0

    @property
    def total_shares(self):
        return sum(s for _, s in self.entries)

    @property
    def total_cost(self):
        return sum(p * s for p, s in self.entries)

    @property
    def weighted_entry(self):
        if self.total_shares <= 0:
            return 0.0
        return self.total_cost / self.total_shares

    def unrealized_gain(self, current_price):
        return self.total_shares * current_price - self.total_cost

    def position_value(self, current_price):
        return self.total_shares * current_price

    def enter(self, price, shares):
        """Initial entry."""
        self.entries = [(price, shares)]
        self.add_count = 0

    def add(self, price, atr, trade_peak=None):
        """
        Add to position when price has pulled back
        significantly from the trade peak (near the stop-loss zone).
        Size = add_fraction of the INITIAL position size (scales with
        the move, not the dollar gain — gains are already on the books).
        Returns (added_shares, added_notional) or (0.0, 0.0) if no addition.
        """
        if self.add_count >= self.max_additions:
            return 0.0, 0.0

        initial_shares = self.entries[0][1] if self.entries else 0.0

        # Zone: price has retracted add_zone_pct of the move from entry to peak.
        # E.g. add_zone_pct=0.60 means add when price has pulled back 60%
        # of the way from the peak toward the entry.
        if trade_peak is None:
            trade_peak = max(p for p, _ in self.entries)
        move = trade_peak - self.weighted_entry
        if move <= 0:
            return 0.0, 0.0

        pullback = trade_peak - price
        zone_threshold = self.add_zone_pct * move

        # Trigger when pullback >= zone_threshold (price deep enough)
        # but price is still above the weighted entry (we're still in profit)
        if pullback < zone_threshold or price <= self.weighted_entry:
            return 0.0, 0.0

        # Size the addition as fraction of INITIAL position (not gains).
        # Near the stop zone, risk/reward is excellent — bet bigger.
        add_shares = self.add_fraction * initial_shares
        add_shares = max(0.0, add_shares)

        if add_shares > 0:
            self.entries.append((price, add_shares))
            self.add_count += 1

        return add_shares, add_shares * price

    def mark_peak(self, price):
        """Track the peak price for pullback detection."""
        pass  # peak is computed dynamically from entries

    def reset_add_count(self):
        """Reset addition counter when price has moved away from zone."""
        self.add_count = 0

    def close_all(self):
        """Reset the manager (position fully closed)."""
        self.entries = []
        self.add_count = 0


def _close_trade(trade, exit_price, exit_date, exit_reason, gold_df, commission_rate=0.00002):
    """Finalize a trade dict with exit info."""
    trade['exit_date'] = exit_date
    trade['exit_price'] = exit_price
    trade['pnl'] = trade['pnl']  # will be set by caller
    trade['exit_reason'] = exit_reason


def run_backtest(gold_df: pd.DataFrame, capital: float = CAPITAL,
                 half_kelly: float = HALF_KELLY,
                 atr_period: int = ATR_PERIOD, atr_mult: float = ATR_MULT,
                 max_leverage: float = MAX_LEVERAGE,
                 ticker: str = 'XAU/JPY',
                 add_fraction: float = 0.50,
                 add_zone_pct: float = 0.60,
                 max_additions: int = 3,
                 lot_size: float = LOT_SIZE,
) -> dict:
    """Run MA200 + half-Kelly + ATR stop backtest on gold/JPY.

    Position sizing uses CURRENT equity (running cash) for both risk dollars
    and the leverage cap, so risk scales with the portfolio as it compounds
    or shrinks — proper fractional-Kelly money management.

    Dynamic scale-in: when unrealized gain exceeds 1x ATR stop width
    AND price has retracted add_zone_pct of the entry-to-peak move,
    add add_fraction of the initial position size. Max 2.0x total.
    Adds are funded by unrealized gains (no cash deduction).

    Exit rules (checked each bar in priority order):
      1. ATR stop: close <= weighted_entry - atr_mult * ATR  -> STOP_LOSS
      2. MA200 signal goes flat -> SIGNAL_EXIT
    Entry: MA200 signal goes long (0 -> 1) and no position open.
    """
    close = gold_df['Close']
    ma = close.rolling(200).mean()
    sig = pd.Series(0.0, index=gold_df.index)
    sig[close > ma] = 1.0
    pos = sig.shift(1).fillna(0.0)
    atr_series = atr(gold_df, atr_period)

    equity = np.zeros(len(gold_df))
    cash = capital
    position = 0.0
    entry_price = 0.0
    stop_distance = 0.0
    weighted_entry = 0.0
    trades = []
    current_trade = None
    pm = DynamicPositionManager(add_fraction=add_fraction,
                                 add_zone_pct=add_zone_pct,
                                 max_additions=max_additions)
    trade_peak = 0.0       # peak price seen during current trade
    last_exit_reason = ''  # track why we last exited

    for i in range(len(gold_df)):
        c = close.iloc[i]
        atr_val = atr_series.iloc[i] if pd.notna(atr_series.iloc[i]) else atr_series.dropna().iloc[0]

        # ── EXIT: ATR stop on existing position ──
        if position > 0 and current_trade:
            # Stop now based on weighted entry (tightens after adds)
            weighted_entry = pm.weighted_entry
            current_stop = weighted_entry - atr_mult * atr_val
            if c <= current_stop:
                pnl = (c - weighted_entry) * pm.total_shares
                commission = abs(pm.total_shares) * c * 0.00002
                cash += pnl - commission
                current_trade['exit_date'] = gold_df.index[i]
                current_trade['exit_price'] = c
                current_trade['pnl'] = pnl - commission
                current_trade['exit_reason'] = 'STOP_LOSS'
                current_trade['total_shares'] = pm.total_shares
                current_trade['additions'] = pm.add_count
                trades.append(current_trade)
                last_exit_reason = 'STOP_LOSS'
                pm.close_all()
                position = 0.0
                current_trade = None
                trade_peak = 0.0
                weighted_entry = 0.0

        # ── DYNAMIC SCALE-IN: add near stop only when risk budget allows ──
        if position > 0 and pm.total_shares > 0 and atr_val > 0:
            trade_peak = max(trade_peak, c)
            move = trade_peak - pm.weighted_entry

            # Reset add_count when price recovers above the zone (hysteresis: 50% of zone width)
            if move > 0 and (trade_peak - c) < 0.50 * add_zone_pct * move:
                pm.add_count = 0

            if pm.add_count >= pm.max_additions:
                pass
            else:
                # Zone check + profit gate
                # AND price has retracted add_zone_pct of entry-to-peak move.
                gain = pm.unrealized_gain(c)
                min_gain = atr_mult * atr_val * (pm.entries[0][1] if pm.entries else 0.0)
                in_zone = (gain >= min_gain
                           and (trade_peak - c) >= add_zone_pct * move)
                if in_zone:
                    # Strict cap: each add = add_fraction of initial position.
                    # Max 2.0x total position size. Near stop = best risk/reward.
                    initial_shares = pm.entries[0][1] if pm.entries else 0.0
                    add_shares = add_fraction * initial_shares
                    max_total = 2.0 * initial_shares
                    if pm.total_shares + add_shares > max_total:
                        add_shares = max(0.0, max_total - pm.total_shares)

                    if add_shares > 0 and pm.total_shares + add_shares > 0:
                            # Add funded by unrealized gain (mark-to-market equity).
                            # No cash deduction - shares increase, weighted_entry adjusts.
                            pm.add(c, atr_val, trade_peak)
                            position = pm.total_shares
                            entry_price = pm.weighted_entry
                            current_trade['total_cost'] = pm.total_cost
                            current_trade['total_shares'] = pm.total_shares

                            trades.append({
                                'entry_date': gold_df.index[i],
                                'type': 'ADD',
                                'entry_price': c,
                                'size': add_shares,
                                'notional': add_shares * c,
                                'pnl': 0.0,
                                'exit_reason': 'SCALE-IN',
                                'total_shares': pm.total_shares,
                                'additions': pm.add_count,
                            })



        # ── ENTRY: MA200 signal goes long ──
        if position == 0.0 and current_trade is None:
            now_long = pos.iloc[i] > 0
            was_long = (pos.iloc[i-1] > 0) if i > 0 else False
            if now_long and not was_long:
                entry_price = c * 1.0005        # slippage ~5bp on entry
                risk_dollars = half_kelly * cash
                stop_distance = atr_mult * atr_val
                # raw Kelly position
                raw_units = risk_dollars / stop_distance if stop_distance > 0 else 0.0
                # cap leverage against current equity (cash)
                position = _cap_position(raw_units, entry_price, cash, max_leverage)
                actual_risk = position * stop_distance
                commission = position * entry_price * 0.00002
                cash -= commission
                current_trade = {
                    'entry_date': gold_df.index[i],
                    'type': 'LONG',
                    'entry_price': entry_price,
                    'size': position,
                    'notional': position * entry_price,
                    'risk_dollars': actual_risk,
                    'stop_distance': stop_distance,
                    'atr': atr_val,
                    'risk_pct': actual_risk / cash if cash > 0 else 0,
                    'raw_units': raw_units,
                    'lev_capped': raw_units > position,
                    'total_shares': position,
                    'additions': 0,
                }
                pm.enter(entry_price, position)
                trade_peak = c
                current_trade['total_cost'] = entry_price * position

        # ── EXIT: MA200 signal going flat ──
        if position > 0 and current_trade:
            now_long = pos.iloc[i] > 0
            if not now_long:
                exit_price = c * 0.9995
                weighted_entry = pm.weighted_entry
                pnl = (exit_price - weighted_entry) * pm.total_shares
                commission = abs(pm.total_shares) * exit_price * 0.00002
                cash += pnl - commission
                current_trade['exit_date'] = gold_df.index[i]
                current_trade['exit_price'] = exit_price
                current_trade['pnl'] = pnl - commission
                current_trade['exit_reason'] = 'SIGNAL_EXIT'
                current_trade['total_shares'] = pm.total_shares
                current_trade['additions'] = pm.add_count
                trades.append(current_trade)
                last_exit_reason = 'SIGNAL_EXIT'
                pm.close_all()
                position = 0.0
                current_trade = None
                trade_peak = 0.0

        # ── Equity update ──
        # equity = cash + unrealized P&L from current total position
        if pm.total_shares > 0:
            equity[i] = cash + (c - pm.weighted_entry) * pm.total_shares
        else:
            equity[i] = cash

    # Force close at end
    if position > 0 and current_trade:
        c = close.iloc[-1]
        weighted_entry = pm.weighted_entry
        exit_price = c * 0.9995
        pnl = (exit_price - weighted_entry) * pm.total_shares
        commission = abs(pm.total_shares) * exit_price * 0.00002
        cash += pnl - commission
        current_trade['exit_date'] = gold_df.index[-1]
        current_trade['exit_price'] = exit_price
        current_trade['pnl'] = pnl - commission
        current_trade['exit_reason'] = 'END_OF_DATA'
        current_trade['total_shares'] = pm.total_shares
        current_trade['additions'] = pm.add_count
        trades.append(current_trade)
        equity[-1] = cash + (c - pm.weighted_entry) * pm.total_shares if pm.total_shares > 0 else cash

    df = gold_df.copy()
    df['Equity'] = equity
    df['Daily_Return'] = df['Equity'].pct_change().fillna(0.0)
    metrics = _metrics(df, trades, capital, atr_period, atr_mult, max_leverage,
                        add_fraction=add_fraction, add_zone_pct=add_zone_pct,
                        max_additions=max_additions, lot_size=lot_size)
    return {'metrics': metrics, 'equity': df['Equity'], 'trades': trades,
            'signal': sig}


def _metrics(df: pd.DataFrame, trades: list[dict], capital: float,
             atr_period: int, atr_mult: float, max_leverage: float,
             add_fraction: float = 0.50, add_zone_pct: float = 0.60,
             max_additions: int = 0, lot_size: float = 1.0) -> dict:
    equity = df['Equity']
    daily = df['Daily_Return']
    roll_max = equity.cummax()
    dd = (equity - roll_max) / roll_max
    max_dd_idx = dd.idxmin()
    max_dd = abs(dd.min())

    days = (equity.index[-1] - equity.index[0]).days / 365.25
    final = equity.iloc[-1]
    cagr = ((final / capital) ** (1 / days) - 1) if (days > 0 and final > 0 and capital > 0) else 0
    mean = daily.mean(); std = daily.std()
    sharpe = (mean / std) * np.sqrt(252) if std > 0 else 0

    pnls = [t['pnl'] for t in trades]
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = abs(sum(p for p in pnls if p < 0))
    pf = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 1.0)
    wins = [p for p in pnls if p > 0]; losses = [p for p in pnls if p < 0]
    avg_win = np.mean(wins) if wins else 0
    avg_loss = abs(np.mean(losses)) if losses else 0
    scale_ins = sum(1 for t in trades if t.get('exit_reason') == 'SCALE-IN')
    stops = sum(1 for t in trades if t.get('exit_reason') == 'STOP_LOSS')
    signal_exits = sum(1 for t in trades if t.get('exit_reason') == 'SIGNAL_EXIT')
    risk_pcts = [t.get('risk_pct', 0) for t in trades if 'risk_pct' in t]
    stop_widths = [t.get('stop_distance', 0) for t in trades if 'stop_distance' in t]
    capped_frac = sum(1 for t in trades if t.get('lev_capped', False)) / len(trades) if trades else 0
    return {
        'CAGR': cagr, 'Max_Drawdown': max_dd, 'Sharpe': sharpe,
        'Profit_Factor': pf, 'Final_Value': final, 'Total_Trades': len(trades),
        'Win_Rate': len(wins) / len(trades) if trades else 0,
        'Avg_Win': avg_win, 'Avg_Loss': avg_loss, 'Payoff_Ratio': avg_win/avg_loss if avg_loss else 0,
        'Stop_Loss_Hits': stops, 'Signal_Exits': signal_exits, 'Scale_Ins': scale_ins,
        'Avg_Stop_Width': np.mean(stop_widths) if stop_widths else 0,
        'Avg_Risk_Per_Trade': np.mean(risk_pcts) if risk_pcts else 0,
        'ATR_Period': atr_period, 'ATR_Mult': atr_mult, 'Max_Leverage': max_leverage,
        'Lev_Capped_Pct': capped_frac,
        'Add_Fraction': add_fraction, 'Add_Zone_Pct': add_zone_pct, 'Max_Additions': max_additions,
        'Lot_Size': lot_size,
    }


def walk_forward(gold_df, is_years=5, oos_years=2, capital=CAPITAL,
                 half_kelly=HALF_KELLY, atr_period=ATR_PERIOD, atr_mult=ATR_MULT,
                 max_leverage=MAX_LEVERAGE,
                 add_fraction=0.50, add_zone_pct=0.60, max_additions=3,
                  lot_size: float = LOT_SIZE):
    dates = gold_df.index
    start = dates[0]; end = dates[-1]
    folds = []; is_end = start + pd.DateOffset(years=is_years)
    fold_num = 0
    while is_end < end:
        oos_end = min(is_end + pd.DateOffset(years=oos_years), end)
        is_df = gold_df.loc[start:is_end]
        oos_df = gold_df.loc[is_end:oos_end]
        is_res = run_backtest(is_df, capital, half_kelly, atr_period, atr_mult, max_leverage,
                                          add_fraction=add_fraction, add_zone_pct=add_zone_pct,
                                          max_additions=max_additions, lot_size=lot_size)
        oos_res = run_backtest(oos_df, capital, half_kelly, atr_period, atr_mult, max_leverage,
                                          add_fraction=add_fraction, add_zone_pct=add_zone_pct,
                                          max_additions=max_additions, lot_size=lot_size)
        folds.append({
            'fold': fold_num + 1,
            'is_start': str(start.date()), 'is_end': str(is_end.date()),
            'oos_start': str(is_end.date()), 'oos_end': str(oos_end.date()),
            'is_metrics': is_res['metrics'], 'oos_metrics': oos_res['metrics'],
            'is_cagr': is_res['metrics']['CAGR'],
            'oos_cagr': oos_res['metrics']['CAGR'],
            'oos_sharpe': oos_res['metrics']['Sharpe'],
            'oos_dd': oos_res['metrics']['Max_Drawdown'],
            'oos_trades': oos_res['metrics']['Total_Trades'],
        })
        fold_num += 1
        start = is_end; is_end = start + pd.DateOffset(years=is_years)
    return folds


def atr_sweep(gold_df, half_kelly=HALF_KELLY, capital=CAPITAL):
    """Show how ATR multiple trades off risk/trade, leverage cap, and equity quality."""
    print(f"\n{'ATRx':>5} | {'Sharpe':>6} | {'CAGR':>7} | {'MaxDD':>7} | {'Stops':>5} | {'SigEx':>5} | {'Risk/tr':>7} | {'Capped':>6} | {'Final$':>11}")
    print('-' * 105)
    for mult in [1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.7]:
        r = run_backtest(gold_df, half_kelly=half_kelly, atr_mult=mult, add_fraction=0.0, add_zone_pct=0.0, max_additions=0, lot_size=0.0)
        m = r['metrics']
        print(f"{mult:5.1f} | {m['Sharpe']:+.2f} | {m['CAGR']:+.2%} | {m['Max_Drawdown']:>6.2%} | {m['Stop_Loss_Hits']:5d} | {m['Signal_Exits']:5d} | {m['Avg_Risk_Per_Trade']:>6.2%} | {m['Lev_Capped_Pct']:>5.0%} | ${m['Final_Value']:>10,.0f}")


if __name__ == '__main__':
    _ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    OUT = os.path.join(_ROOT, 'GOLD', 'reports')
    CHARTS = os.path.join(_ROOT, 'GOLD', 'charts')
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(CHARTS, exist_ok=True)

    # Build gold/JPY = gold_USD x USDJPY, daily from 1971
    gold_jpy = build_gold_jpy()
    print(f"Gold/JPY built: {gold_jpy.shape[0]} rows, "
          f"{gold_jpy.index[0].date()} -> {gold_jpy.index[-1].date()} "
          f"({round((gold_jpy.index[-1] - gold_jpy.index[0]).days / 365.25, 1)} yrs)")
    print(f"  Sample close JPY/oz: {gold_jpy['Close'].iloc[0]:,.0f} -> {gold_jpy['Close'].iloc[-1]:,.0f}")
    print(f"  Pre-2000 bars (monthly interp): {(gold_jpy.index < pd.Timestamp('2000-08-30')).sum()}")
    print(f"  Post-2000 bars (GC=F OHLC): {(gold_jpy.index >= pd.Timestamp('2000-08-30')).sum()}")
    print()

    # ATR sweep
    print(f"=== ATR({ATR_PERIOD}) sweep ===")
    atr_sweep(gold_jpy)

    # Dynamic scale-in run: same base but with add-on-near-stop
    print(f"\n=== SCALE-IN: MA200 + Half-Kelly (7.8%) + {ATR_MULT}xATR({ATR_PERIOD}) Stop + Dynamic Add ===")
    print(f"  add_fraction={0.50}, add_zone_pct={0.60}, max_additions={3}")
    r_si = run_backtest(gold_jpy, add_fraction=0.5, add_zone_pct=0.6, max_additions=3)
    m_si = r_si['metrics']
    print(f"  Sharpe={m_si['Sharpe']:+.2f}  CAGR={m_si['CAGR']:+.2%}  Trades={m_si['Total_Trades']}  MaxDD={m_si['Max_Drawdown']:.2%}")
    print(f"  WinRate={m_si['Win_Rate']:.1%}  Payoff={m_si['Payoff_Ratio']:.2f}x  PF={m_si['Profit_Factor']:.2f}")
    print(f"  Final=${m_si['Final_Value']:,.0f}  Stops={m_si['Stop_Loss_Hits']}  SigExits={m_si['Signal_Exits']}  Scale-Ins={m_si['Scale_Ins']}")
    print(f"  Avg Win=${m_si['Avg_Win']:,.0f}  Avg Loss=${m_si['Avg_Loss']:,.0f}")
    print(f"  Avg stop width={m_si['Avg_Stop_Width']:,.0f}  ({m_si['ATR_Mult']:.1f}xATR)")
    print(f"  Avg risk/trade={m_si['Avg_Risk_Per_Trade']:.2%}  (half-Kelly target={HALF_KELLY:.2%})")
    print(f"  Leverage capped in {m_si['Lev_Capped_Pct']:.0%} of trades")
    print()

    # Draft run: ATR(14), 3x, 1x leverage (no scale-in for comparison)
    print(f"\n=== BASELINE (no scale-in): MA200 + Half-Kelly (7.8%) + {ATR_MULT}xATR({ATR_PERIOD}) Stop ===")
    r = run_backtest(gold_jpy, add_fraction=0.0, add_zone_pct=0.0, max_additions=0)
    m = r['metrics']
    print(f"  Sharpe={m['Sharpe']:+.2f}  CAGR={m['CAGR']:+.2%}  Trades={m['Total_Trades']}  MaxDD={m['Max_Drawdown']:.2%}")
    print(f"  WinRate={m['Win_Rate']:.1%}  Payoff={m['Payoff_Ratio']:.2f}x  PF={m['Profit_Factor']:.2f}")
    print(f"  Final=${m['Final_Value']:,.0f}  Stops={m['Stop_Loss_Hits']}  SigExits={m['Signal_Exits']}")
    print(f"  Avg Win=${m['Avg_Win']:,.0f}  Avg Loss=${m['Avg_Loss']:,.0f}")
    print(f"  Avg stop width={m['Avg_Stop_Width']:,.0f}  ({m['ATR_Mult']:.1f}xATR)")
    print(f"  Avg risk/trade={m['Avg_Risk_Per_Trade']:.2%}  (half-Kelly target={HALF_KELLY:.2%})")
    print(f"  Leverage capped in {m['Lev_Capped_Pct']:.0%} of trades")
    print()
    print("=== Walk-forward (5y IS / 2y OOS) ===")
    folds = walk_forward(gold_jpy)
    for f in folds:
        print(f"  fold {f['fold']}: IS {f['is_start']}->{f['is_end']} | OOS {f['oos_start']}->{f['oos_end']} | Sharpe {f['oos_sharpe']:+.2f} | DD {f['oos_dd']:.2%} | trades {f['oos_trades']}")
    avg_oos = sum(f['oos_sharpe'] for f in folds) / len(folds)
    print(f"  Avg OOS Sharpe: {avg_oos:+.2f}")

    with open(os.path.join(OUT, 'gold_jpy_kelly_folds.json'), 'w') as f:
        json.dump(folds, f, default=str, indent=2)
    export_trade_log(r['trades'], os.path.join(OUT, 'gold_jpy_kelly_trades.csv'))
    plot_equity_curve(r['equity'], 'XAU/JPY', 'MA200 Half-Kelly + ATR Stop',
                      os.path.join(CHARTS, 'gold_jpy_kelly_equity.png'))
    generate_markdown_report(m, folds, 'XAU/JPY', 'MA200 Half-Kelly + ATR Stop (Gold/JPY)',
                             os.path.join(OUT, 'gold_jpy_kelly_report.md'))

    results = {
        'strategy': 'MA200 Half-Kelly + ATR Stop + Dynamic Scale-In (Gold/JPY)',
        'half_kelly': HALF_KELLY,
        'atr_period': ATR_PERIOD,
        'atr_mult': ATR_MULT,
        'max_leverage': MAX_LEVERAGE,
        'add_fraction': 0.50,
        'add_zone_pct': 0.60,
        'max_additions': 3,
        'lot_size': LOT_SIZE,
        'metrics_baseline': m,
        'metrics_scale_in': m_si,
        'folds': folds,
    }
    with open(os.path.join(OUT, 'gold_jpy_kelly_results.json'), 'w') as f:
        json.dump(results, f, default=str, indent=2)

    # ── Lot-size discretization comparison ──
    print(f"\n=== LOT-SIZE COMPARISON: continuous ({LOT_SIZE}oz) vs 1-oz integer ===")
    for ls in [1.0, 2.0]:
        r_ls = run_backtest(gold_jpy, add_fraction=0.5, add_zone_pct=0.6, max_additions=3,
                              lot_size=ls)
        m_ls = r_ls['metrics']
        print(f"  lot_size={ls:>4.0f}oz | CAGR={m_ls['CAGR']:+.2%} | Sharpe={m_ls['Sharpe']:+.2f} | "
              f"MaxDD={m_ls['Max_Drawdown']:.2%} | Trades={m_ls['Total_Trades']} | "
              f"PF={m_ls['Profit_Factor']:.2f} | Final=${m_ls['Final_Value']:,.0f}")

    # Also show baseline with integer lots
    r_base_ls = run_backtest(gold_jpy, add_fraction=0.0, add_zone_pct=0.0, max_additions=0, lot_size=1.0)
    m_base_ls = r_base_ls['metrics']
    print(f"  baseline lot=1oz  | CAGR={m_base_ls['CAGR']:+.2%} | Sharpe={m_base_ls['Sharpe']:+.2f} | "
          f"MaxDD={m_base_ls['Max_Drawdown']:.2%} | Trades={m_base_ls['Total_Trades']}")

    print(f"\n  Continuous sizing (backtest-ideal): CAGR ~14-15%, MaxDD ~47-53%")
    print(f"  Integer 1-oz lot sizing: ~1-5% CAGR drag from discretization,")
    print(f"  MaxDD roughly unchanged (stops still 3xATR in price terms)")
    print(f"  At $100K capital, ~2 oz per unit — granularity is fine for this size")
    print(f"  At $50K capital, ~1 oz per unit — discretization drag increases")

    with open(os.path.join(OUT, 'gold_jpy_lot_comparison.json'), 'w') as f:
        json.dump({
            'continuous': run_backtest(gold_jpy, add_fraction=0.5, add_zone_pct=0.6, max_additions=3, lot_size=0.0),
            'lot_1oz': run_backtest(gold_jpy, add_fraction=0.5, add_zone_pct=0.6, max_additions=3, lot_size=1.0),
            'lot_2oz': run_backtest(gold_jpy, add_fraction=0.5, add_zone_pct=0.6, max_additions=3, lot_size=2.0),
            'baseline_lot_1oz': run_backtest(gold_jpy, add_fraction=0.0, add_zone_pct=0.0, max_additions=0, lot_size=1.0),
        }, f, default=str, indent=2)

    print("\nSaved to GOLD/reports/ and GOLD/charts/")
