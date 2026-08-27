import pandas as pd
import numpy as np

def calculate_equal_volatility_size(capital: float, risk_pct: float, atr_14: float) -> float:
    """
    Implements Robert Carver's Equal-Volatility position sizing.
    Formula: Position Size = (Capital * Risk_Pct) / (2 * ATR_14)
    """
    if atr_14 <= 0 or np.isnan(atr_14):
        return 0.0
    return (capital * risk_pct) / (2.0 * atr_14)
