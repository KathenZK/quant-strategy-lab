from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json

import numpy as np
import pandas as pd

from signal_lab.strategies.common import apply_liquidation_risk_overlay, cross_section_zscore
from signal_lab.strategies.registry import register_strategy


@dataclass(frozen=True, slots=True)
class CrowdingReversalConfig:
    long_term_momentum_factor: str = "ret_24"
    short_term_momentum_factor: str = "ret_4"
    funding_zscore_factor: str = "funding_zscore_72"
    basis_zscore_factor: str = "basis_zscore_72"
    oi_zscore_factor: str = "oi_zscore_72"
    price_oi_regime_factor: str = "price_oi_regime_4"
    min_abs_funding_zscore: float = 1.5
    min_abs_basis_zscore: float = 1.0
    min_oi_zscore: float = 1.0
    min_long_term_trend: float = 0.01
    short_term_reversal_floor: float = 0.0
    require_regime_confirmation: bool = True
    funding_weight: float = 1.0
    basis_weight: float = 1.0
    oi_weight: float = 0.75
    long_term_weight: float = 0.75
    short_term_weight: float = 1.0
    regime_weight: float = 0.5
    max_long_positions: int = 2
    max_short_positions: int = 2
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


@register_strategy("crowding_reversal")
@dataclass(slots=True)
class CrowdingReversalStrategy:
    config: CrowdingReversalConfig

    @classmethod
    def from_options(cls, options: dict[str, object] | None = None) -> "CrowdingReversalStrategy":
        payload = options or {}
        return cls(config=CrowdingReversalConfig(**payload))

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
            self.config.long_term_momentum_factor,
            self.config.short_term_momentum_factor,
            self.config.funding_zscore_factor,
            self.config.basis_zscore_factor,
            self.config.oi_zscore_factor,
            self.config.price_oi_regime_factor,
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
            raise ValueError(f"missing factors for crowding strategy: {missing}")

        long_term = factors[self.config.long_term_momentum_factor]
        short_term = factors[self.config.short_term_momentum_factor]
        funding = factors[self.config.funding_zscore_factor]
        basis = factors[self.config.basis_zscore_factor]
        oi = factors[self.config.oi_zscore_factor]
        regime = factors[self.config.price_oi_regime_factor]

        z_long_term = cross_section_zscore(long_term)
        z_short_term = cross_section_zscore(short_term)
        z_funding = cross_section_zscore(funding)
        z_basis = cross_section_zscore(basis)
        z_oi = cross_section_zscore(oi)
        z_regime = cross_section_zscore(regime.fillna(0.0))

        short_score = (
            self.config.funding_weight * z_funding
            + self.config.basis_weight * z_basis
            + self.config.oi_weight * z_oi
            + self.config.long_term_weight * z_long_term
            - self.config.short_term_weight * z_short_term
            - self.config.regime_weight * z_regime
        )
        long_score = (
            -self.config.funding_weight * z_funding
            - self.config.basis_weight * z_basis
            + self.config.oi_weight * z_oi
            - self.config.long_term_weight * z_long_term
            + self.config.short_term_weight * z_short_term
            + self.config.regime_weight * z_regime
        )

        crowded_long_mask = (
            (funding >= self.config.min_abs_funding_zscore)
            & (basis >= self.config.min_abs_basis_zscore)
            & (oi >= self.config.min_oi_zscore)
            & (long_term >= self.config.min_long_term_trend)
            & (short_term <= self.config.short_term_reversal_floor)
        )
        crowded_short_mask = (
            (funding <= -self.config.min_abs_funding_zscore)
            & (basis <= -self.config.min_abs_basis_zscore)
            & (oi >= self.config.min_oi_zscore)
            & (long_term <= -self.config.min_long_term_trend)
            & (short_term >= self.config.short_term_reversal_floor)
        )

        if self.config.require_regime_confirmation:
            crowded_long_mask &= regime <= 0
            crowded_short_mask &= regime >= 0

        signal = pd.DataFrame(np.nan, index=long_term.index, columns=long_term.columns, dtype="float64")
        signal = signal.where(~crowded_short_mask, long_score.abs())
        signal = signal.where(~crowded_long_mask, -short_score.abs())
        return signal

    def build_weights(
        self,
        signal_frame: pd.DataFrame,
        liquidation_features: dict[str, pd.DataFrame] | None = None,
        price_frame: pd.DataFrame | None = None,
        factors: dict[str, pd.DataFrame] | None = None,
    ) -> pd.DataFrame:
        del price_frame, factors
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
