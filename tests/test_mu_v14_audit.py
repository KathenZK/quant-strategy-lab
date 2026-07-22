from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/mu/scripts/audit_mu_v14_latest.py"


def load_audit() -> Any:
    script_dir = str(SCRIPT.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    spec = importlib.util.spec_from_file_location("mu_v14_latest_audit_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


AUDIT = load_audit()


def frame(
    *,
    open_: list[float],
    high: list[float],
    low: list[float],
    close: list[float],
    signal: list[bool],
) -> pd.DataFrame:
    rows = len(open_)
    return pd.DataFrame(
        {
            "ts": pd.date_range("2026-01-01", periods=rows, freq="15min", tz="UTC"),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "v6_long_signal": signal,
            "v6_long_trend_state": [True] * rows,
            "atr_pct672": [0.01] * rows,
        }
    )


def test_same_bar_tp_sl_conflict_is_stop_first() -> None:
    data = frame(
        open_=[100.0, 100.0, 100.0],
        high=[100.0, 112.0, 100.0],
        low=[100.0, 90.0, 100.0],
        close=[100.0, 100.0, 100.0],
        signal=[True, False, False],
    )
    result = AUDIT.strict_backtest(
        data,
        np.zeros(len(data)),
        start_i=0,
        end_i=2,
    )
    assert result["intrabar_conflicts"] == 1
    assert result["closed_trades"] == 1
    assert result["trades"][0]["exit_reason"] == "same_bar_conflict_stop_first"
    assert result["return"] < 0.0


def test_gap_through_stop_uses_next_open() -> None:
    data = frame(
        open_=[100.0, 100.0, 89.0],
        high=[100.0, 101.0, 90.0],
        low=[100.0, 99.0, 88.0],
        close=[100.0, 100.0, 89.0],
        signal=[True, False, False],
    )
    result = AUDIT.strict_backtest(
        data,
        np.zeros(len(data)),
        start_i=0,
        end_i=2,
    )
    trade = result["trades"][0]
    assert result["gap_stops"] == 1
    assert trade["exit_reason"] == "gap_stop_open"
    assert trade["exit_price"] == 89.0 * (1.0 - AUDIT.SLIPPAGE_RATE)


def test_exit_bar_does_not_immediately_rearm_entry() -> None:
    data = frame(
        open_=[100.0, 100.0, 100.0, 100.0],
        high=[100.0, 112.0, 100.0, 100.0],
        low=[100.0, 90.0, 100.0, 100.0],
        close=[100.0, 100.0, 100.0, 100.0],
        signal=[True, True, False, False],
    )
    result = AUDIT.strict_backtest(
        data,
        np.zeros(len(data)),
        start_i=0,
        end_i=3,
    )
    assert result["closed_trades"] == 1
    assert result["open_position_at_end"] is False


def test_funding_is_applied_to_carried_position() -> None:
    data = frame(
        open_=[100.0, 100.0, 100.0],
        high=[100.0, 101.0, 101.0],
        low=[100.0, 99.0, 99.0],
        close=[100.0, 100.0, 100.0],
        signal=[True, False, False],
    )
    no_funding = AUDIT.strict_backtest(
        data,
        np.zeros(len(data)),
        start_i=0,
        end_i=2,
    )
    funding = np.zeros(len(data))
    funding[2] = 0.01
    with_funding = AUDIT.strict_backtest(
        data,
        funding,
        start_i=0,
        end_i=2,
    )
    assert with_funding["return"] < no_funding["return"]
    assert with_funding["funding_drag_equity"] > 0.0
