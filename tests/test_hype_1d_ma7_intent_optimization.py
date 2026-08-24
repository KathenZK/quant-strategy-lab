from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pandas as pd
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "research/hype/1d-ma7-asymmetric-body-trend/scripts"
    / "research_hype_1d_ma7_intent_optimization.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("hype_1d_ma7_intent_optimization", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RESEARCH = load_module()


@pytest.fixture(scope="module")
def manifest():
    return RESEARCH.build_manifest()


def test_manifest_has_only_deterministic_ids_parents_and_configs(
    manifest, monkeypatch
) -> None:
    assert manifest["no_results"] is True
    assert "results" not in manifest
    assert len(manifest["structure_oat"]) == 9
    assert len(manifest["stages"]["A"]) == 108
    assert len(manifest["stages"]["B"]) == 30
    assert len(manifest["stages"]["C"]) == 27
    assert len(manifest["stages"]["D"]) == 9
    ids = [
        row["id"]
        for rows in manifest["stages"].values()
        for row in rows
    ]
    assert len(ids) == len(set(ids)) == 174
    assert ids[0] == "A001"
    assert ids[107] == "A108"
    assert ids[-1] == "D009"
    assert manifest["stages"]["B"][0]["parent"] == "A_RANK_01"
    assert manifest["stages"]["C"][0]["parent"] == "B_RANK_01"
    assert manifest["stages"]["D"][0]["parent"] == "C_RANK_01"
    assert manifest["pins"]["trace_sha256"] == RESEARCH._sha256(
        RESEARCH.TRACE_PATH
    )
    assert "trace" in RESEARCH.RuntimeContext.__dataclass_fields__
    assert {
        "trace",
        "fair_metrics",
        "evidence",
        "renderer",
    }.issubset(RESEARCH.RuntimeContext.__dataclass_fields__)
    assert len(RESEARCH._manifest_test_files()) == 8
    assert {
        "trace_sha256",
        "fair_metrics_sha256",
        "evidence_sha256",
        "renderer_sha256",
        "indicator_sha256",
        "contract_sha256",
    }.issubset(RESEARCH._tested_implementation_hashes())
    preflight = {
        "self_test_status": "PASS",
        "pytest_status": "PASS",
        "pytest_passed": 83,
        "tests": RESEARCH._manifest_test_files(),
        "tested_implementation": RESEARCH._tested_implementation_hashes(),
    }
    market_audit = {
        "hourly_sha256": "a" * 64,
        "phase_input_hourly_sha256": "b" * 64,
        "funding_sha256": "c" * 64,
    }
    market = {
        "book_count": 432,
        "terminal_ts": "2026-08-06T00:00:00+00:00",
        "market_audit": market_audit,
        "market_audit_sha256": RESEARCH.canonical_hash(market_audit),
    }
    locked = RESEARCH.build_manifest(
        preflight=preflight,
        market_evidence=market,
    )
    monkeypatch.setattr(RESEARCH, "_load_manifest_market_evidence", lambda: market)
    RESEARCH._assert_manifest(locked)
    locked["preflight"]["pytest_passed"] = 45
    with pytest.raises(RuntimeError, match="preflight"):
        RESEARCH._assert_manifest(locked)


def test_manifest_freezes_all_splits_and_counts(manifest, monkeypatch) -> None:
    assert manifest["splits"] == {
        "development": [0, 259],
        "wfo": [[130, 173], [173, 216], [216, 259]],
        "validation": [269, 346],
        "holdout": [356, 432],
        "full": [0, 432],
    }
    assert manifest["expected_counts"] == {
        "structure_oat": 9,
        "A": 108,
        "B": 30,
        "C": 27,
        "D": 9,
        "numeric_total": 174,
    }
    calls = []

    def fake_v4(start, end, **kwargs):
        calls.append((start, end, kwargs))
        return SimpleNamespace(metrics={})

    monkeypatch.setattr(RESEARCH, "run_v4", fake_v4)
    segmented = RESEARCH.run_v4_flat_start(130, 173, slippage=0.0008)
    full = RESEARCH.run_v4_flat_start(0, 259)
    assert calls == [
        (131, 173, {"slippage": 0.0008, "signal_lag": 0, "retain": False}),
        (0, 259, {"slippage": 0.0004, "signal_lag": 0, "retain": False}),
    ]
    assert segmented.metrics["requested_start"] == 130
    assert segmented.metrics["engine_start"] == 131
    assert full.metrics["requested_start"] == full.metrics["engine_start"] == 0


