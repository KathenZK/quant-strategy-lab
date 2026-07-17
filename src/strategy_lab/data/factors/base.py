from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
import hashlib
import importlib
import inspect
import json
from pathlib import Path
import pkgutil
import textwrap

import pandas as pd


@dataclass(frozen=True, slots=True)
class FactorMetadata:
    name: str
    category: str
    frequency: str
    lookback: int
    inputs: tuple[str, ...]
    market_types: tuple[str, ...]
    description: str
    cross_sectional: bool = False
    neutralized: bool = False
    formula: str = ""
    direction: str = "context_dependent"


class PandasFactor(ABC):
    metadata: FactorMetadata

    def parameters(self) -> dict[str, object]:
        return {
            key: value
            for key, value in vars(self).items()
            if key != "metadata"
        }

    def spec(self) -> dict[str, object]:
        return {
            "class_name": type(self).__name__,
            "metadata": asdict(self.metadata),
            "parameters": self.parameters(),
            "source_hash": self._compute_source_hash(),
        }

    def version(self) -> str:
        encoded = json.dumps(self.spec(), sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:16]

    @classmethod
    def _compute_source_hash(cls) -> str:
        """Hash the `compute` implementation so cached features invalidate when the
        algorithm changes, even if no parameter changed."""
        try:
            source = textwrap.dedent(inspect.getsource(cls.compute))
        except (OSError, TypeError):
            source = cls.__qualname__
        return hashlib.sha256(source.encode("utf-8")).hexdigest()[:12]

    @abstractmethod
    def compute(self, frame: pd.DataFrame) -> pd.Series:
        raise NotImplementedError


class FactorRegistry:
    def __init__(self) -> None:
        self._factors: dict[str, PandasFactor] = {}

    def register(self, factor: PandasFactor) -> None:
        name = factor.metadata.name
        if name in self._factors:
            raise ValueError(f"factor already registered: {name}")
        self._factors[name] = factor

    def get(self, name: str) -> PandasFactor:
        try:
            return self._factors[name]
        except KeyError as exc:
            raise KeyError(f"unknown factor: {name}") from exc

    def list_metadata(self) -> list[FactorMetadata]:
        return sorted((factor.metadata for factor in self._factors.values()), key=lambda item: item.name)

    def names(self) -> list[str]:
        return sorted(self._factors)

    def specs(self) -> dict[str, dict[str, object]]:
        return {name: self._factors[name].spec() for name in self.names()}


FactorProvider = Callable[[], Iterable[PandasFactor]]

_factor_providers: dict[str, FactorProvider] = {}
_builtin_factors_discovered = False


def register_factor_provider(name: str | None = None):
    def decorator(provider: FactorProvider) -> FactorProvider:
        provider_name = name or provider.__name__
        existing = _factor_providers.get(provider_name)
        if existing is not None and existing is not provider:
            raise ValueError(f"factor provider already registered: {provider_name}")
        _factor_providers[provider_name] = provider
        return provider

    return decorator


def discover_builtin_factor_providers() -> None:
    global _builtin_factors_discovered

    if _builtin_factors_discovered:
        return

    package_path = Path(__file__).resolve().parent
    package_name = __package__
    skip = {"__init__", "base", "engine"}

    for module_info in pkgutil.iter_modules([str(package_path)]):
        if module_info.name in skip or module_info.ispkg:
            continue
        importlib.import_module(f"{package_name}.{module_info.name}")

    _builtin_factors_discovered = True


def build_registered_factors() -> list[PandasFactor]:
    discover_builtin_factor_providers()

    factors: list[PandasFactor] = []
    for provider_name in sorted(_factor_providers):
        provided = list(_factor_providers[provider_name]())
        for factor in provided:
            if not isinstance(factor, PandasFactor):
                raise TypeError(f"factor provider {provider_name} returned non-factor object: {type(factor)!r}")
        factors.extend(provided)
    return factors


def list_registered_factor_providers() -> list[str]:
    discover_builtin_factor_providers()
    return sorted(_factor_providers)
