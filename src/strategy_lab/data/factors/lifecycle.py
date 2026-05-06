from __future__ import annotations

import pandas as pd

from strategy_lab.data.factors.base import FactorMetadata, PandasFactor, register_factor_provider


class AgeBarsFactor(PandasFactor):
    def __init__(self) -> None:
        self.metadata = FactorMetadata(
            name="age_bars",
            category="lifecycle",
            frequency="bar",
            lookback=1,
            inputs=(),
            market_types=("spot", "perp"),
            description="Number of bars observed for the symbol in the local data window.",
        )

    def compute(self, frame: pd.DataFrame) -> pd.Series:
        return pd.Series(range(1, len(frame) + 1), index=frame.index, dtype="float64")


@register_factor_provider()
def builtin_lifecycle_factors() -> list[PandasFactor]:
    return [AgeBarsFactor()]
