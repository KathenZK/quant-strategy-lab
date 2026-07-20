from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / (
    "research/asset-portfolios/1h-multi-horizon-cross-sectional-ml-allocator/"
    "scripts/finalize_prospective_oos_adjudication.py"
)
SPEC = importlib.util.spec_from_file_location("finalize_oos_adjudication", SCRIPT)
assert SPEC and SPEC.loader
adjudication = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adjudication)

REVEAL_SCRIPT = SCRIPT.parent / "reveal_prospective_oos_once.py"
REVEAL_SPEC = importlib.util.spec_from_file_location(
    "reveal_oos_for_gate_tests", REVEAL_SCRIPT
)
assert REVEAL_SPEC and REVEAL_SPEC.loader
reveal = importlib.util.module_from_spec(REVEAL_SPEC)
REVEAL_SPEC.loader.exec_module(reveal)


def test_reveal_guard_rejects_early_access() -> None:
    with pytest.raises(RuntimeError, match="remains sealed"):
        adjudication.assert_reveal_time(pd.Timestamp("2026-10-20T21:04:59Z"))
    adjudication.assert_reveal_time(pd.Timestamp("2026-10-20T21:05:00Z"))


def test_static_non_oos_gates_are_already_pass() -> None:
    _, _, gates = adjudication.validate_static_evidence()
    assert gates
    assert all(gates.values())


def test_frozen_reveal_gate_names_match_contract() -> None:
    expected = {
        "three_month_return_gte_18_92pct",
        "annualized_return_gte_100pct",
        "max_drawdown_lte_20pct",
        "decision_win_rate_gte_55pct",
        "sharpe_gte_1_5",
        "profit_factor_gte_1_30",
        "active_decisions_gte_45",
        "completed_legs_gte_300",
        "positive_month_cohorts_gte_2",
        "stress_return_positive",
        "stress_drawdown_lte_25pct",
        "symbol_concentration_lte_25pct",
        "month_concentration_lte_35pct",
        "lgbm_beats_ridge_baseline",
        "lgbm_beats_rule_baseline",
    }
    assert adjudication.EXPECTED_REVEAL_GATES == expected


def passing_r4_metrics() -> dict[str, float | int]:
    return {
        "total_return": 0.1892,
        "annualized_return": 1.0,
        "max_drawdown": -0.20,
        "win_rate": 0.55,
        "sharpe": 1.50,
        "profit_factor": 1.30,
        "decision_count": 45,
        "trade_count": 300,
        "positive_fixed_month_cohorts": 2,
        "stress_total_return": 1e-12,
        "stress_max_drawdown": -0.25,
        "symbol_positive_profit_concentration": 0.25,
        "month_positive_profit_concentration": 0.35,
    }


def baseline_metrics(value: float = 0.10) -> dict[str, dict[str, float]]:
    return {
        "ridge_compact": {"total_return": value},
        "rule_carry_momentum": {"total_return": value},
    }


def test_all_frozen_gate_boundaries_pass_at_the_declared_thresholds() -> None:
    gates = reveal.hard_gates(passing_r4_metrics(), baseline_metrics())
    assert set(gates) == adjudication.EXPECTED_REVEAL_GATES
    assert all(gates.values())


@pytest.mark.parametrize(
    ("metric", "failed_value", "expected_gate"),
    [
        ("total_return", 0.189199, "three_month_return_gte_18_92pct"),
        ("annualized_return", 0.999999, "annualized_return_gte_100pct"),
        ("max_drawdown", -0.200001, "max_drawdown_lte_20pct"),
        ("win_rate", 0.549999, "decision_win_rate_gte_55pct"),
        ("sharpe", 1.499999, "sharpe_gte_1_5"),
        ("profit_factor", 1.299999, "profit_factor_gte_1_30"),
        ("decision_count", 44, "active_decisions_gte_45"),
        ("trade_count", 299, "completed_legs_gte_300"),
        ("positive_fixed_month_cohorts", 1, "positive_month_cohorts_gte_2"),
        ("stress_total_return", 0.0, "stress_return_positive"),
        ("stress_max_drawdown", -0.250001, "stress_drawdown_lte_25pct"),
        (
            "symbol_positive_profit_concentration",
            0.250001,
            "symbol_concentration_lte_25pct",
        ),
        (
            "month_positive_profit_concentration",
            0.350001,
            "month_concentration_lte_35pct",
        ),
    ],
)
def test_each_numeric_boundary_fails_in_the_strict_direction(
    metric: str, failed_value: float | int, expected_gate: str
) -> None:
    metrics = passing_r4_metrics()
    metrics[metric] = failed_value
    gates = reveal.hard_gates(metrics, baseline_metrics())
    assert gates[expected_gate] is False


@pytest.mark.parametrize("baseline", ["ridge_compact", "rule_carry_momentum"])
def test_lgbm_must_strictly_beat_each_baseline(baseline: str) -> None:
    metrics = passing_r4_metrics()
    baselines = baseline_metrics()
    baselines[baseline]["total_return"] = float(metrics["total_return"])
    gates = reveal.hard_gates(metrics, baselines)
    gate = (
        "lgbm_beats_ridge_baseline"
        if baseline == "ridge_compact"
        else "lgbm_beats_rule_baseline"
    )
    assert gates[gate] is False


def test_three_fixed_oos_month_cohorts_use_locked_boundaries() -> None:
    decisions = pd.DataFrame(
        {
            "ts": pd.to_datetime(
                [
                    "2026-07-19T00:00:00Z",
                    "2026-08-19T00:00:00Z",
                    "2026-09-19T00:00:00Z",
                ],
                utc=True,
            ),
            "portfolio_return": [1.0, -1.0, 2.0],
        }
    )
    assert reveal.fixed_month_cohort_returns(decisions) == pytest.approx(
        [0.03125, -0.03125, 0.0625]
    )
