from __future__ import annotations

from dataclasses import dataclass

from strategy_lab.strategies.base import CompositeStrategy
from strategy_lab.strategies.registry import register_strategy

from .portfolio import DonchianBreakoutAllocator, DonchianBreakoutAllocatorConfig
from .signal import DonchianBreakoutSignalConfig, DonchianBreakoutSignalModel


@dataclass(frozen=True, slots=True)
class DonchianBreakoutConfig:
    """Configuration for Donchian Commodity Trend Timing."""

    symbols: tuple[str, ...] = ()
    breakout_factor: str = "donchian_breakout_14"
    long_allocation: float = 1.0
    short_allocation: float = 1.0
    trend_factor: str | None = None
    trend_tolerance: float = 0.0
    exit_on_trend_reversal: bool = True
    stop_loss_pct: float | None = None
    trailing_stop_pct: float | None = None
    take_profit_pct: float | None = None
    cooldown_bars: int = 0
    risk_budget_pct: float | None = None
    max_pyramids: int = 0
    pyramid_step_pct: float = 0.05
    pyramid_unit_scale: float = 0.5

    def signal_options(self) -> dict[str, object]:
        return {
            "breakout_factor": self.breakout_factor,
            "trend_factor": self.trend_factor,
            "trend_tolerance": self.trend_tolerance,
        }

    def allocator_options(self) -> dict[str, object]:
        return {
            "long_allocation": self.long_allocation,
            "short_allocation": self.short_allocation,
            "trend_factor": self.trend_factor,
            "trend_tolerance": self.trend_tolerance,
            "exit_on_trend_reversal": self.exit_on_trend_reversal,
            "stop_loss_pct": self.stop_loss_pct,
            "trailing_stop_pct": self.trailing_stop_pct,
            "take_profit_pct": self.take_profit_pct,
            "cooldown_bars": self.cooldown_bars,
            "risk_budget_pct": self.risk_budget_pct,
            "max_pyramids": self.max_pyramids,
            "pyramid_step_pct": self.pyramid_step_pct,
            "pyramid_unit_scale": self.pyramid_unit_scale,
        }


@register_strategy("donchian_breakout")
class DonchianBreakoutStrategy(
    CompositeStrategy[
        DonchianBreakoutConfig,
        DonchianBreakoutSignalModel,
        DonchianBreakoutAllocator,
    ]
):
    default_symbol_bases = ("BTC",)

    @classmethod
    def _config_cls(cls) -> type[DonchianBreakoutConfig]:
        return DonchianBreakoutConfig

    def _build_signal_model(self, config: DonchianBreakoutConfig) -> DonchianBreakoutSignalModel:
        return DonchianBreakoutSignalModel(
            config=DonchianBreakoutSignalConfig(**config.signal_options())
        )

    def _build_allocator(self, config: DonchianBreakoutConfig) -> DonchianBreakoutAllocator:
        return DonchianBreakoutAllocator(
            config=DonchianBreakoutAllocatorConfig(**config.allocator_options())
        )
