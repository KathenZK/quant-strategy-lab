from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass, replace
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from types import SimpleNamespace
import sys
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-machine-learning-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CONTRACT = (
    FAMILY_DIR
    / "specs/hype-1d-ma7-mlt-p4-v7-1-behavior-clone-residual-contract-2026-08-27.md"
)
DIAGNOSTIC = (
    ROOT
    / "research/hype/1d-ma7-asymmetric-body-trend/scripts/"
    "diagnose_hype_1d_ma7_abt_v7_1_oapp_rebound_reset.py"
)

FAMILY = "HYPE-1D-MA7-Machine-Learning-Trend"
EXPERIMENT = "P4_V7_1_BEHAVIOR_CLONE_RESIDUAL"
RUN_DATE = "2026-08-27"
TRAIN_DAYS = 365
TOTAL_DAYS = 446
TRAIN_TERMINAL = pd.Timestamp("2026-05-31T00:00:00Z")
RESIDUAL_FIT_TRADES = 13
RANDOM_STATE = 20260827
MODEL_C = 0.05
THRESHOLD = 0.50
EXTEND_DAYS = 3
SLIPPAGE = 0.0004

PREFIX = "hype_1d_ma7_mlt_p4_v7_1_behavior_clone_residual_2026-08-27"
MANIFEST_PATH = ARTIFACT_DIR / f"{PREFIX}_development_manifest.json"

CLONE_FEATURES = [
    "ma_gap_atr",
    "slope1_atr",
    "slope2_atr_per_day",
    "slope3_atr_per_day",
    "body_atr",
    "close_location",
    "range_atr",
    "return_1d",
    "return_3d",
    "return_7d",
    "er7",
    "rsi6",
    "atr_pct",
    "cross_count14",
    "position_side",
    "bars_in_position",
    "days_since_exit",
    "unrealized_atr",
    "mfe_atr",
    "mae_atr",
    "giveback_atr",
    "wtl_long_run",
    "wtl_short_run",
    "wtl_rsi_run",
    "pehc_shadow_active",
    "pehc_shadow_age",
    "pehc_pending",
]

ENTRY_FEATURES = [
    "entry_side",
    "entry_aligned_ma_gap_atr",
    "entry_aligned_slope1_atr",
    "entry_aligned_slope2_atr_per_day",
    "entry_aligned_slope3_atr_per_day",
    "entry_aligned_body_atr",
    "entry_aligned_close_location",
    "entry_aligned_rsi6",
    "entry_atr_pct",
    "entry_er7",
    "entry_cross_count14",
    "entry_is_pehc",
    "prior_teacher_net_return",
]

EXIT_FEATURES = [
    "exit_side",
    "exit_aligned_ma_gap_atr",
    "exit_aligned_slope1_atr",
    "exit_aligned_slope2_atr_per_day",
    "exit_aligned_slope3_atr_per_day",
    "exit_aligned_return_1d",
    "exit_aligned_return_3d",
    "exit_aligned_body_atr",
    "exit_aligned_rsi6",
    "exit_atr_pct",
    "exit_unrealized_atr",
    "exit_mfe_atr",
    "exit_giveback_atr",
    "exit_bars",
    "reason_long_oapp",
    "reason_ma7_slope",
    "reason_short_rsi",
    "reason_max_hold",
]

ELIGIBLE_EXTENSIONS = {
    "long_mfe_fraction_trail_exit",
    "ma7_slope_exit",
    "short_rsi_take_profit",
    "max_hold",
}
ARM_ORDER = ["EXTEND_ONLY", "FILTER_ONLY", "FILTER_AND_EXTEND"]
ACTION_ORDER = [
    "FLAT",
    "HOLD_LONG",
    "HOLD_SHORT",
    "ENTER_LONG",
    "ENTER_SHORT",
    "EXIT_LONG",
    "EXIT_SHORT",
    "REVERSE_LONG_TO_SHORT",
]
TRANSITIONS = {
    "ENTER_LONG",
    "ENTER_SHORT",
    "EXIT_LONG",
    "EXIT_SHORT",
    "REVERSE_LONG_TO_SHORT",
}


@dataclass(slots=True)
class TeacherRun:
    metrics: dict[str, Any]
    result: Any
    policy: Any


class ConstantProbabilityModel:
    def __init__(self, probability: float):
        self.probability = float(probability)

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        p = np.full(len(frame), self.probability, dtype=float)
        return np.column_stack([1.0 - p, p])


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
    if isinstance(value, np.generic):
        return sanitize(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(sanitize(payload), ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict[str, Any]] | pd.DataFrame) -> None:
    frame = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    frame.to_csv(path, index=False)


def write_sidecar(path: Path) -> None:
    path.with_suffix(path.suffix + ".sha256").write_text(
        f"{sha256(path)}  {path.name}\n", encoding="utf-8"
    )


def load_dependencies(*, train_only: bool = False) -> tuple[Any, Any, Any, Any, Any]:
    diag = load_module(DIAGNOSTIC, "hype_p4_v7_1_diag")
    v6 = diag.load_module(diag.V6_ABLATION_PATH, "hype_p4_v7_1_v6")
    engine = diag.load_module(diag.ENGINE_PATH, "hype_p4_v7_1_engine")
    adapter = diag.load_module(diag.ADAPTER_PATH, "hype_p4_v7_1_adapter")
    if train_only:
        frozen = adapter.load_context()
        original = frozen.original_harness
        original.HOURLY_CUTOFF = TRAIN_TERMINAL
        original.FUNDING_CUTOFF = TRAIN_TERMINAL
        market = original.load_market(0)
        context = replace(
            frozen,
            market=market,
            short_config=replace(frozen.short_config, cooldown_days=3),
        )
        if context.book.count != TRAIN_DAYS:
            raise RuntimeError(
                f"strict training context expected {TRAIN_DAYS} days, got {context.book.count}"
            )
        if pd.Timestamp(context.book.terminal_ts) != TRAIN_TERMINAL:
            raise RuntimeError("strict training context terminal drift")
        if pd.Timestamp(context.market.audit["hourly_end"]) > TRAIN_TERMINAL:
            raise RuntimeError("strict training context read holdout hourly bars")
        if pd.Timestamp(context.market.audit["funding_end"]) > TRAIN_TERMINAL:
            raise RuntimeError("strict training context read holdout funding")
    else:
        _, context = diag.extended_context(adapter)
        if context.book.count != TOTAL_DAYS:
            raise RuntimeError(f"expected {TOTAL_DAYS} days, got {context.book.count}")
    return diag, v6, engine, adapter, context


