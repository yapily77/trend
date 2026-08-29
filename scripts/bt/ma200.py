"""200-day moving average crossover strategy.

Simple trend-following rule: go long when price closes above the 200-day
MA, go flat when it closes below. Serves as the core "set-and-forget"
exit discipline for retail investors.
"""
import pandas as pd
import numpy as np
from abc import ABC, abstractmethod

class MA200Crossover:
    """Long-only trend-following using a 200-day simple moving average.

    Signal logic:
        - 1 (Long) when Close > 200-day SMA
        - 0 (Flat) when Close <= 200-day SMA
    """
    def __init__(self, period: int = 200):
        self.period = period

    def signals(self, df: pd.DataFrame) -> pd.Series:
        close = df['Close']
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        ma = close.rolling(self.period).mean()
        sig = pd.Series(0, index=df.index, dtype=float)
        sig[close > ma] = 1.0
        return sig

    def features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return a diagnostic dataframe with MA, signal and price-vs-MA distance."""
        close = df['Close']
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        ma = close.rolling(self.period).mean()
        dist = (close / ma - 1.0) * 100.0
        sig = self.signals(df)
        return pd.DataFrame({
            'Close': close,
            f'MA{self.period}': ma,
            'Signal': sig,
            'PctAboveMA': dist,
        })
