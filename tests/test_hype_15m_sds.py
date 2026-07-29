from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
ENGINE_PATH = (
    ROOT / "research/hype/15m-sequential-drift-state/scripts/sds_engine.py"
)
SPEC = importlib.util.spec_from_file_location("hype_15m_sds_engine_test", ENGINE_PATH)
assert SPEC is not None and SPEC.loader is not None
ENGINE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ENGINE
SPEC.loader.exec_module(ENGINE)


def _synthetic_book() -> object:
    rows = 12
    ts = pd.date_range("2026-01-01", periods=rows, freq="15min", tz="UTC")
    open_values = np.full(rows, 100.0)
    high = np.full(rows, 100.5)
    low = np.full(rows, 99.5)
    close = np.full(rows, 100.0)
    return ENGINE.FeatureBook(
        ts=ts,
        terminal_ts=ts[-1] + pd.Timedelta(minutes=15),
        open=open_values,
        high=high,
        low=low,
        close=close,
        volume=np.ones(rows),
        atr=np.ones(rows),
        funding_by_bar=np.zeros(rows),
        source_start=ts[0],
    )


def _states(values: list[int]) -> object:
    rows = len(values)
    zeros = np.zeros(rows)
    return ENGINE.StateBook(
        desired_state=np.asarray(values, dtype="int8"),
        normalized_return=zeros.copy(),
        fast_drift=zeros.copy(),
        slow_drift=zeros.copy(),
        efficiency_ratio=zeros.copy(),
        positive_cusum=zeros.copy(),
        negative_cusum=zeros.copy(),
        transition_reason=["test"] * rows,
    )


def test_leverage_above_three_is_rejected() -> None:
    with pytest.raises(ValueError, match="leverage"):
        ENGINE.Config(leverage=3.01).validate()


def test_closed_bar_state_executes_on_next_open() -> None:
    book = _synthetic_book()
    states = _states([0, 1, 1, 0] + [0] * 8)
    result = ENGINE.run_backtest(book, ENGINE.Config(), states=states)
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade["signal_ts"] == "2026-01-01T00:15:00+00:00"
    assert trade["entry_ts"] == "2026-01-01T00:30:00+00:00"
    assert trade["exit_ts"] == "2026-01-01T01:00:00+00:00"
    assert trade["exit_reason"] == "state_exit"


def test_stop_lock_blocks_same_episode_reentry() -> None:
    book = _synthetic_book()
    book.low[2] = 90.0
    states = _states([0, 1, 1, 1, 0, 1, 1, 0, 0, 0, 0, 0])
    result = ENGINE.run_backtest(book, ENGINE.Config(stop_atr=2.0), states=states)
    assert len(result.trades) == 2
    assert result.trades[0]["exit_reason"] == "emergency_stop"
    assert result.trades[1]["entry_ts"] == "2026-01-01T01:30:00+00:00"


def test_future_mutation_does_not_change_prior_states() -> None:
    rng = np.random.default_rng(7)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.01, 500)))
    changed = close.copy()
    changed[400:] *= np.linspace(1.0, 5.0, 100)
    left = ENGINE.generate_states(close, ENGINE.Config()).desired_state
    right = ENGINE.generate_states(changed, ENGINE.Config()).desired_state
    np.testing.assert_array_equal(left[:400], right[:400])
