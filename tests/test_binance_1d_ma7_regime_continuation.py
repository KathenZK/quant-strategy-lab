from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    ROOT
    / "research/asset-portfolios/1d-ma7-regime-continuation/scripts"
    / "research_binance_1d_ma7_regime_continuation.py"
)
SPEC = importlib.util.spec_from_file_location("binance_1d_ma7_rc", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_frozen_config_hash_and_identity() -> None:
    config = MODULE.validate_frozen_config()
    assert config["study_id"] == "BIN-1D-MA7-RC-P0"
    assert config["event"]["primary_ma_period"] == 7
    assert config["binning"]["threshold_search"] is False


def test_rolling_percentile_current_requires_full_finite_window() -> None:
    values = np.array([1.0, 3.0, 2.0, 4.0, 0.0])
    actual = MODULE.rolling_percentile_current(values, 3)
    expected = np.array([np.nan, np.nan, 2 / 3, 1.0, 1 / 3])
    np.testing.assert_allclose(actual, expected, equal_nan=True)

    with_missing = MODULE.rolling_percentile_current(
        np.array([1.0, np.nan, 2.0, 3.0]), 3
    )
    assert np.isnan(with_missing).all()


def test_assign_quintile_is_right_closed_at_internal_edges() -> None:
    values = pd.Series([-1.0, 0.2, 0.21, 0.4, 0.8, 2.0, np.nan])
    actual = MODULE.assign_quintile(values, [0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
    assert actual.tolist() == [1, 1, 2, 2, 4, 5, pd.NA]


def test_feature_block_matches_frozen_formulas() -> None:
    dates = pd.date_range("2020-01-01", periods=310, freq="D", tz="UTC")
    close = pd.Series(np.arange(100.0, 410.0))
    frame = pd.DataFrame(
        {
            "event_date": dates,
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "quote_volume": np.arange(1.0, 311.0),
        }
    )
    result = MODULE._feature_block(frame)
    row = result.iloc[309]
    assert row["atr14"] == pytest.approx(2.0)
    assert row["normalized_slope"] == pytest.approx(0.5)
    assert row["er20"] == pytest.approx(1.0)
    assert 0.0 < row["rv_percentile"] <= 1.0
    assert row["future_close_1"] != row["future_close_1"]


def test_build_events_uses_symmetric_trigger_and_directional_return() -> None:
    dates = pd.date_range("2024-01-01", periods=8, freq="D", tz="UTC")
    close = pd.Series([10.0, 9.0, 8.0, 12.0, 13.0, 8.0, 7.0, 6.0])
    panel = pd.DataFrame(
        {
            "symbol": ["X/USDT:USDT"] * 8,
            "base_asset": ["X"] * 8,
            "event_date": dates,
            "block_id": [1] * 8,
            "close": close,
            "atr14": [2.0] * 8,
            "normalized_slope": [0.1] * 8,
            "er20": [0.5] * 8,
            "rv20": [0.8] * 8,
            "rv_percentile": [0.5] * 8,
            "slope_q": pd.Series([3] * 8, dtype="Int64"),
            "er_q": pd.Series([3] * 8, dtype="Int64"),
            "rv_q": pd.Series([3] * 8, dtype="Int64"),
            "listing_age_days": [500] * 8,
            "adv30_median": [1_000_000.0] * 8,
            "liquidity_rank": [1.0] * 8,
            "liquidity_segment": ["major"] * 8,
            "market_phase": ["bull"] * 8,
            "calendar_year": [2024] * 8,
            "eligible_regime": [True] * 8,
        }
    )
    for period in MODULE.MA_PERIODS:
        panel[f"sma{period}"] = [10.0] * 8
    for horizon in MODULE.HORIZONS:
        panel[f"future_close_{horizon}"] = close.shift(-horizon)
    events = MODULE.build_events(panel)
    long_event = events.loc[
        events["ma_period"].eq(7) & events["direction"].eq("long")
    ].iloc[0]
    short_event = events.loc[
        events["ma_period"].eq(7)
        & events["direction"].eq("short")
        & events["event_date"].eq(dates[5])
    ].iloc[0]
    assert long_event["event_date"] == dates[3]
    assert long_event["raw_return_1"] == pytest.approx(13.0 / 12.0 - 1.0)
    assert long_event["atr_return_1"] == pytest.approx(0.5)
    assert short_event["event_date"] == dates[5]
    assert short_event["raw_return_1"] == pytest.approx(1.0 - 7.0 / 8.0)
    assert short_event["atr_return_1"] == pytest.approx(0.5)


def test_two_way_cluster_inference_and_bh_are_finite_and_monotone() -> None:
    values = pd.Series([0.01, 0.02, -0.01, 0.03, 0.00, 0.02])
    symbols = pd.Series(["A", "A", "B", "B", "C", "C"])
    dates = pd.Series(pd.date_range("2024-01-01", periods=3, tz="UTC").repeat(2))
    result = MODULE.infer_mean(values, symbols, dates)
    assert result["sample_count"] == 6
    assert result["symbol_count"] == 3
    assert result["event_date_count"] == 3
    assert result["mean"] == pytest.approx(values.mean())
    assert np.isfinite(result["cluster_se"])

    adjusted = MODULE.benjamini_hochberg(pd.Series([0.01, 0.04, 0.03, 0.20]))
    assert adjusted.tolist() == pytest.approx([0.04, 0.0533333333, 0.0533333333, 0.20])
    assert (adjusted >= pd.Series([0.01, 0.04, 0.03, 0.20])).all()


def test_grouped_bh_transform_preserves_original_row_index() -> None:
    frame = pd.DataFrame(
        {
            "group": ["A", "B", "A", "B"],
            "p_value": [0.01, 0.20, 0.04, 0.30],
        },
        index=[7, 3, 11, 5],
    )
    adjusted = frame.groupby("group", group_keys=False)["p_value"].transform(
        MODULE.benjamini_hochberg
    )
    assert adjusted.index.tolist() == [7, 3, 11, 5]
    assert adjusted.tolist() == pytest.approx([0.02, 0.30, 0.04, 0.30])
