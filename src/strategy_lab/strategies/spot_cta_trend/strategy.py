from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json

import pandas as pd

from strategy_lab.data import MarketType
from strategy_lab.strategies.registry import register_strategy


@dataclass(frozen=True, slots=True)
class SpotCtaTrendConfig:
    symbols: tuple[str, ...] = ()
    breakout_factor: str = "donchian_breakout_20"
    liquidity_rank_factor: str = "dollar_volume_24"
    benchmark_momentum_factor: str | None = "benchmark_ret_24"
    min_breakout_signal: float = 1.0
    min_liquidity_rank: float = 10_000_000.0
    max_liquidity_rank: float = 100_000_000.0
    min_benchmark_momentum: float | None = -0.03
    max_positions: int = 7
    long_allocation: float = 1.00
    stop_loss_pct: float | None = 0.15


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
        factors = [self.config.breakout_factor, self.config.liquidity_rank_factor]
        if self.config.benchmark_momentum_factor is not None:
            factors.append(self.config.benchmark_momentum_factor)
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
        missing = [name for name in self.required_factors() if name not in factors]
        if missing:
            raise ValueError(f"missing factors for spot_cta_trend research strategy: {missing}")

        breakout = factors[self.config.breakout_factor]
        breakout_signal = breakout.fillna(0.0)
        liquidity_rank = factors[self.config.liquidity_rank_factor].reindex_like(breakout)
        eligible = (
            breakout_signal.ge(self.config.min_breakout_signal)
            & liquidity_rank.ge(self.config.min_liquidity_rank)
            & liquidity_rank.le(self.config.max_liquidity_rank)
        )
        valid = liquidity_rank.notna()
        if self.config.benchmark_momentum_factor is not None:
            benchmark_momentum = factors[self.config.benchmark_momentum_factor].reindex_like(breakout)
            valid &= benchmark_momentum.notna()
            if self.config.min_benchmark_momentum is not None:
                eligible &= benchmark_momentum.ge(self.config.min_benchmark_momentum)
        signal = pd.DataFrame(float("nan"), index=breakout.index, columns=breakout.columns)
        signal = signal.where(~valid, 0.0)
        return signal.where(~eligible, liquidity_rank)

    def build_weights(
        self,
        signal_frame: pd.DataFrame,
        liquidation_features: dict[str, pd.DataFrame] | None = None,
        price_frame: pd.DataFrame | None = None,
        factors: dict[str, pd.DataFrame] | None = None,
    ) -> pd.DataFrame:
        del liquidation_features
        del factors
        self._validate()
        close = self._close_frame(signal_frame, price_frame)
        weights = pd.DataFrame(0.0, index=signal_frame.index, columns=signal_frame.columns)
        current = pd.Series(False, index=signal_frame.columns, dtype="bool")
        entry_prices = pd.Series(float("nan"), index=signal_frame.columns, dtype="float64")

        for ts in signal_frame.index:
            signal_row = signal_frame.loc[ts]
            price_row = close.loc[ts]

            for symbol in signal_frame.columns:
                price = price_row.loc[symbol]
                if not current.loc[symbol] or pd.isna(price):
                    continue
                if self._exit_on_price(float(price), entry_prices.loc[symbol]):
                    current.loc[symbol] = False
                    entry_prices.loc[symbol] = float("nan")

            open_slots = max(self.config.max_positions - int(current.sum()), 0)
            if open_slots > 0:
                candidates = self._entry_candidates(signal_row)
                for symbol in candidates.index:
                    if open_slots <= 0:
                        break
                    price = price_row.loc[symbol]
                    if current.loc[symbol] or pd.isna(price):
                        continue
                    current.loc[symbol] = True
                    entry_prices.loc[symbol] = float(price)
                    open_slots -= 1

            active = current[current].index
            if len(active) > 0:
                weights.loc[ts, active] = self._position_weight()

        return weights

    def _validate(self) -> None:
        if self.config.max_positions < 0:
            raise ValueError("max_positions must be non-negative")
        if self.config.long_allocation < 0.0:
            raise ValueError("long_allocation must be non-negative")
        if self.config.min_liquidity_rank < 0.0:
            raise ValueError("min_liquidity_rank must be non-negative")
        if self.config.max_liquidity_rank <= self.config.min_liquidity_rank:
            raise ValueError("max_liquidity_rank must be greater than min_liquidity_rank")
        if self.config.stop_loss_pct is not None and self.config.stop_loss_pct <= 0.0:
            raise ValueError("stop_loss_pct must be positive")

    def _close_frame(self, signal_frame: pd.DataFrame, price_frame: pd.DataFrame | None) -> pd.DataFrame:
        if price_frame is None:
            return pd.DataFrame(1.0, index=signal_frame.index, columns=signal_frame.columns)
        return price_frame.reindex(index=signal_frame.index, columns=signal_frame.columns)

    def _entry_candidates(self, signal_row: pd.Series) -> pd.Series:
        candidates = signal_row[signal_row > 0.0].dropna()
        if candidates.empty:
            return candidates
        candidates = candidates.sort_values(ascending=False)
        return candidates.head(self.config.max_positions)

    def _exit_on_price(self, price: float, entry_price: float) -> bool:
        if pd.isna(entry_price):
            return False
        return self.config.stop_loss_pct is not None and price <= entry_price * (1.0 - self.config.stop_loss_pct)

    def _position_weight(self) -> float:
        if self.config.max_positions == 0:
            return 0.0
        return self.config.long_allocation / self.config.max_positions
