from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
METRICS_PATH = ROOT / (
    "research/hype/1d-ma7-asymmetric-body-trend/scripts/"
    "hype_1d_ma7_continuous_trend_lifecycle_metrics.py"
)


def load_metrics():
    spec = importlib.util.spec_from_file_location("ctls_metrics_tested", METRICS_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def rows(index: pd.DatetimeIndex, labels: list[str]):
    result = []
    for ts, label in zip(index, labels, strict=True):
        direction = 1 if label.startswith("up_") else -1 if label.startswith("down_") else 0
        phase = label.split("_", 1)[1] if direction else label
        result.append(
            {
                "ts": ts.isoformat(),
                "direction": direction,
                "phase": phase,
                "label": label,
                "transition": "hold",
            }
        )
    return result


def test_perfect_path_has_perfect_available_recalls_and_boundary_exclusion() -> None:
    metrics = load_metrics()
    index = pd.date_range("2026-01-01", periods=20, tz="UTC", freq="D")
    cycle = list(metrics.LABELS)
    labels = (cycle * 2)[:20]
    truth = pd.Series(labels, index=index)
    result = metrics.evaluate_state_path(
        rows(index, labels),
        truth,
        start_ts=index[0],
        end_ts=index[-1] + pd.Timedelta(days=1),
    )
    assert result["samples"] == 14
    assert result["direction_balanced_accuracy"] == 1.0
    assert result["slow_up_recall"] == 1.0
    assert result["slow_down_recall"] == 1.0
    assert result["first_ts"] == index[3].isoformat()
    assert result["last_ts"] == index[-4].isoformat()


def test_fixed_ten_class_macro_f1_penalizes_collapsing_to_neutral() -> None:
    metrics = load_metrics()
    index = pd.date_range("2026-01-01", periods=30, tz="UTC", freq="D")
    labels = (list(metrics.LABELS) * 3)[:30]
    truth = pd.Series(labels, index=index)
    predicted = ["neutral"] * 30
    result = metrics.evaluate_state_path(
        rows(index, predicted),
        truth,
        start_ts=index[0],
        end_ts=index[-1] + pd.Timedelta(days=1),
    )
    assert result["macro_f1_10"] < 0.05
    assert result["direction_balanced_accuracy"] == pytest.approx(1.0 / 3.0)
    assert result["slow_up_recall"] == 0.0
    assert result["slow_down_recall"] == 0.0


def test_gate_requires_four_of_six_blocks_and_all_aggregate_checks() -> None:
    metrics = load_metrics()
    aggregate = {
        "direction_balanced_accuracy": 0.60,
        "macro_f1_10": 0.40,
        "slow_up_recall": 0.40,
        "slow_down_recall": 0.40,
        "accel_decel_macro_f1": 0.30,
        "direction_flip_rate": 0.10,
    }
    passing = [{"direction_balanced_accuracy": 0.51}] * 4
    failing = [{"direction_balanced_accuracy": 0.49}] * 2
    assert metrics.aggregate_gate(aggregate, [*passing, *failing])["status"] == "PASS"
    assert metrics.aggregate_gate(aggregate, [*passing[:3], *failing, *failing])["status"] == "FAIL"

