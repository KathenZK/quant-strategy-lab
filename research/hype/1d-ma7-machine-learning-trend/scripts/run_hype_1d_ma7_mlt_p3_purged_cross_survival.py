from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-machine-learning-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
P2_SCRIPT = FAMILY_DIR / "scripts/run_hype_1d_ma7_mlt_p2_episode_policy.py"
CONTRACT = (
    FAMILY_DIR
    / "specs/hype-1d-ma7-mlt-p3-purged-cross-survival-contract-2026-08-27.md"
)

FAMILY = "HYPE-1D-MA7-Machine-Learning-Trend"
EXPERIMENT = "P3_PURGED_CROSS_SURVIVAL"
RUN_DATE = "2026-08-27"
TRAIN_DAYS = 365
SELECTION_DAYS = 285
FEE = 0.001
SLIPPAGE = 0.0004
COST_PER_FILL = FEE + SLIPPAGE
MODEL_C = 0.05
ENTRY_THRESHOLD = 0.50
SURVIVAL_THRESHOLD = 0.50
REVERSAL_MARGIN = 0.10
ENTRY_HORIZON = 21
ENTRY_TARGET_ATR = 2.0
ENTRY_STOP_ATR = 1.5
SURVIVAL_HORIZON = 14
SURVIVAL_TARGET_ATR = 1.0
SURVIVAL_STOP_ATR = 1.0
MAX_HOLD_DAYS = 30
INITIAL_OOF_GROUPS = 24
OOF_FOLDS = 3
RANDOM_STATE = 20260827

ENTRY_BLOCKS: dict[str, list[str]] = {
    "GEOMETRY_4": [
        "cross_before_atr",
        "cross_after_atr",
        "aligned_body_atr",
        "aligned_close_location",
    ],
    "GEOMETRY_SLOPE_8": [
        "cross_before_atr",
        "cross_after_atr",
        "aligned_body_atr",
        "aligned_close_location",
        "aligned_slope1_atr",
        "aligned_slope3_atr_per_day",
        "aligned_slope_acceleration",
        "slope_turn_aligned",
    ],
    "GEOMETRY_SLOPE_PATH_12": [
        "cross_before_atr",
        "cross_after_atr",
        "aligned_body_atr",
        "aligned_close_location",
        "aligned_slope1_atr",
        "aligned_slope3_atr_per_day",
        "aligned_slope_acceleration",
        "slope_turn_aligned",
        "pre_side_streak_fraction",
        "aligned_prior_return_3d",
        "er7",
        "raw_cross_count14",
    ],
    "ALL_16": [
        "cross_before_atr",
        "cross_after_atr",
        "aligned_body_atr",
        "aligned_close_location",
        "aligned_slope1_atr",
        "aligned_slope3_atr_per_day",
        "aligned_slope_acceleration",
        "slope_turn_aligned",
        "pre_side_streak_fraction",
        "aligned_prior_return_3d",
        "er7",
        "raw_cross_count14",
        "range_atr",
        "volume_z7",
        "atr7_pct",
        "atr7_ratio14",
    ],
}

SURVIVAL_BLOCKS: dict[str, list[str]] = {
    "SURVIVAL_CORE_6": [
        "aligned_ma_gap_atr",
        "aligned_slope1_atr",
        "aligned_slope3_atr_per_day",
        "hold_age_fraction",
        "unrealized_atr",
        "giveback_atr",
    ],
    "SURVIVAL_PATH_11": [
        "aligned_ma_gap_atr",
        "aligned_slope1_atr",
        "aligned_slope3_atr_per_day",
        "hold_age_fraction",
        "unrealized_atr",
        "giveback_atr",
        "aligned_slope_acceleration",
        "aligned_return_3d",
        "mfe_atr",
        "mae_atr",
        "crossed_back_ma7",
    ],
    "SURVIVAL_ALL_15": [
        "aligned_ma_gap_atr",
        "aligned_slope1_atr",
        "aligned_slope3_atr_per_day",
        "hold_age_fraction",
        "unrealized_atr",
        "giveback_atr",
        "aligned_slope_acceleration",
        "aligned_return_3d",
        "mfe_atr",
        "mae_atr",
        "crossed_back_ma7",
        "aligned_rsi6",
        "er7",
        "atr7_pct",
        "raw_cross_count14",
    ],
}


@dataclass(slots=True)
class ModelBundle:
    model: Any
    features: list[str]
    row_count: int
    group_count: int
    positive_rate: float


@dataclass(slots=True)
class BacktestResult:
    metrics: dict[str, Any]
    trades: list[dict[str, Any]]
    path: list[dict[str, Any]]
    decisions: list[dict[str, Any]]


class ConstantProbabilityModel:
    def __init__(self, probability: float):
        self.probability = float(probability)

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        p = np.full(len(frame), self.probability, dtype=float)
        return np.column_stack([1.0 - p, p])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"Run {EXPERIMENT}.")
    parser.add_argument("--stage", choices=("develop", "validate"), default="develop")
    parser.add_argument("--run-date", default=RUN_DATE)
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


def load_dependencies() -> tuple[Any, Any, Any, Any]:
    p2 = load_module(P2_SCRIPT, "hype_1d_ma7_mlt_p3_p2")
    p1, p0, market, _ = p2.load_context()
    return p2, p1, p0, market


def slice_market(market: Any, daily_rows: int) -> Any:
    output = copy.copy(market)
    output.daily = market.daily.iloc[:daily_rows].copy()
    output.open_ts = market.open_ts[: daily_rows + 1].copy()
    output.opens = market.opens[: daily_rows + 1].copy()
    output.funding_by_open = market.funding_by_open[: daily_rows + 1].copy()
    return output


