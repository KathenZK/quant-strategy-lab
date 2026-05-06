from __future__ import annotations

from typing import Protocol

import pandas as pd

from strategy_lab.data import MarketType


class Strategy(Protocol):
    @classmethod
    def from_options(cls, options: dict[str, object] | None = None) -> "Strategy":
        ...

    @property
    def signal_name(self) -> str:
        ...

    def required_data(self) -> list[str]:
        ...

    def build_factors(self, market_data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        ...

    def version(self) -> str:
        ...

    def required_factors(self) -> list[str]:
        ...

    def required_liquidation_features(self) -> list[str]:
        ...

    def default_symbols(self, *, exchange: str, market_type: MarketType) -> list[str]:
        ...

    def build_signal_frame(self, factors: dict[str, pd.DataFrame]) -> pd.DataFrame:
        ...

    def build_weights(
        self,
        signal_frame: pd.DataFrame,
        liquidation_features: dict[str, pd.DataFrame] | None = None,
        price_frame: pd.DataFrame | None = None,
        factors: dict[str, pd.DataFrame] | None = None,
    ) -> pd.DataFrame:
        ...
