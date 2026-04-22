from __future__ import annotations

from typing import Protocol

import pandas as pd


class SignalModel(Protocol):
    @classmethod
    def from_options(cls, options: dict[str, object] | None = None) -> "SignalModel":
        ...

    @property
    def signal_name(self) -> str:
        ...

    def spec(self) -> dict[str, object]:
        ...

    def version(self) -> str:
        ...

    def required_factors(self) -> list[str]:
        ...

    def build_signal_frame(self, factors: dict[str, pd.DataFrame]) -> pd.DataFrame:
        ...
