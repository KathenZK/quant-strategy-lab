from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    ROOT
    / "research/asset-portfolios/1d-trend-prebreakout-state-atlas/scripts"
    / "run_binance_1d_trend_prebreakout_state_atlas_p0.py"
)
SPEC = importlib.util.spec_from_file_location("binance_1d_tpsa_p0", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_frozen_config_hash_and_primary_boundaries() -> None:
    actual = hashlib.sha256(MODULE.CONFIG_PATH.read_bytes()).hexdigest()
    assert actual == MODULE.EXPECTED_CONFIG_SHA256
    assert MODULE.PRIMARY_MA_PERIODS == (7, 30)
    assert not any(
        feature.startswith(("future_", "trigger_")) for feature in MODULE.ML_FEATURES
    )


def _synthetic_block() -> pd.DataFrame:
    count = 180
    index = np.arange(count, dtype=float)
    close = 100.0 * np.exp(0.001 * index + 0.025 * np.sin(index / 4.0))
    dates = pd.date_range("2020-01-01", periods=count, freq="D", tz="UTC")
    return pd.DataFrame(
        {
            "symbol": "TEST/USDT:USDT",
            "base_asset": "TEST",
            "event_date": dates,
            "block_id": 1,
            "open": close * 0.999,
            "high": close * 1.015,
            "low": close * 0.985,
            "close": close,
            "quote_volume": 1_000_000.0 + index * 100.0,
            "listing_age_days": index.astype(int),
            "is_complete_day": True,
        }
    )


def test_prestate_at_t_ignores_trigger_day_and_future_changes() -> None:
    original = _synthetic_block()
    changed = original.copy()
    changed.loc[120:, ["open", "high", "low", "close"]] *= 4.0
    changed.loc[120:, "quote_volume"] *= 10.0

    first = MODULE.feature_block(original)
    second = MODULE.feature_block(changed)
    prestate_columns = [
        "atr20_pre",
        "atr_pct_pre",
        "raw_return_60_pre_atr",
        "raw_prior_50_return_atr",
        "raw_recent_10_return_atr",
        "raw_location_60",
        "er60_pre",
        "return_sign_flips_20_pre",
        "range_ratio_10_60_pre",
        "atr_level_percentile_60_pre",
        "atr_path_percentile_60_pre",
        "rv10_rv60_pre",
    ]
    np.testing.assert_allclose(
        first.loc[120, prestate_columns].to_numpy(dtype=float),
        second.loc[120, prestate_columns].to_numpy(dtype=float),
        equal_nan=True,
    )
    assert first.loc[120, "trigger_return_atr"] != second.loc[120, "trigger_return_atr"]


def test_readable_hypotheses_cover_crash_repair_and_surge_base() -> None:
    rows = pd.DataFrame(
        {
            "aligned_prior_50_return_atr": [-4.0, -4.0],
            "aligned_recent_10_return_atr": [2.0, 0.0],
            "aligned_repair_from_adverse_60_atr": [2.0, 0.5],
            "aligned_max_adverse_excursion_60_atr": [6.0, 6.0],
            "range_ratio_10_60_pre": [0.50, 0.25],
            "er20_pre": [0.30, 0.20],
            "er60_pre": [0.30, 0.20],
            "return_sign_flips_20_pre": [5.0, 9.0],
            "atr_level_percentile_60_pre": [0.50, 0.10],
            "atr_path_percentile_60_pre": [0.50, 0.10],
        }
    )
    labeled = MODULE.add_state_labels(rows)
    assert labeled.loc[0, "hyp_OPPOSITE_SHOCK_THEN_REPAIR"]
    assert labeled.loc[1, "hyp_OPPOSITE_MOVE_THEN_BASE"]
    assert labeled.loc[0, "prior_move_state"] == "LARGE_ADVERSE"
    assert labeled.loc[0, "recent_move_state"] == "FAVORABLE"


def test_movement_buckets_are_fixed_and_ordered() -> None:
    values = pd.Series([-4.0, -2.0, 0.0, 2.0, 4.0])
    assert MODULE.movement_state(values).tolist() == [
        "LARGE_ADVERSE",
        "ADVERSE",
        "FLAT",
        "FAVORABLE",
        "LARGE_FAVORABLE",
    ]


def test_barrier_label_uses_first_hit_order() -> None:
    close = np.asarray([100.0, 102.1, 98.0, 101.0, 101.0])
    atr_pre = np.ones(len(close))
    result = MODULE._forward_path_arrays(close, atr_pre, horizon=4)
    assert result["barrier_long"][0] == 1.0
    assert result["barrier_short"][0] == 0.0

    reverse = np.asarray([100.0, 97.9, 102.5, 99.0, 99.0])
    result = MODULE._forward_path_arrays(reverse, atr_pre, horizon=4)
    assert result["barrier_long"][0] == 0.0
    assert result["barrier_short"][0] == 1.0
