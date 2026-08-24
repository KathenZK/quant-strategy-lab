from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
ENGINE_PATH = ROOT / (
    "research/hype/1d-ma7-asymmetric-body-trend/scripts/"
    "hype_1d_ma7_continuous_trend_lifecycle_engine.py"
)


def load_engine():
    spec = importlib.util.spec_from_file_location("ctls_engine_tested", ENGINE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def feature(engine, day: int, *, z: float, s1: float, s3: float, d3: float, er: float):
    return engine.CausalFeatures(
        ts=pd.Timestamp("2026-01-01", tz="UTC") + pd.Timedelta(days=day),
        close=100.0 + z,
        ma7=100.0,
        atr7=1.0,
        z=z,
        s1=s1,
        s3=s3,
        d3=d3,
        er7=er,
        acceleration=s1 - s3,
    )


def config(engine, **kwargs):
    values = {
        "distance_min": 0.0,
        "slow_slope_min": 0.0,
        "drift_min": 0.0,
        "er_min": 0.1,
        "direction_score_min": 2,
        "enter_confirm_days": 2,
    }
    values.update(kwargs)
    return engine.DetectionConfig(**values)


def test_frozen_detection_grid_has_324_unique_configs() -> None:
    engine = load_engine()
    grid = engine.detection_grid()
    assert len(grid) == 324
    assert len(set(grid)) == 324


def test_causal_features_do_not_change_when_only_future_changes() -> None:
    engine = load_engine()
    index = pd.date_range("2026-01-01", periods=14, tz="UTC", freq="D")
    frame = pd.DataFrame(
        {
            "close": np.linspace(100.0, 113.0, 14),
            "ma7": np.linspace(99.0, 105.5, 14),
            "atr7": np.full(14, 2.0),
        },
        index=index,
    )
    changed = frame.copy()
    changed.loc[index[11]:, "close"] *= 3.0
    original_features = engine.build_causal_features(frame)
    changed_features = engine.build_causal_features(changed)
    pd.testing.assert_frame_equal(
        original_features.loc[: index[10]], changed_features.loc[: index[10]]
    )


def test_slow_uptrend_enters_without_any_fresh_cross_event() -> None:
    engine = load_engine()
    machine = engine.ContinuousTrendMachine(config(engine))
    rows = [
        feature(engine, day, z=0.2 + day * 0.02, s1=0.04, s3=0.04, d3=0.05, er=0.4)
        for day in range(4)
    ]
    snapshots = [machine.observe(row) for row in rows]
    assert snapshots[1].direction == engine.Direction.UP
    assert snapshots[1].phase == engine.Phase.SLOW
    assert all(row.close > row.ma7 for row in rows)


def test_slow_downtrend_is_symmetric() -> None:
    engine = load_engine()
    machine = engine.ContinuousTrendMachine(config(engine))
    snapshots = [
        machine.observe(
            feature(engine, day, z=-0.2, s1=-0.04, s3=-0.04, d3=-0.05, er=-0.4)
        )
        for day in range(2)
    ]
    assert snapshots[-1].direction == engine.Direction.DOWN
    assert snapshots[-1].label == engine.StateLabel.DOWN_SLOW


def test_acceleration_deceleration_and_confirmed_reversal() -> None:
    engine = load_engine()
    machine = engine.ContinuousTrendMachine(config(engine, enter_confirm_days=1))
    up = machine.observe(feature(engine, 0, z=0.3, s1=0.16, s3=0.06, d3=0.1, er=0.5))
    decel = machine.observe(feature(engine, 1, z=0.2, s1=0.0, s3=0.06, d3=0.04, er=0.3))
    reverse_arm = machine.observe(
        feature(engine, 2, z=-0.3, s1=-0.12, s3=-0.08, d3=-0.1, er=-0.5)
    )
    reversed_ = machine.observe(
        feature(engine, 3, z=-0.4, s1=-0.12, s3=-0.08, d3=-0.1, er=-0.5)
    )
    assert up.phase == engine.Phase.ACCELERATING
    assert decel.phase == engine.Phase.DECELERATING
    assert reverse_arm.direction == engine.Direction.UP
    assert reversed_.direction == engine.Direction.DOWN
    assert reversed_.transition == "reverse_to_down"


def test_chop_and_nonconsecutive_data_fail_closed() -> None:
    engine = load_engine()
    machine = engine.ContinuousTrendMachine(
        config(engine, direction_score_min=3, enter_confirm_days=2)
    )
    snapshot = None
    for day, z in enumerate((0.05, -0.05, 0.05, -0.05, 0.05)):
        snapshot = machine.observe(
            feature(engine, day, z=z, s1=0.0, s3=0.0, d3=0.0, er=0.0)
        )
    assert snapshot is not None and snapshot.phase == engine.Phase.CHOP
    with pytest.raises(RuntimeError, match="consecutive"):
        machine.observe(feature(engine, 7, z=0.1, s1=0.1, s3=0.1, d3=0.1, er=0.5))


def test_hindsight_labels_use_only_interior_rows() -> None:
    engine = load_engine()
    index = pd.date_range("2026-01-01", periods=15, tz="UTC", freq="D")
    close = np.array([100, 100.2, 100.4, 101, 102, 104, 107, 111, 114, 116, 117, 117.5, 117.8, 118, 118.1])
    frame = pd.DataFrame(
        {"close": close, "ma7": pd.Series(close, index=index).rolling(7, min_periods=1).mean(), "atr7": 2.0},
        index=index,
    )
    labels = engine.hindsight_labels(frame)
    assert labels.iloc[:3].isna().all()
    assert labels.iloc[-3:].isna().all()
    assert labels.iloc[3:-3].notna().all()


def test_hindsight_neutral_label_requires_finite_center_ma_window() -> None:
    engine = load_engine()
    index = pd.date_range("2026-01-01", periods=15, tz="UTC", freq="D")
    frame = pd.DataFrame(
        {"close": 100.0, "ma7": 100.0, "atr7": 1.0},
        index=index,
    )
    frame.loc[index[:6], "ma7"] = np.nan
    labels = engine.hindsight_labels(frame)
    assert pd.isna(labels.loc[index[3]])
    assert labels.loc[index[9]] == engine.StateLabel.NEUTRAL.value