def run_teacher(diag: Any, v6: Any, engine: Any, context: Any, left: int, right: int) -> TeacherRun:
    metrics, result, policy = diag.run_arm(
        v6,
        engine,
        context,
        "CONTROL",
        window=(left, right),
        slippage=SLIPPAGE,
        include_funding=True,
        retain=True,
    )
    return TeacherRun(metrics=metrics, result=result, policy=policy)


def safe_ratio(numerator: float, denominator: float) -> float:
    if not math.isfinite(numerator) or not math.isfinite(denominator) or denominator == 0:
        return math.nan
    return numerator / denominator


def market_rows(engine: Any, context: Any) -> pd.DataFrame:
    count = context.book.count
    close = np.asarray(context.book.close, dtype=float)
    open_ = np.asarray(context.book.open, dtype=float)
    high = np.asarray(context.book.high, dtype=float)
    low = np.asarray(context.book.low, dtype=float)
    ma7 = np.asarray(context.features.ma7, dtype=float)
    atr7 = np.asarray(context.features.atr7, dtype=float)
    rsi6 = np.asarray(engine._BASE.wilder_rsi6(close), dtype=float)
    rows: list[dict[str, Any]] = []
    crosses: list[int] = []
    for index in range(count):
        atr = atr7[index]
        cross = 0
        if index:
            if close[index - 1] <= ma7[index - 1] and close[index] > ma7[index]:
                cross = 1
            elif close[index - 1] >= ma7[index - 1] and close[index] < ma7[index]:
                cross = -1
        crosses.append(cross)
        movement = np.abs(np.diff(close[max(0, index - 7) : index + 1]))
        er7 = (
            safe_ratio(abs(close[index] - close[index - 7]), float(movement.sum()))
            if index >= 7
            else math.nan
        )
        row = {
            "index": index,
            "ts": pd.Timestamp(context.book.ts[index]).isoformat(),
            "open": open_[index],
            "high": high[index],
            "low": low[index],
            "close": close[index],
            "ma7": ma7[index],
            "atr7": atr,
            "ma_gap_atr": safe_ratio(close[index] - ma7[index], atr),
            "slope1_atr": (
                safe_ratio(ma7[index] - ma7[index - 1], atr) if index >= 1 else math.nan
            ),
            "slope2_atr_per_day": (
                safe_ratio(ma7[index] - ma7[index - 2], 2.0 * atr)
                if index >= 2
                else math.nan
            ),
            "slope3_atr_per_day": (
                safe_ratio(ma7[index] - ma7[index - 3], 3.0 * atr)
                if index >= 3
                else math.nan
            ),
            "body_atr": safe_ratio(close[index] - open_[index], atr),
            "close_location": safe_ratio(close[index] - low[index], high[index] - low[index]),
            "range_atr": safe_ratio(high[index] - low[index], atr),
            "return_1d": (
                safe_ratio(close[index], close[index - 1]) - 1.0 if index >= 1 else math.nan
            ),
            "return_3d": (
                safe_ratio(close[index], close[index - 3]) - 1.0 if index >= 3 else math.nan
            ),
            "return_7d": (
                safe_ratio(close[index], close[index - 7]) - 1.0 if index >= 7 else math.nan
            ),
            "er7": er7,
            "rsi6": rsi6[index],
            "atr_pct": safe_ratio(atr, close[index]),
            "raw_cross": cross,
            "cross_count14": int(sum(abs(value) for value in crosses[max(0, index - 13) :])),
        }
        rows.append(row)
    return pd.DataFrame(rows)


def timestamp_index(context: Any) -> dict[pd.Timestamp, int]:
    return {pd.Timestamp(ts): index for index, ts in enumerate(context.book.ts)}


def trade_for_close_day(trades: list[dict[str, Any]], day: pd.Timestamp) -> dict[str, Any] | None:
    close_of_day = day + pd.Timedelta(days=1)
    for trade in trades:
        if pd.Timestamp(trade["entry_ts"]) < close_of_day <= pd.Timestamp(trade["exit_ts"]):
            return trade
        if pd.Timestamp(trade["entry_ts"]) < close_of_day and pd.Timestamp(trade["exit_ts"]) >= close_of_day:
            return trade
    return None


