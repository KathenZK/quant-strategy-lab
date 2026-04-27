from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import TypeVar, cast

from strategy_lab.strategies.base import Strategy

StrategyType = TypeVar("StrategyType", bound=type)


class StrategyRegistry:
    def __init__(self) -> None:
        self._strategy_classes: dict[str, type] = {}
        self._discovered = False

    def register(self, strategy_type: str, strategy_cls: type) -> None:
        existing = self._strategy_classes.get(strategy_type)
        if existing is not None and existing is not strategy_cls:
            raise ValueError(f"strategy already registered for strategy_type: {strategy_type}")
        self._strategy_classes[strategy_type] = strategy_cls

    def get(self, strategy_type: str) -> type:
        self.discover_builtin_strategies()
        try:
            return self._strategy_classes[strategy_type]
        except KeyError as exc:
            known = ", ".join(sorted(self._strategy_classes)) or "<none>"
            raise ValueError(f"unsupported strategy_type: {strategy_type}. known: {known}") from exc

    def create(self, strategy_type: str, strategy_params: dict[str, object] | None = None) -> Strategy:
        strategy_cls = self.get(strategy_type)
        return cast(Strategy, strategy_cls.from_options(strategy_params))

    def names(self) -> list[str]:
        self.discover_builtin_strategies()
        return sorted(self._strategy_classes)

    def discover_builtin_strategies(self) -> None:
        if self._discovered:
            return
        package_path = Path(__file__).resolve().parent
        package_name = __package__
        skip = {"__init__", "base", "common", "factory", "registry"}
        for module_info in pkgutil.iter_modules([str(package_path)]):
            if module_info.name in skip or module_info.ispkg:
                continue
            importlib.import_module(f"{package_name}.{module_info.name}")
        self._discovered = True


strategy_registry = StrategyRegistry()


def register_strategy(strategy_type: str):
    def decorator(strategy_cls: StrategyType) -> StrategyType:
        strategy_registry.register(strategy_type, strategy_cls)
        setattr(strategy_cls, "STRATEGY_TYPE", strategy_type)
        setattr(strategy_cls, "SIGNAL_TYPE", strategy_type)
        return strategy_cls

    return decorator


def create_registered_strategy(strategy_type: str, strategy_params: dict[str, object] | None = None) -> Strategy:
    return strategy_registry.create(strategy_type, strategy_params)


def list_registered_strategies() -> list[str]:
    return strategy_registry.names()
