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
class CandleCountShortConfig:
    """Trade HYPE reversals when recent candle color counts reach a threshold."""

    symbols: tuple[str, ...] = ("HYPE/USDT:USDT",)
    bullish_count_factor: str = "bullish_candle_count_10"
    bearish_count_factor: str = "bearish_candle_count_10"
    allocation_atr_factor: str | None = "atr_pct_96"
    take_profit_atr_factor: str | None = "atr_pct_192"
    stop_loss_atr_factor: str | None = "atr_pct_288"
    trend_filter_factor: str | None = "ret_96"
    min_count: int = 8
    bullish_signal_direction: float = -1.0
    bearish_signal_direction: float = 1.0
    long_allocation: float = 3.0
    short_allocation: float = 3.0
    target_atr_pct: float | None = 0.004
    stop_loss_pct: float = 0.03
    stop_loss_atr_multiplier: float | None = 5.0
    min_stop_loss_pct: float = 0.025
    max_stop_loss_pct: float = 0.035
    take_profit_pct: float = 0.03
    take_profit_atr_multiplier: float | None = 6.0
    min_take_profit_pct: float = 0.02
    max_take_profit_pct: float = 0.04
    trend_block_pct: float | None = 0.06
    cooldown_bars: int = 8
    entry_mode: str = "signal_start"
    opposite_signal_gap_bars: int = 8
    stop_loss_risk_multiplier: float = 0.5
    min_risk_multiplier: float = 0.125


