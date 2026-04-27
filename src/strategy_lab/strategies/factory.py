from __future__ import annotations

from strategy_lab.strategies.registry import create_registered_strategy, list_registered_strategies


def create_strategy(strategy_type: str, strategy_params: dict[str, object] | None = None):
    return create_registered_strategy(strategy_type, strategy_params)


def list_strategies() -> list[str]:
    return list_registered_strategies()
