from __future__ import annotations

import numpy as np
import pandas as pd

from strategy_lab.data.factors.base import FactorMetadata, PandasFactor, register_factor_provider


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


class DonchianBreakoutFactor(PandasFactor):
    """Richard Donchian's 1960 Commodity Trend Timing breakout signal.

    Emits +1 when the close exceeds the highest close of the prior ``window``
    bars, -1 when it falls below the lowest close of the prior ``window`` bars,
    and NaN otherwise so a persistent allocator can hold the existing position.
    """

    def __init__(self, window: int, price_column: str = "close") -> None:
        self.window = window
        self.price_column = price_column
        self.metadata = FactorMetadata(
            name=f"donchian_breakout_{window}",
            category="momentum",
            frequency="bar",
            lookback=window + 1,
            inputs=(price_column,),
            market_types=("spot", "perp"),
            description=(
                "Donchian breakout: +1/-1 when close breaks the previous "
                f"{window}-bar highest/lowest close, NaN to hold."
            ),
        )

    def compute(self, frame: pd.DataFrame) -> pd.Series:
        close = frame[self.price_column]
        # Previous N-bar high/low of close (exclude the current bar).
        prior_high = close.shift(1).rolling(self.window, min_periods=self.window).max()
        prior_low = close.shift(1).rolling(self.window, min_periods=self.window).min()

        signal = pd.Series(np.nan, index=close.index, dtype="float64")
        long_break = close.gt(prior_high)
        short_break = close.lt(prior_low)
        signal = signal.where(~long_break, 1.0)
        signal = signal.where(~short_break, -1.0)
        return signal


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
        rsi = 100.0 - (100.0 / (1.0 + relative_strength))
        rsi = rsi.mask((avg_loss == 0.0) & (avg_gain > 0.0), 100.0)
        rsi = rsi.mask((avg_gain == 0.0) & (avg_loss > 0.0), 0.0)
        rsi = rsi.mask((avg_gain == 0.0) & (avg_loss == 0.0), 50.0)
        return rsi


class ATRPercentFactor(PandasFactor):
    def __init__(
        self,
        window: int = 14,
        high_column: str = "high",
        low_column: str = "low",
        close_column: str = "close",
    ) -> None:
        self.window = window
        self.high_column = high_column
        self.low_column = low_column
        self.close_column = close_column
        self.metadata = FactorMetadata(
            name=f"atr_pct_{window}",
            category="volatility",
            frequency="bar",
            lookback=window + 1,
            inputs=(high_column, low_column, close_column),
            market_types=("spot", "perp"),
            description="Average true range divided by close price.",
        )

    def compute(self, frame: pd.DataFrame) -> pd.Series:
        high = frame[self.high_column]
        low = frame[self.low_column]
        close = frame[self.close_column]
        previous_close = close.shift(1)
        true_range = pd.concat(
            [
                high - low,
                (high - previous_close).abs(),
                (low - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = true_range.rolling(self.window, min_periods=self.window).mean()
        return atr / close.replace(0.0, np.nan)


@register_factor_provider()
def builtin_momentum_factors() -> list[PandasFactor]:
    return [
        TrailingReturnFactor(periods=1),
        TrailingReturnFactor(periods=4),
        TrailingReturnFactor(periods=6),
        TrailingReturnFactor(periods=12),
        TrailingReturnFactor(periods=20),
        TrailingReturnFactor(periods=24),
        TrailingReturnFactor(periods=60),
        TrailingReturnFactor(periods=72),
        TrailingReturnFactor(periods=120),
        TrailingReturnFactor(periods=168),
        BreakoutFactor(window=20),
        DonchianBreakoutFactor(window=10),
        DonchianBreakoutFactor(window=12),
        DonchianBreakoutFactor(window=14),
        DonchianBreakoutFactor(window=20),
        DonchianBreakoutFactor(window=55),
        MovingAverageDistanceFactor(window=20),
        MovingAverageDistanceFactor(window=30),
        MovingAverageDistanceFactor(window=48),
        MovingAverageDistanceFactor(window=90),
        MovingAverageDistanceFactor(window=120),
        RSIFactor(window=6),
        RSIFactor(window=12),
        RSIFactor(window=14),
        RSIFactor(window=21),
        ATRPercentFactor(window=14),
    ]
