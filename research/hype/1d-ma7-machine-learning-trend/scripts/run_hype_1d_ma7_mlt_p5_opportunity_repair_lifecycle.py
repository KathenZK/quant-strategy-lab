from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-machine-learning-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CONTRACT = (
    FAMILY_DIR
    / "specs/hype-1d-ma7-mlt-p5-opportunity-repair-lifecycle-contract-2026-08-28.md"
)
P4_SCRIPT = (
    FAMILY_DIR
    / "scripts/run_hype_1d_ma7_mlt_p4_v7_1_behavior_clone_residual.py"
)
MISSED_AUDIT = (
    ROOT
    / "research/hype/1d-ma7-asymmetric-body-trend/scripts/"
    "audit_hype_1d_ma7_v6_missed_trend_attribution.py"
)

FAMILY = "HYPE-1D-MA7-Machine-Learning-Trend"
EXPERIMENT = "P5_OPPORTUNITY_REPAIR_LIFECYCLE"
RUN_DATE = "2026-08-28"
PREFIX = "hype_1d_ma7_mlt_p5_opportunity_repair_lifecycle_2026-08-28"
TRAIN_DAYS = 365
TOTAL_DAYS = 446
DEVELOPMENT_DAYS = 285
LABEL_PURGE_DAYS = 3
OOF_WINDOWS = ((120, 160), (160, 200), (200, 240), (240, 285))
RANDOM_STATE = 20260828
ENTRY_THRESHOLD = 0.55
EXIT_THRESHOLD = 0.45
REVERSAL_MARGIN = 0.05
EMA_ALPHA = 0.50
SLIPPAGE = 0.0004

ROOT_FEATURES = [
    "root_age",
    "aligned_ma_gap_atr",
    "initial_cross_gap_atr",
    "gap_expansion_atr",
    "aligned_slope1_atr",
    "aligned_slope2_atr_per_day",
    "aligned_slope3_atr_per_day",
    "aligned_slope_acceleration",
    "aligned_return_1d",
    "aligned_return_3d",
    "aligned_return_7d",
    "aligned_body_atr",
    "aligned_close_location",
    "range_atr",
    "aligned_rsi6",
    "er7",
    "same_side_ratio3",
    "same_side_ratio7",
    "gap_expansion_ratio3",
    "gap_expansion_ratio7",
    "cross_count7",
    "cross_count14",
    "atr_pct",
]

STRUCTURE_FEATURES = [
    "aligned_return_14d",
    "aligned_return_30d",
    "aligned_ma30_gap_atr",
    "aligned_ma7_ma30_atr",
    "aligned_ma30_slope7_atr",
    "directional_range_position30",
    "distance_directional_extreme30_atr",
    "recovery_from_opposite_extreme30_atr",
    "atr_compression7_30",
    "range_compression7_30",
    "return_vol_compression7_30",
]

PARTICIPATION_FEATURES = [
    "volume_z7",
    "volume_z30",
    "aligned_signed_volume_pressure7",
    "aligned_funding_1d",
    "aligned_funding_3d",
    "aligned_funding_7d",
    "aligned_funding_change3d",
]

FEATURE_BLOCKS = {
    "B1_ROOT_PATH": ROOT_FEATURES,
    "B2_PRETREND_STRUCTURE": ROOT_FEATURES + STRUCTURE_FEATURES,
    "B3_PARTICIPATION_FUNDING": ROOT_FEATURES
    + STRUCTURE_FEATURES
    + PARTICIPATION_FEATURES,
}

