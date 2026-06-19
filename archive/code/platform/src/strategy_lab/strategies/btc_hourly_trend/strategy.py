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
class BtcHourlyTrendConfig:
    """BTC/USDT perpetual 1h EMA trend strategy with ATR volatility targeting."""

    symbols: tuple[str, ...] = ("BTC/USDT:USDT",)
    ema_spread_factor: str = "ema_spread_48_336"
    atr_factor: str = "atr_pct_168"
    entry_spread: float = 0.0
    exit_spread: float = 0.0
    long_enabled: bool = True
    short_enabled: bool = True
    long_allocation: float = 2.0
    short_allocation: float = 2.0
    target_atr_pct: float | None = 0.006
    stop_loss_atr_multiplier: float | None = None
    min_stop_loss_pct: float = 0.03
    max_stop_loss_pct: float = 0.12
    max_hold_bars: int = 100_000
    cooldown_bars: int = 0


@register_strategy("btc_hourly_trend")
@dataclass(slots=True)
class BtcHourlyTrendStrategy:
    """Low-turnover BTC 1h trend strategy.

    The mined 1h edge was a plain long/short EMA regime: participate with the
    EMA48/EMA336 trend and size exposure to a 168-hour ATR target. This keeps the
    strategy simple enough to survive walk-forward checks and avoids overfitting
    to short-lived intraday patterns.
    """

    config: BtcHourlyTrendConfig

    @classmethod
    def from_options(
        cls, options: dict[str, object] | None = None
    ) -> "BtcHourlyTrendStrategy":
        return cls(config=BtcHourlyTrendConfig(**(options or {})))

    @property
    def signal_name(self) -> str:
        return self.SIGNAL_TYPE

    def spec(self) -> dict[str, object]:
        return {"class_name": type(self).__name__, "config": asdict(self.config)}

    def version(self) -> str:
        encoded = json.dumps(self.spec(), sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:16]

    def required_factors(self) -> list[str]:
        return [self.config.ema_spread_factor, self.config.atr_factor]

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
        if self.config.ema_spread_factor not in factors:
            raise ValueError(
                "missing factor for btc_hourly_trend strategy: "
                f"{self.config.ema_spread_factor}"
            )

        ema_spread = factors[self.config.ema_spread_factor].astype("float64")
        signal = pd.DataFrame(0.0, index=ema_spread.index, columns=ema_spread.columns)
        if self.config.long_enabled:
            signal = signal.where(~ema_spread.gt(self.config.entry_spread), 1.0)
        if self.config.short_enabled:
            signal = signal.where(~ema_spread.lt(-self.config.entry_spread), -1.0)
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
            raise ValueError("price_frame is required for btc_hourly_trend")
        factors = factors or {}
        missing = [name for name in self.required_factors() if name not in factors]
        if missing:
            raise ValueError(f"missing factors for btc_hourly_trend strategy: {missing}")

        close = price_frame.reindex(
            index=signal_frame.index,
            columns=signal_frame.columns,
        ).astype("float64")
        ema_spread = factors[self.config.ema_spread_factor].reindex_like(signal_frame)
        atr = factors[self.config.atr_factor].reindex_like(signal_frame)
        weights = pd.DataFrame(0.0, index=signal_frame.index, columns=signal_frame.columns)

        direction = pd.Series(0, index=signal_frame.columns, dtype="int64")
        allocation = pd.Series(0.0, index=signal_frame.columns, dtype="float64")
        entry_price = pd.Series(np.nan, index=signal_frame.columns, dtype="float64")
        stop_loss_pct = pd.Series(np.nan, index=signal_frame.columns, dtype="float64")
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
                    should_exit = self._regime_exit(
                        current_direction,
                        ema_row.loc[symbol],
                    )
                    if (
                        not should_exit
                        and self.config.stop_loss_atr_multiplier is not None
                    ):
                        pnl = current_direction * (
                            float(price) / float(entry_price.loc[symbol]) - 1.0
                        )
                        should_exit = pnl <= -abs(float(stop_loss_pct.loc[symbol]))
                    if not should_exit:
                        should_exit = int(hold_bars.loc[symbol]) >= self.config.max_hold_bars

                    if should_exit:
                        direction.loc[symbol] = 0
                        allocation.loc[symbol] = 0.0
                        entry_price.loc[symbol] = np.nan
                        stop_loss_pct.loc[symbol] = np.nan
                        hold_bars.loc[symbol] = 0
                        cooldown.loc[symbol] = self.config.cooldown_bars
                    else:
                        atr_value = atr_row.loc[symbol]
                        if not pd.isna(atr_value) and float(atr_value) > 0.0:
                            allocation.loc[symbol] = self._entry_allocation(
                                desired_direction=current_direction,
                                atr_value=float(atr_value),
                            )

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

                    next_allocation = self._entry_allocation(
                        desired_direction=desired_direction,
                        atr_value=float(atr_value),
                    )
                    if next_allocation <= 0.0:
                        continue

                    direction.loc[symbol] = desired_direction
                    allocation.loc[symbol] = next_allocation
                    entry_price.loc[symbol] = float(price)
                    stop_loss_pct.loc[symbol] = self._dynamic_stop_pct(atr_value)
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

    def _regime_exit(self, direction: int, ema_value: object) -> bool:
        if pd.isna(ema_value):
            return True
        value = float(ema_value)
        if direction > 0:
            return value <= self.config.exit_spread
        return value >= -self.config.exit_spread

    def _dynamic_stop_pct(self, atr_value: object) -> float:
        if self.config.stop_loss_atr_multiplier is None:
            return np.inf
        if pd.isna(atr_value) or float(atr_value) <= 0.0:
            return 0.0
        return float(
            np.clip(
                float(atr_value) * self.config.stop_loss_atr_multiplier,
                self.config.min_stop_loss_pct,
                self.config.max_stop_loss_pct,
            )
        )

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
        if self.config.entry_spread < 0.0:
            raise ValueError("entry_spread must be non-negative")
        if self.config.exit_spread < 0.0:
            raise ValueError("exit_spread must be non-negative")
        if self.config.exit_spread > self.config.entry_spread:
            raise ValueError("exit_spread must be less than or equal to entry_spread")
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
        if self.config.min_stop_loss_pct <= 0.0 or self.config.max_stop_loss_pct <= 0.0:
            raise ValueError("stop-loss bounds must be positive")
        if self.config.min_stop_loss_pct > self.config.max_stop_loss_pct:
            raise ValueError(
                "min_stop_loss_pct must be less than or equal to max_stop_loss_pct"
            )
        if self.config.max_hold_bars < 1:
            raise ValueError("max_hold_bars must be positive")
        if self.config.cooldown_bars < 0:
            raise ValueError("cooldown_bars must be non-negative")
