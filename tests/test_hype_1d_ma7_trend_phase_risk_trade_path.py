from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "research/hype/1d-ma7-asymmetric-body-trend/scripts"
    / "render_hype_1d_ma7_trend_phase_risk.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("hype_tpr_renderer", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RENDERER = load_module()


def run(arm: str) -> dict[str, object]:
    return {
        "arm_id": arm,
        "metrics": {
            "closed_trades": 1,
            "net_return_pct": 5.0,
            "chronological_1h_mdd_pct": -2.0,
            "daily_extreme_mdd_pct": -3.0,
        },
        "trades": [
            {
                "side": "long",
                "entry_ts": "2026-01-01T00:00:00+00:00",
                "exit_ts": "2026-01-02T00:00:00+00:00",
                "entry_price": 100.0,
                "exit_price": 105.0,
                "exit_reason": "terminal_flatten",
                "net_return": 0.05,
            }
        ],
        "path": [
            {
                "ts": "2026-01-01T00:00:00+00:00",
                "close_equity": 1.0,
                "position": 1,
                "action": "open_long",
            },
            {
                "ts": "2026-01-02T00:00:00+00:00",
                "close_equity": 1.05,
                "position": 0,
                "action": "terminal_flatten",
            },
        ],
    }


def candles() -> list[dict[str, object]]:
    return [
        {
            "ts": f"2026-01-0{day}T00:00:00+00:00",
            "open": 99.0 + day,
            "high": 102.0 + day,
            "low": 98.0 + day,
            "close": 100.0 + day,
            "ma7": 99.5 + day,
        }
        for day in (1, 2)
    ]


def test_document_is_self_contained_and_connects_every_trade() -> None:
    document, audit = RENDERER.build_document(
        title="Synthetic",
        candles=candles(),
        candidate=run("CANDIDATE"),
        control=run("EXACT_V4"),
    )
    text = document.decode()
    assert "window.TPR_DATA=" in text
    assert "R.trades.forEach" in text
    assert "http://" not in text and "https://" not in text
    assert audit["all_trades_connected"]
    assert audit["candidate_trades"] == audit["control_trades"] == 1


def test_document_fails_closed_on_trade_count_or_window_drift() -> None:
    broken = run("BROKEN")
    broken["metrics"]["closed_trades"] = 2
    with pytest.raises(RuntimeError, match="trade count"):
        RENDERER.build_document(
            title="Broken",
            candles=candles(),
            candidate=broken,
            control=run("EXACT_V4"),
        )
    broken = run("BROKEN")
    broken["trades"][0]["exit_ts"] = "2026-01-03T00:00:00+00:00"
    with pytest.raises(RuntimeError, match="outside"):
        RENDERER.build_document(
            title="Broken",
            candles=candles(),
            candidate=broken,
            control=run("EXACT_V4"),
        )


def test_locked_html_is_exclusive(tmp_path: Path) -> None:
    path = tmp_path / "path.html"
    first = RENDERER.write_locked(path, b"<html></html>")
    assert first["sha256"] == RENDERER.sha256_bytes(path.read_bytes())
    with pytest.raises(RuntimeError, match="already exists"):
        RENDERER.write_locked(path, b"changed")
