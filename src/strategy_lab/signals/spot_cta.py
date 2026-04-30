from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json

import numpy as np
import pandas as pd

from strategy_lab.signals.common import cross_section_zscore


@dataclass(frozen=True, slots=True)
class SpotCtaTrendSignalConfig:
    breakout_factor: str = "donchian_breakout_20"
    primary_momentum_factor: str = "ret_72"
    confirmation_momentum_factor: str = "ret_24"
    trend_factor: str = "ma_distance_120"
    volume_factor: str = "volume_surge_20"
    rsi_factor: str = "rsi_14"
    illiquidity_factor: str | None = "amihud_illiquidity"
    volatility_factor: str | None = "atr_pct_14"
    min_breakout_signal: float = 1.0
    min_primary_momentum: float = 0.03
    min_confirmation_momentum: float = 0.0
    min_trend_distance: float = 0.0
    min_volume_surge: float = -0.25
    min_rsi: float = 50.0
    max_rsi: float = 86.0
    max_amihud_illiquidity: float | None = None
    max_atr_pct: float | None = 0.30
    breakout_weight: float = 0.8
    primary_momentum_weight: float = 1.0
    confirmation_momentum_weight: float = 0.6
    trend_weight: float = 0.8
    volume_weight: float = 0.3
    rsi_weight: float = 0.2
    illiquidity_penalty_weight: float = 0.4
    volatility_penalty_weight: float = 0.3


@dataclass(slots=True)
class SpotCtaTrendSignalModel:
    """Long-only trend-following signal for Binance spot CTA rotation."""

    config: SpotCtaTrendSignalConfig

    @classmethod
    def from_options(cls, options: dict[str, object] | None = None) -> "SpotCtaTrendSignalModel":
        return cls(config=SpotCtaTrendSignalConfig(**(options or {})))

    @property
    def signal_name(self) -> str:
        return "spot_cta_trend"

    def spec(self) -> dict[str, object]:
        return {
            "class_name": type(self).__name__,
            "config": asdict(self.config),
        }

    def version(self) -> str:
        encoded = json.dumps(self.spec(), sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:16]

    def required_factors(self) -> list[str]:
        factors = [
            self.config.breakout_factor,
            self.config.primary_momentum_factor,
            self.config.confirmation_momentum_factor,
            self.config.trend_factor,
            self.config.volume_factor,
            self.config.rsi_factor,
        ]
        if self.config.illiquidity_factor is not None:
            factors.append(self.config.illiquidity_factor)
        if self.config.volatility_factor is not None:
            factors.append(self.config.volatility_factor)
        return factors

    def build_signal_frame(self, factors: dict[str, pd.DataFrame]) -> pd.DataFrame:
        required = self.required_factors()
        missing = [name for name in required if name not in factors]
        if missing:
            raise ValueError(f"missing factors for spot CTA trend strategy: {missing}")

        breakout = factors[self.config.breakout_factor]
        # Donchian factors use NaN to mean "no fresh breakout". For this
        # cross-sectional CTA model that is a neutral signal, not missing data.
        breakout_signal = breakout.fillna(0.0)
        primary_momentum = factors[self.config.primary_momentum_factor].reindex_like(breakout)
        confirmation_momentum = factors[self.config.confirmation_momentum_factor].reindex_like(breakout)
        trend = factors[self.config.trend_factor].reindex_like(breakout)
        volume_surge = factors[self.config.volume_factor].reindex_like(breakout)
        rsi = factors[self.config.rsi_factor].reindex_like(breakout)

        score = (
            self.config.breakout_weight * cross_section_zscore(breakout_signal)
            + self.config.primary_momentum_weight * cross_section_zscore(primary_momentum)
            + self.config.confirmation_momentum_weight * cross_section_zscore(confirmation_momentum)
            + self.config.trend_weight * cross_section_zscore(trend)
            + self.config.volume_weight * cross_section_zscore(volume_surge)
            + self.config.rsi_weight * cross_section_zscore((rsi - 50.0) / 50.0)
        )

        eligible = (
            breakout_signal.ge(self.config.min_breakout_signal)
            & primary_momentum.ge(self.config.min_primary_momentum)
            & confirmation_momentum.ge(self.config.min_confirmation_momentum)
            & trend.ge(self.config.min_trend_distance)
            & volume_surge.ge(self.config.min_volume_surge)
            & rsi.ge(self.config.min_rsi)
            & rsi.le(self.config.max_rsi)
        )

        illiquidity_factor = self.config.illiquidity_factor
        if illiquidity_factor is not None:
            illiquidity = factors[illiquidity_factor].reindex_like(breakout)
            score -= self.config.illiquidity_penalty_weight * cross_section_zscore(illiquidity)
            if self.config.max_amihud_illiquidity is not None:
                eligible &= illiquidity.le(self.config.max_amihud_illiquidity)

        volatility_factor = self.config.volatility_factor
        if volatility_factor is not None:
            volatility = factors[volatility_factor].reindex_like(breakout)
            score -= self.config.volatility_penalty_weight * cross_section_zscore(volatility)
            if self.config.max_atr_pct is not None:
                eligible &= volatility.le(self.config.max_atr_pct)

        valid = (
            primary_momentum.notna()
            & confirmation_momentum.notna()
            & trend.notna()
            & volume_surge.notna()
            & rsi.notna()
        )
        signal = pd.DataFrame(np.nan, index=breakout.index, columns=breakout.columns, dtype="float64")
        signal = signal.where(~valid, 0.0)
        ranked_score = (score + 1.0).clip(lower=0.001)
        signal = signal.where(~eligible, ranked_score)
        return signal
