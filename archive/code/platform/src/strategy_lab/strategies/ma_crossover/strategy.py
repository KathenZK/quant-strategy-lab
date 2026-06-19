from __future__ import annotations

from dataclasses import dataclass

from strategy_lab.strategies.base import CompositeStrategy
from strategy_lab.strategies.registry import register_strategy

from .portfolio import PersistentSignalAllocator, PersistentSignalAllocatorConfig
from .signal import MovingAverageCrossoverSignalConfig, MovingAverageCrossoverSignalModel


@dataclass(frozen=True, slots=True)
class MovingAverageCrossoverConfig:
    symbols: tuple[str, ...] = ()
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
class MovingAverageCrossoverStrategy(
    CompositeStrategy[
        MovingAverageCrossoverConfig,
        MovingAverageCrossoverSignalModel,
        PersistentSignalAllocator,
    ]
):
    default_symbol_bases = ("BTC",)

    @classmethod
    def _config_cls(cls) -> type[MovingAverageCrossoverConfig]:
        return MovingAverageCrossoverConfig

    def _build_signal_model(self, config: MovingAverageCrossoverConfig) -> MovingAverageCrossoverSignalModel:
        return MovingAverageCrossoverSignalModel(
            config=MovingAverageCrossoverSignalConfig(**config.signal_options())
        )

    def _build_allocator(self, config: MovingAverageCrossoverConfig) -> PersistentSignalAllocator:
        return PersistentSignalAllocator(
            config=PersistentSignalAllocatorConfig(**config.allocator_options())
        )