def test_config_hash_is_canonical_and_order_independent() -> None:
    left = {"b": 2, "a": {"y": 2.0, "x": 1}}
    right = {"a": {"x": 1, "y": 2.0}, "b": 2}
    assert RESEARCH.canonical_hash(left) == RESEARCH.canonical_hash(right)
    assert RESEARCH.canonical_hash(left) != RESEARCH.canonical_hash(
        {"a": {"x": 1, "y": 2.1}, "b": 2}
    )


def test_double_dominance_uses_strict_unrounded_and_material_gates() -> None:
    comparator = {"net_return_pct": 10.0, "max_drawdown_pct": -20.0}
    return_material = RESEARCH.double_dominance(
        {"net_return_pct": 15.0, "max_drawdown_pct": -19.0}, comparator
    )
    assert return_material["pass"] is True
    mdd_material = RESEARCH.double_dominance(
        {"net_return_pct": 10.1, "max_drawdown_pct": -18.0}, comparator
    )
    assert mdd_material["pass"] is True
    not_material = RESEARCH.double_dominance(
        {"net_return_pct": 14.999999999, "max_drawdown_pct": -18.000000001},
        comparator,
    )
    assert not_material["pass"] is False
    equality = RESEARCH.double_dominance(
        {"net_return_pct": 15.0, "max_drawdown_pct": -20.0}, comparator
    )
    assert equality["pass"] is False
    assert RESEARCH.no_double_worse(
        {"net_return_pct": 9.0, "max_drawdown_pct": -19.0}, comparator
    )
    assert not RESEARCH.no_double_worse(
        {"net_return_pct": 9.0, "max_drawdown_pct": -21.0}, comparator
    )
    comparable = {
        "net_return_pct": 15.0,
        "max_drawdown_pct": -19.0,
        "gate_eligible": True,
        "gate_mdd_basis": "daily_extreme_favorable_then_adverse",
        "bankrupt": False,
    }
    comparable_v4 = {
        **comparator,
        "gate_eligible": True,
        "gate_mdd_basis": "daily_extreme_favorable_then_adverse",
        "bankrupt": False,
    }
    assert RESEARCH.double_dominance(comparable, comparable_v4)["pass"] is True
    with pytest.raises(RuntimeError, match="not eligible"):
        RESEARCH.double_dominance(
            {**comparable, "gate_eligible": False}, comparable_v4
        )
    with pytest.raises(RuntimeError, match="bankrupt"):
        RESEARCH.double_dominance(
            {**comparable, "bankrupt": True}, comparable_v4
        )

    common = {
        "equity_multiple": 1.1,
        "net_return_pct": 10.0,
        "max_drawdown_pct": -5.0,
        "closed_trades": 1,
        "long_trades": 1,
        "short_trades": 0,
    }
    candidate_units = RESEARCH._normalize_metrics(
        SimpleNamespace(
            metrics={**common, "cost": 0.02, "funding_payment": -0.001}
        )
    )
    v4_units = RESEARCH._normalize_metrics(
        SimpleNamespace(
            metrics={
                **common,
                "cost_pct_initial": 2.0,
                "funding_pct_initial": -0.1,
            }
        )
    )
    assert candidate_units["cost_pct_initial"] == pytest.approx(2.0)
    assert candidate_units["funding_pct_initial"] == pytest.approx(-0.1)
    assert candidate_units["cost_equity_units"] == pytest.approx(0.02)
    assert candidate_units["funding_equity_units"] == pytest.approx(-0.001)
    assert candidate_units["cost"] == pytest.approx(0.02)
    assert candidate_units["funding_payment"] == pytest.approx(-0.001)
    assert candidate_units["cost_pct_initial"] == v4_units["cost_pct_initial"]
    assert (
        candidate_units["funding_pct_initial"]
        == v4_units["funding_pct_initial"]
    )
    adverse = RESEARCH._trade_adverse_audit(
        [
            {
                "trade_id": "T1",
                "side": "long",
                "entry_ts": "2026-01-01T00:00:00+00:00",
                "exit_ts": "2026-01-02T00:00:00+00:00",
                "entry_price": 100.0,
                "lowest": 90.0,
                "highest": 110.0,
                "mae_return": -0.1,
                "exit_reason": "terminal_flatten",
            }
        ]
    )
    assert adverse["trade_count"] == 1
    assert adverse["worst_max_adverse_return"] == pytest.approx(-0.1)


