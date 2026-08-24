from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
ENGINE_PATH = ROOT / (
    "research/hype/1d-ma7-asymmetric-body-trend/scripts/"
    "hype_1d_ma7_ctls_r2_continuous_strength_engine.py"
)


def load_engine():
    spec = importlib.util.spec_from_file_location("ctls_r2_engine_tested", ENGINE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def strength_config(engine, **updates):
    values = {
        "z_scale": 0.5,
        "slope_scale": 0.08,
        "drift_scale": 0.10,
        "weight_template": "equal",
        "enter_q": 0.35,
        "exit_q": 0.05,
        "enter_confirm_days": 1,
    }
    values.update(updates)
    return engine.StrengthConfig(**values)


def feature(engine, day: int, *, z: float, s3: float, d3: float, er: float, d1: float | None = None, s1: float | None = None):
    d1 = d3 if d1 is None else d1
    s1 = s3 if s1 is None else s1
    return engine.StrengthFeatures(
        ts=pd.Timestamp("2026-01-01", tz="UTC") + pd.Timedelta(days=day),
        close=100.0 + z,
        ma7=100.0,
        atr7=1.0,
        z=z,
        s1=s1,
        s3=s3,
        d1=d1,
        d3=d3,
        er7=er,
        ma_curvature=s1 - s3,
        drift_curvature=d1 - d3,
    )


def test_frozen_r2_grids_have_exact_cardinality() -> None:
    engine = load_engine()
    assert len(engine.direction_grid()) == len(set(engine.direction_grid())) == 1944
    assert len(engine.phase_grid()) == len(set(engine.phase_grid())) == 81


def test_strength_is_directionally_symmetric() -> None:
    engine = load_engine()
    config = strength_config(engine)
    up = feature(engine, 0, z=0.4, s3=0.08, d3=0.1, er=0.5)
    down = feature(engine, 0, z=-0.4, s3=-0.08, d3=-0.1, er=-0.5)
    assert engine.strength(up, config) == -engine.strength(down, config)


def test_hysteresis_can_return_to_flat_instead_of_holding_one_residual_vote() -> None:
    engine = load_engine()
    machine = engine.ContinuousStrengthMachine(strength_config(engine))
    entered = machine.observe(feature(engine, 0, z=0.5, s3=0.1, d3=0.1, er=0.6))
    first_loss = machine.observe(feature(engine, 1, z=0.01, s3=0.0, d3=0.0, er=0.0))
    flat = machine.observe(feature(engine, 2, z=0.01, s3=0.0, d3=0.0, er=0.0))
    assert entered.direction == engine.Direction.UP
    assert first_loss.direction == engine.Direction.UP and first_loss.loss_run == 1
    assert flat.direction == engine.Direction.FLAT
    assert flat.transition == "direction_loss"


def test_slow_phase_has_priority_over_noisy_acceleration() -> None:
    engine = load_engine()
    machine = engine.ContinuousStrengthMachine(
        strength_config(engine),
        engine.PhaseConfig(
            velocity_source="blend",
            accel_source="blend",
            slow_threshold=0.10,
            accel_threshold=0.02,
        ),
    )
    snapshot = machine.observe(
        feature(engine, 0, z=0.5, s3=0.04, d3=0.04, er=0.6, s1=0.20, d1=0.20)
    )
    assert snapshot.direction == engine.Direction.UP
    assert snapshot.acceleration > 0.02
    assert snapshot.phase == engine.Phase.SLOW


def test_acceleration_sources_are_explicit_and_causal() -> None:
    engine = load_engine()
    row = feature(engine, 0, z=0.5, s3=0.15, d3=0.15, er=0.6, s1=0.09, d1=0.35)
    ma_machine = engine.ContinuousStrengthMachine(
        strength_config(engine),
        engine.PhaseConfig(accel_source="ma_curvature", accel_threshold=0.05),
    )
    drift_machine = engine.ContinuousStrengthMachine(
        strength_config(engine),
        engine.PhaseConfig(accel_source="drift_curvature", accel_threshold=0.05),
    )
    assert ma_machine.observe(row).phase == engine.Phase.DECELERATING
    assert drift_machine.observe(row).phase == engine.Phase.ACCELERATING


def test_feature_history_is_unchanged_when_only_future_prices_change() -> None:
    engine = load_engine()
    index = pd.date_range("2026-01-01", periods=15, tz="UTC", freq="D")
    frame = pd.DataFrame(
        {
            "close": np.linspace(100.0, 114.0, 15),
            "ma7": np.linspace(99.0, 106.0, 15),
            "atr7": 2.0,
        },
        index=index,
    )
    changed = frame.copy()
    changed.loc[index[12] :, "close"] *= 2.0
    pd.testing.assert_frame_equal(
        engine.build_features(frame).loc[: index[11]],
        engine.build_features(changed).loc[: index[11]],
    )
