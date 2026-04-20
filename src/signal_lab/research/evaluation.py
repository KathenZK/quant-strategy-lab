from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


def forward_returns(price_frame: pd.DataFrame, periods: int = 1) -> pd.DataFrame:
    return price_frame.shift(-periods) / price_frame - 1.0


def rank_ic(factor_frame: pd.DataFrame, future_returns: pd.DataFrame) -> pd.Series:
    aligned_factor, aligned_future = factor_frame.align(future_returns, join="inner")
    index = aligned_factor.index.intersection(aligned_future.index)
    values = []
    for ts in index:
        current_factor = aligned_factor.loc[ts]
        current_future = aligned_future.loc[ts]
        pair = pd.concat([current_factor, current_future], axis=1, keys=["factor", "future"]).dropna()
        values.append(pair["factor"].corr(pair["future"], method="spearman"))
    return pd.Series(values, index=index, name="rank_ic")


def quantile_bucket_returns(
    factor_frame: pd.DataFrame,
    future_returns: pd.DataFrame,
    quantiles: int = 5,
) -> pd.DataFrame:
    aligned_factor, aligned_future = factor_frame.align(future_returns, join="inner")
    results: list[pd.Series] = []
    for ts in aligned_factor.index:
        pair = pd.concat(
            [aligned_factor.loc[ts], aligned_future.loc[ts]],
            axis=1,
            keys=["factor", "future"],
        ).dropna()
        if pair.empty or pair["factor"].nunique() < quantiles:
            continue
        bucket = pd.qcut(pair["factor"], q=quantiles, labels=False, duplicates="drop")
        grouped = pair.groupby(bucket)["future"].mean()
        grouped.index = [f"q{int(item) + 1}" for item in grouped.index]
        results.append(grouped.rename(ts))
    if not results:
        return pd.DataFrame()
    return pd.DataFrame(results)


@dataclass(frozen=True, slots=True)
class FactorSummary:
    mean_rank_ic: float
    positive_rank_ic_ratio: float
    top_minus_bottom_mean: float


def factor_summary(
    factor_frame: pd.DataFrame,
    price_frame: pd.DataFrame,
    *,
    periods: int = 1,
    quantiles: int = 5,
) -> FactorSummary:
    future = forward_returns(price_frame, periods=periods)
    ic_series = rank_ic(factor_frame, future)
    quantile_returns = quantile_bucket_returns(factor_frame, future, quantiles=quantiles)
    spread = 0.0
    if not quantile_returns.empty:
        first_label = quantile_returns.columns[0]
        last_label = quantile_returns.columns[-1]
        spread = float((quantile_returns[last_label] - quantile_returns[first_label]).mean())
    return FactorSummary(
        mean_rank_ic=float(ic_series.mean()),
        positive_rank_ic_ratio=float((ic_series > 0).mean()),
        top_minus_bottom_mean=spread,
    )
