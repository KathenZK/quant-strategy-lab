from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json

import pandas as pd

from strategy_lab.data import MarketType
from strategy_lab.strategies.registry import register_strategy


def _cross_section_zscore(frame: pd.DataFrame) -> pd.DataFrame:
    mean = frame.mean(axis=1)
    std = frame.std(axis=1, ddof=0).replace(0.0, pd.NA)
    return frame.sub(mean, axis=0).div(std, axis=0).fillna(0.0)


@dataclass(frozen=True, slots=True)
class SpotCtaPumpConfig:
    symbols: tuple[str, ...] = ()
    breakout_factor: str = "donchian_breakout_10"
    primary_momentum_factor: str = "ret_12"
    confirmation_momentum_factor: str = "ret_4"
    acceleration_momentum_factor: str = "ret_1"
    volume_factor: str = "volume_surge_20"
    rsi_factor: str = "rsi_14"
    min_primary_momentum: float = 0.06
    min_confirmation_momentum: float = 0.02
    min_acceleration_momentum: float = 0.0
    min_volume_surge: float = 0.5
    min_rsi: float = 55.0
    max_rsi: float = 96.0
    breakout_weight: float = 0.2
    primary_momentum_weight: float = 1.2
    confirmation_momentum_weight: float = 0.9
    acceleration_momentum_weight: float = 0.8
    volume_weight: float = 0.8
    rsi_weight: float = 0.1
    max_positions: int = 5
    long_allocation: float = 0.60
    stop_loss_pct: float | None = 0.08
    trailing_stop_pct: float | None = 0.28
    max_hold_bars: int | None = 36
    cooldown_bars: int = 4


