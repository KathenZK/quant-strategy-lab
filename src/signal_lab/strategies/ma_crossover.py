from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json

import pandas as pd

from signal_lab.strategies.registry import register_strategy


@dataclass(frozen=True, slots=True)
class MovingAverageCrossoverConfig:
    fast_ma_factor: str = "ma_distance_30"
    slow_ma_factor: str = "ma_distance_120"
    long_allocation: float = 1.0
    short_allocation: float = 1.0


@register_strategy("ma_crossover")
@dataclass(slots=True)
class MovingAverageCrossoverStrategy:
    config: MovingAverageCrossoverConfig

    @classmethod
    def from_options(cls, options: dict[str, object] | None = None) -> "MovingAverageCrossoverStrategy":
        payload = options or {}
        return cls(config=MovingAverageCrossoverConfig(**payload))

    @property
    def signal_name(self) -> str:
        return self.SIGNAL_TYPE

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

    def required_liquidation_features(self) -> list[str]:
        return []

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

    def build_weights(
        self,
        signal_frame: pd.DataFrame,
        liquidation_features: dict[str, pd.DataFrame] | None = None,
    ) -> pd.DataFrame:
        del liquidation_features

        weights = pd.DataFrame(0.0, index=signal_frame.index, columns=signal_frame.columns)
        current = pd.Series(0.0, index=signal_frame.columns, dtype="float64")

        for ts in signal_frame.index:
            row = signal_frame.loc[ts].dropna()
            for symbol, signal in row.items():
                if signal > 0:
                    current.loc[symbol] = self.config.long_allocation
                elif signal < 0:
                    current.loc[symbol] = -self.config.short_allocation
            weights.loc[ts] = current

        return weights
