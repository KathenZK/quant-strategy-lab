from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json

import numpy as np
import pandas as pd

from signal_lab.strategies.common import apply_liquidation_risk_overlay, cross_section_zscore
from signal_lab.strategies.registry import register_strategy


@dataclass(frozen=True, slots=True)
class TrendConfirmationConfig:
    momentum_factor: str = "ret_24"
    breakout_factor: str = "breakout_20"
    oi_change_factor: str = "oi_change_4"
    basis_change_factor: str = "basis_change_4"
    funding_zscore_factor: str = "funding_zscore_72"
    volume_factor: str = "volume_surge_20"
    min_momentum: float = 0.0
    min_oi_change: float = 0.0
    min_basis_change: float = 0.0
    breakout_floor: float = -0.02
    min_volume_surge: float = -1.0
    max_abs_funding_zscore: float = 2.5
    momentum_weight: float = 1.0
    breakout_weight: float = 1.0
    oi_weight: float = 1.0
    basis_weight: float = 1.0
    volume_weight: float = 0.5
    funding_penalty_weight: float = 0.5
    max_long_positions: int = 3
    max_short_positions: int = 3
    long_allocation: float = 0.5
    short_allocation: float = 0.5
    market_neutral: bool = True
    liquidation_spike_factor: str = "liq_spike_zscore"
    liquidation_ratio_factor: str = "liq_notional_vs_dollar_volume"
    liquidation_cooldown_factor: str = "event_cooldown_flag"
    max_liquidation_spike_zscore: float = 2.5
    max_liquidation_notional_ratio: float = 0.03
    liquidation_weight_scale: float = 0.25
    stop_on_event_cooldown: bool = True


@register_strategy("trend_confirmation")
@dataclass(slots=True)
class TrendConfirmationStrategy:
    config: TrendConfirmationConfig

    @classmethod
    def from_options(cls, options: dict[str, object] | None = None) -> "TrendConfirmationStrategy":
        payload = options or {}
        return cls(config=TrendConfirmationConfig(**payload))

    @property
    def signal_name(self) -> str:
        return self.SIGNAL_TYPE

    def spec(self) -> dict[str, object]:
        return {
            "class_name": type(self).__name__,
            "config": asdict(self.config),
        }

    def version(self) -> str:
        encoded = json.dumps(self.spec(), sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:16]

    def required_factors(self) -> list[str]:
        return [
            self.config.momentum_factor,
            self.config.breakout_factor,
            self.config.oi_change_factor,
            self.config.basis_change_factor,
            self.config.funding_zscore_factor,
            self.config.volume_factor,
        ]

    def required_liquidation_features(self) -> list[str]:
        return [
            self.config.liquidation_spike_factor,
            self.config.liquidation_ratio_factor,
            self.config.liquidation_cooldown_factor,
        ]

    def build_signal_frame(self, factors: dict[str, pd.DataFrame]) -> pd.DataFrame:
        required = self.required_factors()
        missing = [name for name in required if name not in factors]
        if missing:
            raise ValueError(f"missing factors for trend strategy: {missing}")

        momentum = factors[self.config.momentum_factor]
        breakout = factors[self.config.breakout_factor]
        oi_change = factors[self.config.oi_change_factor]
        basis_change = factors[self.config.basis_change_factor]
        funding_zscore = factors[self.config.funding_zscore_factor]
        volume_surge = factors[self.config.volume_factor]

        z_momentum = cross_section_zscore(momentum)
        z_breakout = cross_section_zscore(breakout)
        z_oi = cross_section_zscore(oi_change)
        z_basis = cross_section_zscore(basis_change)
        z_volume = cross_section_zscore(volume_surge)
        z_funding_penalty = cross_section_zscore(funding_zscore.abs()).fillna(0.0)

        bullish_score = (
            self.config.momentum_weight * z_momentum
            + self.config.breakout_weight * z_breakout
            + self.config.oi_weight * z_oi
            + self.config.basis_weight * z_basis
            + self.config.volume_weight * z_volume
            - self.config.funding_penalty_weight * z_funding_penalty
        )
        bearish_score = (
            self.config.momentum_weight * (-z_momentum)
            + self.config.breakout_weight * (-z_breakout)
            + self.config.oi_weight * z_oi
            + self.config.basis_weight * (-z_basis)
            + self.config.volume_weight * z_volume
            - self.config.funding_penalty_weight * z_funding_penalty
        )

        long_mask = (
            (momentum > self.config.min_momentum)
            & (breakout > self.config.breakout_floor)
            & (oi_change > self.config.min_oi_change)
            & (basis_change > self.config.min_basis_change)
            & (volume_surge >= self.config.min_volume_surge)
            & (funding_zscore.abs() <= self.config.max_abs_funding_zscore)
        )
        short_mask = (
            (momentum < -self.config.min_momentum)
            & (breakout < -self.config.breakout_floor)
            & (oi_change > self.config.min_oi_change)
            & (basis_change < -self.config.min_basis_change)
            & (volume_surge >= self.config.min_volume_surge)
            & (funding_zscore.abs() <= self.config.max_abs_funding_zscore)
        )

        signal = pd.DataFrame(np.nan, index=momentum.index, columns=momentum.columns, dtype="float64")
        signal = signal.where(~long_mask, bullish_score)
        signal = signal.where(~short_mask, -bearish_score.abs())
        return signal

    def build_weights(
        self,
        signal_frame: pd.DataFrame,
        liquidation_features: dict[str, pd.DataFrame] | None = None,
    ) -> pd.DataFrame:
        weights = pd.DataFrame(0.0, index=signal_frame.index, columns=signal_frame.columns)
        for ts in signal_frame.index:
            row = signal_frame.loc[ts].dropna()
            if row.empty:
                continue

            long_candidates = row[row > 0].sort_values(ascending=False)
            short_candidates = row[row < 0].sort_values(ascending=True)

            if self.config.max_long_positions > 0:
                long_candidates = long_candidates.head(self.config.max_long_positions)
            else:
                long_candidates = long_candidates.iloc[0:0]

            if self.config.market_neutral and self.config.max_short_positions > 0:
                short_candidates = short_candidates.head(self.config.max_short_positions)
            else:
                short_candidates = short_candidates.iloc[0:0]

            if not self.config.market_neutral:
                short_candidates = short_candidates.iloc[0:0]

            if not long_candidates.empty:
                weights.loc[ts, long_candidates.index] = self.config.long_allocation / len(long_candidates)
            if not short_candidates.empty:
                weights.loc[ts, short_candidates.index] = -self.config.short_allocation / len(short_candidates)

        if liquidation_features:
            weights = self.apply_liquidation_risk_overlay(weights, liquidation_features)
        return weights

    def apply_liquidation_risk_overlay(
        self,
        weights: pd.DataFrame,
        liquidation_features: dict[str, pd.DataFrame],
    ) -> pd.DataFrame:
        return apply_liquidation_risk_overlay(
            weights,
            liquidation_features=liquidation_features,
            spike_factor=self.config.liquidation_spike_factor,
            ratio_factor=self.config.liquidation_ratio_factor,
            cooldown_factor=self.config.liquidation_cooldown_factor,
            max_spike_zscore=self.config.max_liquidation_spike_zscore,
            max_notional_ratio=self.config.max_liquidation_notional_ratio,
            weight_scale=self.config.liquidation_weight_scale,
            stop_on_event_cooldown=self.config.stop_on_event_cooldown,
        )
