from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
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
    / "specs/hype-1d-ma7-mlt-p6-v7-anchor-three-head-lifecycle-contract-2026-08-28.md"
)
P4_SCRIPT = FAMILY_DIR / "scripts/run_hype_1d_ma7_mlt_p4_v7_1_behavior_clone_residual.py"
P5_SCRIPT = FAMILY_DIR / "scripts/run_hype_1d_ma7_mlt_p5_opportunity_repair_lifecycle.py"

FAMILY = "HYPE-1D-MA7-Machine-Learning-Trend"
EXPERIMENT = "P6_V7_ANCHOR_THREE_HEAD_LIFECYCLE"
RUN_DATE = "2026-08-28"
PREFIX = "hype_1d_ma7_mlt_p6_v7_anchor_three_head_lifecycle_2026-08-28"
TRAIN_DAYS = 365
TOTAL_DAYS = 446
DEVELOPMENT_DAYS = 285
PURGE_DAYS = 3
OOF_WINDOWS = ((120, 160), (160, 200), (200, 240), (240, 285))
RANDOM_STATE = 20260828
ENTRY_MAX_AGE = 6
ENTRY_HORIZON = 21
REVERSAL_HORIZON = 14
ENTRY_THRESHOLD = 0.65
EXTEND_START_THRESHOLD = 0.60
SURVIVAL_EXIT_THRESHOLD = 0.35
REVERSAL_THRESHOLD = 0.70
LOW_SURVIVAL_CONFIRMATIONS = 2
ROUNDTRIP_COST = 0.0028
REVERSAL_COST = 0.0042
SLIPPAGE = 0.0004

ELIGIBLE_CORE_EXITS = {
    "long_mfe_fraction_trail_exit",
    "ma7_slope_exit",
    "short_rsi_take_profit",
    "max_hold",
}

ENTRY_ADDITIONS = [
    "pre_cross_gap_atr",
    "cross_jump_atr",
    "aligned_pre_cross_return_3d",
    "prior_opposite_run",
    "root_peak_gap_atr",
    "root_gap_giveback_atr",
]
SURVIVAL_ADDITIONS = [
    "root_unrealized_atr",
    "root_mfe_atr",
    "root_mae_atr",
    "root_price_giveback_atr",
    "days_since_favorable_close",
    "same_side_run",
    "aligned_slope_decay3",
]

MANIFEST_PATH = ARTIFACT_DIR / f"{PREFIX}_development_manifest.json"


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
    if isinstance(value, np.ndarray):
        return [sanitize(item) for item in value.tolist()]
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


def write_csv(path: Path, rows: Any) -> None:
    frame = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    frame.to_csv(path, index=False)


def write_sidecar(path: Path) -> None:
    path.with_suffix(path.suffix + ".sha256").write_text(
        f"{sha256(path)}  {path.name}\n", encoding="utf-8"
    )


def _side(trade: dict[str, Any]) -> int:
    return 1 if str(trade["side"]) == "long" else -1


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


def build_frame(p5: Any, p4: Any, engine: Any, context: Any) -> tuple[pd.DataFrame, list[dict[str, Any]], dict[str, Path]]:
    frame, episodes, label_paths = p5.build_labels(
        context, p5.build_feature_frame(p4, engine, context)
    )
    close = frame["close"].to_numpy(float)
    high = frame["high"].to_numpy(float)
    low = frame["low"].to_numpy(float)
    ma7 = frame["ma7"].to_numpy(float)
    atr = frame["atr7"].to_numpy(float)
    root_side = frame["root_side"].to_numpy(int)
    root_index = frame["root_index"].to_numpy(int)
    slope = frame["slope1_atr"].to_numpy(float)
    aligned_gap = frame["aligned_ma_gap_atr"].to_numpy(float)

    additions = {name: np.full(len(frame), np.nan) for name in ENTRY_ADDITIONS + SURVIVAL_ADDITIONS}
    same_side_run = 0
    prior_root = -1
    for index in range(len(frame)):
        side = int(root_side[index])
        origin = int(root_index[index])
        if side == 0 or origin < 0:
            same_side_run = 0
            continue
        if origin != prior_root:
            same_side_run = 0
            prior_root = origin
        if side * (close[index] - ma7[index]) > 0.0:
            same_side_run += 1
        else:
            same_side_run = 0

        prior = origin - 1
        if prior >= 0:
            pre_gap = side * (close[prior] - ma7[prior]) / atr[prior]
            additions["pre_cross_gap_atr"][index] = pre_gap
            additions["cross_jump_atr"][index] = aligned_gap[origin] - pre_gap
        if origin >= 4:
            additions["aligned_pre_cross_return_3d"][index] = side * (
                close[origin - 1] / close[origin - 4] - 1.0
            )
        run = 0
        cursor = origin - 1
        while cursor >= 0 and side * (close[cursor] - ma7[cursor]) <= 0.0:
            run += 1
            cursor -= 1
        additions["prior_opposite_run"][index] = run

        root_gaps = aligned_gap[origin : index + 1]
        peak_gap = float(np.nanmax(root_gaps))
        additions["root_peak_gap_atr"][index] = peak_gap
        additions["root_gap_giveback_atr"][index] = peak_gap - aligned_gap[index]
        base = close[origin]
        base_atr = atr[origin]
        additions["root_unrealized_atr"][index] = side * (close[index] - base) / base_atr
        if side > 0:
            mfe = (float(np.max(high[origin : index + 1])) - base) / base_atr
            mae = (float(np.min(low[origin : index + 1])) - base) / base_atr
            favorable = close[origin : index + 1]
            best_offset = int(np.argmax(favorable))
        else:
            mfe = (base - float(np.min(low[origin : index + 1]))) / base_atr
            mae = (base - float(np.max(high[origin : index + 1]))) / base_atr
            favorable = close[origin : index + 1]
            best_offset = int(np.argmin(favorable))
        additions["root_mfe_atr"][index] = max(0.0, mfe)
        additions["root_mae_atr"][index] = min(0.0, mae)
        additions["root_price_giveback_atr"][index] = max(
            0.0, mfe - additions["root_unrealized_atr"][index]
        )
        additions["days_since_favorable_close"][index] = index - (origin + best_offset)
        additions["same_side_run"][index] = same_side_run
        if index >= 3:
            additions["aligned_slope_decay3"][index] = side * (slope[index] - slope[index - 3])
    for name, values in additions.items():
        frame[name] = values
    return frame, episodes, label_paths


