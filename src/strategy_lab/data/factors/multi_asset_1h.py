from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

from strategy_lab.data.factors.base import FactorMetadata, FactorRegistry, PandasFactor
from strategy_lab.data.factors.derivatives import (
    FundingRateFactor,
    FundingRateZScoreFactor,
)
from strategy_lab.data.factors.lifecycle import AgeBarsFactor
from strategy_lab.data.factors.liquidity import (
    AmihudIlliquidityFactor,
    AverageDollarVolumeFactor,
    RollingDollarVolumeFactor,
    VWAPDistanceFactor,
    VolumeSurgeFactor,
)
from strategy_lab.data.factors.mean_reversion import (
    BollingerDistanceFactor,
    ZScoreFactor,
)
from strategy_lab.data.factors.momentum import (
    ATRPercentFactor,
    BearishCandleCountFactor,
    BreakoutFactor,
    BullishCandleCountFactor,
    DonchianBreakoutStrengthFactor,
    ExponentialMovingAverageSpreadFactor,
    MovingAverageDistanceFactor,
    RSIFactor,
    TrailingReturnFactor,
)


SeriesFn = Callable[[pd.DataFrame], pd.Series]


class FunctionalFactor(PandasFactor):
    def __init__(
        self,
        *,
        name: str,
        category: str,
        lookback: int,
        inputs: tuple[str, ...],
        formula: str,
        description: str,
        fn: SeriesFn,
        parameters: dict[str, object] | None = None,
    ) -> None:
        self._fn = fn
        self._parameters = parameters or {}
        self.metadata = FactorMetadata(
            name=name,
            category=category,
            frequency="1h",
            lookback=lookback,
            inputs=inputs,
            market_types=("perp",),
            description=description,
            formula=formula,
        )

    def compute(self, frame: pd.DataFrame) -> pd.Series:
        return self._fn(frame)

    def parameters(self) -> dict[str, object]:
        return self._parameters


def _rolling_zscore(series: pd.Series, window: int) -> pd.Series:
    mean = series.rolling(window, min_periods=window).mean()
    std = series.rolling(window, min_periods=window).std()
    return (series - mean) / std.replace(0.0, np.nan)


def _realized_volatility(frame: pd.DataFrame, window: int) -> pd.Series:
    returns = np.log(frame["close"]).diff()
    return returns.rolling(window, min_periods=window).std() * np.sqrt(24.0 * 365.0)


def _downside_volatility(frame: pd.DataFrame, window: int) -> pd.Series:
    returns = np.log(frame["close"]).diff().clip(upper=0.0)
    return returns.rolling(window, min_periods=window).std() * np.sqrt(24.0 * 365.0)


def _return_skew(frame: pd.DataFrame, window: int) -> pd.Series:
    return np.log(frame["close"]).diff().rolling(window, min_periods=window).skew()


def _max_drawdown(frame: pd.DataFrame, window: int) -> pd.Series:
    close = frame["close"]
    rolling_high = close.rolling(window, min_periods=window).max()
    return close / rolling_high.replace(0.0, np.nan) - 1.0


def _candle_range_pct(frame: pd.DataFrame) -> pd.Series:
    return (frame["high"] - frame["low"]) / frame["open"].replace(0.0, np.nan)


def _candle_body_strength(frame: pd.DataFrame) -> pd.Series:
    width = (frame["high"] - frame["low"]).replace(0.0, np.nan)
    return (frame["close"] - frame["open"]) / width


def _close_location(frame: pd.DataFrame) -> pd.Series:
    width = (frame["high"] - frame["low"]).replace(0.0, np.nan)
    return (frame["close"] - frame["low"]) / width


def _upper_wick(frame: pd.DataFrame) -> pd.Series:
    width = (frame["high"] - frame["low"]).replace(0.0, np.nan)
    return (frame["high"] - frame[["open", "close"]].max(axis=1)) / width


def _lower_wick(frame: pd.DataFrame) -> pd.Series:
    width = (frame["high"] - frame["low"]).replace(0.0, np.nan)
    return (frame[["open", "close"]].min(axis=1) - frame["low"]) / width


def _taker_imbalance(frame: pd.DataFrame) -> pd.Series:
    volume = frame["volume"].replace(0.0, np.nan)
    return 2.0 * frame["taker_buy_volume"] / volume - 1.0


