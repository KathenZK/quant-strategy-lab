from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json

import pandas as pd


@dataclass(frozen=True, slots=True)
class DonchianBreakoutSignalConfig:
    breakout_factor: str = "donchian_breakout_14"


@dataclass(slots=True)
class DonchianBreakoutSignalModel:
    """Donchian Commodity Trend Timing signal.

    Consumes a pre-computed ``donchian_breakout_*`` factor that already encodes
    +1 / -1 / NaN for long / short / hold. The signal model is intentionally
    thin so it can be paired with the :class:`PersistentSignalAllocator`.
    """

    config: DonchianBreakoutSignalConfig

    @classmethod
    def from_options(cls, options: dict[str, object] | None = None) -> "DonchianBreakoutSignalModel":
        return cls(config=DonchianBreakoutSignalConfig(**(options or {})))

    @property
    def signal_name(self) -> str:
        return "donchian_breakout"

    def spec(self) -> dict[str, object]:
        return {
            "class_name": type(self).__name__,
            "config": asdict(self.config),
        }

    def version(self) -> str:
        encoded = json.dumps(self.spec(), sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:16]

    def required_factors(self) -> list[str]:
        return [self.config.breakout_factor]

    def build_signal_frame(self, factors: dict[str, pd.DataFrame]) -> pd.DataFrame:
        factor_name = self.config.breakout_factor
        if factor_name not in factors:
            raise ValueError(f"missing factor for donchian breakout strategy: {factor_name}")
        return factors[factor_name].astype("float64").copy()