def test_wfo_aggregate_multiplies_returns_and_uses_worst_exact_mdd() -> None:
    aggregate = RESEARCH.aggregate_wfo(
        [
            {
                "equity_multiple": 1.1,
                "max_drawdown_pct": -5.0,
                "closed_trades": 2,
                "turnover": 3.0,
            },
            {
                "equity_multiple": 0.9,
                "max_drawdown_pct": -12.0,
                "closed_trades": 1,
                "turnover": 2.0,
            },
            {
                "equity_multiple": 1.2,
                "max_drawdown_pct": -7.0,
                "closed_trades": 3,
                "turnover": 4.0,
            },
        ]
    )
    assert aggregate["equity_multiple"] == pytest.approx(1.188)
    assert aggregate["net_return_pct"] == pytest.approx(18.8)
    assert aggregate["max_drawdown_pct"] == -12.0
    assert aggregate["closed_trades"] == 6
    assert aggregate["turnover"] == 9.0


def test_initial_oat_records_dormancy_but_only_errors_block_search(
    monkeypatch,
) -> None:
    rows = [
        {
            "id": "OAT00_FULL_INTENT",
            "status": "OK",
            "trade_signatures_sha256": "same",
            "activation_counts": {"arm_create": 2, "arm_confirm": 1},
        },
        {
            "id": "OAT01_VARIANT",
            "status": "OK",
            "trade_signatures_sha256": "same",
            "activation_counts": {"arm_create": 1, "arm_confirm": 1},
        },
    ]
    gate = RESEARCH._oat_wiring_gate(rows)
    assert gate == {
        "pass": True,
        "errors": [],
        "historically_dormant": ["OAT01_VARIANT"],
        "activation_count_deltas": {
            "OAT01_VARIANT": {"arm_create": -1},
        },
    }
    rows[1] = {"id": "OAT01_VARIANT", "status": "ERROR"}
    assert RESEARCH._oat_wiring_gate(rows)["pass"] is False
    anchor_trade = {
        "trade_id": "ANCHOR-001",
        "side": "long",
        "entry_signal_ts": "2026-01-01T00:00:00+00:00",
        "entry_ts": "2026-01-02T00:00:00+00:00",
        "exit_ts": "2026-01-03T00:00:00+00:00",
        "entry_reason": "fresh_long_cross",
        "exit_reason": "long_slope_loss",
    }
    added_trade = {
        "trade_id": "VARIANT-002",
        "side": "short",
        "entry_signal_ts": "2026-01-04T00:00:00+00:00",
        "entry_ts": "2026-01-05T00:00:00+00:00",
        "exit_ts": "2026-01-06T00:00:00+00:00",
        "entry_reason": "fresh_short_cross",
        "exit_reason": "short_slope_loss",
    }
    evidence = [
        {
            "id": "ANCHOR",
            "status": "OK",
            "path_hash": "raw-anchor",
            "behavior_path_hash": "behavior-same",
            "trades": [anchor_trade],
        },
        {
            "id": "VARIANT",
            "status": "OK",
            "path_hash": "raw-diff-from-display-band",
            "behavior_path_hash": "behavior-same",
            "trades": [{**anchor_trade, "trade_id": "VARIANT-001"}, added_trade],
        },
    ]
    RESEARCH._attach_oat_differences(evidence, "ANCHOR")
    assert evidence[1]["path_changed"] is False
    assert evidence[0]["trade_path_changed"] is False
    assert evidence[1]["trade_path_changed"] is True
    assert evidence[1]["removed_trade_signatures"] == []
    assert evidence[1]["added_trade_signatures"] == [
        RESEARCH._trade_signatures([added_trade])[0]
    ]
    assert evidence[1]["activation_count_deltas"] == {}

    state_trace = {
        "rows": [{"ts": "2026-01-01T00:00:00+00:00", "side": 0}],
        "events": [{"event": "arm_create"}],
        "activation_counts": {"arm_create": 1},
        "terminal": {"pending_suppressed": False},
    }
    fake_result = SimpleNamespace(
        metrics={
            "equity_multiple": 1.0,
            "net_return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "closed_trades": 0,
        },
        actions=[{"reason": "fresh_cross_long"}],
        trades=[],
        path=[],
    )
    monkeypatch.setattr(RESEARCH, "run_candidate", lambda *_args, **_kwargs: fake_result)
    monkeypatch.setattr(
        RESEARCH,
        "_replay_candidate_state_trace",
        lambda *_args, **_kwargs: state_trace,
    )
    monkeypatch.setattr(
        RESEARCH,
        "_candidate_gate_metrics",
        lambda *_args, **_kwargs: (
            RESEARCH._normalize_metrics(fake_result),
            {"status": "PASS"},
        ),
    )
    monkeypatch.setattr(
        RESEARCH,
        "_assert_trace_parity",
        lambda *_args, **_kwargs: {"status": "PASS"},
    )
    evaluated = RESEARCH._evaluate_oat(
        {
            "id": "SYNTHETIC_OAT",
            "parent": None,
            "role": "synthetic",
            "config": RESEARCH.base_config(),
        }
    )
    assert evaluated["status"] == "OK"
    assert evaluated["state_trace"] == state_trace
    assert evaluated["activation_counts"] == {"arm_create": 1}
    assert evaluated["action_activation_counts"] == {"fresh_cross_long": 1}


