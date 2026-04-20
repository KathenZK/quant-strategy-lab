from __future__ import annotations

import numpy as np
import pandas as pd

from signal_lab.factors.base import FactorMetadata, PandasFactor


class TrailingReturnFactor(PandasFactor):
    def __init__(self, periods: int, price_column: str = "close") -> None:
        self.periods = periods
        self.price_column = price_column
        self.metadata = FactorMetadata(
            name=f"ret_{periods}",
            category="momentum",
            frequency="bar",
            lookback=periods + 1,
            inputs=(price_column,),
            market_types=("spot", "perp"),
            description=f"Trailing return over the last {periods} bars.",
        )

    def compute(self, frame: pd.DataFrame) -> pd.Series:
        return frame[self.price_column].pct_change(self.periods)


class BreakoutFactor(PandasFactor):
    def __init__(self, window: int, price_column: str = "close") -> None:
        self.window = window
        self.price_column = price_column
        self.metadata = FactorMetadata(
            name=f"breakout_{window}",
            category="momentum",
            frequency="bar",
            lookback=window,
            inputs=(price_column,),
            market_types=("spot", "perp"),
            description="Distance from the rolling high as a breakout score.",
        )

    def compute(self, frame: pd.DataFrame) -> pd.Series:
        rolling_high = frame[self.price_column].rolling(self.window, min_periods=self.window).max()
        return frame[self.price_column] / rolling_high - 1.0


class MovingAverageDistanceFactor(PandasFactor):
    def __init__(self, window: int, price_column: str = "close") -> None:
        self.window = window
        self.price_column = price_column
        self.metadata = FactorMetadata(
            name=f"ma_distance_{window}",
            category="mean_reversion",
            frequency="bar",
            lookback=window,
            inputs=(price_column,),
            market_types=("spot", "perp"),
            description="Relative distance between price and rolling moving average.",
        )

    def compute(self, frame: pd.DataFrame) -> pd.Series:
        moving_average = frame[self.price_column].rolling(self.window, min_periods=self.window).mean()
        return frame[self.price_column] / moving_average - 1.0


class RSIFactor(PandasFactor):
    def __init__(self, window: int = 14, price_column: str = "close") -> None:
        self.window = window
        self.price_column = price_column
        self.metadata = FactorMetadata(
            name=f"rsi_{window}",
            category="momentum",
            frequency="bar",
            lookback=window + 1,
            inputs=(price_column,),
            market_types=("spot", "perp"),
            description="Classic relative strength index.",
        )

    def compute(self, frame: pd.DataFrame) -> pd.Series:
        delta = frame[self.price_column].diff()
        gain = delta.clip(lower=0.0)
        loss = -delta.clip(upper=0.0)
        avg_gain = gain.ewm(alpha=1 / self.window, adjust=False, min_periods=self.window).mean()
        avg_loss = loss.ewm(alpha=1 / self.window, adjust=False, min_periods=self.window).mean()
        relative_strength = avg_gain / avg_loss.replace(0.0, np.nan)
        return 100.0 - (100.0 / (1.0 + relative_strength))
