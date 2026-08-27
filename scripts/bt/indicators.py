"""Technical indicators used by strategies."""
import pandas as pd
import numpy as np


def _ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def _sma(series, period):
    return series.rolling(window=period).mean()


def _atr(df, period=14):
    high = df['High']
    low = df['Low']
    close = df['Close']
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def calculate_atr(df, period=14):
    """Public alias for ATR."""
    return _atr(df, period)


def calculate_kama(series, period=30, fast=2, slow=30):
    """Kaufman's Adaptive Moving Average."""
    direction = series.abs().diff(period)
    volatility = series.diff().abs().rolling(window=period).sum()
    er = direction / volatility.replace(0, np.nan)
    fast_ema = 2.0 / (fast + 1)
    slow_ema = 2.0 / (slow + 1)
    sc = (er * (fast_ema - slow_ema) + slow_ema) ** 2
    kama = series.ewm(alpha=sc, adjust=False).mean()
    return kama


def donchian_channel(df, period=20):
    """Donchian channel: upper = rolling max high, lower = rolling min low."""
    return pd.DataFrame({
        'upper': df['High'].rolling(window=period).max(),
        'lower': df['Low'].rolling(window=period).min()
    })


def roc(series, period=252):
    """Rate of change."""
    return series.pct_change(periods=period)


def efficiency_ratio(series, period=10):
    """Kaufman's Efficiency Ratio."""
    net = (series - series.shift(period)).abs()
    movement = series.diff().abs().rolling(window=period).sum()
    er = net / movement.replace(0, np.nan)
    return er


def rolling_efficiency_ratio(series, period=10):
    """Rolling Efficiency Ratio across the full series."""
    net = (series - series.shift(period)).abs()
    movement = series.diff().abs().rolling(window=period).sum()
    er = net / movement.replace(0, np.nan)
    return er


def calculate_donchian(df, period=20):
    """Legacy alias for donchian_channel."""
    return donchian_channel(df, period=period)


def adx(df, period=14):
    """Average Directional Index (Wilder's). Values > 25 = trending."""
    high = df['High']
    low = df['Low']
    close = df['Close']
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    tr_smooth = _ema(tr, period)
    plus_dm = high.diff().where(high.diff() > -low.diff(), 0)
    minus_dm = -low.diff().where(-low.diff() > high.diff(), 0)
    plus_di = 100 * _ema(plus_dm, period) / tr_smooth
    minus_di = 100 * _ema(minus_dm, period) / tr_smooth
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    return _ema(dx, period)


def rolling_volatility(df, period=20):
    """Annualized rolling volatility from daily returns."""
    return df['Close'].pct_change().rolling(window=period).std() * np.sqrt(252)


def bollinger_bands(df, period=20, num_std=2.0):
    mid = _sma(df['Close'], period)
    std = df['Close'].rolling(window=period).std()
    return pd.DataFrame({'upper': mid + num_std * std, 'middle': mid, 'lower': mid - num_std * std})


def zscore(series, period=20):
    """Z-score of price vs rolling mean."""
    mean = _sma(series, period)
    std = series.rolling(window=period).std()
    return (series - mean) / std.replace(0, np.nan)


# ─── Tom DeMark Sequential Indicators ────────────────────────────────

def td_setup(series, close_offset=4):
    """
    TD Sequential Setup (vectorized).
    Buy Setup: counts consecutive closes > close[i-4], max 9.
    Sell Setup: counts consecutive closes < close[i-4], max 9.
    Returns integer Series (0-9), where 9 = setup complete.
    """
    # Compare each close to close 4 bars ago
    comparison = series > series.shift(close_offset)  # True/False/NaN
    comparison_lt = series < series.shift(close_offset)
    
    # Rolling count of consecutive True values (max 9)
    # Use a cumsum-with-reset approach
    result = pd.Series(0, index=series.index, dtype=int)
    
    # Vectorized: detect breaks (comparison == False or NaN)
    # A "run" of consecutive True values resets at each False
    # Use cumsum of breaks as group IDs
    breaks = (~comparison).astype(int)
    breaks = breaks.fillna(1).astype(int)  # NaN counts as break
    group_ids = breaks.cumsum()
    
    # Within each group, count consecutive Trues from the end
    # For each position, count how many consecutive True values precede it (including itself)
    # Using expanding count within each group
    true_mask = comparison.fillna(False).astype(bool)
    
    # Simple approach: forward fill the count within each group
    # count = cumsum of true_mask within group, capped at 9
    # But we need the trailing count, not cumulative from group start
    # Better: use a loop but only once (vectorized comparison already done)
    
    count = 0
    for i in range(len(series)):
        if i < close_offset:
            continue
        if comparison.iloc[i]:
            count += 1
        elif comparison_lt.iloc[i]:
            count = 1
        else:
            count = 0
        if count > 9:
            count = 9
        result.iloc[i] = count
    
    return result


