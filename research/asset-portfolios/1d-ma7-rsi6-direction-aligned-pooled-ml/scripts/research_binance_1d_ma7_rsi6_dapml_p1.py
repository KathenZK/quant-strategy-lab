from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from strategy_lab.data.fs import atomic_write_path

ROOT = Path(__file__).resolve().parents[4]
BTC_SCRIPT_DIR = (
    ROOT / "research/btc/1d-ma7-rsi6-lightgbm-trend/scripts"
)
BTC_P1_PATH = BTC_SCRIPT_DIR / "research_btc_1d_ma7_rsi6_lgbm_p1.py"
BTC_P1_SPEC = importlib.util.spec_from_file_location(
    "btc_ma7_rsi6_p1_shared",
    BTC_P1_PATH,
)
if BTC_P1_SPEC is None or BTC_P1_SPEC.loader is None:
    raise ImportError(f"Cannot load shared BTC P1 engine: {BTC_P1_PATH}")
btc_p1 = importlib.util.module_from_spec(BTC_P1_SPEC)
sys.modules[BTC_P1_SPEC.name] = btc_p1
BTC_P1_SPEC.loader.exec_module(btc_p1)


FAMILY_DIR = (
    ROOT
    / "research/asset-portfolios/1d-ma7-rsi6-direction-aligned-pooled-ml"
)
P0_ARTIFACT_DIR = FAMILY_DIR / "artifacts/p0_data_2026-08-10"
P1_ARTIFACT_DIR = FAMILY_DIR / "artifacts/p1_pooled_development_2026-08-10"
FEATURE_DIR = ROOT / "data/features/binance_1d_ma7_rsi6_dapml_p0"
DEVELOPMENT_END_EXCLUSIVE = pd.Timestamp("2025-08-07T00:00:00Z")
SEED = 20260810
EXPECTED_EVENT_ROWS = 2_091
EXPECTED_EVENT_SHA256 = (
    "c9bdf1d4e32fa85f11b6b2d5e9de3062d05489acef8ddc68497bfd3a65970b83"
)
EDGE_THRESHOLDS = (0.0, 0.005, 0.010)
INNER_MIN_TOTAL_PER_FOLD = 20
INNER_MIN_PER_ASSET_TOTAL = 5
BOOTSTRAP_SAMPLES = 10_000

ASSETS = {
    "BTC": "btcusdt",
    "ETH": "ethusdt",
    "BNB": "bnbusdt",
    "SOL": "solusdt",
    "TRX": "trxusdt",
}

ALIGNED_MA_FEATURES = (
    "aligned_prev_gap_atr",
    "aligned_close_gap_atr",
    "aligned_cross_span_atr",
    "aligned_ma7_slope_1_atr",
    "aligned_ma7_slope_3_atr",
    "prior_side_duration",
)
ALIGNED_K_FEATURES = (
    "aligned_body_atr",
    "range_atr",
    "rejection_wick_atr",
    "opposition_wick_atr",
    "aligned_close_location",
    "aligned_return_3_atr",
    "aligned_return_5_atr",
)
ALIGNED_RSI_FEATURES = (
    "aligned_rsi6",
    "aligned_rsi6_delta_1",
    "directional_rsi_extreme_5",
    "counter_rsi_extreme_5",
    "directional_rsi80_last5",
    "counter_rsi20_last5",
)
ALIGNED_FEATURES = (
    *ALIGNED_MA_FEATURES,
    *ALIGNED_K_FEATURES,
    *ALIGNED_RSI_FEATURES,
)
RAW_FEATURES = btc_p1.CORE_FEATURES

LGBM_PARAMS: dict[str, Any] = {
    "objective": "binary",
    "n_estimators": 120,
    "learning_rate": 0.03,
    "num_leaves": 7,
    "max_depth": 3,
    "min_child_samples": 20,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.5,
    "reg_lambda": 2.0,
    "random_state": SEED,
    "n_jobs": 1,
    "deterministic": True,
    "force_col_wise": True,
    "verbosity": -1,
}


@dataclass(frozen=True, slots=True)
class ModelVariant:
    variant_id: str
    model_type: str
    features: tuple[str, ...]
    primary_candidate: bool = False


VARIANTS = (
    ModelVariant(
        "logistic_ev_aligned",
        "logistic_ev",
        ALIGNED_FEATURES,
        primary_candidate=True,
    ),
    ModelVariant("logistic_ev_raw_control", "logistic_ev", RAW_FEATURES),
    ModelVariant("lgbm_ev_aligned_diagnostic", "lgbm_ev", ALIGNED_FEATURES),
)


class ConstantProbabilityModel:
    def __init__(self, probability: float) -> None:
        self.probability = float(probability)

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        positive = np.full(len(frame), self.probability, dtype="float64")
        return np.column_stack([1.0 - positive, positive])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build development-only five-asset direction-aligned MA7/RSI6 events "
            "and run frozen pooled time/asset generalization diagnostics."
        )
    )
    parser.add_argument("--output-dir", type=Path, default=P1_ARTIFACT_DIR)
    parser.add_argument("--p0-only", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, np.generic):
        return json_ready(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path: Path, payload: Any) -> None:
    atomic_write_path(
        path,
        lambda temp_path: temp_path.write_text(
            json.dumps(json_ready(payload), ensure_ascii=False, indent=2),
            encoding="utf-8",
        ),
    )


def feature_paths(slug: str) -> dict[str, Path]:
    return {
        "daily": FEATURE_DIR / f"{slug}_perp_1d.parquet",
        "hourly": FEATURE_DIR / f"{slug}_perp_1h.parquet",
        "funding": FEATURE_DIR / f"{slug}_perp_funding_mark.parquet",
    }


