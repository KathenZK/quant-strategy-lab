from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json

import numpy as np
import pandas as pd


@dataclass(frozen=True, slots=True)
class PersistentSignalAllocatorConfig:
    fast_ma_factor: str = "ma_distance_30"
    slow_ma_factor: str = "ma_distance_120"
    long_allocation: float = 1.0
    short_allocation: float = 1.0
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    cooldown_bars: int = 0
    min_ma_gap_ratio: float = 0.0
    min_slow_ma_slope: float = 0.0
    slope_lookback: int = 10
    exit_on_choppy: bool = True


@dataclass(slots=True)
class PersistentSignalAllocator:
    config: PersistentSignalAllocatorConfig

    @classmethod
    def from_options(cls, options: dict[str, object] | None = None) -> "PersistentSignalAllocator":
        return cls(config=PersistentSignalAllocatorConfig(**(options or {})))

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
        del risk_features

        weights = pd.DataFrame(0.0, index=signal_frame.index, columns=signal_frame.columns)
        current = pd.Series(0.0, index=signal_frame.columns, dtype="float64")
        entry_prices = pd.Series(np.nan, index=signal_frame.columns, dtype="float64")
        cooldown_remaining = pd.Series(0, index=signal_frame.columns, dtype="int64")

        close, trade_allowed = self._build_trade_context(
            signal_frame,
            price_frame=price_frame,
            factor_frames=factor_frames,
        )

        for ts in signal_frame.index:
            cooldown_at_start = cooldown_remaining.copy()
            signal_row = signal_frame.loc[ts]
            price_row = close.loc[ts]
            allowed_row = trade_allowed.loc[ts]

            for symbol in signal_frame.columns:
                price = price_row.loc[symbol]
                if pd.isna(price):
                    continue

                if current.loc[symbol] != 0.0:
                    pnl = current.loc[symbol] * (price / entry_prices.loc[symbol] - 1.0)
                    choppy_exit = self._uses_choppy_filter() and self.config.exit_on_choppy and not bool(allowed_row.loc[symbol])
                    stop_hit = self.config.stop_loss_pct is not None and pnl <= -abs(self.config.stop_loss_pct)
                    take_hit = self.config.take_profit_pct is not None and pnl >= abs(self.config.take_profit_pct)
                    if choppy_exit or stop_hit or take_hit:
                        current.loc[symbol] = 0.0
                        entry_prices.loc[symbol] = np.nan
                        cooldown_remaining.loc[symbol] = self.config.cooldown_bars

                signal = signal_row.loc[symbol]
                if pd.notna(signal):
                    desired = 1.0 if signal > 0 else -1.0 if signal < 0 else 0.0
                    entry_allowed = cooldown_remaining.loc[symbol] == 0 and bool(allowed_row.loc[symbol])
                    if desired != 0.0 and entry_allowed:
                        current.loc[symbol] = desired
                        entry_prices.loc[symbol] = price
                    else:
                        current.loc[symbol] = 0.0
                        entry_prices.loc[symbol] = np.nan

            long_mask = current > 0
            short_mask = current < 0
            weights.loc[ts, long_mask] = self.config.long_allocation
            weights.loc[ts, short_mask] = -self.config.short_allocation

            active_cooldown = cooldown_at_start > 0
            cooldown_remaining.loc[active_cooldown] = cooldown_remaining.loc[active_cooldown] - 1

        return weights

    def _build_trade_context(
        self,
        signal_frame: pd.DataFrame,
        *,
        price_frame: pd.DataFrame | None,
        factor_frames: dict[str, pd.DataFrame] | None,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        if price_frame is None:
            if self._uses_advanced_trade_rules():
                raise ValueError("price_frame is required when stop, take-profit, or choppy filters are enabled")
            close = pd.DataFrame(1.0, index=signal_frame.index, columns=signal_frame.columns, dtype="float64")
            allowed = pd.DataFrame(True, index=signal_frame.index, columns=signal_frame.columns, dtype="bool")
            return close, allowed

        close = price_frame.reindex(index=signal_frame.index, columns=signal_frame.columns)
        allowed = pd.DataFrame(True, index=signal_frame.index, columns=signal_frame.columns, dtype="bool")
        if not self._uses_choppy_filter():
            return close, allowed

        if factor_frames is None:
            raise ValueError("factor panels are required when choppy filters are enabled")

        fast_distance = factor_frames[self.config.fast_ma_factor].reindex(index=signal_frame.index, columns=signal_frame.columns)
        slow_distance = factor_frames[self.config.slow_ma_factor].reindex(index=signal_frame.index, columns=signal_frame.columns)
        fast_ma = close / (1.0 + fast_distance)
        slow_ma = close / (1.0 + slow_distance)

        if self.config.min_ma_gap_ratio > 0.0:
            gap_ratio = (fast_ma / slow_ma - 1.0).abs().replace([np.inf, -np.inf], np.nan)
            allowed &= gap_ratio >= abs(self.config.min_ma_gap_ratio)

        if self.config.min_slow_ma_slope > 0.0:
            slope = slow_ma.pct_change(self.config.slope_lookback).abs().replace([np.inf, -np.inf], np.nan)
            allowed &= slope >= abs(self.config.min_slow_ma_slope)

        return close, allowed.fillna(False)

    def _uses_choppy_filter(self) -> bool:
        return self.config.min_ma_gap_ratio > 0.0 or self.config.min_slow_ma_slope > 0.0

    def _uses_advanced_trade_rules(self) -> bool:
        return (
            self.config.stop_loss_pct is not None
            or self.config.take_profit_pct is not None
            or self._uses_choppy_filter()
        )