def teacher_state_rows(
    context: Any,
    market: pd.DataFrame,
    teacher: TeacherRun,
    left: int,
    right: int,
) -> pd.DataFrame:
    paths = {pd.Timestamp(row["ts"]): row for row in teacher.result.raw.path}
    trades = list(teacher.result.raw.trades)
    events = sorted(
        teacher.result.handoff_events,
        key=lambda row: pd.Timestamp(row["ts"]),
    )
    event_cursor = 0
    shadow_active = 0
    shadow_origin = -1
    pending = 0
    last_exit: pd.Timestamp | None = None
    rows: list[dict[str, Any]] = []
    for index in range(left, right):
        day = pd.Timestamp(context.book.ts[index])
        end_of_day = day + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
        while event_cursor < len(events) and pd.Timestamp(events[event_cursor]["ts"]) <= end_of_day:
            event = events[event_cursor]
            kind = str(event["event"])
            if kind == "shadow_start":
                shadow_active = 1
                shadow_origin = int(event.get("origin_index", index))
                pending = 0
            elif kind in {"shadow_cancel_actual_new_long", "shadow_cancel_expired"}:
                shadow_active = 0
                shadow_origin = -1
                pending = 0
            elif kind == "shadow_protective_stop":
                shadow_active = 0
            elif kind == "handoff_delay_scheduled":
                pending = 1
            elif kind in {"handoff_accept", "handoff_reject_filter", "handoff_cancel_actual_position"}:
                pending = 0
                shadow_active = 0
                shadow_origin = -1
            event_cursor += 1

        path = paths.get(day)
        if path is None:
            if index != left:
                raise RuntimeError(f"teacher path missing {day}")
            # A non-zero V7.1 window starts trading on the next UTC open.  The
            # preceding validation decision day is therefore an explicit flat
            # bootstrap state, not a state inherited from the training run.
            path = {
                "action": "hold",
                "position": 0,
                "wtl_long_run": 0,
                "wtl_short_run": 0,
                "wtl_rsi_run": 0,
            }
        position = int(path["position"])
        active = trade_for_close_day(trades, day) if position else None
        entry_index = index
        entry_price = math.nan
        bars = 0
        unrealized = mfe = mae = giveback = 0.0
        if active is not None:
            entry_ts = pd.Timestamp(active["entry_ts"])
            entry_index = max(left, next(
                cursor
                for cursor, ts in enumerate(context.book.ts)
                if pd.Timestamp(ts).normalize() == entry_ts.normalize()
            ))
            entry_price = float(active["entry_price"])
            bars = max(0, index - entry_index + 1)
            atr = float(context.features.atr7[index])
            side = 1 if str(active["side"]) == "long" else -1
            current_close = float(context.book.close[index])
            unrealized = side * (current_close - entry_price) / atr
            if side > 0:
                best = max(float(value) for value in context.book.high[entry_index : index + 1])
                worst = min(float(value) for value in context.book.low[entry_index : index + 1])
                mfe = (best - entry_price) / atr
                mae = (entry_price - worst) / atr
                giveback = (best - current_close) / atr
            else:
                best = min(float(value) for value in context.book.low[entry_index : index + 1])
                worst = max(float(value) for value in context.book.high[entry_index : index + 1])
                mfe = (entry_price - best) / atr
                mae = (worst - entry_price) / atr
                giveback = (current_close - best) / atr

        exited = [pd.Timestamp(row["exit_ts"]) for row in trades if pd.Timestamp(row["exit_ts"]) <= end_of_day]
        if exited:
            last_exit = max(exited)
        days_since_exit = (day.normalize() - last_exit.normalize()).days if last_exit is not None else 999
        base = market.iloc[index].to_dict()
        base.update(
            {
                "teacher_action_today": str(path["action"]),
                "position_side": position,
                "bars_in_position": bars,
                "days_since_exit": days_since_exit,
                "entry_price": entry_price,
                "unrealized_atr": unrealized,
                "mfe_atr": mfe,
                "mae_atr": mae,
                "giveback_atr": giveback,
                "wtl_long_run": int(path["wtl_long_run"]),
                "wtl_short_run": int(path["wtl_short_run"]),
                "wtl_rsi_run": int(path["wtl_rsi_run"]),
                "pehc_shadow_active": shadow_active,
                "pehc_shadow_age": max(0, index - shadow_origin) if shadow_origin >= 0 else 0,
                "pehc_pending": pending,
            }
        )
        rows.append(base)
    return pd.DataFrame(rows)


def action_label(next_path: dict[str, Any], current_position: int) -> str:
    action = str(next_path["action"])
    if action in {"reverse_long_trailing_stop_to_short", "protective_stop_reversal_filter_rejected"}:
        return "SAFETY_DELEGATE"
    if action == "terminal":
        return "TERMINAL"
    if action == "enter_long":
        return "ENTER_LONG"
    if action in {"enter_short", "pehc_handoff_enter_short"}:
        return "ENTER_SHORT"
    if action == "hold":
        position = int(next_path["position"])
        return "HOLD_LONG" if position > 0 else "HOLD_SHORT" if position < 0 else "FLAT"
    if action in ELIGIBLE_EXTENSIONS:
        return "EXIT_LONG" if current_position > 0 else "EXIT_SHORT"
    raise RuntimeError(f"unmapped teacher action: {action}")


def clone_dataset(
    context: Any,
    states: pd.DataFrame,
    teacher: TeacherRun,
    left: int,
    right: int,
) -> pd.DataFrame:
    paths = {pd.Timestamp(row["ts"]): row for row in teacher.result.raw.path}
    rows: list[dict[str, Any]] = []
    states_by_index = {int(row["index"]): row for row in states.to_dict("records")}
    for index in range(left, right - 1):
        current = states_by_index[index]
        next_ts = pd.Timestamp(context.book.ts[index + 1])
        next_path = paths.get(next_ts)
        if next_path is None:
            raise RuntimeError(f"teacher next path missing {next_ts}")
        label = action_label(next_path, int(current["position_side"]))
        if label in {"SAFETY_DELEGATE", "TERMINAL"}:
            continue
        row = dict(current)
        row["target_ts"] = next_ts.isoformat()
        row["target_action"] = label
        row["teacher_raw_action"] = str(next_path["action"])
        rows.append(row)
    return pd.DataFrame(rows)


def clone_model() -> Pipeline:
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            (
                "model",
                ExtraTreesClassifier(
                    n_estimators=500,
                    max_features=None,
                    min_samples_leaf=1,
                    class_weight="balanced",
                    random_state=RANDOM_STATE,
                    n_jobs=-1,
                ),
            ),
        ]
    )


def classification_metrics(actual: list[str], predicted: list[str]) -> dict[str, Any]:
    labels = [label for label in ACTION_ORDER if label in set(actual) | set(predicted)]
    transition_mask = [value in TRANSITIONS for value in actual]
    transition_hits = [
        left == right for left, right, active in zip(actual, predicted, transition_mask, strict=True) if active
    ]
    return {
        "rows": len(actual),
        "accuracy": float(accuracy_score(actual, predicted)),
        "macro_f1": float(f1_score(actual, predicted, labels=labels, average="macro", zero_division=0)),
        "transition_rows": int(sum(transition_mask)),
        "transition_recall": float(np.mean(transition_hits)) if transition_hits else math.nan,
        "labels": labels,
        "confusion_matrix": confusion_matrix(actual, predicted, labels=labels).tolist(),
    }


