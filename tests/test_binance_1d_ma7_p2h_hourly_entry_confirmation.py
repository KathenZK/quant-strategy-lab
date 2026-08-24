from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "research/asset-portfolios/1d-ma7-asset-specific-search/scripts/"
    "audit_binance_1d_ma7_p2h_hourly_entry_confirmation.py"
)


def load_script():
    spec = importlib.util.spec_from_file_location(
        "binance_ma7_p2h_hourly_confirmation_tested", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def fixtures() -> tuple[pd.DataFrame, pd.DataFrame]:
    hourly = pd.DataFrame(
        {
            "ts": pd.to_datetime(
                [
                    "2026-01-02T00:00:00Z",
                    "2026-01-02T01:00:00Z",
                    "2026-01-02T02:00:00Z",
                ]
            ),
            "open": [100.0, 101.0, 102.0],
            "high": [102.0, 103.0, 104.0],
            "low": [99.0, 100.0, 101.0],
            "close": [101.0, 102.0, 103.0],
        }
    )
    daily = pd.DataFrame(
        {
            "ts": pd.to_datetime(["2026-01-01T00:00:00Z"]),
            "high": [105.0],
            "low": [95.0],
        }
    )
    return hourly, daily


def test_confirmations_fill_at_next_hour_open() -> None:
    module = load_script()
    hourly, daily = fixtures()
    row = pd.Series(
        {
            "entry_ts": "2026-01-02T00:00:00Z",
            "exit_ts": "2026-01-03T00:00:00Z",
            "entry_price": 100.0,
            "exit_price": 110.0,
        }
    )
    result = module.confirmation_candidates(
        row, hourly=hourly, daily=daily, side=1
    )
    assert result["H1_POSITIVE_CLOSE"]["candidate_fill_ts"] == (
        "2026-01-02T01:00:00+00:00"
    )
    assert result["H1_POSITIVE_CLOSE"]["candidate_fill_price"] == 101.0
    assert result["H2_POSITIVE_CLOSE"]["candidate_fill_ts"] == (
        "2026-01-02T02:00:00+00:00"
    )
    assert not result["PDX_PRIOR_DAY_EXTREME"]["candidate_valid"]


def test_tail_hit_uses_adverse_extreme() -> None:
    module = load_script()
    hourly, _ = fixtures()
    hourly.loc[0, "low"] = 91.0
    row = pd.Series(
        {
            "entry_ts": "2026-01-02T00:00:00Z",
            "exit_ts": "2026-01-03T00:00:00Z",
            "entry_price": 100.0,
            "exit_price": 110.0,
        }
    )
    assert module.first_tail_hit(row, hourly=hourly, side=1) == pd.Timestamp(
        "2026-01-02T00:00:00Z"
    )


def test_source_keeps_exposed_windows_sealed() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "RESEARCHER_EXPOSED" not in source
    assert "researcher_exposed_audit" not in source
    assert "PROSPECTIVE" not in source
