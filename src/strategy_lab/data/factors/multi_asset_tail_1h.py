from __future__ import annotations

import numpy as np
import pandas as pd

from strategy_lab.data.factors.base import FactorRegistry, PandasFactor
from strategy_lab.data.factors.multi_asset_1h import (
    FunctionalFactor,
    build_multi_asset_1h_factors,
)


def _log_return(frame: pd.DataFrame) -> pd.Series:
    return np.log(frame["close"]).diff()


def _upside_volatility(frame: pd.DataFrame, window: int) -> pd.Series:
    returns = _log_return(frame).clip(lower=0.0)
    return returns.rolling(window, min_periods=window).std() * np.sqrt(24.0 * 365.0)


def _return_kurtosis(frame: pd.DataFrame, window: int) -> pd.Series:
    return _log_return(frame).rolling(window, min_periods=window).kurt()


def _rolling_extreme_return(
    frame: pd.DataFrame, window: int, *, maximum: bool
) -> pd.Series:
    rolling = _log_return(frame).rolling(window, min_periods=window)
    return rolling.max() if maximum else rolling.min()


def _jump_count(
    frame: pd.DataFrame, window: int, *, threshold: float, upside: bool
) -> pd.Series:
    returns = _log_return(frame)
    event = returns.ge(threshold) if upside else returns.le(-threshold)
    return event.astype("float64").rolling(window, min_periods=window).sum()


def _range_max(frame: pd.DataFrame, window: int) -> pd.Series:
    range_pct = (frame["high"] - frame["low"]) / frame["open"].replace(0.0, np.nan)
    return range_pct.rolling(window, min_periods=window).max()


def _taker_imbalance_std(frame: pd.DataFrame, window: int) -> pd.Series:
    imbalance = 2.0 * frame["taker_buy_volume"] / frame["volume"].replace(
        0.0, np.nan
    ) - 1.0
    return imbalance.rolling(window, min_periods=window).std()


def _funding_event_sum(frame: pd.DataFrame, window: int) -> pd.Series:
    return frame["funding_event_rate"].rolling(window, min_periods=window).sum()


def _mark_premium_extreme(
    frame: pd.DataFrame, window: int, *, maximum: bool
) -> pd.Series:
    premium = frame["mark_price"] / frame["close"].replace(0.0, np.nan) - 1.0
    rolling = premium.rolling(window, min_periods=window)
    return rolling.max() if maximum else rolling.min()


def build_multi_asset_tail_1h_factors() -> list[PandasFactor]:
    factors = list(build_multi_asset_1h_factors())
    for window in [12, 24, 72, 168, 336]:
        factors.append(
            FunctionalFactor(
                name=f"upside_vol_{window}",
                category="tail_risk",
                lookback=window + 1,
                inputs=("close",),
                formula=f"std(max(log_return,0),{window})*sqrt(24*365)",
                description="Annualized upside semivolatility for short-squeeze risk.",
                fn=lambda frame, w=window: _upside_volatility(frame, w),
                parameters={"window": window},
            )
        )
    for window in [24, 72, 168, 336]:
        factors.append(
            FunctionalFactor(
                name=f"return_kurtosis_{window}",
                category="tail_risk",
                lookback=window + 1,
                inputs=("close",),
                formula=f"kurtosis(log_return,{window})",
                description="Rolling excess kurtosis of hourly log returns.",
                fn=lambda frame, w=window: _return_kurtosis(frame, w),
                parameters={"window": window},
            )
        )
    for window in [6, 24, 72, 168]:
        for maximum, side in [(True, "up"), (False, "down")]:
            factors.append(
                FunctionalFactor(
                    name=f"extreme_return_{side}_{window}",
                    category="tail_risk",
                    lookback=window + 1,
                    inputs=("close",),
                    formula=(
                        f"{'max' if maximum else 'min'}(log_return,{window})"
                    ),
                    description="Largest signed hourly return in the lookback.",
                    fn=lambda frame, w=window, use_max=maximum: (
                        _rolling_extreme_return(frame, w, maximum=use_max)
                    ),
                    parameters={"window": window, "maximum": maximum},
                )
            )
    for window in [24, 72, 168, 336]:
        for upside, side in [(True, "up"), (False, "down")]:
            factors.append(
                FunctionalFactor(
                    name=f"jump_count_{side}_3pct_{window}",
                    category="tail_risk",
                    lookback=window + 1,
                    inputs=("close",),
                    formula=(
                        f"count(log_return {'>=' if upside else '<='} "
                        f"{'0.03' if upside else '-0.03'},{window})"
                    ),
                    description="Count of 3% hourly jumps in the lookback.",
                    fn=lambda frame, w=window, is_up=upside: _jump_count(
                        frame, w, threshold=0.03, upside=is_up
                    ),
                    parameters={
                        "window": window,
                        "threshold": 0.03,
                        "upside": upside,
                    },
                )
            )
    for window in [24, 72, 168]:
        factors.extend(
            [
                FunctionalFactor(
                    name=f"range_max_{window}",
                    category="tail_risk",
                    lookback=window,
                    inputs=("open", "high", "low"),
                    formula=f"max((high-low)/open,{window})",
                    description="Largest intrabar range in the lookback.",
                    fn=lambda frame, w=window: _range_max(frame, w),
                    parameters={"window": window},
                ),
                FunctionalFactor(
                    name=f"taker_imbalance_std_{window}",
                    category="order_flow",
                    lookback=window,
                    inputs=("volume", "taker_buy_volume"),
                    formula=f"std(2*taker_buy_volume/volume-1,{window})",
                    description="Variability of taker imbalance.",
                    fn=lambda frame, w=window: _taker_imbalance_std(frame, w),
                    parameters={"window": window},
                ),
                FunctionalFactor(
                    name=f"funding_event_sum_{window}",
                    category="derivatives",
                    lookback=window,
                    inputs=("funding_event_rate",),
                    formula=f"sum(funding_event_rate,{window})",
                    description="Realized funding settlements in the lookback.",
                    fn=lambda frame, w=window: _funding_event_sum(frame, w),
                    parameters={"window": window},
                ),
            ]
        )
        for maximum, suffix in [(True, "max"), (False, "min")]:
            factors.append(
                FunctionalFactor(
                    name=f"mark_premium_{suffix}_{window}",
                    category="derivatives",
                    lookback=window,
                    inputs=("mark_price", "close"),
                    formula=(
                        f"{'max' if maximum else 'min'}(mark_price/close-1,{window})"
                    ),
                    description="Extreme mark-price premium in the lookback.",
                    fn=lambda frame, w=window, use_max=maximum: (
                        _mark_premium_extreme(frame, w, maximum=use_max)
                    ),
                    parameters={"window": window, "maximum": maximum},
                )
            )
    return factors


def multi_asset_tail_1h_registry() -> FactorRegistry:
    registry = FactorRegistry()
    for factor in build_multi_asset_tail_1h_factors():
        registry.register(factor)
    return registry


__all__ = ["build_multi_asset_tail_1h_factors", "multi_asset_tail_1h_registry"]
