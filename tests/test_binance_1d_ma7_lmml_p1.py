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
    "research/asset-portfolios/1d-ma7-later-maturity-meta-label/scripts/"
    "research_binance_1d_ma7_lmml_p1.py"
)


def load_script() -> Any:
    name = "test_binance_1d_ma7_lmml_p1_script"
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(name, SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_soft_cross_and_exact_maturity_boundaries() -> None:
    script = load_script()
    daily = pd.DataFrame(
        {
            "close": [9.0, 10.1, 10.0, 9.9],
            "sma7": [10.0, 10.0, 10.0, 10.0],
            "atr7": np.ones(4),
        }
    )
    assert script.raw_cross(daily, 1) == 1
    assert script.raw_cross(daily, 3) == -1
    long = script.maturity_criteria(daily, 2, 1)
    short = script.maturity_criteria(daily, 3, -1)
    assert long["buffer_pass"] is False
    assert short["distance_atr"] == 0.09999999999999964
    assert short["buffer_pass"] is False


def test_probe_outcome_includes_levered_cost_and_funding() -> None:
    script = load_script()
    timestamps = pd.date_range("2024-01-01", periods=10, freq="1D", tz="UTC")
    daily = pd.DataFrame(
        {
            "ts": timestamps,
            "open": np.full(10, 10.0),
            "close": np.full(10, 10.0),
            "sma7": np.full(10, 9.0),
        }
    )
    funding = pd.DataFrame(
        {
            "ts": [timestamps[2] + pd.Timedelta(hours=8)],
            "funding_rate": [0.001],
            "mark_price": [10.0],
        }
    )
    outcome = script.trade_outcome(
        daily,
        funding,
        maturity_index=1,
        side=1,
        slippage=0.0008,
        include_funding=True,
    )
    assert outcome is not None
    entry_fill = 10.0 * 1.0008
    exit_fill = 10.0 * 0.9992
    gross = (exit_fill - entry_fill) / entry_fill
    carry = -0.001 * 10.0 / entry_fill
    fees = 0.001 + 0.001 * exit_fill / entry_fill
    expected = 0.25 * (gross + carry - fees)
    assert math.isclose(
        outcome["direct_net_return"],
        expected,
        rel_tol=1e-12,
        abs_tol=1e-12,
    )


def test_time_split_purges_exit_and_embargo() -> None:
    script = load_script()
    first_test = pd.Timestamp("2024-02-01T00:00:00Z")
    events = pd.DataFrame(
        {
            "signal_ts": [
                pd.Timestamp("2024-01-01T00:00:00Z"),
                pd.Timestamp("2024-01-20T00:00:00Z"),
                first_test,
            ],
            "exit_ts": [
                pd.Timestamp("2024-01-10T00:00:00Z"),
                pd.Timestamp("2024-01-30T00:00:00Z"),
                pd.Timestamp("2024-02-05T00:00:00Z"),
            ],
        }
    )
    train, test = script.split_for_block(
        events,
        first_test=first_test,
        last_test=pd.Timestamp("2024-02-10T00:00:00Z"),
    )
    assert train.index.tolist() == [0]
    assert test.index.tolist() == [2]


def test_development_code_has_no_hype_asset() -> None:
    script = load_script()
    assert "HYPE" not in script.ASSETS
    assert script.DEVELOPMENT_END_EXCLUSIVE == pd.Timestamp(
        "2025-05-31T00:00:00Z"
    )
