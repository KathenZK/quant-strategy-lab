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
class SpotCtaTrendConfig:
    symbols: tuple[str, ...] = ()
    donchian_only: bool = False
    breakout_factor: str = "donchian_breakout_20"
    donchian_exit_factor: str | None = None
    primary_momentum_factor: str = "ret_72"
    confirmation_momentum_factor: str = "ret_24"
    acceleration_momentum_factor: str | None = None
    trend_factor: str | None = None
    volume_factor: str = "volume_surge_20"
    rsi_factor: str = "rsi_14"
    illiquidity_factor: str | None = None
    volatility_factor: str | None = None
    require_breakout: bool = True
    min_breakout_signal: float = 1.0
    min_primary_momentum: float = 0.03
    min_confirmation_momentum: float = 0.0
    benchmark_momentum_factor: str | None = "benchmark_ret_24"
    min_benchmark_momentum: float | None = -0.03
    min_trend_distance: float = 0.0
    min_acceleration_momentum: float = 0.0
    min_volume_surge: float = -0.25
    min_rsi: float = 50.0
    max_rsi: float = 86.0
    max_amihud_illiquidity: float | None = None
    max_atr_pct: float | None = 0.30
    breakout_weight: float = 0.8
    primary_momentum_weight: float = 1.0
    confirmation_momentum_weight: float = 0.6
    acceleration_momentum_weight: float = 0.0
    trend_weight: float = 0.8
    volume_weight: float = 0.3
    rsi_weight: float = 0.2
    illiquidity_penalty_weight: float = 0.4
    volatility_penalty_weight: float = 0.3
    max_positions: int = 10
    long_allocation: float = 0.70
    stop_loss_pct: float | None = 0.10
    trailing_stop_pct: float | None = 0.18
    take_profit_pct: float | None = None
    max_hold_bars: int | None = None
    cooldown_bars: int = 6
    exit_on_signal_loss: bool = True
    exit_on_negative_signal: bool = False
    exit_signal_threshold: float = 0.0
    max_rank_hold_positions: int | None = 20
    failed_breakout_bars: int | None = None
    failed_breakout_min_profit_pct: float | None = None
    breakeven_after_profit_pct: float | None = None
    profit_trailing_activation_pct: float | None = None
    profit_trailing_stop_pct: float | None = None
    entry_confirmation_bars: int = 2
    max_entry_pullback_pct: float | None = 0.025
    min_entry_followthrough_pct: float = 0.0
    age_factor: str | None = "age_bars"
    min_entry_age_bars: int = 72
    young_age_bars: int = 240
    young_min_primary_momentum: float | None = 0.08
    young_min_volume_surge: float | None = 0.5
    young_max_rsi: float | None = 82.0
    entry_rank_limit: int | None = 20
    entry_score_quantile: float | None = 0.95
    failed_followthrough_bars: int | None = 12
    failed_followthrough_min_profit_pct: float | None = 0.02


