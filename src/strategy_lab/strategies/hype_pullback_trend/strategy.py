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
class HypePullbackTrendConfig:
    """Trade HYPE pullbacks in the direction of the higher-timeframe trend."""

    symbols: tuple[str, ...] = ("HYPE/USDT:USDT",)
    short_return_factor: str = "ret_48"
    long_return_factor: str = "ret_192"
    ema_spread_factor: str | None = None
    atr_factor: str = "atr_pct_672"
    bullish_count_factor: str | None = None
    bearish_count_factor: str | None = None
    volume_surge_factor: str | None = None
    min_trend_return: float = 0.04
    min_pullback_return: float = 0.03
    min_pullback_count: int | None = None
    min_volume_surge: float | None = 0.0
    long_enabled: bool = True
    short_enabled: bool = True
    long_allocation: float = 2.0
    short_allocation: float = 1.0
    target_atr_pct: float | None = 0.008
    stop_loss_atr_multiplier: float = 6.0
    take_profit_atr_multiplier: float = 6.0
    max_hold_bars: int = 192
    cooldown_bars: int = 16


@register_strategy("hype_pullback_trend")
@dataclass(slots=True)
class HypePullbackTrendStrategy:
    """HYPE 15m trend-pullback strategy with ATR sizing and exits.

    The mined edge is not a naive breakout. HYPE's 15m data favored entering
    after a short-term pullback while the 2-day trend and EMA regime still
    point in the same direction.
    """

    config: HypePullbackTrendConfig

    @classmethod
    def from_options(
        cls, options: dict[str, object] | None = None
    ) -> "HypePullbackTrendStrategy":
        return cls(config=HypePullbackTrendConfig(**(options or {})))

    @property
    def signal_name(self) -> str:
        return self.SIGNAL_TYPE

    def spec(self) -> dict[str, object]:
        return {"class_name": type(self).__name__, "config": asdict(self.config)}

    def version(self) -> str:
        encoded = json.dumps(self.spec(), sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:16]

    def required_factors(self) -> list[str]:
        factors = [
            self.config.short_return_factor,
            self.config.long_return_factor,
            self.config.atr_factor,
        ]
        for optional_factor in (
            self.config.ema_spread_factor,
            self.config.bullish_count_factor,
            self.config.bearish_count_factor,
        ):
            if optional_factor is not None:
                factors.append(optional_factor)
        if self.config.volume_surge_factor is not None:
            factors.append(self.config.volume_surge_factor)
        return factors

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
        missing = [name for name in self.required_factors() if name not in factors]
        if missing:
            raise ValueError(
                f"missing factors for hype_pullback_trend strategy: {missing}"
            )

        short_return = factors[self.config.short_return_factor].astype("float64")
        long_return = factors[self.config.long_return_factor].reindex_like(
            short_return
        )

        signal = pd.DataFrame(0.0, index=short_return.index, columns=short_return.columns)
        long_setup = (
            long_return.gt(self.config.min_trend_return)
            & short_return.le(-self.config.min_pullback_return)
        )
        short_setup = (
            long_return.lt(-self.config.min_trend_return)
            & short_return.ge(self.config.min_pullback_return)
        )

        if self.config.ema_spread_factor is not None:
            ema_spread = factors[self.config.ema_spread_factor].reindex_like(
                short_return
            )
            long_setup &= ema_spread.gt(0.0)
            short_setup &= ema_spread.lt(0.0)

        if (
            self.config.min_pullback_count is not None
            and self.config.bearish_count_factor is not None
            and self.config.bullish_count_factor is not None
        ):
            bearish_count = factors[self.config.bearish_count_factor].reindex_like(
                short_return
            )
            bullish_count = factors[self.config.bullish_count_factor].reindex_like(
                short_return
            )
            long_setup &= bearish_count.ge(self.config.min_pullback_count)
            short_setup &= bullish_count.ge(self.config.min_pullback_count)

        if self.config.volume_surge_factor is not None:
            volume_surge = factors[self.config.volume_surge_factor].reindex_like(
                short_return
            )
            if self.config.min_volume_surge is not None:
                volume_ok = volume_surge.ge(self.config.min_volume_surge)
                long_setup &= volume_ok
                short_setup &= volume_ok

        if self.config.long_enabled:
            signal = signal.where(~long_setup, 1.0)
        if self.config.short_enabled:
            signal = signal.where(~short_setup, -1.0)
        return signal

    def build_weights(
        self,
        signal_frame: pd.DataFrame,
        liquidation_features: dict[str, pd.DataFrame] | None = None,
        price_frame: pd.DataFrame | None = None,
        factors: dict[str, pd.DataFrame] | None = None,
    ) -> pd.DataFrame:
        del liquidation_features
        self._validate()
        if price_frame is None:
            raise ValueError(
                "price_frame is required for hype_pullback_trend stop/take rules"
            )
        factors = factors or {}
        if self.config.atr_factor not in factors:
            raise ValueError(
                f"missing factor for hype_pullback_trend strategy: {self.config.atr_factor}"
            )

        close = price_frame.reindex(
            index=signal_frame.index,
            columns=signal_frame.columns,
        ).astype("float64")
        atr = factors[self.config.atr_factor].reindex_like(signal_frame).astype(
            "float64"
        )
        weights = pd.DataFrame(0.0, index=signal_frame.index, columns=signal_frame.columns)

        direction = pd.Series(0, index=signal_frame.columns, dtype="int64")
        allocation = pd.Series(0.0, index=signal_frame.columns, dtype="float64")
        entry_price = pd.Series(np.nan, index=signal_frame.columns, dtype="float64")
        hold_bars = pd.Series(0, index=signal_frame.columns, dtype="int64")
        cooldown = pd.Series(0, index=signal_frame.columns, dtype="int64")

        for ts in signal_frame.index:
            signal_row = signal_frame.loc[ts]
            price_row = close.loc[ts]
            atr_row = atr.loc[ts]

            for symbol in signal_frame.columns:
                price = price_row.loc[symbol]
                if pd.isna(price):
                    continue

                current_direction = int(direction.loc[symbol])
                if current_direction != 0:
                    hold_bars.loc[symbol] += 1
                    pnl = current_direction * (
                        float(price) / float(entry_price.loc[symbol]) - 1.0
                    )
                    stop_pct = self._dynamic_pct(
                        atr_row.loc[symbol],
                        self.config.stop_loss_atr_multiplier,
                    )
                    take_pct = self._dynamic_pct(
                        atr_row.loc[symbol],
                        self.config.take_profit_atr_multiplier,
                    )
                    should_exit = (
                        pnl <= -stop_pct
                        or pnl >= take_pct
                        or int(hold_bars.loc[symbol]) >= self.config.max_hold_bars
                    )
                    if should_exit:
                        direction.loc[symbol] = 0
                        allocation.loc[symbol] = 0.0
                        entry_price.loc[symbol] = np.nan
                        hold_bars.loc[symbol] = 0
                        cooldown.loc[symbol] = self.config.cooldown_bars

                if direction.loc[symbol] == 0:
                    if cooldown.loc[symbol] > 0:
                        cooldown.loc[symbol] -= 1
                        continue

                    desired_direction = self._desired_direction(signal_row.loc[symbol])
                    if desired_direction != 0:
                        atr_value = atr_row.loc[symbol]
                        if pd.isna(atr_value) or float(atr_value) <= 0.0:
                            continue
                        direction.loc[symbol] = desired_direction
                        allocation.loc[symbol] = self._entry_allocation(
                            desired_direction=desired_direction,
                            atr_value=float(atr_value),
                        )
                        entry_price.loc[symbol] = float(price)
                        hold_bars.loc[symbol] = 0

            weights.loc[ts] = direction.astype("float64") * allocation

        return weights

    def _entry_allocation(self, *, desired_direction: int, atr_value: float) -> float:
        max_allocation = (
            self.config.long_allocation
            if desired_direction > 0
            else self.config.short_allocation
        )
        if self.config.target_atr_pct is None:
            return max_allocation
        return min(max_allocation, self.config.target_atr_pct / atr_value)

    @staticmethod
    def _desired_direction(value: object) -> int:
        if pd.isna(value):
            return 0
        if float(value) > 0.0:
            return 1
        if float(value) < 0.0:
            return -1
        return 0

    @staticmethod
    def _dynamic_pct(value: object, multiplier: float) -> float:
        if pd.isna(value) or float(value) <= 0.0:
            return np.inf
        return abs(float(value) * multiplier)

    def _validate(self) -> None:
        if self.config.min_trend_return < 0.0:
            raise ValueError("min_trend_return must be non-negative")
        if self.config.min_pullback_return < 0.0:
            raise ValueError("min_pullback_return must be non-negative")
        if (
            self.config.min_pullback_count is not None
            and self.config.min_pullback_count < 1
        ):
            raise ValueError("min_pullback_count must be positive")
        if self.config.long_allocation <= 0.0 or self.config.short_allocation <= 0.0:
            raise ValueError("allocations must be positive")
        if self.config.target_atr_pct is not None and self.config.target_atr_pct <= 0.0:
            raise ValueError("target_atr_pct must be positive when configured")
        if self.config.stop_loss_atr_multiplier <= 0.0:
            raise ValueError("stop_loss_atr_multiplier must be positive")
        if self.config.take_profit_atr_multiplier <= 0.0:
            raise ValueError("take_profit_atr_multiplier must be positive")
        if self.config.max_hold_bars < 1:
            raise ValueError("max_hold_bars must be positive")
        if self.config.cooldown_bars < 0:
            raise ValueError("cooldown_bars must be non-negative")
