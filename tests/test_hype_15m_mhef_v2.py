from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
ENGINE_PATH = (
    ROOT
    / "research/hype/15m-multi-horizon-ema-forecast/scripts/mhef_v2_engine.py"
)
SPEC = importlib.util.spec_from_file_location("hype_15m_mhef_v2_engine", ENGINE_PATH)
assert SPEC is not None and SPEC.loader is not None
ENGINE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ENGINE
SPEC.loader.exec_module(ENGINE)


def _fixture_book(rows: int = 2400) -> ENGINE.MarketBook:
    ts = pd.date_range("2025-01-01", periods=rows, freq="15min", tz="UTC")
    log_price = (
        np.linspace(0.0, 0.7, rows)
        + 0.025 * np.sin(np.arange(rows) / 21.0)
        + 0.006 * np.sin(np.arange(rows) / 3.0)
    )
    close = 100.0 * np.exp(log_price)
    frame = pd.DataFrame(
        {
            "ts": ts,
            "open": close,
            "high": close * 1.002,
            "low": close * 0.998,
            "close": close,
        }
    )
    funding = pd.DataFrame(
        {
            "ts": pd.Series([], dtype="datetime64[ns, UTC]"),
            "funding_rate": pd.Series([], dtype="float64"),
        }
    )
    return ENGINE.MarketBook(
        frame=frame,
        funding=funding,
        terminal_ts=ts[-1] + pd.Timedelta(minutes=15),
    )


def test_forecasts_are_bounded_continuous_and_causal() -> None:
    book = _fixture_book()
    base = ENGINE.build_forecasts(book, ENGINE.BASELINE_CONFIG)
    changed_book = _fixture_book()
    changed_book.frame.loc[len(changed_book.frame) - 1, "close"] *= 1.5
    changed = ENGINE.build_forecasts(changed_book, ENGINE.BASELINE_CONFIG)

    component_columns = [
        f"forecast_{fast}_{slow}"
        for fast, slow in ENGINE.BASELINE_CONFIG.ema_pairs
    ]
    assert float(base[component_columns + ["target_close"]].abs().max().max()) <= 1.0
    pd.testing.assert_series_equal(
        base.loc[: len(base) - 2, "target_close"],
        changed.loc[: len(changed) - 2, "target_close"],
    )
    valid = base["target_close"].dropna()
    assert not valid.empty
    assert valid.nunique() > 100


def test_coherence_reduces_conflicted_forecast() -> None:
    book = _fixture_book()
    unfiltered = ENGINE.build_forecasts(
        book,
        ENGINE.Config(coherence_power=0.0, dead_zone=0.0),
    )
    filtered = ENGINE.build_forecasts(
        book,
        ENGINE.Config(coherence_power=1.0, dead_zone=0.0),
    )
    valid = unfiltered["target_close"].notna() & filtered["target_close"].notna()
    assert (
        filtered.loc[valid, "target_close"].abs()
        <= unfiltered.loc[valid, "target_close"].abs() + 1e-12
    ).all()


def test_boundary_tracker_moves_to_band_edge_and_respects_step() -> None:
    desired = pd.Series([0.0, 0.10, 0.40, 0.80, 0.50, -0.40])
    actual = ENGINE.boundary_track(
        desired,
        buffer=0.15,
        minimum_change=0.0,
        max_step=0.25,
        max_abs_position=1.0,
    )
    assert actual.tolist() == pytest.approx(
        [0.0, 0.0, 0.25, 0.50, 0.50, 0.25]
    )


def test_zero_buffer_and_large_step_tracks_target_exactly() -> None:
    desired = pd.Series([0.0, 0.2, -0.4, 0.7])
    actual = ENGINE.boundary_track(
        desired,
        buffer=0.0,
        minimum_change=0.0,
        max_step=2.0,
        max_abs_position=1.0,
    )
    assert actual.tolist() == pytest.approx(desired.tolist())


def test_minimum_change_accumulates_small_boundary_moves() -> None:
    desired = pd.Series([0.20, 0.22, 0.24, 0.27, 0.29])
    actual = ENGINE.boundary_track(
        desired,
        buffer=0.10,
        minimum_change=0.05,
        max_step=1.0,
        max_abs_position=1.0,
    )
    assert actual.tolist() == pytest.approx([0.10, 0.10, 0.10, 0.17, 0.17])


def test_backtest_uses_prior_closed_bar_and_charges_turnover() -> None:
    book = _fixture_book()
    config = ENGINE.Config(no_trade_buffer=0.0, max_position_step=2.0)
    features = ENGINE.build_forecasts(book, config)
    result = ENGINE.run_backtest(book, config)
    first_ts = pd.Timestamp(result.path["ts"].iloc[0])
    source_index = int(book.frame.index[book.frame["ts"] == first_ts][0])
    expected = float(features["target_close"].iloc[source_index - 1])
    assert float(result.path["desired_position"].iloc[0]) == pytest.approx(expected)
    assert (result.path["turnover"] >= 0.0).all()
    assert float(result.path["cost_amount"].sum()) > 0.0


def test_config_round_trip_keeps_tuple_identity() -> None:
    restored = ENGINE.config_from_payload(
        ENGINE.config_payload(ENGINE.BASELINE_CONFIG)
    )
    assert restored == ENGINE.BASELINE_CONFIG
    assert ENGINE.config_sha256(restored) == ENGINE.config_sha256(
        ENGINE.BASELINE_CONFIG
    )
