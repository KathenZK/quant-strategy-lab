from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json

import pandas as pd

from signal_lab.allocators import PersistentSignalAllocator, PersistentSignalAllocatorConfig
from signal_lab.signals import MovingAverageCrossoverSignalConfig, MovingAverageCrossoverSignalModel
from signal_lab.strategies.registry import register_strategy


@dataclass(frozen=True, slots=True)
class MovingAverageCrossoverConfig:
    fast_ma_factor: str = "ma_distance_30"
    slow_ma_factor: str = "ma_distance_120"
    long_allocation: float = 1.0
    short_allocation: float = 1.0
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    cooldown_bars: int = 0
    min_ma_gap_ratio: float = 0.0
    min_slow_ma_slope: float = 0.0
    slope_lookback: int = 10
    exit_on_choppy: bool = True

    def signal_options(self) -> dict[str, object]:
        return {
            "fast_ma_factor": self.fast_ma_factor,
            "slow_ma_factor": self.slow_ma_factor,
        }

    def allocator_options(self) -> dict[str, object]:
        return {
            "fast_ma_factor": self.fast_ma_factor,
            "slow_ma_factor": self.slow_ma_factor,
            "long_allocation": self.long_allocation,
            "short_allocation": self.short_allocation,
            "stop_loss_pct": self.stop_loss_pct,
            "take_profit_pct": self.take_profit_pct,
            "cooldown_bars": self.cooldown_bars,
            "min_ma_gap_ratio": self.min_ma_gap_ratio,
            "min_slow_ma_slope": self.min_slow_ma_slope,
            "slope_lookback": self.slope_lookback,
            "exit_on_choppy": self.exit_on_choppy,
        }


@register_strategy("ma_crossover")
@dataclass(slots=True)
class MovingAverageCrossoverStrategy:
    config: MovingAverageCrossoverConfig
    signal_model: MovingAverageCrossoverSignalModel = field(init=False)
    allocator: PersistentSignalAllocator = field(init=False)

    def __post_init__(self) -> None:
        self.signal_model = MovingAverageCrossoverSignalModel(
            config=MovingAverageCrossoverSignalConfig(**self.config.signal_options())
        )
        self.allocator = PersistentSignalAllocator(
            config=PersistentSignalAllocatorConfig(**self.config.allocator_options())
        )

    @classmethod
    def from_options(cls, options: dict[str, object] | None = None) -> "MovingAverageCrossoverStrategy":
        return cls(config=MovingAverageCrossoverConfig(**(options or {})))

    @property
    def signal_name(self) -> str:
        return self.SIGNAL_TYPE

    def spec(self) -> dict[str, object]:
        return {
            "class_name": type(self).__name__,
            "signal_model": self.signal_model.spec(),
            "allocator": self.allocator.spec(),
        }

    def version(self) -> str:
        encoded = json.dumps(self.spec(), sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:16]

    def required_factors(self) -> list[str]:
        return self.signal_model.required_factors()

    def required_liquidation_features(self) -> list[str]:
        return self.allocator.required_risk_features()

    def build_signal_frame(self, factors: dict[str, pd.DataFrame]) -> pd.DataFrame:
        return self.signal_model.build_signal_frame(factors)

    def build_weights(
        self,
        signal_frame: pd.DataFrame,
        liquidation_features: dict[str, pd.DataFrame] | None = None,
        price_frame: pd.DataFrame | None = None,
        factors: dict[str, pd.DataFrame] | None = None,
    ) -> pd.DataFrame:
        return self.allocator.build_weights(
            signal_frame,
            risk_features=liquidation_features,
            price_frame=price_frame,
            factor_frames=factors,
        )
