from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import TypeVar, cast

from signal_lab.strategies.base import Strategy

StrategyType = TypeVar("StrategyType", bound=type)


class StrategyRegistry:
    def __init__(self) -> None:
        self._strategy_classes: dict[str, type] = {}
        self._discovered = False

    def register(self, signal_type: str, strategy_cls: type) -> None:
        existing = self._strategy_classes.get(signal_type)
        if existing is not None and existing is not strategy_cls:
            raise ValueError(f"strategy already registered for signal_type: {signal_type}")
        self._strategy_classes[signal_type] = strategy_cls

    def get(self, signal_type: str) -> type:
        self.discover_builtin_strategies()
        try:
            return self._strategy_classes[signal_type]
        except KeyError as exc:
            known = ", ".join(sorted(self._strategy_classes)) or "<none>"
            raise ValueError(f"unsupported strategy signal_type: {signal_type}. known: {known}") from exc

    def create(self, signal_type: str, strategy_options: dict[str, object] | None = None) -> Strategy:
        strategy_cls = self.get(signal_type)
        return cast(Strategy, strategy_cls.from_options(strategy_options))

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


def register_strategy(signal_type: str):
    def decorator(strategy_cls: StrategyType) -> StrategyType:
        strategy_registry.register(signal_type, strategy_cls)
        setattr(strategy_cls, "SIGNAL_TYPE", signal_type)
        return strategy_cls

    return decorator


def create_registered_strategy(signal_type: str, strategy_options: dict[str, object] | None = None) -> Strategy:
    return strategy_registry.create(signal_type, strategy_options)


def list_registered_strategies() -> list[str]:
    return strategy_registry.names()
