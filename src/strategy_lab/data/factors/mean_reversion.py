from __future__ import annotations

import pandas as pd

from strategy_lab.data.factors.base import FactorMetadata, PandasFactor, register_factor_provider


class ZScoreFactor(PandasFactor):
    def __init__(self, window: int = 20, price_column: str = "close") -> None:
        self.window = window
        self.price_column = price_column
        self.metadata = FactorMetadata(
            name=f"zscore_{window}",
            category="mean_reversion",
            frequency="bar",
            lookback=window,
            inputs=(price_column,),
            market_types=("spot", "perp"),
            description="Rolling z-score of price versus its local mean.",
        )

    def compute(self, frame: pd.DataFrame) -> pd.Series:
        rolling_mean = frame[self.price_column].rolling(self.window, min_periods=self.window).mean()
        rolling_std = frame[self.price_column].rolling(self.window, min_periods=self.window).std()
        return (frame[self.price_column] - rolling_mean) / rolling_std


class BollingerDistanceFactor(PandasFactor):
    def __init__(self, window: int = 20, num_std: float = 2.0, price_column: str = "close") -> None:
        self.window = window
        self.num_std = num_std
        self.price_column = price_column
        self.metadata = FactorMetadata(
            name=f"bollinger_distance_{window}",
            category="mean_reversion",
            frequency="bar",
            lookback=window,
            inputs=(price_column,),
            market_types=("spot", "perp"),
            description="Signed distance from Bollinger band midpoint in band-width units.",
        )

    def compute(self, frame: pd.DataFrame) -> pd.Series:
        rolling_mean = frame[self.price_column].rolling(self.window, min_periods=self.window).mean()
        rolling_std = frame[self.price_column].rolling(self.window, min_periods=self.window).std()
        band_width = self.num_std * rolling_std
        return (frame[self.price_column] - rolling_mean) / band_width


@register_factor_provider()
def builtin_mean_reversion_factors() -> list[PandasFactor]:
    return [
        ZScoreFactor(window=20),
        BollingerDistanceFactor(window=20),
    ]
