from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True, slots=True)
class RiskLimits:
    max_abs_weight: float = 0.20
    max_gross_leverage: float = 1.0
    max_net_exposure: float = 1.0
    min_dollar_volume: float = 0.0
    max_funding_rate_abs: float | None = None
    max_drawdown: float | None = None


@dataclass(slots=True)
class RiskManager:
    limits: RiskLimits

    def apply_weights(
        self,
        weights: pd.Series,
        *,
        dollar_volume_row: pd.Series | None = None,
        funding_rate_row: pd.Series | None = None,
        current_drawdown: float | None = None,
    ) -> pd.Series:
        constrained = weights.fillna(0.0).astype(float).copy()

        if current_drawdown is not None and self.limits.max_drawdown is not None and current_drawdown <= -abs(self.limits.max_drawdown):
            return pd.Series(0.0, index=constrained.index, name=weights.name)

        constrained = constrained.clip(lower=-self.limits.max_abs_weight, upper=self.limits.max_abs_weight)

        if dollar_volume_row is not None:
            aligned_volume = dollar_volume_row.reindex(constrained.index).fillna(0.0)
            constrained[aligned_volume < self.limits.min_dollar_volume] = 0.0

        if funding_rate_row is not None and self.limits.max_funding_rate_abs is not None:
            aligned_funding = funding_rate_row.reindex(constrained.index).fillna(0.0).abs()
            constrained[aligned_funding > self.limits.max_funding_rate_abs] = 0.0

        gross = constrained.abs().sum()
        if gross > self.limits.max_gross_leverage and gross > 0:
            constrained *= self.limits.max_gross_leverage / gross

        net = constrained.sum()
        if abs(net) > self.limits.max_net_exposure and net != 0:
            target_net = self.limits.max_net_exposure * (1 if net > 0 else -1)
            constrained -= (net - target_net) / len(constrained)
            gross = constrained.abs().sum()
            if gross > self.limits.max_gross_leverage and gross > 0:
                constrained *= self.limits.max_gross_leverage / gross
        return constrained.rename(weights.name)
