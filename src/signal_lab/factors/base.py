from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
import hashlib
import json

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
        }

    def version(self) -> str:
        encoded = json.dumps(self.spec(), sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:16]

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