@register_strategy("candle_count_short")
@dataclass(slots=True)
class CandleCountShortStrategy:
    """15m candle-count reversal strategy with V10 risk controls.

    By default, 8 of the last 10 bullish candles open short, and 8 of the
    last 10 bearish candles open long. V10 sizes entries by ATR96, blocks
    strong 24h trends, uses ATR-based stop/take distances, and halves risk
    after consecutive stop losses until a take-profit resets the multiplier.
    """

    config: CandleCountShortConfig

    @classmethod
    def from_options(
        cls, options: dict[str, object] | None = None
    ) -> "CandleCountShortStrategy":
        return cls(config=CandleCountShortConfig(**(options or {})))

    @property
    def signal_name(self) -> str:
        return self.SIGNAL_TYPE

    def spec(self) -> dict[str, object]:
        return {"class_name": type(self).__name__, "config": asdict(self.config)}

    def version(self) -> str:
        encoded = json.dumps(self.spec(), sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:16]

    def required_factors(self) -> list[str]:
        factors = [self.config.bullish_count_factor, self.config.bearish_count_factor]
        for optional_factor in (
            self.config.allocation_atr_factor,
            self.config.take_profit_atr_factor,
            self.config.stop_loss_atr_factor,
            self.config.trend_filter_factor,
        ):
            if optional_factor is not None and optional_factor not in factors:
                factors.append(optional_factor)
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
        signal_factors = [
            self.config.bullish_count_factor,
            self.config.bearish_count_factor,
        ]
        missing = [name for name in signal_factors if name not in factors]
        if missing:
            raise ValueError(
                f"missing factors for candle_count_short strategy: {missing}"
            )

        bullish_count = factors[self.config.bullish_count_factor].astype("float64")
        bearish_count = (
            factors[self.config.bearish_count_factor]
            .reindex_like(bullish_count)
            .astype("float64")
        )
        signal = pd.DataFrame(
            0.0, index=bullish_count.index, columns=bullish_count.columns
        )

        bullish_trigger = bullish_count.ge(self.config.min_count)
        bearish_trigger = bearish_count.ge(self.config.min_count)
        signal = signal.where(
            ~bullish_trigger,
            self._normalized_direction(self.config.bullish_signal_direction),
        )
        signal = signal.where(
            ~bearish_trigger,
            self._normalized_direction(self.config.bearish_signal_direction),
        )
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
                "price_frame is required for candle_count_short stop-loss and take-profit rules"
            )
        factors = factors or {}

        close = price_frame.reindex(
            index=signal_frame.index, columns=signal_frame.columns
        )
        allocation_atr = self._optional_factor_frame(
            factors,
            self.config.allocation_atr_factor,
            signal_frame=signal_frame,
        )
        stop_loss_atr = self._optional_factor_frame(
            factors,
            self.config.stop_loss_atr_factor,
            signal_frame=signal_frame,
        )
        take_profit_atr = self._optional_factor_frame(
            factors,
            self.config.take_profit_atr_factor,
            signal_frame=signal_frame,
        )
        trend_filter = self._optional_factor_frame(
            factors,
            self.config.trend_filter_factor,
            signal_frame=signal_frame,
        )
        weights = pd.DataFrame(
            0.0, index=signal_frame.index, columns=signal_frame.columns
        )
        current_direction = pd.Series(0, index=signal_frame.columns, dtype="int64")
        entry_prices = pd.Series(np.nan, index=signal_frame.columns, dtype="float64")
        current_allocations = pd.Series(
            0.0, index=signal_frame.columns, dtype="float64"
        )
        stop_loss_pcts = pd.Series(
            self.config.stop_loss_pct, index=signal_frame.columns, dtype="float64"
        )
        take_profit_pcts = pd.Series(
            self.config.take_profit_pct, index=signal_frame.columns, dtype="float64"
        )
        cooldown_remaining = pd.Series(0, index=signal_frame.columns, dtype="int64")
        risk_multipliers = pd.Series(1.0, index=signal_frame.columns, dtype="float64")

        for ts in signal_frame.index:
            cooldown_at_start = cooldown_remaining.copy()
            signal_row = signal_frame.loc[ts]
            price_row = close.loc[ts]

            for symbol in signal_frame.columns:
                price = price_row.loc[symbol]
                if pd.isna(price):
                    continue

                exited_this_bar = False
                direction = int(current_direction.loc[symbol])
                if direction != 0:
                    pnl = direction * (
                        float(price) / float(entry_prices.loc[symbol]) - 1.0
                    )
                    stop_hit = pnl <= -abs(float(stop_loss_pcts.loc[symbol]))
                    take_hit = pnl >= abs(float(take_profit_pcts.loc[symbol]))
                    if stop_hit or take_hit:
                        direction = 0
                        current_direction.loc[symbol] = 0
                        entry_prices.loc[symbol] = np.nan
                        current_allocations.loc[symbol] = 0.0
                        cooldown_remaining.loc[symbol] = self.config.cooldown_bars
                        exited_this_bar = True
                        if stop_hit:
                            risk_multipliers.loc[symbol] = max(
                                self.config.min_risk_multiplier,
                                float(risk_multipliers.loc[symbol])
                                * self.config.stop_loss_risk_multiplier,
                            )
                        else:
                            risk_multipliers.loc[symbol] = 1.0

                if direction == 0:
                    signal = signal_row.loc[symbol]
                    desired_direction = self._desired_direction(signal)
                    entry_allowed = (
                        cooldown_remaining.loc[symbol] == 0
                        and not exited_this_bar
                        and self._entry_mode_allows(
                            signal_frame,
                            ts=ts,
                            symbol=symbol,
                            desired_direction=desired_direction,
                        )
                        and self._opposite_gap_allows(
                            signal_frame,
                            ts=ts,
                            symbol=symbol,
                            desired_direction=desired_direction,
                        )
                        and self._trend_filter_allows(
                            trend_filter,
                            ts=ts,
                            symbol=symbol,
                            desired_direction=desired_direction,
                        )
                    )
                    if desired_direction != 0 and entry_allowed:
                        allocation = self._entry_allocation(
                            allocation_atr,
                            ts=ts,
                            symbol=symbol,
                            desired_direction=desired_direction,
                        )
                        stop_pct = self._dynamic_pct(
                            stop_loss_atr,
                            ts=ts,
                            symbol=symbol,
                            fallback=self.config.stop_loss_pct,
                            multiplier=self.config.stop_loss_atr_multiplier,
                            lower=self.config.min_stop_loss_pct,
                            upper=self.config.max_stop_loss_pct,
                        )
                        take_pct = self._dynamic_pct(
                            take_profit_atr,
                            ts=ts,
                            symbol=symbol,
                            fallback=self.config.take_profit_pct,
                            multiplier=self.config.take_profit_atr_multiplier,
                            lower=self.config.min_take_profit_pct,
                            upper=self.config.max_take_profit_pct,
                        )
                        if allocation > 0.0 and stop_pct > 0.0 and take_pct > 0.0:
                            direction = desired_direction
                            current_direction.loc[symbol] = desired_direction
                            entry_prices.loc[symbol] = float(price)
                            current_allocations.loc[symbol] = allocation * float(
                                risk_multipliers.loc[symbol]
                            )
                            stop_loss_pcts.loc[symbol] = stop_pct
                            take_profit_pcts.loc[symbol] = take_pct

                if direction > 0:
                    weights.loc[ts, symbol] = current_allocations.loc[symbol]
                elif direction < 0:
                    weights.loc[ts, symbol] = -current_allocations.loc[symbol]

            active_cooldown = cooldown_at_start > 0
            cooldown_remaining.loc[active_cooldown] = (
                cooldown_remaining.loc[active_cooldown] - 1
            )

        return weights

    def _validate(self) -> None:
        if self.config.min_count <= 0:
            raise ValueError("min_count must be positive")
        if self.config.long_allocation < 0.0:
            raise ValueError("long_allocation must be non-negative")
        if self.config.short_allocation < 0.0:
            raise ValueError("short_allocation must be non-negative")
        if self.config.target_atr_pct is not None and self.config.target_atr_pct <= 0.0:
            raise ValueError("target_atr_pct must be positive when configured")
        if self.config.stop_loss_pct <= 0.0:
            raise ValueError("stop_loss_pct must be positive")
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
        if self.config.take_profit_pct <= 0.0:
            raise ValueError("take_profit_pct must be positive")
        if (
            self.config.take_profit_atr_multiplier is not None
            and self.config.take_profit_atr_multiplier <= 0.0
        ):
            raise ValueError(
                "take_profit_atr_multiplier must be positive when configured"
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
        if (
            self.config.trend_block_pct is not None
            and self.config.trend_block_pct <= 0.0
        ):
            raise ValueError("trend_block_pct must be positive when configured")
        if self.config.cooldown_bars < 0:
            raise ValueError("cooldown_bars must be non-negative")
        if self.config.entry_mode not in {"always", "signal_start"}:
            raise ValueError("entry_mode must be one of: always, signal_start")
        if self.config.opposite_signal_gap_bars < 0:
            raise ValueError("opposite_signal_gap_bars must be non-negative")
        if not 0.0 < self.config.stop_loss_risk_multiplier <= 1.0:
            raise ValueError("stop_loss_risk_multiplier must be in (0, 1]")
        if not 0.0 < self.config.min_risk_multiplier <= 1.0:
            raise ValueError("min_risk_multiplier must be in (0, 1]")

    def _desired_direction(self, signal: object) -> int:
        if pd.isna(signal):
            return 0
        return self._normalized_direction(float(signal))

    @staticmethod
    def _normalized_direction(value: float) -> int:
        if value > 0.0:
            return 1
        if value < 0.0:
            return -1
        return 0

    def _entry_mode_allows(
        self,
        signal_frame: pd.DataFrame,
        *,
        ts: pd.Timestamp,
        symbol: str,
        desired_direction: int,
    ) -> bool:
        if desired_direction == 0 or self.config.entry_mode == "always":
            return True
        position = int(signal_frame.index.get_loc(ts))
        if position == 0:
            return True
        previous_signal = self._desired_direction(
            signal_frame[symbol].iloc[position - 1]
        )
        return previous_signal != desired_direction

    def _opposite_gap_allows(
        self,
        signal_frame: pd.DataFrame,
        *,
        ts: pd.Timestamp,
        symbol: str,
        desired_direction: int,
    ) -> bool:
        if desired_direction == 0 or self.config.opposite_signal_gap_bars == 0:
            return True
        position = int(signal_frame.index.get_loc(ts))
        if position == 0:
            return True
        start = max(0, position - self.config.opposite_signal_gap_bars)
        recent_signals = signal_frame[symbol].iloc[start:position]
        return not any(
            self._desired_direction(value) == -desired_direction
            for value in recent_signals
        )

    def _optional_factor_frame(
        self,
        factors: dict[str, pd.DataFrame],
        factor_name: str | None,
        *,
        signal_frame: pd.DataFrame,
    ) -> pd.DataFrame | None:
        if factor_name is None:
            return None
        if factor_name not in factors:
            raise ValueError(
                f"missing factor for candle_count_short strategy: {factor_name}"
            )
        return factors[factor_name].reindex_like(signal_frame).astype("float64")

    def _trend_filter_allows(
        self,
        trend_filter: pd.DataFrame | None,
        *,
        ts: pd.Timestamp,
        symbol: str,
        desired_direction: int,
    ) -> bool:
        if (
            desired_direction == 0
            or trend_filter is None
            or self.config.trend_block_pct is None
        ):
            return True
        trend_value = trend_filter.loc[ts, symbol]
        if pd.isna(trend_value):
            return False
        if desired_direction < 0 and float(trend_value) > self.config.trend_block_pct:
            return False
        if desired_direction > 0 and float(trend_value) < -self.config.trend_block_pct:
            return False
        return True

    def _entry_allocation(
        self,
        allocation_atr: pd.DataFrame | None,
        *,
        ts: pd.Timestamp,
        symbol: str,
        desired_direction: int,
    ) -> float:
        max_allocation = (
            self.config.long_allocation
            if desired_direction > 0
            else self.config.short_allocation
        )
        if allocation_atr is None or self.config.target_atr_pct is None:
            return float(max_allocation)
        atr_value = allocation_atr.loc[ts, symbol]
        if pd.isna(atr_value) or float(atr_value) <= 0.0:
            return 0.0
        return float(
            min(
                max_allocation,
                max_allocation * self.config.target_atr_pct / float(atr_value),
            )
        )

    @staticmethod
    def _dynamic_pct(
        factor_frame: pd.DataFrame | None,
        *,
        ts: pd.Timestamp,
        symbol: str,
        fallback: float,
        multiplier: float | None,
        lower: float,
        upper: float,
    ) -> float:
        if factor_frame is None or multiplier is None:
            return float(fallback)
        value = factor_frame.loc[ts, symbol]
        if pd.isna(value) or float(value) <= 0.0:
            return 0.0
        return float(np.clip(float(value) * multiplier, lower, upper))
