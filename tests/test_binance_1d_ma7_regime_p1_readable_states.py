from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = (
    ROOT / "research/asset-portfolios/1d-ma7-regime-continuation/scripts"
)
SCRIPT_PATH = SCRIPT_DIR / "analyze_binance_1d_ma7_regime_p1_readable_states.py"
sys.path.insert(0, str(SCRIPT_DIR))
SPEC = importlib.util.spec_from_file_location("binance_1d_ma7_rc_p1", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_p1_frozen_config_hash_and_identity() -> None:
    actual_hash = MODULE.sha256_file(MODULE.CONFIG_PATH)
    config = json.loads(MODULE.CONFIG_PATH.read_text(encoding="utf-8"))
    assert actual_hash == MODULE.EXPECTED_CONFIG_SHA256
    assert config["study_id"] == "BIN-1D-MA7-RC-P1"
    assert config["market_state"]["UP_TREND"].endswith(
        "er_percentile > 0.60"
    )
    assert config["decision_boundary"]["not_a_strategy_backtest"] is True


def test_p1_percentile_quintiles_are_right_closed() -> None:
    values = pd.Series([0.01, 0.20, 0.21, 0.40, 0.60, 0.80, 0.81, 1.0, np.nan])
    actual = MODULE.assign_quintile(values)
    assert actual.tolist() == [1, 1, 2, 2, 3, 4, 5, 5, pd.NA]


def test_p1_filter_masks_are_directional_and_mutually_interpretable() -> None:
    frame = pd.DataFrame(
        {
            "direction": ["long", "long", "short", "short", "short"],
            "market_state": [
                "UP_TREND",
                "DOWN_TREND",
                "DOWN_TREND",
                "UP_TREND",
                "DOWN_TREND",
            ],
            "rv_q_p1": pd.Series([2, 5, 4, 1, 3], dtype="Int64"),
            "compression_expansion": [False, True, False, True, True],
        }
    )
    masks = MODULE.filter_masks(frame)
    assert masks["ALL_MA7"].tolist() == [True, True, True, True, True]
    assert masks["ALIGNED_STATE"].tolist() == [True, False, True, False, True]
    assert masks["ALIGNED_LOW_VOL"].tolist() == [True, False, False, False, False]
    assert masks["ALIGNED_MID_VOL"].tolist() == [False, False, False, False, True]
    assert masks["ALIGNED_HIGH_VOL"].tolist() == [False, False, True, False, False]
    assert masks["ALIGNED_COMPRESSION_EXPANSION"].tolist() == [
        False,
        False,
        False,
        False,
        True,
    ]


def test_period_key_uses_utc_day_monday_week_and_month_start() -> None:
    dates = pd.Series(
        pd.to_datetime(
            [
                "2024-01-07T23:00:00Z",
                "2024-01-08T01:00:00Z",
                "2024-02-02T00:00:00Z",
            ],
            utc=True,
        )
    )
    day = MODULE.period_key(dates, "day")
    week = MODULE.period_key(dates, "week")
    month = MODULE.period_key(dates, "month")
    assert day.dt.strftime("%Y-%m-%d").tolist() == [
        "2024-01-07",
        "2024-01-08",
        "2024-02-02",
    ]
    assert week.dt.strftime("%Y-%m-%d").tolist() == [
        "2024-01-01",
        "2024-01-08",
        "2024-01-29",
    ]
    assert month.dt.strftime("%Y-%m-%d").tolist() == [
        "2024-01-01",
        "2024-01-01",
        "2024-02-01",
    ]
