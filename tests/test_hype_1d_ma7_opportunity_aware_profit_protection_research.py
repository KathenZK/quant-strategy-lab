from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "research/hype/1d-ma7-asymmetric-body-trend/scripts/research_hype_1d_ma7_opportunity_aware_profit_protection.py"


def load_research():
    spec = importlib.util.spec_from_file_location("test_hype_oapp_research", PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def metrics(ret: float, mdd: float, trades: int, long: int, short: int) -> dict:
    return {
        "net_return_pct": ret,
        "chronological_1h_mdd_pct": mdd,
        "daily_extreme_mdd_pct": mdd - 1.0,
        "closed_trades": trades,
        "long_trades": long,
        "short_trades": short,
        "equity_multiple": 1.0 + ret / 100.0,
        "bankrupt_intraday": False,
    }


def run(ret: float, mdd: float, trades: int, long: int, short: int, path: str, long_exits: int = 0, rsi_exits: int = 0) -> dict:
    return {
        "status": "PASS",
        "metrics": metrics(ret, mdd, trades, long, short),
        "trades_sha256": path,
        "activation_counts": {"long_trail_exit": long_exits, "short_rsi_exit": rsi_exits},
    }


def test_opportunity_prepass_accepts_one_v_trade_when_evidence_is_sufficient() -> None:
    research = load_research()
    controls = {
        "D": run(100.0, -20.0, 10, 4, 6, "d0"),
        "V": run(10.0, -18.0, 3, 2, 1, "v0"),
    }
    row = {
        "D": run(130.0, -15.0, 11, 5, 6, "d1", long_exits=3, rsi_exits=3),
        "V": run(25.0, -10.0, 1, 1, 0, "v1", long_exits=1),
    }
    gate = research.opportunity_prepass(row, controls)
    assert gate["status"] == "PASS"
    assert gate["checks"]["V_candidate_opportunity_floor"]
    assert row["V"]["metrics"]["closed_trades"] == 1


def test_opportunity_prepass_rejects_unactivated_rsi_and_thin_combined_path() -> None:
    research = load_research()
    controls = {"D": run(100.0, -20.0, 10, 4, 6, "d0"), "V": run(10.0, -18.0, 3, 2, 1, "v0")}
    row = {"D": run(130.0, -15.0, 8, 4, 4, "d1", long_exits=2), "V": run(25.0, -10.0, 1, 1, 0, "v1", long_exits=1)}
    gate = research.opportunity_prepass(row, controls)
    assert gate["status"] == "FAIL"
    assert not gate["checks"]["DV_combined_trade_floor"]
    assert not gate["checks"]["rsi_exit_total"]


def trade(side: str, entry: str, exit_: str, pnl: float, reason: str, entry_reason: str = "natural") -> dict:
    return {"side": side, "entry_ts": entry, "exit_ts": exit_, "exit_price": 10.0, "exit_reason": reason, "entry_reason": entry_reason, "net_pnl": pnl}


def test_paired_episode_audit_drops_largest_increment_and_detects_suppression() -> None:
    research = load_research()
    candidate = {
        "D": {"trades": [trade("long", "1", "3", 5.0, "long_mfe"), trade("short", "4", "6", 3.0, "rsi")]},
        "V": {"trades": [trade("long", "7", "9", 4.0, "long_mfe")]},
    }
    control = {
        "D": {"trades": [trade("long", "1", "4", 2.0, "native"), trade("short", "4", "7", 1.0, "native")]},
        "V": {"trades": [trade("long", "7", "10", 2.0, "native"), trade("short", "11", "12", -3.0, "native", "forced_reversal")]},
    }
    audit = research.paired_episode_audit(candidate, control)
    assert audit["changed_episode_count"] == 4
    assert audit["positive_episode_count"] == 4
    assert audit["suppressed_forced_reversal_count"] == 1
    assert audit["incremental_after_dropping_largest_positive"] > 0.0


def test_paired_episode_audit_exposes_single_episode_concentration() -> None:
    research = load_research()
    candidate = {"D": {"trades": [trade("long", "1", "2", 10.0, "mfe")]}, "V": {"trades": []}}
    control = {"D": {"trades": [trade("long", "1", "3", 0.0, "native")]}, "V": {"trades": []}}
    audit = research.paired_episode_audit(candidate, control)
    assert audit["positive_episode_count"] == 1
    assert audit["incremental_after_dropping_largest_positive"] == 0.0


def test_frontier_obeys_mdd_caps() -> None:
    research = load_research()
    rows = [
        {"id": "A", "status": "PASS", "metrics": metrics(100.0, -19.0, 1, 1, 0)},
        {"id": "B", "status": "PASS", "metrics": metrics(250.0, -32.0, 1, 1, 0)},
        {"id": "C", "status": "PASS", "metrics": metrics(500.0, -55.0, 1, 1, 0)},
    ]
    frontier = research._frontier(rows)
    assert frontier["20"]["id"] == "A"
    assert frontier["35"]["id"] == "B"
    assert frontier["50"]["id"] == "B"


def test_self_test_and_forbidden_family_guard() -> None:
    research = load_research()
    assert research.self_test()["stage_a_count"] == 957
    engine = research.load_module(research.ENGINE_PATH, "test_oapp_family_engine")
    assert research.module_family(engine.WTLConfig("L", long_exit=engine.trail_specs()[0])) == "long_exit"
    try:
        research.module_family(engine.WTLConfig("E", entry=engine.EntryFilter("er", "both", 3, 0.0)))
    except ValueError:
        pass
    else:
        raise AssertionError("entry filter must not become an OAPP search family")


def test_holdout_is_last_window_and_locked_after_freeze_artifacts() -> None:
    research = load_research()
    assert research.H_EVAL == (356, 432)
    paths = research.downstream_paths()
    assert paths.index(research.HOLDOUT_LOCK_PATH) > paths.index(research.LEVERAGE_PATH)
    assert paths.index(research.HOLDOUT_PATH) > paths.index(research.HOLDOUT_LOCK_PATH)

