from __future__ import annotations

from dataclasses import dataclass

from strategy_lab.strategies.base import CompositeStrategy
from strategy_lab.strategies.registry import register_strategy

from .portfolio import RankedCrossSectionalAllocator, RankedCrossSectionalAllocatorConfig
from .signal import MomentumRotationSignalConfig, MomentumRotationSignalModel


@dataclass(frozen=True, slots=True)
class MomentumRotationConfig:
    """Cross-sectional price momentum rotation."""

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
class MomentumRotationStrategy(
    CompositeStrategy[
        MomentumRotationConfig,
        MomentumRotationSignalModel,
        RankedCrossSectionalAllocator,
    ]
):
    default_symbol_bases = ("BTC", "ETH", "SOL")

    @classmethod
    def _config_cls(cls) -> type[MomentumRotationConfig]:
        return MomentumRotationConfig

    def _build_signal_model(self, config: MomentumRotationConfig) -> MomentumRotationSignalModel:
        return MomentumRotationSignalModel(
            config=MomentumRotationSignalConfig(**config.signal_options())
        )

    def _build_allocator(self, config: MomentumRotationConfig) -> RankedCrossSectionalAllocator:
        return RankedCrossSectionalAllocator(
            config=RankedCrossSectionalAllocatorConfig(**config.allocator_options())
        )
