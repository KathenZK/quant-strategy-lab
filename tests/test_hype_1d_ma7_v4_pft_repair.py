from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "research/hype/1d-ma7-asymmetric-body-trend/scripts"
    / "research_hype_1d_ma7_v4_pft_repair.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("hype_v4_pft_repair", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RESEARCH = load_module()


def metrics(return_pct, mdd_pct, trades=5, *, bankrupt=False):
    return {
        "net_return_pct": return_pct,
        "max_drawdown_pct": mdd_pct,
        "closed_trades": trades,
        "bankrupt_intraday": bankrupt,
    }


def test_window_start_semantics_are_frozen() -> None:
    assert RESEARCH.engine_start((0, 259)) == 0
    assert RESEARCH.engine_start((130, 173)) == 131
    assert RESEARCH.engine_start((269, 346)) == 270


def test_module_disable_mapping_is_exact() -> None:
    assert RESEARCH.enabled_modules("A000_V4") == []
    assert RESEARCH.enabled_modules("A111_PFT") == ["P", "F", "T"]
    assert RESEARCH.module_arm("A111_PFT", "P") == "A011_FT"
    assert RESEARCH.module_arm("A111_PFT", "F") == "A101_PT"
    assert RESEARCH.module_arm("A111_PFT", "T") == "A110_PF"
    assert RESEARCH.module_arm("A101_PT", "T") == "A100_P"


def test_fold_aggregation_compounds_return_and_uses_worst_mdd() -> None:
    folds = [
        {"metrics": {**metrics(10.0, -5.0, 2), "equity_multiple": 1.1, "long_trades": 1, "short_trades": 1}},
        {"metrics": {**metrics(-10.0, -8.0, 1), "equity_multiple": 0.9, "long_trades": 0, "short_trades": 1}},
    ]
    result = RESEARCH.aggregate_folds(folds)
    assert result["equity_multiple"] == pytest.approx(0.99)
    assert result["net_return_pct"] == pytest.approx(-1.0)
    assert result["max_drawdown_pct"] == -8.0
    assert result["closed_trades"] == 3


def test_comparison_requires_strict_dual_dominance_and_materiality() -> None:
    control = metrics(100.0, -20.0)
    good = RESEARCH.compare(metrics(105.0, -19.999), control)
    assert good["return_strictly_higher"]
    assert good["mdd_strictly_smaller"]
    assert good["material"]
    equality = RESEARCH.compare(metrics(100.0, -18.0), control)
    assert not equality["return_strictly_higher"]
    assert equality["mdd_strictly_smaller"]
    worse = RESEARCH.compare(metrics(99.0, -21.0), control)
    assert worse["double_worse"]


def test_activation_gate_uses_effect_events_not_display_fields() -> None:
    counts = {"p_delayed_confirm": 1, "f_reject": 2, "t_exit": 3}
    assert all(RESEARCH.activation_pass(module, counts) for module in "PFT")
    assert not RESEARCH.activation_pass("P", {"p_arm": 9})
    assert not RESEARCH.activation_pass("F", {"f_accept": 9})


def test_evaluation_gate_is_fail_closed_on_trade_floor() -> None:
    candidate = {
        "metrics": metrics(110.0, -18.0, 2),
        "ledger_audit": {"status": "PASS"},
    }
    control = {
        "metrics": metrics(100.0, -20.0, 4),
        "ledger_audit": {"status": "PASS"},
    }
    gate = RESEARCH.evaluation_gate(candidate, control)
    assert gate["comparison"]["return_strictly_higher"]
    assert gate["status"] == "FAIL"
    assert not gate["checks"]["candidate_trade_floor"]


def test_rank_key_prefers_worst_fold_then_smaller_structure() -> None:
    def trial(arm_id, fold_delta, wfo_delta=10.0):
        return {
            "arm_id": arm_id,
            "gate": {
                "fold_comparisons": [{"return_delta_pp": fold_delta}],
                "wfo_comparison": {"return_delta_pp": wfo_delta, "mdd_delta_pp": 3.0},
                "full_comparison": {"return_delta_pp": 6.0, "mdd_delta_pp": 2.0},
            },
        }

    assert RESEARCH.rank_key(trial("A001_T", 2.0)) < RESEARCH.rank_key(
        trial("A111_PFT", 1.0)
    )
    assert RESEARCH.rank_key(trial("A001_T", 1.0)) < RESEARCH.rank_key(
        trial("A011_FT", 1.0)
    )


def test_locked_json_is_exclusive_and_hash_verified(tmp_path) -> None:
    path = tmp_path / "artifact.json"
    digest = RESEARCH.write_locked(path, {"value": 1})
    loaded, actual = RESEARCH.read_locked(path)
    assert loaded == {"value": 1}
    assert actual == digest
    with pytest.raises(RuntimeError, match="already exists"):
        RESEARCH.write_locked(path, {"value": 2})


def test_self_test_does_not_create_artifacts() -> None:
    before = {
        path: path.exists()
        for path in (
            RESEARCH.MANIFEST_PATH,
            RESEARCH.TRIALS_PATH,
            RESEARCH.DEVELOPMENT_PATH,
        )
    }
    assert RESEARCH.self_test() == {"status": "PASS", "arms": 8}
    assert {path: path.exists() for path in before} == before
