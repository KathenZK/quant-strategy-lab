from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / (
    "research/asset-portfolios/1h-multi-horizon-cross-sectional-ml-allocator/"
    "scripts/build_multihorizon_factor_panel.py"
)


def load_script():
    spec = importlib.util.spec_from_file_location(
        "build_multihorizon_factor_panel_for_test", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def label_frame() -> pd.DataFrame:
    rows = 80
    open_price = np.linspace(100.0, 140.0, rows)
    return pd.DataFrame(
        {
            "open": open_price,
            "high": open_price * 1.02,
            "low": open_price * 0.98,
            "funding_event_rate": np.where(np.arange(rows) % 8 == 0, 0.001, 0.0),
            "bar_present": True,
        }
    )


def test_multihorizon_short_label_uses_linear_contract_return() -> None:
    panel = load_script()
    frame = label_frame()

    result = panel.add_multihorizon_labels(frame)

    entry = frame.loc[1, "open"]
    exit_price = frame.loc[5, "open"]
    funding = result.loc[0, "label_funding_sum_4h"]
    expected = 1.0 - exit_price / entry - panel.ROUND_TRIP_COST + funding
    assert result.loc[0, "label_short_net_4h"] == pytest.approx(expected)


def test_multihorizon_labels_fail_closed_across_missing_bars() -> None:
    panel = load_script()
    frame = label_frame()
    frame.loc[3, "bar_present"] = False
    frame.loc[3, ["open", "high", "low"]] = np.nan

    result = panel.add_multihorizon_labels(frame)

    assert not bool(result.loc[0, "label_path_valid_4h"])
    assert pd.isna(result.loc[0, "label_long_net_4h"])
    assert pd.isna(result.loc[0, "label_short_net_4h"])
    assert bool(result.loc[4, "label_path_valid_4h"])


def test_tail_labels_capture_squeeze_and_crash_direction() -> None:
    panel = load_script()
    frame = label_frame()
    frame.loc[2, "high"] = frame.loc[1, "open"] * 1.25
    frame.loc[2, "low"] = frame.loc[1, "open"] * 0.75

    result = panel.add_multihorizon_labels(frame)

    assert result.loc[0, "label_short_squeeze_20pct_4h"] == 1.0
    assert result.loc[0, "label_long_crash_20pct_4h"] == 1.0
    assert result.loc[0, "label_short_mae_4h"] <= -0.25
    assert result.loc[0, "label_long_mae_4h"] <= -0.25


def test_mae_and_mfe_are_clipped_to_zero_on_fully_favorable_paths() -> None:
    panel = load_script()
    frame = label_frame()
    entry = frame.loc[1, "open"]
    frame.loc[1:4, "low"] = entry * 1.01
    frame.loc[1:4, "high"] = entry * 1.05

    result = panel.add_multihorizon_labels(frame)

    assert result.loc[0, "label_long_mae_4h"] == 0.0
    assert result.loc[0, "label_long_mfe_4h"] > 0.0
    assert result.loc[0, "label_short_mae_4h"] < 0.0
    assert result.loc[0, "label_short_mfe_4h"] == 0.0
