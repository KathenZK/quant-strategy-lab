from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / (
    "research/hype/1d-ma7-asymmetric-body-trend/scripts/"
    "observe_hype_1d_ma7_profit_exit_handoff_continuity.py"
)


def load():
    spec = importlib.util.spec_from_file_location("pehc_prospective_test_module", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def trade(
    side: str,
    exit_ts: str,
    *,
    reason: str = "native_exit",
) -> dict:
    return {"side": side, "exit_ts": exit_ts, "exit_reason": reason}


def sufficient_trades(start: pd.Timestamp) -> list[dict]:
    return [
        trade("long", (start + pd.Timedelta(days=10)).isoformat()),
        trade("short", (start + pd.Timedelta(days=20)).isoformat()),
        trade("long", (start + pd.Timedelta(days=30)).isoformat()),
        trade("short", (start + pd.Timedelta(days=40)).isoformat()),
        trade("long", (start + pd.Timedelta(days=50)).isoformat()),
    ]


def test_locked_json_roundtrip_and_tamper_detection(tmp_path: Path) -> None:
    module = load()
    path = tmp_path / "evidence.json"
    digest = module.write_locked(path, {"b": 2, "a": 1})
    payload, actual = module.read_locked(path)
    assert payload == {"a": 1, "b": 2}
    assert actual == digest
    path.write_text('{"a": 2}\n', encoding="utf-8")
    with pytest.raises(RuntimeError, match="invalid sidecar"):
        module.read_locked(path)


def test_latest_terminal_requires_a_complete_prior_utc_day() -> None:
    module = load()
    ts = pd.date_range("2026-08-09T00:00:00Z", periods=49, freq="h")
    assert module._latest_complete_terminal(pd.DataFrame({"ts": ts})) == pd.Timestamp(
        "2026-08-11T00:00:00Z"
    )
    broken = pd.DataFrame({"ts": ts.delete(30)})
    with pytest.raises(RuntimeError, match="not continuous"):
        module._latest_complete_terminal(broken)


def test_prospective_window_is_zero_before_start_and_cold_flat_after() -> None:
    module = load()
    pre = SimpleNamespace(
        book=SimpleNamespace(
            ts=pd.date_range("2026-08-01T00:00:00Z", periods=5, freq="D"),
            count=5,
            terminal_ts=pd.Timestamp("2026-08-06T00:00:00Z"),
        )
    )
    assert module.prospective_window(pre)["complete_days"] == 0

    daily = pd.date_range("2026-08-01T00:00:00Z", periods=101, freq="D")
    context = SimpleNamespace(
        book=SimpleNamespace(
            ts=daily,
            count=len(daily),
            terminal_ts=daily[-1] + pd.Timedelta(days=1),
        )
    )
    result = module.prospective_window(context)
    assert daily[result["start_index"]] == module.PROSPECTIVE_START
    assert result["engine_start_index"] == result["start_index"] + 1
    assert result["complete_days"] == len(daily) - result["start_index"]


def test_terminal_flatten_and_terminal_open_events_do_not_fill_sample_gate() -> None:
    module = load()
    terminal = pd.Timestamp("2026-12-01T00:00:00Z")
    candidate = sufficient_trades(module.PROSPECTIVE_START)
    candidate.append(trade("short", terminal.isoformat(), reason="terminal_flatten"))
    control = sufficient_trades(module.PROSPECTIVE_START)
    events = [
        {"event": "handoff_opportunity", "ts": "2026-10-01T00:00:00Z"},
        {"event": "handoff_opportunity", "ts": terminal.isoformat()},
        {"event": "handoff_accept", "ts": "2026-10-02T00:00:00Z"},
    ]
    counts = module.sample_counts(
        candidate_trades=candidate,
        control_trades=control,
        handoff_events=events,
        terminal_ts=terminal,
    )
    assert counts["candidate_closed_trades"] == 5
    assert counts["handoff_opportunities"] == 1
    assert module.sample_gate(counts)["status"] == "INSUFFICIENT"


def test_sample_gate_requires_each_strategy_and_each_side() -> None:
    module = load()
    counts = {
        "candidate_closed_trades": 5,
        "control_closed_trades": 5,
        "candidate_long_trades": 3,
        "candidate_short_trades": 2,
        "control_long_trades": 3,
        "control_short_trades": 2,
        "handoff_opportunities": 2,
        "handoff_accepts": 1,
    }
    assert module.sample_gate(counts)["status"] == "PASS"
    counts["control_short_trades"] = 1
    assert module.sample_gate(counts)["status"] == "INSUFFICIENT"


def test_earliest_terminal_is_deterministic_and_not_the_run_date() -> None:
    module = load()
    start = module.PROSPECTIVE_START
    daily = pd.date_range(start, periods=100, freq="D")
    candidate = sufficient_trades(start)
    control = sufficient_trades(start)
    events = [
        {"event": "handoff_opportunity", "ts": (start + pd.Timedelta(days=60)).isoformat()},
        {"event": "handoff_accept", "ts": (start + pd.Timedelta(days=61)).isoformat()},
        {"event": "handoff_opportunity", "ts": (start + pd.Timedelta(days=70)).isoformat()},
    ]
    result = module.earliest_sample_eligible_terminal(
        daily_ts=daily,
        book_terminal_ts=daily[-1] + pd.Timedelta(days=1),
        start_index=0,
        candidate_trades=candidate,
        control_trades=control,
        handoff_events=events,
    )
    assert result is not None
    assert result["complete_days"] == 90
    assert result["terminal_ts"] == (start + pd.Timedelta(days=90)).isoformat()


def test_event_exactly_at_day_90_moves_earliest_terminal_to_day_91() -> None:
    module = load()
    start = module.PROSPECTIVE_START
    daily = pd.date_range(start, periods=100, freq="D")
    candidate = sufficient_trades(start)
    control = sufficient_trades(start)
    events = [
        {"event": "handoff_opportunity", "ts": (start + pd.Timedelta(days=60)).isoformat()},
        {"event": "handoff_accept", "ts": (start + pd.Timedelta(days=61)).isoformat()},
        {"event": "handoff_opportunity", "ts": (start + pd.Timedelta(days=90)).isoformat()},
    ]
    result = module.earliest_sample_eligible_terminal(
        daily_ts=daily,
        book_terminal_ts=daily[-1] + pd.Timedelta(days=1),
        start_index=0,
        candidate_trades=candidate,
        control_trades=control,
        handoff_events=events,
    )
    assert result is not None
    assert result["complete_days"] == 91


class FakeResearch:
    @staticmethod
    def comparison(candidate: dict, control: dict) -> dict:
        cm = candidate["metrics"]
        vm = control["metrics"]
        return_delta = cm["net_return_pct"] - vm["net_return_pct"]
        mdd_delta = cm["chronological_1h_mdd_pct"] - vm["chronological_1h_mdd_pct"]
        return {
            "return_delta_pp": return_delta,
            "mdd_delta_pp": mdd_delta,
            "return_higher": return_delta > 0,
            "mdd_smaller": mdd_delta > 0,
            "material": return_delta >= 5 or mdd_delta >= 2,
            "double_worse": return_delta < 0 and mdd_delta < 0,
        }


def run_payload(
    return_pct: float,
    mdd_pct: float,
    path_hash: str,
    *,
    opportunities: int = 2,
    accepts: int = 1,
) -> dict:
    return {
        "metrics": {
            "net_return_pct": return_pct,
            "chronological_1h_mdd_pct": mdd_pct,
            "bankrupt_intraday": False,
        },
        "replay_parity": {"turnover": True, "equity": True},
        "trades_sha256": path_hash,
        "activation_counts": {
            "handoff_opportunity": opportunities,
            "handoff_accept": accepts,
        },
    }


def test_performance_gate_requires_strict_dual_improvement_and_materiality() -> None:
    module = load()
    candidate = run_payload(12.0, -8.0, "candidate")
    control = run_payload(7.0, -10.0, "control", opportunities=0, accepts=0)
    result = module.performance_gate(
        research=FakeResearch,
        candidate=candidate,
        control=control,
        stress_candidate=run_payload(9.0, -9.0, "stress-candidate"),
        stress_control=run_payload(7.0, -10.0, "stress-control"),
        funding_off_candidate=run_payload(13.0, -8.0, "funding-candidate"),
        funding_off_control=run_payload(8.0, -10.0, "funding-control"),
        handoff_off=run_payload(8.0, -10.0, "handoff-off", opportunities=0, accepts=0),
    )
    assert result["status"] == "PASS"

    equality = run_payload(7.0, -8.0, "candidate")
    failed = module.performance_gate(
        research=FakeResearch,
        candidate=equality,
        control=control,
        stress_candidate=run_payload(9.0, -9.0, "stress-candidate"),
        stress_control=run_payload(7.0, -10.0, "stress-control"),
        funding_off_candidate=run_payload(13.0, -8.0, "funding-candidate"),
        funding_off_control=run_payload(8.0, -10.0, "funding-control"),
        handoff_off=run_payload(8.0, -10.0, "handoff-off", opportunities=0, accepts=0),
    )
    assert failed["status"] == "FAIL"
    assert not failed["checks"]["base_return_strictly_higher"]


def test_performance_gate_rejects_stress_double_worse_and_dormant_handoff() -> None:
    module = load()
    candidate = run_payload(12.0, -8.0, "same", opportunities=0, accepts=0)
    control = run_payload(7.0, -10.0, "control", opportunities=0, accepts=0)
    result = module.performance_gate(
        research=FakeResearch,
        candidate=candidate,
        control=control,
        stress_candidate=run_payload(5.0, -12.0, "stress-candidate"),
        stress_control=run_payload(7.0, -10.0, "stress-control"),
        funding_off_candidate=run_payload(13.0, -8.0, "funding-candidate"),
        funding_off_control=run_payload(8.0, -10.0, "funding-control"),
        handoff_off=run_payload(8.0, -10.0, "same", opportunities=0, accepts=0),
    )
    assert result["status"] == "FAIL"
    assert not result["checks"]["stress_8bps_not_double_worse"]
    assert not result["checks"]["handoff_opportunity_activated"]
    assert not result["checks"]["handoff_changes_economic_trade_path"]


def test_snapshot_path_is_keyed_by_last_complete_day() -> None:
    module = load()
    path = module._snapshot_path("2026-08-12T00:00:00+00:00")
    assert path.name.endswith("observation_through_2026-08-11.json")

