from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/hype/1d-ma7-asymmetric-body-trend/scripts/research_hype_1d_ma7_v6_delayed_episode.py"


def load_research():
    spec = importlib.util.spec_from_file_location("hype_dtec_research_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run(metrics, *, accuracy=None, trades_sha="x", counts=None):
    return {
        "status": "PASS",
        "metrics": metrics,
        "accuracy": accuracy or {
            "combined": {"evaluable": 4, "precision": 0.75},
            "long": {"evaluable": 2, "precision": 0.5},
            "short": {"evaluable": 2, "precision": 1.0},
        },
        "trades_sha256": trades_sha,
        "activation_counts": counts or {
            "long_trail_exit": 1,
            "short_rsi_exit": 1,
            "shadow_start": 1,
        },
    }


def metrics(ret, mdd, trades=5):
    return {
        "equity_multiple": 1 + ret / 100,
        "net_return_pct": ret,
        "chronological_1h_mdd_pct": mdd,
        "closed_trades": trades,
        "long_trades": 3,
        "short_trades": 2,
        "bankrupt_intraday": False,
    }


def test_episode_accuracy_uses_future_only_for_evaluation():
    research = load_research()
    close = np.array([10, 10, 10, 10, 10, 11, 11], dtype=float)
    ma7 = np.array([9, 9, 9, 9, 9, 9, 9], dtype=float)
    context = SimpleNamespace(
        book=SimpleNamespace(close=close),
        features=SimpleNamespace(ma7=ma7),
    )
    events = [
        {"event": "arm_raw_cross", "signal_index": 0, "side": "long"},
        {"event": "confirm_delayed_episode", "signal_index": 0, "side": "long"},
    ]
    result = research.episode_accuracy(events, context, start_index=0, terminal_index=7)
    assert result["combined"]["evaluable"] == 1
    assert result["combined"]["precision"] == 1.0


def test_comparison_uses_more_positive_mdd_as_smaller_drawdown():
    research = load_research()
    candidate = {"status": "PASS", "metrics": metrics(20, -10)}
    control = {"status": "PASS", "metrics": metrics(15, -12)}
    result = research.comparison(candidate, control)
    assert result["dual_improvement"]
    assert result["return_delta_pp"] == 5
    assert result["mdd_delta_pp"] == 2


def test_stage_b_gate_requires_accuracy_and_v6_modules():
    research = load_research()
    candidate = run(metrics(20, -10), trades_sha="candidate")
    control_full = run(metrics(10, -15), trades_sha="control")
    control = {"full": control_full}
    row = {
        "full": candidate,
        "blocks": [candidate] * 6,
        "full_comparison": research.comparison(candidate, control_full),
        "wfo_comparison": research.comparison(candidate, control_full),
        "stress_comparison": research.comparison(candidate, control_full),
        "block_comparisons": [research.comparison(candidate, control_full)] * 6,
    }
    assert research.stage_b_gate(row, control)["status"] == "PASS"
    row["full"]["accuracy"]["combined"]["precision"] = 0.5
    assert research.stage_b_gate(row, control)["status"] == "FAIL"


def test_evaluation_gate_is_strict_dual_improvement():
    research = load_research()
    candidate = run(metrics(20, -10), trades_sha="candidate")
    control = run(metrics(15, -10), trades_sha="control")
    gate = research.evaluation_gate(candidate, control, candidate, control)
    assert gate["status"] == "FAIL"


def test_engine_start_keeps_first_flat_day_as_priming_only():
    research = load_research()
    assert research.engine_start((0, 54)) == 0
    assert research.engine_start((54, 108)) == 55