def occupied(ts: pd.Timestamp, trades: list[dict[str, Any]]) -> bool:
    return any(
        pd.Timestamp(trade["entry_ts"]) <= ts < pd.Timestamp(trade["exit_ts"])
        for trade in trades
    )


def path_excursions(
    context: Any, entry_index: int, exit_index: int, side: int, atr: float
) -> tuple[float, float]:
    entry = _open_price(context, entry_index)
    if exit_index <= entry_index:
        return 0.0, 0.0
    highs = np.asarray(context.book.high[entry_index:exit_index], dtype=float)
    lows = np.asarray(context.book.low[entry_index:exit_index], dtype=float)
    if side > 0:
        return (float(highs.max()) - entry) / atr, (float(lows.min()) - entry) / atr
    return (entry - float(lows.min())) / atr, (entry - float(highs.max())) / atr


def build_entry_rows(
    context: Any,
    frame: pd.DataFrame,
    episodes: list[dict[str, Any]],
    teacher_trades: list[dict[str, Any]],
    left: int,
    right: int,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in frame.to_dict("records"):
        index = int(row["index"])
        side = int(row["root_side"])
        if not (left <= index < right - 1) or side == 0 or int(row["root_age"]) > ENTRY_MAX_AGE:
            continue
        entry_index = index + 1
        entry_ts = _open_ts(context, entry_index)
        if occupied(entry_ts, teacher_trades):
            continue
        complete = index + ENTRY_HORIZON < right
        matches = [
            episode
            for episode in episodes
            if int(episode["side"]) == side
            and int(episode["start_index"]) <= index + 2
            and int(episode["end_index"]) >= index + 3
        ]
        best: dict[str, Any] | None = None
        for episode in matches:
            exit_index = min(int(episode["end_index"]) + 1, right)
            if exit_index <= entry_index:
                continue
            entry = _open_price(context, entry_index)
            exit_price = _open_price(context, exit_index)
            net = side * (exit_price / entry - 1.0) - ROUNDTRIP_COST
            mfe, mae = path_excursions(
                context, entry_index, exit_index, side, float(row["atr7"])
            )
            candidate = {
                "matched_episode_id": episode["episode_id"],
                "label_exit_index": exit_index,
                "label_net_return": net,
                "label_mfe_atr": mfe,
                "label_mae_atr": mae,
            }
            if best is None or net > float(best["label_net_return"]):
                best = candidate
        if best is None:
            best = {
                "matched_episode_id": None,
                "label_exit_index": None,
                "label_net_return": math.nan,
                "label_mfe_atr": math.nan,
                "label_mae_atr": math.nan,
            }
            target = 0
        else:
            target = int(
                float(best["label_net_return"]) >= 0.03
                and float(best["label_mfe_atr"]) >= 1.5
                and float(best["label_mae_atr"]) >= -1.5
            )
        rows.append(
            {
                **row,
                "entry_open_index": entry_index,
                "entry_ts": entry_ts.isoformat(),
                "entry_label_complete": complete,
                "entry_value": target if complete else math.nan,
                **best,
            }
        )
    return pd.DataFrame(rows)


def build_survival_rows(frame: pd.DataFrame, left: int, right: int) -> pd.DataFrame:
    stable = frame["stable_side"].to_numpy(float)
    rows: list[dict[str, Any]] = []
    for row in frame.to_dict("records"):
        index = int(row["index"])
        side = int(row["root_side"])
        if not (left <= index < right) or side == 0:
            continue
        complete = index + 3 < right and all(math.isfinite(stable[j]) for j in range(index, index + 4))
        target = math.nan
        if complete:
            current = int(stable[index]) == side
            future_matches = sum(int(stable[j]) == side for j in range(index + 1, index + 4))
            target = int(current and future_matches >= 2)
        rows.append({**row, "survival_label_complete": complete, "survival_3d": target})
    return pd.DataFrame(rows)


def build_reversal_rows(
    context: Any, frame: pd.DataFrame, left: int, right: int
) -> pd.DataFrame:
    stable = frame["stable_side"].to_numpy(float)
    rows: list[dict[str, Any]] = []
    for row in frame.to_dict("records"):
        index = int(row["index"])
        side = int(row["raw_cross"])
        if not (left <= index < right - 1) or side == 0:
            continue
        entry_index = index + 1
        complete = entry_index + REVERSAL_HORIZON < right
        best_net = mae = math.nan
        confirmed = False
        target = math.nan
        if complete:
            entry = _open_price(context, entry_index)
            prices = np.asarray(
                [_open_price(context, cursor) for cursor in range(entry_index + 1, entry_index + REVERSAL_HORIZON + 1)],
                dtype=float,
            )
            best_net = float(np.max(side * (prices / entry - 1.0))) - REVERSAL_COST
            _, mae = path_excursions(
                context,
                entry_index,
                entry_index + REVERSAL_HORIZON,
                side,
                float(row["atr7"]),
            )
            confirmed = any(
                index + offset < len(stable)
                and math.isfinite(stable[index + offset])
                and int(stable[index + offset]) == side
                for offset in range(3)
            )
            target = int(best_net >= 0.04 and mae >= -1.5 and confirmed)
        rows.append(
            {
                **row,
                "reversal_label_complete": complete,
                "reversal_value": target,
                "reversal_best_net_return": best_net,
                "reversal_mae_atr": mae,
                "reversal_stable_confirmed": confirmed,
            }
        )
    return pd.DataFrame(rows)


def make_model() -> Pipeline:
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            (
                "model",
                ExtraTreesClassifier(
                    n_estimators=600,
                    max_depth=5,
                    min_samples_leaf=6,
                    max_features=0.75,
                    class_weight="balanced",
                    random_state=RANDOM_STATE,
                    n_jobs=-1,
                ),
            ),
        ]
    )


