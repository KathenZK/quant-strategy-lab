from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json

import pandas as pd


@dataclass(frozen=True, slots=True)
class MovingAverageCrossoverSignalConfig:
    fast_ma_factor: str = "ma_distance_30"
    slow_ma_factor: str = "ma_distance_120"


@dataclass(slots=True)
class MovingAverageCrossoverSignalModel:
    config: MovingAverageCrossoverSignalConfig

    @classmethod
    def from_options(cls, options: dict[str, object] | None = None) -> "MovingAverageCrossoverSignalModel":
        return cls(config=MovingAverageCrossoverSignalConfig(**(options or {})))

    @property
    def signal_name(self) -> str:
        return "ma_crossover"

    def spec(self) -> dict[str, object]:
        return {
            "class_name": type(self).__name__,
            "config": asdict(self.config),
        }

    def version(self) -> str:
        encoded = json.dumps(self.spec(), sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:16]

    def required_factors(self) -> list[str]:
        return [self.config.fast_ma_factor, self.config.slow_ma_factor]

    def build_signal_frame(self, factors: dict[str, pd.DataFrame]) -> pd.DataFrame:
        required = self.required_factors()
        missing = [name for name in required if name not in factors]
        if missing:
            raise ValueError(f"missing factors for moving average crossover strategy: {missing}")

        fast_distance = factors[self.config.fast_ma_factor]
        slow_distance = factors[self.config.slow_ma_factor]

        # Because `ma_distance = close / moving_average - 1`, a smaller distance
        # implies a higher moving average when the price is positive.
        spread = slow_distance - fast_distance
        previous_spread = spread.shift(1)

        initial_long = spread.gt(0.0) & previous_spread.isna()
        initial_short = spread.lt(0.0) & previous_spread.isna()
        cross_up = spread.gt(0.0) & previous_spread.le(0.0)
        cross_down = spread.lt(0.0) & previous_spread.ge(0.0)

        signal = pd.DataFrame(index=spread.index, columns=spread.columns, dtype="float64")
        signal = signal.where(~initial_long, 1.0)
        signal = signal.where(~initial_short, -1.0)
        signal = signal.where(~cross_up, 1.0)
        signal = signal.where(~cross_down, -1.0)
        return signal
