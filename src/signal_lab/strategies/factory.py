from __future__ import annotations

from signal_lab.strategies.registry import create_registered_strategy, list_registered_strategies


def create_strategy(signal_type: str, strategy_options: dict[str, object] | None = None):
    return create_registered_strategy(signal_type, strategy_options)


def list_strategies() -> list[str]:
    return list_registered_strategies()
