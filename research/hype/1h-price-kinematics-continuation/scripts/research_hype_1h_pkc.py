from __future__ import annotations

import importlib.util
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from strategy_lab.data import DataLakeLayout, DuckDBWarehouse
from strategy_lab.data.settings import load_settings


ROOT = Path("research/hype/1h-price-kinematics-continuation")
ARTIFACT_DIR = ROOT / "artifacts"
DATA_LOADER_SCRIPT = Path(
    "research/hype/15m-multidimensional-trend-pyramiding/scripts/"
    "research_hype_15m_mdtp.py"
)
SYMBOL = "HYPE/USDT:USDT"
RUN_DATE = "2026-08-02"
TRAIN_START = pd.Timestamp("2025-06-03 00:00:00+00:00")
TRAIN_END = pd.Timestamp("2026-02-01 00:00:00+00:00")
VALIDATION_START = pd.Timestamp("2026-02-15 00:00:00+00:00")
VALIDATION_END = pd.Timestamp("2026-08-02 00:00:00+00:00")
PROSPECTIVE_START = pd.Timestamp("2026-08-02 00:00:00+00:00")
PROSPECTIVE_END = pd.Timestamp("2026-11-02 00:00:00+00:00")
PAST_WINDOWS = (6, 24, 72)
FUTURE_HORIZONS = (72, 168, 336)
BAR_MINUTES = 60
DIRECTION_WINDOW = 24
ACCELERATION_PAIRS = ((6, 24), (24, 72))
SENSITIVITY_HORIZON = 168
ANCHOR_PHASES = (0, 1, 2, 3)
PRIMARY_PHASE = 0
ANCHOR_PHASE_MODE = "intraday_mod"
EPSILON = 1e-12
BOOTSTRAP_SAMPLES = 2_000
BLOCK_HOURS = 14 * 24
RIDGE_ALPHA = 10.0
LOGIT_C = 0.1
OOF_MIN_ROWS = 250
OOF_MIN_TRAIN_ROWS = 100

BASELINE_FEATURES = tuple(f"dir_velocity_{window}" for window in PAST_WINDOWS)
FULL_FEATURES = (
    *BASELINE_FEATURES,
    *(f"path_speed_{window}" for window in PAST_WINDOWS),
    *(f"coherence_{window}" for window in PAST_WINDOWS),
    *(f"burst_{window}" for window in PAST_WINDOWS),
    *(f"noise_{window}" for window in PAST_WINDOWS),
    *(f"roughness_{window}" for window in PAST_WINDOWS),
    *(f"dir_acceleration_{short}_{long}" for short, long in ACCELERATION_PAIRS),
    "scale_alignment",
)
EXPECTED_POSITIVE = (
    *(f"coherence_{window}" for window in PAST_WINDOWS),
    *(f"dir_acceleration_{short}_{long}" for short, long in ACCELERATION_PAIRS),
    "scale_alignment",
)
EXPECTED_NEGATIVE = (
    *(f"burst_{window}" for window in PAST_WINDOWS),
    *(f"roughness_{window}" for window in PAST_WINDOWS),
)


@dataclass(frozen=True, slots=True)
class ModelEvaluation:
    ridge_ic: float
    ridge_top_bottom_z: float
    logit_auc: float
    logit_brier: float
    constant_brier: float
    samples: int
    positive_rate: float
    ridge_predictions: np.ndarray
    logit_predictions: np.ndarray