def load_asset_inputs(asset: str, slug: str) -> tuple[pd.DataFrame, ...]:
    paths = feature_paths(slug)
    for path in paths.values():
        if not path.exists():
            raise FileNotFoundError(path)
    daily = pd.read_parquet(
        paths["daily"],
        filters=[("ts", "<", DEVELOPMENT_END_EXCLUSIVE.to_pydatetime())],
    )
    hourly = pd.read_parquet(
        paths["hourly"],
        columns=["ts", "open", "high", "low", "close", "is_closed", "source"],
        filters=[("ts", "<", DEVELOPMENT_END_EXCLUSIVE.to_pydatetime())],
    )
    funding = pd.read_parquet(
        paths["funding"],
        columns=[
            "ts",
            "funding_nominal_ts",
            "funding_rate",
            "mark_price",
            "mark_price_source",
        ],
        filters=[("ts", "<", DEVELOPMENT_END_EXCLUSIVE.to_pydatetime())],
    )
    for frame in (daily, hourly, funding):
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
        frame.sort_values("ts", inplace=True)
        frame.reset_index(drop=True, inplace=True)
        if frame.empty or frame["ts"].max() >= DEVELOPMENT_END_EXCLUSIVE:
            raise RuntimeError(f"{asset} invalid development-only input")
    funding["funding_nominal_ts"] = pd.to_datetime(
        funding["funding_nominal_ts"], utc=True
    )
    if daily["ts"].duplicated().any() or hourly["ts"].duplicated().any():
        raise RuntimeError(f"{asset} OHLCV contains duplicate timestamps")
    if funding["funding_nominal_ts"].duplicated().any():
        raise RuntimeError(f"{asset} funding contains duplicate nominal timestamps")
    hourly_expected = pd.date_range(
        hourly["ts"].min(), hourly["ts"].max(), freq="1h"
    )
    if len(hourly_expected.difference(pd.DatetimeIndex(hourly["ts"]))):
        raise RuntimeError(f"{asset} development hourly path contains gaps")
    funding_gaps = (
        funding["funding_nominal_ts"].diff().dt.total_seconds().div(3600.0)
    )
    invalid_funding_gaps = funding_gaps.dropna().loc[
        funding_gaps.dropna().le(0.0)
        | funding_gaps.dropna().gt(8.0)
        | np.mod(funding_gaps.dropna(), 1.0).ne(0.0)
    ]
    if len(invalid_funding_gaps):
        raise RuntimeError(
            f"{asset} development funding contains invalid dynamic intervals"
        )
    return daily, hourly, funding


def add_direction_aligned_features(events: pd.DataFrame) -> pd.DataFrame:
    frame = events.copy()
    side = frame["side"].to_numpy(dtype="float64")
    frame["aligned_prev_gap_atr"] = side * frame["prev_close_ma_gap_atr"]
    frame["aligned_close_gap_atr"] = side * frame["close_ma_gap_atr"]
    frame["aligned_cross_span_atr"] = (
        frame["aligned_close_gap_atr"] - frame["aligned_prev_gap_atr"]
    )
    frame["aligned_ma7_slope_1_atr"] = side * frame["ma7_slope_1_atr"]
    frame["aligned_ma7_slope_3_atr"] = side * frame["ma7_slope_3_atr"]
    frame["aligned_body_atr"] = side * frame["body_atr"]
    frame["aligned_close_location"] = (
        0.5 + side * (frame["close_location"] - 0.5)
    )
    is_long = frame["side"].gt(0)
    frame["rejection_wick_atr"] = np.where(
        is_long, frame["lower_wick_atr"], frame["upper_wick_atr"]
    )
    frame["opposition_wick_atr"] = np.where(
        is_long, frame["upper_wick_atr"], frame["lower_wick_atr"]
    )
    frame["aligned_return_3_atr"] = side * frame["return_3_atr"]
    frame["aligned_return_5_atr"] = side * frame["return_5_atr"]
    frame["aligned_rsi6"] = np.where(
        is_long, frame["rsi6"], 100.0 - frame["rsi6"]
    )
    frame["aligned_rsi6_delta_1"] = side * frame["rsi6_delta_1"]
    frame["directional_rsi_extreme_5"] = np.where(
        is_long, frame["rsi6_max_5"], 100.0 - frame["rsi6_min_5"]
    )
    frame["counter_rsi_extreme_5"] = np.where(
        is_long, frame["rsi6_min_5"], 100.0 - frame["rsi6_max_5"]
    )
    frame["directional_rsi80_last5"] = np.where(
        is_long, frame["rsi6_high80_last5"], frame["rsi6_low20_last5"]
    )
    frame["counter_rsi20_last5"] = np.where(
        is_long, frame["rsi6_low20_last5"], frame["rsi6_high80_last5"]
    )
    if frame[list(ALIGNED_FEATURES)].isna().any().any():
        raise RuntimeError("Direction-aligned features contain missing values")
    if not np.isfinite(
        frame[list(ALIGNED_FEATURES)].to_numpy(dtype="float64")
    ).all():
        raise RuntimeError("Direction-aligned features contain non-finite values")
    return frame


def build_pooled_events() -> tuple[pd.DataFrame, dict[int, pd.DataFrame], dict[str, Any]]:
    frames: list[pd.DataFrame] = []
    pooled_paths: dict[int, pd.DataFrame] = {}
    asset_quality: dict[str, Any] = {}
    next_event_id = 0
    for asset, slug in ASSETS.items():
        daily, hourly, funding = load_asset_inputs(asset, slug)
        daily_with_indicators = btc_p1.add_indicators(daily)
        local_events, local_paths = btc_p1.build_events(
            daily_with_indicators, hourly, funding
        )
        local_events["asset"] = asset
        local_events["asset_event_id"] = local_events["event_id"].astype("int64")
        id_map: dict[int, int] = {}
        global_ids: list[int] = []
        for local_id in local_events["event_id"].astype(int):
            id_map[local_id] = next_event_id
            global_ids.append(next_event_id)
            pooled_paths[next_event_id] = local_paths[local_id]
            next_event_id += 1
        local_events["event_id"] = global_ids
        local_events = add_direction_aligned_features(local_events)
        frames.append(local_events)
        asset_quality[asset] = {
            "daily_rows": int(len(daily)),
            "daily_start": daily["ts"].min(),
            "daily_end": daily["ts"].max(),
            "hourly_rows": int(len(hourly)),
            "funding_rows": int(len(funding)),
            "event_rows": int(len(local_events)),
            "long_events": int(local_events["side"].gt(0).sum()),
            "short_events": int(local_events["side"].lt(0).sum()),
            "positive_rate": float(local_events["label"].mean()),
            "mean_net_return": float(local_events["net_return"].mean()),
        }
    events = (
        pd.concat(frames, ignore_index=True)
        .sort_values(["signal_ts", "asset", "event_id"])
        .reset_index(drop=True)
    )
    if events["event_id"].duplicated().any():
        raise RuntimeError("Pooled event ids are not unique")
    if events["signal_ts"].max() >= DEVELOPMENT_END_EXCLUSIVE:
        raise RuntimeError("Sealed validation event entered pooled events")
    return events, pooled_paths, asset_quality


