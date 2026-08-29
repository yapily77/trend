import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from scripts.bt.indicators import calculate_kama, donchian_channel, adx, rolling_efficiency_ratio, rolling_volatility, td_buy_setup, td_sell_setup, td_buy_countdown, td_sell_countdown, td_combo, td_st_demand, td_st_supply

class Strategy(ABC):
    """Abstract Base Class for systematic strategies."""

    @abstractmethod
    def signals(self, df: pd.DataFrame) -> pd.Series:
        """
        Returns a series of signals:
        1 for Long, 0 for Flat, -1 for Short
        """
        pass

class KAMASlope(Strategy):
    def __init__(self, period: int = 10, fast: int = 2, slow: int = 30):
        self.period = period
        self.fast = fast
        self.slow = slow

    def signals(self, df: pd.DataFrame) -> pd.Series:
        close = df['Close']
        kama = calculate_kama(close, period=self.period, fast=self.fast, slow=self.slow)
        kama_diff = kama.diff()
        signals = pd.Series(0, index=df.index)
        signals[kama_diff > 0] = 1
        signals[kama_diff < 0] = -1
        return signals

class KAMAAdaptivePositionSizing(Strategy):
    def __init__(self, period: int = 10, fast: int = 2, slow: int = 30,
                 er_min: float = 0.1, er_max: float = 1.0, min_size: float = 0.25):
        self.period = period
        self.fast = fast
        self.slow = slow
        self.er_min = er_min
        self.er_max = er_max
        self.min_size = min_size

    def signals(self, df: pd.DataFrame) -> pd.Series:
        close = df['Close']
        kama = calculate_kama(close, period=self.period, fast=self.fast, slow=self.slow)
        kama_diff = kama.diff()
        direction = pd.Series(0, index=df.index)
        direction[kama_diff > 0] = 1
        direction[kama_diff < 0] = -1
        er = rolling_efficiency_ratio(close, period=self.period)
        er = er.fillna(0.5)
        size_mult = er.clip(self.er_min, self.er_max)
        signals = pd.Series(0.0, index=df.index)
        signals = direction * size_mult
        return signals

class DonchianBreakoutWithFilter(Strategy):
    """Alias: Donchian 20 with ADX regime filter."""
    def __init__(self, period: int = 20, adx_threshold: float = 25.0,
                 er_filter: bool = False, er_threshold: float = 0.3,
                 vol_filter: bool = False, vol_pct: float = 0.15):
        self.period = period
        self.adx_filter = True
        self.adx_threshold = adx_threshold
        self.er_filter = er_filter
        self.er_threshold = er_threshold
        self.vol_filter = vol_filter
        self.vol_pct = vol_pct

    def signals(self, df: pd.DataFrame) -> pd.Series:
        return DonchianBreakout(period=self.period, adx_filter=True,
                                adx_threshold=self.adx_threshold,
                                er_filter=self.er_filter,
                                er_threshold=self.er_threshold,
                                vol_filter=self.vol_filter,
                                vol_pct=self.vol_pct).signals(df)

class DonchianBreakout(Strategy):
    def __init__(self, period: int = 20, adx_filter: bool = False, adx_threshold: float = 25.0,
                 er_filter: bool = False, er_threshold: float = 0.3,
                 vol_filter: bool = False, vol_pct: float = 0.15):
        self.period = period
        self.adx_filter = adx_filter
        self.adx_threshold = adx_threshold
        self.er_filter = er_filter
        self.er_threshold = er_threshold
        self.vol_filter = vol_filter
        self.vol_pct = vol_pct

    def signals(self, df: pd.DataFrame) -> pd.Series:
        ch = donchian_channel(df, period=self.period)
        upper = ch['upper']
        lower = ch['lower']
        close = df['Close']
        prev_upper = upper.shift(1)
        prev_lower = lower.shift(1)
        if self.adx_filter and 'ADX' not in df.columns:
            df['ADX'] = adx(df)
        if self.er_filter and 'ER' not in df.columns:
            df['ER'] = rolling_efficiency_ratio(close)
        if self.vol_filter and 'Volatility' not in df.columns:
            df['Volatility'] = rolling_volatility(df)
        signals = pd.Series(0, index=df.index)
        position = 0
        for i in range(len(df)):
            c = close.iloc[i]
            u = prev_upper.iloc[i]
            l = prev_lower.iloc[i]
            if pd.isna(u) or pd.isna(l):
                signals.iloc[i] = 0
                continue
            if c > u:
                position = 1
            elif c < l:
                position = -1
            if position != 0:
                if self.adx_filter:
                    adx_val = df['ADX'].iloc[i] if 'ADX' in df.columns else np.nan
                    if pd.notna(adx_val) and adx_val < self.adx_threshold:
                        position = 0
                if self.er_filter and position != 0:
                    er = df['ER'].iloc[i] if 'ER' in df.columns else np.nan
                    if pd.notna(er) and er < self.er_threshold:
                        position = 0
                if self.vol_filter and position != 0:
                    vol = df['Volatility'].iloc[i] if 'Volatility' in df.columns else np.nan
                    if pd.notna(vol):
                        median_vol = df['Volatility'].median()
                        if median_vol > 0 and (vol < median_vol * (1 - self.vol_pct) or vol > median_vol * (1 + self.vol_pct)):
                            position = 0
            signals.iloc[i] = position
        return signals