def load_data_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "hype_pkc_data_loader", DATA_LOADER_SCRIPT
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load data helper: {DATA_LOADER_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_price_data() -> tuple[pd.DataFrame, dict[str, Any]]:
    module = load_data_module()
    warehouse = DuckDBWarehouse(DataLakeLayout.from_settings(load_settings(None)))
    frame, _, quality = module.load_symbol_data(
        warehouse,
        SYMBOL,
        require_raw_parity=True,
    )
    if frame.index.max() >= PROSPECTIVE_START:
        raise RuntimeError(
            "prospective OOS is present in the input; refuse to compute any label"
        )
    return frame[["open", "high", "low", "close"]].copy(), quality


def build_complete_hourly(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    grouped = frame.resample("1h", label="left", closed="left")
    hourly = grouped.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        source_bars=("close", "count"),
    )
    incomplete = hourly.loc[hourly["source_bars"].ne(4)].copy()
    hourly = hourly.loc[hourly["source_bars"].eq(4)].copy()
    hourly.index = hourly.index + pd.Timedelta(hours=1)
    expected = pd.date_range(
        hourly.index.min(), hourly.index.max(), freq="1h", tz="UTC"
    )
    missing = expected.difference(hourly.index)
    invalid = hourly["high"].lt(hourly[["open", "close", "low"]].max(axis=1)) | hourly[
        "low"
    ].gt(hourly[["open", "close", "high"]].min(axis=1))
    quality = {
        "rows": int(len(hourly)),
        "start": hourly.index.min().isoformat(),
        "end": hourly.index.max().isoformat(),
        "incomplete_source_hours": int(len(incomplete)),
        "missing_complete_hours": int(len(missing)),
        "first_missing_complete_hours": [value.isoformat() for value in missing[:10]],
        "invalid_ohlc_rows": int(invalid.sum()),
        "accepted": bool(len(missing) == 0 and int(invalid.sum()) == 0),
        "availability_semantics": (
            "index is the first timestamp when the completed prior one-hour bar is known"
        ),
    }
    if not quality["accepted"]:
        raise RuntimeError(f"hourly data quality blocker: {quality}")
    return hourly, quality


def _roughness(values: np.ndarray) -> float:
    if not np.isfinite(values).all() or len(values) < 2:
        return math.nan
    path_length = float(np.abs(np.diff(values)).sum())
    if path_length <= EPSILON:
        return 0.0
    line = np.linspace(values[0], values[-1], len(values))
    residual_rms = float(np.sqrt(np.mean(np.square(values - line))))
    return residual_rms / (path_length + EPSILON)


def build_kinematic_state(hourly: pd.DataFrame) -> pd.DataFrame:
    state = pd.DataFrame(index=hourly.index)
    state["log_price"] = np.log(hourly["close"].astype(float))
    state["step"] = state["log_price"].diff()
    absolute_step = state["step"].abs()
    squared_step = state["step"].pow(2)
    for window in PAST_WINDOWS:
        displacement = state["log_price"] - state["log_price"].shift(window)
        path_length = absolute_step.rolling(window, min_periods=window).sum()
        state[f"displacement_{window}"] = displacement
        state[f"velocity_{window}"] = displacement / window
        state[f"path_length_{window}"] = path_length
        state[f"path_speed_{window}"] = path_length / window
        state[f"signed_coherence_{window}"] = displacement / (path_length + EPSILON)
        state[f"coherence_{window}"] = state[f"signed_coherence_{window}"].abs()
        state[f"burst_{window}"] = absolute_step.rolling(
            window, min_periods=window
        ).max() / (path_length + EPSILON)
        state[f"noise_{window}"] = np.sqrt(
            squared_step.rolling(window, min_periods=window).mean()
        )
        state[f"roughness_{window}"] = (
            state["log_price"]
            .rolling(window + 1, min_periods=window + 1)
            .apply(_roughness, raw=True)
        )

    state["direction"] = np.sign(state[f"displacement_{DIRECTION_WINDOW}"])
    for window in PAST_WINDOWS:
        state[f"dir_velocity_{window}"] = (
            state["direction"] * state[f"velocity_{window}"]
        )
    for short, long in ACCELERATION_PAIRS:
        state[f"dir_acceleration_{short}_{long}"] = (
            state["direction"]
            * (state[f"velocity_{short}"] - state[f"velocity_{long}"])
            / float(long - short)
        )
    aligned = [
        np.sign(state[f"velocity_{window}"]).eq(state["direction"])
        for window in PAST_WINDOWS
    ]
    state["scale_alignment"] = sum(item.astype(int) for item in aligned)
    if ANCHOR_PHASE_MODE == "intraday_mod":
        bar_number = (state.index.hour * 60 + state.index.minute) // BAR_MINUTES
        state["anchor_phase"] = bar_number % len(ANCHOR_PHASES)
    elif ANCHOR_PHASE_MODE == "daily_stride":
        origin = state.index.min().normalize()
        day_number = (state.index.normalize() - origin).days
        state["anchor_phase"] = day_number % len(ANCHOR_PHASES)
    else:
        raise ValueError(f"unknown ANCHOR_PHASE_MODE={ANCHOR_PHASE_MODE}")
    return state


def add_future_labels(state: pd.DataFrame) -> pd.DataFrame:
    labelled = state.copy()
    log_price = labelled["log_price"].to_numpy(float)
    direction = labelled["direction"].to_numpy(float)
    noise_long = labelled[f"noise_{PAST_WINDOWS[-1]}"].to_numpy(float)
    count = len(labelled)
    for horizon in FUTURE_HORIZONS:
        names = (
            f"future_return_{horizon}",
            f"future_z_{horizon}",
            f"continuation_{horizon}",
            f"future_path_length_{horizon}",
            f"future_coherence_{horizon}",
            f"mfe_{horizon}",
            f"mae_{horizon}",
            f"mfe_share_{horizon}",
            f"first_passage_{horizon}",
        )
        arrays = {name: np.full(count, np.nan, dtype=float) for name in names}
        for index in range(0, count - horizon):
            side = direction[index]
            scale = noise_long[index] * math.sqrt(horizon)
            if side == 0.0 or not np.isfinite(scale) or scale <= EPSILON:
                continue
            future = side * (
                log_price[index + 1 : index + horizon + 1] - log_price[index]
            )
            if not np.isfinite(future).all():
                continue
            path = float(np.abs(np.diff(log_price[index : index + horizon + 1])).sum())
            final = float(future[-1])
            mfe = max(0.0, float(np.max(future)))
            mae = max(0.0, float(np.max(-future)))
            plus = np.flatnonzero(future >= scale)
            minus = np.flatnonzero(future <= -scale)
            if plus.size and (not minus.size or plus[0] < minus[0]):
                passage = 1.0
            elif minus.size and (not plus.size or minus[0] < plus[0]):
                passage = -1.0
            else:
                passage = 0.0
            values = (
                final,
                final / (scale + EPSILON),
                float(final > 0.0),
                path,
                final / (path + EPSILON),
                mfe,
                mae,
                mfe / (mfe + mae + EPSILON),
                passage,
            )
            for name, value in zip(names, values, strict=True):
                arrays[name][index] = value
        for name, values in arrays.items():
            labelled[name] = values
    return labelled


def phase_subset(
    labelled: pd.DataFrame,
    *,
    phase: int | None,
    side: int,
    horizon: int,
    period: str,
) -> pd.DataFrame:
    if period == "train":
        start = TRAIN_START
        end = TRAIN_END - pd.Timedelta(minutes=horizon * BAR_MINUTES)
    elif period == "validation":
        start = VALIDATION_START
        end = VALIDATION_END - pd.Timedelta(minutes=horizon * BAR_MINUTES)
    else:
        raise ValueError(period)
    target = f"future_z_{horizon}"
    binary = f"continuation_{horizon}"
    phase_mask: pd.Series | bool = (
        True if phase is None else labelled["anchor_phase"].eq(phase)
    )
    mask = (
        phase_mask
        & labelled["direction"].eq(side)
        & (labelled.index >= start)
        & (labelled.index < end)
        & labelled[target].notna()
        & labelled[binary].notna()
    )
    label_columns = [
        f"future_return_{horizon}",
        target,
        binary,
        f"future_path_length_{horizon}",
        f"future_coherence_{horizon}",
        f"mfe_{horizon}",
        f"mae_{horizon}",
        f"mfe_share_{horizon}",
        f"first_passage_{horizon}",
    ]
    columns = list(dict.fromkeys([*FULL_FEATURES, *label_columns]))
    return labelled.loc[mask, columns].dropna().copy()


def frozen_edges(values: pd.Series) -> np.ndarray:
    finite = pd.to_numeric(values, errors="coerce").dropna().to_numpy(float)
    if len(finite) < 10:
        return np.array([-math.inf, math.inf])
    quantiles = np.quantile(finite, [0.2, 0.4, 0.6, 0.8])
    unique = np.unique(quantiles)
    return np.concatenate(([-math.inf], unique, [math.inf]))


def apply_edges(values: pd.Series, edges: np.ndarray) -> pd.Series:
    labels = list(range(1, len(edges)))
    return pd.cut(values, bins=edges, labels=labels, include_lowest=True).astype(
        "float"
    )


def _block_effect_ci(
    frame: pd.DataFrame,
    *,
    bin_column: str,
    target: str,
    samples: int,
    seed: int,
) -> tuple[float, float, float, int]:
    selected = frame.loc[frame[bin_column].isin((1.0, 5.0)), [bin_column, target]]
    if selected.empty:
        return math.nan, math.nan, math.nan, 0
    origin = selected.index.min().floor("D")
    block = ((selected.index - origin).total_seconds() // (BLOCK_HOURS * 3600)).astype(
        int
    )
    selected = selected.assign(block=block)
    aggregates = (
        selected.groupby(["block", bin_column])[target]
        .agg(["sum", "count"])
        .reset_index()
    )
    blocks = np.sort(aggregates["block"].unique())
    if len(blocks) == 0:
        return math.nan, math.nan, math.nan, 0
    summary: dict[tuple[int, int], tuple[float, int]] = {}
    for row in aggregates.itertuples(index=False):
        summary[(int(row.block), int(getattr(row, bin_column)))] = (
            float(row.sum),
            int(row.count),
        )
    rng = np.random.default_rng(seed)
    effects: list[float] = []
    for _ in range(samples):
        sampled = rng.choice(blocks, size=len(blocks), replace=True)
        totals: dict[int, list[float]] = {1: [0.0, 0.0], 5: [0.0, 0.0]}
        for block_id in sampled:
            for bin_id in (1, 5):
                value_sum, value_count = summary.get((int(block_id), bin_id), (0.0, 0))
                totals[bin_id][0] += value_sum
                totals[bin_id][1] += value_count
        if totals[1][1] and totals[5][1]:
            effects.append(totals[5][0] / totals[5][1] - totals[1][0] / totals[1][1])
    observed = (
        selected.loc[selected[bin_column].eq(5.0), target].mean()
        - selected.loc[selected[bin_column].eq(1.0), target].mean()
    )
    if not effects:
        return float(observed), math.nan, math.nan, int(len(blocks))
    return (
        float(observed),
        float(np.quantile(effects, 0.025)),
        float(np.quantile(effects, 0.975)),
        int(len(blocks)),
    )


def run_univariate(labelled: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    bin_rows: list[dict[str, Any]] = []
    effect_rows: list[dict[str, Any]] = []
    for side, direction_name in ((1, "long"), (-1, "short")):
        for horizon in FUTURE_HORIZONS:
            train = phase_subset(
                labelled,
                phase=PRIMARY_PHASE,
                side=side,
                horizon=horizon,
                period="train",
            )
            validation = phase_subset(
                labelled,
                phase=PRIMARY_PHASE,
                side=side,
                horizon=horizon,
                period="validation",
            )
            target = f"future_z_{horizon}"
            binary = f"continuation_{horizon}"
            for feature_index, feature in enumerate(FULL_FEATURES):
                edges = frozen_edges(train[feature])
                train_bin = apply_edges(train[feature], edges)
                validation_bin = apply_edges(validation[feature], edges)
                for period, frame, bins in (
                    ("train", train, train_bin),
                    ("validation", validation, validation_bin),
                ):
                    work = frame.assign(feature_bin=bins)
                    for bin_id, group in work.groupby("feature_bin", observed=True):
                        bin_rows.append(
                            {
                                "direction": direction_name,
                                "horizon_hours": horizon,
                                "period": period,
                                "feature": feature,
                                "bin": int(bin_id),
                                "samples": int(len(group)),
                                "mean_z": float(group[target].mean()),
                                "median_z": float(group[target].median()),
                                "continuation_rate": float(group[binary].mean()),
                            }
                        )
                validation_work = validation.assign(feature_bin=validation_bin)
                observed, low, high, blocks = _block_effect_ci(
                    validation_work,
                    bin_column="feature_bin",
                    target=target,
                    samples=BOOTSTRAP_SAMPLES,
                    seed=20260802 + side * 1000 + horizon + feature_index,
                )
                expected = (
                    "positive"
                    if feature in EXPECTED_POSITIVE
                    else "negative"
                    if feature in EXPECTED_NEGATIVE
                    else "unspecified"
                )
                effect_rows.append(
                    {
                        "direction": direction_name,
                        "horizon_hours": horizon,
                        "feature": feature,
                        "expected_direction": expected,
                        "q5_minus_q1_mean_z": observed,
                        "bootstrap_ci_low": low,
                        "bootstrap_ci_high": high,
                        "independent_blocks": blocks,
                        "expected_sign_ci_excludes_zero": bool(
                            (expected == "positive" and low > 0.0)
                            or (expected == "negative" and high < 0.0)
                        ),
                    }
                )
    return pd.DataFrame(bin_rows), pd.DataFrame(effect_rows)


def _safe_spearman(predictions: np.ndarray, actual: np.ndarray) -> float:
    if len(actual) < 3 or np.std(predictions) <= EPSILON:
        return math.nan
    result = spearmanr(predictions, actual, nan_policy="omit")
    return float(result.statistic)


def _prediction_top_bottom(predictions: np.ndarray, actual: np.ndarray) -> float:
    if len(actual) < 10:
        return math.nan
    low = np.quantile(predictions, 0.2)
    high = np.quantile(predictions, 0.8)
    bottom = actual[predictions <= low]
    top = actual[predictions >= high]
    if not len(bottom) or not len(top):
        return math.nan
    return float(np.mean(top) - np.mean(bottom))


def fit_and_evaluate(
    train: pd.DataFrame,
    test: pd.DataFrame,
    *,
    features: Iterable[str],
    horizon: int,
) -> ModelEvaluation:
    feature_list = list(features)
    target = f"future_z_{horizon}"
    binary = f"continuation_{horizon}"
    ridge = make_pipeline(StandardScaler(), Ridge(alpha=RIDGE_ALPHA))
    logit = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=LOGIT_C, max_iter=2_000, solver="lbfgs"),
    )
    ridge.fit(train[feature_list], train[target])
    logit.fit(train[feature_list], train[binary].astype(int))
    ridge_predictions = ridge.predict(test[feature_list])
    logit_predictions = logit.predict_proba(test[feature_list])[:, 1]
    actual = test[target].to_numpy(float)
    actual_binary = test[binary].to_numpy(int)
    train_probability = float(train[binary].mean())
    auc = (
        float(roc_auc_score(actual_binary, logit_predictions))
        if len(np.unique(actual_binary)) > 1
        else math.nan
    )
    return ModelEvaluation(
        ridge_ic=_safe_spearman(ridge_predictions, actual),
        ridge_top_bottom_z=_prediction_top_bottom(ridge_predictions, actual),
        logit_auc=auc,
        logit_brier=float(brier_score_loss(actual_binary, logit_predictions)),
        constant_brier=float(
            brier_score_loss(actual_binary, np.full(len(test), train_probability))
        ),
        samples=int(len(test)),
        positive_rate=float(np.mean(actual_binary)),
        ridge_predictions=np.asarray(ridge_predictions, dtype=float),
        logit_predictions=np.asarray(logit_predictions, dtype=float),
    )