def event_identity_sha256(events: pd.DataFrame) -> str:
    frame = events.sort_values(["signal_ts", "asset", "event_id"]).reset_index(
        drop=True
    )
    digest = hashlib.sha256()
    for column in ("signal_ts", "entry_ts", "exit_ts"):
        values = (
            pd.to_datetime(frame[column], utc=True)
            .to_numpy(dtype="datetime64[ns]")
            .astype("int64")
        )
        digest.update(np.ascontiguousarray(values, dtype="int64").tobytes())
    for column in ("event_id", "asset_event_id", "side", "label"):
        values = frame[column].to_numpy(dtype="int64")
        digest.update(np.ascontiguousarray(values, dtype="int64").tobytes())
    for column in ("net_return", *RAW_FEATURES, *ALIGNED_FEATURES):
        values = frame[column].to_numpy(dtype="float64")
        digest.update(np.ascontiguousarray(values, dtype="float64").tobytes())
    digest.update("\0".join(frame["asset"].astype(str)).encode("utf-8"))
    digest.update("\0".join(frame["exit_reason"].astype(str)).encode("utf-8"))
    return digest.hexdigest()


def unique_time_folds(
    events: pd.DataFrame,
    *,
    initial_fraction: float,
    blocks: int,
) -> list[tuple[int, pd.DataFrame, pd.DataFrame]]:
    dates = np.array(
        sorted(pd.DatetimeIndex(events["signal_ts"].drop_duplicates()))
    )
    initial = int(math.floor(len(dates) * initial_fraction))
    if initial < 2 or len(dates) - initial < blocks:
        raise RuntimeError("Too few unique signal dates for time folds")
    test_date_blocks = np.array_split(dates[initial:], blocks)
    folds: list[tuple[int, pd.DataFrame, pd.DataFrame]] = []
    for fold_number, test_dates in enumerate(test_date_blocks, start=1):
        first_test = pd.Timestamp(test_dates[0])
        last_test = pd.Timestamp(test_dates[-1])
        train = events.loc[
            events["signal_ts"].lt(first_test) & events["exit_ts"].lt(first_test)
        ].copy()
        test = events.loc[
            events["signal_ts"].ge(first_test)
            & events["signal_ts"].le(last_test)
        ].copy()
        if train.empty or test.empty or train["label"].nunique() < 2:
            raise RuntimeError(f"Invalid time fold {fold_number}")
        overlap_dates = set(train["signal_ts"]).intersection(test["signal_ts"])
        if overlap_dates:
            raise RuntimeError(f"Fold {fold_number} has same-date leakage")
        folds.append((fold_number, train, test))
    return folds


def asset_balanced_weights(events: pd.DataFrame) -> np.ndarray:
    counts = events["asset"].value_counts()
    return events["asset"].map(
        {asset: len(events) / (len(counts) * count) for asset, count in counts.items()}
    ).to_numpy(dtype="float64")


def weighted_outcome_mean(events: pd.DataFrame, mask: pd.Series) -> float:
    selected = events.loc[mask]
    weights = asset_balanced_weights(events)[mask.to_numpy()]
    return float(np.average(selected["net_return"], weights=weights))


def fit_model(events: pd.DataFrame, variant: ModelVariant) -> Any:
    labels = events["label"].astype(int)
    if labels.nunique() < 2:
        return ConstantProbabilityModel(float(labels.mean()))
    weights = asset_balanced_weights(events)
    features = events[list(variant.features)]
    if variant.model_type == "logistic_ev":
        model: Any = Pipeline(
            [
                ("scale", StandardScaler()),
                (
                    "model",
                    LogisticRegression(
                        C=1.0,
                        solver="lbfgs",
                        max_iter=2000,
                        class_weight=None,
                        random_state=SEED,
                    ),
                ),
            ]
        )
        model.fit(features, labels, model__sample_weight=weights)
        return model
    model = lgb.LGBMClassifier(**LGBM_PARAMS)
    model.fit(features, labels, sample_weight=weights)
    return model


def predict_ev(
    model: Any,
    train: pd.DataFrame,
    test: pd.DataFrame,
    variant: ModelVariant,
) -> tuple[np.ndarray, np.ndarray]:
    probability = np.asarray(
        model.predict_proba(test[list(variant.features)])[:, 1],
        dtype="float64",
    )
    positive = train["label"].eq(1)
    nonpositive = ~positive
    mean_win = weighted_outcome_mean(train, positive)
    mean_loss = weighted_outcome_mean(train, nonpositive)
    predicted_ev = probability * mean_win + (1.0 - probability) * mean_loss
    return probability, predicted_ev


def event_metrics(events: pd.DataFrame) -> dict[str, Any]:
    ordered = events.sort_values(["exit_ts", "asset", "event_id"]).reset_index(
        drop=True
    )
    if ordered.empty:
        return {
            "closed_trades": 0,
            "total_return": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "mean_net_return": 0.0,
            "median_net_return": 0.0,
            "event_sequence_max_drawdown": 0.0,
            "long_trades": 0,
            "short_trades": 0,
        }
    returns = ordered["net_return"].to_numpy(dtype="float64")
    factors = np.cumprod(1.0 + returns)
    running_max = np.maximum.accumulate(np.concatenate([[1.0], factors]))[1:]
    drawdown = factors / running_max - 1.0
    positive = float(returns[returns > 0.0].sum())
    negative = float(-returns[returns < 0.0].sum())
    return {
        "closed_trades": int(len(ordered)),
        "total_return": float(factors[-1] - 1.0),
        "profit_factor": float(positive / negative) if negative > 0.0 else math.inf,
        "win_rate": float(np.mean(returns > 0.0)),
        "mean_net_return": float(np.mean(returns)),
        "median_net_return": float(np.median(returns)),
        "event_sequence_max_drawdown": float(np.min(drawdown)),
        "long_trades": int(ordered["side"].gt(0).sum()),
        "short_trades": int(ordered["side"].lt(0).sum()),
    }


def route_events(events: pd.DataFrame, route: str) -> pd.DataFrame:
    if route == "combined":
        return events.copy()
    if route == "long_only":
        return events.loc[events["side"].gt(0)].copy()
    if route == "short_only":
        return events.loc[events["side"].lt(0)].copy()
    raise ValueError(f"Unknown route: {route}")


