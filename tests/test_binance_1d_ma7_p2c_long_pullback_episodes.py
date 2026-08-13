from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "research/asset-portfolios/1d-ma7-asset-specific-search/scripts/"
    "audit_binance_1d_ma7_p2c_long_pullback_episodes.py"
)


def load_script():
    spec = importlib.util.spec_from_file_location(
        "binance_ma7_p2c_episode_tested", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_probe_changes_only_long_entry_mode() -> None:
    module = load_script()
    baseline = module.load_module(
        module.BASELINE_PATH, "binance_ma7_p2c_test_baseline"
    )
    transfer = baseline.load_module(
        baseline.TRANSFER_PATH,
        baseline.TRANSFER_SHA256,
        "binance_ma7_p2c_test_transfer",
    )
    engine = transfer.load_engine()
    long_config, _ = baseline.v1_configs(engine)
    probe = module.probe_long_config(long_config)
    before = vars_for_slots(long_config)
    after = vars_for_slots(probe)
    assert {key for key in before if before[key] != after[key]} == {
        "entry_mode"
    }
    assert after["entry_mode"] == "pullback_reclaim"


def vars_for_slots(config):
    return {
        field: getattr(config, field)
        for field in config.__dataclass_fields__
    }


def test_price_excursion_uses_held_hours_before_exit() -> None:
    module = load_script()
    hourly = pd.DataFrame(
        {
            "ts": pd.to_datetime(
                ["2026-01-01T00:00Z", "2026-01-01T01:00Z", "2026-01-01T02:00Z"]
            ),
            "high": [103.0, 110.0, 999.0],
            "low": [98.0, 95.0, 1.0],
        }
    )
    result = module.price_excursion(
        hourly,
        entry_ts=pd.Timestamp("2026-01-01T00:00Z"),
        exit_ts=pd.Timestamp("2026-01-01T02:00Z"),
        entry_price=100.0,
        exit_price=105.0,
    )
    assert result["max_favorable_price"] == 110.0
    assert result["max_adverse_price"] == 95.0
    assert result["mfe_pct"] == pytest.approx(10.0)
    assert result["mae_pct"] == pytest.approx(-5.0)
    assert result["giveback_pct_entry"] == pytest.approx(-5.0)


def test_source_does_not_reference_exposed_window() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "RESEARCHER_EXPOSED" not in source
    assert "researcher_exposed_audit" not in source
