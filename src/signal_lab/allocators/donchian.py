from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json

import pandas as pd


@dataclass(frozen=True, slots=True)
class DonchianBreakoutAllocatorConfig:
    long_allocation: float = 1.0
    short_allocation: float = 1.0
    stop_loss_pct: float | None = None
    trailing_stop_pct: float | None = None
    take_profit_pct: float | None = None
    cooldown_bars: int = 0
    risk_budget_pct: float | None = None
    max_pyramids: int = 0
    pyramid_step_pct: float = 0.05
    pyramid_unit_scale: float = 0.5


@dataclass(slots=True)
class DonchianBreakoutAllocator:
    config: DonchianBreakoutAllocatorConfig

    @classmethod
    def from_options(cls, options: dict[str, object] | None = None) -> "DonchianBreakoutAllocator":
        return cls(config=DonchianBreakoutAllocatorConfig(**(options or {})))

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
            raise ValueError("price_frame is required when donchian stops or pyramiding are enabled")

        close = self._build_close_frame(signal_frame, price_frame=price_frame)
        weights = pd.DataFrame(0.0, index=signal_frame.index, columns=signal_frame.columns)
        direction = pd.Series(0, index=signal_frame.columns, dtype="int64")
        entry_prices = pd.Series(float("nan"), index=signal_frame.columns, dtype="float64")
        trail_reference = pd.Series(float("nan"), index=signal_frame.columns, dtype="float64")
        last_add_prices = pd.Series(float("nan"), index=signal_frame.columns, dtype="float64")
        pyramid_counts = pd.Series(0, index=signal_frame.columns, dtype="int64")
        cooldown_remaining = pd.Series(0, index=signal_frame.columns, dtype="int64")

        for ts in signal_frame.index:
            cooldown_at_start = cooldown_remaining.copy()
            signal_row = signal_frame.loc[ts]
            price_row = close.loc[ts]

            for symbol in signal_frame.columns:
                price = price_row.loc[symbol]
                if pd.isna(price):
                    continue

                current_direction = int(direction.loc[symbol])
                if current_direction != 0:
                    trail_reference.loc[symbol] = self._updated_trail_reference(
                        current_direction=current_direction,
                        price=float(price),
                        current_reference=trail_reference.loc[symbol],
                    )
                    if self._should_exit(
                        current_direction=current_direction,
                        price=float(price),
                        entry_price=entry_prices.loc[symbol],
                        trail_reference=trail_reference.loc[symbol],
                    ):
                        current_direction = 0
                        direction.loc[symbol] = 0
                        entry_prices.loc[symbol] = float("nan")
                        trail_reference.loc[symbol] = float("nan")
                        last_add_prices.loc[symbol] = float("nan")
                        pyramid_counts.loc[symbol] = 0
                        cooldown_remaining.loc[symbol] = self.config.cooldown_bars

                signal = signal_row.loc[symbol]
                desired_direction = self._desired_direction(signal)
                entry_allowed = cooldown_remaining.loc[symbol] == 0

                if desired_direction != 0 and desired_direction != current_direction:
                    if entry_allowed:
                        current_direction = desired_direction
                        direction.loc[symbol] = desired_direction
                        entry_prices.loc[symbol] = float(price)
                        trail_reference.loc[symbol] = float(price)
                        last_add_prices.loc[symbol] = float(price)
                        pyramid_counts.loc[symbol] = 0
                elif current_direction != 0:
                    pyramid_counts.loc[symbol], last_add_prices.loc[symbol] = self._apply_pyramids(
                        current_direction=current_direction,
                        price=float(price),
                        current_count=int(pyramid_counts.loc[symbol]),
                        last_add_price=last_add_prices.loc[symbol],
                    )

                if current_direction == 0:
                    weights.loc[ts, symbol] = 0.0
                else:
                    weights.loc[ts, symbol] = self._position_weight(
                        current_direction=current_direction,
                        pyramid_count=int(pyramid_counts.loc[symbol]),
                    )

            active_cooldown = cooldown_at_start > 0
            cooldown_remaining.loc[active_cooldown] = cooldown_remaining.loc[active_cooldown] - 1

        return weights

    def _build_close_frame(
        self,
        signal_frame: pd.DataFrame,
        *,
        price_frame: pd.DataFrame | None,
    ) -> pd.DataFrame:
        if price_frame is None:
            return pd.DataFrame(1.0, index=signal_frame.index, columns=signal_frame.columns, dtype="float64")
        return price_frame.reindex(index=signal_frame.index, columns=signal_frame.columns)

    def _validate(self) -> None:
        if self.config.cooldown_bars < 0:
            raise ValueError("cooldown_bars must be non-negative")
        if self.config.max_pyramids < 0:
            raise ValueError("max_pyramids must be non-negative")
        if self.config.pyramid_unit_scale < 0.0:
            raise ValueError("pyramid_unit_scale must be non-negative")
        if self.config.max_pyramids > 0 and self.config.pyramid_step_pct <= 0.0:
            raise ValueError("pyramid_step_pct must be positive when pyramiding is enabled")
        if self.config.risk_budget_pct is not None:
            if self.config.risk_budget_pct <= 0.0:
                raise ValueError("risk_budget_pct must be positive")
            if self.config.stop_loss_pct is None or self.config.stop_loss_pct <= 0.0:
                raise ValueError("stop_loss_pct must be positive when risk_budget_pct is configured")
        for name, value in (
            ("long_allocation", self.config.long_allocation),
            ("short_allocation", self.config.short_allocation),
        ):
            if value < 0.0:
                raise ValueError(f"{name} must be non-negative")
        for name, value in (
            ("stop_loss_pct", self.config.stop_loss_pct),
            ("trailing_stop_pct", self.config.trailing_stop_pct),
            ("take_profit_pct", self.config.take_profit_pct),
        ):
            if value is not None and value <= 0.0:
                raise ValueError(f"{name} must be positive when provided")

    def _uses_price_context(self) -> bool:
        return (
            self.config.stop_loss_pct is not None
            or self.config.trailing_stop_pct is not None
            or self.config.take_profit_pct is not None
            or self.config.max_pyramids > 0
        )

    def _desired_direction(self, signal: object) -> int:
        if pd.isna(signal):
            return 0
        value = float(signal)
        if value > 0.0:
            return 1
        if value < 0.0:
            return -1
        return 0

    def _updated_trail_reference(
        self,
        *,
        current_direction: int,
        price: float,
        current_reference: float,
    ) -> float:
        if pd.isna(current_reference):
            return price
        if current_direction > 0:
            return max(float(current_reference), price)
        return min(float(current_reference), price)

    def _should_exit(
        self,
        *,
        current_direction: int,
        price: float,
        entry_price: float,
        trail_reference: float,
    ) -> bool:
        if pd.isna(entry_price):
            return False

        if self.config.stop_loss_pct is not None:
            stop_level = (
                entry_price * (1.0 - self.config.stop_loss_pct)
                if current_direction > 0
                else entry_price * (1.0 + self.config.stop_loss_pct)
            )
            if current_direction > 0 and price <= stop_level:
                return True
            if current_direction < 0 and price >= stop_level:
                return True

        if self.config.trailing_stop_pct is not None and not pd.isna(trail_reference):
            trailing_level = (
                float(trail_reference) * (1.0 - self.config.trailing_stop_pct)
                if current_direction > 0
                else float(trail_reference) * (1.0 + self.config.trailing_stop_pct)
            )
            if current_direction > 0 and price <= trailing_level:
                return True
            if current_direction < 0 and price >= trailing_level:
                return True

        if self.config.take_profit_pct is not None:
            pnl = current_direction * (price / entry_price - 1.0)
            if pnl >= self.config.take_profit_pct:
                return True

        return False

    def _apply_pyramids(
        self,
        *,
        current_direction: int,
        price: float,
        current_count: int,
        last_add_price: float,
    ) -> tuple[int, float]:
        if self.config.max_pyramids == 0:
            return current_count, last_add_price
        if pd.isna(last_add_price):
            return current_count, price

        updated_count = current_count
        updated_last_add = float(last_add_price)
        tolerance = 1e-12
        while updated_count < self.config.max_pyramids:
            threshold = (
                updated_last_add * (1.0 + self.config.pyramid_step_pct)
                if current_direction > 0
                else updated_last_add * (1.0 - self.config.pyramid_step_pct)
            )
            crossed = (
                price >= threshold - tolerance
                if current_direction > 0
                else price <= threshold + tolerance
            )
            if not crossed:
                break
            updated_count += 1
            updated_last_add = price
        return updated_count, updated_last_add

    def _position_weight(
        self,
        *,
        current_direction: int,
        pyramid_count: int,
    ) -> float:
        allocation_cap = self.config.long_allocation if current_direction > 0 else self.config.short_allocation
        base_unit = allocation_cap
        if self.config.risk_budget_pct is not None and self.config.stop_loss_pct is not None:
            base_unit = min(allocation_cap, self.config.risk_budget_pct / self.config.stop_loss_pct)
        gross_weight = min(
            allocation_cap,
            base_unit * (1.0 + pyramid_count * self.config.pyramid_unit_scale),
        )
        return gross_weight if current_direction > 0 else -gross_weight