def edge_eligibility(
    selected_folds: list[pd.DataFrame],
    *,
    expected_assets: tuple[str, ...],
) -> tuple[bool, dict[str, Any]]:
    fold_counts = [int(len(frame)) for frame in selected_folds]
    combined = pd.concat(selected_folds, ignore_index=True)
    asset_counts = {
        asset: int(combined["asset"].eq(asset).sum()) for asset in expected_assets
    }
    eligible = bool(
        all(count >= INNER_MIN_TOTAL_PER_FOLD for count in fold_counts)
        and all(count >= INNER_MIN_PER_ASSET_TOTAL for count in asset_counts.values())
    )
    return eligible, {
        "fold_trade_counts": fold_counts,
        "asset_trade_counts": asset_counts,
    }


def select_edge_inner(
    events: pd.DataFrame,
    variant: ModelVariant,
    route: str,
) -> tuple[float | None, list[dict[str, Any]]]:
    folds = unique_time_folds(events, initial_fraction=0.50, blocks=3)
    expected_assets = tuple(sorted(events["asset"].unique()))
    fold_predictions: list[pd.DataFrame] = []
    for fold_number, train, test in folds:
        model = fit_model(train, variant)
        probability, predicted_ev = predict_ev(model, train, test, variant)
        prediction = test.copy()
        prediction["inner_fold"] = fold_number
        prediction["probability"] = probability
        prediction["predicted_ev"] = predicted_ev
        fold_predictions.append(prediction)
    scores: list[dict[str, Any]] = []
    for edge in EDGE_THRESHOLDS:
        selected_folds = [
            route_events(frame, route)
            .loc[lambda routed: routed["predicted_ev"].gt(edge)]
            .copy()
            for frame in fold_predictions
        ]
        eligible, coverage = edge_eligibility(
            selected_folds,
            expected_assets=expected_assets,
        )
        fold_metrics = [event_metrics(frame) for frame in selected_folds]
        scores.append(
            {
                "edge": float(edge),
                "eligible": eligible,
                **coverage,
                "worst_fold_mean_net_return": (
                    min(float(item["mean_net_return"]) for item in fold_metrics)
                    if eligible
                    else None
                ),
                "fold_metrics": fold_metrics,
            }
        )
    eligible_scores = [item for item in scores if item["eligible"]]
    if not eligible_scores:
        return None, scores
    ranked = sorted(
        eligible_scores,
        key=lambda item: (
            -float(item["worst_fold_mean_net_return"]),
            float(item["edge"]),
            -sum(int(count) for count in item["fold_trade_counts"]),
        ),
    )
    return float(ranked[0]["edge"]), scores


def predictive_ranking(frame: pd.DataFrame) -> dict[str, Any]:
    spearman = float(
        frame["predicted_ev"].corr(frame["net_return"], method="spearman")
    )
    folds: list[dict[str, Any]] = []
    stable_count = 0
    for fold_number, fold in frame.groupby("fold", sort=True):
        top_count = max(1, int(math.ceil(len(fold) * 0.20)))
        top = fold.nlargest(top_count, "predicted_ev")
        all_mean = float(fold["net_return"].mean())
        top_mean = float(top["net_return"].mean())
        stable = bool(top_mean > all_mean)
        stable_count += int(stable)
        folds.append(
            {
                "fold": int(fold_number),
                "rows": int(len(fold)),
                "top_rows": int(len(top)),
                "all_realized_mean": all_mean,
                "top_quintile_realized_mean": top_mean,
                "top_quintile_beats_all": stable,
            }
        )
    return {
        "spearman_predicted_vs_realized": spearman,
        "top_quintile_stable_fold_count": stable_count,
        "folds": folds,
        "ranking_gate_pass": bool(
            math.isfinite(spearman) and spearman > 0.10 and stable_count >= 3
        ),
    }


def stratified_bootstrap(
    selected: pd.DataFrame,
    *,
    samples: int = BOOTSTRAP_SAMPLES,
) -> dict[str, Any]:
    if selected.empty:
        return {
            "samples": samples,
            "positive_probability": 0.0,
            "quantiles": {"2.5%": 0.0, "50%": 0.0, "97.5%": 0.0},
            "gate_pass": False,
        }
    groups = [
        group["net_return"].to_numpy(dtype="float64")
        for _, group in selected.groupby(["fold", "asset"], sort=True)
    ]
    rng = np.random.default_rng(SEED)
    outcomes = np.empty(samples, dtype="float64")
    for sample_index in range(samples):
        sampled = [
            rng.choice(group, size=len(group), replace=True) for group in groups
        ]
        outcomes[sample_index] = (
            float(np.prod(1.0 + np.concatenate(sampled))) - 1.0
        )
    positive_probability = float(np.mean(outcomes > 0.0))
    return {
        "samples": samples,
        "seed": SEED,
        "strata": "outer_fold x asset",
        "positive_probability": positive_probability,
        "quantiles": {
            "2.5%": float(np.quantile(outcomes, 0.025)),
            "50%": float(np.quantile(outcomes, 0.50)),
            "97.5%": float(np.quantile(outcomes, 0.975)),
        },
        "gate_pass": bool(positive_probability >= 0.95),
    }


def summarize_route(predictions: pd.DataFrame, route: str) -> dict[str, Any]:
    routed = route_events(predictions, route)
    selected_column = f"selected_{route}"
    selected = routed.loc[routed[selected_column]].copy()
    fold_reports: list[dict[str, Any]] = []
    positive_folds = 0
    better_folds = 0
    for fold_number in range(1, 5):
        fold = routed.loc[routed["fold"].eq(fold_number)]
        fold_selected = fold.loc[fold[selected_column]]
        model = event_metrics(fold_selected)
        baseline = event_metrics(fold)
        positive = float(model["total_return"]) > 0.0
        better = float(model["mean_net_return"]) > float(
            baseline["mean_net_return"]
        )
        positive_folds += int(positive)
        better_folds += int(better)
        fold_reports.append(
            {
                "fold": fold_number,
                "model": model,
                "all_cross_baseline": baseline,
                "absolute_positive": positive,
                "mean_return_beats_baseline": better,
            }
        )
    model_metrics = event_metrics(selected)
    baseline_metrics = event_metrics(routed)
    per_asset: dict[str, Any] = {}
    for asset in ASSETS:
        asset_frame = routed.loc[routed["asset"].eq(asset)]
        asset_selected = asset_frame.loc[asset_frame[selected_column]]
        per_asset[asset] = {
            "model": event_metrics(asset_selected),
            "all_cross_baseline": event_metrics(asset_frame),
        }
    ranking = predictive_ranking(routed)
    bootstrap = stratified_bootstrap(selected)
    asset_coverage = all(
        int(per_asset[asset]["model"]["closed_trades"]) >= 10 for asset in ASSETS
    )
    economic_gate = bool(
        int(model_metrics["closed_trades"]) >= 100
        and asset_coverage
        and float(model_metrics["total_return"]) > 0.0
        and float(model_metrics["profit_factor"]) >= 1.20
        and positive_folds >= 3
        and better_folds >= 3
        and float(model_metrics["mean_net_return"])
        > float(baseline_metrics["mean_net_return"])
    )
    return {
        "model": model_metrics,
        "all_cross_baseline": baseline_metrics,
        "per_asset": per_asset,
        "positive_fold_count": positive_folds,
        "mean_return_beats_baseline_fold_count": better_folds,
        "asset_coverage_gate_pass": asset_coverage,
        "economic_gate_pass": economic_gate,
        "ranking": ranking,
        "bootstrap": bootstrap,
        "temporal_gate_pass": bool(
            economic_gate
            and ranking["ranking_gate_pass"]
            and bootstrap["gate_pass"]
        ),
        "folds": fold_reports,
    }


