from __future__ import annotations

from signal_lab.strategies.crowding import CrowdingReversalStrategy
from signal_lab.strategies.trend import TrendConfirmationStrategy


def create_strategy(signal_type: str, strategy_options: dict[str, object] | None = None):
    if signal_type == "trend_confirmation":
        return TrendConfirmationStrategy.from_options(strategy_options)
    if signal_type == "crowding_reversal":
        return CrowdingReversalStrategy.from_options(strategy_options)
    raise ValueError(f"unsupported strategy signal_type: {signal_type}")
