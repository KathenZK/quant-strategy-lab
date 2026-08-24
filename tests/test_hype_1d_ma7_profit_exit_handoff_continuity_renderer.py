from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "research/hype/1d-ma7-asymmetric-body-trend/scripts/render_hype_1d_ma7_profit_exit_handoff_continuity.py"


def load():
    spec = importlib.util.spec_from_file_location("pehc_renderer_test_module", PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run(arm: str, *, handoffs: list[dict] | None = None) -> dict:
    return {
        "arm_id": arm,
        "metrics": {"closed_trades": 1, "net_return_pct": 10.0, "chronological_1h_mdd_pct": -5.0, "daily_extreme_mdd_pct": -6.0},
        "trades": [{"side": "short", "entry_ts": "2026-01-01T03:00:00+00:00", "exit_ts": "2026-01-02T00:00:00+00:00", "entry_price": 99.0, "exit_price": 90.0, "exit_reason": "max_hold", "net_return": 0.1}],
        "path": [{"ts": "2026-01-01T00:00:00+00:00", "close_equity": 1.05, "position": -1, "action": "hold"}],
        "handoff_events": handoffs or [],
    }


def candles() -> list[dict]:
    return [
        {"ts": "2026-01-01T00:00:00+00:00", "open": 100.0, "high": 101.0, "low": 98.0, "close": 99.0, "ma7": 100.0, "display_only_terminal": False},
        {"ts": "2026-01-02T00:00:00+00:00", "open": 90.0, "high": 90.0, "low": 90.0, "close": 90.0, "ma7": None, "display_only_terminal": True},
    ]


def test_document_embeds_linked_shadow_and_no_external_assets() -> None:
    module = load()
    events = [
        {"event": "handoff_opportunity", "ts": "2026-01-01T03:00:00+00:00", "origin_index": 1, "price": 99.0},
        {"event": "handoff_accept", "ts": "2026-01-01T03:00:00+00:00", "origin_index": 1, "price": 99.0},
    ]
    document, audit = module.build_document(title="PEHC <audit>", candles=candles(), candidate=run("PEHC", handoffs=events), control=run("V4"))
    text = document.decode()
    assert "window.PEHC_DATA=" in text
    assert "PEHC &lt;audit&gt;" in text
    assert "https://" not in text and "src=\"/" not in text
    assert audit["handoff_audit"]["accepts"] == 1
    assert audit["shadow_capital_isolated"]


def test_renderer_rejects_accept_without_opportunity() -> None:
    module = load()
    events = [{"event": "handoff_accept", "ts": "2026-01-01T03:00:00+00:00", "origin_index": 1, "price": 99.0}]
    with pytest.raises(RuntimeError, match="not linked"):
        module.build_document(title="bad", candles=candles(), candidate=run("PEHC", handoffs=events), control=run("V4"))


def test_renderer_rejects_shadow_equity_field() -> None:
    module = load()
    events = [{"event": "handoff_opportunity", "ts": "2026-01-01T03:00:00+00:00", "origin_index": 1, "shadow_equity": 1.0}]
    with pytest.raises(RuntimeError, match="capital-isolated"):
        module.build_document(title="bad", candles=candles(), candidate=run("PEHC", handoffs=events), control=run("V4"))

