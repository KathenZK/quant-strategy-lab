from __future__ import annotations

from typing import Protocol

import pandas as pd


class Allocator(Protocol):
    @classmethod
    def from_options(cls, options: dict[str, object] | None = None) -> "Allocator":
        ...

    def spec(self) -> dict[str, object]:
        ...

    def version(self) -> str:
        ...

    def required_risk_features(self) -> list[str]:
        ...

    def build_weights(
        self,
        signal_frame: pd.DataFrame,
        risk_features: dict[str, pd.DataFrame] | None = None,
        price_frame: pd.DataFrame | None = None,
        factor_frames: dict[str, pd.DataFrame] | None = None,
    ) -> pd.DataFrame:
        ...
