from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json

import pandas as pd

from strategy_lab.allocators import RankedCrossSectionalAllocator, RankedCrossSectionalAllocatorConfig
from strategy_lab.signals import MomentumRotationSignalConfig, MomentumRotationSignalModel
from strategy_lab.strategies.common import resolve_configured_symbols
from strategy_lab.strategies.registry import register_strategy


@dataclass(frozen=True, slots=True)
class MomentumRotationConfig:
    """Cross-sectional price momentum rotation.

    This strategy intentionally avoids derivatives confirmation factors so it can
    act as a clean price-only momentum baseline against trend confirmation and
    crowding reversal variants.
    """

    symbols: tuple[str, ...] = ()
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
    max_long_positions: int = 2
    max_short_positions: int = 2
    long_allocation: float = 0.5
    short_allocation: float = 0.5
    market_neutral: bool = True
    liquidation_spike_factor: str = "liq_spike_zscore"
    liquidation_ratio_factor: str = "liq_notional_vs_dollar_volume"
    liquidation_cooldown_factor: str = "event_cooldown_flag"
    max_liquidation_spike_zscore: float = 2.5
    max_liquidation_notional_ratio: float = 0.03
    liquidation_weight_scale: float = 0.25
    stop_on_event_cooldown: bool = True

    def signal_options(self) -> dict[str, object]:
        return {
            "primary_momentum_factor": self.primary_momentum_factor,
            "short_momentum_factor": self.short_momentum_factor,
            "breakout_factor": self.breakout_factor,
            "rsi_factor": self.rsi_factor,
            "volume_factor": self.volume_factor,
            "min_momentum": self.min_momentum,
            "breakout_floor": self.breakout_floor,
            "min_volume_surge": self.min_volume_surge,
            "min_long_rsi": self.min_long_rsi,
            "max_long_rsi": self.max_long_rsi,
            "min_short_rsi": self.min_short_rsi,
            "max_short_rsi": self.max_short_rsi,
            "primary_momentum_weight": self.primary_momentum_weight,
            "short_momentum_weight": self.short_momentum_weight,
            "breakout_weight": self.breakout_weight,
            "rsi_weight": self.rsi_weight,
            "volume_weight": self.volume_weight,
        }

    def allocator_options(self) -> dict[str, object]:
        return {
            "max_long_positions": self.max_long_positions,
            "max_short_positions": self.max_short_positions,
            "long_allocation": self.long_allocation,
            "short_allocation": self.short_allocation,
            "market_neutral": self.market_neutral,
            "liquidation_spike_factor": self.liquidation_spike_factor,
            "liquidation_ratio_factor": self.liquidation_ratio_factor,
            "liquidation_cooldown_factor": self.liquidation_cooldown_factor,
            "max_liquidation_spike_zscore": self.max_liquidation_spike_zscore,
            "max_liquidation_notional_ratio": self.max_liquidation_notional_ratio,
            "liquidation_weight_scale": self.liquidation_weight_scale,
            "stop_on_event_cooldown": self.stop_on_event_cooldown,
        }


@register_strategy("momentum_rotation")
@dataclass(slots=True)
class MomentumRotationStrategy:
    config: MomentumRotationConfig
    signal_model: MomentumRotationSignalModel = field(init=False)
    allocator: RankedCrossSectionalAllocator = field(init=False)

    def __post_init__(self) -> None:
        self.signal_model = MomentumRotationSignalModel(
            config=MomentumRotationSignalConfig(**self.config.signal_options())
        )
        self.allocator = RankedCrossSectionalAllocator(
            config=RankedCrossSectionalAllocatorConfig(**self.config.allocator_options())
        )

    @classmethod
    def from_options(cls, options: dict[str, object] | None = None) -> "MomentumRotationStrategy":
        return cls(config=MomentumRotationConfig(**(options or {})))

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

    def default_symbols(self, *, exchange: str, market_type) -> list[str]:
        return resolve_configured_symbols(
            self.config.symbols,
            market_type=market_type,
            default_bases=("BTC", "ETH", "SOL"),
        )

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