def fit_clone(frame: pd.DataFrame) -> tuple[Any, pd.DataFrame, dict[str, Any]]:
    model = clone_model()
    model.fit(frame[CLONE_FEATURES], frame["target_action"])
    predictions = model.predict(frame[CLONE_FEATURES])
    output = frame[["index", "ts", "target_ts", "target_action", "teacher_raw_action"]].copy()
    output["predicted_action"] = predictions
    output["correct"] = output["target_action"] == output["predicted_action"]
    metrics = classification_metrics(output["target_action"].tolist(), output["predicted_action"].tolist())
    return model, output, metrics


def clone_expanding_oof(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    first_test = 180
    boundaries = np.linspace(first_test, len(frame), 4, dtype=int)
    rows: list[pd.DataFrame] = []
    for fold in range(3):
        start = int(boundaries[fold])
        end = int(boundaries[fold + 1])
        train = frame.iloc[:start]
        test = frame.iloc[start:end]
        if test.empty:
            continue
        model = clone_model()
        model.fit(train[CLONE_FEATURES], train["target_action"])
        predicted = model.predict(test[CLONE_FEATURES])
        part = test[["index", "ts", "target_ts", "target_action", "teacher_raw_action"]].copy()
        part["fold"] = fold + 1
        part["train_rows"] = len(train)
        part["predicted_action"] = predicted
        part["correct"] = part["target_action"] == part["predicted_action"]
        rows.append(part)
    output = pd.concat(rows, ignore_index=True)
    metrics = classification_metrics(output["target_action"].tolist(), output["predicted_action"].tolist())
    metrics["first_test_row"] = first_test
    metrics["folds"] = 3
    return output, metrics


def signed(value: float, side: int) -> float:
    return side * float(value)


def entry_rows(
    context: Any,
    states: pd.DataFrame,
    teacher: TeacherRun,
    left: int,
    right: int,
) -> pd.DataFrame:
    state_by_index = {int(row["index"]): row for row in states.to_dict("records")}
    day_index = timestamp_index(context)
    path_action = {pd.Timestamp(row["ts"]): str(row["action"]) for row in teacher.result.raw.path}
    prior_return = 0.0
    rows: list[dict[str, Any]] = []
    for order, trade in enumerate(teacher.result.raw.trades):
        entry_ts = pd.Timestamp(trade["entry_ts"])
        entry_day = entry_ts.normalize()
        index = day_index[entry_day]
        decision_index = max(left, index - 1)
        if decision_index >= right:
            continue
        state = state_by_index[decision_index]
        side = 1 if str(trade["side"]) == "long" else -1
        close_location = float(state["close_location"])
        row = {
            "trade_order": order,
            "entry_ts": entry_ts.isoformat(),
            "exit_ts": pd.Timestamp(trade["exit_ts"]).isoformat(),
            "side": str(trade["side"]),
            "teacher_net_return": float(trade["net_return"]),
            "target_positive": int(float(trade["net_return"]) > 0.0),
            "entry_side": side,
            "entry_aligned_ma_gap_atr": signed(state["ma_gap_atr"], side),
            "entry_aligned_slope1_atr": signed(state["slope1_atr"], side),
            "entry_aligned_slope2_atr_per_day": signed(state["slope2_atr_per_day"], side),
            "entry_aligned_slope3_atr_per_day": signed(state["slope3_atr_per_day"], side),
            "entry_aligned_body_atr": signed(state["body_atr"], side),
            "entry_aligned_close_location": close_location if side > 0 else 1.0 - close_location,
            "entry_aligned_rsi6": float(state["rsi6"]) if side > 0 else 100.0 - float(state["rsi6"]),
            "entry_atr_pct": float(state["atr_pct"]),
            "entry_er7": float(state["er7"]),
            "entry_cross_count14": float(state["cross_count14"]),
            "entry_is_pehc": int(path_action.get(entry_day) == "pehc_handoff_enter_short"),
            "prior_teacher_net_return": prior_return,
        }
        rows.append(row)
        prior_return = float(trade["net_return"])
    return pd.DataFrame(rows)


def exit_rows(
    context: Any,
    states: pd.DataFrame,
    teacher: TeacherRun,
    left: int,
    right: int,
) -> pd.DataFrame:
    state_by_index = {int(row["index"]): row for row in states.to_dict("records")}
    day_index = timestamp_index(context)
    rows: list[dict[str, Any]] = []
    for order, trade in enumerate(teacher.result.raw.trades):
        reason = str(trade["exit_reason"])
        exit_ts = pd.Timestamp(trade["exit_ts"])
        if reason not in ELIGIBLE_EXTENSIONS or exit_ts.hour != 0:
            continue
        index = day_index[exit_ts.normalize()]
        decision_index = index - 1
        extension_index = index + EXTEND_DAYS
        if decision_index < left or extension_index >= right:
            continue
        state = state_by_index[decision_index]
        side = 1 if str(trade["side"]) == "long" else -1
        continuation = side * (
            float(context.book.open[extension_index]) / float(trade["exit_price"]) - 1.0
        )
        row = {
            "trade_order": order,
            "entry_ts": pd.Timestamp(trade["entry_ts"]).isoformat(),
            "exit_ts": exit_ts.isoformat(),
            "side": str(trade["side"]),
            "exit_reason": reason,
            "extension_ts": pd.Timestamp(context.book.ts[extension_index]).isoformat(),
            "continuation_return": continuation,
            "target_continue": int(continuation > 0.0),
            "exit_side": side,
            "exit_aligned_ma_gap_atr": signed(state["ma_gap_atr"], side),
            "exit_aligned_slope1_atr": signed(state["slope1_atr"], side),
            "exit_aligned_slope2_atr_per_day": signed(state["slope2_atr_per_day"], side),
            "exit_aligned_slope3_atr_per_day": signed(state["slope3_atr_per_day"], side),
            "exit_aligned_return_1d": signed(state["return_1d"], side),
            "exit_aligned_return_3d": signed(state["return_3d"], side),
            "exit_aligned_body_atr": signed(state["body_atr"], side),
            "exit_aligned_rsi6": float(state["rsi6"]) if side > 0 else 100.0 - float(state["rsi6"]),
            "exit_atr_pct": float(state["atr_pct"]),
            "exit_unrealized_atr": float(state["unrealized_atr"]),
            "exit_mfe_atr": float(state["mfe_atr"]),
            "exit_giveback_atr": float(state["giveback_atr"]),
            "exit_bars": float(trade.get("bars_held", 0)),
            "reason_long_oapp": int(reason.startswith("long_mfe_")),
            "reason_ma7_slope": int(reason == "ma7_slope_exit"),
            "reason_short_rsi": int(reason == "short_rsi_take_profit"),
            "reason_max_hold": int(reason == "max_hold"),
        }
        rows.append(row)
    return pd.DataFrame(rows)


def residual_model(frame: pd.DataFrame, features: list[str], target: str) -> Any:
    values = frame[target].astype(int)
    if values.nunique() < 2:
        return ConstantProbabilityModel(float(values.iloc[0]))
    model = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            (
                "model",
                LogisticRegression(
                    C=MODEL_C,
                    class_weight="balanced",
                    random_state=RANDOM_STATE,
                    max_iter=5000,
                ),
            ),
        ]
    )
    model.fit(frame[features], values)
    return model


