from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json

import numpy as np
import pandas as pd

from signal_lab.signals.common import cross_section_zscore


@dataclass(frozen=True, slots=True)
class CrowdingReversalSignalConfig:
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


@dataclass(slots=True)
class CrowdingReversalSignalModel:
    config: CrowdingReversalSignalConfig

    @classmethod
    def from_options(cls, options: dict[str, object] | None = None) -> "CrowdingReversalSignalModel":
        return cls(config=CrowdingReversalSignalConfig(**(options or {})))

    @property
    def signal_name(self) -> str:
        return "crowding_reversal"

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