MANIFEST_PATH = ARTIFACT_DIR / f"{PREFIX}_development_manifest.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"Run {EXPERIMENT}.")
    parser.add_argument("--stage", choices=("develop", "validate"), default="develop")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value).isoformat()
    if isinstance(value, np.ndarray):
        return [sanitize(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return sanitize(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(sanitize(payload), ensure_ascii=False, indent=2, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, rows: Any) -> None:
    frame = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    frame.to_csv(path, index=False)


def write_sidecar(path: Path) -> None:
    path.with_suffix(path.suffix + ".sha256").write_text(
        f"{sha256(path)}  {path.name}\n", encoding="utf-8"
    )


def safe_ratio(numerator: float, denominator: float) -> float:
    if not math.isfinite(numerator) or not math.isfinite(denominator) or denominator == 0:
        return math.nan
    return numerator / denominator


def _daily_external_features(context: Any, daily_index: pd.DatetimeIndex) -> pd.DataFrame:
    hourly = context.market.hourly.copy()
    hourly["day"] = pd.to_datetime(hourly["ts"], utc=True).dt.floor("D")
    volume = hourly.groupby("day", sort=True)["volume"].sum().reindex(daily_index)
    funding = context.market.funding.copy()
    funding["day"] = pd.to_datetime(funding["ts"], utc=True).dt.floor("D")
    funding_daily = (
        funding.groupby("day", sort=True)["funding_rate"].sum().reindex(daily_index).fillna(0.0)
    )
    return pd.DataFrame(
        {"daily_volume": volume.astype(float), "funding_1d_raw": funding_daily.astype(float)},
        index=daily_index,
    )


def build_feature_frame(p4: Any, engine: Any, context: Any) -> pd.DataFrame:
    base = p4.market_rows(engine, context).copy()
    daily_index = pd.DatetimeIndex(pd.to_datetime(base["ts"], utc=True))
    external = _daily_external_features(context, daily_index).reset_index(drop=True)
    base = pd.concat([base.reset_index(drop=True), external], axis=1)

    close = base["close"].astype(float)
    open_ = base["open"].astype(float)
    high = base["high"].astype(float)
    low = base["low"].astype(float)
    ma7 = base["ma7"].astype(float)
    atr = base["atr7"].astype(float)
    raw_cross = base["raw_cross"].astype(int).to_numpy()

    root_side = np.zeros(len(base), dtype=int)
    root_age = np.zeros(len(base), dtype=int)
    root_index = np.full(len(base), -1, dtype=int)
    current_side = 0
    current_root = -1
    for index, cross in enumerate(raw_cross):
        if cross:
            current_side = int(cross)
            current_root = index
        root_side[index] = current_side
        root_index[index] = current_root
        root_age[index] = index - current_root if current_root >= 0 else 0
    base["root_side"] = root_side
    base["root_index"] = root_index
    base["root_age"] = root_age

    ma30 = close.rolling(30, min_periods=10).mean()
    rolling_high30 = high.rolling(30, min_periods=10).max()
    rolling_low30 = low.rolling(30, min_periods=10).min()
    range30 = rolling_high30 - rolling_low30
    daily_range = high - low
    returns = close.pct_change()
    volume = base["daily_volume"].astype(float)
    signed_volume = ((close - open_) / daily_range.replace(0.0, np.nan)) * volume

    aligned_gap = root_side * (close - ma7) / atr
    initial_gap = np.full(len(base), np.nan)
    for index, origin in enumerate(root_index):
        if origin >= 0:
            initial_gap[index] = aligned_gap.iloc[origin]
    gap_array = aligned_gap.to_numpy(float)
    side_array = root_side.astype(float)
    same_side = (side_array * (close - ma7).to_numpy(float) > 0.0).astype(float)
    gap_delta = pd.Series(gap_array).diff()

    base["aligned_ma_gap_atr"] = aligned_gap
    base["initial_cross_gap_atr"] = initial_gap
    base["gap_expansion_atr"] = aligned_gap - initial_gap
    base["aligned_slope1_atr"] = root_side * base["slope1_atr"].astype(float)
    base["aligned_slope2_atr_per_day"] = root_side * base[
        "slope2_atr_per_day"
    ].astype(float)
    base["aligned_slope3_atr_per_day"] = root_side * base[
        "slope3_atr_per_day"
    ].astype(float)
    base["aligned_slope_acceleration"] = base["aligned_slope1_atr"].diff()
    for days in (1, 3, 7, 14, 30):
        base[f"aligned_return_{days}d"] = root_side * (close / close.shift(days) - 1.0)
    base["aligned_body_atr"] = root_side * (close - open_) / atr
    base["aligned_close_location"] = np.where(
        root_side >= 0,
        base["close_location"].astype(float),
        1.0 - base["close_location"].astype(float),
    )
    base["aligned_rsi6"] = root_side * (base["rsi6"].astype(float) - 50.0) / 50.0
    base["same_side_ratio3"] = pd.Series(same_side).rolling(3, min_periods=1).mean()
    base["same_side_ratio7"] = pd.Series(same_side).rolling(7, min_periods=1).mean()
    base["gap_expansion_ratio3"] = gap_delta.gt(0.0).rolling(3, min_periods=1).mean()
    base["gap_expansion_ratio7"] = gap_delta.gt(0.0).rolling(7, min_periods=1).mean()
    base["cross_count7"] = base["raw_cross"].abs().rolling(7, min_periods=1).sum()

    base["aligned_ma30_gap_atr"] = root_side * (close - ma30) / atr
    base["aligned_ma7_ma30_atr"] = root_side * (ma7 - ma30) / atr
    base["aligned_ma30_slope7_atr"] = root_side * (ma30 - ma30.shift(7)) / (7.0 * atr)
    position30 = (close - rolling_low30) / range30.replace(0.0, np.nan)
    base["directional_range_position30"] = np.where(
        root_side >= 0, position30, 1.0 - position30
    )
    base["distance_directional_extreme30_atr"] = np.where(
        root_side >= 0,
        (close - rolling_high30) / atr,
        (rolling_low30 - close) / atr,
    )
    base["recovery_from_opposite_extreme30_atr"] = np.where(
        root_side >= 0,
        (close - rolling_low30) / atr,
        (rolling_high30 - close) / atr,
    )
    base["atr_compression7_30"] = atr.rolling(7, min_periods=3).mean() / atr.rolling(
        30, min_periods=10
    ).mean()
    base["range_compression7_30"] = daily_range.rolling(7, min_periods=3).mean() / daily_range.rolling(
        30, min_periods=10
    ).mean()
    base["return_vol_compression7_30"] = returns.rolling(7, min_periods=3).std() / returns.rolling(
        30, min_periods=10
    ).std()

    log_volume = np.log1p(volume)
    base["volume_z7"] = (log_volume - log_volume.rolling(7, min_periods=3).mean()) / log_volume.rolling(
        7, min_periods=3
    ).std()
    base["volume_z30"] = (
        log_volume - log_volume.rolling(30, min_periods=10).mean()
    ) / log_volume.rolling(30, min_periods=10).std()
    pressure7 = signed_volume.rolling(7, min_periods=3).sum() / volume.rolling(
        7, min_periods=3
    ).sum()
    base["aligned_signed_volume_pressure7"] = root_side * pressure7
    funding_1d = base["funding_1d_raw"].astype(float)
    base["aligned_funding_1d"] = root_side * funding_1d
    base["aligned_funding_3d"] = root_side * funding_1d.rolling(3, min_periods=1).sum()
    base["aligned_funding_7d"] = root_side * funding_1d.rolling(7, min_periods=1).sum()
    base["aligned_funding_change3d"] = root_side * (funding_1d - funding_1d.shift(3))
    return base


def build_labels(context: Any, frame: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]], dict[str, Path]]:
    audit = load_module(MISSED_AUDIT, f"hype_p5_missed_{context.book.count}")
    labels = load_module(audit.LABEL_ENGINE_PATH, f"hype_p5_labels_{context.book.count}")
    r3 = load_module(audit.R3_PATH, f"hype_p5_r3_{context.book.count}")
    r4 = load_module(audit.R4_PATH, f"hype_p5_r4_{context.book.count}")
    daily = context.market.daily.copy()
    raw_labels = labels.hindsight_labels(daily.loc[:, ["close", "ma7", "atr7"]])
    raw_direction = r3.direction_target(raw_labels)
    stable = r4.stable_direction_target(raw_direction)
    episodes = audit.extract_reference_episodes(stable, daily, raw_labels)
    output = frame.copy()
    output["stable_side"] = stable.to_numpy(float)
    output["target_known"] = output["stable_side"].notna()
    output["trend_active"] = np.where(
        output["target_known"],
        (
            (output["root_side"].astype(int) != 0)
            & (output["stable_side"].astype(float) == output["root_side"].astype(float))
        ).astype(int),
        np.nan,
    )
    return output, episodes, {
        "missed_audit": MISSED_AUDIT,
        "label_engine": Path(audit.LABEL_ENGINE_PATH),
        "r3_direction": Path(audit.R3_PATH),
        "r4_stable": Path(audit.R4_PATH),
    }


def candidate_rows(frame: pd.DataFrame, left: int, right: int) -> pd.DataFrame:
    mask = (
        (frame["index"].astype(int) >= left)
        & (frame["index"].astype(int) < right)
        & frame["target_known"].astype(bool)
        & (frame["root_side"].astype(int) != 0)
    )
    return frame.loc[mask].copy()


def make_model() -> Pipeline:
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            (
                "model",
                ExtraTreesClassifier(
                    n_estimators=600,
                    max_depth=6,
                    min_samples_leaf=6,
                    max_features=0.75,
                    class_weight="balanced",
                    random_state=RANDOM_STATE,
                    n_jobs=-1,
                ),
            ),
        ]
    )


