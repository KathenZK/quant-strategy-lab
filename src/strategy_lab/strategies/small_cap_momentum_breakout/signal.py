from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json

import numpy as np
import pandas as pd

from .signal_common import cross_section_zscore


@dataclass(frozen=True, slots=True)
class SmallCapMomentumBreakoutSignalConfig:
    breakout_factor: str = "donchian_breakout_10"
    fast_momentum_factor: str = "ret_1"
    confirmation_momentum_factor: str = "ret_4"
    volume_factor: str = "volume_surge_20"
    rsi_factor: str = "rsi_14"
    illiquidity_factor: str | None = "amihud_illiquidity"
    min_breakout_signal: float = 1.0
    min_fast_momentum: float = 0.02
    min_confirmation_momentum: float = 0.01
    min_volume_surge: float = 2.0
    min_rsi: float = 55.0
    max_rsi: float = 88.0
    max_amihud_illiquidity: float | None = None
    breakout_weight: float = 0.5
    fast_momentum_weight: float = 1.0
    confirmation_momentum_weight: float = 0.6
    volume_weight: float = 0.8
    rsi_weight: float = 0.3
    illiquidity_penalty_weight: float = 0.4


@dataclass(slots=True)
class SmallCapMomentumBreakoutSignalModel:
    """Long-only intraday breakout signal for pre-filtered small-cap universes."""

    config: SmallCapMomentumBreakoutSignalConfig

    @classmethod
    def from_options(
        cls,
        options: dict[str, object] | None = None,
    ) -> "SmallCapMomentumBreakoutSignalModel":
        return cls(config=SmallCapMomentumBreakoutSignalConfig(**(options or {})))

    @property
    def signal_name(self) -> str:
        return "small_cap_momentum_breakout"

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
            self.config.fast_momentum_factor,
            self.config.confirmation_momentum_factor,
            self.config.volume_factor,
            self.config.rsi_factor,
        ]
        if self.config.illiquidity_factor is not None:
            factors.append(self.config.illiquidity_factor)
        return factors

    def build_signal_frame(self, factors: dict[str, pd.DataFrame]) -> pd.DataFrame:
        required = self.required_factors()
        missing = [name for name in required if name not in factors]
        if missing:
            raise ValueError(f"missing factors for small-cap momentum breakout strategy: {missing}")

        breakout = factors[self.config.breakout_factor]
        fast_momentum = factors[self.config.fast_momentum_factor].reindex_like(breakout)
        confirmation_momentum = factors[self.config.confirmation_momentum_factor].reindex_like(breakout)
        volume_surge = factors[self.config.volume_factor].reindex_like(breakout)
        rsi = factors[self.config.rsi_factor].reindex_like(breakout)

        score = (
            self.config.breakout_weight * cross_section_zscore(breakout.fillna(0.0))
            + self.config.fast_momentum_weight * cross_section_zscore(fast_momentum)
            + self.config.confirmation_momentum_weight * cross_section_zscore(confirmation_momentum)
            + self.config.volume_weight * cross_section_zscore(volume_surge)
            + self.config.rsi_weight * cross_section_zscore((rsi - 50.0) / 50.0)
        )

        eligible = (
            breakout.ge(self.config.min_breakout_signal)
            & fast_momentum.ge(self.config.min_fast_momentum)
            & confirmation_momentum.ge(self.config.min_confirmation_momentum)
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

        signal = pd.DataFrame(np.nan, index=breakout.index, columns=breakout.columns, dtype="float64")
        ranked_score = (score + 1.0).clip(lower=0.001)
        signal = signal.where(~eligible, ranked_score)
        return signal
