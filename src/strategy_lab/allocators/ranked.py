from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json

import pandas as pd

from strategy_lab.allocators.common import apply_liquidation_risk_overlay


@dataclass(frozen=True, slots=True)
class RankedCrossSectionalAllocatorConfig:
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


@dataclass(slots=True)
class RankedCrossSectionalAllocator:
    config: RankedCrossSectionalAllocatorConfig

    @classmethod
    def from_options(cls, options: dict[str, object] | None = None) -> "RankedCrossSectionalAllocator":
        return cls(config=RankedCrossSectionalAllocatorConfig(**(options or {})))

    def spec(self) -> dict[str, object]:
        return {
            "class_name": type(self).__name__,
            "config": asdict(self.config),
        }

    def version(self) -> str:
        encoded = json.dumps(self.spec(), sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:16]

    def required_risk_features(self) -> list[str]:
        return [
            self.config.liquidation_spike_factor,
            self.config.liquidation_ratio_factor,
            self.config.liquidation_cooldown_factor,
        ]

    def build_weights(
        self,
        signal_frame: pd.DataFrame,
        risk_features: dict[str, pd.DataFrame] | None = None,
        price_frame: pd.DataFrame | None = None,
        factor_frames: dict[str, pd.DataFrame] | None = None,
    ) -> pd.DataFrame:
        del price_frame, factor_frames

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

        if risk_features:
            weights = apply_liquidation_risk_overlay(
                weights,
                risk_features=risk_features,
                spike_factor=self.config.liquidation_spike_factor,
                ratio_factor=self.config.liquidation_ratio_factor,
                cooldown_factor=self.config.liquidation_cooldown_factor,
                max_spike_zscore=self.config.max_liquidation_spike_zscore,
                max_notional_ratio=self.config.max_liquidation_notional_ratio,
                weight_scale=self.config.liquidation_weight_scale,
                stop_on_event_cooldown=self.config.stop_on_event_cooldown,
            )
        return weights
