from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json

import numpy as np
import pandas as pd


@dataclass(frozen=True, slots=True)
class SmallCapMomentumBreakoutAllocatorConfig:
    max_positions: int = 3
    long_allocation: float = 0.30
    position_weight: float | None = None
    stop_loss_pct: float | None = 0.06
    trailing_stop_pct: float | None = 0.08
    take_profit_pct: float | None = None
    max_hold_bars: int | None = 12
    cooldown_bars: int = 6
    exit_on_signal_loss: bool = False
    exit_on_negative_signal: bool = False
    failed_breakout_bars: int | None = None
    failed_breakout_min_profit_pct: float | None = None
    breakeven_after_profit_pct: float | None = None
    profit_trailing_activation_pct: float | None = None
    profit_trailing_stop_pct: float | None = None
    exit_signal_threshold: float = 0.0
    max_rank_hold_positions: int | None = None


@dataclass(slots=True)
class SmallCapMomentumBreakoutAllocator:
    """Persistent long-only allocator for short-lived momentum bursts."""

    config: SmallCapMomentumBreakoutAllocatorConfig

    @classmethod
    def from_options(
        cls,
        options: dict[str, object] | None = None,
    ) -> "SmallCapMomentumBreakoutAllocator":
        return cls(config=SmallCapMomentumBreakoutAllocatorConfig(**(options or {})))

    def spec(self) -> dict[str, object]:
        return {
            "class_name": type(self).__name__,
            "config": asdict(self.config),
        }

    def version(self) -> str:
        encoded = json.dumps(self.spec(), sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:16]

    def required_risk_features(self) -> list[str]:
        return []

    def build_weights(
        self,
        signal_frame: pd.DataFrame,
        risk_features: dict[str, pd.DataFrame] | None = None,
        price_frame: pd.DataFrame | None = None,
        factor_frames: dict[str, pd.DataFrame] | None = None,
    ) -> pd.DataFrame:
        del risk_features, factor_frames
        self._validate()

        if price_frame is None and self._uses_price_context():
            raise ValueError("price_frame is required when small-cap momentum exits use price context")

        close = self._build_close_frame(signal_frame, price_frame=price_frame)
        weights = pd.DataFrame(0.0, index=signal_frame.index, columns=signal_frame.columns)
        current = pd.Series(False, index=signal_frame.columns, dtype="bool")
        entry_prices = pd.Series(np.nan, index=signal_frame.columns, dtype="float64")
        trail_highs = pd.Series(np.nan, index=signal_frame.columns, dtype="float64")
        holding_bars = pd.Series(0, index=signal_frame.columns, dtype="int64")
        cooldown_remaining = pd.Series(0, index=signal_frame.columns, dtype="int64")

        for ts in signal_frame.index:
            cooldown_at_start = cooldown_remaining.copy()
            signal_row = signal_frame.loc[ts]
            price_row = close.loc[ts]
            ranked_hold_symbols = self._ranked_hold_symbols(signal_row)

            for symbol in signal_frame.columns:
                price = price_row.loc[symbol]
                if not current.loc[symbol] or pd.isna(price):
                    continue

                if self._should_exit_on_signal(
                    symbol=symbol,
                    signal_row=signal_row,
                    ranked_hold_symbols=ranked_hold_symbols,
                ):
                    current.loc[symbol] = False
                    entry_prices.loc[symbol] = np.nan
                    trail_highs.loc[symbol] = np.nan
                    holding_bars.loc[symbol] = 0
                    cooldown_remaining.loc[symbol] = self.config.cooldown_bars
                    continue

                holding_bars.loc[symbol] += 1
                trail_highs.loc[symbol] = self._updated_trail_high(
                    price=float(price),
                    current_trail=trail_highs.loc[symbol],
                )
                if self._should_exit(
                    price=float(price),
                    entry_price=entry_prices.loc[symbol],
                    trail_high=trail_highs.loc[symbol],
                    holding_bars=int(holding_bars.loc[symbol]),
                ):
                    current.loc[symbol] = False
                    entry_prices.loc[symbol] = np.nan
                    trail_highs.loc[symbol] = np.nan
                    holding_bars.loc[symbol] = 0
                    cooldown_remaining.loc[symbol] = self.config.cooldown_bars

            open_slots = max(self.config.max_positions - int(current.sum()), 0)
            if open_slots > 0:
                candidates = signal_row[signal_row > 0.0].dropna().sort_values(ascending=False)
                for symbol in candidates.index:
                    if open_slots <= 0:
                        break
                    price = price_row.loc[symbol]
                    if current.loc[symbol] or cooldown_remaining.loc[symbol] > 0 or pd.isna(price):
                        continue
                    current.loc[symbol] = True
                    entry_prices.loc[symbol] = float(price)
                    trail_highs.loc[symbol] = float(price)
                    holding_bars.loc[symbol] = 0
                    open_slots -= 1

            active = current[current].index
            if len(active) > 0:
                weights.loc[ts, active] = self._position_weight()

            active_cooldown = cooldown_at_start > 0
            cooldown_remaining.loc[active_cooldown] = cooldown_remaining.loc[active_cooldown] - 1

        return weights

    def _validate(self) -> None:
        if self.config.max_positions < 0:
            raise ValueError("max_positions must be non-negative")
        if self.config.long_allocation < 0.0:
            raise ValueError("long_allocation must be non-negative")
        if self.config.position_weight is not None and self.config.position_weight <= 0.0:
            raise ValueError("position_weight must be positive when provided")
        if self.config.cooldown_bars < 0:
            raise ValueError("cooldown_bars must be non-negative")
        if self.config.max_hold_bars is not None and self.config.max_hold_bars <= 0:
            raise ValueError("max_hold_bars must be positive when provided")
        if self.config.failed_breakout_bars is not None and self.config.failed_breakout_bars <= 0:
            raise ValueError("failed_breakout_bars must be positive when provided")
        if self.config.max_rank_hold_positions is not None and self.config.max_rank_hold_positions <= 0:
            raise ValueError("max_rank_hold_positions must be positive when provided")
        for name, value in (
            ("stop_loss_pct", self.config.stop_loss_pct),
            ("trailing_stop_pct", self.config.trailing_stop_pct),
            ("take_profit_pct", self.config.take_profit_pct),
            ("failed_breakout_min_profit_pct", self.config.failed_breakout_min_profit_pct),
            ("breakeven_after_profit_pct", self.config.breakeven_after_profit_pct),
            ("profit_trailing_activation_pct", self.config.profit_trailing_activation_pct),
            ("profit_trailing_stop_pct", self.config.profit_trailing_stop_pct),
        ):
            if value is not None and value <= 0.0:
                raise ValueError(f"{name} must be positive when provided")
        if (self.config.failed_breakout_bars is None) != (self.config.failed_breakout_min_profit_pct is None):
            raise ValueError("failed breakout exit requires both bars and min profit pct")
        if (self.config.profit_trailing_activation_pct is None) != (self.config.profit_trailing_stop_pct is None):
            raise ValueError("profit trailing exit requires both activation and stop pct")

    def _build_close_frame(
        self,
        signal_frame: pd.DataFrame,
        *,
        price_frame: pd.DataFrame | None,
    ) -> pd.DataFrame:
        if price_frame is None:
            return pd.DataFrame(1.0, index=signal_frame.index, columns=signal_frame.columns, dtype="float64")
        return price_frame.reindex(index=signal_frame.index, columns=signal_frame.columns)

    def _uses_price_context(self) -> bool:
        return (
            self.config.stop_loss_pct is not None
            or self.config.trailing_stop_pct is not None
            or self.config.take_profit_pct is not None
        )

    def _ranked_hold_symbols(self, signal_row: pd.Series) -> set[str] | None:
        if self.config.max_rank_hold_positions is None:
            return None
        candidates = signal_row[signal_row > self.config.exit_signal_threshold].dropna().sort_values(ascending=False)
        return set(candidates.head(self.config.max_rank_hold_positions).index)

    def _should_exit_on_signal(
        self,
        *,
        symbol: str,
        signal_row: pd.Series,
        ranked_hold_symbols: set[str] | None,
    ) -> bool:
        signal_value = signal_row.loc[symbol]
        if self.config.exit_on_negative_signal and not pd.isna(signal_value) and float(signal_value) < 0.0:
            return True
        if self.config.exit_on_signal_loss:
            if pd.isna(signal_value) or float(signal_value) <= self.config.exit_signal_threshold:
                return True
        if ranked_hold_symbols is not None and symbol not in ranked_hold_symbols:
            return True
        return False

    def _updated_trail_high(self, *, price: float, current_trail: float) -> float:
        if pd.isna(current_trail):
            return price
        return max(float(current_trail), price)

    def _should_exit(
        self,
        *,
        price: float,
        entry_price: float,
        trail_high: float,
        holding_bars: int,
    ) -> bool:
        if self.config.max_hold_bars is not None and holding_bars >= self.config.max_hold_bars:
            return True
        if pd.isna(entry_price):
            return False

        if self.config.stop_loss_pct is not None and price <= entry_price * (1.0 - self.config.stop_loss_pct):
            return True
        if self.config.take_profit_pct is not None and price >= entry_price * (1.0 + self.config.take_profit_pct):
            return True
        if self.config.trailing_stop_pct is not None and not pd.isna(trail_high):
            if price <= float(trail_high) * (1.0 - self.config.trailing_stop_pct):
                return True
        if (
            self.config.failed_breakout_bars is not None
            and self.config.failed_breakout_min_profit_pct is not None
            and holding_bars >= self.config.failed_breakout_bars
            and not pd.isna(trail_high)
            and float(trail_high) < entry_price * (1.0 + self.config.failed_breakout_min_profit_pct)
        ):
            return True
        if (
            self.config.breakeven_after_profit_pct is not None
            and not pd.isna(trail_high)
            and float(trail_high) >= entry_price * (1.0 + self.config.breakeven_after_profit_pct)
            and price <= entry_price
        ):
            return True
        if (
            self.config.profit_trailing_activation_pct is not None
            and self.config.profit_trailing_stop_pct is not None
            and not pd.isna(trail_high)
            and float(trail_high) >= entry_price * (1.0 + self.config.profit_trailing_activation_pct)
            and price <= float(trail_high) * (1.0 - self.config.profit_trailing_stop_pct)
        ):
            return True
        return False

    def _position_weight(self) -> float:
        if self.config.max_positions == 0:
            return 0.0
        if self.config.position_weight is not None:
            return min(self.config.position_weight, self.config.long_allocation)
        return self.config.long_allocation / self.config.max_positions
