from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / (
    "research/asset-portfolios/1h-multi-horizon-cross-sectional-ml-allocator/scripts"
)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


collector = load_script("collect_blind_prospective_signals")
inference = load_script("frozen_r4_inference")
reveal = load_script("reveal_prospective_oos_once")


def test_schedule_starts_only_after_first_k0_is_closed() -> None:
    assert collector.scheduled_through(pd.Timestamp("2026-07-19T00:59:59Z")) == []
    assert collector.scheduled_through(pd.Timestamp("2026-07-19T01:05:00Z")) == [
        pd.Timestamp("2026-07-19T00:00:00Z")
    ]


def test_schedule_ends_at_last_frozen_decision() -> None:
    values = collector.scheduled_through(pd.Timestamp("2026-10-20T21:04:00Z"))
    assert values[-1] == pd.Timestamp("2026-10-18T20:00:00Z")
    assert len(values) == 552


def test_outcome_column_guard_allows_historical_risk_factors() -> None:
    columns = ["max_drawdown_72", "cs_rank_max_drawdown_72", "ret_24"]
    assert inference.outcome_columns(columns) == []
    assert inference.outcome_columns(["label_short_net_48"]) == [
        "label_short_net_48"
    ]
    assert inference.outcome_columns(["realized_pnl"]) == ["realized_pnl"]


def test_output_guard_allows_predicted_mae_but_not_realized_drawdown() -> None:
    assert inference.outcome_columns(
        ["short_mae_score", "mae_z", "utility"], output=True
    ) == []
    assert inference.outcome_columns(["drawdown"], output=True) == ["drawdown"]


def test_reveal_guard_fails_closed_until_last_leg_matures() -> None:
    with pytest.raises(RuntimeError, match="remain sealed"):
        reveal.assert_reveal_time(pd.Timestamp("2026-10-20T21:04:59Z"))
    reveal.assert_reveal_time(pd.Timestamp("2026-10-20T21:05:00Z"))
