from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


SCRIPT = Path(
    "research/asset-portfolios/1h-four-asset-trend-habitat-audit/scripts/"
    "research_binance_1h_fatha.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("test_binance_1h_fatha_module", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_trend_efficiency_separates_smooth_and_noisy_paths() -> None:
    module = load_module()
    smooth = np.array([0.0, 1.0, 2.0, 3.0])
    noisy = np.array([0.0, 2.0, -1.0, 3.0])
    assert module.trend_efficiency(smooth) == 1.0
    assert 0.0 < module.trend_efficiency(noisy) < 1.0


def test_first_passage_uses_only_path_order() -> None:
    module = load_module()
    assert module.first_passage(np.array([0.4, 1.1, -1.2]), 1.0) == "favorable"
    assert module.first_passage(np.array([-0.2, -1.1, 1.3]), 1.0) == "adverse"
    assert module.first_passage(np.array([0.2, -0.3]), 1.0) == "none"


def test_half_mfe_protection_activates_only_after_two_r() -> None:
    module = load_module()
    below_two = np.array([0.0, 0.5, 1.8, 0.7, 1.2])
    result = module.path_diagnostics(below_two, 1, 1.0, 4)
    assert not result["half_mfe_triggered_after_2r"]
    above_two = np.array([0.0, 1.0, 2.2, 0.9, 1.1])
    result = module.path_diagnostics(above_two, 1, 1.0, 4)
    assert result["half_mfe_triggered_after_2r"]


def test_delay_capture_is_remaining_move_not_lookahead_entry_signal() -> None:
    module = load_module()
    path = np.linspace(0.0, 1.0, 25)
    result = module.path_diagnostics(path, 1, 0.1, 24)
    assert np.isclose(result["delay_12h_capture_ratio"], 0.5)
    assert np.isclose(result["delay_24h_capture_ratio"], 0.0)


def test_common_bounds_reserve_past_and_future() -> None:
    module = load_module()
    index_a = pd.date_range("2025-01-01", periods=2_000, freq="1h", tz="UTC")
    index_b = pd.date_range("2025-01-15", periods=1_500, freq="1h", tz="UTC")
    empty = pd.DataFrame(index=index_a)
    assets = {
        "A": module.AssetData("A", "A", empty, {}),
        "B": module.AssetData("B", "B", pd.DataFrame(index=index_b), {}),
    }
    start, end = module.common_bounds(assets)
    assert start >= index_b.min() + pd.Timedelta(hours=module.PAST_VOL_HOURS)
    assert end <= min(index_a.max(), index_b.max()) - pd.Timedelta(
        hours=max(module.HORIZONS)
    )


def test_onset_followthrough_summarizes_observed_early_direction() -> None:
    module = load_module()
    paths = pd.DataFrame(
        {
            "asset": ["X", "X", "X"],
            "horizon_hours": [72, 72, 72],
            "onset_4h_side": [1, -1, 1],
            "onset_4h_scaled_move": [0.2, 0.5, 0.9],
            "onset_4h_efficiency": [0.3, 0.6, 0.8],
            "onset_4h_continuation": [True, False, True],
            "onset_4h_remaining_return": [0.01, -0.02, 0.03],
            "onset_4h_net": [0.007, -0.023, 0.027],
            "onset_4h_net_positive": [True, False, True],
            "onset_4h_mfe_r": [1.0, 0.2, 2.0],
            "onset_4h_mae_r": [0.2, 1.0, 0.1],
            "onset_4h_first_passage": ["favorable", "adverse", "favorable"],
        }
    )
    for delay in (12, 24):
        for suffix in (
            "side",
            "scaled_move",
            "efficiency",
            "continuation",
            "remaining_return",
            "net",
            "net_positive",
            "mfe_r",
            "mae_r",
            "first_passage",
        ):
            paths[f"onset_{delay}h_{suffix}"] = paths[f"onset_4h_{suffix}"]
    summary = module.summarize_onset_followthrough(paths, "test")
    all_row = summary.loc[
        summary["delay_hours"].eq(4) & summary["strength_tier"].eq("all")
    ].iloc[0]
    assert all_row["continuation_rate"] == pytest.approx(2.0 / 3.0)
    assert all_row["mean_remaining_return"] == pytest.approx(0.02 / 3.0)