def build_state(p1: Any, p0: Any, market: Any) -> pd.DataFrame:
    state = p1.build_state_frame(p0, market)
    raw_cross = np.zeros(len(state), dtype=int)
    for index in range(1, len(state)):
        prior = state.iloc[index - 1]
        current = state.iloc[index]
        if prior["close"] <= prior["ma7"] and current["close"] > current["ma7"]:
            raw_cross[index] = 1
        elif prior["close"] >= prior["ma7"] and current["close"] < current["ma7"]:
            raw_cross[index] = -1
    state["raw_cross"] = raw_cross
    state["raw_cross_count14"] = (
        pd.Series(np.abs(raw_cross), index=state.index).rolling(14, min_periods=1).sum()
    )
    state["slope_acceleration"] = state["slope1_atr"].diff()
    state["atr7_ratio14"] = state["atr7"] / state["atr7"].rolling(14, min_periods=7).mean()
    return state


def finite(row: dict[str, Any], features: list[str]) -> bool:
    return all(np.isfinite(float(row[name])) for name in features)


def pre_side_streak(state: pd.DataFrame, index: int, side: int) -> int:
    count = 0
    for cursor in range(index - 1, max(-1, index - 11), -1):
        row = state.iloc[cursor]
        if side * (float(row["close"]) - float(row["ma7"])) <= 0.0:
            count += 1
        else:
            break
    return count


def entry_feature_row(state: pd.DataFrame, index: int, side: int) -> dict[str, float]:
    current = state.iloc[index]
    prior = state.iloc[index - 1]
    atr = float(current["atr7"])
    prior_atr = float(prior["atr7"])
    current_aligned_slope = side * float(current["slope1_atr"])
    prior_aligned_slope = side * float(prior["slope1_atr"])
    return {
        "cross_before_atr": -side * (float(prior["close"]) - float(prior["ma7"])) / prior_atr,
        "cross_after_atr": side * (float(current["close"]) - float(current["ma7"])) / atr,
        "aligned_body_atr": side * (float(current["close"]) - float(current["open"])) / atr,
        "aligned_close_location": (
            float(current["close_location"])
            if side > 0
            else 1.0 - float(current["close_location"])
        ),
        "aligned_slope1_atr": current_aligned_slope,
        "aligned_slope3_atr_per_day": side * float(current["slope3_atr_per_day"]),
        "aligned_slope_acceleration": side * float(current["slope_acceleration"]),
        "slope_turn_aligned": float(current_aligned_slope > 0.0 and prior_aligned_slope <= 0.0),
        "pre_side_streak_fraction": pre_side_streak(state, index, side) / 10.0,
        "aligned_prior_return_3d": side * float(prior["return_3d"]),
        "er7": float(current["er7"]),
        "raw_cross_count14": float(current["raw_cross_count14"]),
        "range_atr": (float(current["high"]) - float(current["low"])) / atr,
        "volume_z7": float(current["volume_z7"]),
        "atr7_pct": float(current["atr7_pct"]),
        "atr7_ratio14": float(current["atr7_ratio14"]),
    }


def build_events(state: pd.DataFrame, market: Any) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    all_features = ENTRY_BLOCKS["ALL_16"]
    event_number = 0
    for index in np.flatnonzero(state["raw_cross"].to_numpy()):
        side = int(state.iloc[index]["raw_cross"])
        features = entry_feature_row(state, int(index), side)
        if not finite(features, all_features):
            continue
        event_number += 1
        rows.append(
            {
                "event_id": f"P3X{event_number:03d}",
                "decision_index": int(index),
                "decision_ts": pd.Timestamp(state.iloc[index]["ts"]).isoformat(),
                "entry_open_index": int(index) + 1,
                "entry_ts": pd.Timestamp(market.open_ts[int(index) + 1]).isoformat(),
                "side_value": side,
                "side": "long" if side > 0 else "short",
                "entry_atr": float(state.iloc[index]["atr7"]),
                **features,
            }
        )
    return pd.DataFrame(rows)


def label_entry_events(events: pd.DataFrame, market: Any, max_known_open: int, p2: Any) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for event in events.to_dict("records"):
        entry = int(event["entry_open_index"])
        label_end = entry + ENTRY_HORIZON
        if label_end > max_known_open:
            continue
        label, mfe, mae = p2.first_hit_label(
            market,
            base_open_index=entry,
            side=int(event["side_value"]),
            atr=float(event["entry_atr"]),
            horizon=ENTRY_HORIZON,
            target_atr=ENTRY_TARGET_ATR,
            stop_atr=ENTRY_STOP_ATR,
            max_open_index=max_known_open,
        )
        rows.append(
            {
                **event,
                "trend_success": label,
                "entry_label_end_index": label_end,
                "entry_mfe_21_atr": mfe,
                "entry_mae_21_atr": mae,
            }
        )
    return pd.DataFrame(rows)


def survival_feature_row(
    state: pd.DataFrame,
    market: Any,
    *,
    entry_open_index: int,
    decision_index: int,
    side: int,
    entry_atr: float,
) -> dict[str, float]:
    current = state.iloc[decision_index]
    entry_price = float(market.opens[entry_open_index])
    held = state.iloc[entry_open_index : decision_index + 1]
    if side > 0:
        mfe = (float(held["high"].max()) - entry_price) / entry_atr
        adverse = (float(held["low"].min()) - entry_price) / entry_atr
    else:
        mfe = (entry_price - float(held["low"].min())) / entry_atr
        adverse = (entry_price - float(held["high"].max())) / entry_atr
    mfe = max(0.0, mfe)
    mae = max(0.0, -adverse)
    unrealized = side * (float(current["close"]) - entry_price) / entry_atr
    return {
        "aligned_ma_gap_atr": side * (float(current["close"]) - float(current["ma7"])) / float(current["atr7"]),
        "aligned_slope1_atr": side * float(current["slope1_atr"]),
        "aligned_slope3_atr_per_day": side * float(current["slope3_atr_per_day"]),
        "hold_age_fraction": (decision_index - entry_open_index + 1) / MAX_HOLD_DAYS,
        "unrealized_atr": unrealized,
        "giveback_atr": max(0.0, mfe - unrealized),
        "aligned_slope_acceleration": side * float(current["slope_acceleration"]),
        "aligned_return_3d": side * float(current["return_3d"]),
        "mfe_atr": mfe,
        "mae_atr": mae,
        "crossed_back_ma7": float(side * (float(current["close"]) - float(current["ma7"])) <= 0.0),
        "aligned_rsi6": side * (float(current["rsi6"]) - 50.0) / 50.0,
        "er7": float(current["er7"]),
        "atr7_pct": float(current["atr7_pct"]),
        "raw_cross_count14": float(current["raw_cross_count14"]),
    }


