from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json

import pandas as pd

from .portfolio import RankedCrossSectionalAllocator, RankedCrossSectionalAllocatorConfig
from .signal import TrendConfirmationSignalConfig, TrendConfirmationSignalModel
from strategy_lab.strategies.common import resolve_configured_symbols
from strategy_lab.strategies.registry import register_strategy


@dataclass(frozen=True, slots=True)
class TrendConfirmationConfig:
    symbols: tuple[str, ...] = ()
    momentum_factor: str = "ret_24"
    breakout_factor: str = "breakout_20"
    oi_change_factor: str = "oi_change_4"
    basis_change_factor: str = "basis_change_4"
    funding_zscore_factor: str = "funding_zscore_72"
    volume_factor: str = "volume_surge_20"
    min_momentum: float = 0.0
    min_oi_change: float = 0.0
    min_basis_change: float = 0.0
    breakout_floor: float = -0.02
    min_volume_surge: float = -1.0
    max_abs_funding_zscore: float = 2.5
    momentum_weight: float = 1.0
    breakout_weight: float = 1.0
    oi_weight: float = 1.0
    basis_weight: float = 1.0
    volume_weight: float = 0.5
    funding_penalty_weight: float = 0.5
    max_long_positions: int = 3
    max_short_positions: int = 3
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
            "momentum_factor": self.momentum_factor,
            "breakout_factor": self.breakout_factor,
            "oi_change_factor": self.oi_change_factor,
            "basis_change_factor": self.basis_change_factor,
            "funding_zscore_factor": self.funding_zscore_factor,
            "volume_factor": self.volume_factor,
            "min_momentum": self.min_momentum,
            "min_oi_change": self.min_oi_change,
            "min_basis_change": self.min_basis_change,
            "breakout_floor": self.breakout_floor,
            "min_volume_surge": self.min_volume_surge,
            "max_abs_funding_zscore": self.max_abs_funding_zscore,
            "momentum_weight": self.momentum_weight,
            "breakout_weight": self.breakout_weight,
            "oi_weight": self.oi_weight,
            "basis_weight": self.basis_weight,
            "volume_weight": self.volume_weight,
            "funding_penalty_weight": self.funding_penalty_weight,
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


@register_strategy("trend_confirmation")
@dataclass(slots=True)
class TrendConfirmationStrategy:
    config: TrendConfirmationConfig
    signal_model: TrendConfirmationSignalModel = field(init=False)
    allocator: RankedCrossSectionalAllocator = field(init=False)

    def __post_init__(self) -> None:
        self.signal_model = TrendConfirmationSignalModel(
            config=TrendConfirmationSignalConfig(**self.config.signal_options())
        )
        self.allocator = RankedCrossSectionalAllocator(
            config=RankedCrossSectionalAllocatorConfig(**self.config.allocator_options())
        )

    @classmethod
    def from_options(cls, options: dict[str, object] | None = None) -> "TrendConfirmationStrategy":
        return cls(config=TrendConfirmationConfig(**(options or {})))

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
