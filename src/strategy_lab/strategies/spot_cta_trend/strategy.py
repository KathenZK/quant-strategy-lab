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
    acceleration_momentum_factor: str | None = None
    volatility_factor: str | None = None
    require_breakout: bool = True
    min_breakout_signal: float = 1.0
    benchmark_momentum_factor: str | None = "benchmark_ret_24"
    min_benchmark_momentum: float | None = -0.03
    min_acceleration_momentum: float = 0.0
    max_atr_pct: float | None = 0.30
    breakout_weight: float = 0.8
    acceleration_momentum_weight: float = 0.0
    volatility_penalty_weight: float = 0.3
    max_positions: int = 7
    long_allocation: float = 1.00
    stop_loss_pct: float | None = 0.10
    cooldown_bars: int = 6
    exit_on_signal_loss: bool = True
    exit_signal_loss_bars: int = 6
    exit_on_negative_signal: bool = False
    exit_signal_threshold: float = 0.0
    entry_confirmation_bars: int = 1
    age_factor: str | None = "age_bars"
    min_entry_age_bars: int = 72
    entry_rank_limit: int | None = 20
    entry_score_quantile: float | None = 0.95


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
        ]
        if self.config.benchmark_momentum_factor is not None:
            factors.append(self.config.benchmark_momentum_factor)
        if self.config.acceleration_momentum_factor is not None:
            factors.append(self.config.acceleration_momentum_factor)
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

        score = self.config.breakout_weight * _cross_section_zscore(breakout_signal)
        eligible = pd.DataFrame(True, index=breakout.index, columns=breakout.columns)
        if require_breakout:
            eligible &= breakout_signal.ge(self.config.min_breakout_signal)

        acceleration = None
        if self.config.acceleration_momentum_factor is not None:
            acceleration = factors[self.config.acceleration_momentum_factor].reindex_like(breakout)
            score += self.config.acceleration_momentum_weight * _cross_section_zscore(acceleration)
            eligible &= acceleration.ge(self.config.min_acceleration_momentum)

        if self.config.volatility_factor is not None:
            volatility = factors[self.config.volatility_factor].reindex_like(breakout)
            score -= self.config.volatility_penalty_weight * _cross_section_zscore(volatility)
            if self.config.max_atr_pct is not None:
                eligible &= volatility.le(self.config.max_atr_pct)

        age = None
        if apply_entry_filters and self.config.age_factor is not None:
            age = factors[self.config.age_factor].reindex_like(breakout)
            eligible &= age.ge(self.config.min_entry_age_bars)

        benchmark_momentum = None
        if apply_entry_filters and self.config.benchmark_momentum_factor is not None:
            benchmark_momentum = factors[self.config.benchmark_momentum_factor].reindex_like(breakout)
            if self.config.min_benchmark_momentum is not None:
                eligible &= benchmark_momentum.ge(self.config.min_benchmark_momentum)

        valid = pd.DataFrame(True, index=breakout.index, columns=breakout.columns)
        if acceleration is not None:
            valid &= acceleration.notna()
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
        holding_bars = pd.Series(0, index=signal_frame.columns, dtype="int64")
        signal_loss_bars = pd.Series(0, index=signal_frame.columns, dtype="int64")
        cooldown_remaining = pd.Series(0, index=signal_frame.columns, dtype="int64")
        pending = pd.Series(False, index=signal_frame.columns, dtype="bool")
        pending_scores = pd.Series(float("nan"), index=signal_frame.columns, dtype="float64")
        pending_bars = pd.Series(0, index=signal_frame.columns, dtype="int64")

        for ts in signal_frame.index:
            cooldown_at_start = cooldown_remaining.copy()
            signal_row = signal_frame.loc[ts]
            hold_signal_row = hold_signal_frame.loc[ts]
            price_row = close.loc[ts]

            for symbol in signal_frame.columns:
                price = price_row.loc[symbol]
                if not current.loc[symbol] or pd.isna(price):
                    continue
                signal_lost = self._exit_on_signal(symbol, hold_signal_row)
                if signal_lost:
                    signal_loss_bars.loc[symbol] += 1
                else:
                    signal_loss_bars.loc[symbol] = 0
                if signal_lost and self._signal_loss_exit_ready(symbol, int(signal_loss_bars.loc[symbol])):
                    current.loc[symbol] = False
                    entry_prices.loc[symbol] = float("nan")
                    holding_bars.loc[symbol] = 0
                    signal_loss_bars.loc[symbol] = 0
                    cooldown_remaining.loc[symbol] = self.config.cooldown_bars
                    continue
                holding_bars.loc[symbol] += 1
                if self._exit_on_price(float(price), entry_prices.loc[symbol]):
                    current.loc[symbol] = False
                    entry_prices.loc[symbol] = float("nan")
                    holding_bars.loc[symbol] = 0
                    signal_loss_bars.loc[symbol] = 0
                    cooldown_remaining.loc[symbol] = self.config.cooldown_bars

            open_slots = max(self.config.max_positions - int(current.sum()), 0)
            if self.config.entry_confirmation_bars > 0:
                ready: list[tuple[str, float]] = []
                for symbol in signal_frame.columns:
                    if not pending.loc[symbol]:
                        continue
                    price = price_row.loc[symbol]
                    if current.loc[symbol] or cooldown_remaining.loc[symbol] > 0 or pd.isna(price):
                        pending.loc[symbol] = False
                        pending_scores.loc[symbol] = float("nan")
                        pending_bars.loc[symbol] = 0
                        continue
                    pending_bars.loc[symbol] += 1
                    if int(pending_bars.loc[symbol]) < self.config.entry_confirmation_bars:
                        continue
                    ready.append((symbol, float(pending_scores.loc[symbol])))
                    pending.loc[symbol] = False
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
                    holding_bars.loc[symbol] = 0
                    signal_loss_bars.loc[symbol] = 0
                    open_slots -= 1

            if open_slots > 0:
                candidates = self._entry_candidates(signal_row)
                for symbol in candidates.index:
                    if open_slots <= 0:
                        break
                    price = price_row.loc[symbol]
                    if current.loc[symbol] or pending.loc[symbol] or cooldown_remaining.loc[symbol] > 0 or pd.isna(price):
                        continue
                    if self.config.entry_confirmation_bars > 0:
                        pending.loc[symbol] = True
                        pending_scores.loc[symbol] = float(candidates.loc[symbol])
                        pending_bars.loc[symbol] = 0
                        continue
                    current.loc[symbol] = True
                    entry_prices.loc[symbol] = float(price)
                    holding_bars.loc[symbol] = 0
                    signal_loss_bars.loc[symbol] = 0
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
        if self.config.exit_signal_loss_bars <= 0:
            raise ValueError("exit_signal_loss_bars must be positive")
        if self.config.min_entry_age_bars < 0:
            raise ValueError("min_entry_age_bars must be non-negative")
        if self.config.entry_rank_limit is not None and self.config.entry_rank_limit <= 0:
            raise ValueError("entry_rank_limit must be positive when provided")
        if self.config.entry_score_quantile is not None and not 0.0 <= self.config.entry_score_quantile <= 1.0:
            raise ValueError("entry_score_quantile must be between 0 and 1 when provided")
        for name, value in (
            ("stop_loss_pct", self.config.stop_loss_pct),
        ):
            if value is not None and value <= 0.0:
                raise ValueError(f"{name} must be positive when provided")

    def _close_frame(self, signal_frame: pd.DataFrame, price_frame: pd.DataFrame | None) -> pd.DataFrame:
        if price_frame is None:
            return pd.DataFrame(1.0, index=signal_frame.index, columns=signal_frame.columns)
        return price_frame.reindex(index=signal_frame.index, columns=signal_frame.columns)

    def _hold_signal_frame(self, signal_frame: pd.DataFrame, factors: dict[str, pd.DataFrame] | None) -> pd.DataFrame:
        if factors is None or self.config.donchian_only:
            return signal_frame
        return pd.DataFrame(1.0, index=signal_frame.index, columns=signal_frame.columns)

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

    def _exit_on_signal(self, symbol: str, signal_row: pd.Series) -> bool:
        signal_value = signal_row.loc[symbol]
        if self.config.exit_on_negative_signal and not pd.isna(signal_value) and float(signal_value) < 0.0:
            return True
        if self.config.exit_on_signal_loss and (pd.isna(signal_value) or float(signal_value) <= self.config.exit_signal_threshold):
            return True
        return False

    def _signal_loss_exit_ready(self, symbol: str, signal_loss_bars: int) -> bool:
        del symbol
        if self.config.donchian_only and self.config.exit_on_negative_signal:
            return True
        return signal_loss_bars >= self.config.exit_signal_loss_bars

    def _exit_on_price(self, price: float, entry_price: float) -> bool:
        if pd.isna(entry_price):
            return False
        return self.config.stop_loss_pct is not None and price <= entry_price * (1.0 - self.config.stop_loss_pct)

    def _position_weight(self) -> float:
        if self.config.max_positions == 0:
            return 0.0
        return self.config.long_allocation / self.config.max_positions