@register_strategy("spot_cta_pump")
@dataclass(slots=True)
class SpotCtaPumpStrategy:
    """Isolated short-horizon pump scanner for Binance spot."""

    config: SpotCtaPumpConfig

    @classmethod
    def from_options(cls, options: dict[str, object] | None = None) -> "SpotCtaPumpStrategy":
        return cls(config=SpotCtaPumpConfig(**(options or {})))

    @property
    def signal_name(self) -> str:
        return self.SIGNAL_TYPE

    def spec(self) -> dict[str, object]:
        return {"class_name": type(self).__name__, "config": asdict(self.config)}

    def version(self) -> str:
        encoded = json.dumps(self.spec(), sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:16]

    def required_factors(self) -> list[str]:
        return [
            self.config.breakout_factor,
            self.config.primary_momentum_factor,
            self.config.confirmation_momentum_factor,
            self.config.acceleration_momentum_factor,
            self.config.volume_factor,
            self.config.rsi_factor,
        ]

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
        missing = [name for name in self.required_factors() if name not in factors]
        if missing:
            raise ValueError(f"missing factors for spot_cta_pump strategy: {missing}")
        breakout = factors[self.config.breakout_factor].fillna(0.0)
        primary = factors[self.config.primary_momentum_factor].reindex_like(breakout)
        confirm = factors[self.config.confirmation_momentum_factor].reindex_like(breakout)
        acceleration = factors[self.config.acceleration_momentum_factor].reindex_like(breakout)
        volume = factors[self.config.volume_factor].reindex_like(breakout)
        rsi = factors[self.config.rsi_factor].reindex_like(breakout)

        score = (
            self.config.breakout_weight * _cross_section_zscore(breakout)
            + self.config.primary_momentum_weight * _cross_section_zscore(primary)
            + self.config.confirmation_momentum_weight * _cross_section_zscore(confirm)
            + self.config.acceleration_momentum_weight * _cross_section_zscore(acceleration)
            + self.config.volume_weight * _cross_section_zscore(volume)
            + self.config.rsi_weight * _cross_section_zscore((rsi - 50.0) / 50.0)
        )
        eligible = (
            primary.ge(self.config.min_primary_momentum)
            & confirm.ge(self.config.min_confirmation_momentum)
            & acceleration.ge(self.config.min_acceleration_momentum)
            & volume.ge(self.config.min_volume_surge)
            & rsi.ge(self.config.min_rsi)
            & rsi.le(self.config.max_rsi)
        )
        valid = primary.notna() & confirm.notna() & acceleration.notna() & volume.notna() & rsi.notna()
        signal = pd.DataFrame(float("nan"), index=breakout.index, columns=breakout.columns)
        signal = signal.where(~valid, 0.0)
        return signal.where(~eligible, (score + 1.0).clip(lower=0.001))

    def build_weights(
        self,
        signal_frame: pd.DataFrame,
        liquidation_features: dict[str, pd.DataFrame] | None = None,
        price_frame: pd.DataFrame | None = None,
        factors: dict[str, pd.DataFrame] | None = None,
    ) -> pd.DataFrame:
        del liquidation_features, factors
        self._validate()
        close = price_frame.reindex_like(signal_frame) if price_frame is not None else pd.DataFrame(1.0, index=signal_frame.index, columns=signal_frame.columns)
        weights = pd.DataFrame(0.0, index=signal_frame.index, columns=signal_frame.columns)
        current = pd.Series(False, index=signal_frame.columns, dtype="bool")
        entry_prices = pd.Series(float("nan"), index=signal_frame.columns, dtype="float64")
        trail_highs = pd.Series(float("nan"), index=signal_frame.columns, dtype="float64")
        holding_bars = pd.Series(0, index=signal_frame.columns, dtype="int64")
        cooldown_remaining = pd.Series(0, index=signal_frame.columns, dtype="int64")

        for ts in signal_frame.index:
            cooldown_at_start = cooldown_remaining.copy()
            signal_row = signal_frame.loc[ts]
            price_row = close.loc[ts]
            for symbol in signal_frame.columns:
                price = price_row.loc[symbol]
                if not current.loc[symbol] or pd.isna(price):
                    continue
                holding_bars.loc[symbol] += 1
                trail_highs.loc[symbol] = max(float(trail_highs.loc[symbol]), float(price)) if not pd.isna(trail_highs.loc[symbol]) else float(price)
                if self._should_exit(float(price), entry_prices.loc[symbol], trail_highs.loc[symbol], int(holding_bars.loc[symbol])):
                    current.loc[symbol] = False
                    entry_prices.loc[symbol] = float("nan")
                    trail_highs.loc[symbol] = float("nan")
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
            cooldown_remaining.loc[cooldown_at_start > 0] = cooldown_remaining.loc[cooldown_at_start > 0] - 1
        return weights

    def _validate(self) -> None:
        if self.config.max_positions < 0:
            raise ValueError("max_positions must be non-negative")
        if self.config.long_allocation < 0.0:
            raise ValueError("long_allocation must be non-negative")
        if self.config.cooldown_bars < 0:
            raise ValueError("cooldown_bars must be non-negative")
        if self.config.max_hold_bars is not None and self.config.max_hold_bars <= 0:
            raise ValueError("max_hold_bars must be positive when provided")
        for name, value in (
            ("stop_loss_pct", self.config.stop_loss_pct),
            ("trailing_stop_pct", self.config.trailing_stop_pct),
        ):
            if value is not None and value <= 0.0:
                raise ValueError(f"{name} must be positive when provided")

    def _should_exit(self, price: float, entry_price: float, trail_high: float, holding_bars: int) -> bool:
        if self.config.max_hold_bars is not None and holding_bars >= self.config.max_hold_bars:
            return True
        if pd.isna(entry_price):
            return False
        if self.config.stop_loss_pct is not None and price <= entry_price * (1.0 - self.config.stop_loss_pct):
            return True
        return self.config.trailing_stop_pct is not None and not pd.isna(trail_high) and price <= float(trail_high) * (1.0 - self.config.trailing_stop_pct)

    def _position_weight(self) -> float:
        if self.config.max_positions == 0:
            return 0.0
        return self.config.long_allocation / self.config.max_positions
