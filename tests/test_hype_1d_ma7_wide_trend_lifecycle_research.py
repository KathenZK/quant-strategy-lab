from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "research/hype/1d-ma7-asymmetric-body-trend/scripts"
    / "research_hype_1d_ma7_wide_trend_lifecycle.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("hype_wtl_research", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RESEARCH = load_module()


def metrics(
    return_pct: float,
    mdd: float,
    *,
    daily_mdd: float = -20.0,
    trades: int = 10,
    long_trades: int = 5,
    short_trades: int = 5,
    bankrupt: bool = False,
) -> dict[str, object]:
    return {
        "equity_multiple": 1.0 + return_pct / 100.0,
        "net_return_pct": return_pct,
        "chronological_1h_mdd_pct": mdd,
        "daily_extreme_mdd_pct": daily_mdd,
        "closed_trades": trades,
        "long_trades": long_trades,
        "short_trades": short_trades,
        "bankrupt_intraday": bankrupt,
        "max_marked_leverage": 1.0,
    }


def run(
    row: dict[str, object],
    *,
    trade_hash: str = "candidate",
    counts: dict[str, int] | None = None,
) -> dict[str, object]:
    return {
        "status": "PASS",
        "metrics": row,
        "trades_sha256": trade_hash,
        "activation_counts": counts
        or {"long_trail_exit": 1, "short_trail_exit": 0, "short_rsi_exit": 0},
    }


def test_window_boundaries_and_flat_start_are_frozen() -> None:
    assert RESEARCH.D_FULL == (0, 259)
    assert RESEARCH.V_FULL == (269, 346)
    assert RESEARCH.H_EVAL == (356, 432)
    assert RESEARCH.engine_start(RESEARCH.D_FULL) == 0
    assert RESEARCH.engine_start(RESEARCH.V_FULL) == 270
    assert RESEARCH.engine_start((130, 173)) == 131


def test_comparison_is_strict_and_material() -> None:
    control = metrics(100.0, -20.0)
    equality = RESEARCH.compare(metrics(100.0, -18.0), control)
    assert not equality["return_higher"]
    assert equality["mdd_smaller"] and equality["material"]
    good = RESEARCH.compare(metrics(105.0, -19.999), control)
    assert good["return_higher"] and good["mdd_smaller"] and good["material"]
    assert RESEARCH.compare(metrics(99.0, -21.0), control)["double_worse"]


def test_fold_aggregation_compounds_and_keeps_worst_mdd() -> None:
    folds = [run(metrics(10.0, -5.0, trades=2)), run(metrics(-10.0, -8.0, trades=1))]
    row = RESEARCH.aggregate_folds(folds)
    assert row["equity_multiple"] == pytest.approx(0.99)
    assert row["net_return_pct"] == pytest.approx(-1.0)
    assert row["chronological_1h_mdd_pct"] == -8.0
    assert row["closed_trades"] == 3


def test_prepass_requires_both_domain_dominance_path_and_v_exit() -> None:
    controls = {
        "D": run(metrics(100.0, -20.0), trade_hash="control-d"),
        "V": run(metrics(10.0, -10.0, trades=3), trade_hash="control-v"),
    }
    row = {
        "D": run(metrics(106.0, -18.0)),
        "V": run(metrics(16.0, -8.0, trades=3)),
    }
    assert RESEARCH.prepass_gate(row, controls)["status"] == "PASS"
    row["V"]["activation_counts"] = {
        "long_trail_exit": 0,
        "short_trail_exit": 0,
        "short_rsi_exit": 0,
    }
    gate = RESEARCH.prepass_gate(row, controls)
    assert gate["status"] == "FAIL"
    assert not gate["checks"]["V_exit_activation"]