def td_buy_setup(series, close_offset=4):
    """TD Buy Setup: 9 consecutive closes where close > close[i-4]."""
    return td_setup(series, close_offset=close_offset)


def td_sell_setup(series, close_offset=4):
    """TD Sell Setup: 9 consecutive closes where close < close[i-4]."""
    return td_setup(-series, close_offset=close_offset)


def td_countdown_vectorized(df, direction='buy', window_size=20):
    """
    TD Sequential Countdown (vectorized, relaxed).
    Buy Countdown: counts bars where close < low[i-2] within a rolling window.
    Sell Countdown: counts bars where close > high[i-2] within a rolling window.
    The countdown starts after a completed setup of 9.
    Returns integer Series (0-13), where 13 = countdown complete.
    
    Classic TD Sequential requires 13 strictly consecutive valid bars,
    which is extremely rare on daily FX data. This relaxed version counts
    up to 13 valid bars within a rolling window of `window_size` bars
    after a setup completes.
    """
    close = df['Close']
    high = df['High']
    low = df['Low']
    
    if direction == 'buy':
        cond = (close < low.shift(2)).astype(int)
        setup = (td_buy_setup(close) >= 9)
    else:
        cond = (close > high.shift(2)).astype(int)
        setup = (td_sell_setup(close) >= 9)
    
    n = len(df)
    countdown = np.zeros(n, dtype=int)
    
    cond_vals = cond.values.astype(np.int32)
    setup_vals = setup.values.astype(np.int32)
    
    for i in range(n):
        if not setup_vals[i]:
            continue
        # Count valid bars in the window [i, i+window_size)
        count = 0
        for j in range(i, min(i + window_size, n)):
            if cond_vals[j]:
                count += 1
            if count >= 13:
                # Mark all bars from j-12 to j as countdown=13
                for k in range(max(i, j-12), j+1):
                    countdown[k] = 13
                break
    
    return pd.Series(countdown, index=df.index)


def td_buy_countdown(df):
    """Buy countdown: 13 consecutive closes where close < low[i-2]."""
    return td_countdown_vectorized(df, direction='buy')


def td_sell_countdown(df):
    """Sell countdown: 13 consecutive closes where close > high[i-2]."""
    return td_countdown_vectorized(df, direction='sell')


def td_combo(df):
    """
    TD Combo — stricter version combining Setup + Countdown.
    Buy Combo signal fires when both Buy Setup (9) and Buy Countdown (13) complete.
    Sell Combo signal fires when both Sell Setup (9) and Sell Countdown (13) complete.
    Returns a Series with +1 (buy combo), -1 (sell combo), 0 (none).
    """
    close = df['Close']
    high = df['High']
    low = df['Low']
    signals = pd.Series(0, index=df.index, dtype=int)
    
    # Compute setup and countdown
    buy_setup = td_buy_setup(close) >= 9
    sell_setup = td_sell_setup(close) >= 9
    buy_cd = td_buy_countdown(df) >= 13
    sell_cd = td_sell_countdown(df) >= 13
    
    # Combo fires where both setup and countdown complete
    signals[buy_setup & buy_cd] = 1
    signals[sell_setup & sell_cd] = -1
    
    return signals


def td_st_demand(df, period=9):
    """
    TDST Demand Level.
    For a completed Buy Setup (9 consecutive closes > close[i-4]),
    the TDST Demand = highest high during the setup.
    """
    close = df['Close']
    high = df['High']
    result = pd.Series(np.nan, index=df.index)
    
    # Precompute buy setup
    buy_setup = td_buy_setup(close) >= 9
    
    for i in range(period - 1, len(df)):
        if buy_setup.iloc[i]:
            # Find the start of this 9-bar setup
            # The setup is bars [i-8, i] where close[j] > close[j-4] for all j in range
            result.iloc[i] = high.iloc[i-8:i+1].max()
    
    return result


def td_st_supply(df, period=9):
    """
    TDST Supply Level.
    For a completed Sell Setup, the TDST Supply = lowest low during the setup.
    """
    close = df['Close']
    low = df['Low']
    result = pd.Series(np.nan, index=df.index)
    
    sell_setup = td_sell_setup(close) >= 9
    
    for i in range(period - 1, len(df)):
        if sell_setup.iloc[i]:
            result.iloc[i] = low.iloc[i-8:i+1].min()
    
    return result
