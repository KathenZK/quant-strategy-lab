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
    min_count: int = 8
    bullish_signal_direction: float = -1.0
    bearish_signal_direction: float = 1.0
    long_allocation: float = 3.0
    short_allocation: float = 3.0
    stop_loss_pct: float = 0.03
    take_profit_pct: float = 0.03
    cooldown_bars: int = 8
    entry_mode: str = "signal_start"
    opposite_signal_gap_bars: int = 8


@register_strategy("candle_count_short")
@dataclass(slots=True)
class CandleCountShortStrategy:
    """15m candle-count strategy with fixed stop-loss and take-profit exits.

    By default, 8 of the last 10 bullish candles open short, and 8 of the
    last 10 bearish candles open long. Entries are only taken at the start of
    a new crowding segment to avoid repeatedly re-entering the same signal.
    """

    config: CandleCountShortConfig

    @classmethod
    def from_options(cls, options: dict[str, object] | None = None) -> "CandleCountShortStrategy":
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
        return [self.config.bullish_count_factor, self.config.bearish_count_factor]

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
            raise ValueError(f"missing factors for candle_count_short strategy: {missing}")

        bullish_count = factors[self.config.bullish_count_factor].astype("float64")
        bearish_count = factors[self.config.bearish_count_factor].reindex_like(bullish_count).astype("float64")
        signal = pd.DataFrame(0.0, index=bullish_count.index, columns=bullish_count.columns)

        bullish_trigger = bullish_count.ge(self.config.min_count)
        bearish_trigger = bearish_count.ge(self.config.min_count)
        signal = signal.where(~bullish_trigger, self._normalized_direction(self.config.bullish_signal_direction))
        signal = signal.where(~bearish_trigger, self._normalized_direction(self.config.bearish_signal_direction))
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
            raise ValueError("price_frame is required for candle_count_short stop-loss and take-profit rules")

        close = price_frame.reindex(index=signal_frame.index, columns=signal_frame.columns)
        weights = pd.DataFrame(0.0, index=signal_frame.index, columns=signal_frame.columns)
        current_direction = pd.Series(0, index=signal_frame.columns, dtype="int64")
        entry_prices = pd.Series(np.nan, index=signal_frame.columns, dtype="float64")
        cooldown_remaining = pd.Series(0, index=signal_frame.columns, dtype="int64")

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
                    pnl = direction * (float(price) / float(entry_prices.loc[symbol]) - 1.0)
                    stop_hit = pnl <= -abs(self.config.stop_loss_pct)
                    take_hit = pnl >= abs(self.config.take_profit_pct)
                    if stop_hit or take_hit:
                        direction = 0
                        current_direction.loc[symbol] = 0
                        entry_prices.loc[symbol] = np.nan
                        cooldown_remaining.loc[symbol] = self.config.cooldown_bars
                        exited_this_bar = True

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
                    )
                    if desired_direction != 0 and entry_allowed:
                        direction = desired_direction
                        current_direction.loc[symbol] = desired_direction
                        entry_prices.loc[symbol] = float(price)

                if direction > 0:
                    weights.loc[ts, symbol] = self.config.long_allocation
                elif direction < 0:
                    weights.loc[ts, symbol] = -self.config.short_allocation

            active_cooldown = cooldown_at_start > 0
            cooldown_remaining.loc[active_cooldown] = cooldown_remaining.loc[active_cooldown] - 1

        return weights

    def _validate(self) -> None:
        if self.config.min_count <= 0:
            raise ValueError("min_count must be positive")
        if self.config.long_allocation < 0.0:
            raise ValueError("long_allocation must be non-negative")
        if self.config.short_allocation < 0.0:
            raise ValueError("short_allocation must be non-negative")
        if self.config.stop_loss_pct <= 0.0:
            raise ValueError("stop_loss_pct must be positive")
        if self.config.take_profit_pct <= 0.0:
            raise ValueError("take_profit_pct must be positive")
        if self.config.cooldown_bars < 0:
            raise ValueError("cooldown_bars must be non-negative")
        if self.config.entry_mode not in {"always", "signal_start"}:
            raise ValueError("entry_mode must be one of: always, signal_start")
        if self.config.opposite_signal_gap_bars < 0:
            raise ValueError("opposite_signal_gap_bars must be non-negative")

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
        previous_signal = self._desired_direction(signal_frame[symbol].iloc[position - 1])
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
        return not any(self._desired_direction(value) == -desired_direction for value in recent_signals)
