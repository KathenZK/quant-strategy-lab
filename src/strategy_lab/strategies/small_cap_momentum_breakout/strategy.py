from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json

import pandas as pd

from .portfolio import SmallCapMomentumBreakoutAllocator, SmallCapMomentumBreakoutAllocatorConfig
from .signal import SmallCapMomentumBreakoutSignalConfig, SmallCapMomentumBreakoutSignalModel
from strategy_lab.strategies.common import resolve_configured_symbols
from strategy_lab.strategies.registry import register_strategy


@dataclass(frozen=True, slots=True)
class SmallCapMomentumBreakoutConfig:
    """Small-cap intraday momentum breakout strategy."""

    symbols: tuple[str, ...] = ()
    breakout_factor: str = "donchian_breakout_10"
    fast_momentum_factor: str = "ret_1"
    confirmation_momentum_factor: str = "ret_4"
    volume_factor: str = "volume_surge_20"
    rsi_factor: str = "rsi_14"
    illiquidity_factor: str | None = "amihud_illiquidity"
    min_breakout_signal: float = 1.0
    min_fast_momentum: float = 0.02
    min_confirmation_momentum: float = 0.01
    min_volume_surge: float = 2.0
    min_rsi: float = 55.0
    max_rsi: float = 88.0
    max_amihud_illiquidity: float | None = None
    breakout_weight: float = 0.5
    fast_momentum_weight: float = 1.0
    confirmation_momentum_weight: float = 0.6
    volume_weight: float = 0.8
    rsi_weight: float = 0.3
    illiquidity_penalty_weight: float = 0.4
    max_positions: int = 3
    long_allocation: float = 0.30
    position_weight: float | None = None
    stop_loss_pct: float | None = 0.06
    trailing_stop_pct: float | None = 0.08
    take_profit_pct: float | None = None
    max_hold_bars: int | None = 12
    cooldown_bars: int = 6

    def signal_options(self) -> dict[str, object]:
        return {
            "breakout_factor": self.breakout_factor,
            "fast_momentum_factor": self.fast_momentum_factor,
            "confirmation_momentum_factor": self.confirmation_momentum_factor,
            "volume_factor": self.volume_factor,
            "rsi_factor": self.rsi_factor,
            "illiquidity_factor": self.illiquidity_factor,
            "min_breakout_signal": self.min_breakout_signal,
            "min_fast_momentum": self.min_fast_momentum,
            "min_confirmation_momentum": self.min_confirmation_momentum,
            "min_volume_surge": self.min_volume_surge,
            "min_rsi": self.min_rsi,
            "max_rsi": self.max_rsi,
            "max_amihud_illiquidity": self.max_amihud_illiquidity,
            "breakout_weight": self.breakout_weight,
            "fast_momentum_weight": self.fast_momentum_weight,
            "confirmation_momentum_weight": self.confirmation_momentum_weight,
            "volume_weight": self.volume_weight,
            "rsi_weight": self.rsi_weight,
            "illiquidity_penalty_weight": self.illiquidity_penalty_weight,
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
        }


@register_strategy("small_cap_momentum_breakout")
@dataclass(slots=True)
class SmallCapMomentumBreakoutStrategy:
    config: SmallCapMomentumBreakoutConfig
    signal_model: SmallCapMomentumBreakoutSignalModel = field(init=False)
    allocator: SmallCapMomentumBreakoutAllocator = field(init=False)

    def __post_init__(self) -> None:
        self.signal_model = SmallCapMomentumBreakoutSignalModel(
            config=SmallCapMomentumBreakoutSignalConfig(**self.config.signal_options())
        )
        self.allocator = SmallCapMomentumBreakoutAllocator(
            config=SmallCapMomentumBreakoutAllocatorConfig(**self.config.allocator_options())
        )

    @classmethod
    def from_options(
        cls,
        options: dict[str, object] | None = None,
    ) -> "SmallCapMomentumBreakoutStrategy":
        return cls(config=SmallCapMomentumBreakoutConfig(**(options or {})))

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
            default_bases=("DOGE", "PEPE", "FLOKI", "WIF", "BONK"),
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
