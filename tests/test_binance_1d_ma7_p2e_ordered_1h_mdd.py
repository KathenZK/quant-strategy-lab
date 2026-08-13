from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "research/asset-portfolios/1d-ma7-asset-specific-search/scripts/"
    "audit_binance_1d_ma7_p2e_ordered_1h_mdd.py"
)


def load_script():
    spec = importlib.util.spec_from_file_location(
        "binance_ma7_p2e_ordered_mdd_tested", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_target_from_flat_pays_entry_cost() -> None:
    module = load_script()
    qty, post_equity = module.target_from_flat(1.0, 1, 100.0, 0.0014)
    assert post_equity < 1.0
    assert qty * 100.0 == post_equity
    assert abs(1.0 - post_equity - qty * 100.0 * 0.0014) < 1e-12


def test_source_keeps_exposed_windows_sealed() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "RESEARCHER_EXPOSED" not in source
    assert "researcher_exposed_audit" not in source


def test_protective_stop_hour_distinguishes_gap_and_intrahour() -> None:
    module = load_script()
    hourly = pd.DataFrame(
        {
            "ts": pd.to_datetime(
                ["2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z"]
            ),
            "open": [100.0, 95.0],
        }
    )
    gap_hour = module.protective_stop_hour(
        hourly,
        exit_ts=pd.Timestamp("2026-01-01T01:00:00Z"),
        exit_price=95.0,
    )
    intrahour = module.protective_stop_hour(
        hourly,
        exit_ts=pd.Timestamp("2026-01-01T01:00:00Z"),
        exit_price=97.0,
    )
    assert gap_hour is None
    assert intrahour == pd.Timestamp("2026-01-01T00:00:00Z")