def fit_model(frame: pd.DataFrame, features: list[str]) -> Pipeline:
    if frame.empty or frame["trend_active"].nunique() < 2:
        raise RuntimeError("training frame does not contain both target classes")
    model = make_model()
    model.fit(frame[features], frame["trend_active"].astype(int))
    return model


def classification_metrics(actual: np.ndarray, probability: np.ndarray) -> dict[str, Any]:
    y = np.asarray(actual, dtype=int)
    p = np.asarray(probability, dtype=float)
    predicted = p >= 0.5
    return {
        "rows": len(y),
        "positive_rate": float(y.mean()) if len(y) else math.nan,
        "auc": float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else math.nan,
        "brier": float(brier_score_loss(y, p)) if len(y) else math.nan,
        "accuracy_at_0_5": float(accuracy_score(y, predicted)) if len(y) else math.nan,
        "balanced_accuracy_at_0_5": (
            float(balanced_accuracy_score(y, predicted)) if len(np.unique(y)) == 2 else math.nan
        ),
        "precision_at_0_5": float(precision_score(y, predicted, zero_division=0)),
        "recall_at_0_5": float(recall_score(y, predicted, zero_division=0)),
        "f1_at_0_5": float(f1_score(y, predicted, zero_division=0)),
    }


def expanding_oof(frame: pd.DataFrame, features: list[str]) -> tuple[pd.DataFrame, dict[str, Any]]:
    outputs: list[pd.DataFrame] = []
    fold_audit: list[dict[str, Any]] = []
    for fold, (start, end) in enumerate(OOF_WINDOWS, start=1):
        train = candidate_rows(frame, 0, start - LABEL_PURGE_DAYS)
        test = candidate_rows(frame, start, end)
        model = fit_model(train, features)
        probability = model.predict_proba(test[features])[:, 1]
        part = test[["index", "ts", "root_side", "stable_side", "trend_active"]].copy()
        part["fold"] = fold
        part["probability"] = probability
        outputs.append(part)
        fold_audit.append(
            {
                "fold": fold,
                "train_end_exclusive": start - LABEL_PURGE_DAYS,
                "train_rows": len(train),
                "test_start": start,
                "test_end_exclusive": end,
                "test_rows": len(test),
            }
        )
    output = pd.concat(outputs, ignore_index=True)
    metrics = classification_metrics(
        output["trend_active"].astype(int).to_numpy(), output["probability"].to_numpy(float)
    )
    metrics["folds"] = fold_audit
    return output, metrics


