from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "research/hype/1d-ma7-asymmetric-body-trend/scripts"
    / "render_hype_1d_ma7_wide_trend_lifecycle.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("hype_wtl_renderer", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RENDERER = load_module()


def retained_run(arm_id: str) -> dict[str, object]:
    return {
        "arm_id": arm_id,
        "metrics": {
            "closed_trades": 1,
            "net_return_pct": 10.0,
            "chronological_1h_mdd_pct": -5.0,
            "daily_extreme_mdd_pct": -6.0,
        },
        "trades": [
            {
                "side": "long",
                "entry_ts": "2026-01-01T00:00:00+00:00",
                "exit_ts": "2026-01-02T00:00:00+00:00",
                "entry_price": 10.0,
                "exit_price": 11.0,
                "exit_reason": "test_exit",
                "net_return": 0.10,
                "entry_leverage": 1.0,
            }
        ],
        "path": [
            {"ts": "2026-01-01T00:00:00+00:00", "close_equity": 1.0, "position": 1, "action": "enter_long"},
            {"ts": "2026-01-02T00:00:00+00:00", "close_equity": 1.1, "position": 0, "action": "test_exit"},
        ],
    }


def candles() -> list[dict[str, object]]:
    return [
        {"ts": "2026-01-01T00:00:00+00:00", "open": 10.0, "high": 10.5, "low": 9.5, "close": 10.2, "ma7": 10.0},
        {"ts": "2026-01-02T00:00:00+00:00", "open": 10.2, "high": 11.2, "low": 10.0, "close": 11.0, "ma7": 10.1},
    ]


def test_document_is_self_contained_and_connects_all_trades() -> None:
    document, audit = RENDERER.build_document(
        title="WTL test",
        candles=candles(),
        candidate=retained_run("candidate"),
        control=retained_run("control"),
    )
    text = document.decode()
    assert "window.WTL_DATA" in text
    assert "https://" not in text and "http://" not in text
    assert audit["all_trades_connected"]
    assert audit["candidate_trades"] == 1 and audit["control_trades"] == 1
    assert audit["external_dependencies"] == 0


def test_document_fails_closed_on_trade_count_or_window_mismatch() -> None:
    bad = retained_run("bad")
    bad["metrics"]["closed_trades"] = 2
    with pytest.raises(RuntimeError, match="trade count"):
        RENDERER.build_document(title="bad", candles=candles(), candidate=bad, control=retained_run("control"))
    bad = retained_run("bad")
    bad["trades"][0]["exit_ts"] = "2026-01-03T00:00:00+00:00"
    with pytest.raises(RuntimeError, match="outside"):
        RENDERER.build_document(title="bad", candles=candles(), candidate=bad, control=retained_run("control"))


def test_locked_html_is_exclusive_and_sidecar_matches(tmp_path: Path) -> None:
    document, audit = RENDERER.build_document(
        title="WTL test",
        candles=candles(),
        candidate=retained_run("candidate"),
        control=retained_run("control"),
    )
    path = tmp_path / "trade_path.html"
    record = RENDERER.write_locked(path, document)
    assert record["sha256"] == audit["sha256"]
    assert path.with_suffix(".sha256").is_file()
    with pytest.raises(RuntimeError, match="already exists"):
        RENDERER.write_locked(path, document)

