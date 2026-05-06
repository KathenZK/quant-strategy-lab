from __future__ import annotations

import numpy as np
import pandas as pd

from strategy_lab.data.factors.base import FactorMetadata, PandasFactor, register_factor_provider


def _rolling_zscore(series: pd.Series, window: int) -> pd.Series:
    rolling_mean = series.rolling(window, min_periods=window).mean()
    rolling_std = series.rolling(window, min_periods=window).std()
    return (series - rolling_mean) / rolling_std.replace(0.0, np.nan)


class FundingRateFactor(PandasFactor):
    def __init__(self, column: str = "funding_rate") -> None:
        self.column = column
        self.metadata = FactorMetadata(
            name="funding_rate",
            category="derivatives",
            frequency="bar",
            lookback=1,
            inputs=(column,),
            market_types=("perp",),
            description="Raw funding rate, useful for crowdedness and carry analysis.",
        )

    def compute(self, frame: pd.DataFrame) -> pd.Series:
        return frame[self.column]


class FundingRateZScoreFactor(PandasFactor):
    def __init__(self, window: int = 72, column: str = "funding_rate") -> None:
        self.window = window
        self.column = column
        self.metadata = FactorMetadata(
            name=f"funding_zscore_{window}",
            category="derivatives",
            frequency="bar",
            lookback=window,
            inputs=(column,),
            market_types=("perp",),
            description=f"Rolling z-score of funding rate over {window} bars.",
        )

    def compute(self, frame: pd.DataFrame) -> pd.Series:
        return _rolling_zscore(frame[self.column], self.window)


class OpenInterestChangeFactor(PandasFactor):
    def __init__(self, periods: int = 4, column: str = "open_interest") -> None:
        self.periods = periods
        self.column = column
        self.metadata = FactorMetadata(
            name=f"oi_change_{periods}",
            category="derivatives",
            frequency="bar",
            lookback=periods + 1,
            inputs=(column,),
            market_types=("perp",),
            description=f"Open interest percentage change over {periods} bars.",
        )

    def compute(self, frame: pd.DataFrame) -> pd.Series:
        return frame[self.column].pct_change(self.periods)


class OpenInterestZScoreFactor(PandasFactor):
    def __init__(self, window: int = 72, column: str = "open_interest") -> None:
        self.window = window
        self.column = column
        self.metadata = FactorMetadata(
            name=f"oi_zscore_{window}",
            category="derivatives",
            frequency="bar",
            lookback=window,
            inputs=(column,),
            market_types=("perp",),
            description=f"Rolling z-score of open interest over {window} bars.",
        )

    def compute(self, frame: pd.DataFrame) -> pd.Series:
        return _rolling_zscore(frame[self.column], self.window)


class BasisFactor(PandasFactor):
    def __init__(self, column: str = "basis") -> None:
        self.column = column
        self.metadata = FactorMetadata(
            name="basis",
            category="derivatives",
            frequency="bar",
            lookback=1,
            inputs=(column,),
            market_types=("perp",),
            description="Raw futures basis level.",
        )

    def compute(self, frame: pd.DataFrame) -> pd.Series:
        return frame[self.column]


class BasisChangeFactor(PandasFactor):
    def __init__(self, periods: int = 4, column: str = "basis") -> None:
        self.periods = periods
        self.column = column
        self.metadata = FactorMetadata(
            name=f"basis_change_{periods}",
            category="derivatives",
            frequency="bar",
            lookback=periods + 1,
            inputs=(column,),
            market_types=("perp",),
            description=f"Percentage change in basis over {periods} bars.",
        )

    def compute(self, frame: pd.DataFrame) -> pd.Series:
        return frame[self.column].pct_change(self.periods)


class BasisZScoreFactor(PandasFactor):
    def __init__(self, window: int = 72, column: str = "basis") -> None:
        self.window = window
        self.column = column
        self.metadata = FactorMetadata(
            name=f"basis_zscore_{window}",
            category="derivatives",
            frequency="bar",
            lookback=window,
            inputs=(column,),
            market_types=("perp",),
            description=f"Rolling z-score of basis level over {window} bars.",
        )

    def compute(self, frame: pd.DataFrame) -> pd.Series:
        return _rolling_zscore(frame[self.column], self.window)


class PriceOpenInterestRegimeFactor(PandasFactor):
    def __init__(
        self,
        periods: int = 4,
        price_column: str = "close",
        oi_column: str = "open_interest",
    ) -> None:
        self.periods = periods
        self.price_column = price_column
        self.oi_column = oi_column
        self.metadata = FactorMetadata(
            name=f"price_oi_regime_{periods}",
            category="derivatives",
            frequency="bar",
            lookback=periods + 1,
            inputs=(price_column, oi_column),
            market_types=("perp",),
            description="Numeric regime based on joint price and open interest changes.",
        )

    def compute(self, frame: pd.DataFrame) -> pd.Series:
        price_change = frame[self.price_column].pct_change(self.periods)
        oi_change = frame[self.oi_column].pct_change(self.periods)
        conditions = [
            (price_change > 0) & (oi_change > 0),
            (price_change > 0) & (oi_change <= 0),
            (price_change <= 0) & (oi_change > 0),
            (price_change <= 0) & (oi_change <= 0),
        ]
        values = [2.0, 1.0, -2.0, -1.0]
        regime = np.select(conditions, values, default=np.nan)
        return pd.Series(regime, index=frame.index, name=self.metadata.name)


@register_factor_provider()
def builtin_derivatives_factors() -> list[PandasFactor]:
    return [
        FundingRateFactor(),
        FundingRateZScoreFactor(window=72),
        OpenInterestChangeFactor(periods=4),
        OpenInterestZScoreFactor(window=72),
        BasisFactor(),
        BasisChangeFactor(periods=4),
        BasisZScoreFactor(window=72),
        PriceOpenInterestRegimeFactor(periods=4),
    ]