def expanding_oof(
    frame: pd.DataFrame,
    *,
    features: Iterable[str],
    horizon: int,
) -> ModelEvaluation | None:
    if len(frame) < OOF_MIN_ROWS:
        return None
    ordered = frame.sort_index()
    boundaries = np.linspace(0.4, 1.0, 5)
    ridge_predictions: list[np.ndarray] = []
    logit_predictions: list[np.ndarray] = []
    actual_values: list[np.ndarray] = []
    binary_values: list[np.ndarray] = []
    constant_values: list[np.ndarray] = []
    feature_list = list(features)
    target = f"future_z_{horizon}"
    binary = f"continuation_{horizon}"
    for left, right in zip(boundaries[:-1], boundaries[1:], strict=True):
        start_index = int(len(ordered) * left)
        end_index = int(len(ordered) * right)
        test = ordered.iloc[start_index:end_index]
        if test.empty:
            continue
        cutoff = test.index.min() - pd.Timedelta(minutes=horizon * BAR_MINUTES)
        train = ordered.loc[ordered.index < cutoff]
        if len(train) < OOF_MIN_TRAIN_ROWS or train[binary].nunique() < 2:
            continue
        evaluation = fit_and_evaluate(
            train,
            test,
            features=feature_list,
            horizon=horizon,
        )
        ridge_predictions.append(evaluation.ridge_predictions)
        logit_predictions.append(evaluation.logit_predictions)
        actual_values.append(test[target].to_numpy(float))
        binary_values.append(test[binary].to_numpy(int))
        constant_values.append(np.full(len(test), float(train[binary].mean())))
    if not actual_values:
        return None
    ridge_pred = np.concatenate(ridge_predictions)
    logit_pred = np.concatenate(logit_predictions)
    actual = np.concatenate(actual_values)
    actual_binary = np.concatenate(binary_values)
    constant = np.concatenate(constant_values)
    auc = (
        float(roc_auc_score(actual_binary, logit_pred))
        if len(np.unique(actual_binary)) > 1
        else math.nan
    )
    return ModelEvaluation(
        ridge_ic=_safe_spearman(ridge_pred, actual),
        ridge_top_bottom_z=_prediction_top_bottom(ridge_pred, actual),
        logit_auc=auc,
        logit_brier=float(brier_score_loss(actual_binary, logit_pred)),
        constant_brier=float(brier_score_loss(actual_binary, constant)),
        samples=int(len(actual)),
        positive_rate=float(np.mean(actual_binary)),
        ridge_predictions=ridge_pred,
        logit_predictions=logit_pred,
    )