def test_deep_gate_requires_rolling_dual_and_four_active_pairs() -> None:
    base_fold = run(metrics(10.0, -10.0, trades=1))
    candidate_fold = run(metrics(12.0, -8.0, trades=1))
    controls = {
        "stress_D": run(metrics(100.0, -20.0)),
        "stress_V": run(metrics(10.0, -10.0)),
        "folds": [base_fold] * 6,
        "rolling": RESEARCH.aggregate_folds([base_fold] * 6),
    }
    row = {
        "stress": {"D": run(metrics(106.0, -18.0)), "V": run(metrics(16.0, -8.0))},
        "funding_off": {"D": run(metrics(106.0, -18.0)), "V": run(metrics(16.0, -8.0))},
        "folds": [candidate_fold] * 6,
    }
    gate = RESEARCH.deep_gate(row, controls)
    assert gate["status"] == "PASS"
    row["folds"] = [run(metrics(12.0, -8.0, trades=0))] * 3 + [candidate_fold] * 3
    assert RESEARCH.deep_gate(row, controls)["status"] == "FAIL"


def test_ablation_gate_rejects_dormant_and_isolated_candidate() -> None:
    config = SimpleNamespace(enabled_modules=lambda: ["long_exit"])
    controls = {
        "D": run(metrics(100.0, -20.0), trade_hash="control-d"),
        "V": run(metrics(10.0, -10.0, trades=3), trade_hash="control-v"),
    }
    candidate = {
        "D": run(metrics(106.0, -18.0), counts={"long_trail_exit": 1}),
        "V": run(metrics(16.0, -8.0, trades=3), counts={"long_trail_exit": 1}),
    }
    leave = [
        {
            "module": "long_exit",
            "D": run(metrics(100.0, -20.0), trade_hash="disabled-d"),
            "V": run(metrics(10.0, -10.0, trades=3), trade_hash="disabled-v"),
        }
    ]
    neighbor = {
        "D": run(metrics(105.0, -18.0)),
        "V": run(metrics(15.0, -8.0, trades=3)),
    }
    assert RESEARCH._ablation_gate(
        config=config,
        candidate=candidate,
        leave_one_out=leave,
        neighbors=[neighbor],
        controls=controls,
    )["status"] == "PASS"
    assert RESEARCH._ablation_gate(
        config=config,
        candidate=candidate,
        leave_one_out=leave,
        neighbors=[],
        controls=controls,
    )["status"] == "FAIL"


def test_leverage_eligibility_requires_both_domains_stress_and_cap() -> None:
    one_x = {"D": run(metrics(100.0, -20.0)), "V": run(metrics(10.0, -10.0))}
    row = {}
    for label, ret, mdd in (("D", 120.0, -30.0), ("V", 20.0, -15.0)):
        row[label] = {
            "base": run(metrics(ret, mdd)),
            "stress": run(metrics(ret - 2.0, mdd - 1.0)),
            "funding_off": run(metrics(ret + 1.0, mdd)),
        }
    assert RESEARCH.leverage_eligible(row, one_x, 35.0)
    row["V"]["stress"] = {"status": "ERROR"}
    assert not RESEARCH.leverage_eligible(row, one_x, 35.0)


def test_final_gate_is_fail_closed_on_path_equality_and_trade_floor() -> None:
    control = run(metrics(10.0, -10.0, trades=3), trade_hash="same")
    candidate = run(metrics(16.0, -8.0, trades=3), trade_hash="different")
    assert RESEARCH.final_evaluation_gate(candidate, control)["status"] == "PASS"
    candidate["trades_sha256"] = "same"
    assert RESEARCH.final_evaluation_gate(candidate, control)["status"] == "FAIL"
    candidate = run(metrics(16.0, -8.0, trades=2), trade_hash="different")
    assert RESEARCH.final_evaluation_gate(candidate, control)["status"] == "FAIL"


def test_locked_json_is_exclusive_and_hash_verified(tmp_path: Path) -> None:
    path = tmp_path / "artifact.json"
    digest = RESEARCH.write_locked(path, {"value": 1})
    loaded, actual = RESEARCH.read_locked(path)
    assert loaded == {"value": 1}
    assert actual == digest
    with pytest.raises(RuntimeError, match="already exists"):
        RESEARCH.write_locked(path, {"value": 2})


def test_self_test_does_not_create_artifacts() -> None:
    paths = (RESEARCH.MANIFEST_PATH, RESEARCH.STAGE_A_PATH, RESEARCH.HOLDOUT_PATH)
    before = {path: path.exists() for path in paths}
    assert RESEARCH.self_test() == {
        "status": "PASS",
        "stage_a_count": 555,
        "max_combo_count": 624,
        "leverage_count": 9,
    }
    assert {path: path.exists() for path in paths} == before

