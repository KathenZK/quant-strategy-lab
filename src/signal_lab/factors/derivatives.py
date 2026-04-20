from __future__ import annotations

import numpy as np
import pandas as pd

from signal_lab.factors.base import FactorMetadata, PandasFactor


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
