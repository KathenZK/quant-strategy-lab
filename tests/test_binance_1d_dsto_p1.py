from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / (
    "research/asset-portfolios/1d-derivatives-structure-trend-opportunity/"
    "scripts/research_binance_1d_dsto_p1.py"
)


def load_script() -> Any:
    name = "test_binance_1d_dsto_p1_script"
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(name, SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_metric_features_use_only_rows_before_anchor() -> None:
    script = load_script()
    timestamps = pd.date_range(
        "2021-12-01", periods=8 * 288, freq="5min", tz="UTC"
    )
    index = np.arange(len(timestamps), dtype="float64")
    frame = pd.DataFrame(
        {
            "ts": timestamps,
            "sum_open_interest": np.exp(10.0 + index * 1e-5),
            "sum_open_interest_value": np.exp(20.0 + index * 2e-5),
        }
    )
    funding = pd.DataFrame(
        {
            "funding_nominal_ts": pd.date_range(
                "2021-12-01", "2021-12-08", freq="8h", tz="UTC"
            ),
            "funding_rate": 0.0001,
        }
    )
    anchor = pd.DatetimeIndex([pd.Timestamp("2021-12-08T00:00:00Z")])
    features = script.metric_anchor_features(frame, funding, anchor)
    end = 7 * 288
    expected_oi_24h = 1e-5 * ((end - 1) - (end - 288))
    assert np.isclose(features.at[0, "oi_log_change_24h"], expected_oi_24h)
    assert np.isclose(features.at[0, "funding_sum_24h"], 0.0003)


def test_policy_enforces_five_day_non_overlap() -> None:
    script = load_script()
    anchors = pd.date_range("2024-01-01", periods=7, freq="1D", tz="UTC")
    frame = pd.DataFrame(
        {
            "anchor_id": [f"BTC-{day:%Y%m%d}" for day in anchors],
            "asset": ["BTC"] * len(anchors),
            "anchor_ts": anchors,
            "entry_ts": anchors,
            "exit_ts": anchors + pd.Timedelta(days=5),
            "p_short": [0.1] * len(anchors),
            "p_flat": [0.1] * len(anchors),
            "p_long": [0.8] * len(anchors),
            "selected_threshold": [0.55] * len(anchors),
        }
    )
    for side in ("long", "short"):
        for suffix in (
            "z_4bps",
            "z_8bps",
            "z_12bps",
            "z_funding_off",
            "z_lag1h",
        ):
            frame[f"{side}_{suffix}"] = 0.01 if side == "long" else -0.01
    decisions = script.apply_policy(frame)
    executed = decisions.loc[decisions["executed"]]
    assert executed["anchor_ts"].tolist() == [anchors[0], anchors[5]]
    assert executed["direction"].tolist() == [1, 1]
    assert executed["selected_z_4bps"].tolist() == [0.01, 0.01]


def test_split_excludes_held_asset_and_purges_labels() -> None:
    script = load_script()
    first_test = pd.Timestamp("2024-03-01T00:00:00Z")
    frame = pd.DataFrame(
        {
            "asset": ["ETH", "ETH", "BTC"],
            "anchor_ts": [
                pd.Timestamp("2024-02-15T00:00:00Z"),
                pd.Timestamp("2024-02-25T00:00:00Z"),
                first_test,
            ],
            "exit_ts": [
                pd.Timestamp("2024-02-20T00:00:00Z"),
                pd.Timestamp("2024-03-01T00:00:00Z"),
                pd.Timestamp("2024-03-06T00:00:00Z"),
            ],
        }
    )
    train, test = script.split_fold(
        frame,
        held_asset="BTC",
        first_test=first_test,
        last_test=pd.Timestamp("2024-03-31T00:00:00Z"),
    )
    assert train.index.tolist() == [0]
    assert test.index.tolist() == [2]


def test_feature_contract_and_hype_lock() -> None:
    script = load_script()
    assert len(script.PRICE_FEATURES) == 8
    assert len(script.DERIVATIVE_FEATURES) == 22
    assert len(script.FULL_FEATURES) == 30
    assert "HYPE" not in script.ASSETS
    assert all("hype" not in slug.lower() for slug in script.ASSET_SLUGS.values())


def test_frozen_five_asset_nested_aggregate_is_fail_closed() -> None:
    script = load_script()
    capacity = script.strict_nested_aggregate_capacity()

    assert capacity["outer_fold_peers"] == 3
    assert capacity["outer_feasible"]
    assert capacity["inner_fold_peers"] == 2
    assert not capacity["inner_feasible"]
    with pytest.raises(RuntimeError, match="historical P1 aggregate"):
        script.enforce_strict_nested_aggregate_capacity()
