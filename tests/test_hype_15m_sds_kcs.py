from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "research/hype/15m-sequential-drift-state/scripts"
sys.path.insert(0, str(SCRIPT_DIR))
SCRIPT_PATH = SCRIPT_DIR / "research_hype_15m_sds_kalman_cusum_structure.py"
SPEC = importlib.util.spec_from_file_location("hype_15m_sds_kcs_test", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
KCS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = KCS
SPEC.loader.exec_module(KCS)


def _book(close: np.ndarray) -> object:
    rows = len(close)
    ts = pd.date_range("2026-01-01", periods=rows, freq="15min", tz="UTC")
    return KCS.engine.FeatureBook(
        ts=ts,
        terminal_ts=ts[-1] + pd.Timedelta(minutes=15),
        open=close.copy(),
        high=close + 0.1,
        low=close - 0.1,
        close=close.copy(),
        volume=np.ones(rows),
        atr=np.ones(rows),
        funding_by_bar=np.zeros(rows),
        source_start=ts[0],
    )


def test_invalid_kalman_process_ratio_is_rejected() -> None:
    with pytest.raises(ValueError, match="process_ratio"):
        KCS.KCSConfig(kalman_process_ratio=0.0).validate()


def test_kalman_is_causal_under_future_mutation() -> None:
    rng = np.random.default_rng(41)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.008, 600)))
    changed = close.copy()
    changed[500:] *= np.linspace(1.0, 4.0, 100)
    config = KCS.KCSConfig()
    left = KCS.build_features(_book(close), config)
    right = KCS.build_features(_book(changed), config)
    np.testing.assert_allclose(
        left.kalman_slope[:500],
        right.kalman_slope[:500],
        equal_nan=True,
    )
    np.testing.assert_allclose(
        left.innovation_z[:500],
        right.innovation_z[:500],
        equal_nan=True,
    )


def test_structure_uses_only_prior_bars() -> None:
    close = np.linspace(100.0, 120.0, 300)
    book = _book(close)
    config = KCS.KCSConfig(structure_window=32, efficiency_window=32)
    features = KCS.build_features(book, config)
    expected = np.max(book.high[67:99])
    assert features.prior_high[99] == pytest.approx(expected)
    book.high[99] = 999.0
    changed = KCS.build_features(book, config)
    assert changed.prior_high[99] == pytest.approx(expected)


def test_state_machine_enters_only_after_structure_breakout() -> None:
    rows = 40
    close = np.full(rows, 100.0)
    close[30:] = np.linspace(100.0, 110.0, 10)
    book = _book(close)
    config = KCS.KCSConfig(
        structure_window=4,
        exit_window=2,
        efficiency_window=4,
        arm_timeout_bars=8,
    )
    values = np.full(rows, 2.0)
    prior_high = np.full(rows, 105.0)
    features = KCS.KCSFeatures(
        normalized_return=values.copy(),
        kalman_level=np.log(close),
        kalman_slope=np.full(rows, 0.01),
        kalman_slope_vol=np.full(rows, 0.2),
        kalman_slope_z=np.full(rows, 2.0),
        innovation_z=np.zeros(rows),
        efficiency=np.ones(rows),
        prior_high=prior_high,
        prior_low=np.full(rows, 95.0),
        exit_high=np.full(rows, 120.0),
        exit_low=np.full(rows, 90.0),
    )
    states = KCS.generate_kcs_states(book, config, features=features)
    breakout_indices = np.flatnonzero(close > prior_high)
    assert len(breakout_indices)
    first_active = int(np.flatnonzero(states.desired_state == 1)[0])
    assert first_active == int(breakout_indices[0])
