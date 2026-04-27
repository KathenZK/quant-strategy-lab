from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from strategy_lab.research.evaluation import FactorSummary, factor_summary, forward_returns, quantile_bucket_returns, rank_ic


def factor_decay(
    factor_frame: pd.DataFrame,
    price_frame: pd.DataFrame,
    *,
    horizons: tuple[int, ...] = (1, 2, 4, 8, 16),
) -> pd.Series:
    values: dict[str, float] = {}
    for horizon in horizons:
        future = forward_returns(price_frame, periods=horizon)
        values[f"h{horizon}"] = float(rank_ic(factor_frame, future).mean())
    return pd.Series(values, name="decay")


def factor_turnover(factor_frame: pd.DataFrame, *, quantiles: int = 5, target_bucket: int | None = None) -> pd.Series:
    bucket_index = target_bucket or quantiles - 1
    memberships: list[set[str]] = []
    timestamps: list[pd.Timestamp] = []
    for ts in factor_frame.index:
        row = factor_frame.loc[ts].dropna()
        if row.nunique() < quantiles:
            continue
        bucket = pd.qcut(row, q=quantiles, labels=False, duplicates="drop")
        selected = set(bucket[bucket == bucket_index].index.tolist())
        memberships.append(selected)
        timestamps.append(ts)

    values: list[float] = []
    labels: list[pd.Timestamp] = []
    for previous, current, label in zip(memberships, memberships[1:], timestamps[1:], strict=False):
        base = previous | current
        turnover = 0.0 if not base else 1.0 - len(previous & current) / len(base)
        values.append(turnover)
        labels.append(label)
    return pd.Series(values, index=labels, name="turnover")


def factor_correlation_matrix(factors: dict[str, pd.DataFrame]) -> pd.DataFrame:
    flattened = {}
    for name, frame in factors.items():
        series = frame.stack().dropna()
        series.index = [f"{timestamp}|{asset}" for timestamp, asset in series.index]
        flattened[name] = series
    combined = pd.DataFrame(flattened)
    return combined.corr()


def walk_forward_summary(
    factor_frame: pd.DataFrame,
    price_frame: pd.DataFrame,
    *,
    periods: int = 1,
    quantiles: int = 5,
    train_window: int = 60,
    step: int = 20,
) -> pd.DataFrame:
    rows = []
    timestamps = factor_frame.index
    for start in range(0, max(len(timestamps) - train_window + 1, 0), step):
        window_index = timestamps[start : start + train_window]
        if len(window_index) < train_window:
            continue
        summary = factor_summary(
            factor_frame.loc[window_index],
            price_frame.loc[window_index],
            periods=periods,
            quantiles=quantiles,
        )
        rows.append(
            {
                "start": window_index[0],
                "end": window_index[-1],
                "mean_rank_ic": summary.mean_rank_ic,
                "positive_rank_ic_ratio": summary.positive_rank_ic_ratio,
                "top_minus_bottom_mean": summary.top_minus_bottom_mean,
            }
        )
    return pd.DataFrame(rows)


@dataclass(frozen=True, slots=True)
class FactorDiagnostics:
    summary: FactorSummary
    quantile_returns: pd.DataFrame
    decay: pd.Series
    turnover: pd.Series
    walk_forward: pd.DataFrame


@dataclass(slots=True)
class FactorResearchLab:
    quantiles: int = 5
    horizons: tuple[int, ...] = (1, 2, 4, 8, 16)
    walk_forward_window: int = 60
    walk_forward_step: int = 20

    def evaluate(self, factor_frame: pd.DataFrame, price_frame: pd.DataFrame, *, periods: int = 1) -> FactorDiagnostics:
        future = forward_returns(price_frame, periods=periods)
        return FactorDiagnostics(
            summary=factor_summary(factor_frame, price_frame, periods=periods, quantiles=self.quantiles),
            quantile_returns=quantile_bucket_returns(factor_frame, future, quantiles=self.quantiles),
            decay=factor_decay(factor_frame, price_frame, horizons=self.horizons),
            turnover=factor_turnover(factor_frame, quantiles=self.quantiles),
            walk_forward=walk_forward_summary(
                factor_frame,
                price_frame,
                periods=periods,
                quantiles=self.quantiles,
                train_window=self.walk_forward_window,
                step=self.walk_forward_step,
            ),
        )