def _rolling_mean(series_fn: SeriesFn, frame: pd.DataFrame, window: int) -> pd.Series:
    return series_fn(frame).rolling(window, min_periods=window).mean()


def _rolling_ratio(frame: pd.DataFrame, column: str, window: int) -> pd.Series:
    baseline = frame[column].rolling(window, min_periods=window).mean()
    return frame[column] / baseline.replace(0.0, np.nan) - 1.0


def _mark_premium(frame: pd.DataFrame) -> pd.Series:
    return frame["mark_price"] / frame["close"].replace(0.0, np.nan) - 1.0


def build_multi_asset_1h_factors() -> list[PandasFactor]:
    factors: list[PandasFactor] = [AgeBarsFactor(), FundingRateFactor(), VWAPDistanceFactor()]

    for window in [1, 2, 4, 8, 12, 24, 48, 72, 168, 336, 720]:
        factors.append(TrailingReturnFactor(window))
    for fast, slow in [
        (6, 24),
        (12, 48),
        (24, 96),
        (48, 192),
        (96, 384),
        (168, 720),
    ]:
        factors.append(ExponentialMovingAverageSpreadFactor(fast, slow))
    for window in [12, 24, 48, 96, 168, 336, 720]:
        factors.extend(
            [
                MovingAverageDistanceFactor(window),
                BreakoutFactor(window),
            ]
        )
    for window in [12, 24, 48, 96, 168, 336]:
        factors.append(DonchianBreakoutStrengthFactor(window))
    for window in [6, 12, 24, 48, 96]:
        factors.append(RSIFactor(window))
    for window in [6, 12, 24, 48, 96, 168, 336]:
        factors.append(ATRPercentFactor(window))
    for window in [24, 72, 168, 336]:
        factors.extend(
            [
                ZScoreFactor(window),
                BollingerDistanceFactor(window),
                BullishCandleCountFactor(window),
                BearishCandleCountFactor(window),
            ]
        )
    for window in [6, 24, 72, 168, 336]:
        factors.extend(
            [
                VolumeSurgeFactor(window),
                AverageDollarVolumeFactor(window),
                RollingDollarVolumeFactor(window),
            ]
        )
    factors.append(AmihudIlliquidityFactor())
    for window in [24, 72, 168, 336]:
        factors.append(FundingRateZScoreFactor(window))

    factors.extend(
        [
            FunctionalFactor(
                name="candle_range_pct",
                category="price_action",
                lookback=1,
                inputs=("open", "high", "low"),
                formula="(high-low)/open",
                description="Intrabar range normalized by open.",
                fn=_candle_range_pct,
            ),
            FunctionalFactor(
                name="candle_body_strength",
                category="price_action",
                lookback=1,
                inputs=("open", "high", "low", "close"),
                formula="(close-open)/(high-low)",
                description="Signed candle body as a fraction of range.",
                fn=_candle_body_strength,
            ),
            FunctionalFactor(
                name="close_location",
                category="price_action",
                lookback=1,
                inputs=("high", "low", "close"),
                formula="(close-low)/(high-low)",
                description="Close location within the bar range.",
                fn=_close_location,
            ),
            FunctionalFactor(
                name="upper_wick_ratio",
                category="price_action",
                lookback=1,
                inputs=("open", "high", "low", "close"),
                formula="(high-max(open,close))/(high-low)",
                description="Upper wick fraction of range.",
                fn=_upper_wick,
            ),
            FunctionalFactor(
                name="lower_wick_ratio",
                category="price_action",
                lookback=1,
                inputs=("open", "high", "low", "close"),
                formula="(min(open,close)-low)/(high-low)",
                description="Lower wick fraction of range.",
                fn=_lower_wick,
            ),
            FunctionalFactor(
                name="taker_imbalance_1",
                category="order_flow",
                lookback=1,
                inputs=("volume", "taker_buy_volume"),
                formula="2*taker_buy_volume/volume-1",
                description="Signed taker buy/sell volume imbalance.",
                fn=_taker_imbalance,
            ),
            FunctionalFactor(
                name="mark_premium",
                category="derivatives",
                lookback=1,
                inputs=("mark_price", "close"),
                formula="mark_price/close-1",
                description="Mark price premium to traded close.",
                fn=_mark_premium,
            ),
        ]
    )

    for window in [6, 12, 24, 72, 168, 336]:
        factors.extend(
            [
                FunctionalFactor(
                    name=f"realized_vol_{window}",
                    category="volatility",
                    lookback=window + 1,
                    inputs=("close",),
                    formula=f"std(log_return,{window})*sqrt(24*365)",
                    description="Annualized realized volatility.",
                    fn=lambda frame, w=window: _realized_volatility(frame, w),
                    parameters={"window": window},
                ),
                FunctionalFactor(
                    name=f"downside_vol_{window}",
                    category="volatility",
                    lookback=window + 1,
                    inputs=("close",),
                    formula=f"std(min(log_return,0),{window})*sqrt(24*365)",
                    description="Annualized downside volatility.",
                    fn=lambda frame, w=window: _downside_volatility(frame, w),
                    parameters={"window": window},
                ),
                FunctionalFactor(
                    name=f"max_drawdown_{window}",
                    category="volatility",
                    lookback=window,
                    inputs=("close",),
                    formula=f"close/rolling_max(close,{window})-1",
                    description="Current drawdown from the rolling high.",
                    fn=lambda frame, w=window: _max_drawdown(frame, w),
                    parameters={"window": window},
                ),
                FunctionalFactor(
                    name=f"taker_imbalance_mean_{window}",
                    category="order_flow",
                    lookback=window,
                    inputs=("volume", "taker_buy_volume"),
                    formula=f"mean(2*taker_buy_volume/volume-1,{window})",
                    description="Rolling taker imbalance.",
                    fn=lambda frame, w=window: _rolling_mean(_taker_imbalance, frame, w),
                    parameters={"window": window},
                ),
                FunctionalFactor(
                    name=f"quote_volume_ratio_{window}",
                    category="liquidity",
                    lookback=window,
                    inputs=("quote_volume",),
                    formula=f"quote_volume/mean(quote_volume,{window})-1",
                    description="Quote-volume surprise against its rolling mean.",
                    fn=lambda frame, w=window: _rolling_ratio(
                        frame, "quote_volume", w
                    ),
                    parameters={"window": window},
                ),
                FunctionalFactor(
                    name=f"trade_count_ratio_{window}",
                    category="liquidity",
                    lookback=window,
                    inputs=("trade_count",),
                    formula=f"trade_count/mean(trade_count,{window})-1",
                    description="Trade-count surprise against its rolling mean.",
                    fn=lambda frame, w=window: _rolling_ratio(frame, "trade_count", w),
                    parameters={"window": window},
                ),
            ]
        )
    for window in [24, 72, 168, 336]:
        factors.extend(
            [
                FunctionalFactor(
                    name=f"return_skew_{window}",
                    category="distribution",
                    lookback=window + 1,
                    inputs=("close",),
                    formula=f"skew(log_return,{window})",
                    description="Rolling return skewness.",
                    fn=lambda frame, w=window: _return_skew(frame, w),
                    parameters={"window": window},
                ),
                FunctionalFactor(
                    name=f"mark_premium_zscore_{window}",
                    category="derivatives",
                    lookback=window,
                    inputs=("mark_price", "close"),
                    formula=f"zscore(mark_price/close-1,{window})",
                    description="Rolling z-score of mark premium.",
                    fn=lambda frame, w=window: _rolling_zscore(_mark_premium(frame), w),
                    parameters={"window": window},
                ),
            ]
        )
    for window in [24, 72, 168]:
        factors.append(
            FunctionalFactor(
                name=f"funding_mean_{window}",
                category="derivatives",
                lookback=window,
                inputs=("funding_rate",),
                formula=f"mean(funding_rate,{window})",
                description="Rolling mean of the latest-known funding rate.",
                fn=lambda frame, w=window: frame["funding_rate"].rolling(
                    w, min_periods=w
                ).mean(),
                parameters={"window": window},
            )
        )
    return factors


def multi_asset_1h_registry() -> FactorRegistry:
    registry = FactorRegistry()
    for factor in build_multi_asset_1h_factors():
        registry.register(factor)
    return registry


__all__ = ["FunctionalFactor", "build_multi_asset_1h_factors", "multi_asset_1h_registry"]