def build_survival_rows(
    events: pd.DataFrame,
    state: pd.DataFrame,
    market: Any,
    max_known_open: int,
    p2: Any,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    all_features = SURVIVAL_BLOCKS["SURVIVAL_ALL_15"]
    for event in events.to_dict("records"):
        entry = int(event["entry_open_index"])
        for decision_index in range(entry, entry + MAX_HOLD_DAYS):
            base_open = decision_index + 1
            label_end = base_open + SURVIVAL_HORIZON
            if decision_index >= len(state) or label_end > max_known_open:
                break
            features = survival_feature_row(
                state,
                market,
                entry_open_index=entry,
                decision_index=decision_index,
                side=int(event["side_value"]),
                entry_atr=float(event["entry_atr"]),
            )
            if not finite(features, all_features):
                continue
            label, future_mfe, future_mae = p2.first_hit_label(
                market,
                base_open_index=base_open,
                side=int(event["side_value"]),
                atr=float(state.iloc[decision_index]["atr7"]),
                horizon=SURVIVAL_HORIZON,
                target_atr=SURVIVAL_TARGET_ATR,
                stop_atr=SURVIVAL_STOP_ATR,
                max_open_index=max_known_open,
            )
            rows.append(
                {
                    "event_id": event["event_id"],
                    "cross_decision_index": int(event["decision_index"]),
                    "entry_open_index": entry,
                    "decision_index": decision_index,
                    "decision_ts": pd.Timestamp(state.iloc[decision_index]["ts"]).isoformat(),
                    "side_value": int(event["side_value"]),
                    "survival_label": label,
                    "survival_label_end_index": label_end,
                    "future_mfe_14_atr": future_mfe,
                    "future_mae_14_atr": future_mae,
                    **features,
                }
            )
    output = pd.DataFrame(rows)
    if len(output):
        counts = output.groupby("cross_decision_index")["cross_decision_index"].transform("size")
        output["group_weight"] = 1.0 / counts.astype(float)
    return output


def row_weights(frame: pd.DataFrame, group_column: str) -> np.ndarray:
    counts = frame.groupby(group_column)[group_column].transform("size").astype(float)
    return (1.0 / counts).to_numpy()


def fit_model(frame: pd.DataFrame, features: list[str], target: str, group_column: str) -> ModelBundle:
    y = frame[target].astype(int)
    positive_rate = float(np.average(y, weights=row_weights(frame, group_column)))
    if y.nunique() < 2:
        model: Any = ConstantProbabilityModel(positive_rate)
    else:
        model = Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                (
                    "model",
                    LogisticRegression(
                        C=MODEL_C,
                        penalty="l2",
                        class_weight="balanced",
                        random_state=RANDOM_STATE,
                        max_iter=2000,
                    ),
                ),
            ]
        )
        model.fit(
            frame[features],
            y,
            model__sample_weight=row_weights(frame, group_column),
        )
    return ModelBundle(
        model=model,
        features=features,
        row_count=len(frame),
        group_count=int(frame[group_column].nunique()),
        positive_rate=positive_rate,
    )


def probability(bundle: ModelBundle, row: dict[str, Any]) -> float:
    frame = pd.DataFrame([{name: float(row[name]) for name in bundle.features}])
    return float(bundle.model.predict_proba(frame)[0, 1])


def metric_bundle(y: np.ndarray, p: np.ndarray, weights: np.ndarray) -> dict[str, Any]:
    has_two = len(np.unique(y)) == 2
    return {
        "auc": float(roc_auc_score(y, p, sample_weight=weights)) if has_two else None,
        "brier": float(brier_score_loss(y, p, sample_weight=weights)),
        "accuracy_at_0_5": float(accuracy_score(y, p >= 0.5, sample_weight=weights)),
        "positive_rate": float(np.average(y, weights=weights)),
        "predicted_positive_rate": float(np.average(p >= 0.5, weights=weights)),
    }