def _evaluation_row(
    evaluation: ModelEvaluation,
    *,
    direction: str,
    horizon: int,
    period: str,
    model: str,
    trimmed_ic: float | None = None,
) -> dict[str, Any]:
    return {
        "direction": direction,
        "horizon_hours": horizon,
        "period": period,
        "feature_set": model,
        "samples": evaluation.samples,
        "positive_rate": evaluation.positive_rate,
        "ridge_ic": evaluation.ridge_ic,
        "ridge_top_bottom_z": evaluation.ridge_top_bottom_z,
        "logit_auc": evaluation.logit_auc,
        "logit_brier": evaluation.logit_brier,
        "constant_brier": evaluation.constant_brier,
        "brier_improvement": evaluation.constant_brier - evaluation.logit_brier,
        "trimmed_1pct_ridge_ic": trimmed_ic,
    }


def run_models(
    labelled: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[tuple[str, int], dict[str, np.ndarray]]]:
    rows: list[dict[str, Any]] = []
    predictions: dict[tuple[str, int], dict[str, np.ndarray]] = {}
    for side, direction in ((1, "long"), (-1, "short")):
        for horizon in FUTURE_HORIZONS:
            train = phase_subset(
                labelled,
                phase=PRIMARY_PHASE,
                side=side,
                horizon=horizon,
                period="train",
            )
            validation = phase_subset(
                labelled,
                phase=PRIMARY_PHASE,
                side=side,
                horizon=horizon,
                period="validation",
            )
            target = f"future_z_{horizon}"
            for model_name, features in (
                ("baseline", BASELINE_FEATURES),
                ("full", FULL_FEATURES),
            ):
                oof = expanding_oof(train, features=features, horizon=horizon)
                if oof is not None:
                    rows.append(
                        _evaluation_row(
                            oof,
                            direction=direction,
                            horizon=horizon,
                            period="train_expanding_oof",
                            model=model_name,
                        )
                    )
                evaluation = fit_and_evaluate(
                    train,
                    validation,
                    features=features,
                    horizon=horizon,
                )
                actual = validation[target].to_numpy(float)
                threshold = np.quantile(np.abs(actual), 0.99)
                keep = np.abs(actual) <= threshold
                trimmed_ic = _safe_spearman(
                    evaluation.ridge_predictions[keep], actual[keep]
                )
                rows.append(
                    _evaluation_row(
                        evaluation,
                        direction=direction,
                        horizon=horizon,
                        period="validation",
                        model=model_name,
                        trimmed_ic=trimmed_ic,
                    )
                )
                predictions.setdefault((direction, horizon), {})[
                    f"{model_name}_ridge"
                ] = evaluation.ridge_predictions
                predictions[(direction, horizon)]["actual"] = actual
    return pd.DataFrame(rows), predictions


