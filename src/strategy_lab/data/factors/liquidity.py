from __future__ import annotations

import pandas as pd

from strategy_lab.data.factors.base import FactorMetadata, PandasFactor, register_factor_provider


class VolumeSurgeFactor(PandasFactor):
    def __init__(self, window: int = 20, volume_column: str = "volume") -> None:
        self.window = window
        self.volume_column = volume_column
        self.metadata = FactorMetadata(
            name=f"volume_surge_{window}",
            category="liquidity",
            frequency="bar",
            lookback=window,
            inputs=(volume_column,),
            market_types=("spot", "perp"),
            description="Volume relative to its rolling average.",
        )

    def compute(self, frame: pd.DataFrame) -> pd.Series:
        rolling_mean = frame[self.volume_column].rolling(self.window, min_periods=self.window).mean()
        return frame[self.volume_column] / rolling_mean - 1.0


class AverageDollarVolumeFactor(PandasFactor):
    def __init__(self, window: int = 20, close_column: str = "close", volume_column: str = "volume") -> None:
        self.window = window
        self.close_column = close_column
        self.volume_column = volume_column
        self.metadata = FactorMetadata(
            name=f"avg_dollar_volume_{window}",
            category="liquidity",
            frequency="bar",
            lookback=window,
            inputs=(close_column, volume_column),
            market_types=("spot", "perp"),
            description="Rolling average traded notional using close times volume.",
        )

    def compute(self, frame: pd.DataFrame) -> pd.Series:
        dollar_volume = frame[self.close_column] * frame[self.volume_column]
        return dollar_volume.rolling(self.window, min_periods=self.window).mean()


class RollingDollarVolumeFactor(PandasFactor):
    def __init__(self, window: int = 24, close_column: str = "close", volume_column: str = "volume") -> None:
        self.window = window
        self.close_column = close_column
        self.volume_column = volume_column
        self.metadata = FactorMetadata(
            name=f"dollar_volume_{window}",
            category="liquidity",
            frequency="bar",
            lookback=window,
            inputs=(close_column, volume_column),
            market_types=("spot", "perp"),
            description="Rolling traded notional sum using close times volume.",
        )

    def compute(self, frame: pd.DataFrame) -> pd.Series:
        dollar_volume = frame[self.close_column] * frame[self.volume_column]
        return dollar_volume.rolling(self.window, min_periods=self.window).sum()


class AmihudIlliquidityFactor(PandasFactor):
    def __init__(self, return_column: str = "close", volume_column: str = "volume") -> None:
        self.return_column = return_column
        self.volume_column = volume_column
        self.metadata = FactorMetadata(
            name="amihud_illiquidity",
            category="liquidity",
            frequency="bar",
            lookback=2,
            inputs=(return_column, volume_column),
            market_types=("spot", "perp"),
            description="Absolute return divided by dollar volume proxy.",
        )

    def compute(self, frame: pd.DataFrame) -> pd.Series:
        returns = frame[self.return_column].pct_change().abs()
        dollar_volume = frame[self.return_column] * frame[self.volume_column]
        return returns / dollar_volume.replace(0.0, pd.NA)


class VWAPDistanceFactor(PandasFactor):
    def __init__(self, close_column: str = "close", vwap_column: str = "vwap") -> None:
        self.close_column = close_column
        self.vwap_column = vwap_column
        self.metadata = FactorMetadata(
            name="vwap_distance",
            category="liquidity",
            frequency="bar",
            lookback=1,
            inputs=(close_column, vwap_column),
            market_types=("spot", "perp"),
            description="Distance between last close and session VWAP.",
        )

    def compute(self, frame: pd.DataFrame) -> pd.Series:
        return frame[self.close_column] / frame[self.vwap_column] - 1.0


@register_factor_provider()
def builtin_liquidity_factors() -> list[PandasFactor]:
    return [
        VolumeSurgeFactor(window=20),
        AverageDollarVolumeFactor(window=20),
        RollingDollarVolumeFactor(window=1),
        RollingDollarVolumeFactor(window=24),
        AmihudIlliquidityFactor(),
        VWAPDistanceFactor(),
    ]
