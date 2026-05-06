from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json

import pandas as pd

from .portfolio import RankedCrossSectionalAllocator, RankedCrossSectionalAllocatorConfig
from .signal import CrowdingReversalSignalConfig, CrowdingReversalSignalModel
from strategy_lab.strategies.common import resolve_configured_symbols
from strategy_lab.strategies.registry import register_strategy


@dataclass(frozen=True, slots=True)
class CrowdingReversalConfig:
    symbols: tuple[str, ...] = ()
    long_term_momentum_factor: str = "ret_24"
    short_term_momentum_factor: str = "ret_4"
    funding_zscore_factor: str = "funding_zscore_72"
    basis_zscore_factor: str = "basis_zscore_72"
    oi_zscore_factor: str = "oi_zscore_72"
    price_oi_regime_factor: str = "price_oi_regime_4"
    min_abs_funding_zscore: float = 1.5
    min_abs_basis_zscore: float = 1.0
    min_oi_zscore: float = 1.0
    min_long_term_trend: float = 0.01
    short_term_reversal_floor: float = 0.0
    require_regime_confirmation: bool = True
    funding_weight: float = 1.0
    basis_weight: float = 1.0
    oi_weight: float = 0.75
    long_term_weight: float = 0.75
    short_term_weight: float = 1.0
    regime_weight: float = 0.5
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
            "long_term_momentum_factor": self.long_term_momentum_factor,
            "short_term_momentum_factor": self.short_term_momentum_factor,
            "funding_zscore_factor": self.funding_zscore_factor,
            "basis_zscore_factor": self.basis_zscore_factor,
            "oi_zscore_factor": self.oi_zscore_factor,
            "price_oi_regime_factor": self.price_oi_regime_factor,
            "min_abs_funding_zscore": self.min_abs_funding_zscore,
            "min_abs_basis_zscore": self.min_abs_basis_zscore,
            "min_oi_zscore": self.min_oi_zscore,
            "min_long_term_trend": self.min_long_term_trend,
            "short_term_reversal_floor": self.short_term_reversal_floor,
            "require_regime_confirmation": self.require_regime_confirmation,
            "funding_weight": self.funding_weight,
            "basis_weight": self.basis_weight,
            "oi_weight": self.oi_weight,
            "long_term_weight": self.long_term_weight,
            "short_term_weight": self.short_term_weight,
            "regime_weight": self.regime_weight,
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


@register_strategy("crowding_reversal")
@dataclass(slots=True)
class CrowdingReversalStrategy:
    config: CrowdingReversalConfig
    signal_model: CrowdingReversalSignalModel = field(init=False)
    allocator: RankedCrossSectionalAllocator = field(init=False)

    def __post_init__(self) -> None:
        self.signal_model = CrowdingReversalSignalModel(
            config=CrowdingReversalSignalConfig(**self.config.signal_options())
        )
        self.allocator = RankedCrossSectionalAllocator(
            config=RankedCrossSectionalAllocatorConfig(**self.config.allocator_options())
        )

    @classmethod
    def from_options(cls, options: dict[str, object] | None = None) -> "CrowdingReversalStrategy":
        return cls(config=CrowdingReversalConfig(**(options or {})))

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