def select_feature_block(results: list[dict[str, Any]]) -> str:
    best_auc = max(float(row["metrics"]["auc"]) for row in results)
    eligible = [row for row in results if best_auc - float(row["metrics"]["auc"]) <= 0.01]
    return min(eligible, key=lambda row: list(FEATURE_BLOCKS).index(str(row["block"]))) ["block"]


def predict_frame(model: Pipeline, frame: pd.DataFrame, features: list[str], left: int, right: int) -> pd.DataFrame:
    score = frame.loc[
        (frame["index"].astype(int) >= left)
        & (frame["index"].astype(int) < right)
        & (frame["root_side"].astype(int) != 0)
    ].copy()
    score["probability"] = model.predict_proba(score[features])[:, 1]
    return score


def _open_ts(context: Any, index: int) -> pd.Timestamp:
    if index < context.book.count:
        return pd.Timestamp(context.book.ts[index])
    if index == context.book.count:
        return pd.Timestamp(context.book.terminal_ts)
    raise IndexError(index)


def _open_price(context: Any, index: int) -> float:
    if index < context.book.count:
        return float(context.book.open[index])
    if index == context.book.count:
        return float(context.book.quality["terminal_open"])
    raise IndexError(index)


def apply_policy(
    context: Any,
    frame: pd.DataFrame,
    probabilities: pd.DataFrame,
    left: int,
    right: int,
) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    probability_map = dict(
        zip(probabilities["index"].astype(int), probabilities["probability"].astype(float), strict=True)
    )
    state = frame.set_index(frame["index"].astype(int), drop=False)
    side = 0
    entry_index = -1
    entry_probability = math.nan
    entry_root_index = -1
    cooldown_decision = left
    smooth = math.nan
    prior_root = 0
    trades: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []

    def close_trade(exit_index: int, reason: str, reversal: bool = False) -> None:
        nonlocal side, entry_index, entry_probability, entry_root_index
        trades.append(
            {
                "entry_ts": _open_ts(context, entry_index).isoformat(),
                "exit_ts": _open_ts(context, exit_index).isoformat(),
                "side": "long" if side > 0 else "short",
                "entry_price": _open_price(context, entry_index),
                "entry_leverage": 1.0,
                "exit_price": _open_price(context, exit_index),
                "bars_held": exit_index - entry_index,
                "exit_reason": reason,
                "entry_probability": entry_probability,
                "entry_root_index": entry_root_index,
                "direct_reversal": reversal,
            }
        )
        side = 0
        entry_index = -1
        entry_probability = math.nan
        entry_root_index = -1

    for decision_index in range(left, right):
        row = state.loc[decision_index]
        root = int(row["root_side"])
        raw_probability = float(probability_map.get(decision_index, 0.0))
        if root == 0:
            smooth = 0.0
        elif root != prior_root or not math.isfinite(smooth):
            smooth = raw_probability
        else:
            smooth = EMA_ALPHA * raw_probability + (1.0 - EMA_ALPHA) * smooth
        prior_root = root
        action_index = decision_index + 1
        action = "FLAT" if side == 0 else "HOLD"
        old_side = side

        if action_index >= right:
            if side != 0:
                close_trade(right, "terminal")
                action = "TERMINAL_EXIT"
        elif side == 0:
            if decision_index >= cooldown_decision and root != 0 and smooth >= ENTRY_THRESHOLD:
                side = root
                entry_index = action_index
                entry_probability = smooth
                entry_root_index = int(row["root_index"])
                action = "ENTER_LONG" if side > 0 else "ENTER_SHORT"
        elif root != side:
            reverse_ready = root != 0 and smooth >= max(
                ENTRY_THRESHOLD, EXIT_THRESHOLD + REVERSAL_MARGIN
            )
            close_trade(action_index, "direct_reversal" if reverse_ready else "opposite_cross_exit", reverse_ready)
            cooldown_decision = decision_index + 1
            if reverse_ready:
                side = root
                entry_index = action_index
                entry_probability = smooth
                entry_root_index = int(row["root_index"])
                action = "REVERSE_TO_LONG" if side > 0 else "REVERSE_TO_SHORT"
            else:
                action = "EXIT_ON_OPPOSITE_CROSS"
        elif smooth < EXIT_THRESHOLD:
            close_trade(action_index, "trend_probability_exit")
            cooldown_decision = decision_index + 1
            action = "EXIT_LONG" if old_side > 0 else "EXIT_SHORT"

        decisions.append(
            {
                "decision_index": decision_index,
                "decision_ts": pd.Timestamp(row["ts"]).isoformat(),
                "action_ts": _open_ts(context, min(action_index, right)).isoformat(),
                "root_side": root,
                "raw_probability": raw_probability,
                "smoothed_probability": smooth,
                "position_after_action": side,
                "action": action,
            }
        )
    if side != 0:
        close_trade(right, "terminal")
    return trades, pd.DataFrame(decisions)


