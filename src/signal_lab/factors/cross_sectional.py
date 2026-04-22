from __future__ import annotations

import pandas as pd

from signal_lab.factors.base import FactorMetadata, PandasFactor, register_factor_provider


class RelativeStrengthFactor(PandasFactor):
    def __init__(
        self,
        periods: int = 24,
        price_column: str = "close",
        benchmark_column: str = "benchmark_close",
    ) -> None:
        self.periods = periods
        self.price_column = price_column
        self.benchmark_column = benchmark_column
        self.metadata = FactorMetadata(
            name=f"relative_strength_{periods}",
            category="cross_sectional",
            frequency="bar",
            lookback=periods + 1,
            inputs=(price_column, benchmark_column),
            market_types=("spot", "perp"),
            description="Asset trailing return minus benchmark trailing return.",
            cross_sectional=True,
        )

    def compute(self, frame: pd.DataFrame) -> pd.Series:
        asset_return = frame[self.price_column].pct_change(self.periods)
        benchmark_return = frame[self.benchmark_column].pct_change(self.periods)
        return asset_return - benchmark_return


@register_factor_provider()
def builtin_cross_sectional_factors() -> list[PandasFactor]:
    return [
        RelativeStrengthFactor(periods=24),
    ]
