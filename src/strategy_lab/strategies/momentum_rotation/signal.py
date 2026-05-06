from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json

import numpy as np
import pandas as pd

from .signal_common import cross_section_zscore


@dataclass(frozen=True, slots=True)
class MomentumRotationSignalConfig:
    primary_momentum_factor: str = "ret_24"
    short_momentum_factor: str = "ret_4"
    breakout_factor: str = "breakout_20"
    rsi_factor: str = "rsi_14"
    volume_factor: str = "volume_surge_20"
    min_momentum: float = 0.005
    breakout_floor: float = -0.01
    min_volume_surge: float = -0.5
    min_long_rsi: float = 50.0
    max_long_rsi: float = 85.0
    min_short_rsi: float = 15.0
    max_short_rsi: float = 50.0
    primary_momentum_weight: float = 1.0
    short_momentum_weight: float = 0.5
    breakout_weight: float = 0.8
    rsi_weight: float = 0.5
    volume_weight: float = 0.3


@dataclass(slots=True)
class MomentumRotationSignalModel:
    config: MomentumRotationSignalConfig

    @classmethod
    def from_options(cls, options: dict[str, object] | None = None) -> "MomentumRotationSignalModel":
        return cls(config=MomentumRotationSignalConfig(**(options or {})))

    @property
    def signal_name(self) -> str:
        return "momentum_rotation"

    def spec(self) -> dict[str, object]:
        return {
            "class_name": type(self).__name__,
            "config": asdict(self.config),
        }

    def version(self) -> str:
        encoded = json.dumps(self.spec(), sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:16]

    def required_factors(self) -> list[str]:
        return [
            self.config.primary_momentum_factor,
            self.config.short_momentum_factor,
            self.config.breakout_factor,
            self.config.rsi_factor,
            self.config.volume_factor,
        ]

    def build_signal_frame(self, factors: dict[str, pd.DataFrame]) -> pd.DataFrame:
        required = self.required_factors()
        missing = [name for name in required if name not in factors]
        if missing:
            raise ValueError(f"missing factors for momentum rotation strategy: {missing}")

        primary_momentum = factors[self.config.primary_momentum_factor]
        short_momentum = factors[self.config.short_momentum_factor]
        breakout = factors[self.config.breakout_factor]
        rsi = factors[self.config.rsi_factor]
        volume_surge = factors[self.config.volume_factor]

        score = (
            self.config.primary_momentum_weight * cross_section_zscore(primary_momentum)
            + self.config.short_momentum_weight * cross_section_zscore(short_momentum)
            + self.config.breakout_weight * cross_section_zscore(breakout)
            + self.config.rsi_weight * cross_section_zscore((rsi - 50.0) / 50.0)
            + self.config.volume_weight * cross_section_zscore(volume_surge)
        )

        long_mask = (
            (primary_momentum > self.config.min_momentum)
            & (breakout > self.config.breakout_floor)
            & (volume_surge >= self.config.min_volume_surge)
            & (rsi >= self.config.min_long_rsi)
            & (rsi <= self.config.max_long_rsi)
        )
        short_mask = (
            (primary_momentum < -self.config.min_momentum)
            & (breakout < -self.config.breakout_floor)
            & (volume_surge >= self.config.min_volume_surge)
            & (rsi >= self.config.min_short_rsi)
            & (rsi <= self.config.max_short_rsi)
        )

        signal = pd.DataFrame(np.nan, index=primary_momentum.index, columns=primary_momentum.columns, dtype="float64")
        signal = signal.where(~long_mask, score)
        signal = signal.where(~short_mask, -score.abs())
        return signal
