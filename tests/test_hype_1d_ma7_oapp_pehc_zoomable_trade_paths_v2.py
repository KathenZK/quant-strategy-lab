from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / (
    "research/hype/1d-ma7-asymmetric-body-trend/scripts/"
    "render_hype_1d_ma7_oapp_pehc_zoomable_trade_paths_v2.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("zoomable_trade_paths_v2", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def synthetic_run(label: str = "SYNTH") -> dict:
    return {
        "arm_id": label,
        "metrics": {
            "net_return_pct": 1.25,
            "chronological_1h_mdd_pct": -2.0,
            "daily_extreme_mdd_pct": -2.5,
            "closed_trades": 1,
        },
        "trades": [
            {
                "side": "long",
                "entry_ts": "2026-01-01T00:00:00+00:00",
                "exit_ts": "2026-01-03T00:00:00+00:00",
                "entry_price": 10.0,
                "exit_price": 11.0,
                "exit_reason": "synthetic_exit",
                "net_return": 0.0125,
                "bars_held": 2,
                "entry_leverage": 1.0,
            }
        ],
        "path": [
            {
                "ts": f"2026-01-0{index}T00:00:00+00:00",
                "close_equity": 1.0 + index / 100.0,
                "position": 1 if index < 3 else 0,
                "action": "hold" if index < 3 else "exit",
            }
            for index in range(1, 4)
        ],
    }


def candles() -> list[dict]:
    return [
        {
            "ts": f"2026-01-0{index}T00:00:00+00:00",
            "open": 9.0 + index,
            "high": 10.0 + index,
            "low": 8.0 + index,
            "close": 9.5 + index,
            "ma7": 9.25 + index,
            "displayOnlyTerminal": False,
        }
        for index in range(1, 4)
    ]


def test_build_document_is_self_contained_and_interactive() -> None:
    module = load_module()
    run = synthetic_run()
    document, audit = module.build_document(
        title="交互测试",
        evidence_role="synthetic",
        candles=candles(),
        candidate=run,
        candidate_label="Candidate",
        control=run,
        events=[
            {
                "event": "handoff_accept",
                "ts": "2026-01-02T00:00:00+00:00",
                "tradeIndex": 0,
            }
        ],
        parameter_groups_payload=[
            {"title": "参数", "rows": [["threshold", "0.5", "解释"]]}
        ],
    )
    html = document.decode("utf-8")

    assert "交互测试" in html
    assert "window.__ZOOMABLE_TRADE_PATH__" in html
    assert "addEventListener('wheel'" in html
    assert "pointerdown" in html
    assert "rangeStart" in html and "rangeEnd" in html
    assert "focusTrade" in html
    assert "https://" not in html and "http://" not in html
    assert audit["all_trades_connected"] is True
    assert audit["external_dependencies"] == 0
    assert all(audit["interaction"].values())


def test_rejects_trade_outside_candle_range() -> None:
    module = load_module()
    run = synthetic_run()
    run["trades"][0]["exit_ts"] = "2026-01-04T00:00:00+00:00"

    with pytest.raises(RuntimeError, match="outside candle range"):
        module.build_document(
            title="invalid",
            evidence_role="synthetic",
            candles=candles(),
            candidate=run,
            candidate_label="Candidate",
            control=synthetic_run("CONTROL"),
            events=[],
            parameter_groups_payload=[],
        )


def test_rejects_trade_count_mismatch() -> None:
    module = load_module()
    run = synthetic_run()
    run["metrics"]["closed_trades"] = 2

    with pytest.raises(RuntimeError, match="trade count mismatch"):
        module.build_document(
            title="invalid",
            evidence_role="synthetic",
            candles=candles(),
            candidate=run,
            candidate_label="Candidate",
            control=synthetic_run("CONTROL"),
            events=[],
            parameter_groups_payload=[],
        )


def test_parameter_tables_identify_inheritance_and_dormant_fields() -> None:
    module = load_module()
    long_config = {
        "entry_mode": "reclaim",
        "slope_lookback": 1,
        "slope_min_atr": 0.02,
        "confirm_days": 1,
        "entry_buffer_atr": 0.0,
        "exit_confirm_days": 1,
        "exit_buffer_atr": 0.75,
        "hard_stop_atr": 0.0,
        "trail_atr": 1.5,
        "max_hold_days": 90,
        "cooldown_days": 2,
        "pullback_lookback": 5,
        "breakout_lookback": 2,
    }
    short_config = {
        "entry_mode": "reclaim",
        "slope_lookback": 2,
        "slope_min_atr": 0.02,
        "confirm_days": 1,
        "entry_buffer_atr": 0.1,
        "exit_confirm_days": 1,
        "exit_buffer_atr": 0.75,
        "slope_exit_lookback": 1,
        "hard_stop_atr": 1.5,
        "trail_atr": 4.0,
        "max_hold_days": 20,
        "cooldown_days": 5,
        "pullback_lookback": 10,
        "breakout_lookback": 5,
    }
    oapp = {
        "entry": {"kind": "off"},
        "long_exit": {"activation_atr": 0.5, "giveback": 0.1, "confirm_days": 2},
        "roundtrip_guard": 0.0028,
        "short_exit": {"mode": "off"},
        "short_rsi": {"threshold": 20, "days": 2},
    }
    pehc = {
        "expiry_days": 8,
        "slope_threshold": None,
        "chase_cap_atr": float("inf"),
        "execution": "next_utc_open",
    }

    groups = module.parameter_groups(
        long_config=long_config,
        short_config=short_config,
        oapp_config=oapp,
        pehc_config=pehc,
    )
    flattened = repr(groups)

    assert len(groups) == 5
    assert "休眠字段" in flattened
    assert "固定 OAPP + exact V4" in flattened
    assert "single consume" in flattened
    assert "capital isolation" in flattened