def expanding_purged_oof(
    frame: pd.DataFrame,
    features: list[str],
    target: str,
    group_column: str,
    label_end_column: str,
) -> dict[str, Any]:
    groups = np.asarray(sorted(frame[group_column].unique()), dtype=int)
    if len(groups) <= INITIAL_OOF_GROUPS:
        return {"available": False, "reason": "insufficient_groups", "groups": len(groups)}
    test_folds = [part for part in np.array_split(groups[INITIAL_OOF_GROUPS:], OOF_FOLDS) if len(part)]
    predictions: list[float] = []
    actuals: list[int] = []
    weights_out: list[float] = []
    constants: list[float] = []
    folds: list[dict[str, Any]] = []
    for fold_number, test_groups in enumerate(test_folds, start=1):
        first_test = int(test_groups[0])
        train = frame.loc[frame[label_end_column] < first_test].copy()
        test = frame.loc[frame[group_column].isin(test_groups)].copy()
        if train.empty or test.empty or train[target].nunique() < 2:
            continue
        bundle = fit_model(train, features, target, group_column)
        p = bundle.model.predict_proba(test[features])[:, 1]
        y = test[target].astype(int).to_numpy()
        w = row_weights(test, group_column)
        train_rate = float(np.average(train[target].astype(int), weights=row_weights(train, group_column)))
        predictions.extend(p.tolist())
        actuals.extend(y.tolist())
        weights_out.extend(w.tolist())
        constants.extend([train_rate] * len(test))
        fold_metrics = metric_bundle(y, p, w)
        folds.append(
            {
                "fold": fold_number,
                "train_groups": int(train[group_column].nunique()),
                "test_groups": int(test[group_column].nunique()),
                "train_rows": len(train),
                "test_rows": len(test),
                "first_test_group": first_test,
                "last_test_group": int(test_groups[-1]),
                **fold_metrics,
            }
        )
    if not predictions:
        return {"available": False, "reason": "no_valid_folds", "groups": len(groups)}
    y_all = np.asarray(actuals, dtype=int)
    p_all = np.asarray(predictions, dtype=float)
    w_all = np.asarray(weights_out, dtype=float)
    result = metric_bundle(y_all, p_all, w_all)
    result.update(
        {
            "available": True,
            "all_groups": len(groups),
            "oof_groups": int(sum(fold["test_groups"] for fold in folds)),
            "oof_rows": len(y_all),
            "constant_brier": float(
                brier_score_loss(y_all, np.asarray(constants), sample_weight=w_all)
            ),
            "folds": folds,
        }
    )
    return result


def evaluate_blocks(
    frame: pd.DataFrame,
    blocks: dict[str, list[str]],
    target: str,
    group_column: str,
    label_end_column: str,
) -> dict[str, dict[str, Any]]:
    return {
        name: {
            "feature_count": len(features),
            "features": features,
            **expanding_purged_oof(
                frame,
                features,
                target,
                group_column,
                label_end_column,
            ),
        }
        for name, features in blocks.items()
    }


def choose_block(results: dict[str, dict[str, Any]]) -> str:
    available = [
        (name, result)
        for name, result in results.items()
        if result.get("available") and result.get("auc") is not None
    ]
    if not available:
        raise RuntimeError("no feature block has usable OOF metrics")
    best_auc = max(float(result["auc"]) for _, result in available)
    near_best = [
        (name, result)
        for name, result in available
        if float(result["auc"]) >= best_auc - 0.01
    ]
    near_best.sort(key=lambda item: (int(item[1]["feature_count"]), -float(item[1]["auc"])))
    return near_best[0][0]


def training_gate(entry_oof: dict[str, Any], survival_oof: dict[str, Any]) -> bool:
    def passed(result: dict[str, Any]) -> bool:
        fold_wins = sum(
            fold.get("auc") is not None and float(fold["auc"]) > 0.5
            for fold in result.get("folds", [])
        )
        return bool(result.get("auc") is not None and float(result["auc"]) > 0.5 and fold_wins >= 2)

    return passed(entry_oof) and passed(survival_oof)


def coefficients(bundle: ModelBundle) -> list[dict[str, Any]]:
    if not isinstance(bundle.model, Pipeline):
        return [{"feature": "constant", "coefficient": 0.0}]
    values = bundle.model.named_steps["model"].coef_[0]
    return sorted(
        [
            {"feature": name, "coefficient": float(value)}
            for name, value in zip(bundle.features, values, strict=True)
        ],
        key=lambda row: abs(row["coefficient"]),
        reverse=True,
    )


def model_in_sample(
    frame: pd.DataFrame,
    bundle: ModelBundle,
    target: str,
    group_column: str,
) -> dict[str, Any]:
    y = frame[target].astype(int).to_numpy()
    p = bundle.model.predict_proba(frame[bundle.features])[:, 1]
    weights = row_weights(frame, group_column)
    return {
        "rows": len(frame),
        "groups": int(frame[group_column].nunique()),
        **metric_bundle(y, p, weights),
    }


