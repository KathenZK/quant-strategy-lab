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
class BtcIntradayRegimeConfig:
    """BTC 15m low-turnover EMA regime strategy with ATR risk sizing."""

    symbols: tuple[str, ...] = ("BTC/USDT:USDT",)
    ema_spread_factor: str = "ema_spread_192_672"
    trend_return_factor: str | None = None
    atr_factor: str = "atr_pct_288"
    entry_spread: float = 0.006
    exit_spread: float = 0.0
    min_trend_return: float = 0.0
    long_enabled: bool = True
    short_enabled: bool = True
    long_allocation: float = 1.0
    short_allocation: float = 0.75
    target_atr_pct: float | None = 0.002
    stop_loss_atr_multiplier: float | None = 6.0
    min_stop_loss_pct: float = 0.018
    max_stop_loss_pct: float = 0.045
    take_profit_atr_multiplier: float | None = None
    min_take_profit_pct: float = 0.035
    max_take_profit_pct: float = 0.090
    max_hold_bars: int = 672
    cooldown_bars: int = 16


@register_strategy("btc_intraday_regime")
@dataclass(slots=True)
class BtcIntradayRegimeStrategy:
    """BTC 15m regime strategy mined from local Binance perp data.

    The research favored low turnover over frequent intraday signals. The
    strategy enters only when a long-horizon EMA spread clears a threshold,
    scales exposure by ATR, and exits on regime loss or explicit risk stops.
    """

    config: BtcIntradayRegimeConfig

    @classmethod
    def from_options(
        cls, options: dict[str, object] | None = None
    ) -> "BtcIntradayRegimeStrategy":
        return cls(config=BtcIntradayRegimeConfig(**(options or {})))

    @property
    def signal_name(self) -> str:
        return self.SIGNAL_TYPE

    def spec(self) -> dict[str, object]:
        return {"class_name": type(self).__name__, "config": asdict(self.config)}

    def version(self) -> str:
        encoded = json.dumps(self.spec(), sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:16]

    def required_factors(self) -> list[str]:
        factors = [self.config.ema_spread_factor, self.config.atr_factor]
        if self.config.trend_return_factor is not None:
            factors.append(self.config.trend_return_factor)
        return factors

    def required_liquidation_features(self) -> list[str]:
        return []

    def default_symbols(self, *, exchange: str, market_type: MarketType) -> list[str]:
        del exchange
        return resolve_configured_symbols(
            self.config.symbols,
            market_type=market_type,
            default_bases=("BTC",),
        )

    def build_signal_frame(self, factors: dict[str, pd.DataFrame]) -> pd.DataFrame:
        self._validate()
        missing = [name for name in self.required_factors() if name not in factors]
        if missing:
            raise ValueError(
                f"missing factors for btc_intraday_regime strategy: {missing}"
            )

        ema_spread = factors[self.config.ema_spread_factor].astype("float64")
        signal = pd.DataFrame(0.0, index=ema_spread.index, columns=ema_spread.columns)
        long_setup = ema_spread.gt(self.config.entry_spread)
        short_setup = ema_spread.lt(-self.config.entry_spread)

        if self.config.trend_return_factor is not None:
            trend_return = factors[self.config.trend_return_factor].reindex_like(
                ema_spread
            )
            long_setup &= trend_return.ge(self.config.min_trend_return)
            short_setup &= trend_return.le(-self.config.min_trend_return)

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
                "price_frame is required for btc_intraday_regime risk controls"
            )
        factors = factors or {}
        missing = [
            name
            for name in (self.config.ema_spread_factor, self.config.atr_factor)
            if name not in factors
        ]
        if missing:
            raise ValueError(
                f"missing factors for btc_intraday_regime strategy: {missing}"
            )

        close = price_frame.reindex(
            index=signal_frame.index,
            columns=signal_frame.columns,
        ).astype("float64")
        ema_spread = factors[self.config.ema_spread_factor].reindex_like(
            signal_frame
        )
        atr = factors[self.config.atr_factor].reindex_like(signal_frame)
        weights = pd.DataFrame(0.0, index=signal_frame.index, columns=signal_frame.columns)

        direction = pd.Series(0, index=signal_frame.columns, dtype="int64")
        allocation = pd.Series(0.0, index=signal_frame.columns, dtype="float64")
        entry_price = pd.Series(np.nan, index=signal_frame.columns, dtype="float64")
        stop_loss_pct = pd.Series(np.nan, index=signal_frame.columns, dtype="float64")
        take_profit_pct = pd.Series(np.nan, index=signal_frame.columns, dtype="float64")
        hold_bars = pd.Series(0, index=signal_frame.columns, dtype="int64")
        cooldown = pd.Series(0, index=signal_frame.columns, dtype="int64")

        for ts in signal_frame.index:
            signal_row = signal_frame.loc[ts]
            price_row = close.loc[ts]
            ema_row = ema_spread.loc[ts]
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
                    should_exit = self._regime_exit(
                        current_direction,
                        ema_row.loc[symbol],
                    )
                    if (
                        not should_exit
                        and self.config.stop_loss_atr_multiplier is not None
                    ):
                        should_exit = pnl <= -abs(float(stop_loss_pct.loc[symbol]))
                    if (
                        not should_exit
                        and self.config.take_profit_atr_multiplier is not None
                    ):
                        should_exit = pnl >= abs(float(take_profit_pct.loc[symbol]))
                    if not should_exit:
                        should_exit = int(hold_bars.loc[symbol]) >= self.config.max_hold_bars

                    if should_exit:
                        direction.loc[symbol] = 0
                        allocation.loc[symbol] = 0.0
                        entry_price.loc[symbol] = np.nan
                        stop_loss_pct.loc[symbol] = np.nan
                        take_profit_pct.loc[symbol] = np.nan
                        hold_bars.loc[symbol] = 0
                        cooldown.loc[symbol] = self.config.cooldown_bars

                if direction.loc[symbol] == 0:
                    if cooldown.loc[symbol] > 0:
                        cooldown.loc[symbol] -= 1
                        continue

                    desired_direction = self._desired_direction(signal_row.loc[symbol])
                    if desired_direction == 0:
                        continue
                    atr_value = atr_row.loc[symbol]
                    if pd.isna(atr_value) or float(atr_value) <= 0.0:
                        continue

                    allocation.loc[symbol] = self._entry_allocation(
                        desired_direction=desired_direction,
                        atr_value=float(atr_value),
                    )
                    if allocation.loc[symbol] <= 0.0:
                        continue
                    stop_loss_pct.loc[symbol] = self._dynamic_pct(
                        atr_value,
                        multiplier=self.config.stop_loss_atr_multiplier,
                        lower=self.config.min_stop_loss_pct,
                        upper=self.config.max_stop_loss_pct,
                    )
                    take_profit_pct.loc[symbol] = self._dynamic_pct(
                        atr_value,
                        multiplier=self.config.take_profit_atr_multiplier,
                        lower=self.config.min_take_profit_pct,
                        upper=self.config.max_take_profit_pct,
                    )
                    direction.loc[symbol] = desired_direction
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
        return min(max_allocation, max_allocation * self.config.target_atr_pct / atr_value)

    def _regime_exit(self, direction: int, ema_value: object) -> bool:
        if pd.isna(ema_value):
            return True
        value = float(ema_value)
        if direction > 0:
            return value <= self.config.exit_spread
        return value >= -self.config.exit_spread

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
    def _dynamic_pct(
        value: object,
        *,
        multiplier: float | None,
        lower: float,
        upper: float,
    ) -> float:
        if multiplier is None:
            return np.inf
        if pd.isna(value) or float(value) <= 0.0:
            return 0.0
        return float(np.clip(float(value) * multiplier, lower, upper))

    def _validate(self) -> None:
        if self.config.entry_spread < 0.0:
            raise ValueError("entry_spread must be non-negative")
        if self.config.exit_spread < 0.0:
            raise ValueError("exit_spread must be non-negative")
        if self.config.exit_spread > self.config.entry_spread:
            raise ValueError("exit_spread must be less than or equal to entry_spread")
        if self.config.min_trend_return < 0.0:
            raise ValueError("min_trend_return must be non-negative")
        if self.config.long_allocation < 0.0 or self.config.short_allocation < 0.0:
            raise ValueError("allocations must be non-negative")
        if self.config.target_atr_pct is not None and self.config.target_atr_pct <= 0.0:
            raise ValueError("target_atr_pct must be positive when configured")
        if (
            self.config.stop_loss_atr_multiplier is not None
            and self.config.stop_loss_atr_multiplier <= 0.0
        ):
            raise ValueError(
                "stop_loss_atr_multiplier must be positive when configured"
            )
        if (
            self.config.take_profit_atr_multiplier is not None
            and self.config.take_profit_atr_multiplier <= 0.0
        ):
            raise ValueError(
                "take_profit_atr_multiplier must be positive when configured"
            )
        if self.config.min_stop_loss_pct <= 0.0 or self.config.max_stop_loss_pct <= 0.0:
            raise ValueError("stop-loss bounds must be positive")
        if self.config.min_stop_loss_pct > self.config.max_stop_loss_pct:
            raise ValueError(
                "min_stop_loss_pct must be less than or equal to max_stop_loss_pct"
            )
        if (
            self.config.min_take_profit_pct <= 0.0
            or self.config.max_take_profit_pct <= 0.0
        ):
            raise ValueError("take-profit bounds must be positive")
        if self.config.min_take_profit_pct > self.config.max_take_profit_pct:
            raise ValueError(
                "min_take_profit_pct must be less than or equal to max_take_profit_pct"
            )
        if self.config.max_hold_bars < 1:
            raise ValueError("max_hold_bars must be positive")
        if self.config.cooldown_bars < 0:
            raise ValueError("cooldown_bars must be non-negative")