def run_phase_space(labelled: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for side, direction in ((1, "long"), (-1, "short")):
        for horizon in FUTURE_HORIZONS:
            train = phase_subset(
                labelled,
                phase=PRIMARY_PHASE,
                side=side,
                horizon=horizon,
                period="train",
            )
            validation = phase_subset(
                labelled,
                phase=PRIMARY_PHASE,
                side=side,
                horizon=horizon,
                period="validation",
            )
            speed_feature = f"dir_velocity_{DIRECTION_WINDOW}"
            first_short, first_long = ACCELERATION_PAIRS[0]
            acceleration_feature = f"dir_acceleration_{first_short}_{first_long}"
            speed_edges = frozen_edges(train[speed_feature])
            acceleration_edges = frozen_edges(train[acceleration_feature])
            target = f"future_z_{horizon}"
            binary = f"continuation_{horizon}"
            for period, frame in (("train", train), ("validation", validation)):
                work = frame.assign(
                    speed_bin=apply_edges(frame[speed_feature], speed_edges),
                    acceleration_bin=apply_edges(
                        frame[acceleration_feature], acceleration_edges
                    ),
                )
                for (speed_bin, acceleration_bin), group in work.groupby(
                    ["speed_bin", "acceleration_bin"], observed=True
                ):
                    rows.append(
                        {
                            "direction": direction,
                            "horizon_hours": horizon,
                            "period": period,
                            "speed_bin": int(speed_bin),
                            "acceleration_bin": int(acceleration_bin),
                            "samples": int(len(group)),
                            "mean_z": float(group[target].mean()),
                            "continuation_rate": float(group[binary].mean()),
                        }
                    )
    return pd.DataFrame(rows)


def run_phase_sensitivity(labelled: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    horizon = SENSITIVITY_HORIZON
    target = f"future_z_{horizon}"
    for side, direction in ((1, "long"), (-1, "short")):
        for phase in ANCHOR_PHASES:
            train = phase_subset(
                labelled,
                phase=phase,
                side=side,
                horizon=horizon,
                period="train",
            )
            validation = phase_subset(
                labelled,
                phase=phase,
                side=side,
                horizon=horizon,
                period="validation",
            )
            evaluation = fit_and_evaluate(
                train,
                validation,
                features=FULL_FEATURES,
                horizon=horizon,
            )
            rows.append(
                {
                    "direction": direction,
                    "phase": phase,
                    "samples": int(len(validation)),
                    "ridge_ic": evaluation.ridge_ic,
                    "mean_actual_z": float(validation[target].mean()),
                }
            )
    return pd.DataFrame(rows)


def run_label_summary(labelled: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for side, direction in ((1, "long"), (-1, "short")):
        for horizon in FUTURE_HORIZONS:
            for period in ("train", "validation"):
                frame = phase_subset(
                    labelled,
                    phase=PRIMARY_PHASE,
                    side=side,
                    horizon=horizon,
                    period=period,
                )
                target = f"future_z_{horizon}"
                binary = f"continuation_{horizon}"
                passage = frame[f"first_passage_{horizon}"]
                rows.append(
                    {
                        "direction": direction,
                        "horizon_hours": horizon,
                        "period": period,
                        "samples": int(len(frame)),
                        "mean_z": float(frame[target].mean()),
                        "median_z": float(frame[target].median()),
                        "continuation_rate": float(frame[binary].mean()),
                        "mean_mfe_share": float(frame[f"mfe_share_{horizon}"].mean()),
                        "positive_first_passage_rate": float(passage.eq(1.0).mean()),
                        "negative_first_passage_rate": float(passage.eq(-1.0).mean()),
                        "no_passage_rate": float(passage.eq(0.0).mean()),
                    }
                )
    return pd.DataFrame(rows)


def run_model_coefficients(labelled: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for side, direction in ((1, "long"), (-1, "short")):
        for horizon in FUTURE_HORIZONS:
            train = phase_subset(
                labelled,
                phase=PRIMARY_PHASE,
                side=side,
                horizon=horizon,
                period="train",
            )
            target = f"future_z_{horizon}"
            binary = f"continuation_{horizon}"
            for feature_set, features in (
                ("baseline", BASELINE_FEATURES),
                ("full", FULL_FEATURES),
            ):
                feature_list = list(features)
                ridge = make_pipeline(StandardScaler(), Ridge(alpha=RIDGE_ALPHA))
                logit = make_pipeline(
                    StandardScaler(),
                    LogisticRegression(C=LOGIT_C, max_iter=2_000, solver="lbfgs"),
                )
                ridge.fit(train[feature_list], train[target])
                logit.fit(train[feature_list], train[binary].astype(int))
                ridge_values = ridge.named_steps["ridge"].coef_
                logit_values = logit.named_steps["logisticregression"].coef_[0]
                for feature, ridge_value, logit_value in zip(
                    feature_list, ridge_values, logit_values, strict=True
                ):
                    rows.append(
                        {
                            "direction": direction,
                            "horizon_hours": horizon,
                            "feature_set": feature_set,
                            "feature": feature,
                            "ridge_standardized_coefficient": float(ridge_value),
                            "logit_standardized_coefficient": float(logit_value),
                        }
                    )
    return pd.DataFrame(rows)


def post_reveal_credibility(
    model_metrics: pd.DataFrame, direction: str
) -> dict[str, Any]:
    full = model_metrics.loc[
        model_metrics["direction"].eq(direction)
        & model_metrics["feature_set"].eq("full")
    ]
    train = full.loc[full["period"].eq("train_expanding_oof")].set_index(
        "horizon_hours"
    )
    validation = full.loc[full["period"].eq("validation")].set_index("horizon_hours")
    common = train.index.intersection(validation.index)
    same_sign = int(
        (
            np.sign(train.loc[common, "ridge_ic"].to_numpy(float))
            == np.sign(validation.loc[common, "ridge_ic"].to_numpy(float))
        ).sum()
    )
    return {
        "train_validation_full_ridge_ic_same_sign_horizons": same_sign,
        "at_least_2_of_3_train_validation_ic_signs_agree": same_sign >= 2,
        "note": (
            "Added only as a stricter post-reveal credibility diagnostic; formulas, "
            "models, gates and candidate status were not changed or rerun."
        ),
    }


def build_gate(
    model_metrics: pd.DataFrame,
    effects: pd.DataFrame,
    phase_sensitivity: pd.DataFrame,
    direction: str,
) -> dict[str, Any]:
    validation = model_metrics.loc[
        model_metrics["period"].eq("validation")
        & model_metrics["direction"].eq(direction)
    ]
    full = validation.loc[validation["feature_set"].eq("full")].set_index(
        "horizon_hours"
    )
    baseline = validation.loc[validation["feature_set"].eq("baseline")].set_index(
        "horizon_hours"
    )
    positive_ic_count = int(full["ridge_ic"].gt(0.0).sum())
    median_not_worse = bool(full["ridge_ic"].median() >= baseline["ridge_ic"].median())
    useful_logit_count = int(
        (full["logit_auc"].gt(0.5) & full["logit_brier"].le(full["constant_brier"]))
        .fillna(False)
        .sum()
    )
    direction_effects = effects.loc[
        effects["direction"].eq(direction)
        & effects["expected_direction"].isin(("positive", "negative"))
    ]
    feature_hits = (
        direction_effects.groupby("feature")["expected_sign_ci_excludes_zero"]
        .sum()
        .sort_values(ascending=False)
    )
    robust_features = [str(name) for name, count in feature_hits.items() if count >= 2]
    sign_same_after_trim = int(
        (
            np.sign(full["ridge_ic"].to_numpy(float))
            == np.sign(full["trimmed_1pct_ridge_ic"].to_numpy(float))
        ).sum()
    )
    phase = phase_sensitivity.loc[phase_sensitivity["direction"].eq(direction)]
    primary_value = float(
        phase.loc[phase["phase"].eq(PRIMARY_PHASE), "ridge_ic"].iloc[0]
    )
    phase_same_sign = int((np.sign(phase["ridge_ic"]) == np.sign(primary_value)).sum())
    min_blocks = int(direction_effects["independent_blocks"].min())
    gate = {
        "positive_full_ridge_ic_at_least_2_of_3": positive_ic_count >= 2,
        "median_full_ic_not_worse_than_baseline": median_not_worse,
        "useful_full_logit_at_least_2_of_3": useful_logit_count >= 2,
        "at_least_two_structural_features_with_two_robust_horizons": len(
            robust_features
        )
        >= 2,
        "trimmed_1pct_majority_ic_sign_preserved": sign_same_after_trim >= 2,
        "three_of_four_anchor_phases_same_7d_ic_sign": phase_same_sign >= 3,
        "at_least_10_independent_14d_blocks": min_blocks >= 10,
        "details": {
            "positive_ic_horizons": positive_ic_count,
            "useful_logit_horizons": useful_logit_count,
            "robust_structural_features": robust_features,
            "trimmed_sign_preserved_horizons": sign_same_after_trim,
            "same_sign_anchor_phases": phase_same_sign,
            "minimum_independent_blocks": min_blocks,
        },
    }
    gate["kinematic_evidence_supported"] = all(
        value for key, value in gate.items() if key != "details"
    )
    return gate


def rounded_records(frame: pd.DataFrame, digits: int = 8) -> list[dict[str, Any]]:
    output = frame.copy()
    float_columns = output.select_dtypes(include=["float"]).columns
    output[float_columns] = output[float_columns].round(digits)
    return output.replace({np.nan: None}).to_dict(orient="records")


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    frame, source_quality = load_price_data()
    hourly, hourly_quality = build_complete_hourly(frame)
    state = build_kinematic_state(hourly)
    labelled = add_future_labels(state)
    univariate_bins, univariate_effects = run_univariate(labelled)
    model_metrics, _ = run_models(labelled)
    phase_space = run_phase_space(labelled)
    phase_sensitivity = run_phase_sensitivity(labelled)
    label_summary = run_label_summary(labelled)
    model_coefficients = run_model_coefficients(labelled)
    gates = {
        direction: build_gate(
            model_metrics,
            univariate_effects,
            phase_sensitivity,
            direction,
        )
        for direction in ("long", "short")
    }
    observation_counts: dict[str, Any] = {}
    for direction, side in (("long", 1), ("short", -1)):
        observation_counts[direction] = {}
        for horizon in FUTURE_HORIZONS:
            observation_counts[direction][str(horizon)] = {
                period: int(
                    len(
                        phase_subset(
                            labelled,
                            phase=PRIMARY_PHASE,
                            side=side,
                            horizon=horizon,
                            period=period,
                        )
                    )
                )
                for period in ("train", "validation")
            }
    payload = {
        "family": "HYPE-1H-Price-Kinematics-Continuation",
        "research_role": "unregistered indicator-free price-kinematics diagnostic",
        "status": "explore / diagnostic-only / not promoted / not live-ready",
        "run_date": RUN_DATE,
        "data_quality": {
            "source_15m": source_quality,
            "derived_complete_1h": hourly_quality,
        },
        "contract": {
            "past_windows_hours": PAST_WINDOWS,
            "future_horizons_hours": FUTURE_HORIZONS,
            "primary_anchor_phase": PRIMARY_PHASE,
            "anchor_phases": ANCHOR_PHASES,
            "train": [TRAIN_START.isoformat(), TRAIN_END.isoformat()],
            "validation": [VALIDATION_START.isoformat(), VALIDATION_END.isoformat()],
            "prospective_oos_locked_not_revealed": [
                PROSPECTIVE_START.isoformat(),
                PROSPECTIVE_END.isoformat(),
            ],
            "ridge_alpha": RIDGE_ALPHA,
            "logit_c": LOGIT_C,
            "bootstrap_samples": BOOTSTRAP_SAMPLES,
            "block_hours": BLOCK_HOURS,
        },
        "observation_counts": observation_counts,
        "model_metrics": rounded_records(model_metrics),
        "univariate_effects": rounded_records(univariate_effects),
        "phase_sensitivity": rounded_records(phase_sensitivity),
        "direction_gates": gates,
        "post_reveal_credibility": {
            direction: post_reveal_credibility(model_metrics, direction)
            for direction in ("long", "short")
        },
        "prospective_oos_touched": False,
        "strategy_backtest_performed": False,
    }
    univariate_bins.to_csv(
        ARTIFACT_DIR / f"hype_1h_pkc_univariate_bins_{RUN_DATE}.csv", index=False
    )
    univariate_effects.to_csv(
        ARTIFACT_DIR / f"hype_1h_pkc_univariate_effects_{RUN_DATE}.csv", index=False
    )
    model_metrics.to_csv(
        ARTIFACT_DIR / f"hype_1h_pkc_model_metrics_{RUN_DATE}.csv", index=False
    )
    phase_space.to_csv(
        ARTIFACT_DIR / f"hype_1h_pkc_phase_space_{RUN_DATE}.csv", index=False
    )
    phase_sensitivity.to_csv(
        ARTIFACT_DIR / f"hype_1h_pkc_phase_sensitivity_{RUN_DATE}.csv", index=False
    )
    label_summary.to_csv(
        ARTIFACT_DIR / f"hype_1h_pkc_label_summary_{RUN_DATE}.csv", index=False
    )
    model_coefficients.to_csv(
        ARTIFACT_DIR / f"hype_1h_pkc_model_coefficients_{RUN_DATE}.csv", index=False
    )
    labelled.loc[
        labelled.index < PROSPECTIVE_START,
        [
            "direction",
            "anchor_phase",
            *FULL_FEATURES,
            *(f"future_z_{horizon}" for horizon in FUTURE_HORIZONS),
            *(f"continuation_{horizon}" for horizon in FUTURE_HORIZONS),
        ],
    ].to_parquet(ARTIFACT_DIR / f"hype_1h_pkc_labelled_observations_{RUN_DATE}.parquet")
    result_path = ARTIFACT_DIR / f"hype_1h_pkc_research_{RUN_DATE}.json"
    result_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