def backtest_policy(
    state: pd.DataFrame,
    market: Any,
    candidates: pd.DataFrame,
    entry_model: ModelBundle,
    survival_model: ModelBundle,
    p2: Any,
    *,
    strategy: str,
    start_open: int,
    terminal_open: int,
) -> BacktestResult:
    candidate_map = {
        int(index): group.to_dict("records")
        for index, group in candidates.groupby("decision_index", sort=False)
    }
    equity = 1.0
    peak = 1.0
    mdd = 0.0
    side = 0
    entry_index = -1
    entry_equity = math.nan
    entry_price = math.nan
    entry_atr = math.nan
    entry_event: dict[str, Any] | None = None
    entry_probability: float | None = None
    pending: dict[str, Any] | None = None
    used_events: set[str] = set()
    total_cost = 0.0
    total_funding = 0.0
    exposure_days = 0
    reversal_count = 0
    trades: list[dict[str, Any]] = []
    path: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    previous_open = float(market.opens[start_open])

    def close_trade(open_index: int, info: dict[str, Any]) -> None:
        nonlocal equity, side, entry_index, entry_equity, entry_price, entry_atr
        nonlocal entry_event, entry_probability, total_cost
        exit_cost = equity * COST_PER_FILL
        equity -= exit_cost
        total_cost += exit_cost
        stats = p2.trade_path_stats(
            state,
            market,
            entry_open_index=entry_index,
            exit_open_index=open_index,
            side=side,
            entry_atr=entry_atr,
        )
        trades.append(
            {
                "strategy": strategy,
                "event_id": entry_event["event_id"] if entry_event else None,
                "entry_signal_ts": entry_event["decision_ts"] if entry_event else None,
                "entry_ts": pd.Timestamp(market.open_ts[entry_index]).isoformat(),
                "exit_ts": pd.Timestamp(market.open_ts[open_index]).isoformat(),
                "side": "long" if side > 0 else "short",
                "side_value": side,
                "entry_price": entry_price,
                "exit_price": float(market.opens[open_index]),
                "entry_probability": entry_probability,
                "exit_survival_probability": info.get("survival_probability"),
                "opposite_entry_probability": info.get("opposite_probability"),
                "bars_held": open_index - entry_index,
                "exit_reason": info["reason"],
                "net_return": equity / entry_equity - 1.0,
                **stats,
            }
        )
        side = 0
        entry_index = -1
        entry_equity = math.nan
        entry_price = math.nan
        entry_atr = math.nan
        entry_event = None
        entry_probability = None

    def open_trade(open_index: int, event: dict[str, Any], p_entry: float | None) -> None:
        nonlocal equity, side, entry_index, entry_equity, entry_price, entry_atr
        nonlocal entry_event, entry_probability, total_cost
        entry_equity = equity
        cost = equity * COST_PER_FILL
        equity -= cost
        total_cost += cost
        side = int(event["side_value"])
        entry_index = open_index
        entry_price = float(market.opens[open_index])
        entry_atr = float(event["entry_atr"])
        entry_event = event
        entry_probability = p_entry
        used_events.add(str(event["event_id"]))

    for open_index in range(start_open, terminal_open + 1):
        current_open = float(market.opens[open_index])
        current_ts = pd.Timestamp(market.open_ts[open_index])
        if open_index > start_open and side != 0:
            price_return = current_open / previous_open - 1.0
            equity *= 1.0 + side * price_return
            funding_amount = equity * side * float(market.funding_by_open[open_index])
            equity -= funding_amount
            total_funding += funding_amount
            exposure_days += 1

        action = pending
        pending = None
        suppress_event: str | None = None
        if side != 0 and open_index == terminal_open:
            action = action or {"target": 0, "reason": "terminal_mark"}
        if side != 0 and action is not None:
            old_side = side
            target = int(action["target"])
            close_trade(open_index, action)
            suppress_event = action.get("suppress_event")
            if target != 0 and open_index < terminal_open:
                reverse_event = action["event"]
                open_trade(open_index, reverse_event, float(action["opposite_probability"]))
                reversal_count += int(target == -old_side)

        prior_decision_index = open_index - 1
        prior_candidates = candidate_map.get(prior_decision_index, [])
        if side == 0 and open_index < terminal_open and prior_candidates:
            event = prior_candidates[0]
            if str(event["event_id"]) not in used_events and str(event["event_id"]) != suppress_event:
                p_entry = None if strategy == "RAW_CROSS_H7" else probability(entry_model, event)
                accepted = p_entry is None or p_entry >= ENTRY_THRESHOLD
                decisions.append(
                    {
                        "strategy": strategy,
                        "kind": "entry",
                        "decision_ts": event["decision_ts"],
                        "action_ts": current_ts.isoformat(),
                        "event_id": event["event_id"],
                        "side": event["side"],
                        "probability": p_entry,
                        "accepted": accepted,
                    }
                )
                if accepted:
                    open_trade(open_index, event, p_entry)

        if side != 0 and open_index < terminal_open and entry_event is not None:
            hold_days = open_index - entry_index + 1
            if strategy == "RAW_CROSS_H7":
                if hold_days >= 7:
                    pending = {"target": 0, "reason": "fixed_7d"}
            else:
                features = survival_feature_row(
                    state,
                    market,
                    entry_open_index=entry_index,
                    decision_index=open_index,
                    side=side,
                    entry_atr=entry_atr,
                )
                p_survival = probability(survival_model, features)
                opposite = next(
                    (
                        event
                        for event in candidate_map.get(open_index, [])
                        if int(event["side_value"]) == -side
                        and str(event["event_id"]) not in used_events
                    ),
                    None,
                )
                p_opposite = probability(entry_model, opposite) if opposite is not None else None
                reversal_ready = bool(
                    opposite is not None
                    and p_opposite is not None
                    and p_opposite >= ENTRY_THRESHOLD
                    and p_opposite >= p_survival + REVERSAL_MARGIN
                )
                reason: str | None = None
                target = side
                if hold_days >= MAX_HOLD_DAYS:
                    reason, target = "max_hold_30d", 0
                elif reversal_ready and strategy == "P3_FULL_POLICY":
                    reason, target = "direct_reversal", -side
                elif reversal_ready and strategy == "P3_NO_REVERSAL":
                    reason, target = "opposite_cross_exit", 0
                elif p_survival < SURVIVAL_THRESHOLD:
                    reason, target = "survival_exit", 0
                decisions.append(
                    {
                        "strategy": strategy,
                        "kind": "hold",
                        "decision_ts": pd.Timestamp(state.iloc[open_index]["ts"]).isoformat(),
                        "action_ts": pd.Timestamp(market.open_ts[open_index + 1]).isoformat(),
                        "event_id": entry_event["event_id"],
                        "side": "long" if side > 0 else "short",
                        "survival_probability": p_survival,
                        "opposite_event_id": opposite["event_id"] if opposite else None,
                        "opposite_probability": p_opposite,
                        "action": reason or "hold",
                    }
                )
                if reason is not None:
                    pending = {
                        "target": target,
                        "reason": reason,
                        "survival_probability": p_survival,
                        "opposite_probability": p_opposite,
                        "event": opposite,
                        "suppress_event": opposite["event_id"] if opposite is not None and target == 0 else None,
                    }

        peak = max(peak, equity)
        mdd = min(mdd, equity / peak - 1.0)
        path.append(
            {
                "ts": current_ts.isoformat(),
                "open": current_open,
                "equity": equity,
                "position": side,
            }
        )
        previous_open = current_open

    trade_returns = np.asarray([trade["net_return"] for trade in trades], dtype=float)
    capture_values = [trade["capture_ratio"] for trade in trades if trade["gross_favorable_return"] > 0]
    metrics = {
        "total_return": float(equity - 1.0),
        "max_drawdown": float(mdd),
        "profit_factor": p2._profit_factor(trades),
        "win_rate": float(np.mean(trade_returns > 0.0)) if len(trade_returns) else 0.0,
        "trade_count": len(trades),
        "long_count": sum(int(trade["side_value"]) > 0 for trade in trades),
        "short_count": sum(int(trade["side_value"]) < 0 for trade in trades),
        "reversal_count": reversal_count,
        "exposure_days": exposure_days,
        "total_cost": float(total_cost),
        "total_funding": float(total_funding),
        "mean_capture_ratio_profitable": float(np.mean(capture_values)) if capture_values else 0.0,
        "mean_remaining_mfe_14_atr": float(np.mean([trade["remaining_mfe_14_atr"] for trade in trades])) if trades else 0.0,
        "final_equity": float(equity),
    }
    return BacktestResult(metrics=metrics, trades=trades, path=path, decisions=decisions)


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_hashed(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.with_suffix(path.suffix + ".sha256").write_text(
        f"{hash_file(path)}  {path.name}\n", encoding="utf-8"
    )


def json_ready(value: Any, p2: Any) -> Any:
    return p2.json_ready(value)


def flatten_block_results(results: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for name, result in results.items():
        rows.append(
            {
                "block": name,
                "feature_count": result.get("feature_count"),
                "available": result.get("available"),
                "auc": result.get("auc"),
                "brier": result.get("brier"),
                "constant_brier": result.get("constant_brier"),
                "accuracy_at_0_5": result.get("accuracy_at_0_5"),
                "positive_rate": result.get("positive_rate"),
                "oof_groups": result.get("oof_groups"),
                "oof_rows": result.get("oof_rows"),
                "fold_auc": json.dumps([fold.get("auc") for fold in result.get("folds", [])]),
                "features": json.dumps(result.get("features", [])),
            }
        )
    return pd.DataFrame(rows)


def develop(run_date: str) -> dict[str, Any]:
    p2, p1, p0, full_market = load_dependencies()
    market = slice_market(full_market, TRAIN_DAYS)
    expected_last = pd.Timestamp("2026-05-30", tz="UTC")
    observed_last = pd.Timestamp(market.daily["ts"].iloc[-1])
    if len(market.daily) != TRAIN_DAYS or observed_last != expected_last:
        raise RuntimeError(f"development boundary failed: {len(market.daily)} / {observed_last}")
    state = build_state(p1, p0, market)
    events = build_events(state, market)
    selection_events = label_entry_events(events, market, SELECTION_DAYS - 1, p2)
    selection_survival = build_survival_rows(
        selection_events,
        state,
        market,
        SELECTION_DAYS - 1,
        p2,
    )
    entry_results = evaluate_blocks(
        selection_events,
        ENTRY_BLOCKS,
        "trend_success",
        "decision_index",
        "entry_label_end_index",
    )
    survival_results = evaluate_blocks(
        selection_survival,
        SURVIVAL_BLOCKS,
        "survival_label",
        "cross_decision_index",
        "survival_label_end_index",
    )
    selected_entry = choose_block(entry_results)
    selected_survival = choose_block(survival_results)
    entry_model = fit_model(
        selection_events,
        ENTRY_BLOCKS[selected_entry],
        "trend_success",
        "decision_index",
    )
    survival_model = fit_model(
        selection_survival,
        SURVIVAL_BLOCKS[selected_survival],
        "survival_label",
        "cross_decision_index",
    )
    internal_candidates = events.loc[
        (events["decision_index"] >= SELECTION_DAYS - 1)
        & (events["decision_index"] < TRAIN_DAYS - 1)
    ].copy()
    internal_results = {
        strategy: backtest_policy(
            state,
            market,
            internal_candidates,
            entry_model,
            survival_model,
            p2,
            strategy=strategy,
            start_open=SELECTION_DAYS,
            terminal_open=TRAIN_DAYS - 1,
        )
        for strategy in ("P3_FULL_POLICY", "P3_NO_REVERSAL", "RAW_CROSS_H7")
    }
    selected_entry_oof = entry_results[selected_entry]
    selected_survival_oof = survival_results[selected_survival]
    gate = training_gate(selected_entry_oof, selected_survival_oof)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"hype_1d_ma7_mlt_p3_purged_cross_survival_{run_date}"
    paths = {
        "development_manifest": ARTIFACT_DIR / f"{stem}_development_manifest.json",
        "entry_blocks": ARTIFACT_DIR / f"{stem}_development_entry_blocks.csv",
        "survival_blocks": ARTIFACT_DIR / f"{stem}_development_survival_blocks.csv",
        "internal_trades": ARTIFACT_DIR / f"{stem}_internal_confirmation_trades.csv",
        "internal_path": ARTIFACT_DIR / f"{stem}_internal_confirmation_path.csv",
        "internal_decisions": ARTIFACT_DIR / f"{stem}_internal_confirmation_decisions.csv",
    }
    flatten_block_results(entry_results).to_csv(paths["entry_blocks"], index=False)
    flatten_block_results(survival_results).to_csv(paths["survival_blocks"], index=False)
    pd.concat(
        [pd.DataFrame(result.trades) for result in internal_results.values()],
        ignore_index=True,
    ).to_csv(paths["internal_trades"], index=False)
    path_frames: list[pd.DataFrame] = []
    decision_frames: list[pd.DataFrame] = []
    for strategy, result in internal_results.items():
        path_frame = pd.DataFrame(result.path)
        path_frame.insert(0, "strategy", strategy)
        path_frames.append(path_frame)
        decision_frames.append(pd.DataFrame(result.decisions))
    pd.concat(path_frames, ignore_index=True).to_csv(paths["internal_path"], index=False)
    pd.concat(decision_frames, ignore_index=True).to_csv(paths["internal_decisions"], index=False)
    manifest = {
        "family": FAMILY,
        "experiment": EXPERIMENT,
        "stage": "develop_train_only",
        "run_date": run_date,
        "contract": str(CONTRACT.relative_to(ROOT)),
        "contract_sha256": hash_file(CONTRACT),
        "data_boundary": {
            "daily_rows": len(market.daily),
            "first_ts": market.daily["ts"].iloc[0],
            "last_ts": market.daily["ts"].iloc[-1],
            "selection_days": SELECTION_DAYS,
            "validation_rows_read_by_feature_pipeline": 0,
        },
        "selection_samples": {
            "entry_events": len(selection_events),
            "entry_positive_rate": float(selection_events["trend_success"].mean()),
            "survival_rows": len(selection_survival),
            "survival_groups": int(selection_survival["cross_decision_index"].nunique()),
            "survival_group_weighted_positive_rate": float(
                np.average(
                    selection_survival["survival_label"],
                    weights=row_weights(selection_survival, "cross_decision_index"),
                )
            ),
        },
        "entry_blocks": entry_results,
        "survival_blocks": survival_results,
        "selected": {
            "entry_block": selected_entry,
            "entry_features": ENTRY_BLOCKS[selected_entry],
            "survival_block": selected_survival,
            "survival_features": SURVIVAL_BLOCKS[selected_survival],
            "entry_threshold": ENTRY_THRESHOLD,
            "survival_threshold": SURVIVAL_THRESHOLD,
            "reversal_margin": REVERSAL_MARGIN,
        },
        "training_gate_pass": gate,
        "training_gate_label": "TRAINING_GATE_PASS" if gate else "TRAINING_GENERALIZATION_FAILED",
        "internal_confirmation": {
            strategy: result.metrics for strategy, result in internal_results.items()
        },
        "artifacts": {key: str(path.relative_to(ROOT)) for key, path in paths.items()},
    }
    write_hashed(
        paths["development_manifest"],
        json.dumps(json_ready(manifest, p2), ensure_ascii=False, indent=2),
    )
    for key, path in paths.items():
        if key != "development_manifest":
            path.with_suffix(path.suffix + ".sha256").write_text(
                f"{hash_file(path)}  {path.name}\n", encoding="utf-8"
            )
    return manifest


def validation_verdict(
    training_gate_pass: bool,
    results: dict[str, BacktestResult],
) -> str:
    if not training_gate_pass:
        return "TRAINING_GENERALIZATION_FAILED"
    full = results["P3_FULL_POLICY"].metrics
    raw = results["RAW_CROSS_H7"].metrics
    if (
        full["total_return"] <= 0.0
        or full["profit_factor"] < 1.0
        or full["total_return"] <= raw["total_return"]
    ):
        return "VALIDATION_FAILED"
    return "EDUCATIONAL_VALIDATION_PASS"


def validate(run_date: str) -> dict[str, Any]:
    p2, p1, p0, market = load_dependencies()
    stem = f"hype_1d_ma7_mlt_p3_purged_cross_survival_{run_date}"
    manifest_path = ARTIFACT_DIR / f"{stem}_development_manifest.json"
    manifest_hash_path = manifest_path.with_suffix(manifest_path.suffix + ".sha256")
    if not manifest_path.exists() or not manifest_hash_path.exists():
        raise RuntimeError("development manifest and hash are required before validation")
    expected_hash = manifest_hash_path.read_text(encoding="utf-8").split()[0]
    if hash_file(manifest_path) != expected_hash:
        raise RuntimeError("development manifest hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["contract_sha256"] != hash_file(CONTRACT):
        raise RuntimeError("contract changed after development freeze")
    selected = manifest["selected"]
    state = build_state(p1, p0, market)
    events = build_events(state, market)
    train_events = label_entry_events(
        events.loc[events["decision_index"] < TRAIN_DAYS - 1].copy(),
        market,
        TRAIN_DAYS - 1,
        p2,
    )
    train_survival = build_survival_rows(
        train_events,
        state,
        market,
        TRAIN_DAYS - 1,
        p2,
    )
    entry_model = fit_model(
        train_events,
        list(selected["entry_features"]),
        "trend_success",
        "decision_index",
    )
    survival_model = fit_model(
        train_survival,
        list(selected["survival_features"]),
        "survival_label",
        "cross_decision_index",
    )
    validation_candidates = events.loc[
        (events["decision_index"] >= TRAIN_DAYS - 1)
        & (events["decision_index"] < len(state) - 1)
    ].copy()
    results = {
        strategy: backtest_policy(
            state,
            market,
            validation_candidates,
            entry_model,
            survival_model,
            p2,
            strategy=strategy,
            start_open=TRAIN_DAYS,
            terminal_open=len(market.daily),
        )
        for strategy in ("P3_FULL_POLICY", "P3_NO_REVERSAL", "RAW_CROSS_H7")
    }
    training_candidates = events.loc[events["decision_index"] < TRAIN_DAYS - 2].copy()
    training_resubstitution = {
        strategy: backtest_policy(
            state.iloc[:TRAIN_DAYS].copy(),
            slice_market(market, TRAIN_DAYS),
            training_candidates,
            entry_model,
            survival_model,
            p2,
            strategy=strategy,
            start_open=0,
            terminal_open=TRAIN_DAYS - 1,
        )
        for strategy in ("P3_FULL_POLICY", "P3_NO_REVERSAL", "RAW_CROSS_H7")
    }
    paths = {
        "summary": ARTIFACT_DIR / f"{stem}_summary.json",
        "model_manifest": ARTIFACT_DIR / f"{stem}_model_manifest.json",
        "training_events": ARTIFACT_DIR / f"{stem}_training_events.csv",
        "training_survival_rows": ARTIFACT_DIR / f"{stem}_training_survival_rows.csv",
        "validation_candidates": ARTIFACT_DIR / f"{stem}_validation_candidates.csv",
        "validation_trades": ARTIFACT_DIR / f"{stem}_validation_trades.csv",
        "validation_path": ARTIFACT_DIR / f"{stem}_validation_path.csv",
        "validation_decisions": ARTIFACT_DIR / f"{stem}_validation_decisions.csv",
    }
    train_events.to_csv(paths["training_events"], index=False)
    train_survival.to_csv(paths["training_survival_rows"], index=False)
    output_candidates = validation_candidates.copy()
    output_candidates["entry_probability"] = [
        probability(entry_model, row) for row in output_candidates.to_dict("records")
    ]
    output_candidates.to_csv(paths["validation_candidates"], index=False)
    pd.concat([pd.DataFrame(result.trades) for result in results.values()], ignore_index=True).to_csv(
        paths["validation_trades"], index=False
    )
    path_frames: list[pd.DataFrame] = []
    decision_frames: list[pd.DataFrame] = []
    for strategy, result in results.items():
        path_frame = pd.DataFrame(result.path)
        path_frame.insert(0, "strategy", strategy)
        path_frames.append(path_frame)
        decision_frames.append(pd.DataFrame(result.decisions))
    pd.concat(path_frames, ignore_index=True).to_csv(paths["validation_path"], index=False)
    pd.concat(decision_frames, ignore_index=True).to_csv(paths["validation_decisions"], index=False)
    model_manifest = {
        "entry": {
            "block": selected["entry_block"],
            "features": entry_model.features,
            "rows": entry_model.row_count,
            "groups": entry_model.group_count,
            "positive_rate": entry_model.positive_rate,
            "in_sample": model_in_sample(train_events, entry_model, "trend_success", "decision_index"),
            "coefficients": coefficients(entry_model),
        },
        "survival": {
            "block": selected["survival_block"],
            "features": survival_model.features,
            "rows": survival_model.row_count,
            "groups": survival_model.group_count,
            "positive_rate": survival_model.positive_rate,
            "in_sample": model_in_sample(
                train_survival,
                survival_model,
                "survival_label",
                "cross_decision_index",
            ),
            "coefficients": coefficients(survival_model),
        },
    }
    write_hashed(
        paths["model_manifest"],
        json.dumps(json_ready(model_manifest, p2), ensure_ascii=False, indent=2),
    )
    verdict = validation_verdict(bool(manifest["training_gate_pass"]), results)
    summary = {
        "family": FAMILY,
        "experiment": EXPERIMENT,
        "run_date": run_date,
        "status": "reused holdout / diagnostic-only / not promoted / not live-ready",
        "verdict": verdict,
        "contract": str(CONTRACT.relative_to(ROOT)),
        "contract_sha256": hash_file(CONTRACT),
        "development_manifest": str(manifest_path.relative_to(ROOT)),
        "development_manifest_sha256": expected_hash,
        "data": {
            "daily_rows": len(market.daily),
            "train_rows": TRAIN_DAYS,
            "train_last_ts": market.daily["ts"].iloc[TRAIN_DAYS - 1],
            "validation_rows": len(market.daily) - TRAIN_DAYS,
            "validation_first_ts": market.daily["ts"].iloc[TRAIN_DAYS],
            "validation_last_ts": market.daily["ts"].iloc[-1],
            "terminal_open_ts": market.open_ts[-1],
        },
        "selected": selected,
        "development_training_gate_pass": manifest["training_gate_pass"],
        "development_training_gate_label": manifest["training_gate_label"],
        "development_selected_oof": {
            "entry": manifest["entry_blocks"][selected["entry_block"]],
            "survival": manifest["survival_blocks"][selected["survival_block"]],
        },
        "development_internal_confirmation": manifest["internal_confirmation"],
        "final_training": model_manifest,
        "training_resubstitution": {
            strategy: result.metrics for strategy, result in training_resubstitution.items()
        },
        "validation": {
            strategy: {**result.metrics, "recent_slices": p2.recent_slices(result.path)}
            for strategy, result in results.items()
        },
        "limitations": [
            "the 81-day window was revealed in P0-P2 and is a reused holdout",
            "only HYPE daily raw-cross events are available, so independent event count is small",
            "daily-close exit has no intraday protective stop",
            "no P3 setting may be changed after this validation run",
        ],
        "artifacts": {key: str(path.relative_to(ROOT)) for key, path in paths.items()},
    }
    write_hashed(
        paths["summary"],
        json.dumps(json_ready(summary, p2), ensure_ascii=False, indent=2),
    )
    for key, path in paths.items():
        if key not in {"summary", "model_manifest"}:
            path.with_suffix(path.suffix + ".sha256").write_text(
                f"{hash_file(path)}  {path.name}\n", encoding="utf-8"
            )
    return summary


def self_test() -> None:
    assert list(map(len, ENTRY_BLOCKS.values())) == [4, 8, 12, 16]
    assert list(map(len, SURVIVAL_BLOCKS.values())) == [6, 11, 15]
    mock = {
        "A": {"available": True, "auc": 0.61, "feature_count": 4},
        "B": {"available": True, "auc": 0.619, "feature_count": 8},
        "C": {"available": True, "auc": 0.63, "feature_count": 12},
    }
    assert choose_block(mock) == "C"
    mock["C"]["auc"] = 0.619
    assert choose_block(mock) == "A"
    frame = pd.DataFrame({"x": [-2.0, -1.0, 1.0, 2.0], "y": [0, 0, 1, 1], "g": [1, 2, 3, 4]})
    bundle = fit_model(frame, ["x"], "y", "g")
    assert probability(bundle, {"x": 2.0}) > probability(bundle, {"x": -2.0})


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        print("self-test PASS")
        return
    output = develop(args.run_date) if args.stage == "develop" else validate(args.run_date)
    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
