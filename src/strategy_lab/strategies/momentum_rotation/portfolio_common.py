from __future__ import annotations

import pandas as pd


def apply_liquidation_risk_overlay(
    weights: pd.DataFrame,
    *,
    risk_features: dict[str, pd.DataFrame] | None,
    spike_factor: str,
    ratio_factor: str,
    cooldown_factor: str,
    max_spike_zscore: float,
    max_notional_ratio: float,
    weight_scale: float,
    stop_on_event_cooldown: bool,
) -> pd.DataFrame:
    adjusted = weights.copy()
    if not risk_features:
        return adjusted

    spike = risk_features.get(spike_factor)
    ratio = risk_features.get(ratio_factor)
    cooldown = risk_features.get(cooldown_factor)
    if spike is None and ratio is None and cooldown is None:
        return adjusted

    for ts in adjusted.index:
        for symbol in adjusted.columns:
            weight = float(adjusted.loc[ts, symbol])
            if weight == 0.0:
                continue
            cooldown_flag = 0.0 if cooldown is None else float(cooldown.reindex(index=[ts], columns=[symbol]).iloc[0, 0])
            spike_value = 0.0 if spike is None else float(spike.reindex(index=[ts], columns=[symbol]).iloc[0, 0])
            ratio_value = 0.0 if ratio is None else float(ratio.reindex(index=[ts], columns=[symbol]).iloc[0, 0])

            if stop_on_event_cooldown and cooldown_flag > 0:
                adjusted.loc[ts, symbol] = 0.0
                continue

            if spike_value >= max_spike_zscore or ratio_value >= max_notional_ratio:
                adjusted.loc[ts, symbol] = weight * weight_scale
    return adjusted