def run_temporal_walk_forward(
    events: pd.DataFrame,
    variant: ModelVariant,
) -> tuple[pd.DataFrame, dict[str, Any], list[dict[str, Any]]]:
    prediction_frames: list[pd.DataFrame] = []
    fold_reports: list[dict[str, Any]] = []
    model_states: list[dict[str, Any]] = []
    for fold_number, train, test in unique_time_folds(
        events, initial_fraction=0.40, blocks=4
    ):
        route_edges: dict[str, float | None] = {}
        route_inner_scores: dict[str, list[dict[str, Any]]] = {}
        for route in ("combined", "long_only", "short_only"):
            edge, scores = select_edge_inner(train, variant, route)
            route_edges[route] = edge
            route_inner_scores[route] = scores
        model = fit_model(train, variant)
        probability, predicted_ev = predict_ev(model, train, test, variant)
        prediction = test.copy()
        prediction["variant_id"] = variant.variant_id
        prediction["evaluation"] = "temporal_oos"
        prediction["fold"] = fold_number
        prediction["probability"] = probability
        prediction["predicted_ev"] = predicted_ev
        for route, edge in route_edges.items():
            prediction[f"edge_threshold_{route}"] = (
                np.nan if edge is None else edge
            )
            prediction[f"edge_eligible_{route}"] = edge is not None
            prediction[f"selected_{route}"] = (
                False if edge is None else prediction["predicted_ev"].gt(edge)
            )
        prediction["edge_threshold"] = prediction["edge_threshold_combined"]
        prediction["edge_eligible"] = prediction["edge_eligible_combined"]
        prediction["selected"] = prediction["selected_combined"]
        prediction_frames.append(prediction)
        fold_reports.append(
            {
                "fold": fold_number,
                "train_rows": int(len(train)),
                "train_start": train["signal_ts"].min(),
                "train_end": train["signal_ts"].max(),
                "train_assets": train["asset"].value_counts().to_dict(),
                "test_rows": int(len(test)),
                "test_start": test["signal_ts"].min(),
                "test_end": test["signal_ts"].max(),
                "test_assets": test["asset"].value_counts().to_dict(),
                "selected_edge_by_route": route_edges,
                "edge_selection_failed_by_route": {
                    route: edge is None for route, edge in route_edges.items()
                },
                "inner_edge_scores_by_route": route_inner_scores,
            }
        )
        model_states.append(model_state(model, train, variant, fold_number))
    predictions = pd.concat(prediction_frames, ignore_index=True)
    routes = {
        route: summarize_route(predictions, route)
        for route in ("combined", "long_only", "short_only")
    }
    return predictions, {"folds": fold_reports, "routes": routes}, model_states


def summarize_leave_one_asset_route(
    predictions: pd.DataFrame,
    route: str,
) -> dict[str, Any]:
    routed = route_events(predictions, route)
    selected_column = f"selected_{route}"
    assets: dict[str, Any] = {}
    positive_assets = 0
    covered_assets = 0
    for asset in ASSETS:
        frame = routed.loc[routed["held_asset"].eq(asset)]
        selected = frame.loc[frame[selected_column]]
        model = event_metrics(selected)
        baseline = event_metrics(frame)
        positive = float(model["total_return"]) > 0.0
        covered = int(model["closed_trades"]) >= 10
        positive_assets += int(positive)
        covered_assets += int(covered)
        assets[asset] = {
            "model": model,
            "all_cross_baseline": baseline,
            "absolute_positive": positive,
            "trade_coverage_pass": covered,
            "mean_return_beats_baseline": (
                float(model["mean_net_return"])
                > float(baseline["mean_net_return"])
            ),
        }
    selected_all = routed.loc[routed[selected_column]]
    overall = event_metrics(selected_all)
    baseline = event_metrics(routed)
    ranking = predictive_ranking(routed)
    gate = bool(
        covered_assets == len(ASSETS)
        and positive_assets >= 4
        and float(overall["total_return"]) > 0.0
        and float(overall["profit_factor"]) >= 1.10
        and float(overall["mean_net_return"]) > float(baseline["mean_net_return"])
        and math.isfinite(ranking["spearman_predicted_vs_realized"])
        and float(ranking["spearman_predicted_vs_realized"]) > 0.05
    )
    return {
        "overall": overall,
        "all_cross_baseline": baseline,
        "assets": assets,
        "covered_asset_count": covered_assets,
        "positive_asset_count": positive_assets,
        "ranking": ranking,
        "leave_one_asset_gate_pass": gate,
    }