def episode_capture(
    context: Any,
    episodes: list[dict[str, Any]],
    trades: list[dict[str, Any]],
    left: int,
    right: int,
) -> tuple[dict[str, Any], pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    total_days = 0
    covered_days = 0
    for episode in episodes:
        start = max(left, int(episode["start_index"]))
        end = min(right - 1, int(episode["end_index"]))
        if start > end:
            continue
        side = int(episode["side"])
        covered = 0
        for index in range(start, end + 1):
            ts = _open_ts(context, index)
            if any(
                (1 if str(trade["side"]) == "long" else -1) == side
                and pd.Timestamp(trade["entry_ts"]) <= ts < pd.Timestamp(trade["exit_ts"])
                for trade in trades
            ):
                covered += 1
        duration = end - start + 1
        total_days += duration
        covered_days += covered
        rows.append(
            {
                "episode_id": episode["episode_id"],
                "side": side,
                "direction": episode["direction"],
                "start_index": start,
                "end_index": end,
                "start_ts": _open_ts(context, start).isoformat(),
                "end_ts": _open_ts(context, end).isoformat(),
                "duration_days": duration,
                "covered_days": covered,
                "capture_ratio": covered / duration,
                "fully_missed": covered == 0,
            }
        )
    metrics = {
        "reference_episodes": len(rows),
        "episodes_with_any_exposure": sum(not row["fully_missed"] for row in rows),
        "fully_missed_episodes": sum(row["fully_missed"] for row in rows),
        "reference_days": total_days,
        "covered_days": covered_days,
        "duration_weighted_capture": covered_days / total_days if total_days else math.nan,
    }
    return metrics, pd.DataFrame(rows)


def replay_bundle(p4: Any, v6: Any, context: Any, trades: list[dict[str, Any]]) -> dict[str, Any]:
    return p4.replay_metrics(v6, context, trades)


def recent_slices(
    p4: Any,
    diag: Any,
    v6: Any,
    engine: Any,
    context: Any,
    frame: pd.DataFrame,
    probabilities: pd.DataFrame,
    left: int,
    right: int,
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for name, days in {"1d": 1, "7d": 7, "1m": 30, "3m": 90, "6m": 182, "1y": 365}.items():
        slice_left = max(left, right - days)
        ml_trades, _ = apply_policy(context, frame, probabilities, slice_left, right)
        teacher = p4.run_teacher(diag, v6, engine, context, slice_left, right)
        output[name] = {
            "available_days": right - slice_left,
            "p5": replay_bundle(p4, v6, context, ml_trades),
            "v7_1": replay_bundle(p4, v6, context, list(teacher.result.raw.trades)),
        }
    return output


def source_manifest(p4: Any, diag: Any, label_paths: dict[str, Path]) -> dict[str, Any]:
    paths = {
        "contract": CONTRACT,
        "script": Path(__file__),
        "p4_shared_runtime": P4_SCRIPT,
        "v7_1_diagnostic": Path(p4.DIAGNOSTIC),
        "v7_1_engine": Path(diag.ENGINE_PATH),
        "v7_1_adapter": Path(diag.ADAPTER_PATH),
        "v6_replay": Path(diag.V6_ABLATION_PATH),
        **label_paths,
    }
    return {
        name: {"path": str(path.relative_to(ROOT)), "sha256": sha256(path)}
        for name, path in paths.items()
    }


def verify_manifest(manifest: dict[str, Any]) -> None:
    sidecar = MANIFEST_PATH.with_suffix(MANIFEST_PATH.suffix + ".sha256")
    if not sidecar.exists() or sidecar.read_text(encoding="utf-8").split()[0] != sha256(MANIFEST_PATH):
        raise RuntimeError("development manifest hash mismatch")
    for source in manifest["sources"].values():
        path = ROOT / source["path"]
        if sha256(path) != source["sha256"]:
            raise RuntimeError(f"frozen source drift: {path}")


def develop() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    p4 = load_module(P4_SCRIPT, "hype_p5_p4_train")
    diag, v6, engine, _, context = p4.load_dependencies(train_only=True)
    if context.book.count != TRAIN_DAYS:
        raise RuntimeError("development context is not physically limited to 365 days")
    if pd.Timestamp(context.market.audit["hourly_end"]) > p4.TRAIN_TERMINAL:
        raise RuntimeError("development read holdout hourly bars")
    if pd.Timestamp(context.market.audit["funding_end"]) > p4.TRAIN_TERMINAL:
        raise RuntimeError("development read holdout funding")

    frame, episodes, label_paths = build_labels(context, build_feature_frame(p4, engine, context))
    block_results: list[dict[str, Any]] = []
    oof_outputs: list[pd.DataFrame] = []
    for block, features in FEATURE_BLOCKS.items():
        predictions, metrics = expanding_oof(frame, features)
        predictions["feature_block"] = block
        oof_outputs.append(predictions)
        block_results.append({"block": block, "feature_count": len(features), "metrics": metrics})
    selected_block = select_feature_block(block_results)
    selected_features = FEATURE_BLOCKS[selected_block]
    selected_oof = next(row for row in block_results if row["block"] == selected_block)

    development_fit = candidate_rows(frame, 0, DEVELOPMENT_DAYS - LABEL_PURGE_DAYS)
    development_model = fit_model(development_fit, selected_features)
    confirmation_predictions = predict_frame(
        development_model, frame, selected_features, DEVELOPMENT_DAYS, TRAIN_DAYS
    )
    confirmation_known = confirmation_predictions.loc[confirmation_predictions["target_known"].astype(bool)]
    confirmation_classification = classification_metrics(
        confirmation_known["trend_active"].astype(int).to_numpy(),
        confirmation_known["probability"].to_numpy(float),
    )
    confirmation_trades, confirmation_decisions = apply_policy(
        context, frame, confirmation_predictions, DEVELOPMENT_DAYS, TRAIN_DAYS
    )
    confirmation_metrics = replay_bundle(p4, v6, context, confirmation_trades)
    confirmation_teacher = p4.run_teacher(
        diag, v6, engine, context, DEVELOPMENT_DAYS, TRAIN_DAYS
    )
    confirmation_teacher_trades = list(confirmation_teacher.result.raw.trades)
    teacher_confirmation_metrics = replay_bundle(p4, v6, context, confirmation_teacher_trades)
    p5_confirmation_capture, p5_confirmation_episodes = episode_capture(
        context, episodes, confirmation_trades, DEVELOPMENT_DAYS, TRAIN_DAYS
    )
    v7_confirmation_capture, v7_confirmation_episodes = episode_capture(
        context, episodes, confirmation_teacher_trades, DEVELOPMENT_DAYS, TRAIN_DAYS
    )
    development_gate = bool(
        float(selected_oof["metrics"]["auc"]) >= 0.55
        and float(confirmation_classification["auc"]) >= 0.55
        and float(confirmation_metrics["net_return_pct"]) >= 0.0
        and float(p5_confirmation_capture["duration_weighted_capture"])
        > float(v7_confirmation_capture["duration_weighted_capture"])
    )

    full_fit = candidate_rows(frame, 0, TRAIN_DAYS)
    full_model = fit_model(full_fit, selected_features)
    full_predictions = predict_frame(full_model, frame, selected_features, 0, TRAIN_DAYS)
    full_known = full_predictions.loc[full_predictions["target_known"].astype(bool)]
    full_classification = classification_metrics(
        full_known["trend_active"].astype(int).to_numpy(),
        full_known["probability"].to_numpy(float),
    )
    full_trades, full_decisions = apply_policy(context, frame, full_predictions, 0, TRAIN_DAYS)
    full_metrics = replay_bundle(p4, v6, context, full_trades)
    teacher = p4.run_teacher(diag, v6, engine, context, 0, TRAIN_DAYS)
    teacher_trades = list(teacher.result.raw.trades)
    teacher_metrics = replay_bundle(p4, v6, context, teacher_trades)
    p5_full_capture, p5_full_episodes = episode_capture(
        context, episodes, full_trades, 0, TRAIN_DAYS
    )
    v7_full_capture, v7_full_episodes = episode_capture(
        context, episodes, teacher_trades, 0, TRAIN_DAYS
    )
    importances = pd.DataFrame(
        {
            "feature": selected_features,
            "importance": full_model.named_steps["model"].feature_importances_,
        }
    ).sort_values("importance", ascending=False)
    slices = recent_slices(
        p4, diag, v6, engine, context, frame, full_predictions, 0, TRAIN_DAYS
    )
    status = (
        "DEVELOPMENT_PASS_READY_FOR_REUSED_HOLDOUT"
        if development_gate
        else "DEVELOPMENT_FAILED_HOLDOUT_LOCKED"
    )

    paths = {
        "feature_labels": ARTIFACT_DIR / f"{PREFIX}_training_feature_labels.csv",
        "oof": ARTIFACT_DIR / f"{PREFIX}_development_oof_predictions.csv",
        "confirmation_predictions": ARTIFACT_DIR / f"{PREFIX}_internal_confirmation_predictions.csv",
        "confirmation_decisions": ARTIFACT_DIR / f"{PREFIX}_internal_confirmation_decisions.csv",
        "confirmation_trades": ARTIFACT_DIR / f"{PREFIX}_internal_confirmation_trades.csv",
        "full_predictions": ARTIFACT_DIR / f"{PREFIX}_training_predictions.csv",
        "full_decisions": ARTIFACT_DIR / f"{PREFIX}_training_decisions.csv",
        "full_trades": ARTIFACT_DIR / f"{PREFIX}_training_trades.csv",
        "teacher_trades": ARTIFACT_DIR / f"{PREFIX}_training_v7_1_trades.csv",
        "episode_capture": ARTIFACT_DIR / f"{PREFIX}_training_episode_capture.csv",
        "feature_importance": ARTIFACT_DIR / f"{PREFIX}_feature_importance.csv",
        "summary": ARTIFACT_DIR / f"{PREFIX}_development_summary.json",
    }
    write_csv(paths["feature_labels"], frame)
    write_csv(paths["oof"], pd.concat(oof_outputs, ignore_index=True))
    write_csv(paths["confirmation_predictions"], confirmation_predictions)
    write_csv(paths["confirmation_decisions"], confirmation_decisions)
    write_csv(paths["confirmation_trades"], confirmation_trades)
    write_csv(paths["full_predictions"], full_predictions)
    write_csv(paths["full_decisions"], full_decisions)
    write_csv(paths["full_trades"], full_trades)
    write_csv(paths["teacher_trades"], teacher_trades)
    episode_comparison = pd.concat(
        [
            p5_full_episodes.assign(strategy="P5"),
            v7_full_episodes.assign(strategy="V7.1"),
            p5_confirmation_episodes.assign(strategy="P5_INTERNAL_CONFIRMATION"),
            v7_confirmation_episodes.assign(strategy="V7.1_INTERNAL_CONFIRMATION"),
        ],
        ignore_index=True,
    )
    write_csv(paths["episode_capture"], episode_comparison)
    write_csv(paths["feature_importance"], importances)

    summary = {
        "family": FAMILY,
        "experiment": EXPERIMENT,
        "run_date": RUN_DATE,
        "stage": "develop",
        "status": status,
        "research_status": ["diagnostic-only", "reused-holdout", "not promoted", "not live-ready"],
        "data_boundary": {
            "train_days": TRAIN_DAYS,
            "train_start": pd.Timestamp(context.book.ts[0]),
            "train_last_feature_day": pd.Timestamp(context.book.ts[-1]),
            "train_terminal": pd.Timestamp(context.book.terminal_ts),
            "holdout_days": TOTAL_DAYS - TRAIN_DAYS,
            "holdout_read": False,
            "hourly_end": context.market.audit["hourly_end"],
            "funding_end": context.market.audit["funding_end"],
        },
        "label": {
            "name": "stable_trend_matches_current_ma7_cross_root",
            "hindsight_audit_only": True,
            "mature_training_rows": len(full_fit),
            "positive_rate": float(full_fit["trend_active"].mean()),
            "reference_episodes": len(episodes),
        },
        "model": {
            "type": "ExtraTreesClassifier",
            "random_state": RANDOM_STATE,
            "selected_feature_block": selected_block,
            "selected_features": selected_features,
            "feature_block_oof": block_results,
            "fixed_policy": {
                "entry_threshold": ENTRY_THRESHOLD,
                "exit_threshold": EXIT_THRESHOLD,
                "reversal_margin": REVERSAL_MARGIN,
                "ema_alpha": EMA_ALPHA,
            },
        },
        "development_gate": {
            "passed": development_gate,
            "requirements": {
                "oof_auc_gte_0_55": float(selected_oof["metrics"]["auc"]) >= 0.55,
                "confirmation_auc_gte_0_55": float(confirmation_classification["auc"]) >= 0.55,
                "confirmation_net_nonnegative": float(confirmation_metrics["net_return_pct"]) >= 0.0,
                "confirmation_capture_gt_v7_1": float(p5_confirmation_capture["duration_weighted_capture"])
                > float(v7_confirmation_capture["duration_weighted_capture"]),
            },
            "internal_confirmation": {
                "classification": confirmation_classification,
                "p5": confirmation_metrics,
                "v7_1": teacher_confirmation_metrics,
                "p5_episode_capture": p5_confirmation_capture,
                "v7_1_episode_capture": v7_confirmation_capture,
            },
        },
        "full_training_resubstitution": {
            "classification": full_classification,
            "p5": full_metrics,
            "v7_1": teacher_metrics,
            "p5_episode_capture": p5_full_capture,
            "v7_1_episode_capture": v7_full_capture,
            "recent_slices_flat_start": slices,
        },
        "top_feature_importance": importances.head(20).to_dict("records"),
    }
    write_json(paths["summary"], summary)
    for path in paths.values():
        write_sidecar(path)

    manifest = {
        "family": FAMILY,
        "experiment": EXPERIMENT,
        "run_date": RUN_DATE,
        "status": status,
        "train_days": TRAIN_DAYS,
        "total_days": TOTAL_DAYS,
        "development_days": DEVELOPMENT_DAYS,
        "label_purge_days": LABEL_PURGE_DAYS,
        "selected_feature_block": selected_block,
        "selected_features": selected_features,
        "model": {
            "n_estimators": 600,
            "max_depth": 6,
            "min_samples_leaf": 6,
            "max_features": 0.75,
            "class_weight": "balanced",
            "random_state": RANDOM_STATE,
        },
        "policy": {
            "entry_threshold": ENTRY_THRESHOLD,
            "exit_threshold": EXIT_THRESHOLD,
            "reversal_margin": REVERSAL_MARGIN,
            "ema_alpha": EMA_ALPHA,
        },
        "development_gate": development_gate,
        "holdout_permitted": development_gate,
        "sources": source_manifest(p4, diag, label_paths),
        "development_artifacts": {
            name: {"path": str(path.relative_to(ROOT)), "sha256": sha256(path)}
            for name, path in paths.items()
        },
    }
    write_json(MANIFEST_PATH, manifest)
    write_sidecar(MANIFEST_PATH)
    return summary


def validate() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        raise RuntimeError("run --stage develop first")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    verify_manifest(manifest)
    if not manifest.get("holdout_permitted"):
        raise RuntimeError("development gates failed; contract forbids holdout read")

    p4 = load_module(P4_SCRIPT, "hype_p5_p4_validate")
    train_diag, _, train_engine, _, train_context = p4.load_dependencies(train_only=True)
    train_frame, _, _ = build_labels(
        train_context, build_feature_frame(p4, train_engine, train_context)
    )
    selected_features = list(manifest["selected_features"])
    model = fit_model(candidate_rows(train_frame, 0, TRAIN_DAYS), selected_features)

    diag, v6, engine, _, context = p4.load_dependencies(train_only=False)
    if context.book.count != TOTAL_DAYS:
        raise RuntimeError("validation context length drift")
    frame, episodes, _ = build_labels(context, build_feature_frame(p4, engine, context))
    predictions = predict_frame(model, frame, selected_features, TRAIN_DAYS, TOTAL_DAYS)
    known = predictions.loc[predictions["target_known"].astype(bool)]
    classification = classification_metrics(
        known["trend_active"].astype(int).to_numpy(), known["probability"].to_numpy(float)
    )
    trades, decisions = apply_policy(context, frame, predictions, TRAIN_DAYS, TOTAL_DAYS)
    metrics = replay_bundle(p4, v6, context, trades)
    teacher = p4.run_teacher(diag, v6, engine, context, TRAIN_DAYS, TOTAL_DAYS)
    teacher_trades = list(teacher.result.raw.trades)
    teacher_metrics = replay_bundle(p4, v6, context, teacher_trades)
    p5_capture, p5_episodes = episode_capture(
        context, episodes, trades, TRAIN_DAYS, TOTAL_DAYS
    )
    v7_capture, v7_episodes = episode_capture(
        context, episodes, teacher_trades, TRAIN_DAYS, TOTAL_DAYS
    )
    slices = recent_slices(
        p4, diag, v6, engine, context, frame, predictions, TRAIN_DAYS, TOTAL_DAYS
    )
    won = bool(
        float(metrics["net_return_pct"]) > float(teacher_metrics["net_return_pct"])
        and float(p5_capture["duration_weighted_capture"])
        > float(v7_capture["duration_weighted_capture"])
        and float(metrics["chronological_1h_mdd_pct"])
        >= float(teacher_metrics["chronological_1h_mdd_pct"]) - 2.0
    )
    status = "EDUCATIONAL_REUSED_HOLDOUT_WIN" if won else "V7_1_NOT_BEATEN"
    summary = {
        "family": FAMILY,
        "experiment": EXPERIMENT,
        "run_date": RUN_DATE,
        "stage": "validate",
        "status": status,
        "research_status": ["diagnostic-only", "reused-holdout", "not promoted", "not live-ready"],
        "boundary": {
            "start": pd.Timestamp(context.book.ts[TRAIN_DAYS]),
            "last_feature_day": pd.Timestamp(context.book.ts[TOTAL_DAYS - 1]),
            "terminal": pd.Timestamp(context.book.terminal_ts),
            "days": TOTAL_DAYS - TRAIN_DAYS,
            "holdout_classification": "reused_holdout_not_clean_oos",
        },
        "frozen_model": {
            "selected_feature_block": manifest["selected_feature_block"],
            "selected_features": selected_features,
            "policy": manifest["policy"],
            "training_rows": len(candidate_rows(train_frame, 0, TRAIN_DAYS)),
        },
        "classification": classification,
        "p5": metrics,
        "v7_1": teacher_metrics,
        "p5_episode_capture": p5_capture,
        "v7_1_episode_capture": v7_capture,
        "v7_1_beaten": won,
        "recent_slices_flat_start": slices,
    }
    paths = {
        "predictions": ARTIFACT_DIR / f"{PREFIX}_validation_predictions.csv",
        "decisions": ARTIFACT_DIR / f"{PREFIX}_validation_decisions.csv",
        "trades": ARTIFACT_DIR / f"{PREFIX}_validation_trades.csv",
        "teacher_trades": ARTIFACT_DIR / f"{PREFIX}_validation_v7_1_trades.csv",
        "episode_capture": ARTIFACT_DIR / f"{PREFIX}_validation_episode_capture.csv",
        "summary": ARTIFACT_DIR / f"{PREFIX}_validation_summary.json",
    }
    write_csv(paths["predictions"], predictions)
    write_csv(paths["decisions"], decisions)
    write_csv(paths["trades"], trades)
    write_csv(paths["teacher_trades"], teacher_trades)
    write_csv(
        paths["episode_capture"],
        pd.concat(
            [p5_episodes.assign(strategy="P5"), v7_episodes.assign(strategy="V7.1")],
            ignore_index=True,
        ),
    )
    write_json(paths["summary"], summary)
    for path in paths.values():
        write_sidecar(path)
    return summary


def self_test() -> dict[str, Any]:
    rows = pd.DataFrame(
        {
            "index": [0, 1, 2, 3],
            "ts": pd.date_range("2026-01-01", periods=4, tz="UTC").astype(str),
            "root_side": [1, 1, -1, -1],
            "root_index": [0, 0, 2, 2],
        }
    )
    context = SimpleNamespace(
        book=SimpleNamespace(
            count=4,
            ts=pd.date_range("2026-01-01", periods=4, tz="UTC"),
            open=np.asarray([100.0, 101.0, 102.0, 99.0]),
            terminal_ts=pd.Timestamp("2026-01-05", tz="UTC"),
            quality={"terminal_open": 98.0},
        )
    )
    probabilities = pd.DataFrame(
        {"index": [0, 1, 2, 3], "probability": [0.8, 0.8, 0.8, 0.8]}
    )
    trades, decisions = apply_policy(context, rows, probabilities, 0, 4)
    assert len(trades) == 2
    assert trades[0]["exit_reason"] == "direct_reversal"
    assert trades[0]["exit_ts"] == trades[1]["entry_ts"]
    assert decisions.iloc[2]["action"] == "REVERSE_TO_SHORT"
    return {"status": "PASS", "trades": len(trades), "direct_reversals": 1}


def main() -> int:
    args = parse_args()
    if args.self_test:
        print(json.dumps(self_test(), ensure_ascii=False, indent=2))
        return 0
    result = develop() if args.stage == "develop" else validate()
    print(json.dumps(sanitize(result), ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
