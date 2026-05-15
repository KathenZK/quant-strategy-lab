from __future__ import annotations

import numpy as np
import pandas as pd

from strategy_lab.data.factors.base import (
    FactorMetadata,
    PandasFactor,
    register_factor_provider,
)


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


class BenchmarkReturnFactor(PandasFactor):
    def __init__(self, periods: int, price_column: str = "benchmark_close") -> None:
        self.periods = periods
        self.price_column = price_column
        self.metadata = FactorMetadata(
            name=f"benchmark_ret_{periods}",
            category="momentum",
            frequency="bar",
            lookback=periods + 1,
            inputs=(price_column,),
            market_types=("spot", "perp"),
            description=f"Benchmark trailing return over the last {periods} bars.",
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
        rolling_high = (
            frame[self.price_column].rolling(self.window, min_periods=self.window).max()
        )
        return frame[self.price_column] / rolling_high - 1.0


class DonchianBreakoutFactor(PandasFactor):
    """Richard Donchian's 1960 Commodity Trend Timing breakout signal.

    Emits +1 when the current bar's high exceeds the highest high of the prior
    ``window`` bars, -1 when the low falls below the lowest low of the prior
    ``window`` bars, and NaN otherwise so a persistent allocator can hold the
    existing position. If high/low columns are unavailable, it falls back to the
    configured price column for compatibility with narrow test frames.
    """

    def __init__(
        self,
        window: int,
        price_column: str = "close",
        high_column: str = "high",
        low_column: str = "low",
    ) -> None:
        self.window = window
        self.price_column = price_column
        self.high_column = high_column
        self.low_column = low_column
        self.metadata = FactorMetadata(
            name=f"donchian_breakout_{window}",
            category="momentum",
            frequency="bar",
            lookback=window + 1,
            inputs=(high_column, low_column),
            market_types=("spot", "perp"),
            description=(
                "Donchian breakout: +1/-1 when intrabar high/low breaks the "
                f"previous {window}-bar highest/lowest range, NaN to hold."
            ),
        )

    def compute(self, frame: pd.DataFrame) -> pd.Series:
        high = (
            frame[self.high_column]
            if self.high_column in frame
            else frame[self.price_column]
        )
        low = (
            frame[self.low_column]
            if self.low_column in frame
            else frame[self.price_column]
        )
        # Previous N-bar range excludes the current bar.
        prior_high = high.shift(1).rolling(self.window, min_periods=self.window).max()
        prior_low = low.shift(1).rolling(self.window, min_periods=self.window).min()

        signal = pd.Series(np.nan, index=high.index, dtype="float64")
        long_break = high.gt(prior_high)
        short_break = low.lt(prior_low)
        signal = signal.where(~long_break, 1.0)
        signal = signal.where(~short_break, -1.0)
        return signal


class DonchianBreakoutStrengthFactor(PandasFactor):
    """Close-confirmed Donchian breakout quality normalized by ATR percent."""

    def __init__(
        self,
        window: int,
        atr_window: int = 14,
        high_column: str = "high",
        low_column: str = "low",
        close_column: str = "close",
    ) -> None:
        self.window = window
        self.atr_window = atr_window
        self.high_column = high_column
        self.low_column = low_column
        self.close_column = close_column
        self.metadata = FactorMetadata(
            name=f"donchian_breakout_strength_{window}",
            category="momentum",
            frequency="bar",
            lookback=max(window, atr_window) + 1,
            inputs=(high_column, low_column, close_column),
            market_types=("spot", "perp"),
            description=(
                "Close-confirmed Donchian breakout distance over the previous "
                f"{window}-bar high, normalized by {atr_window}-bar ATR percent."
            ),
        )

    def compute(self, frame: pd.DataFrame) -> pd.Series:
        high = frame[self.high_column]
        low = frame[self.low_column]
        close = frame[self.close_column]
        prior_high = high.shift(1).rolling(self.window, min_periods=self.window).max()

        previous_close = close.shift(1)
        true_range = pd.concat(
            [
                high - low,
                (high - previous_close).abs(),
                (low - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = true_range.rolling(self.atr_window, min_periods=self.atr_window).mean()
        atr_pct = atr / close.replace(0.0, np.nan)

        breakout_pct = close / prior_high.replace(0.0, np.nan) - 1.0
        strength = breakout_pct / atr_pct.replace(0.0, np.nan)
        return strength.where(close.gt(prior_high))


class BullishCandleCountFactor(PandasFactor):
    def __init__(
        self, window: int, open_column: str = "open", close_column: str = "close"
    ) -> None:
        self.window = window
        self.open_column = open_column
        self.close_column = close_column
        self.metadata = FactorMetadata(
            name=f"bullish_candle_count_{window}",
            category="momentum",
            frequency="bar",
            lookback=window,
            inputs=(open_column, close_column),
            market_types=("spot", "perp"),
            description=f"Count of bullish candles over the last {window} bars.",
        )

    def compute(self, frame: pd.DataFrame) -> pd.Series:
        bullish = frame[self.close_column].gt(frame[self.open_column]).astype("float64")
        return bullish.rolling(self.window, min_periods=self.window).sum()


class BearishCandleCountFactor(PandasFactor):
    def __init__(
        self, window: int, open_column: str = "open", close_column: str = "close"
    ) -> None:
        self.window = window
        self.open_column = open_column
        self.close_column = close_column
        self.metadata = FactorMetadata(
            name=f"bearish_candle_count_{window}",
            category="momentum",
            frequency="bar",
            lookback=window,
            inputs=(open_column, close_column),
            market_types=("spot", "perp"),
            description=f"Count of bearish candles over the last {window} bars.",
        )

    def compute(self, frame: pd.DataFrame) -> pd.Series:
        bearish = frame[self.close_column].lt(frame[self.open_column]).astype("float64")
        return bearish.rolling(self.window, min_periods=self.window).sum()


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
        moving_average = (
            frame[self.price_column]
            .rolling(self.window, min_periods=self.window)
            .mean()
        )
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
        avg_gain = gain.ewm(
            alpha=1 / self.window, adjust=False, min_periods=self.window
        ).mean()
        avg_loss = loss.ewm(
            alpha=1 / self.window, adjust=False, min_periods=self.window
        ).mean()
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
        TrailingReturnFactor(periods=96),
        TrailingReturnFactor(periods=120),
        TrailingReturnFactor(periods=168),
        BenchmarkReturnFactor(periods=24),
        BenchmarkReturnFactor(periods=72),
        BullishCandleCountFactor(window=10),
        BearishCandleCountFactor(window=10),
        BreakoutFactor(window=20),
        DonchianBreakoutFactor(window=10),
        DonchianBreakoutFactor(window=12),
        DonchianBreakoutFactor(window=14),
        DonchianBreakoutFactor(window=20),
        DonchianBreakoutFactor(window=55),
        DonchianBreakoutStrengthFactor(window=20),
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
        ATRPercentFactor(window=96),
        ATRPercentFactor(window=192),
        ATRPercentFactor(window=288),
    ]