class DonchianBreakoutWithER(Strategy):
    def __init__(self, period: int = 20, er_threshold: float = 0.3):
        self.period = period
        self.er_threshold = er_threshold

    def signals(self, df: pd.DataFrame) -> pd.Series:
        return DonchianBreakout(period=self.period, er_filter=True, er_threshold=self.er_threshold).signals(df)

class DonchianBreakoutDual(Strategy):
    def __init__(self, period_fast: int = 20, period_slow: int = 50):
        self.period_fast = period_fast
        self.period_slow = period_slow

    def signals(self, df: pd.DataFrame) -> pd.Series:
        ch_f = donchian_channel(df, period=self.period_fast)
        ch_s = donchian_channel(df, period=self.period_slow)
        upper_f = ch_f['upper']
        lower_f = ch_f['lower']
        upper_s = ch_s['upper']
        lower_s = ch_s['lower']
        close = df['Close']
        prev_upper_f = upper_f.shift(1)
        prev_lower_f = lower_f.shift(1)
        prev_upper_s = upper_s.shift(1)
        prev_lower_s = lower_s.shift(1)
        signals = pd.Series(0, index=df.index)
        position = 0
        for i in range(len(df)):
            c = close.iloc[i]
            uf = prev_upper_f.iloc[i]
            lf = prev_lower_f.iloc[i]
            us = prev_upper_s.iloc[i]
            ls = prev_lower_s.iloc[i]
            if pd.isna(uf) or pd.isna(lf) or pd.isna(us) or pd.isna(ls):
                signals.iloc[i] = 0
                continue
            if c > uf and c > us:
                position = 1
            elif c < lf and c < ls:
                position = -1
            else:
                position = 0
            signals.iloc[i] = position
        return signals

class TDSequentialCounterTrend(Strategy):
    def __init__(self):
        pass

    def signals(self, df: pd.DataFrame) -> pd.Series:
        buy_countdown = td_buy_countdown(df)
        sell_countdown = td_sell_countdown(df)
        signals = pd.Series(0, index=df.index)
        position = 0
        for i in range(len(df)):
            sell_complete = pd.notna(sell_countdown.iloc[i]) and sell_countdown.iloc[i] == 13
            buy_complete = pd.notna(buy_countdown.iloc[i]) and buy_countdown.iloc[i] == 13
            if sell_complete and not buy_complete:
                position = 1
            elif buy_complete and not sell_complete:
                position = -1
            signals.iloc[i] = position
        return signals

class TDComboStrategy(Strategy):
    def __init__(self):
        pass

    def signals(self, df: pd.DataFrame) -> pd.Series:
        close = df['Close']
        high = df['High']
        low = df['Low']
        signals = pd.Series(0, index=df.index)
        position = 0
        buy_setup = td_buy_setup(close) >= 9
        sell_setup = td_sell_setup(close) >= 9
        buy_cd = td_buy_countdown(df) >= 13
        sell_cd = td_sell_countdown(df) >= 13
        for i in range(len(df)):
            if position == 0:
                if sell_setup.iloc[i] and buy_cd.iloc[i]:
                    signals.iloc[i] = 1
                    position = 1
                elif buy_setup.iloc[i] and sell_cd.iloc[i]:
                    signals.iloc[i] = -1
                    position = -1
            elif position == 1:
                if buy_setup.iloc[i] and sell_cd.iloc[i]:
                    signals.iloc[i] = -1
                    position = -1
                else:
                    signals.iloc[i] = 1
            elif position == -1:
                if sell_setup.iloc[i] and buy_cd.iloc[i]:
                    signals.iloc[i] = 1
                    position = 1
                else:
                    signals.iloc[i] = -1
        return signals

class TDSequentialBreakout(Strategy):
    def __init__(self):
        pass

    def signals(self, df: pd.DataFrame) -> pd.Series:
        close = df['Close']
        signals = pd.Series(0, index=df.index)
        position = 0
        buy_setup = td_buy_setup(close)
        sell_setup = td_sell_setup(close)
        demand = td_st_demand(df)
        supply = td_st_supply(df)
        for i in range(len(df)):
            if position == 0:
                if pd.notna(buy_setup.iloc[i]) and buy_setup.iloc[i] >= 9:
                    if pd.notna(demand.iloc[i]) and close.iloc[i] > demand.iloc[i]:
                        position = 1
                elif pd.notna(sell_setup.iloc[i]) and sell_setup.iloc[i] >= 9:
                    if pd.notna(supply.iloc[i]) and close.iloc[i] < supply.iloc[i]:
                        position = -1
            elif position == 1:
                if pd.notna(sell_setup.iloc[i]) and sell_setup.iloc[i] >= 9:
                    position = -1
            elif position == -1:
                if pd.notna(buy_setup.iloc[i]) and buy_setup.iloc[i] >= 9:
                    position = 1
            signals.iloc[i] = position
        return signals
