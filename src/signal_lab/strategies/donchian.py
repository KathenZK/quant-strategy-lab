from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json

import pandas as pd

from signal_lab.allocators import PersistentSignalAllocator, PersistentSignalAllocatorConfig
from signal_lab.signals import DonchianBreakoutSignalConfig, DonchianBreakoutSignalModel
from signal_lab.strategies.registry import register_strategy


@dataclass(frozen=True, slots=True)
class DonchianBreakoutConfig:
    """Configuration for Donchian Commodity Trend Timing.

    The default ``donchian_breakout_14`` factor mirrors Richard Donchian's 1960
    rule on crypto daily bars (two calendar weeks). Use ``donchian_breakout_10``
    for the classic futures version based on ten trading days.
    """

    breakout_factor: str = "donchian_breakout_14"
    long_allocation: float = 1.0
    short_allocation: float = 1.0
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    cooldown_bars: int = 0

    def signal_options(self) -> dict[str, object]:
        return {
            "breakout_factor": self.breakout_factor,
        }

    def allocator_options(self) -> dict[str, object]:
        return {
            "long_allocation": self.long_allocation,
            "short_allocation": self.short_allocation,
            "stop_loss_pct": self.stop_loss_pct,
            "take_profit_pct": self.take_profit_pct,
            "cooldown_bars": self.cooldown_bars,
        }


@register_strategy("donchian_breakout")
@dataclass(slots=True)
class DonchianBreakoutStrategy:
    config: DonchianBreakoutConfig
    signal_model: DonchianBreakoutSignalModel = field(init=False)
    allocator: PersistentSignalAllocator = field(init=False)

    def __post_init__(self) -> None:
        self.signal_model = DonchianBreakoutSignalModel(
            config=DonchianBreakoutSignalConfig(**self.config.signal_options())
        )
        self.allocator = PersistentSignalAllocator(
            config=PersistentSignalAllocatorConfig(**self.config.allocator_options())
        )

    @classmethod
    def from_options(cls, options: dict[str, object] | None = None) -> "DonchianBreakoutStrategy":
        return cls(config=DonchianBreakoutConfig(**(options or {})))

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