def _trial(trial_id: str, **ranking):
    defaults = {
        "dominance_domains": 2,
        "wfo_return_delta_pp": 5.0,
        "worst_fold_return_delta_pp": 1.0,
        "wfo_mdd_delta_pp": 2.0,
        "full_return_delta_pp": 4.0,
        "active_parameter_count": 8,
        "turnover": 10.0,
    }
    defaults.update(ranking)
    return {"id": trial_id, "status": "OK", "ranking": defaults}


def test_rank_is_lexicographic_and_final_tie_breaks_by_id() -> None:
    trials = [
        _trial("A003"),
        _trial("A002", dominance_domains=1, wfo_return_delta_pp=100.0),
        _trial("A001"),
        {"id": "ERR", "status": "ERROR"},
    ]
    ranked = RESEARCH.rank_trials(trials)
    assert [row["id"] for row in ranked] == ["A001", "A003", "A002"]
    templates = RESEARCH.build_manifest()["stages"]["C"]
    skipped = RESEARCH._skipped_stage(
        templates,
        "C",
        "Stage B supplied 2 of 3 required valid parents",
    )
    assert len(skipped) == 27
    assert [row["id"] for row in skipped] == [row["id"] for row in templates]
    assert {row["status"] for row in skipped} == {"SKIPPED"}
    assert {row["skip_reason_code"] for row in skipped} == {
        "UPSTREAM_INSUFFICIENT"
    }
    assert all(row["config"] is None and row["config_hash"] is None for row in skipped)


