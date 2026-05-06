from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
import hashlib
import json
from typing import Generic, Protocol, TypeVar

import pandas as pd

from strategy_lab.data import MarketType
from strategy_lab.strategies.common import resolve_configured_symbols


class Strategy(Protocol):
    @classmethod
    def from_options(cls, options: dict[str, object] | None = None) -> "Strategy":
        ...

    @property
    def signal_name(self) -> str:
        ...

    def required_data(self) -> list[str]:
        ...

    def build_factors(self, market_data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        ...

    def version(self) -> str:
        ...

    def required_factors(self) -> list[str]:
        ...

    def required_liquidation_features(self) -> list[str]:
        ...

    def default_symbols(self, *, exchange: str, market_type: MarketType) -> list[str]:
        ...

    def build_signal_frame(self, factors: dict[str, pd.DataFrame]) -> pd.DataFrame:
        ...

    def build_weights(
        self,
        signal_frame: pd.DataFrame,
        liquidation_features: dict[str, pd.DataFrame] | None = None,
        price_frame: pd.DataFrame | None = None,
        factors: dict[str, pd.DataFrame] | None = None,
    ) -> pd.DataFrame:
        ...


ConfigT = TypeVar("ConfigT")
SignalModelT = TypeVar("SignalModelT")
AllocatorT = TypeVar("AllocatorT")


class CompositeStrategy(ABC, Generic[ConfigT, SignalModelT, AllocatorT]):
    """Reusable scaffold for strategies built from a SignalModel + Allocator pair.

    Subclasses only need to declare the Config dataclass and the two factory methods.
    Common boilerplate (`from_options`, `spec`, `version`, factor/feature requirements,
    `build_signal_frame` / `build_weights`, default symbol resolution) is provided here.
    """

    default_symbol_bases: Sequence[str] = ("BTC",)
    SIGNAL_TYPE: str = ""

    def __init__(self, config: ConfigT) -> None:
        self.config = config
        self._signal_model: SignalModelT = self._build_signal_model(config)
        self._allocator: AllocatorT = self._build_allocator(config)

    # --- factory methods subclasses must override -------------------------------------

    @classmethod
    @abstractmethod
    def _config_cls(cls) -> type[ConfigT]:
        ...

    @abstractmethod
    def _build_signal_model(self, config: ConfigT) -> SignalModelT:
        ...

    @abstractmethod
    def _build_allocator(self, config: ConfigT) -> AllocatorT:
        ...

    # --- public Strategy protocol -----------------------------------------------------

    @classmethod
    def from_options(cls, options: dict[str, object] | None = None):
        return cls(config=cls._config_cls()(**(options or {})))

    @property
    def signal_model(self) -> SignalModelT:
        return self._signal_model

    @property
    def allocator(self) -> AllocatorT:
        return self._allocator

    @property
    def signal_name(self) -> str:
        return self.SIGNAL_TYPE

    def spec(self) -> dict[str, object]:
        return {
            "class_name": type(self).__name__,
            "signal_model": self._signal_model.spec(),
            "allocator": self._allocator.spec(),
        }

    def version(self) -> str:
        encoded = json.dumps(self.spec(), sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:16]

    def required_factors(self) -> list[str]:
        return self._signal_model.required_factors()

    def required_liquidation_features(self) -> list[str]:
        return self._allocator.required_risk_features()

    def default_symbols(self, *, exchange: str, market_type: MarketType) -> list[str]:
        del exchange
        return resolve_configured_symbols(
            getattr(self.config, "symbols", ()),
            market_type=market_type,
            default_bases=self.default_symbol_bases,
        )

    def build_signal_frame(self, factors: dict[str, pd.DataFrame]) -> pd.DataFrame:
        return self._signal_model.build_signal_frame(factors)

    def build_weights(
        self,
        signal_frame: pd.DataFrame,
        liquidation_features: dict[str, pd.DataFrame] | None = None,
        price_frame: pd.DataFrame | None = None,
        factors: dict[str, pd.DataFrame] | None = None,
    ) -> pd.DataFrame:
        return self._allocator.build_weights(
            signal_frame,
            risk_features=liquidation_features,
            price_frame=price_frame,
            factor_frames=factors,
        )
