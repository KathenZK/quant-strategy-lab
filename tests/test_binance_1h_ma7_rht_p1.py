from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / (
    "research/asset-portfolios/1h-ma7-root-hazard-timing/scripts/"
    "research_binance_1h_ma7_rht_p1.py"
)


def load_script() -> Any:
    name = "test_binance_1h_ma7_rht_p1_script"
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(name, SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def synthetic_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    timestamps = pd.date_range("2024-01-01", periods=400, freq="1h", tz="UTC")
    close = 100.0 + np.linspace(0.0, 8.0, len(timestamps))
    hourly = pd.DataFrame(
        {
            "ts": timestamps,
            "open": close - 0.02,
            "high": close + 0.10,
            "low": close - 0.10,
            "close": close,
        }
    )
    funding_ts = timestamps[::8] + pd.Timedelta(milliseconds=5)
    funding = pd.DataFrame(
        {
            "ts": funding_ts,
            "funding_rate": np.full(len(funding_ts), 0.0001),
            "mark_price": np.interp(
                funding_ts.view("int64"),
                timestamps.view("int64"),
                close,
            ),
        }
    )
    return hourly, funding


def test_fast_outcome_matches_reference_path() -> None:
    script = load_script()
    hourly, funding = synthetic_inputs()
    cache = script._hourly_cache(hourly, funding)
    entry_index = 100
    recross_index = 180
    fast = script._fast_outcome(
        cache,
        entry_index=entry_index,
        recross_index=recross_index,
        admission_end_index=200,
        side=1,
        slippage=script.MAIN_SLIPPAGE,
        include_funding=True,
    )
    reference = script.hourly_trade_outcome(
        hourly,
        funding,
        entry_ts=pd.Timestamp(hourly.at[entry_index, "ts"]),
        recross_ts=pd.Timestamp(hourly.at[recross_index, "ts"]),
        admission_end=pd.Timestamp(hourly.at[200, "ts"]),
        side=1,
        slippage=script.MAIN_SLIPPAGE,
        include_funding=True,
    )
    assert fast is not None and reference is not None
    assert fast["entry_ts"] == reference["entry_ts"]
    assert fast["exit_ts"] == reference["exit_ts"]
    assert math.isclose(
        fast["direct_net_return"],
        reference["direct_net_return"],
        rel_tol=1e-12,
        abs_tol=1e-12,
    )


def test_fast_landmark_features_match_reference() -> None:
    script = load_script()
    hourly, funding = synthetic_inputs()
    cache = script._hourly_cache(hourly, funding)
    root_index = 100
    decision_index = 130
    side = 1
    atr = 2.0
    root_open = float(hourly.at[root_index, "open"])
    window = hourly.iloc[root_index:decision_index]
    root_mfe = (float(window["high"].max()) - root_open) / atr
    root_mae = max(0.0, (root_open - float(window["low"].min())) / atr)
    kwargs = {
        "side": side,
        "cross_atr": atr,
        "cross_distance": 0.2,
        "cross_slope_1": 0.03,
        "cross_slope_2": 0.05,
    }
    fast = script._fast_landmark_features(
        cache,
        decision_index=decision_index,
        root_start_index=root_index,
        age_hours=decision_index - root_index,
        root_mfe=root_mfe,
        root_mae=root_mae,
        **kwargs,
    )
    reference = script.landmark_features(
        hourly,
        funding,
        decision_ts=pd.Timestamp(hourly.at[decision_index, "ts"]),
        root_start=pd.Timestamp(hourly.at[root_index, "ts"]),
        age_hours=decision_index - root_index,
        **kwargs,
    )
    assert reference is not None
    for feature in script.FULL_FEATURES:
        assert math.isclose(
            fast[feature],
            reference[feature],
            rel_tol=1e-12,
            abs_tol=1e-12,
        ), feature


def test_first_hit_keeps_only_earliest_threshold_cross() -> None:
    script = load_script()
    rows = pd.DataFrame(
        {
            "root_id": ["A", "A", "A", "B", "B"],
            "decision_ts": pd.date_range(
                "2024-01-01", periods=5, freq="1h", tz="UTC"
            ),
            "probability": [0.49, 0.55, 0.70, 0.60, 0.40],
            "selected_threshold": [0.50] * 5,
        }
    )
    hits = script.first_hits(rows)
    assert hits["root_id"].tolist() == ["A", "B"]
    assert hits["probability"].tolist() == [0.55, 0.60]


def test_root_split_purges_information_end_and_hype_is_absent() -> None:
    script = load_script()
    first_test = pd.Timestamp("2024-03-01T00:00:00Z")
    roots = pd.DataFrame(
        {
            "root_start": [
                pd.Timestamp("2024-01-01T00:00:00Z"),
                pd.Timestamp("2024-02-01T00:00:00Z"),
                first_test,
            ],
            "root_information_end": [
                pd.Timestamp("2024-01-10T00:00:00Z"),
                pd.Timestamp("2024-02-28T00:00:00Z"),
                pd.Timestamp("2024-03-10T00:00:00Z"),
            ],
        }
    )
    train, test = script.split_roots_for_block(
        roots,
        first_test=first_test,
        last_test=pd.Timestamp("2024-03-31T00:00:00Z"),
    )
    assert train.index.tolist() == [0]
    assert test.index.tolist() == [2]
    assert "HYPE" not in script.ASSETS
