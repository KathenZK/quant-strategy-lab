from __future__ import annotations

import pandas as pd


def cross_section_zscore(frame: pd.DataFrame) -> pd.DataFrame:
    mean = frame.mean(axis=1)
    std = frame.std(axis=1, ddof=0).replace(0.0, pd.NA)
    return frame.sub(mean, axis=0).div(std, axis=0).fillna(0.0)


def apply_liquidation_risk_overlay(
    weights: pd.DataFrame,
    *,
    liquidation_features: dict[str, pd.DataFrame] | None,
    spike_factor: str,
    ratio_factor: str,
    cooldown_factor: str,
    max_spike_zscore: float,
    max_notional_ratio: float,
    weight_scale: float,
    stop_on_event_cooldown: bool,
) -> pd.DataFrame:
    adjusted = weights.copy()
    if not liquidation_features:
        return adjusted

    spike = liquidation_features.get(spike_factor)
    ratio = liquidation_features.get(ratio_factor)
    cooldown = liquidation_features.get(cooldown_factor)
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
