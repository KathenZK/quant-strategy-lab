from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json

import pandas as pd

from strategy_lab.data import MarketType
from strategy_lab.strategies.registry import register_strategy


@dataclass(frozen=True, slots=True)
class SpotTrendConfig:
    symbols: tuple[str, ...] = ()
    breakout_factor: str = "donchian_breakout_strength_20"
    liquidity_rank_factor: str = "dollar_volume_1"
    benchmark_momentum_factor: str | None = None
    volatility_factor: str | None = "atr_pct_14"
    min_breakout_signal: float = 1.00
    min_liquidity_rank: float = 10_000_000.0
    max_liquidity_rank: float | None = 200_000_000.0
    min_benchmark_momentum: float | None = None
    max_positions: int = 7
    long_allocation: float = 1.00
    max_position_weight: float = 0.15
    min_volatility_pct: float = 0.005
    stop_loss_pct: float | None = 0.15
    trailing_atr_multiplier: float | None = 3.0
    failed_breakout_bars: int | None = 12
    min_followthrough_pct: float = 0.02
    refill_interval_bars: int = 12


@register_strategy("spot_trend")
@dataclass(slots=True)
class SpotTrendStrategy:
    """Isolated spot trend strategy; no shared signal model or allocator."""

    config: SpotTrendConfig

    @classmethod
    def from_options(cls, options: dict[str, object] | None = None) -> "SpotTrendStrategy":
        return cls(config=SpotTrendConfig(**(options or {})))

    @property
    def signal_name(self) -> str:
        return self.SIGNAL_TYPE

    def spec(self) -> dict[str, object]:
        return {"class_name": type(self).__name__, "config": asdict(self.config)}

    def version(self) -> str:
        encoded = json.dumps(self.spec(), sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:16]

    def required_factors(self) -> list[str]:
        factors = [self.config.breakout_factor, self.config.liquidity_rank_factor]
        if self.config.volatility_factor is not None:
            factors.append(self.config.volatility_factor)
        if self.config.benchmark_momentum_factor is not None:
            factors.append(self.config.benchmark_momentum_factor)
        return list(dict.fromkeys(factors))

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
            raise ValueError(f"missing factors for spot_trend research strategy: {missing}")

        breakout_score = factors[self.config.breakout_factor]
        liquidity_rank = factors[self.config.liquidity_rank_factor].reindex_like(breakout_score)
        eligible = breakout_score.gt(self.config.min_breakout_signal) & liquidity_rank.ge(self.config.min_liquidity_rank)
        if self.config.max_liquidity_rank is not None:
            eligible &= liquidity_rank.le(self.config.max_liquidity_rank)
        valid = liquidity_rank.notna()
        if self.config.benchmark_momentum_factor is not None:
            benchmark_momentum = factors[self.config.benchmark_momentum_factor].reindex_like(breakout_score)
            valid &= benchmark_momentum.notna()
            if self.config.min_benchmark_momentum is not None:
                eligible &= benchmark_momentum.ge(self.config.min_benchmark_momentum)
        signal = pd.DataFrame(float("nan"), index=breakout_score.index, columns=breakout_score.columns)
        signal = signal.where(~valid, 0.0)
        return signal.where(~eligible, breakout_score)

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
        volatility_frame = self._factor_frame(signal_frame, factors, self.config.volatility_factor)
        weights = pd.DataFrame(0.0, index=signal_frame.index, columns=signal_frame.columns)
        current = pd.Series(False, index=signal_frame.columns, dtype="bool")
        entry_prices = pd.Series(float("nan"), index=signal_frame.columns, dtype="float64")
        peak_prices = pd.Series(float("nan"), index=signal_frame.columns, dtype="float64")
        entry_scores = pd.Series(float("nan"), index=signal_frame.columns, dtype="float64")
        position_weights = pd.Series(0.0, index=signal_frame.columns, dtype="float64")
        holding_bars = pd.Series(0, index=signal_frame.columns, dtype="int64")
        bars_since_refill = self.config.refill_interval_bars

        for ts in signal_frame.index:
            composition_changed = False
            refilled_this_bar = False
            signal_row = signal_frame.loc[ts]
            price_row = close.loc[ts]
            volatility_row = volatility_frame.loc[ts] if volatility_frame is not None else None

            for symbol in signal_frame.columns:
                price = price_row.loc[symbol]
                if not current.loc[symbol] or pd.isna(price):
                    continue
                holding_bars.loc[symbol] = holding_bars.loc[symbol] + 1
                peak_prices.loc[symbol] = self._updated_peak(float(price), peak_prices.loc[symbol])

                if self._should_exit(
                    symbol=symbol,
                    price=float(price),
                    entry_price=entry_prices.loc[symbol],
                    peak_price=peak_prices.loc[symbol],
                    holding_bars=int(holding_bars.loc[symbol]),
                    volatility_row=volatility_row,
                ):
                    self._clear_position(symbol, current, entry_prices, peak_prices, entry_scores, holding_bars)
                    composition_changed = True

            open_slots = max(self.config.max_positions - int(current.sum()), 0)
            candidates = self._entry_candidates(signal_row)
            if open_slots > 0 and bars_since_refill >= self.config.refill_interval_bars:
                for symbol in candidates.index:
                    if open_slots <= 0:
                        break
                    price = price_row.loc[symbol]
                    if current.loc[symbol] or pd.isna(price):
                        continue
                    self._enter_position(symbol, float(price), float(candidates.loc[symbol]), current, entry_prices, peak_prices, entry_scores, holding_bars)
                    composition_changed = True
                    refilled_this_bar = True
                    open_slots -= 1

            active = current[current].index
            if composition_changed:
                position_weights.loc[:] = 0.0
                if len(active) > 0:
                    position_weights.loc[active] = self._target_weights(active, volatility_row)
            if len(active) > 0:
                weights.loc[ts, active] = position_weights.loc[active]
            bars_since_refill = 0 if refilled_this_bar else bars_since_refill + 1

        return weights

    def _validate(self) -> None:
        if self.config.max_positions < 0:
            raise ValueError("max_positions must be non-negative")
        if self.config.long_allocation < 0.0:
            raise ValueError("long_allocation must be non-negative")
        if self.config.max_position_weight <= 0.0:
            raise ValueError("max_position_weight must be positive")
        if self.config.min_volatility_pct <= 0.0:
            raise ValueError("min_volatility_pct must be positive")
        if self.config.refill_interval_bars < 0:
            raise ValueError("refill_interval_bars must be non-negative")
        if self.config.failed_breakout_bars is not None and self.config.failed_breakout_bars < 1:
            raise ValueError("failed_breakout_bars must be at least 1")
        if self.config.min_followthrough_pct < 0.0:
            raise ValueError("min_followthrough_pct must be non-negative")
        if self.config.trailing_atr_multiplier is not None and self.config.trailing_atr_multiplier <= 0.0:
            raise ValueError("trailing_atr_multiplier must be positive")
        if self.config.min_liquidity_rank < 0.0:
            raise ValueError("min_liquidity_rank must be non-negative")
        if self.config.max_liquidity_rank is not None and self.config.max_liquidity_rank <= self.config.min_liquidity_rank:
            raise ValueError("max_liquidity_rank must be greater than min_liquidity_rank")
        if self.config.stop_loss_pct is not None and self.config.stop_loss_pct <= 0.0:
            raise ValueError("stop_loss_pct must be positive")

    def _close_frame(self, signal_frame: pd.DataFrame, price_frame: pd.DataFrame | None) -> pd.DataFrame:
        if price_frame is None:
            return pd.DataFrame(1.0, index=signal_frame.index, columns=signal_frame.columns)
        return price_frame.reindex(index=signal_frame.index, columns=signal_frame.columns)

    def _factor_frame(
        self,
        signal_frame: pd.DataFrame,
        factors: dict[str, pd.DataFrame] | None,
        factor_name: str | None,
    ) -> pd.DataFrame | None:
        if factor_name is None or factors is None or factor_name not in factors:
            return None
        return factors[factor_name].reindex_like(signal_frame)

    def _entry_candidates(self, signal_row: pd.Series) -> pd.Series:
        candidates = signal_row[signal_row > 0.0].dropna()
        if candidates.empty:
            return candidates
        return candidates.sort_values(ascending=False)

    def _updated_peak(self, price: float, peak_price: float) -> float:
        if pd.isna(peak_price):
            return price
        return max(price, float(peak_price))

    def _should_exit(
        self,
        *,
        symbol: str,
        price: float,
        entry_price: float,
        peak_price: float,
        holding_bars: int,
        volatility_row: pd.Series | None,
    ) -> bool:
        if self._exit_on_price(price, entry_price):
            return True
        if self._exit_on_atr_trailing(symbol, price, peak_price, volatility_row):
            return True
        return self._exit_on_failed_breakout(peak_price, entry_price, holding_bars)

    def _exit_on_price(self, price: float, entry_price: float) -> bool:
        if pd.isna(entry_price):
            return False
        return self.config.stop_loss_pct is not None and price <= entry_price * (1.0 - self.config.stop_loss_pct)

    def _exit_on_atr_trailing(
        self,
        symbol: str,
        price: float,
        peak_price: float,
        volatility_row: pd.Series | None,
    ) -> bool:
        if self.config.trailing_atr_multiplier is None or volatility_row is None or pd.isna(peak_price):
            return False
        volatility = volatility_row.loc[symbol]
        if pd.isna(volatility) or float(volatility) <= 0.0:
            return False
        trailing_stop = float(peak_price) * (1.0 - self.config.trailing_atr_multiplier * float(volatility))
        return price <= trailing_stop

    def _exit_on_failed_breakout(self, peak_price: float, entry_price: float, holding_bars: int) -> bool:
        if self.config.failed_breakout_bars is None or pd.isna(peak_price) or pd.isna(entry_price):
            return False
        return holding_bars >= self.config.failed_breakout_bars and peak_price < entry_price * (1.0 + self.config.min_followthrough_pct)

    def _enter_position(
        self,
        symbol: str,
        price: float,
        score: float,
        current: pd.Series,
        entry_prices: pd.Series,
        peak_prices: pd.Series,
        entry_scores: pd.Series,
        holding_bars: pd.Series,
    ) -> None:
        current.loc[symbol] = True
        entry_prices.loc[symbol] = price
        peak_prices.loc[symbol] = price
        entry_scores.loc[symbol] = score
        holding_bars.loc[symbol] = 0

    def _clear_position(
        self,
        symbol: str,
        current: pd.Series,
        entry_prices: pd.Series,
        peak_prices: pd.Series,
        entry_scores: pd.Series,
        holding_bars: pd.Series,
    ) -> None:
        current.loc[symbol] = False
        entry_prices.loc[symbol] = float("nan")
        peak_prices.loc[symbol] = float("nan")
        entry_scores.loc[symbol] = float("nan")
        holding_bars.loc[symbol] = 0

    def _target_weights(self, active: pd.Index, volatility_row: pd.Series | None) -> pd.Series:
        if len(active) == 0:
            return pd.Series(dtype="float64")
        if volatility_row is None:
            equal_weight = min(self.config.long_allocation / len(active), self.config.max_position_weight)
            return pd.Series(equal_weight, index=active, dtype="float64")

        volatility = volatility_row.reindex(active).astype("float64")
        volatility = volatility.where(volatility.gt(self.config.min_volatility_pct), self.config.min_volatility_pct)
        if volatility.isna().all():
            equal_weight = min(self.config.long_allocation / len(active), self.config.max_position_weight)
            return pd.Series(equal_weight, index=active, dtype="float64")
        volatility = volatility.fillna(volatility.median())
        inverse_vol = 1.0 / volatility
        raw = inverse_vol / inverse_vol.sum() * self.config.long_allocation
        return raw.clip(upper=self.config.max_position_weight)
