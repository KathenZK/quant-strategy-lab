from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = (
    ROOT
    / "research/asset-portfolios/15m-asset-specific-six-strategy-selector/scripts"
)
sys.path.insert(0, str(SCRIPTS))

import reveal_binance_as6s_v6_mark_joint_future_oos as reveal  # noqa: E402


def passing_results() -> dict[str, object]:
    row = {
        "trades": 30,
        "wins": 24,
        "win_rate": 0.80,
        "total_return": 1e-12,
        "max_dd": -0.199999,
        "trades_per_day": 1.0,
    }
    scenarios = {
        scenario: {
            "full": deepcopy(row),
            "future_3m_oos": deepcopy(row),
        }
        for scenario in reveal.account.SCENARIOS
    }
    return {
        mode: {"scenarios": deepcopy(scenarios)}
        for mode in reveal.MODES
    }


def test_all_frozen_final_gate_boundaries_pass() -> None:
    results = passing_results()
    results["nonpreemptive"]["scenarios"]["base"]["future_3m_oos"][
        "trades_per_day"
    ] = 2.0
    gates = reveal.final_gates(results)

    assert set(gates) == set(reveal.MODES)
    for route in gates.values():
        assert route["pass"] is True
        assert len(route["checks"]) == 20
        assert all(route["checks"].values())


@pytest.mark.parametrize("field,bad_value,suffix", [
    ("win_rate", 0.799999, "win_ge_80pct"),
    ("max_dd", -0.20, "dd_lt_20pct"),
    ("total_return", 0.0, "return_positive"),
])
@pytest.mark.parametrize("scenario", ["base", "stress_8bps", "k_plus_2"])
@pytest.mark.parametrize("window", ["full", "future_3m_oos"])
def test_each_scenario_window_hard_gate_fails_closed(
    field: str,
    bad_value: float,
    suffix: str,
    scenario: str,
    window: str,
) -> None:
    results = passing_results()
    results["nonpreemptive"]["scenarios"][scenario][window][field] = bad_value

    gates = reveal.final_gates(results)
    check = f"{scenario}_{window}_{suffix}"
    assert gates["nonpreemptive"]["checks"][check] is False
    assert gates["nonpreemptive"]["pass"] is False
    assert gates["strong_breakout_preemptive"]["pass"] is True


@pytest.mark.parametrize("trades", [0, 29])
def test_future_oos_minimum_trade_count_fails_closed(trades: int) -> None:
    results = passing_results()
    results["nonpreemptive"]["scenarios"]["base"]["future_3m_oos"][
        "trades"
    ] = trades
    gates = reveal.final_gates(results)
    assert gates["nonpreemptive"]["checks"]["future_oos_trades_ge_30"] is False
    assert gates["nonpreemptive"]["pass"] is False


@pytest.mark.parametrize("frequency", [0.999999, 2.000001])
def test_future_oos_frequency_outside_one_to_two_fails_closed(
    frequency: float,
) -> None:
    results = passing_results()
    results["strong_breakout_preemptive"]["scenarios"]["base"][
        "future_3m_oos"
    ]["trades_per_day"] = frequency
    gates = reveal.final_gates(results)
    assert (
        gates["strong_breakout_preemptive"]["checks"]
        ["future_oos_frequency_1_to_2"]
        is False
    )
    assert gates["strong_breakout_preemptive"]["pass"] is False


def test_gate_contract_has_no_missing_or_extra_check_names() -> None:
    expected = {
        f"{scenario}_{window}_{suffix}"
        for scenario in reveal.account.SCENARIOS
        for window in ("full", "future_3m_oos")
        for suffix in ("win_ge_80pct", "dd_lt_20pct", "return_positive")
    } | {"future_oos_trades_ge_30", "future_oos_frequency_1_to_2"}

    gates = reveal.final_gates(passing_results())
    for mode in reveal.MODES:
        assert set(gates[mode]["checks"]) == expected


def test_main_refuses_before_window_without_reconstruction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reconstructed = False

    def forbidden_reconstruct(*_args: object, **_kwargs: object) -> None:
        nonlocal reconstructed
        reconstructed = True
        raise AssertionError("future reconstruction must not run before the clock gate")

    monkeypatch.setattr(
        reveal,
        "parse_args",
        lambda: SimpleNamespace(check_only=False, historical_parity=False),
    )
    monkeypatch.setattr(reveal, "load_manifest", lambda: {})
    monkeypatch.setattr(reveal.verify, "main", lambda: None)
    monkeypatch.setattr(reveal, "future_ready", lambda: (False, "synthetic pre-end"))
    monkeypatch.setattr(reveal, "reconstruct", forbidden_reconstruct)

    with pytest.raises(RuntimeError, match="refused before the complete locked window"):
        reveal.main()
    assert reconstructed is False


def test_check_only_reports_no_future_read_without_reconstruction(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        reveal,
        "parse_args",
        lambda: SimpleNamespace(check_only=True, historical_parity=False),
    )
    monkeypatch.setattr(reveal, "load_manifest", lambda: {})
    monkeypatch.setattr(reveal.verify, "main", lambda: None)
    monkeypatch.setattr(reveal, "future_ready", lambda: (False, "synthetic pre-end"))
    monkeypatch.setattr(
        reveal,
        "reconstruct",
        lambda *_args, **_kwargs: pytest.fail("check-only reconstructed market data"),
    )

    reveal.main()
    payload = json.loads(capsys.readouterr().out)
    assert payload["future_oos_ready"] is False
    assert payload["future_market_data_read"] is False
