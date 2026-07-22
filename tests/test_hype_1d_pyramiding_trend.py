from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "research/hype/1d-pyramiding-trend/scripts/research_hype_1d_pyramiding_trend.py"
)


def load_module() -> object:
    spec = importlib.util.spec_from_file_location("hype_1d_pt_test_module", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_prior_channel_excludes_current_bar() -> None:
    module = load_module()
    values = np.array([100.0, 101.0, 200.0, 102.0])
    result = module._prior_roll(values, 2, "max")
    assert np.isnan(result[1])
    assert result[2] == 101.0
    assert result[3] == 200.0


def test_funding_events_align_across_datetime_units() -> None:
    module = load_module()
    opens = pd.DatetimeIndex(
        ["2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"],
        dtype="datetime64[ms, UTC]",
    )
    funding = pd.DataFrame(
        {
            "ts": pd.to_datetime(
                ["2026-01-01T08:00:00Z", "2026-01-01T16:00:00Z"], utc=True
            ),
            "funding_rate": [0.001, 0.002],
        }
    )
    result = module._funding_by_open(opens, funding)
    assert result.tolist() == [0.0, 0.003]


def test_annual_factor_uses_compounding() -> None:
    module = load_module()
    assert module._annual_factor(4.0, 730.5) == 2.0