def run_leave_one_asset_time_oos(
    events: pd.DataFrame,
    variant: ModelVariant,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    base_folds = unique_time_folds(events, initial_fraction=0.40, blocks=4)
    prediction_frames: list[pd.DataFrame] = []
    fold_reports: list[dict[str, Any]] = []
    for held_asset in ASSETS:
        for fold_number, base_train, base_test in base_folds:
            train = base_train.loc[base_train["asset"].ne(held_asset)].copy()
            test = base_test.loc[base_test["asset"].eq(held_asset)].copy()
            if train.empty or test.empty:
                raise RuntimeError(
                    f"{held_asset} LOAO fold {fold_number} lacks train/test events"
                )
            route_edges: dict[str, float | None] = {}
            route_inner_scores: dict[str, list[dict[str, Any]]] = {}
            for route in ("combined", "long_only", "short_only"):
                edge, scores = select_edge_inner(train, variant, route)
                route_edges[route] = edge
                route_inner_scores[route] = scores
            model = fit_model(train, variant)
            probability, predicted_ev = predict_ev(model, train, test, variant)
            prediction = test.copy()
            prediction["variant_id"] = variant.variant_id
            prediction["evaluation"] = "leave_one_asset_time_oos"
            prediction["held_asset"] = held_asset
            prediction["fold"] = fold_number
            prediction["probability"] = probability
            prediction["predicted_ev"] = predicted_ev
            for route, edge in route_edges.items():
                prediction[f"edge_threshold_{route}"] = (
                    np.nan if edge is None else edge
                )
                prediction[f"edge_eligible_{route}"] = edge is not None
                prediction[f"selected_{route}"] = (
                    False
                    if edge is None
                    else prediction["predicted_ev"].gt(edge)
                )
            prediction["edge_threshold"] = prediction[
                "edge_threshold_combined"
            ]
            prediction["edge_eligible"] = prediction[
                "edge_eligible_combined"
            ]
            prediction["selected"] = prediction["selected_combined"]
            prediction_frames.append(prediction)
            fold_reports.append(
                {
                    "held_asset": held_asset,
                    "fold": fold_number,
                    "train_rows": int(len(train)),
                    "train_assets": train["asset"].value_counts().to_dict(),
                    "test_rows": int(len(test)),
                    "test_start": test["signal_ts"].min(),
                    "test_end": test["signal_ts"].max(),
                    "selected_edge_by_route": route_edges,
                    "edge_selection_failed_by_route": {
                        route: edge is None
                        for route, edge in route_edges.items()
                    },
                    "inner_edge_scores_by_route": route_inner_scores,
                }
            )
    predictions = pd.concat(prediction_frames, ignore_index=True)
    routes = {
        route: summarize_leave_one_asset_route(predictions, route)
        for route in ("combined", "long_only", "short_only")
    }
    return predictions, {
        "routes": routes,
        "folds": fold_reports,
    }


def model_state(
    model: Any,
    train: pd.DataFrame,
    variant: ModelVariant,
    fold_number: int,
) -> dict[str, Any]:
    positive = train["label"].eq(1)
    state: dict[str, Any] = {
        "fold": fold_number,
        "variant_id": variant.variant_id,
        "train_rows": int(len(train)),
        "train_asset_counts": train["asset"].value_counts().to_dict(),
        "mean_win": weighted_outcome_mean(train, positive),
        "mean_nonpositive": weighted_outcome_mean(train, ~positive),
    }
    if isinstance(model, Pipeline):
        estimator = model.named_steps["model"]
        scaler = model.named_steps["scale"]
        state["coefficients"] = {
            feature: float(value)
            for feature, value in zip(
                variant.features, estimator.coef_[0], strict=True
            )
        }
        state["intercept"] = float(estimator.intercept_[0])
        state["scaler_mean"] = {
            feature: float(value)
            for feature, value in zip(
                variant.features, scaler.mean_, strict=True
            )
        }
        state["scaler_scale"] = {
            feature: float(value)
            for feature, value in zip(
                variant.features, scaler.scale_, strict=True
            )
        }
    elif isinstance(model, lgb.LGBMClassifier):
        state["feature_importance_gain"] = {
            feature: float(value)
            for feature, value in zip(
                variant.features,
                model.booster_.feature_importance(importance_type="gain"),
                strict=True,
            )
        }
    payload = json.dumps(json_ready(state), sort_keys=True).encode("utf-8")
    state["state_sha256"] = hashlib.sha256(payload).hexdigest()
    return state


def choose_route(report: dict[str, Any]) -> str | None:
    routes = report["routes"]
    if routes["combined"]["temporal_gate_pass"]:
        return "combined"
    passing = [
        route
        for route in ("long_only", "short_only")
        if routes[route]["temporal_gate_pass"]
    ]
    if not passing:
        return None
    return max(
        passing,
        key=lambda route: (
            float(routes[route]["bootstrap"]["positive_probability"]),
            float(routes[route]["model"]["mean_net_return"]),
        ),
    )


def aligned_ablation_gate(
    reports: dict[str, Any],
    route: str | None,
) -> dict[str, Any]:
    aligned = reports["logistic_ev_aligned"]
    raw = reports["logistic_ev_raw_control"]
    route_reports: dict[str, Any] = {}
    for candidate_route in ("combined", "long_only", "short_only"):
        aligned_temporal = aligned["temporal"]["routes"][candidate_route]["model"]
        raw_temporal = raw["temporal"]["routes"][candidate_route]["model"]
        aligned_loao = aligned["leave_one_asset"]["routes"][candidate_route]
        raw_loao = raw["leave_one_asset"]["routes"][candidate_route]
        asset_improved = sum(
            float(aligned_loao["assets"][asset]["model"]["total_return"])
            > float(raw_loao["assets"][asset]["model"]["total_return"])
            for asset in ASSETS
        )
        temporal_improved = float(
            aligned_temporal["mean_net_return"]
        ) > float(raw_temporal["mean_net_return"])
        loao_improved = float(
            aligned_loao["overall"]["mean_net_return"]
        ) > float(raw_loao["overall"]["mean_net_return"])
        route_reports[candidate_route] = {
            "temporal_mean_improved": temporal_improved,
            "temporal_aligned_mean": aligned_temporal["mean_net_return"],
            "temporal_raw_mean": raw_temporal["mean_net_return"],
            "loao_mean_improved": loao_improved,
            "loao_aligned_mean": aligned_loao["overall"]["mean_net_return"],
            "loao_raw_mean": raw_loao["overall"]["mean_net_return"],
            "asset_return_improved_count": int(asset_improved),
            "gate_pass": bool(
                temporal_improved and loao_improved and asset_improved >= 3
            ),
        }
    return {
        "candidate_route": route,
        "routes": route_reports,
        "gate_pass": bool(
            route is not None and route_reports[route]["gate_pass"]
        ),
    }


def recent_slices(predictions: pd.DataFrame, route: str | None) -> dict[str, Any]:
    frame = (
        route_events(predictions, route) if route is not None else predictions.copy()
    )
    selected_column = (
        f"selected_{route}" if route is not None else "selected_combined"
    )
    end = DEVELOPMENT_END_EXCLUSIVE - pd.Timedelta(days=1)
    result: dict[str, Any] = {}
    for label, days in (
        ("1d", 1),
        ("7d", 7),
        ("1m", 30),
        ("3m", 90),
        ("6m", 180),
        ("1y", 365),
    ):
        cutoff = end - pd.Timedelta(days=days)
        window = frame.loc[frame["signal_ts"].ge(cutoff)]
        result[label] = {
            "start": cutoff,
            "end": end,
            "selection_role": "audit_only",
            "model": event_metrics(window.loc[window[selected_column]]),
            "all_cross_baseline": event_metrics(window),
        }
    return result


def compact_variant_summary(report: dict[str, Any]) -> dict[str, Any]:
    temporal: dict[str, Any] = {}
    leave_one_asset: dict[str, Any] = {}
    for route in ("combined", "long_only", "short_only"):
        time_route = report["temporal"]["routes"][route]
        temporal[route] = {
            "model": time_route["model"],
            "all_cross_baseline": time_route["all_cross_baseline"],
            "positive_fold_count": time_route["positive_fold_count"],
            "mean_return_beats_baseline_fold_count": time_route[
                "mean_return_beats_baseline_fold_count"
            ],
            "asset_coverage_gate_pass": time_route[
                "asset_coverage_gate_pass"
            ],
            "economic_gate_pass": time_route["economic_gate_pass"],
            "ranking": {
                "spearman_predicted_vs_realized": time_route["ranking"][
                    "spearman_predicted_vs_realized"
                ],
                "top_quintile_stable_fold_count": time_route["ranking"][
                    "top_quintile_stable_fold_count"
                ],
                "ranking_gate_pass": time_route["ranking"]["ranking_gate_pass"],
            },
            "bootstrap": time_route["bootstrap"],
            "temporal_gate_pass": time_route["temporal_gate_pass"],
        }
        loao_route = report["leave_one_asset"]["routes"][route]
        leave_one_asset[route] = {
            "overall": loao_route["overall"],
            "all_cross_baseline": loao_route["all_cross_baseline"],
            "covered_asset_count": loao_route["covered_asset_count"],
            "positive_asset_count": loao_route["positive_asset_count"],
            "per_asset_model": {
                asset: loao_route["assets"][asset]["model"] for asset in ASSETS
            },
            "ranking": {
                "spearman_predicted_vs_realized": loao_route["ranking"][
                    "spearman_predicted_vs_realized"
                ],
                "top_quintile_stable_fold_count": loao_route["ranking"][
                    "top_quintile_stable_fold_count"
                ],
            },
            "leave_one_asset_gate_pass": loao_route[
                "leave_one_asset_gate_pass"
            ],
        }
    return {
        "variant": report["variant"],
        "temporal": temporal,
        "leave_one_asset": leave_one_asset,
    }


def interpretability_summary(
    temporal_predictions: pd.DataFrame,
    model_states: dict[str, Any],
) -> dict[str, Any]:
    coefficient_rows: list[dict[str, Any]] = []
    logistic_states = model_states["logistic_ev_aligned"]
    for feature in ALIGNED_FEATURES:
        values = np.array(
            [state["coefficients"][feature] for state in logistic_states],
            dtype="float64",
        )
        coefficient_rows.append(
            {
                "feature": feature,
                "mean_coefficient": float(values.mean()),
                "mean_abs_coefficient": float(np.abs(values).mean()),
                "min_coefficient": float(values.min()),
                "max_coefficient": float(values.max()),
                "positive_fold_count": int(np.sum(values > 0.0)),
                "negative_fold_count": int(np.sum(values < 0.0)),
                "sign_consistency": float(
                    max(np.sum(values > 0.0), np.sum(values < 0.0))
                    / len(values)
                ),
            }
        )
    coefficient_rows.sort(
        key=lambda row: (
            -float(row["sign_consistency"]),
            -float(row["mean_abs_coefficient"]),
        )
    )
    lgbm_states = model_states["lgbm_ev_aligned_diagnostic"]
    gain_rows = [
        {
            "feature": feature,
            "mean_gain": float(
                np.mean(
                    [
                        state["feature_importance_gain"][feature]
                        for state in lgbm_states
                    ]
                )
            ),
        }
        for feature in ALIGNED_FEATURES
    ]
    gain_rows.sort(key=lambda row: -float(row["mean_gain"]))
    frame = temporal_predictions.loc[
        temporal_predictions["variant_id"].eq("logistic_ev_aligned")
    ].copy()
    columns = [
        "event_id",
        "asset",
        "signal_ts",
        "side_name",
        "predicted_ev",
        "edge_threshold",
        "selected",
        "net_return",
        "exit_reason",
        "aligned_rsi6",
        "directional_rsi_extreme_5",
        "aligned_close_gap_atr",
        "aligned_ma7_slope_3_atr",
        "rejection_wick_atr",
        "opposition_wick_atr",
        "aligned_close_location",
    ]
    selected = frame.loc[frame["selected"]]
    return {
        "logistic_aligned_coefficient_stability": coefficient_rows,
        "lgbm_aligned_mean_feature_gain": gain_rows,
        "typical_events": {
            "highest_ev_winners": frame.loc[frame["label"].eq(1)]
            .nlargest(5, "predicted_ev")[columns]
            .to_dict("records"),
            "highest_ev_losers": frame.loc[frame["label"].eq(0)]
            .nlargest(5, "predicted_ev")[columns]
            .to_dict("records"),
            "selected_best": selected.nlargest(5, "net_return")[
                columns
            ].to_dict("records"),
            "selected_worst": selected.nsmallest(5, "net_return")[
                columns
            ].to_dict("records"),
        },
    }


def run_self_tests() -> None:
    sample = pd.DataFrame(
        {
            "signal_ts": pd.date_range(
                "2020-01-01", periods=100, freq="D", tz="UTC"
            ).repeat(2),
            "exit_ts": pd.date_range(
                "2020-01-02", periods=100, freq="D", tz="UTC"
            ).repeat(2),
            "asset": ["BTC", "ETH"] * 100,
            "label": [0, 1] * 100,
        }
    )
    folds = unique_time_folds(sample, initial_fraction=0.40, blocks=4)
    assert len(folds) == 4
    assert all(
        set(train["signal_ts"]).isdisjoint(set(test["signal_ts"]))
        for _, train, test in folds
    )
    features = pd.DataFrame(
        {
            **{feature: [1.0, -1.0] for feature in RAW_FEATURES},
            "side": [1, -1],
            "prev_close_ma_gap_atr": [-0.2, 0.2],
            "close_ma_gap_atr": [0.1, -0.1],
            "ma7_slope_1_atr": [0.05, -0.05],
            "ma7_slope_3_atr": [0.1, -0.1],
            "body_atr": [0.2, -0.2],
            "close_location": [0.8, 0.2],
            "upper_wick_atr": [0.1, 0.4],
            "lower_wick_atr": [0.4, 0.1],
            "return_3_atr": [0.3, -0.3],
            "return_5_atr": [0.5, -0.5],
            "rsi6": [70.0, 30.0],
            "rsi6_delta_1": [5.0, -5.0],
            "rsi6_min_5": [30.0, 20.0],
            "rsi6_max_5": [80.0, 70.0],
            "rsi6_low20_last5": [0.0, 1.0],
            "rsi6_high80_last5": [1.0, 0.0],
        }
    )
    aligned = add_direction_aligned_features(features)
    assert np.allclose(aligned["aligned_body_atr"], [0.2, 0.2])
    assert np.allclose(aligned["aligned_close_location"], [0.8, 0.8])
    assert np.allclose(aligned["rejection_wick_atr"], [0.4, 0.4])
    assert np.allclose(aligned["aligned_rsi6"], [70.0, 70.0])


def main() -> None:
    args = parse_args()
    if args.self_test:
        run_self_tests()
        print(json.dumps({"self_test": "PASS"}, indent=2))
        return
    generated_at = datetime.now(UTC)
    events, paths, asset_quality = build_pooled_events()
    del paths
    event_hash = event_identity_sha256(events)
    p0_capacity = {
        "generated_at_utc": generated_at,
        "development_end_exclusive": DEVELOPMENT_END_EXCLUSIVE,
        "sealed_rows_consumed": 0,
        "assets": asset_quality,
        "total_events": int(len(events)),
        "long_events": int(events["side"].gt(0).sum()),
        "short_events": int(events["side"].lt(0).sum()),
        "positive_rate": float(events["label"].mean()),
        "mean_net_return": float(events["net_return"].mean()),
        "event_identity_sha256": event_hash,
        "aligned_feature_names": list(ALIGNED_FEATURES),
        "raw_control_feature_names": list(RAW_FEATURES),
    }
    P0_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    write_json(P0_ARTIFACT_DIR / "p0_event_capacity.json", p0_capacity)
    atomic_write_path(
        P0_ARTIFACT_DIR / "p0_development_events.parquet",
        lambda temp_path: events.to_parquet(temp_path, index=False),
    )
    if args.p0_only:
        print(json.dumps(json_ready(p0_capacity), ensure_ascii=False, indent=2))
        return
    if len(events) != EXPECTED_EVENT_ROWS or event_hash != EXPECTED_EVENT_SHA256:
        raise RuntimeError(
            "P1 event identity differs from frozen P0 evidence: "
            f"rows={len(events)}, sha256={event_hash}"
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    all_predictions: list[pd.DataFrame] = []
    reports: dict[str, Any] = {}
    model_states: dict[str, Any] = {}
    for variant in VARIANTS:
        temporal_predictions, temporal_report, states = (
            run_temporal_walk_forward(events, variant)
        )
        loao_predictions, loao_report = run_leave_one_asset_time_oos(
            events, variant
        )
        all_predictions.extend([temporal_predictions, loao_predictions])
        reports[variant.variant_id] = {
            "variant": asdict(variant),
            "temporal": temporal_report,
            "leave_one_asset": loao_report,
        }
        model_states[variant.variant_id] = states
    predictions = pd.concat(all_predictions, ignore_index=True)
    atomic_write_path(
        args.output_dir / "p1_outer_predictions.parquet",
        lambda temp_path: predictions.to_parquet(temp_path, index=False),
    )
    atomic_write_path(
        args.output_dir / "p1_events.parquet",
        lambda temp_path: events.to_parquet(temp_path, index=False),
    )
    primary_report = reports["logistic_ev_aligned"]
    primary_route = choose_route(primary_report["temporal"])
    loao_pass = bool(
        primary_route is not None
        and primary_report["leave_one_asset"]["routes"][primary_route][
            "leave_one_asset_gate_pass"
        ]
    )
    ablation = aligned_ablation_gate(reports, primary_route)
    temporal_pass = bool(
        primary_route is not None
        and primary_report["temporal"]["routes"][primary_route][
            "temporal_gate_pass"
        ]
    )
    development_gate = bool(temporal_pass and loao_pass and ablation["gate_pass"])
    primary_temporal_predictions = predictions.loc[
        predictions["variant_id"].eq("logistic_ev_aligned")
        & predictions["evaluation"].eq("temporal_oos")
    ].copy()
    report = {
        "generated_at_utc": generated_at,
        "family": "BIN-1D-MA7-RSI6-DAPML",
        "stage": "P1 pooled development-only",
        "contract": (
            "specs/binance-1d-ma7-rsi6-dapml-p1-pooled-development-"
            "contract-2026-08-10.md"
        ),
        "development_end_exclusive": DEVELOPMENT_END_EXCLUSIVE,
        "sealed_period_consumed": False,
        "event_rows": int(len(events)),
        "event_identity_sha256": event_hash,
        "variants": reports,
        "model_states": model_states,
        "primary_variant": "logistic_ev_aligned",
        "primary_route": primary_route,
        "primary_temporal_gate_pass": temporal_pass,
        "primary_leave_one_asset_gate_pass": loao_pass,
        "direction_aligned_ablation": ablation,
        "development_gate_pass": development_gate,
        "validation_eligible": development_gate,
        "validation_authorized": False,
        "recent_slices": recent_slices(
            primary_temporal_predictions, primary_route
        ),
        "metric_scope_warning": (
            "P1 metrics are equal-event diagnostics. Simultaneous portfolio "
            "allocation, total leverage, and portfolio-path MDD are not modeled "
            "and cannot support promotion."
        ),
    }
    write_json(args.output_dir / "p1_report.json", report)
    write_json(args.output_dir / "p1_model_states.json", model_states)
    write_json(
        args.output_dir / "p1_interpretability.json",
        interpretability_summary(
            primary_temporal_predictions,
            model_states,
        ),
    )
    write_json(
        args.output_dir / "p1_summary.json",
        {
            "generated_at_utc": generated_at,
            "event_rows": int(len(events)),
            "event_identity_sha256": event_hash,
            "variants": {
                variant_id: compact_variant_summary(variant_report)
                for variant_id, variant_report in reports.items()
            },
            "primary_variant": "logistic_ev_aligned",
            "primary_route": primary_route,
            "direction_aligned_ablation": ablation,
            "development_gate_pass": development_gate,
            "validation_eligible": development_gate,
            "validation_authorized": False,
        },
    )
    print(json.dumps(json_ready(report), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