@register_strategy("spot_cta_trend")
@dataclass(slots=True)
class SpotCtaTrendStrategy:
    """Isolated CTA trend strategy; no shared signal model or allocator."""

    config: SpotCtaTrendConfig

    @classmethod
    def from_options(cls, options: dict[str, object] | None = None) -> "SpotCtaTrendStrategy":
        return cls(config=SpotCtaTrendConfig(**(options or {})))

    @property
    def signal_name(self) -> str:
        return self.SIGNAL_TYPE

    def spec(self) -> dict[str, object]:
        return {"class_name": type(self).__name__, "config": asdict(self.config)}

    def version(self) -> str:
        encoded = json.dumps(self.spec(), sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:16]

    def required_factors(self) -> list[str]:
        if self.config.donchian_only:
            factors = [self.config.breakout_factor]
            if self.config.donchian_exit_factor is not None and self.config.donchian_exit_factor != self.config.breakout_factor:
                factors.append(self.config.donchian_exit_factor)
            return factors
        factors = [
            self.config.breakout_factor,
            self.config.primary_momentum_factor,
            self.config.confirmation_momentum_factor,
            self.config.volume_factor,
            self.config.rsi_factor,
        ]
        if self.config.benchmark_momentum_factor is not None:
            factors.append(self.config.benchmark_momentum_factor)
        if self.config.acceleration_momentum_factor is not None:
            factors.append(self.config.acceleration_momentum_factor)
        if self.config.trend_factor is not None:
            factors.append(self.config.trend_factor)
        if self.config.illiquidity_factor is not None:
            factors.append(self.config.illiquidity_factor)
        if self.config.volatility_factor is not None:
            factors.append(self.config.volatility_factor)
        if self.config.age_factor is not None:
            factors.append(self.config.age_factor)
        return factors

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
        return self._build_signal_frame(
            factors,
            require_breakout=self.config.require_breakout,
            apply_entry_filters=True,
        )

    def _build_signal_frame(
        self,
        factors: dict[str, pd.DataFrame],
        *,
        require_breakout: bool,
        apply_entry_filters: bool,
    ) -> pd.DataFrame:
        missing = [name for name in self.required_factors() if name not in factors]
        if missing:
            raise ValueError(f"missing factors for spot_cta_trend research strategy: {missing}")

        breakout = factors[self.config.breakout_factor]
        if self.config.donchian_only:
            entry = breakout.astype("float64").copy()
            exit_factor = self.config.donchian_exit_factor
            if exit_factor is None:
                return entry
            exit_breakout = factors[exit_factor].reindex_like(entry).astype("float64")
            signal = pd.DataFrame(float("nan"), index=entry.index, columns=entry.columns)
            signal = signal.where(~entry.gt(0.0), 1.0)
            signal = signal.where(~exit_breakout.lt(0.0), -1.0)
            return signal
        breakout_signal = breakout.fillna(0.0)
        primary = factors[self.config.primary_momentum_factor].reindex_like(breakout)
        confirm = factors[self.config.confirmation_momentum_factor].reindex_like(breakout)
        volume = factors[self.config.volume_factor].reindex_like(breakout)
        rsi = factors[self.config.rsi_factor].reindex_like(breakout)

        score = (
            self.config.breakout_weight * _cross_section_zscore(breakout_signal)
            + self.config.primary_momentum_weight * _cross_section_zscore(primary)
            + self.config.confirmation_momentum_weight * _cross_section_zscore(confirm)
            + self.config.volume_weight * _cross_section_zscore(volume)
            + self.config.rsi_weight * _cross_section_zscore((rsi - 50.0) / 50.0)
        )
        eligible = (
            primary.ge(self.config.min_primary_momentum)
            & confirm.ge(self.config.min_confirmation_momentum)
            & volume.ge(self.config.min_volume_surge)
            & rsi.ge(self.config.min_rsi)
            & rsi.le(self.config.max_rsi)
        )
        if require_breakout:
            eligible &= breakout_signal.ge(self.config.min_breakout_signal)

        acceleration = None
        if self.config.acceleration_momentum_factor is not None:
            acceleration = factors[self.config.acceleration_momentum_factor].reindex_like(breakout)
            score += self.config.acceleration_momentum_weight * _cross_section_zscore(acceleration)
            eligible &= acceleration.ge(self.config.min_acceleration_momentum)

        trend = None
        if self.config.trend_factor is not None:
            trend = factors[self.config.trend_factor].reindex_like(breakout)
            score += self.config.trend_weight * _cross_section_zscore(trend)
            eligible &= trend.ge(self.config.min_trend_distance)
        if self.config.illiquidity_factor is not None:
            illiquidity = factors[self.config.illiquidity_factor].reindex_like(breakout)
            score -= self.config.illiquidity_penalty_weight * _cross_section_zscore(illiquidity)
            if self.config.max_amihud_illiquidity is not None:
                eligible &= illiquidity.le(self.config.max_amihud_illiquidity)
        if self.config.volatility_factor is not None:
            volatility = factors[self.config.volatility_factor].reindex_like(breakout)
            score -= self.config.volatility_penalty_weight * _cross_section_zscore(volatility)
            if self.config.max_atr_pct is not None:
                eligible &= volatility.le(self.config.max_atr_pct)

        age = None
        if apply_entry_filters and self.config.age_factor is not None:
            age = factors[self.config.age_factor].reindex_like(breakout)
            eligible &= age.ge(self.config.min_entry_age_bars)
            young = age.lt(self.config.young_age_bars)
            if self.config.young_min_primary_momentum is not None:
                eligible &= ~young | primary.ge(self.config.young_min_primary_momentum)
            if self.config.young_min_volume_surge is not None:
                eligible &= ~young | volume.ge(self.config.young_min_volume_surge)
            if self.config.young_max_rsi is not None:
                eligible &= ~young | rsi.le(self.config.young_max_rsi)

        benchmark_momentum = None
        if apply_entry_filters and self.config.benchmark_momentum_factor is not None:
            benchmark_momentum = factors[self.config.benchmark_momentum_factor].reindex_like(breakout)
            if self.config.min_benchmark_momentum is not None:
                eligible &= benchmark_momentum.ge(self.config.min_benchmark_momentum)

        valid = primary.notna() & confirm.notna() & volume.notna() & rsi.notna()
        if acceleration is not None:
            valid &= acceleration.notna()
        if trend is not None:
            valid &= trend.notna()
        if age is not None:
            valid &= age.notna()
        if benchmark_momentum is not None:
            valid &= benchmark_momentum.notna()
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
        del liquidation_features
        self._validate()
        close = self._close_frame(signal_frame, price_frame)
        hold_signal_frame = self._hold_signal_frame(signal_frame, factors)
        weights = pd.DataFrame(0.0, index=signal_frame.index, columns=signal_frame.columns)
        current = pd.Series(False, index=signal_frame.columns, dtype="bool")
        entry_prices = pd.Series(float("nan"), index=signal_frame.columns, dtype="float64")
        trail_highs = pd.Series(float("nan"), index=signal_frame.columns, dtype="float64")
        holding_bars = pd.Series(0, index=signal_frame.columns, dtype="int64")
        cooldown_remaining = pd.Series(0, index=signal_frame.columns, dtype="int64")
        pending = pd.Series(False, index=signal_frame.columns, dtype="bool")
        pending_prices = pd.Series(float("nan"), index=signal_frame.columns, dtype="float64")
        pending_scores = pd.Series(float("nan"), index=signal_frame.columns, dtype="float64")
        pending_bars = pd.Series(0, index=signal_frame.columns, dtype="int64")

        for ts in signal_frame.index:
            cooldown_at_start = cooldown_remaining.copy()
            signal_row = signal_frame.loc[ts]
            hold_signal_row = hold_signal_frame.loc[ts]
            price_row = close.loc[ts]
            ranked_hold = self._ranked_hold_symbols(hold_signal_row)

            for symbol in signal_frame.columns:
                price = price_row.loc[symbol]
                if not current.loc[symbol] or pd.isna(price):
                    continue
                if self._exit_on_signal(symbol, hold_signal_row, ranked_hold):
                    current.loc[symbol] = False
                    entry_prices.loc[symbol] = float("nan")
                    trail_highs.loc[symbol] = float("nan")
                    holding_bars.loc[symbol] = 0
                    cooldown_remaining.loc[symbol] = self.config.cooldown_bars
                    continue
                holding_bars.loc[symbol] += 1
                trail_highs.loc[symbol] = max(float(trail_highs.loc[symbol]), float(price)) if not pd.isna(trail_highs.loc[symbol]) else float(price)
                if self._exit_on_price(float(price), entry_prices.loc[symbol], trail_highs.loc[symbol], int(holding_bars.loc[symbol])):
                    current.loc[symbol] = False
                    entry_prices.loc[symbol] = float("nan")
                    trail_highs.loc[symbol] = float("nan")
                    holding_bars.loc[symbol] = 0
                    cooldown_remaining.loc[symbol] = self.config.cooldown_bars

            open_slots = max(self.config.max_positions - int(current.sum()), 0)
            if self.config.entry_confirmation_bars > 0:
                ready: list[tuple[str, float]] = []
                for symbol in signal_frame.columns:
                    if not pending.loc[symbol]:
                        continue
                    price = price_row.loc[symbol]
                    if current.loc[symbol] or cooldown_remaining.loc[symbol] > 0 or pd.isna(price):
                        continue
                    pending_bars.loc[symbol] += 1
                    trigger_price = float(pending_prices.loc[symbol])
                    hold_signal_value = hold_signal_row.loc[symbol]
                    if (
                        pd.isna(trigger_price)
                        or self._entry_pullback_failed(float(price), trigger_price)
                        or pd.isna(hold_signal_value)
                        or float(hold_signal_value) <= self.config.exit_signal_threshold
                    ):
                        pending.loc[symbol] = False
                        pending_prices.loc[symbol] = float("nan")
                        pending_scores.loc[symbol] = float("nan")
                        pending_bars.loc[symbol] = 0
                        continue
                    if int(pending_bars.loc[symbol]) < self.config.entry_confirmation_bars:
                        continue
                    if self._entry_followthrough_ok(float(price), trigger_price):
                        ready.append((symbol, float(hold_signal_value)))
                    pending.loc[symbol] = False
                    pending_prices.loc[symbol] = float("nan")
                    pending_scores.loc[symbol] = float("nan")
                    pending_bars.loc[symbol] = 0

                for symbol, _ in sorted(ready, key=lambda item: item[1], reverse=True):
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

            if open_slots > 0:
                candidates = self._entry_candidates(signal_row)
                for symbol in candidates.index:
                    if self.config.entry_confirmation_bars <= 0 and open_slots <= 0:
                        break
                    price = price_row.loc[symbol]
                    if current.loc[symbol] or pending.loc[symbol] or cooldown_remaining.loc[symbol] > 0 or pd.isna(price):
                        continue
                    if self.config.entry_confirmation_bars > 0:
                        pending.loc[symbol] = True
                        pending_prices.loc[symbol] = float(price)
                        pending_scores.loc[symbol] = float(candidates.loc[symbol])
                        pending_bars.loc[symbol] = 0
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
        if self.config.entry_confirmation_bars < 0:
            raise ValueError("entry_confirmation_bars must be non-negative")
        if self.config.min_entry_age_bars < 0:
            raise ValueError("min_entry_age_bars must be non-negative")
        if self.config.young_age_bars < 0:
            raise ValueError("young_age_bars must be non-negative")
        if self.config.max_hold_bars is not None and self.config.max_hold_bars <= 0:
            raise ValueError("max_hold_bars must be positive when provided")
        if self.config.max_rank_hold_positions is not None and self.config.max_rank_hold_positions <= 0:
            raise ValueError("max_rank_hold_positions must be positive when provided")
        if self.config.entry_rank_limit is not None and self.config.entry_rank_limit <= 0:
            raise ValueError("entry_rank_limit must be positive when provided")
        if self.config.entry_score_quantile is not None and not 0.0 <= self.config.entry_score_quantile <= 1.0:
            raise ValueError("entry_score_quantile must be between 0 and 1 when provided")
        if (self.config.failed_breakout_bars is None) != (self.config.failed_breakout_min_profit_pct is None):
            raise ValueError("failed breakout exit requires both bars and min profit pct")
        if (self.config.failed_followthrough_bars is None) != (self.config.failed_followthrough_min_profit_pct is None):
            raise ValueError("failed followthrough exit requires both bars and min profit pct")
        if (self.config.profit_trailing_activation_pct is None) != (self.config.profit_trailing_stop_pct is None):
            raise ValueError("profit trailing exit requires both activation and stop pct")
        for name, value in (
            ("stop_loss_pct", self.config.stop_loss_pct),
            ("trailing_stop_pct", self.config.trailing_stop_pct),
            ("take_profit_pct", self.config.take_profit_pct),
            ("failed_breakout_min_profit_pct", self.config.failed_breakout_min_profit_pct),
            ("failed_followthrough_min_profit_pct", self.config.failed_followthrough_min_profit_pct),
            ("breakeven_after_profit_pct", self.config.breakeven_after_profit_pct),
            ("profit_trailing_activation_pct", self.config.profit_trailing_activation_pct),
            ("profit_trailing_stop_pct", self.config.profit_trailing_stop_pct),
            ("max_entry_pullback_pct", self.config.max_entry_pullback_pct),
        ):
            if value is not None and value <= 0.0:
                raise ValueError(f"{name} must be positive when provided")

    def _close_frame(self, signal_frame: pd.DataFrame, price_frame: pd.DataFrame | None) -> pd.DataFrame:
        if price_frame is None:
            return pd.DataFrame(1.0, index=signal_frame.index, columns=signal_frame.columns)
        return price_frame.reindex(index=signal_frame.index, columns=signal_frame.columns)

    def _hold_signal_frame(self, signal_frame: pd.DataFrame, factors: dict[str, pd.DataFrame] | None) -> pd.DataFrame:
        if factors is None or self.config.donchian_only or not self.config.require_breakout:
            return signal_frame
        hold_signal = self._build_signal_frame(factors, require_breakout=False, apply_entry_filters=False)
        return hold_signal.reindex(index=signal_frame.index, columns=signal_frame.columns)

    def _ranked_hold_symbols(self, signal_row: pd.Series) -> set[str] | None:
        if self.config.max_rank_hold_positions is None:
            return None
        candidates = signal_row[signal_row > self.config.exit_signal_threshold].dropna().sort_values(ascending=False)
        return set(candidates.head(self.config.max_rank_hold_positions).index)

    def _entry_candidates(self, signal_row: pd.Series) -> pd.Series:
        candidates = signal_row[signal_row > 0.0].dropna()
        if candidates.empty:
            return candidates
        if self.config.entry_score_quantile is not None:
            candidates = candidates[candidates >= candidates.quantile(self.config.entry_score_quantile)]
        candidates = candidates.sort_values(ascending=False)
        if self.config.entry_rank_limit is not None:
            candidates = candidates.head(self.config.entry_rank_limit)
        return candidates

    def _exit_on_signal(self, symbol: str, signal_row: pd.Series, ranked_hold: set[str] | None) -> bool:
        signal_value = signal_row.loc[symbol]
        if self.config.exit_on_negative_signal and not pd.isna(signal_value) and float(signal_value) < 0.0:
            return True
        if self.config.exit_on_signal_loss and (pd.isna(signal_value) or float(signal_value) <= self.config.exit_signal_threshold):
            return True
        return ranked_hold is not None and symbol not in ranked_hold

    def _exit_on_price(self, price: float, entry_price: float, trail_high: float, holding_bars: int) -> bool:
        if self.config.max_hold_bars is not None and holding_bars >= self.config.max_hold_bars:
            return True
        if pd.isna(entry_price):
            return False
        if self.config.stop_loss_pct is not None and price <= entry_price * (1.0 - self.config.stop_loss_pct):
            return True
        if self.config.take_profit_pct is not None and price >= entry_price * (1.0 + self.config.take_profit_pct):
            return True
        if (
            self.config.failed_followthrough_bars is not None
            and self.config.failed_followthrough_min_profit_pct is not None
            and holding_bars >= self.config.failed_followthrough_bars
            and not pd.isna(trail_high)
            and float(trail_high) < entry_price * (1.0 + self.config.failed_followthrough_min_profit_pct)
        ):
            return True
        if self.config.trailing_stop_pct is not None and not pd.isna(trail_high) and price <= float(trail_high) * (1.0 - self.config.trailing_stop_pct):
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
        return (
            self.config.profit_trailing_activation_pct is not None
            and self.config.profit_trailing_stop_pct is not None
            and not pd.isna(trail_high)
            and float(trail_high) >= entry_price * (1.0 + self.config.profit_trailing_activation_pct)
            and price <= float(trail_high) * (1.0 - self.config.profit_trailing_stop_pct)
        )

    def _entry_pullback_failed(self, price: float, trigger_price: float) -> bool:
        return (
            self.config.max_entry_pullback_pct is not None
            and price < trigger_price * (1.0 - self.config.max_entry_pullback_pct)
        )

    def _entry_followthrough_ok(self, price: float, trigger_price: float) -> bool:
        return price >= trigger_price * (1.0 + self.config.min_entry_followthrough_pct)

    def _position_weight(self) -> float:
        if self.config.max_positions == 0:
            return 0.0
        return self.config.long_allocation / self.config.max_positions
