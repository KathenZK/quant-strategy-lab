from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd


SCRIPT = Path("research/asset-portfolios/multi-timeframe-pullback-trend-campaign/scripts/research_continuation_meter_v0.py")


def load_module():
    spec = importlib.util.spec_from_file_location("test_bin_mtf_ptc_continuation", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_same_bar_two_barriers_is_conservative_failure() -> None:
    module = load_module()
    index = pd.date_range("2026-01-01", periods=4, freq="1h", tz="UTC")
    hourly = pd.DataFrame({"high": [100.0, 112.0, 100.0, 100.0], "low": [100.0, 94.0, 100.0, 100.0]}, index=index)
    events = pd.DataFrame({"close": [100.0], "direction": [1], "r_log": [np.log(1.1)]}, index=index[:1])
    label = module.label_events(events, hourly, 2)
    assert label.iloc[0] == 0.0


def test_long_success_before_failure_is_positive() -> None:
    module = load_module()
    index = pd.date_range("2026-01-01", periods=4, freq="1h", tz="UTC")
    hourly = pd.DataFrame({"high": [100.0, 111.0, 100.0, 100.0], "low": [100.0, 99.0, 90.0, 100.0]}, index=index)
    events = pd.DataFrame({"close": [100.0], "direction": [1], "r_log": [np.log(1.1)]}, index=index[:1])
    label = module.label_events(events, hourly, 3)
    assert label.iloc[0] == 1.0


def test_short_success_before_failure_is_positive() -> None:
    module = load_module()
    index = pd.date_range("2026-01-01", periods=4, freq="1h", tz="UTC")
    hourly = pd.DataFrame({"high": [100.0, 101.0, 120.0, 100.0], "low": [100.0, 90.0, 100.0, 100.0]}, index=index)
    events = pd.DataFrame({"close": [100.0], "direction": [-1], "r_log": [np.log(1.1)]}, index=index[:1])
    label = module.label_events(events, hourly, 3)
    assert label.iloc[0] == 1.0


def test_incomplete_future_path_is_unresolved() -> None:
    module = load_module()
    index = pd.date_range("2026-01-01", periods=2, freq="1h", tz="UTC")
    hourly = pd.DataFrame({"high": [100.0, 101.0], "low": [100.0, 99.0]}, index=index)
    events = pd.DataFrame({"close": [100.0], "direction": [1], "r_log": [0.1]}, index=index[:1])
    assert np.isnan(module.label_events(events, hourly, 2).iloc[0])