def test_slope_recompute_is_causal_and_uses_l_normalization() -> None:
    index = pd.date_range("2026-01-01", periods=8, freq="1D", tz="UTC")
    daily = pd.DataFrame(
        {
            "ma7": [100.0, 101.0, 103.0, 106.0, 110.0, 115.0, 121.0, 128.0],
            "atr7": [2.0] * 8,
        },
        index=index,
    )
    original = daily.copy(deep=True)
    baseline = RESEARCH.recompute_slope(daily, 2)
    assert baseline.loc[index[2], "slope_atr"] == pytest.approx(0.75)
    changed = daily.copy()
    changed.loc[index[6]:, "ma7"] = [999.0, 1000.0]
    changed_result = RESEARCH.recompute_slope(changed, 2)
    pd.testing.assert_series_equal(
        baseline.loc[: index[5], "slope_atr"],
        changed_result.loc[: index[5], "slope_atr"],
    )
    pd.testing.assert_frame_equal(daily, original)


def test_self_test_does_not_load_runtime(monkeypatch, tmp_path) -> None:
    def forbidden():
        raise AssertionError("self-test must not load market or run candidates")

    monkeypatch.setattr(RESEARCH, "load_runtime", forbidden)
    result = RESEARCH.self_test()
    assert result["status"] == "PASS"
    assert result["counts"]["numeric_total"] == 174

    subprocess_calls = []

    def passing_subprocess(command, **kwargs):
        subprocess_calls.append((command, kwargs))
        return SimpleNamespace(
            returncode=0,
            stdout="................................................................."
            ".................. [100%]\n83 passed in 2.00s\n",
            stderr="",
        )

    monkeypatch.setattr(RESEARCH.subprocess, "run", passing_subprocess)
    preflight = RESEARCH._run_manifest_preflight()
    assert preflight["pytest_passed"] == 83
    assert "duration" not in preflight
    assert len(preflight["tests"]) == 8
    assert subprocess_calls[0][0][0] == sys.executable
    assert "PYTEST_ADDOPTS" not in subprocess_calls[0][1]["env"]

    def failing_subprocess(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout="45 passed in 2.00s\n", stderr="")

    monkeypatch.setattr(RESEARCH.subprocess, "run", failing_subprocess)
    with pytest.raises(RuntimeError, match="exactly 83 passed"):
        RESEARCH._run_manifest_preflight()

    validation_path = tmp_path / "validation.json"
    validation_sha_path = tmp_path / "validation.sha256"
    monkeypatch.setattr(RESEARCH, "VALIDATION_PATH", validation_path)
    monkeypatch.setattr(RESEARCH, "VALIDATION_SHA_PATH", validation_sha_path)
    monkeypatch.setattr(
        RESEARCH,
        "_load_champion",
        lambda: ({"config": RESEARCH.base_config()}, "champion-hash"),
    )

    def evaluation_error(*_args, **_kwargs):
        raise RuntimeError("locked evaluation failed")

    monkeypatch.setattr(RESEARCH, "_eval_once", evaluation_error)
    validation = RESEARCH.stage_validation()
    assert validation["status"] == "ERROR"
    saved_validation, _ = RESEARCH._read_locked_json(
        validation_path, validation_sha_path
    )
    assert saved_validation["failure_blocks_holdout"] is True

    validation_pass_path = tmp_path / "validation-pass.json"
    validation_pass_sha_path = tmp_path / "validation-pass.sha256"
    RESEARCH._write_locked_json(
        validation_pass_path,
        validation_pass_sha_path,
        {"status": "PASS", "champion_sha256": "champion-hash"},
    )
    holdout_path = tmp_path / "holdout.json"
    holdout_sha_path = tmp_path / "holdout.sha256"
    monkeypatch.setattr(RESEARCH, "VALIDATION_PATH", validation_pass_path)
    monkeypatch.setattr(RESEARCH, "VALIDATION_SHA_PATH", validation_pass_sha_path)
    monkeypatch.setattr(RESEARCH, "HOLDOUT_PATH", holdout_path)
    monkeypatch.setattr(RESEARCH, "HOLDOUT_SHA_PATH", holdout_sha_path)
    holdout = RESEARCH.stage_holdout()
    assert holdout["status"] == "ERROR"
    saved_holdout, _ = RESEARCH._read_locked_json(holdout_path, holdout_sha_path)
    assert saved_holdout["locked_retrospective_oos"] is True