def fit_model(frame: pd.DataFrame, features: list[str], target: str) -> Any:
    y = frame[target].astype(int)
    if y.empty:
        raise RuntimeError(f"empty training rows for {target}")
    if y.nunique() < 2:
        return ConstantProbabilityModel(float(y.mean()))
    model = make_model()
    model.fit(frame[features], y)
    return model


def probability(model: Any, frame: pd.DataFrame, features: list[str]) -> np.ndarray:
    if frame.empty:
        return np.asarray([], dtype=float)
    return np.asarray(model.predict_proba(frame[features])[:, 1], dtype=float)


def classification_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, Any]:
    y = np.asarray(actual, dtype=int)
    p = np.asarray(predicted, dtype=float)
    binary = p >= 0.5
    return {
        "rows": len(y),
        "positive_rate": float(y.mean()) if len(y) else math.nan,
        "auc": float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else math.nan,
        "brier": float(brier_score_loss(y, p)) if len(y) else math.nan,
        "accuracy_at_0_5": float(accuracy_score(y, binary)) if len(y) else math.nan,
        "balanced_accuracy_at_0_5": (
            float(balanced_accuracy_score(y, binary)) if len(np.unique(y)) == 2 else math.nan
        ),
        "precision_at_0_5": float(precision_score(y, binary, zero_division=0)),
        "recall_at_0_5": float(recall_score(y, binary, zero_division=0)),
        "f1_at_0_5": float(f1_score(y, binary, zero_division=0)),
    }


def complete_rows(frame: pd.DataFrame, target: str, complete: str, left: int, right: int) -> pd.DataFrame:
    return frame.loc[
        (frame["index"].astype(int) >= left)
        & (frame["index"].astype(int) < right)
        & frame[complete].astype(bool)
        & frame[target].notna()
    ].copy()


