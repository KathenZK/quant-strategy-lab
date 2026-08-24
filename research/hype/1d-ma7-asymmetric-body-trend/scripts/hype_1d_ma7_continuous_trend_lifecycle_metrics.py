"""Outcome-independent state-path metrics for the CTLS research branch."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from typing import Any, Iterable

import numpy as np
import pandas as pd


LABELS = (
    "neutral",
    "chop",
    "up_slow",
    "up_established",
    "up_accelerating",
    "up_decelerating",
    "down_slow",
    "down_established",
    "down_accelerating",
    "down_decelerating",
)
PHASE_CHANGE_LABELS = (
    "up_accelerating",
    "up_decelerating",
    "down_accelerating",
    "down_decelerating",
)


def _direction(label: str) -> int:
    if label.startswith("up_"):
        return 1
    if label.startswith("down_"):
        return -1
    return 0


def _recall(y_true: list[str], y_pred: list[str], label: str) -> float:
    relevant = sum(value == label for value in y_true)
    if relevant == 0:
        return math.nan
    return sum(left == label and right == label for left, right in zip(y_true, y_pred, strict=True)) / relevant


def _f1(y_true: list[str], y_pred: list[str], label: str) -> float:
    tp = sum(left == label and right == label for left, right in zip(y_true, y_pred, strict=True))
    fp = sum(left != label and right == label for left, right in zip(y_true, y_pred, strict=True))
    fn = sum(left == label and right != label for left, right in zip(y_true, y_pred, strict=True))
    denominator = 2 * tp + fp + fn
    return 0.0 if denominator == 0 else 2.0 * tp / denominator


def state_path_sha256(rows: Iterable[dict[str, Any]]) -> str:
    payload = [
        {
            "ts": str(row["ts"]),
            "direction": int(row["direction"]),
            "phase": str(row["phase"]),
            "label": str(row["label"]),
            "transition": str(row["transition"]),
        }
        for row in rows
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def evaluate_state_path(
    rows: Iterable[dict[str, Any]],
    truth: pd.Series,
    *,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
    boundary_days: int = 3,
) -> dict[str, Any]:
    """Evaluate one cold-flat state path without crossing label boundaries."""

    start = pd.Timestamp(start_ts)
    end = pd.Timestamp(end_ts)
    if start.tz is None or end.tz is None or start >= end:
        raise ValueError("metric window requires ordered timezone-aware timestamps")
    eligible_start = start + pd.Timedelta(days=boundary_days)
    eligible_end = end - pd.Timedelta(days=boundary_days)
    row_list = [dict(row) for row in rows]
    by_ts = {pd.Timestamp(row["ts"]): row for row in row_list}
    if len(by_ts) != len(row_list):
        raise ValueError("state rows contain duplicate timestamps")
    y_true: list[str] = []
    y_pred: list[str] = []
    timestamps: list[pd.Timestamp] = []
    for ts, actual in truth.items():
        timestamp = pd.Timestamp(ts)
        if timestamp < eligible_start or timestamp >= eligible_end or pd.isna(actual):
            continue
        predicted = by_ts.get(timestamp)
        if predicted is None:
            continue
        actual_label = str(actual)
        predicted_label = str(predicted["label"])
        if actual_label not in LABELS or predicted_label not in LABELS:
            raise ValueError("unknown CTLS state label")
        timestamps.append(timestamp)
        y_true.append(actual_label)
        y_pred.append(predicted_label)
    if not y_true:
        raise RuntimeError("state metric window has no eligible labeled rows")

    true_direction = [_direction(value) for value in y_true]
    predicted_direction = [_direction(value) for value in y_pred]
    direction_recalls: dict[str, float] = {}
    for value, name in ((-1, "down"), (0, "flat"), (1, "up")):
        relevant = sum(row == value for row in true_direction)
        direction_recalls[name] = (
            sum(left == value and right == value for left, right in zip(true_direction, predicted_direction, strict=True)) / relevant
            if relevant
            else math.nan
        )
    available_direction = [value for value in direction_recalls.values() if math.isfinite(value)]
    balanced_accuracy = float(np.mean(available_direction)) if available_direction else math.nan
    label_f1 = {label: _f1(y_true, y_pred, label) for label in LABELS}
    phase_f1 = {label: label_f1[label] for label in PHASE_CHANGE_LABELS}
    direction_flips = sum(
        left != right
        for left, right in zip(predicted_direction, predicted_direction[1:], strict=False)
    )
    return {
        "start_ts": start.isoformat(),
        "end_ts": end.isoformat(),
        "eligible_start_ts": eligible_start.isoformat(),
        "eligible_end_ts": eligible_end.isoformat(),
        "samples": len(y_true),
        "direction_balanced_accuracy": balanced_accuracy,
        "direction_recalls": direction_recalls,
        "macro_f1_10": float(np.mean(list(label_f1.values()))),
        "label_f1": label_f1,
        "slow_up_recall": _recall(y_true, y_pred, "up_slow"),
        "slow_down_recall": _recall(y_true, y_pred, "down_slow"),
        "accel_decel_macro_f1": float(np.mean(list(phase_f1.values()))),
        "accel_decel_f1": phase_f1,
        "direction_flip_rate": direction_flips / max(1, len(predicted_direction) - 1),
        "true_counts": dict(sorted(Counter(y_true).items())),
        "predicted_counts": dict(sorted(Counter(y_pred).items())),
        "first_ts": timestamps[0].isoformat(),
        "last_ts": timestamps[-1].isoformat(),
    }


def aggregate_gate(metrics: dict[str, Any], blocks: Iterable[dict[str, Any]]) -> dict[str, Any]:
    block_rows = list(blocks)
    checks = {
        "balanced_accuracy_ge_055": metrics["direction_balanced_accuracy"] >= 0.55,
        "macro_f1_ge_035": metrics["macro_f1_10"] >= 0.35,
        "slow_up_recall_ge_035": metrics["slow_up_recall"] >= 0.35,
        "slow_down_recall_ge_035": metrics["slow_down_recall"] >= 0.35,
        "accel_decel_macro_f1_ge_025": metrics["accel_decel_macro_f1"] >= 0.25,
        "flip_rate_le_015": metrics["direction_flip_rate"] <= 0.15,
        "four_of_six_blocks_balanced_accuracy_ge_050": sum(
            row["direction_balanced_accuracy"] >= 0.50 for row in block_rows
        )
        >= 4,
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "passing_blocks": sum(
            row["direction_balanced_accuracy"] >= 0.50 for row in block_rows
        ),
    }
