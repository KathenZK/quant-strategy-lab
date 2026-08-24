from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "research/asset-portfolios/1d-ma7-asset-specific-search/scripts/"
    "audit_binance_1d_ma7_p2g_entry_information.py"
)


def load_script():
    spec = importlib.util.spec_from_file_location(
        "binance_ma7_p2g_entry_information_tested", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_rank_effect_auc_has_declared_direction() -> None:
    module = load_script()
    frame = pd.DataFrame(
        {"x": [1.0, 2.0, 3.0, 4.0], "early_tail": [False, False, True, True]}
    )
    result = module.rank_effect_auc(frame, "x")
    assert result["auc"] == 1.0
    assert result["rank_biserial_effect"] == 1.0


def test_sum_before_excludes_event_at_right_boundary() -> None:
    module = load_script()
    timestamps = pd.to_datetime(
        ["2026-01-01T00:00:00Z", "2026-01-01T08:00:00Z"]
    )
    rates = np.asarray([0.01, 0.02])
    cumulative = np.concatenate(([0.0], np.cumsum(rates)))
    result = module.sum_before(
        timestamps.to_numpy(dtype="datetime64[ns]").astype(np.int64),
        cumulative,
        left=pd.Timestamp("2025-12-31T00:00:00Z"),
        right=pd.Timestamp("2026-01-01T08:00:00Z"),
    )
    assert result == 0.01


def test_early_outcome_respects_actual_early_exit() -> None:
    module = load_script()
    hourly = pd.DataFrame(
        {
            "ts": pd.to_datetime(
                ["2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z"]
            ),
            "open": [100.0, 99.0],
            "high": [101.0, 100.0],
            "low": [95.0, 90.0],
            "close": [99.0, 91.0],
        }
    )
    trade = {
        "entry_ts": "2026-01-01T00:00:00Z",
        "exit_ts": "2026-01-01T01:00:00Z",
        "entry_price": 100.0,
        "exit_price": 94.0,
    }
    result = module.early_outcome(trade, hourly=hourly, side=1)
    assert result["early_adverse_return"] == -0.06
    assert result["early_tail"] is False
    assert result["return_48h_or_exit"] == -0.06


def test_source_keeps_exposed_windows_sealed() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "RESEARCHER_EXPOSED" not in source
    assert "researcher_exposed_audit" not in source
    assert "PROSPECTIVE" not in source