def expanding_oof(
    frame: pd.DataFrame,
    features: list[str],
    target: str,
    complete: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    outputs: list[pd.DataFrame] = []
    audits: list[dict[str, Any]] = []
    for fold, (start, end) in enumerate(OOF_WINDOWS, start=1):
        train = complete_rows(frame, target, complete, 0, start - PURGE_DAYS)
        test = complete_rows(frame, target, complete, start, end)
        if test.empty:
            continue
        model = fit_model(train, features, target)
        values = probability(model, test, features)
        part = test[["index", "ts", target]].copy()
        part["fold"] = fold
        part["probability"] = values
        outputs.append(part)
        audits.append(
            {
                "fold": fold,
                "train_end_exclusive": start - PURGE_DAYS,
                "train_rows": len(train),
                "train_positive_rate": float(train[target].mean()),
                "test_start": start,
                "test_end_exclusive": end,
                "test_rows": len(test),
            }
        )
    if not outputs:
        return pd.DataFrame(), {"rows": 0, "auc": math.nan, "folds": audits}
    output = pd.concat(outputs, ignore_index=True)
    metrics = classification_metrics(output[target].astype(int), output["probability"].astype(float))
    metrics["folds"] = audits
    return output, metrics


def score_rows(
    model: Any,
    frame: pd.DataFrame,
    features: list[str],
    left: int,
    right: int,
) -> pd.DataFrame:
    if frame.empty or "index" not in frame.columns:
        return pd.DataFrame(columns=["index", "probability"])
    output = frame.loc[
        (frame["index"].astype(int) >= left) & (frame["index"].astype(int) < right)
    ].copy()
    output["probability"] = probability(model, output, features)
    return output


def probability_map(frame: pd.DataFrame) -> dict[int, float]:
    return dict(zip(frame["index"].astype(int), frame["probability"].astype(float), strict=True))


def extend_core_trades(
    p4: Any,
    context: Any,
    frame: pd.DataFrame,
    teacher_trades: list[dict[str, Any]],
    survival_probability: dict[int, float],
    right: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    day_index = {pd.Timestamp(ts): index for index, ts in enumerate(context.book.ts)}
    states = frame.set_index(frame["index"].astype(int), drop=False)
    extended = copy.deepcopy(teacher_trades)
    decisions: list[dict[str, Any]] = []
    terminal = _open_ts(context, right)
    for order, trade in enumerate(extended):
        original_exit = pd.Timestamp(trade["exit_ts"])
        reason = str(trade["exit_reason"])
        can_consider = reason in ELIGIBLE_CORE_EXITS and original_exit.hour == 0
        start_probability = math.nan
        changed = False
        exit_trigger = "teacher_exit"
        if can_consider and original_exit.normalize() in day_index:
            exit_index = day_index[original_exit.normalize()]
            start_probability = float(survival_probability.get(exit_index - 1, 0.0))
            if start_probability >= EXTEND_START_THRESHOLD:
                cap = terminal
                if order + 1 < len(extended):
                    cap = min(cap, pd.Timestamp(extended[order + 1]["entry_ts"]))
                low_run = 0
                target = cap
                for decision_index in range(exit_index, right):
                    action_ts = _open_ts(context, decision_index + 1)
                    if action_ts >= cap:
                        target = cap
                        exit_trigger = "next_core_or_terminal"
                        break
                    side = _side(trade)
                    root = int(states.loc[decision_index]["root_side"])
                    p = float(survival_probability.get(decision_index, 0.0))
                    low_run = low_run + 1 if p < SURVIVAL_EXIT_THRESHOLD else 0
                    if root == -side:
                        target = action_ts
                        exit_trigger = "opposite_root"
                        break
                    if low_run >= LOW_SURVIVAL_CONFIRMATIONS:
                        target = action_ts
                        exit_trigger = "two_day_survival_death"
                        break
                if target > original_exit:
                    trade["exit_ts"] = target.isoformat()
                    trade["exit_price"] = p4.price_at(context, target)
                    trade["bars_held"] = int(
                        (target - pd.Timestamp(trade["entry_ts"])).total_seconds() / 86_400
                    )
                    trade["exit_reason"] = f"{reason}_p6_dynamic_survival"
                    changed = True
        decisions.append(
            {
                "kind": "core_exit",
                "core_order": order,
                "side": str(trade["side"]),
                "entry_ts": trade["entry_ts"],
                "teacher_exit_ts": original_exit.isoformat(),
                "p6_exit_ts": trade["exit_ts"],
                "teacher_exit_reason": reason,
                "p6_exit_reason": trade["exit_reason"],
                "survival_probability_at_teacher_exit": start_probability,
                "eligible": can_consider,
                "extended": changed,
                "exit_trigger": exit_trigger,
            }
        )
    return extended, decisions


def gap_intervals(
    context: Any,
    core: list[dict[str, Any]],
    left: int,
    right: int,
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    cursor = _open_ts(context, left)
    terminal = _open_ts(context, right)
    gaps: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    for trade in core:
        entry = pd.Timestamp(trade["entry_ts"])
        exit_ts = pd.Timestamp(trade["exit_ts"])
        if entry > cursor:
            gaps.append((cursor, min(entry, terminal)))
        cursor = max(cursor, exit_ts)
    if cursor < terminal:
        gaps.append((cursor, terminal))
    return [(left_ts, right_ts) for left_ts, right_ts in gaps if left_ts < right_ts]


def supplemental_trades(
    p4: Any,
    context: Any,
    frame: pd.DataFrame,
    entry_probability: dict[int, float],
    survival_probability: dict[int, float],
    reversal_probability: dict[int, float],
    gaps: list[tuple[pd.Timestamp, pd.Timestamp]],
    left: int,
    right: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    states = frame.set_index(frame["index"].astype(int), drop=False)
    trades: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    for gap_order, (gap_start, gap_end) in enumerate(gaps):
        side = 0
        entry_ts: pd.Timestamp | None = None
        entry_price = entry_p = math.nan
        entry_root = -1
        low_run = 0

        def close_trade(exit_ts: pd.Timestamp, reason: str, direct_reversal: bool = False) -> None:
            nonlocal side, entry_ts, entry_price, entry_p, entry_root, low_run
            if entry_ts is None:
                raise RuntimeError("supplemental close without entry")
            trades.append(
                {
                    "entry_ts": entry_ts.isoformat(),
                    "exit_ts": exit_ts.isoformat(),
                    "side": "long" if side > 0 else "short",
                    "entry_price": entry_price,
                    "entry_leverage": 1.0,
                    "exit_price": p4.price_at(context, exit_ts),
                    "bars_held": int((exit_ts - entry_ts).total_seconds() / 86_400),
                    "exit_reason": reason,
                    "entry_probability": entry_p,
                    "entry_root_index": entry_root,
                    "direct_reversal": direct_reversal,
                    "source": "p6_supplemental",
                    "gap_order": gap_order,
                }
            )
            side = 0
            entry_ts = None
            entry_price = entry_p = math.nan
            entry_root = -1
            low_run = 0

        for decision_index in range(left, right):
            action_ts = _open_ts(context, decision_index + 1)
            if not (gap_start < action_ts < gap_end):
                continue
            row = states.loc[decision_index]
            root = int(row["root_side"])
            p_entry = float(entry_probability.get(decision_index, 0.0))
            p_survival = float(survival_probability.get(decision_index, 0.0))
            p_reversal = float(reversal_probability.get(decision_index, 0.0))
            action = "flat" if side == 0 else "hold"
            if side == 0:
                if root != 0 and int(row["root_age"]) <= ENTRY_MAX_AGE and p_entry >= ENTRY_THRESHOLD:
                    side = root
                    entry_ts = action_ts
                    entry_price = p4.price_at(context, action_ts)
                    entry_p = p_entry
                    entry_root = int(row["root_index"])
                    action = "enter_long" if side > 0 else "enter_short"
            elif root == -side:
                old_side = side
                reverse = int(row["raw_cross"]) == root and p_reversal >= REVERSAL_THRESHOLD
                close_trade(action_ts, "p6_direct_reversal" if reverse else "p6_opposite_root_exit", reverse)
                action = "reverse" if reverse else "opposite_exit"
                if reverse:
                    side = root
                    entry_ts = action_ts
                    entry_price = p4.price_at(context, action_ts)
                    entry_p = p_entry
                    entry_root = int(row["root_index"])
            else:
                low_run = low_run + 1 if p_survival < SURVIVAL_EXIT_THRESHOLD else 0
                if low_run >= LOW_SURVIVAL_CONFIRMATIONS:
                    close_trade(action_ts, "p6_two_day_survival_death")
                    action = "survival_exit"
            decisions.append(
                {
                    "kind": "supplemental",
                    "gap_order": gap_order,
                    "decision_index": decision_index,
                    "decision_ts": row["ts"],
                    "action_ts": action_ts.isoformat(),
                    "root_side": root,
                    "entry_probability": p_entry,
                    "survival_probability": p_survival,
                    "reversal_probability": p_reversal,
                    "action": action,
                    "position_after_action": side,
                }
            )
        if side != 0:
            close_trade(gap_end, "p6_next_core_or_terminal")
    return trades, decisions


def apply_policy(
    p4: Any,
    context: Any,
    frame: pd.DataFrame,
    teacher_trades: list[dict[str, Any]],
    entry_scores: pd.DataFrame,
    survival_scores: pd.DataFrame,
    reversal_scores: pd.DataFrame,
    left: int,
    right: int,
) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    entry_map = probability_map(entry_scores)
    survival_map = probability_map(survival_scores)
    reversal_map = probability_map(reversal_scores)
    core, core_decisions = extend_core_trades(
        p4, context, frame, teacher_trades, survival_map, right
    )
    gaps = gap_intervals(context, core, left, right)
    supplemental, supplemental_decisions = supplemental_trades(
        p4,
        context,
        frame,
        entry_map,
        survival_map,
        reversal_map,
        gaps,
        left,
        right,
    )
    combined = core + supplemental
    combined.sort(key=lambda row: (pd.Timestamp(row["entry_ts"]), pd.Timestamp(row["exit_ts"])))
    for prior, current in zip(combined, combined[1:]):
        if pd.Timestamp(prior["exit_ts"]) > pd.Timestamp(current["entry_ts"]):
            raise RuntimeError(f"P6 schedule overlap: {prior} then {current}")
    return combined, pd.DataFrame(core_decisions + supplemental_decisions)


def score_bundle(
    models: dict[str, Any],
    datasets: dict[str, pd.DataFrame],
    features: dict[str, list[str]],
    left: int,
    right: int,
) -> dict[str, pd.DataFrame]:
    return {
        head: score_rows(models[head], datasets[head], features[head], left, right)
        for head in models
    }


def model_metrics(
    scored: pd.DataFrame, target: str, complete: str
) -> dict[str, Any]:
    known = scored.loc[scored[complete].astype(bool) & scored[target].notna()]
    if known.empty:
        return {"rows": 0, "auc": math.nan}
    return classification_metrics(known[target].astype(int), known["probability"].astype(float))


def recent_slices(
    p4: Any,
    diag: Any,
    v6: Any,
    engine: Any,
    context: Any,
    p5: Any,
    models: dict[str, Any],
    features: dict[str, list[str]],
    frame: pd.DataFrame,
    episodes: list[dict[str, Any]],
    left: int,
    right: int,
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for label, days in {"1d": 1, "7d": 7, "1m": 30, "3m": 90, "6m": 182, "1y": 365}.items():
        slice_left = max(left, right - days)
        teacher = p4.run_teacher(diag, v6, engine, context, slice_left, right)
        datasets = {
            "entry": build_entry_rows(context, frame, episodes, list(teacher.result.raw.trades), slice_left, right),
            "survival": build_survival_rows(frame, slice_left, right),
            "reversal": build_reversal_rows(context, frame, slice_left, right),
        }
        scores = score_bundle(models, datasets, features, slice_left, right)
        trades, _ = apply_policy(
            p4,
            context,
            frame,
            list(teacher.result.raw.trades),
            scores["entry"],
            scores["survival"],
            scores["reversal"],
            slice_left,
            right,
        )
        output[label] = {
            "available_days": right - slice_left,
            "p6": p4.replay_metrics(v6, context, trades),
            "v7_1": p4.replay_metrics(v6, context, list(teacher.result.raw.trades)),
        }
    return output


def attach_replay_returns(
    trades: list[dict[str, Any]], metrics: dict[str, Any]
) -> list[dict[str, Any]]:
    enriched = copy.deepcopy(trades)
    returns = list(metrics["per_trade_returns"])
    if len(enriched) != len(returns):
        raise RuntimeError("trade count and replay return count disagree")
    for trade, net_return in zip(enriched, returns):
        trade["net_return"] = float(net_return)
    return enriched


def source_manifest(p4: Any, diag: Any, label_paths: dict[str, Path]) -> dict[str, Any]:
    paths = {
        "contract": CONTRACT,
        "script": Path(__file__),
        "p4_runtime": P4_SCRIPT,
        "p5_feature_runtime": P5_SCRIPT,
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
    p4 = load_module(P4_SCRIPT, "hype_p6_p4_develop")
    p5 = load_module(P5_SCRIPT, "hype_p6_p5_develop")
    diag, v6, engine, _, context = p4.load_dependencies(train_only=True)
    if context.book.count != TRAIN_DAYS:
        raise RuntimeError("P6 development context is not physically limited to 365 days")
    if pd.Timestamp(context.market.audit["hourly_end"]) > p4.TRAIN_TERMINAL:
        raise RuntimeError("P6 development read holdout hourly bars")
    if pd.Timestamp(context.market.audit["funding_end"]) > p4.TRAIN_TERMINAL:
        raise RuntimeError("P6 development read holdout funding")

    frame, episodes, label_paths = build_frame(p5, p4, engine, context)
    teacher_full = p4.run_teacher(diag, v6, engine, context, 0, TRAIN_DAYS)
    teacher_development = p4.run_teacher(diag, v6, engine, context, 0, DEVELOPMENT_DAYS)
    teacher_confirmation = p4.run_teacher(
        diag, v6, engine, context, DEVELOPMENT_DAYS, TRAIN_DAYS
    )
    entry = build_entry_rows(
        context, frame, episodes, list(teacher_full.result.raw.trades), 0, TRAIN_DAYS
    )
    survival = build_survival_rows(frame, 0, TRAIN_DAYS)
    reversal = build_reversal_rows(context, frame, 0, TRAIN_DAYS)
    datasets = {"entry": entry, "survival": survival, "reversal": reversal}
    features = {
        "entry": list(p5.ROOT_FEATURES) + ENTRY_ADDITIONS,
        "survival": list(p5.ROOT_FEATURES) + ENTRY_ADDITIONS + SURVIVAL_ADDITIONS,
        "reversal": list(p5.ROOT_FEATURES) + ENTRY_ADDITIONS,
    }
    targets = {
        "entry": ("entry_value", "entry_label_complete"),
        "survival": ("survival_3d", "survival_label_complete"),
        "reversal": ("reversal_value", "reversal_label_complete"),
    }
    oof_outputs: list[pd.DataFrame] = []
    oof_metrics: dict[str, Any] = {}
    for head in datasets:
        target, complete = targets[head]
        output, metrics = expanding_oof(datasets[head], features[head], target, complete)
        output["head"] = head
        oof_outputs.append(output)
        oof_metrics[head] = metrics

    development_fit = {
        head: complete_rows(
            datasets[head], targets[head][0], targets[head][1], 0, DEVELOPMENT_DAYS - PURGE_DAYS
        )
        for head in datasets
    }
    development_models = {
        head: fit_model(development_fit[head], features[head], targets[head][0])
        for head in datasets
    }
    confirmation_datasets = {
        "entry": build_entry_rows(
            context,
            frame,
            episodes,
            list(teacher_confirmation.result.raw.trades),
            DEVELOPMENT_DAYS,
            TRAIN_DAYS,
        ),
        "survival": survival,
        "reversal": reversal,
    }
    confirmation_scores = score_bundle(
        development_models,
        confirmation_datasets,
        features,
        DEVELOPMENT_DAYS,
        TRAIN_DAYS,
    )
    confirmation_head_metrics = {
        head: model_metrics(
            confirmation_scores[head], targets[head][0], targets[head][1]
        )
        for head in datasets
    }
    confirmation_trades, confirmation_decisions = apply_policy(
        p4,
        context,
        frame,
        list(teacher_confirmation.result.raw.trades),
        confirmation_scores["entry"],
        confirmation_scores["survival"],
        confirmation_scores["reversal"],
        DEVELOPMENT_DAYS,
        TRAIN_DAYS,
    )
    confirmation_metrics = p4.replay_metrics(v6, context, confirmation_trades)
    teacher_confirmation_trades = list(teacher_confirmation.result.raw.trades)
    teacher_confirmation_metrics = p4.replay_metrics(v6, context, teacher_confirmation_trades)
    confirmation_trades = attach_replay_returns(confirmation_trades, confirmation_metrics)
    teacher_confirmation_trades = attach_replay_returns(
        teacher_confirmation_trades, teacher_confirmation_metrics
    )
    p6_confirmation_capture, p6_confirmation_episodes = p5.episode_capture(
        context, episodes, confirmation_trades, DEVELOPMENT_DAYS, TRAIN_DAYS
    )
    v7_confirmation_capture, v7_confirmation_episodes = p5.episode_capture(
        context, episodes, teacher_confirmation_trades, DEVELOPMENT_DAYS, TRAIN_DAYS
    )
    gate_requirements = {
        "entry_oof_auc_gte_0_60": float(oof_metrics["entry"]["auc"]) >= 0.60,
        "survival_oof_auc_gte_0_60": float(oof_metrics["survival"]["auc"]) >= 0.60,
        "confirmation_return_gt_v7_1": float(confirmation_metrics["net_return_pct"])
        > float(teacher_confirmation_metrics["net_return_pct"]),
        "confirmation_capture_gte_v7_1": float(p6_confirmation_capture["duration_weighted_capture"])
        >= float(v7_confirmation_capture["duration_weighted_capture"]),
        "confirmation_mdd_within_2pp": float(confirmation_metrics["chronological_1h_mdd_pct"])
        >= float(teacher_confirmation_metrics["chronological_1h_mdd_pct"]) - 2.0,
        "confirmation_trades_le_v7_plus_4": int(confirmation_metrics["trades"])
        <= int(teacher_confirmation_metrics["trades"]) + 4,
    }
    development_gate = all(gate_requirements.values())

    full_fit = {
        head: complete_rows(datasets[head], targets[head][0], targets[head][1], 0, TRAIN_DAYS)
        for head in datasets
    }
    full_models = {
        head: fit_model(full_fit[head], features[head], targets[head][0])
        for head in datasets
    }
    full_scores = score_bundle(full_models, datasets, features, 0, TRAIN_DAYS)
    full_head_metrics = {
        head: model_metrics(full_scores[head], targets[head][0], targets[head][1])
        for head in datasets
    }
    full_trades, full_decisions = apply_policy(
        p4,
        context,
        frame,
        list(teacher_full.result.raw.trades),
        full_scores["entry"],
        full_scores["survival"],
        full_scores["reversal"],
        0,
        TRAIN_DAYS,
    )
    full_metrics = p4.replay_metrics(v6, context, full_trades)
    teacher_full_trades = list(teacher_full.result.raw.trades)
    teacher_full_metrics = p4.replay_metrics(v6, context, teacher_full_trades)
    full_trades = attach_replay_returns(full_trades, full_metrics)
    teacher_full_trades = attach_replay_returns(teacher_full_trades, teacher_full_metrics)
    p6_full_capture, p6_full_episodes = p5.episode_capture(
        context, episodes, full_trades, 0, TRAIN_DAYS
    )
    v7_full_capture, v7_full_episodes = p5.episode_capture(
        context, episodes, teacher_full_trades, 0, TRAIN_DAYS
    )
    slices = recent_slices(
        p4,
        diag,
        v6,
        engine,
        context,
        p5,
        full_models,
        features,
        frame,
        episodes,
        0,
        TRAIN_DAYS,
    )
    status = (
        "DEVELOPMENT_PASS_READY_FOR_REUSED_HOLDOUT"
        if development_gate
        else "DEVELOPMENT_FAILED_HOLDOUT_LOCKED"
    )

    paths = {
        "feature_frame": ARTIFACT_DIR / f"{PREFIX}_training_feature_frame.csv",
        "entry_rows": ARTIFACT_DIR / f"{PREFIX}_entry_rows.csv",
        "survival_rows": ARTIFACT_DIR / f"{PREFIX}_survival_rows.csv",
        "reversal_rows": ARTIFACT_DIR / f"{PREFIX}_reversal_rows.csv",
        "oof": ARTIFACT_DIR / f"{PREFIX}_oof_predictions.csv",
        "confirmation_scores": ARTIFACT_DIR / f"{PREFIX}_internal_confirmation_scores.csv",
        "confirmation_decisions": ARTIFACT_DIR / f"{PREFIX}_internal_confirmation_decisions.csv",
        "confirmation_trades": ARTIFACT_DIR / f"{PREFIX}_internal_confirmation_trades.csv",
        "full_scores": ARTIFACT_DIR / f"{PREFIX}_training_scores.csv",
        "full_decisions": ARTIFACT_DIR / f"{PREFIX}_training_decisions.csv",
        "full_trades": ARTIFACT_DIR / f"{PREFIX}_training_trades.csv",
        "teacher_trades": ARTIFACT_DIR / f"{PREFIX}_training_v7_1_trades.csv",
        "episode_capture": ARTIFACT_DIR / f"{PREFIX}_training_episode_capture.csv",
        "summary": ARTIFACT_DIR / f"{PREFIX}_development_summary.json",
    }
    write_csv(paths["feature_frame"], frame)
    write_csv(paths["entry_rows"], entry)
    write_csv(paths["survival_rows"], survival)
    write_csv(paths["reversal_rows"], reversal)
    write_csv(paths["oof"], pd.concat(oof_outputs, ignore_index=True, sort=False))
    confirmation_long = pd.concat(
        [score.assign(head=head) for head, score in confirmation_scores.items()],
        ignore_index=True,
        sort=False,
    )
    write_csv(paths["confirmation_scores"], confirmation_long)
    write_csv(paths["confirmation_decisions"], confirmation_decisions)
    write_csv(paths["confirmation_trades"], confirmation_trades)
    full_long = pd.concat(
        [score.assign(head=head) for head, score in full_scores.items()],
        ignore_index=True,
        sort=False,
    )
    write_csv(paths["full_scores"], full_long)
    write_csv(paths["full_decisions"], full_decisions)
    write_csv(paths["full_trades"], full_trades)
    write_csv(paths["teacher_trades"], teacher_full_trades)
    write_csv(
        paths["episode_capture"],
        pd.concat(
            [
                p6_full_episodes.assign(strategy="P6"),
                v7_full_episodes.assign(strategy="V7.1"),
                p6_confirmation_episodes.assign(strategy="P6_INTERNAL_CONFIRMATION"),
                v7_confirmation_episodes.assign(strategy="V7.1_INTERNAL_CONFIRMATION"),
            ],
            ignore_index=True,
        ),
    )
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
        "features": features,
        "labels": {
            head: {
                "target": targets[head][0],
                "complete_rows": len(full_fit[head]),
                "positive_rate": float(full_fit[head][targets[head][0]].mean()),
            }
            for head in datasets
        },
        "oof": oof_metrics,
        "policy": {
            "entry_threshold": ENTRY_THRESHOLD,
            "extend_start_threshold": EXTEND_START_THRESHOLD,
            "survival_exit_threshold": SURVIVAL_EXIT_THRESHOLD,
            "low_survival_confirmations": LOW_SURVIVAL_CONFIRMATIONS,
            "reversal_threshold": REVERSAL_THRESHOLD,
        },
        "development_gate": {
            "passed": development_gate,
            "requirements": gate_requirements,
            "internal_confirmation": {
                "head_metrics": confirmation_head_metrics,
                "p6": confirmation_metrics,
                "v7_1": teacher_confirmation_metrics,
                "p6_episode_capture": p6_confirmation_capture,
                "v7_1_episode_capture": v7_confirmation_capture,
            },
        },
        "full_training_resubstitution": {
            "head_metrics": full_head_metrics,
            "p6": full_metrics,
            "v7_1": teacher_full_metrics,
            "p6_episode_capture": p6_full_capture,
            "v7_1_episode_capture": v7_full_capture,
            "recent_slices_flat_start": slices,
        },
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
        "purge_days": PURGE_DAYS,
        "features": features,
        "targets": targets,
        "model": {
            "n_estimators": 600,
            "max_depth": 5,
            "min_samples_leaf": 6,
            "max_features": 0.75,
            "class_weight": "balanced",
            "random_state": RANDOM_STATE,
        },
        "policy": summary["policy"],
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

    p4 = load_module(P4_SCRIPT, "hype_p6_p4_validate")
    p5 = load_module(P5_SCRIPT, "hype_p6_p5_validate")
    train_diag, train_v6, train_engine, _, train_context = p4.load_dependencies(
        train_only=True
    )
    train_frame, train_episodes, _ = build_frame(p5, p4, train_engine, train_context)
    train_teacher = p4.run_teacher(
        train_diag, train_v6, train_engine, train_context, 0, TRAIN_DAYS
    )
    features = {key: list(value) for key, value in manifest["features"].items()}
    targets = {key: tuple(value) for key, value in manifest["targets"].items()}
    train_datasets = {
        "entry": build_entry_rows(
            train_context,
            train_frame,
            train_episodes,
            list(train_teacher.result.raw.trades),
            0,
            TRAIN_DAYS,
        ),
        "survival": build_survival_rows(train_frame, 0, TRAIN_DAYS),
        "reversal": build_reversal_rows(train_context, train_frame, 0, TRAIN_DAYS),
    }
    models = {
        head: fit_model(
            complete_rows(train_datasets[head], targets[head][0], targets[head][1], 0, TRAIN_DAYS),
            features[head],
            targets[head][0],
        )
        for head in train_datasets
    }

    diag, v6, engine, _, context = p4.load_dependencies(train_only=False)
    if context.book.count != TOTAL_DAYS:
        raise RuntimeError("P6 validation context length drift")
    frame, episodes, _ = build_frame(p5, p4, engine, context)
    teacher = p4.run_teacher(diag, v6, engine, context, TRAIN_DAYS, TOTAL_DAYS)
    teacher_trades = list(teacher.result.raw.trades)
    datasets = {
        "entry": build_entry_rows(
            context, frame, episodes, teacher_trades, TRAIN_DAYS, TOTAL_DAYS
        ),
        "survival": build_survival_rows(frame, TRAIN_DAYS, TOTAL_DAYS),
        "reversal": build_reversal_rows(context, frame, TRAIN_DAYS, TOTAL_DAYS),
    }
    scores = score_bundle(models, datasets, features, TRAIN_DAYS, TOTAL_DAYS)
    head_metrics = {
        head: model_metrics(scores[head], targets[head][0], targets[head][1])
        for head in datasets
    }
    trades, decisions = apply_policy(
        p4,
        context,
        frame,
        teacher_trades,
        scores["entry"],
        scores["survival"],
        scores["reversal"],
        TRAIN_DAYS,
        TOTAL_DAYS,
    )
    metrics = p4.replay_metrics(v6, context, trades)
    teacher_metrics = p4.replay_metrics(v6, context, teacher_trades)
    trades = attach_replay_returns(trades, metrics)
    teacher_trades = attach_replay_returns(teacher_trades, teacher_metrics)
    p6_capture, p6_episodes = p5.episode_capture(
        context, episodes, trades, TRAIN_DAYS, TOTAL_DAYS
    )
    v7_capture, v7_episodes = p5.episode_capture(
        context, episodes, teacher_trades, TRAIN_DAYS, TOTAL_DAYS
    )
    won = bool(
        float(metrics["net_return_pct"]) > float(teacher_metrics["net_return_pct"])
        and float(p6_capture["duration_weighted_capture"])
        > float(v7_capture["duration_weighted_capture"])
        and float(metrics["chronological_1h_mdd_pct"])
        >= float(teacher_metrics["chronological_1h_mdd_pct"]) - 2.0
    )
    slices = recent_slices(
        p4,
        diag,
        v6,
        engine,
        context,
        p5,
        models,
        features,
        frame,
        episodes,
        TRAIN_DAYS,
        TOTAL_DAYS,
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
            "last_feature_day": pd.Timestamp(context.book.ts[-1]),
            "terminal": pd.Timestamp(context.book.terminal_ts),
            "days": TOTAL_DAYS - TRAIN_DAYS,
            "holdout_classification": "reused_holdout_not_clean_oos",
        },
        "head_metrics": head_metrics,
        "p6": metrics,
        "v7_1": teacher_metrics,
        "p6_episode_capture": p6_capture,
        "v7_1_episode_capture": v7_capture,
        "v7_1_beaten": won,
        "recent_slices_flat_start": slices,
    }
    paths = {
        "scores": ARTIFACT_DIR / f"{PREFIX}_validation_scores.csv",
        "decisions": ARTIFACT_DIR / f"{PREFIX}_validation_decisions.csv",
        "trades": ARTIFACT_DIR / f"{PREFIX}_validation_trades.csv",
        "teacher_trades": ARTIFACT_DIR / f"{PREFIX}_validation_v7_1_trades.csv",
        "episode_capture": ARTIFACT_DIR / f"{PREFIX}_validation_episode_capture.csv",
        "summary": ARTIFACT_DIR / f"{PREFIX}_validation_summary.json",
    }
    write_csv(
        paths["scores"],
        pd.concat([score.assign(head=head) for head, score in scores.items()], ignore_index=True, sort=False),
    )
    write_csv(paths["decisions"], decisions)
    write_csv(paths["trades"], trades)
    write_csv(paths["teacher_trades"], teacher_trades)
    write_csv(
        paths["episode_capture"],
        pd.concat(
            [p6_episodes.assign(strategy="P6"), v7_episodes.assign(strategy="V7.1")],
            ignore_index=True,
        ),
    )
    write_json(paths["summary"], summary)
    for path in paths.values():
        write_sidecar(path)
    return summary


def self_test() -> dict[str, Any]:
    assert ENTRY_THRESHOLD > EXTEND_START_THRESHOLD > SURVIVAL_EXIT_THRESHOLD
    assert REVERSAL_THRESHOLD > ENTRY_THRESHOLD
    assert LOW_SURVIVAL_CONFIRMATIONS == 2
    assert set(ELIGIBLE_CORE_EXITS).isdisjoint({"long_protective_stop", "short_protective_stop"})
    return {
        "status": "PASS",
        "three_heads": ["entry", "survival", "reversal"],
        "protective_stops_delegated": True,
    }


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