def probabilities(model: Any, frame: pd.DataFrame, features: list[str]) -> np.ndarray:
    if frame.empty:
        return np.asarray([], dtype=float)
    return np.asarray(model.predict_proba(frame[features])[:, 1], dtype=float)


def price_at(context: Any, ts: pd.Timestamp) -> float:
    if ts == pd.Timestamp(context.book.terminal_ts):
        return float(context.book.quality["terminal_open"])
    day_lookup = timestamp_index(context)
    day = ts.normalize()
    index = day_lookup[day]
    return float(context.features.hourly_open[index, ts.hour])


def apply_arm(
    context: Any,
    trades: list[dict[str, Any]],
    arm: str,
    entry_probability: dict[int, float],
    exit_probability: dict[int, float],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    filter_enabled = arm in {"FILTER_ONLY", "FILTER_AND_EXTEND"}
    extend_enabled = arm in {"EXTEND_ONLY", "FILTER_AND_EXTEND"}
    selected: list[tuple[int, dict[str, Any]]] = []
    decisions: list[dict[str, Any]] = []
    for order, source in enumerate(trades):
        entry_p = float(entry_probability.get(order, 1.0))
        accepted = not filter_enabled or entry_p >= THRESHOLD
        decisions.append(
            {
                "trade_order": order,
                "entry_ts": pd.Timestamp(source["entry_ts"]).isoformat(),
                "side": str(source["side"]),
                "teacher_exit_ts": pd.Timestamp(source["exit_ts"]).isoformat(),
                "teacher_exit_reason": str(source["exit_reason"]),
                "entry_probability": entry_p,
                "accepted": accepted,
                "exit_probability": float(exit_probability.get(order, 0.0)),
                "extended": False,
            }
        )
        if accepted:
            selected.append((order, copy.deepcopy(source)))

    terminal = pd.Timestamp(context.book.terminal_ts)
    for selected_index, (order, trade) in enumerate(selected):
        reason = str(trade["exit_reason"])
        exit_ts = pd.Timestamp(trade["exit_ts"])
        exit_p = float(exit_probability.get(order, 0.0))
        can_extend = (
            extend_enabled
            and reason in ELIGIBLE_EXTENSIONS
            and exit_ts.hour == 0
            and exit_p >= THRESHOLD
        )
        if not can_extend:
            continue
        target = min(exit_ts + pd.Timedelta(days=EXTEND_DAYS), terminal)
        if order + 1 < len(trades):
            next_teacher_entry = pd.Timestamp(trades[order + 1]["entry_ts"])
            target = min(target, next_teacher_entry)
        if target <= exit_ts:
            continue
        trade["exit_ts"] = target.isoformat()
        trade["exit_price"] = price_at(context, target)
        trade["exit_reason"] = f"{reason}_ml_extend_{EXTEND_DAYS}d"
        for decision in decisions:
            if int(decision["trade_order"]) == order:
                decision["extended"] = True
                decision["overlay_exit_ts"] = target.isoformat()
                decision["overlay_exit_price"] = float(trade["exit_price"])
                break
    return [trade for _, trade in selected], decisions


def replay_metrics(v6: Any, context: Any, trades: list[dict[str, Any]]) -> dict[str, Any]:
    raw = SimpleNamespace(trades=trades, metrics={"equity_multiple": math.nan})
    replay = v6.chronological_replay(context, raw, slippage=SLIPPAGE, include_funding=True)
    independent: list[float] = []
    for trade in trades:
        one = SimpleNamespace(trades=[trade], metrics={"equity_multiple": math.nan})
        result = v6.chronological_replay(context, one, slippage=SLIPPAGE, include_funding=True)
        independent.append(float(result["terminal_equity"]) - 1.0)
    positives = sum(value for value in independent if value > 0.0)
    negatives = -sum(value for value in independent if value < 0.0)
    duration_hours = sum(
        (pd.Timestamp(row["exit_ts"]) - pd.Timestamp(row["entry_ts"])).total_seconds() / 3600.0
        for row in trades
    )
    return {
        "terminal_equity": float(replay["terminal_equity"]),
        "net_return_pct": (float(replay["terminal_equity"]) - 1.0) * 100.0,
        "chronological_1h_mdd_pct": float(replay["chronological_1h_mdd_pct"]),
        "trades": len(trades),
        "long_trades": sum(str(row["side"]) == "long" for row in trades),
        "short_trades": sum(str(row["side"]) == "short" for row in trades),
        "win_rate": float(np.mean([value > 0.0 for value in independent])) if independent else math.nan,
        "profit_factor": positives / negatives if negatives > 0.0 else math.inf if positives > 0 else math.nan,
        "turnover_multiple": float(replay["turnover_multiple"]),
        "cost_pct_initial": float(replay["cost_pct_initial"]),
        "funding_pct_initial": float(replay["funding_pct_initial"]),
        "max_marked_leverage": float(replay["max_marked_leverage"]),
        "exposure_days": duration_hours / 24.0,
        "per_trade_returns": independent,
    }


def source_manifest(diag: Any, engine: Any, v6: Any) -> dict[str, Any]:
    sources = {
        "contract": CONTRACT,
        "script": Path(__file__),
        "diagnostic": DIAGNOSTIC,
        "v7_1_engine": Path(diag.ENGINE_PATH),
        "v7_1_adapter": Path(diag.ADAPTER_PATH),
        "v6_replay": Path(diag.V6_ABLATION_PATH),
    }
    return {name: {"path": str(path.relative_to(ROOT)), "sha256": sha256(path)} for name, path in sources.items()}


def verify_manifest(manifest: dict[str, Any]) -> None:
    expected = MANIFEST_PATH.with_suffix(MANIFEST_PATH.suffix + ".sha256")
    if not expected.exists():
        raise RuntimeError("development manifest sidecar missing")
    stored = expected.read_text(encoding="utf-8").split()[0]
    if stored != sha256(MANIFEST_PATH):
        raise RuntimeError("development manifest hash mismatch")
    for source in manifest["sources"].values():
        path = ROOT / source["path"]
        if sha256(path) != source["sha256"]:
            raise RuntimeError(f"frozen source drift: {path}")


def residual_predictions(
    entry: pd.DataFrame,
    exits: pd.DataFrame,
    fit_orders: set[int],
    score_orders: set[int],
) -> tuple[dict[int, float], dict[int, float], dict[str, Any]]:
    entry_fit = entry[entry["trade_order"].isin(fit_orders)]
    entry_score = entry[entry["trade_order"].isin(score_orders)]
    exit_fit = exits[exits["trade_order"].isin(fit_orders)]
    exit_score = exits[exits["trade_order"].isin(score_orders)]
    entry_model = residual_model(entry_fit, ENTRY_FEATURES, "target_positive")
    exit_model = residual_model(exit_fit, EXIT_FEATURES, "target_continue")
    entry_p = dict(zip(entry_score["trade_order"].astype(int), probabilities(entry_model, entry_score, ENTRY_FEATURES), strict=True))
    exit_p = dict(zip(exit_score["trade_order"].astype(int), probabilities(exit_model, exit_score, EXIT_FEATURES), strict=True))
    audit = {
        "entry_fit_rows": len(entry_fit),
        "entry_fit_positive_rate": float(entry_fit["target_positive"].mean()),
        "entry_score_rows": len(entry_score),
        "exit_fit_rows": len(exit_fit),
        "exit_fit_positive_rate": float(exit_fit["target_continue"].mean()),
        "exit_score_rows": len(exit_score),
    }
    return entry_p, exit_p, audit


def choose_arm(candidate_metrics: dict[str, dict[str, Any]], baseline_equity: float) -> tuple[str, bool]:
    best_equity = max(float(row["terminal_equity"]) for row in candidate_metrics.values())
    within = [
        arm
        for arm in ARM_ORDER
        if best_equity - float(candidate_metrics[arm]["terminal_equity"]) <= 0.005
    ]
    chosen = min(
        within,
        key=lambda arm: (
            ARM_ORDER.index(arm),
            -float(candidate_metrics[arm]["chronological_1h_mdd_pct"]),
        ),
    )
    return chosen, float(candidate_metrics[chosen]["terminal_equity"]) > baseline_equity


def develop() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    diag, v6, engine, _, context = load_dependencies(train_only=True)
    teacher = run_teacher(diag, v6, engine, context, 0, TRAIN_DAYS)
    if pd.Timestamp(teacher.result.raw.path[-1]["ts"]) != pd.Timestamp(context.book.terminal_ts):
        raise RuntimeError("training terminal drift")
    market = market_rows(engine, context)
    states = teacher_state_rows(context, market, teacher, 0, TRAIN_DAYS)
    clone = clone_dataset(context, states, teacher, 0, TRAIN_DAYS)
    clone_fitted_model, clone_predictions, clone_fit_metrics = fit_clone(clone)
    del clone_fitted_model
    clone_oof, clone_oof_metrics = clone_expanding_oof(clone)

    entry = entry_rows(context, states, teacher, 0, TRAIN_DAYS)
    exits = exit_rows(context, states, teacher, 0, TRAIN_DAYS)
    if len(entry) != len(teacher.result.raw.trades):
        raise RuntimeError("entry training rows do not match teacher trades")
    all_orders = set(entry["trade_order"].astype(int))
    fit_orders = {order for order in all_orders if order < RESIDUAL_FIT_TRADES}
    confirm_orders = all_orders - fit_orders
    if not confirm_orders:
        raise RuntimeError("internal confirmation contains no trades")
    entry_p, exit_p, residual_audit = residual_predictions(
        entry, exits, fit_orders, confirm_orders
    )
    confirm_trades = [
        copy.deepcopy(trade)
        for order, trade in enumerate(teacher.result.raw.trades)
        if order in confirm_orders
    ]
    order_offset = min(confirm_orders)
    local_entry_p = {order - order_offset: value for order, value in entry_p.items()}
    local_exit_p = {order - order_offset: value for order, value in exit_p.items()}
    baseline_metrics = replay_metrics(v6, context, confirm_trades)
    candidates: dict[str, dict[str, Any]] = {}
    candidate_decisions: list[dict[str, Any]] = []
    for arm in ARM_ORDER:
        arm_trades, decisions = apply_arm(
            context, confirm_trades, arm, local_entry_p, local_exit_p
        )
        candidates[arm] = replay_metrics(v6, context, arm_trades)
        for decision in decisions:
            decision["arm"] = arm
            decision["teacher_trade_order"] = int(decision["trade_order"]) + order_offset
            candidate_decisions.append(decision)
    chosen_arm, residual_gate = choose_arm(candidates, float(baseline_metrics["terminal_equity"]))

    full_entry_p, full_exit_p, full_audit = residual_predictions(
        entry, exits, all_orders, all_orders
    )
    full_trades, full_decisions = apply_arm(
        context,
        list(teacher.result.raw.trades),
        chosen_arm,
        full_entry_p,
        full_exit_p,
    )
    full_metrics = replay_metrics(v6, context, full_trades)
    clone_gate = (
        clone_fit_metrics["accuracy"] >= 0.99
        and clone_fit_metrics["transition_recall"] == 1.0
    )
    oof_weak = clone_oof_metrics["transition_recall"] < 0.50
    status = (
        "DEVELOPMENT_PASS_READY_FOR_REUSED_HOLDOUT"
        if clone_gate and residual_gate
        else "CLONE_FIT_FAILED"
        if not clone_gate
        else "RESIDUAL_TRAINING_FAILED"
    )

    paths = {
        "teacher_states": ARTIFACT_DIR / f"{PREFIX}_teacher_daily_states.csv",
        "clone_predictions": ARTIFACT_DIR / f"{PREFIX}_clone_predictions.csv",
        "clone_oof": ARTIFACT_DIR / f"{PREFIX}_clone_oof_predictions.csv",
        "residual_rows": ARTIFACT_DIR / f"{PREFIX}_residual_training_rows.csv",
        "internal": ARTIFACT_DIR / f"{PREFIX}_internal_confirmation.csv",
        "full_decisions": ARTIFACT_DIR / f"{PREFIX}_training_residual_decisions.csv",
        "summary": ARTIFACT_DIR / f"{PREFIX}_development_summary.json",
    }
    write_csv(paths["teacher_states"], states)
    write_csv(paths["clone_predictions"], clone_predictions)
    write_csv(paths["clone_oof"], clone_oof)
    residual_rows = pd.concat(
        [
            entry.assign(sample_type="trade_filter"),
            exits.assign(sample_type="exit_extension"),
        ],
        ignore_index=True,
        sort=False,
    )
    write_csv(paths["residual_rows"], residual_rows)
    write_csv(paths["internal"], candidate_decisions)
    write_csv(paths["full_decisions"], full_decisions)
    development = {
        "family": FAMILY,
        "experiment": EXPERIMENT,
        "run_date": RUN_DATE,
        "stage": "develop",
        "status": status,
        "data_boundary": {
            "train_days": TRAIN_DAYS,
            "train_start": pd.Timestamp(context.book.ts[0]),
            "train_last_feature_day": pd.Timestamp(context.book.ts[TRAIN_DAYS - 1]),
            "train_terminal": pd.Timestamp(context.book.terminal_ts),
            "holdout_days": TOTAL_DAYS - TRAIN_DAYS,
            "holdout_read": False,
        },
        "teacher_v7_1": teacher.metrics,
        "clone": {
            "features": CLONE_FEATURES,
            "training_fit": clone_fit_metrics,
            "expanding_oof": clone_oof_metrics,
            "clone_fit_gate": clone_gate,
            "clone_generalization_weak": oof_weak,
        },
        "residual": {
            "fit_trade_orders": sorted(fit_orders),
            "internal_confirmation_trade_orders": sorted(confirm_orders),
            "model_audit": residual_audit,
            "baseline_internal_confirmation": baseline_metrics,
            "candidate_internal_confirmation": candidates,
            "chosen_arm": chosen_arm,
            "residual_internal_gate": residual_gate,
            "full_training_refit_audit": full_audit,
            "full_training_overlay": full_metrics,
        },
    }
    write_json(paths["summary"], development)
    for path in paths.values():
        write_sidecar(path)

    manifest = {
        "family": FAMILY,
        "experiment": EXPERIMENT,
        "run_date": RUN_DATE,
        "status": status,
        "train_days": TRAIN_DAYS,
        "total_days": TOTAL_DAYS,
        "residual_fit_trades": RESIDUAL_FIT_TRADES,
        "clone_features": CLONE_FEATURES,
        "entry_features": ENTRY_FEATURES,
        "exit_features": EXIT_FEATURES,
        "model_c": MODEL_C,
        "threshold": THRESHOLD,
        "extend_days": EXTEND_DAYS,
        "chosen_arm": chosen_arm,
        "clone_fit_gate": clone_gate,
        "residual_internal_gate": residual_gate,
        "holdout_permitted": bool(clone_gate and residual_gate),
        "sources": source_manifest(diag, engine, v6),
        "development_artifacts": {
            name: {"path": str(path.relative_to(ROOT)), "sha256": sha256(path)}
            for name, path in paths.items()
        },
    }
    write_json(MANIFEST_PATH, manifest)
    write_sidecar(MANIFEST_PATH)
    return development


def validate() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        raise RuntimeError("run --stage develop first")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    verify_manifest(manifest)
    if not manifest.get("holdout_permitted"):
        raise RuntimeError("development gates failed; contract forbids holdout read")
    train_diag, train_v6, train_engine, _, train_context = load_dependencies(
        train_only=True
    )
    training = run_teacher(
        train_diag, train_v6, train_engine, train_context, 0, TRAIN_DAYS
    )
    training_market = market_rows(train_engine, train_context)
    training_states = teacher_state_rows(
        train_context, training_market, training, 0, TRAIN_DAYS
    )
    training_clone = clone_dataset(
        train_context, training_states, training, 0, TRAIN_DAYS
    )
    clone_model_fitted, _, clone_fit_metrics = fit_clone(training_clone)
    if clone_fit_metrics["accuracy"] < 0.99 or clone_fit_metrics["transition_recall"] != 1.0:
        raise RuntimeError("retrained clone no longer passes frozen gate")
    training_entry = entry_rows(
        train_context, training_states, training, 0, TRAIN_DAYS
    )
    training_exits = exit_rows(
        train_context, training_states, training, 0, TRAIN_DAYS
    )
    entry_model = residual_model(training_entry, ENTRY_FEATURES, "target_positive")
    exit_model = residual_model(training_exits, EXIT_FEATURES, "target_continue")

    diag, v6, engine, _, context = load_dependencies(train_only=False)
    market = market_rows(engine, context)
    validation = run_teacher(diag, v6, engine, context, TRAIN_DAYS, TOTAL_DAYS)
    validation_states = teacher_state_rows(
        context, market, validation, TRAIN_DAYS, TOTAL_DAYS
    )
    validation_clone = clone_dataset(
        context, validation_states, validation, TRAIN_DAYS, TOTAL_DAYS
    )
    validation_clone_pred = clone_model_fitted.predict(validation_clone[CLONE_FEATURES])
    clone_validation_metrics = classification_metrics(
        validation_clone["target_action"].tolist(), validation_clone_pred.tolist()
    )
    validation_clone_output = validation_clone[
        ["index", "ts", "target_ts", "target_action", "teacher_raw_action"]
    ].copy()
    validation_clone_output["predicted_action"] = validation_clone_pred
    validation_clone_output["correct"] = (
        validation_clone_output["target_action"] == validation_clone_output["predicted_action"]
    )

    validation_entry = entry_rows(
        context, validation_states, validation, TRAIN_DAYS, TOTAL_DAYS
    )
    validation_exits = exit_rows(
        context, validation_states, validation, TRAIN_DAYS, TOTAL_DAYS
    )
    entry_p_values = probabilities(entry_model, validation_entry, ENTRY_FEATURES)
    exit_p_values = probabilities(exit_model, validation_exits, EXIT_FEATURES)
    entry_p = dict(zip(validation_entry["trade_order"].astype(int), entry_p_values, strict=True))
    exit_p = dict(zip(validation_exits["trade_order"].astype(int), exit_p_values, strict=True))
    chosen_arm = str(manifest["chosen_arm"])
    overlay_trades, decisions = apply_arm(
        context, list(validation.result.raw.trades), chosen_arm, entry_p, exit_p
    )
    teacher_metrics = replay_metrics(v6, context, list(validation.result.raw.trades))
    overlay_metrics = replay_metrics(v6, context, overlay_trades)
    beaten = (
        overlay_metrics["net_return_pct"] > teacher_metrics["net_return_pct"]
        and overlay_metrics["chronological_1h_mdd_pct"]
        >= teacher_metrics["chronological_1h_mdd_pct"] - 2.0
        and all(float(trade.get("entry_leverage", 1.0)) <= 1.0 for trade in overlay_trades)
    )
    status = "EDUCATIONAL_REUSED_HOLDOUT_WIN" if beaten else "V7_1_NOT_BEATEN"
    summary = {
        "family": FAMILY,
        "experiment": EXPERIMENT,
        "run_date": RUN_DATE,
        "stage": "validate",
        "status": status,
        "holdout_classification": "reused_holdout_not_clean_oos",
        "boundary": {
            "start": pd.Timestamp(context.book.ts[TRAIN_DAYS]),
            "last_day": pd.Timestamp(context.book.ts[TOTAL_DAYS - 1]),
            "terminal": pd.Timestamp(context.book.terminal_ts),
            "days": TOTAL_DAYS - TRAIN_DAYS,
        },
        "frozen_chosen_arm": chosen_arm,
        "clone_validation": clone_validation_metrics,
        "teacher_v7_1": teacher_metrics,
        "ml_residual_overlay": overlay_metrics,
        "v7_1_beaten": beaten,
        "model_training_rows": {
            "clone": len(training_clone),
            "trade_filter": len(training_entry),
            "exit_extension": len(training_exits),
        },
    }
    paths = {
        "clone": ARTIFACT_DIR / f"{PREFIX}_validation_clone_predictions.csv",
        "entry": ARTIFACT_DIR / f"{PREFIX}_validation_entry_rows.csv",
        "exit": ARTIFACT_DIR / f"{PREFIX}_validation_exit_rows.csv",
        "decisions": ARTIFACT_DIR / f"{PREFIX}_validation_residual_decisions.csv",
        "teacher_trades": ARTIFACT_DIR / f"{PREFIX}_validation_teacher_trades.csv",
        "overlay_trades": ARTIFACT_DIR / f"{PREFIX}_validation_overlay_trades.csv",
        "summary": ARTIFACT_DIR / f"{PREFIX}_validation_summary.json",
    }
    write_csv(paths["clone"], validation_clone_output)
    write_csv(paths["entry"], validation_entry.assign(predicted_probability=entry_p_values))
    exit_output = validation_exits.copy()
    exit_output["predicted_probability"] = exit_p_values
    write_csv(paths["exit"], exit_output)
    write_csv(paths["decisions"], decisions)
    write_csv(paths["teacher_trades"], list(validation.result.raw.trades))
    write_csv(paths["overlay_trades"], overlay_trades)
    write_json(paths["summary"], summary)
    for path in paths.values():
        write_sidecar(path)
    return summary


def self_test() -> None:
    assert action_label({"action": "hold", "position": 0}, 0) == "FLAT"
    assert action_label({"action": "hold", "position": 1}, 1) == "HOLD_LONG"
    assert action_label({"action": "ma7_slope_exit", "position": 0}, -1) == "EXIT_SHORT"
    assert action_label({"action": "pehc_handoff_enter_short", "position": -1}, 0) == "ENTER_SHORT"
    assert safe_ratio(2.0, 4.0) == 0.5
    assert math.isnan(safe_ratio(1.0, 0.0))
    fake = pd.DataFrame({"x": [0.0, 1.0], "y": [1, 1]})
    constant = residual_model(fake, ["x"], "y")
    assert np.allclose(constant.predict_proba(fake[["x"]])[:, 1], 1.0)
    print("P4 self-test passed: 7 assertions")


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return
    result = develop() if args.stage == "develop" else validate()
    print(json.dumps(sanitize(result), ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
