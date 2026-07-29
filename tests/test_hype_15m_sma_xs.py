from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
ENGINE_PATH = (
    ROOT / "research/hype/15m-sma-crossover-slope/scripts/sma_xs_engine.py"
)
SPEC = importlib.util.spec_from_file_location("hype_15m_sma_xs_engine_test", ENGINE_PATH)
assert SPEC is not None and SPEC.loader is not None
ENGINE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ENGINE
SPEC.loader.exec_module(ENGINE)


def _book(rows: int = 16) -> object:
    ts = pd.date_range("2026-01-01", periods=rows, freq="15min", tz="UTC")
    return ENGINE.FeatureBook(
        ts=ts,
        terminal_ts=ts[-1] + pd.Timedelta(minutes=15),
        open=np.full(rows, 100.0),
        high=np.full(rows, 100.5),
        low=np.full(rows, 99.5),
        close=np.full(rows, 100.0),
        volume=np.ones(rows),
        atr=np.ones(rows),
        funding_by_bar=np.zeros(rows),
        source_start=ts[0],
    )


def _states(values: list[int], reasons: list[str] | None = None) -> object:
    rows = len(values)
    zeros = np.zeros(rows)
    falses = np.zeros(rows, dtype=bool)
    return ENGINE.StateBook(
        desired_state=np.asarray(values, dtype="int8"),
        sma_fast=zeros.copy(),
        sma_slow=zeros.copy(),
        fast_slope=zeros.copy(),
        normalized_gap=zeros.copy(),
        gap_slope=zeros.copy(),
        golden_cross=falses.copy(),
        dead_cross=falses.copy(),
        transition_reason=reasons or ["test"] * rows,
    )


def test_closed_cross_executes_on_next_open() -> None:
    book = _book()
    states = _states([0, 1, 1, 0] + [0] * 12)
    result = ENGINE.run_backtest(book, ENGINE.Config(), states=states)
    assert len(result.trades) == 1
    assert result.trades[0]["signal_ts"] == "2026-01-01T00:15:00+00:00"
    assert result.trades[0]["entry_ts"] == "2026-01-01T00:30:00+00:00"
    assert result.trades[0]["exit_ts"] == "2026-01-01T01:00:00+00:00"


def test_slope_exit_stays_flat_until_fresh_cross() -> None:
    close = np.r_[np.arange(1.0, 10.0), np.arange(9.0, 0.0, -1.0), np.arange(1.0, 10.0)]
    atr = np.ones(len(close))
    config = ENGINE.Config(
        fast_window=2,
        slow_window=4,
        slope_window=1,
        exit_confirm_bars=1,
        exit_mode="fast_slope",
    )
    states = ENGINE.generate_states(close, atr, config)
    exits = [
        index
        for index, reason in enumerate(states.transition_reason)
        if reason == "fast_slope_exit"
    ]
    assert exits
    first_exit = exits[0]
    next_crosses = np.flatnonzero(
        (states.golden_cross | states.dead_cross)
        & (np.arange(len(close)) > first_exit)
    )
    assert len(next_crosses)
    assert np.all(states.desired_state[first_exit:next_crosses[0]] == 0)


def test_future_mutation_does_not_change_prior_states() -> None:
    rng = np.random.default_rng(23)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.01, 500)))
    changed = close.copy()
    changed[400:] *= np.linspace(1.0, 3.0, 100)
    atr = np.ones(500)
    config = ENGINE.Config(exit_mode="hybrid_both")
    left = ENGINE.generate_states(close, atr, config).desired_state
    right = ENGINE.generate_states(changed, atr, config).desired_state
    np.testing.assert_array_equal(left[:400], right[:400])


def test_invalid_cost_is_rejected() -> None:
    with pytest.raises(ValueError, match="costs"):
        ENGINE.Config(fee_per_fill=-0.01).validate()
