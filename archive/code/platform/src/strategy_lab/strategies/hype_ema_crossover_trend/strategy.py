from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json

import numpy as np
import pandas as pd

from strategy_lab.data import MarketType
from strategy_lab.strategies.common import resolve_configured_symbols
from strategy_lab.strategies.registry import register_strategy


@dataclass(frozen=True, slots=True)
class HypeEmaCrossoverTrendConfig:
    """HYPE 15m EMA96/EMA384 crossover trend strategy."""

    symbols: tuple[str, ...] = ("HYPE/USDT:USDT",)
    ema_spread_factor: str = "ema_spread_96_384"
    long_enabled: bool = True
    short_enabled: bool = True
    long_allocation: float = 1.0
    short_allocation: float = 1.0
    take_profit_pct: float = 0.10
    cooldown_bars: int = 0
    enter_initial_regime: bool = False


@register_strategy("hype_ema_crossover_trend")
@dataclass(slots=True)
class HypeEmaCrossoverTrendStrategy:
    config: HypeEmaCrossoverTrendConfig

    @classmethod
    def from_options(
        cls, options: dict[str, object] | None = None
    ) -> "HypeEmaCrossoverTrendStrategy":
        return cls(config=HypeEmaCrossoverTrendConfig(**(options or {})))

    @property
    def signal_name(self) -> str:
        return self.SIGNAL_TYPE

    def spec(self) -> dict[str, object]:
        return {"class_name": type(self).__name__, "config": asdict(self.config)}

    def version(self) -> str:
        encoded = json.dumps(self.spec(), sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:16]

    def required_factors(self) -> list[str]:
        return [self.config.ema_spread_factor]

    def required_liquidation_features(self) -> list[str]:
        return []

    def default_symbols(self, *, exchange: str, market_type: MarketType) -> list[str]:
        del exchange
        return resolve_configured_symbols(
            self.config.symbols,
            market_type=market_type,
            default_bases=("HYPE",),
        )

    def build_signal_frame(self, factors: dict[str, pd.DataFrame]) -> pd.DataFrame:
        self._validate()
        if self.config.ema_spread_factor not in factors:
            raise ValueError(
                "missing factors for hype_ema_crossover_trend strategy: "
                f"{[self.config.ema_spread_factor]}"
            )

        spread = factors[self.config.ema_spread_factor].astype("float64")
        previous = spread.shift(1)
        long_cross = spread.gt(0.0) & previous.le(0.0)
        short_cross = spread.lt(0.0) & previous.ge(0.0)

        if self.config.enter_initial_regime:
            long_cross |= spread.gt(0.0) & previous.isna()
            short_cross |= spread.lt(0.0) & previous.isna()

        signal = pd.DataFrame(np.nan, index=spread.index, columns=spread.columns)
        if self.config.long_enabled:
            signal = signal.where(~long_cross, 1.0)
        if self.config.short_enabled:
            signal = signal.where(~short_cross, -1.0)
        return signal

    def build_weights(
        self,
        signal_frame: pd.DataFrame,
        liquidation_features: dict[str, pd.DataFrame] | None = None,
        price_frame: pd.DataFrame | None = None,
        factors: dict[str, pd.DataFrame] | None = None,
    ) -> pd.DataFrame:
        del liquidation_features, factors
        self._validate()
        if price_frame is None:
            raise ValueError(
                "price_frame is required for hype_ema_crossover_trend take-profit rules"
            )

        close = price_frame.reindex(
            index=signal_frame.index,
            columns=signal_frame.columns,
        ).astype("float64")
        weights = pd.DataFrame(0.0, index=signal_frame.index, columns=signal_frame.columns)

        direction = pd.Series(0, index=signal_frame.columns, dtype="int64")
        allocation = pd.Series(0.0, index=signal_frame.columns, dtype="float64")
        entry_price = pd.Series(np.nan, index=signal_frame.columns, dtype="float64")
        cooldown = pd.Series(0, index=signal_frame.columns, dtype="int64")

        for ts in signal_frame.index:
            cooldown_at_start = cooldown.copy()
            signal_row = signal_frame.loc[ts]
            price_row = close.loc[ts]

            for symbol in signal_frame.columns:
                price = price_row.loc[symbol]
                if pd.isna(price):
                    continue

                current_direction = int(direction.loc[symbol])
                if current_direction != 0:
                    pnl = current_direction * (
                        float(price) / float(entry_price.loc[symbol]) - 1.0
                    )
                    if pnl >= self.config.take_profit_pct:
                        direction.loc[symbol] = 0
                        allocation.loc[symbol] = 0.0
                        entry_price.loc[symbol] = np.nan
                        cooldown.loc[symbol] = self.config.cooldown_bars

                desired_direction = self._desired_direction(signal_row.loc[symbol])
                if desired_direction == 0:
                    continue
                if cooldown.loc[symbol] > 0:
                    continue

                direction.loc[symbol] = desired_direction
                allocation.loc[symbol] = (
                    self.config.long_allocation
                    if desired_direction > 0
                    else self.config.short_allocation
                )
                entry_price.loc[symbol] = float(price)

            weights.loc[ts] = direction.astype("float64") * allocation
            active_cooldown = cooldown_at_start > 0
            cooldown.loc[active_cooldown] = cooldown.loc[active_cooldown] - 1

        return weights

    @staticmethod
    def _desired_direction(value: object) -> int:
        if pd.isna(value):
            return 0
        if float(value) > 0.0:
            return 1
        if float(value) < 0.0:
            return -1
        return 0

    def _validate(self) -> None:
        if self.config.long_allocation <= 0.0 or self.config.short_allocation <= 0.0:
            raise ValueError("allocations must be positive")
        if self.config.take_profit_pct <= 0.0:
            raise ValueError("take_profit_pct must be positive")
        if self.config.cooldown_bars < 0:
            raise ValueError("cooldown_bars must be non-negative")
