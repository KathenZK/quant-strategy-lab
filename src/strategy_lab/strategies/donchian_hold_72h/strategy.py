from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json

import pandas as pd

from strategy_lab.data import MarketType
from strategy_lab.strategies.registry import register_strategy


@dataclass(frozen=True, slots=True)
class DonchianHold72hConfig:
    symbols: tuple[str, ...] = ()
    breakout_factor: str = "donchian_breakout_20"
    hold_bars: int = 72
    max_positions: int = 1
    long_allocation: float = 1.0


@register_strategy("donchian_hold_72h")
@dataclass(slots=True)
class DonchianHold72hStrategy:
    """Isolated research strategy: enter on Donchian20 breakout, exit after 72 bars."""

    config: DonchianHold72hConfig

    @classmethod
    def from_options(cls, options: dict[str, object] | None = None) -> "DonchianHold72hStrategy":
        return cls(config=DonchianHold72hConfig(**(options or {})))

    @property
    def signal_name(self) -> str:
        return self.SIGNAL_TYPE

    def spec(self) -> dict[str, object]:
        return {"class_name": type(self).__name__, "config": asdict(self.config)}

    def version(self) -> str:
        encoded = json.dumps(self.spec(), sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:16]

    def required_factors(self) -> list[str]:
        return [self.config.breakout_factor]

    def required_liquidation_features(self) -> list[str]:
        return []

    def default_symbols(self, *, exchange: str, market_type: MarketType) -> list[str]:
        del exchange
        if self.config.symbols:
            return [symbol.upper() for symbol in self.config.symbols]
        if market_type == MarketType.SPOT:
            return ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        return ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]

    def build_signal_frame(self, factors: dict[str, pd.DataFrame]) -> pd.DataFrame:
        factor_name = self.config.breakout_factor
        if factor_name not in factors:
            raise ValueError(f"missing factor for donchian_hold_72h strategy: {factor_name}")
        breakout = factors[factor_name].astype("float64")
        signal = pd.DataFrame(0.0, index=breakout.index, columns=breakout.columns)
        signal = signal.where(~breakout.gt(0.0), 1.0)
        return signal

    def build_weights(
        self,
        signal_frame: pd.DataFrame,
        liquidation_features: dict[str, pd.DataFrame] | None = None,
        price_frame: pd.DataFrame | None = None,
        factors: dict[str, pd.DataFrame] | None = None,
    ) -> pd.DataFrame:
        del liquidation_features, price_frame, factors
        self._validate()

        weights = pd.DataFrame(0.0, index=signal_frame.index, columns=signal_frame.columns)
        current = pd.Series(False, index=signal_frame.columns, dtype="bool")
        holding_bars = pd.Series(0, index=signal_frame.columns, dtype="int64")

        for ts in signal_frame.index:
            for symbol in signal_frame.columns:
                if not current.loc[symbol]:
                    continue
                holding_bars.loc[symbol] += 1
                if holding_bars.loc[symbol] >= self.config.hold_bars:
                    current.loc[symbol] = False
                    holding_bars.loc[symbol] = 0

            open_slots = max(self.config.max_positions - int(current.sum()), 0)
            if open_slots > 0:
                candidates = signal_frame.loc[ts]
                candidates = candidates[candidates > 0.0].dropna().sort_values(ascending=False)
                for symbol in candidates.index:
                    if open_slots <= 0:
                        break
                    if current.loc[symbol]:
                        continue
                    current.loc[symbol] = True
                    holding_bars.loc[symbol] = 0
                    open_slots -= 1

            active = current[current].index
            if len(active) > 0:
                weights.loc[ts, active] = self._position_weight()

        return weights

    def _validate(self) -> None:
        if self.config.hold_bars <= 0:
            raise ValueError("hold_bars must be positive")
        if self.config.max_positions < 0:
            raise ValueError("max_positions must be non-negative")
        if self.config.long_allocation < 0.0:
            raise ValueError("long_allocation must be non-negative")

    def _position_weight(self) -> float:
        if self.config.max_positions == 0:
            return 0.0
        return self.config.long_allocation / self.config.max_positions
