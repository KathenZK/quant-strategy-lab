from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
ENGINE_PATH = ROOT / "research/hype/1d-ma7-asymmetric-body-trend/scripts/hype_1d_ma7_v6_delayed_episode_engine.py"


def load_engine():
    spec = importlib.util.spec_from_file_location("hype_dtec_engine_test", ENGINE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def synthetic(close, ma7=None, atr7=None):
    close = np.asarray(close, dtype=float)
    ma7 = np.asarray(ma7 if ma7 is not None else np.ones(len(close)) * 10.0, dtype=float)
    atr7 = np.asarray(atr7 if atr7 is not None else np.ones(len(close)), dtype=float)
    book = SimpleNamespace(close=close)
    features = SimpleNamespace(ma7=ma7, atr7=atr7)
    long_config = SimpleNamespace(side=1)
    short_config = SimpleNamespace(side=-1)
    return book, features, long_config, short_config


def params(engine, **overrides):
    values = {
        "persistence_days": 3,
        "slope_lookback": 2,
        "slope_min_atr": 0.0,
        "max_distance_atr": 1.0,
        "max_age_days": 10,
    }
    values.update(overrides)
    return engine.EpisodeParams(**values)


def signal(engine, close, *, long=True, short=False, native=None, **overrides):
    book, features, long_config, short_config = synthetic(close)
    config = engine.DTECConfig(
        "T",
        long=params(engine, **overrides) if long else None,
        short=params(engine, **overrides) if short else None,
    )
    native = native or (lambda *_args: False)
    instance = engine.DelayedEpisodeSignal(
        SimpleNamespace(), native, long_config, short_config, config
    )
    return instance, book, features, long_config, short_config


def test_frozen_grid_has_576_per_side_and_v6_hash():
    engine = load_engine()
    assert len(engine.single_side_configs(1)) == 576
    assert len(engine.single_side_configs(-1)) == 576
    assert engine._PEHC.config_sha256(engine.fixed_v6_config()) == engine.V6_CONFIG_SHA256


def test_cross_arms_then_confirms_only_after_persistence():
    engine = load_engine()
    instance, book, features, long_config, _ = signal(
        engine, [9.8, 10.1, 10.2, 10.3]
    )
    assert not instance(long_config, book, features, 1)
    assert not instance(long_config, book, features, 2)
    assert instance(long_config, book, features, 3)
    confirms = [row for row in instance.events if row["event"] == "confirm_delayed_episode"]
    assert len(confirms) == 1
    assert confirms[0]["age"] == 2


def test_recross_equality_cancels_episode():
    engine = load_engine()
    instance, book, features, long_config, _ = signal(
        engine, [9.8, 10.1, 10.0, 10.2]
    )
    for index in (1, 2, 3):
        assert not instance(long_config, book, features, index)
    assert any(row["event"] == "cancel_recross_ma7" for row in instance.events)


def test_distance_cap_is_inclusive_and_slope_threshold_is_inclusive():
    engine = load_engine()
    instance, book, features, long_config, _ = signal(
        engine,
        [9.8, 10.2, 10.75],
        persistence_days=2,
        slope_lookback=2,
        slope_min_atr=0.0,
        max_distance_atr=0.75,
    )
    assert not instance(long_config, book, features, 1)
    assert instance(long_config, book, features, 2)


def test_native_v6_signal_has_precedence_and_cancels_episode():
    engine = load_engine()
    calls = {2: True}

    def native(config, _book, _features, index):
        return bool(config.side == 1 and calls.get(index, False))

    instance, book, features, long_config, _ = signal(
        engine, [9.8, 10.1, 10.2], native=native
    )
    assert not instance(long_config, book, features, 1)
    assert instance(long_config, book, features, 2)
    assert any(row["event"] == "cancel_native_precedence" for row in instance.events)
    assert not any(row["event"] == "confirm_delayed_episode" for row in instance.events)


def test_gap_in_calls_cannot_carry_episode_through_position_or_cooldown():
    engine = load_engine()
    instance, book, features, long_config, _ = signal(
        engine, [9.8, 10.1, 10.2, 10.3, 10.4]
    )
    assert not instance(long_config, book, features, 1)
    assert not instance(long_config, book, features, 4)
    assert any(row["event"] == "cancel_call_gap" for row in instance.events)


def test_invalid_frozen_parameter_is_rejected():
    engine = load_engine()
    with pytest.raises(ValueError, match="persistence_days"):
        engine.EpisodeParams(6, 2, 0.0, 1.0, 10)
