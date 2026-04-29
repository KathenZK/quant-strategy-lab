from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json

import pandas as pd

from strategy_lab.allocators import SmallCapMomentumBreakoutAllocator, SmallCapMomentumBreakoutAllocatorConfig
from strategy_lab.signals import SpotCtaTrendSignalConfig, SpotCtaTrendSignalModel
from strategy_lab.strategies.registry import register_strategy


@dataclass(frozen=True, slots=True)
class SpotCtaTrendConfig:
    breakout_factor: str = "donchian_breakout_20"
    primary_momentum_factor: str = "ret_72"
    confirmation_momentum_factor: str = "ret_24"
    trend_factor: str = "ma_distance_120"
    volume_factor: str = "volume_surge_20"
    rsi_factor: str = "rsi_14"
    illiquidity_factor: str | None = "amihud_illiquidity"
    volatility_factor: str | None = "atr_pct_14"
    min_breakout_signal: float = 1.0
    min_primary_momentum: float = 0.03
    min_confirmation_momentum: float = 0.0
    min_trend_distance: float = 0.0
    min_volume_surge: float = -0.25
    min_rsi: float = 50.0
    max_rsi: float = 86.0
    max_amihud_illiquidity: float | None = None
    max_atr_pct: float | None = 0.30
    breakout_weight: float = 0.8
    primary_momentum_weight: float = 1.0
    confirmation_momentum_weight: float = 0.6
    trend_weight: float = 0.8
    volume_weight: float = 0.3
    rsi_weight: float = 0.2
    illiquidity_penalty_weight: float = 0.4
    volatility_penalty_weight: float = 0.3
    max_positions: int = 10
    long_allocation: float = 0.70
    position_weight: float | None = None
    stop_loss_pct: float | None = 0.10
    trailing_stop_pct: float | None = 0.18
    take_profit_pct: float | None = None
    max_hold_bars: int | None = None
    cooldown_bars: int = 6
    exit_on_signal_loss: bool = True
    exit_signal_threshold: float = 0.0
    max_rank_hold_positions: int | None = 20

    def signal_options(self) -> dict[str, object]:
        return {
            "breakout_factor": self.breakout_factor,
            "primary_momentum_factor": self.primary_momentum_factor,
            "confirmation_momentum_factor": self.confirmation_momentum_factor,
            "trend_factor": self.trend_factor,
            "volume_factor": self.volume_factor,
            "rsi_factor": self.rsi_factor,
            "illiquidity_factor": self.illiquidity_factor,
            "volatility_factor": self.volatility_factor,
            "min_breakout_signal": self.min_breakout_signal,
            "min_primary_momentum": self.min_primary_momentum,
            "min_confirmation_momentum": self.min_confirmation_momentum,
            "min_trend_distance": self.min_trend_distance,
            "min_volume_surge": self.min_volume_surge,
            "min_rsi": self.min_rsi,
            "max_rsi": self.max_rsi,
            "max_amihud_illiquidity": self.max_amihud_illiquidity,
            "max_atr_pct": self.max_atr_pct,
            "breakout_weight": self.breakout_weight,
            "primary_momentum_weight": self.primary_momentum_weight,
            "confirmation_momentum_weight": self.confirmation_momentum_weight,
            "trend_weight": self.trend_weight,
            "volume_weight": self.volume_weight,
            "rsi_weight": self.rsi_weight,
            "illiquidity_penalty_weight": self.illiquidity_penalty_weight,
            "volatility_penalty_weight": self.volatility_penalty_weight,
        }

    def allocator_options(self) -> dict[str, object]:
        return {
            "max_positions": self.max_positions,
            "long_allocation": self.long_allocation,
            "position_weight": self.position_weight,
            "stop_loss_pct": self.stop_loss_pct,
            "trailing_stop_pct": self.trailing_stop_pct,
            "take_profit_pct": self.take_profit_pct,
            "max_hold_bars": self.max_hold_bars,
            "cooldown_bars": self.cooldown_bars,
            "exit_on_signal_loss": self.exit_on_signal_loss,
            "exit_signal_threshold": self.exit_signal_threshold,
            "max_rank_hold_positions": self.max_rank_hold_positions,
        }


@register_strategy("spot_cta_trend")
@dataclass(slots=True)
class SpotCtaTrendStrategy:
    config: SpotCtaTrendConfig
    signal_model: SpotCtaTrendSignalModel = field(init=False)
    allocator: SmallCapMomentumBreakoutAllocator = field(init=False)

    def __post_init__(self) -> None:
        self.signal_model = SpotCtaTrendSignalModel(
            config=SpotCtaTrendSignalConfig(**self.config.signal_options())
        )
        self.allocator = SmallCapMomentumBreakoutAllocator(
            config=SmallCapMomentumBreakoutAllocatorConfig(**self.config.allocator_options())
        )

    @classmethod
    def from_options(cls, options: dict[str, object] | None = None) -> "SpotCtaTrendStrategy":
        return cls(config=SpotCtaTrendConfig(**(options or {})))

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
