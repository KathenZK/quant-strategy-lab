"""Stage-locked exposed-history PEHC search and prospective shadow freeze."""

from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
from types import ModuleType
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CONTRACT_PATH = FAMILY_DIR / "specs/hype-1d-ma7-profit-exit-handoff-continuity-preregistration-2026-08-10.md"
ENGINE_PATH = SCRIPT_DIR / "hype_1d_ma7_profit_exit_handoff_continuity_engine.py"
OAPP_RESEARCH_PATH = SCRIPT_DIR / "research_hype_1d_ma7_opportunity_aware_profit_protection.py"
METRICS_PATH = SCRIPT_DIR / "hype_1d_ma7_trend_phase_risk_metrics.py"
ADAPTER_PATH = SCRIPT_DIR / "hype_1d_ma7_v4_fair_adapter.py"
RENDERER_PATH = SCRIPT_DIR / "render_hype_1d_ma7_profit_exit_handoff_continuity.py"
ORCHESTRATOR_PATH = Path(__file__).resolve()

ENGINE_TEST_PATH = ROOT / "tests/test_hype_1d_ma7_profit_exit_handoff_continuity_engine.py"
RESEARCH_TEST_PATH = ROOT / "tests/test_hype_1d_ma7_profit_exit_handoff_continuity_research.py"
RENDERER_TEST_PATH = ROOT / "tests/test_hype_1d_ma7_profit_exit_handoff_continuity_renderer.py"
UPSTREAM_TEST_PATHS = (
    ROOT / "tests/test_hype_1d_ma7_wide_trend_lifecycle_engine.py",
    ROOT / "tests/test_hype_1d_ma7_wide_trend_lifecycle_research.py",
    ROOT / "tests/test_hype_1d_ma7_wide_trend_lifecycle_trade_path.py",
    ROOT / "tests/test_hype_1d_ma7_v4_fair_adapter.py",
    ROOT / "tests/test_hype_1d_ma7_intent_harness.py",
    ROOT / "tests/test_hype_1d_ma7_intent_fair_metrics.py",
    ROOT / "tests/test_hype_1d_ma7_trend_phase_risk.py",
    ROOT / "tests/test_hype_1d_ma7_opportunity_aware_profit_protection_engine.py",
    ROOT / "tests/test_hype_1d_ma7_opportunity_aware_profit_protection_research.py",
)
TEST_PATHS = (
    *UPSTREAM_TEST_PATHS,
    ENGINE_TEST_PATH,
    RESEARCH_TEST_PATH,
    RENDERER_TEST_PATH,
)
EXPECTED_TEST_COUNT = 87

PREFIX = ARTIFACT_DIR / "hype_1d_ma7_profit_exit_handoff_continuity_2026-08-10"
MANIFEST_PATH = Path(f"{PREFIX}_manifest.json")
STAGE_A_PATH = Path(f"{PREFIX}_stage_a.json")
STAGE_B_PATH = Path(f"{PREFIX}_stage_b.json")
STAGE_C_PATH = Path(f"{PREFIX}_stage_c.json")
SHADOW_PATH = Path(f"{PREFIX}_shadow_candidate.json")
PROSPECTIVE_PATH = Path(f"{PREFIX}_prospective_protocol.json")
HTML_PATH = Path(f"{PREFIX}_full_trade_path.html")
WTL_MANIFEST_PATH = ARTIFACT_DIR / "hype_1d_ma7_wide_trend_lifecycle_2026-08-10_manifest.json"

FULL = (0, 432)
PRE_OLD_H = (0, 356)
BLOCKS = tuple((start, start + 54) for start in range(0, 432, 54))
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
PROSPECTIVE_START = "2026-08-11T00:00:00+00:00"


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_OAPP_RESEARCH = load_module(OAPP_RESEARCH_PATH, "hype_pehc_upstream_oapp_research")
sha256 = _OAPP_RESEARCH.sha256
write_locked = _OAPP_RESEARCH.write_locked
read_locked = _OAPP_RESEARCH.read_locked
sidecar = _OAPP_RESEARCH.sidecar
engine_start = _OAPP_RESEARCH._BASE_RESEARCH.engine_start
economic_trades = _OAPP_RESEARCH._BASE_RESEARCH.economic_trades
economic_path = _OAPP_RESEARCH._BASE_RESEARCH.economic_path


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def implementation_paths() -> dict[str, Path]:
    paths = {
        "contract": CONTRACT_PATH,
        "engine": ENGINE_PATH,
        "orchestrator": ORCHESTRATOR_PATH,
        "renderer": RENDERER_PATH,
        "engine_test": ENGINE_TEST_PATH,
        "research_test": RESEARCH_TEST_PATH,
        "renderer_test": RENDERER_TEST_PATH,
        "oapp_research": OAPP_RESEARCH_PATH,
        "metrics": METRICS_PATH,
        "adapter": ADAPTER_PATH,
    }
    paths.update({f"upstream_test_{index}": path for index, path in enumerate(UPSTREAM_TEST_PATHS, 1)})
    return paths


def current_pins() -> dict[str, dict[str, str]]:
    return {
        label: {"path": str(path), "sha256": sha256(path)}
        for label, path in implementation_paths().items()
    }


def assert_pins(pins: dict[str, dict[str, str]]) -> None:
    if current_pins() != pins:
        raise RuntimeError("PEHC implementation pin drift")


def load_runtime() -> tuple[ModuleType, ModuleType, ModuleType, Any]:
    engine = load_module(ENGINE_PATH, "hype_pehc_engine_runtime")
    risk = load_module(METRICS_PATH, "hype_pehc_risk_runtime")
    adapter = load_module(ADAPTER_PATH, "hype_pehc_adapter_runtime")
    return engine, risk, adapter, adapter.load_context()


def run_preflight() -> dict[str, Any]:
    if EXPECTED_TEST_COUNT <= 0:
        raise RuntimeError("EXPECTED_TEST_COUNT must be frozen before manifest")
    command = [str(ROOT / ".venv/bin/pytest"), "-q", *map(str, TEST_PATHS)]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    output = f"{completed.stdout}\n{completed.stderr}".strip()
    import re

    match = re.search(r"(\d+) passed", output)
    passed = int(match.group(1)) if match else -1
    status = "PASS" if completed.returncode == 0 and passed == EXPECTED_TEST_COUNT else "FAIL"
    record = {
        "status": status,
        "passed": passed,
        "expected": EXPECTED_TEST_COUNT,
        "returncode": completed.returncode,
        "tests": {str(path): sha256(path) for path in TEST_PATHS},
        "output_tail": output[-4000:],
    }
    if status != "PASS":
        raise RuntimeError(f"PEHC preflight expected {EXPECTED_TEST_COUNT}, got {passed}")
    return record


def _metrics(raw: Any, replay: Any) -> dict[str, Any]:
    return {
        "equity_multiple": float(replay.terminal_equity),
        "net_return_pct": (float(replay.terminal_equity) - 1.0) * 100.0,
        "chronological_1h_mdd_pct": float(replay.chronological_1h_mdd_pct),
        "daily_extreme_mdd_pct": float(raw.metrics["max_drawdown_pct"]),
        "closed_trades": int(raw.metrics["closed_trades"]),
        "long_trades": sum(str(row["side"]) == "long" for row in raw.trades),
        "short_trades": sum(str(row["side"]) == "short" for row in raw.trades),
        "turnover_multiple": float(replay.turnover_multiple),
        "cost_equity_units": float(replay.cost_equity_units),
        "funding_equity_units": float(replay.funding_equity_units),
        "max_marked_leverage": float(replay.max_marked_leverage),
        "bankrupt_intraday": bool(raw.metrics["bankrupt_intraday"]),
        "worst_ts": replay.worst_ts,
        "worst_trade_index": replay.worst_trade_index,
    }


def _result_payload(
    *,
    arm_id: str,
    window: tuple[int, int],
    raw: Any,
    replay: Any,
    source_sha256: str,
    activation_counts: dict[str, int],
    handoff_events: list[dict[str, Any]],
    slippage: float,
    include_funding: bool,
    retain: bool,
) -> dict[str, Any]:
    if not all(bool(value) for value in replay.parity.values()):
        raise RuntimeError(f"ledger replay parity failed: {arm_id}")
    if bool(raw.metrics["bankrupt_intraday"]):
        raise RuntimeError(f"bankruptcy: {arm_id}")
    payload = {
        "status": "PASS",
        "arm_id": arm_id,
        "requested_window": list(window),
        "engine_window": [engine_start(window), window[1]],
        "slippage": slippage,
        "include_funding": include_funding,
        "metrics": _metrics(raw, replay),
        "replay_parity": replay.parity,
        "source_sha256": source_sha256,
        "activation_counts": dict(activation_counts),
        "handoff_events": list(handoff_events),
        "trades_sha256": canonical_hash(economic_trades(raw.trades)),
        "path_sha256": canonical_hash(economic_path(raw.path)) if retain else None,
    }
    if retain:
        payload["trades"] = list(raw.trades)
        payload["path"] = list(raw.path)
        payload["replay"] = replay.canonical()
    return payload


def run_candidate(
    *,
    engine: ModuleType,
    risk: ModuleType,
    context: Any,
    config: Any,
    window: tuple[int, int],
    slippage: float = BASE_SLIPPAGE,
    include_funding: bool = True,
    retain: bool = False,
    short_rsi_enabled: bool = True,
) -> dict[str, Any]:
    result = engine.run_variant(
        context,
        config,
        start_index=engine_start(window),
        terminal_index=window[1],
        slippage=slippage,
        include_funding=include_funding,
        retain=retain,
        short_rsi_enabled=short_rsi_enabled,
    )
    replay = risk.replay_chronological_1h(
        context,
        result.raw,
        slippage=slippage,
        include_funding=include_funding,
        retain_points=retain,
    )
    return _result_payload(
        arm_id=config.arm_id,
        window=window,
        raw=result.raw,
        replay=replay,
        source_sha256=result.source_sha256,
        activation_counts=result.activation_counts,
        handoff_events=result.handoff_events,
        slippage=slippage,
        include_funding=include_funding,
        retain=retain,
    )


def run_exact(
    *,
    risk: ModuleType,
    context: Any,
    window: tuple[int, int],
    slippage: float = BASE_SLIPPAGE,
    include_funding: bool = True,
    retain: bool = False,
) -> dict[str, Any]:
    start = engine_start(window)
    raw = context.backtest(
        context.book,
        context.features,
        long_config=context.long_config,
        short_config=context.short_config,
        start_index=start,
        terminal_index=window[1],
        slippage=slippage,
        signal_lag=0,
        include_funding=include_funding,
        retain=retain,
    )
    replay = risk.replay_chronological_1h(
        context,
        raw,
        slippage=slippage,
        include_funding=include_funding,
        retain_points=retain,
    )
    return _result_payload(
        arm_id="C000_EXACT_V4",
        window=window,
        raw=raw,
        replay=replay,
        source_sha256="exact-v4-pinned-source",
        activation_counts={},
        handoff_events=[],
        slippage=slippage,
        include_funding=include_funding,
        retain=retain,
    )


def safe(call: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        return call()
    except Exception as exc:  # noqa: BLE001 - every trial must persist its error
        return {"status": "ERROR", "error_type": type(exc).__name__, "error": str(exc)}


def comparison(candidate: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    if candidate.get("status") != "PASS" or control.get("status") != "PASS":
        return {"status": "ERROR"}
    cm = candidate["metrics"]
    vm = control["metrics"]
    return_delta = float(cm["net_return_pct"]) - float(vm["net_return_pct"])
    mdd_delta = float(cm["chronological_1h_mdd_pct"]) - float(vm["chronological_1h_mdd_pct"])
    return {
        "status": "PASS",
        "return_delta_pp": return_delta,
        "mdd_delta_pp": mdd_delta,
        "return_higher": return_delta > 0.0,
        "mdd_smaller": mdd_delta > 0.0,
        "material": return_delta >= 5.0 or mdd_delta >= 2.0,
        "dual_improvement": return_delta > 0.0 and mdd_delta > 0.0,
        "double_worse": return_delta < 0.0 and mdd_delta < 0.0,
    }


def aggregate_blocks(candidate_blocks: list[dict[str, Any]], control_blocks: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [comparison(candidate, control) for candidate, control in zip(candidate_blocks, control_blocks, strict=True)]
    if any(row["status"] != "PASS" for row in rows):
        return {"status": "ERROR", "comparisons": rows}
    return {
        "status": "PASS",
        "dual_improvement_blocks": sum(row["dual_improvement"] for row in rows),
        "non_double_worse_blocks": sum(not row["double_worse"] for row in rows),
        "worst_return_delta_pp": min(row["return_delta_pp"] for row in rows),
        "worst_mdd_delta_pp": min(row["mdd_delta_pp"] for row in rows),
        "compound_candidate_return_pct": (
            math.prod(row["metrics"]["equity_multiple"] for row in candidate_blocks) - 1.0
        )
        * 100.0,
        "compound_control_return_pct": (
            math.prod(row["metrics"]["equity_multiple"] for row in control_blocks) - 1.0
        )
        * 100.0,
        "comparisons": rows,
    }


def economic_path_key(full: dict[str, Any], blocks: list[dict[str, Any]]) -> str:
    return canonical_hash(
        {
            "full": full.get("trades_sha256"),
            "blocks": [row.get("trades_sha256") for row in blocks],
        }
    )


def stage_a_rank(row: dict[str, Any]) -> tuple[Any, ...]:
    if row.get("status") != "PASS":
        return (1, math.inf, math.inf, math.inf, math.inf, row["arm_id"])
    full = row["full_comparison"]
    blocked = row["blocked_aggregate"]
    config = row["config"]
    complexity = (
        int(config["slope_threshold"] is not None)
        + int(config["chase_cap_atr"] != "INF")
        + int(config["execution"] != "same_1h_open")
    )
    return (
        0,
        -min(full["return_delta_pp"], blocked["worst_return_delta_pp"]),
        -min(full["mdd_delta_pp"], blocked["worst_mdd_delta_pp"]),
        -blocked["dual_improvement_blocks"],
        -int(row["full"]["activation_counts"].get("handoff_accept", 0)),
        complexity,
        row["arm_id"],
    )


def neighbor_configs(engine: ModuleType, config: Any) -> list[Any]:
    rows: list[Any] = []
    fields = (
        ("expiry_days", engine.EXPIRY_DAYS),
        ("slope_threshold", engine.SLOPE_THRESHOLDS),
        ("chase_cap_atr", engine.CHASE_CAPS),
        ("execution", engine.EXECUTIONS),
    )
    for field, grid in fields:
        index = grid.index(getattr(config, field))
        for neighbor_index in (index - 1, index + 1):
            if 0 <= neighbor_index < len(grid):
                value = grid[neighbor_index]
                rows.append(
                    replace(
                        config,
                        arm_id=f"{config.arm_id}_N_{field}_{neighbor_index}",
                        **{field: value},
                    )
                )
    unique = {engine.config_sha256(replace(row, arm_id="neighbor")): row for row in rows}
    return sorted(unique.values(), key=lambda row: row.arm_id)


def accepted_origins(run: dict[str, Any]) -> list[int]:
    return sorted(
        {
            int(row["origin_index"])
            for row in run.get("handoff_events", [])
            if row.get("event") == "handoff_accept"
        }
    )


def max_winner_origin(run: dict[str, Any]) -> int | None:
    accepted = {
        str(row["ts"]): int(row["origin_index"])
        for row in run.get("handoff_events", [])
        if row.get("event") == "handoff_accept"
    }
    matches = [
        (float(trade["net_pnl"]), accepted[str(trade["entry_ts"])])
        for trade in run.get("trades", [])
        if str(trade.get("entry_ts")) in accepted and str(trade.get("side")) == "short"
    ]
    return max(matches)[1] if matches else None


def stage_manifest() -> dict[str, Any]:
    downstream = (STAGE_A_PATH, STAGE_B_PATH, STAGE_C_PATH, SHADOW_PATH, PROSPECTIVE_PATH, HTML_PATH)
    if MANIFEST_PATH.exists() or sidecar(MANIFEST_PATH).exists() or any(path.exists() or sidecar(path).exists() for path in downstream):
        raise RuntimeError("PEHC artifact already exists")
    preflight = run_preflight()
    engine, risk, _, context = load_runtime()
    grid = engine.grid_configs()
    if len(grid) != 490 or len(BLOCKS) != 8:
        raise RuntimeError("frozen PEHC search dimensions drift")
    v4_full = run_exact(risk=risk, context=context, window=FULL)
    upstream, upstream_sha = read_locked(WTL_MANIFEST_PATH)
    pins = current_pins()
    payload = {
        "schema": "hype-pehc-manifest-v1",
        "status": "PASS",
        "research_state": "all [0,432) researcher-exposed; shadow-only discovery",
        "prospective_start": PROSPECTIVE_START,
        "preflight": preflight,
        "pins": pins,
        "upstream_wtl_manifest_sha256": upstream_sha,
        "market_audit": upstream["market_audit"],
        "book_quality": upstream["book_quality"],
        "exact_v4_full_anchor": v4_full,
        "windows": {"full_exposed": FULL, "pre_old_h": PRE_OLD_H, "blocked": BLOCKS},
        "grid_count": len(grid),
        "grid": [row.canonical() for row in grid],
        "grid_hashes": {row.arm_id: engine.config_sha256(row) for row in grid},
        "stage_b_max": 32,
        "stage_c_max": 16,
        "leverage_locked": True,
    }
    assert_pins(pins)
    write_locked(MANIFEST_PATH, payload)
    return payload


def assert_manifest() -> dict[str, Any]:
    manifest, _ = read_locked(MANIFEST_PATH)
    if manifest.get("status") != "PASS" or manifest.get("grid_count") != 490:
        raise RuntimeError("invalid PEHC manifest")
    assert_pins(manifest["pins"])
    return manifest


def stage_a() -> dict[str, Any]:
    manifest = assert_manifest()
    if STAGE_A_PATH.exists() or sidecar(STAGE_A_PATH).exists():
        raise RuntimeError("PEHC Stage A already exists")
    engine, risk, _, context = load_runtime()
    control_full = run_exact(risk=risk, context=context, window=FULL)
    control_blocks = [run_exact(risk=risk, context=context, window=window) for window in BLOCKS]
    rows: list[dict[str, Any]] = []
    for config in engine.grid_configs():
        full = safe(lambda config=config: run_candidate(engine=engine, risk=risk, context=context, config=config, window=FULL))
        blocks = [
            safe(lambda config=config, window=window: run_candidate(engine=engine, risk=risk, context=context, config=config, window=window))
            for window in BLOCKS
        ]
        if full.get("status") == "PASS" and all(row.get("status") == "PASS" for row in blocks):
            full_compare = comparison(full, control_full)
            blocked = aggregate_blocks(blocks, control_blocks)
            status = "PASS"
            path_key = economic_path_key(full, blocks)
        else:
            full_compare = {"status": "ERROR"}
            blocked = {"status": "ERROR"}
            status = "ERROR"
            path_key = None
        row = {
            "status": status,
            "arm_id": config.arm_id,
            "config": config.canonical(),
            "config_sha256": engine.config_sha256(config),
            "full": full,
            "blocks": blocks,
            "full_comparison": full_compare,
            "blocked_aggregate": blocked,
            "economic_path_key": path_key,
        }
        rows.append(row)
    ranked = sorted(rows, key=stage_a_rank)
    unique: list[str] = []
    seen: set[str] = set()
    for row in ranked:
        key = row.get("economic_path_key")
        if row["status"] == "PASS" and key not in seen:
            unique.append(row["arm_id"])
            seen.add(key)
    shortlist = unique[:32]
    payload = {
        "schema": "hype-pehc-stage-a-v1",
        "status": "PASS" if rows and all(row["status"] == "PASS" for row in rows) else "FAIL",
        "manifest_sha256": sha256(MANIFEST_PATH),
        "controls": {"full": control_full, "blocks": control_blocks},
        "trial_count": len(rows),
        "unique_economic_paths": len(unique),
        "shortlist": shortlist,
        "rows": rows,
    }
    assert_pins(manifest["pins"])
    write_locked(STAGE_A_PATH, payload)
    return payload


def _config_by_id(engine: ModuleType) -> dict[str, Any]:
    return {row.arm_id: row for row in engine.grid_configs()}


def stage_b() -> dict[str, Any]:
    manifest = assert_manifest()
    stage_a_payload, stage_a_sha = read_locked(STAGE_A_PATH)
    if stage_a_payload.get("status") != "PASS" or len(stage_a_payload.get("shortlist", [])) > 32:
        raise RuntimeError("invalid PEHC Stage A")
    engine, risk, _, context = load_runtime()
    phase_market = context.original_harness.load_market(12)
    phase_context = replace(context, market=phase_market)
    phase_window = (0, phase_context.book.count)
    controls = {
        "stress": run_exact(risk=risk, context=context, window=FULL, slippage=STRESS_SLIPPAGE),
        "funding_off": run_exact(risk=risk, context=context, window=FULL, include_funding=False),
        "phase_12h": run_exact(risk=risk, context=phase_context, window=phase_window),
    }
    configs = _config_by_id(engine)
    rows: list[dict[str, Any]] = []
    for arm_id in stage_a_payload["shortlist"]:
        config = configs[arm_id]
        base = run_candidate(engine=engine, risk=risk, context=context, config=config, window=FULL, retain=True)
        stress = safe(lambda: run_candidate(engine=engine, risk=risk, context=context, config=config, window=FULL, slippage=STRESS_SLIPPAGE))
        funding_off = safe(lambda: run_candidate(engine=engine, risk=risk, context=context, config=config, window=FULL, include_funding=False))
        phase = safe(lambda: run_candidate(engine=engine, risk=risk, context=phase_context, config=config, window=phase_window))
        stress_compare = comparison(stress, controls["stress"])
        phase_compare = comparison(phase, controls["phase_12h"])
        status = "PASS" if all(row.get("status") == "PASS" for row in (base, stress, funding_off, phase)) else "ERROR"
        rows.append(
            {
                "status": status,
                "arm_id": arm_id,
                "config": config.canonical(),
                "base": base,
                "stress": stress,
                "funding_off": funding_off,
                "phase_12h": phase,
                "stress_comparison": stress_compare,
                "phase_comparison": phase_compare,
            }
        )
    stage_a_rows = {row["arm_id"]: row for row in stage_a_payload["rows"]}
    ranked = sorted(
        rows,
        key=lambda row: (
            row["status"] != "PASS",
            row.get("stress_comparison", {}).get("double_worse", True),
            row.get("phase_comparison", {}).get("double_worse", True),
            stage_a_rank(stage_a_rows[row["arm_id"]]),
        ),
    )
    shortlist = [row["arm_id"] for row in ranked if row["status"] == "PASS"][:16]
    payload = {
        "schema": "hype-pehc-stage-b-v1",
        "status": "PASS" if rows and all(row["status"] == "PASS" for row in rows) else "FAIL",
        "manifest_sha256": sha256(MANIFEST_PATH),
        "stage_a_sha256": stage_a_sha,
        "phase_market_audit": phase_market.audit,
        "controls": controls,
        "trial_count": len(rows),
        "shortlist": shortlist,
        "rows": rows,
    }
    assert_pins(manifest["pins"])
    write_locked(STAGE_B_PATH, payload)
    return payload


def stage_c() -> dict[str, Any]:
    manifest = assert_manifest()
    stage_b_payload, stage_b_sha = read_locked(STAGE_B_PATH)
    if stage_b_payload.get("status") != "PASS" or len(stage_b_payload.get("shortlist", [])) > 16:
        raise RuntimeError("invalid PEHC Stage B")
    engine, risk, _, context = load_runtime()
    configs = _config_by_id(engine)
    controls = {
        "v4_full": run_exact(risk=risk, context=context, window=FULL, retain=True),
        "v4_pre_old_h": run_exact(risk=risk, context=context, window=PRE_OLD_H),
    }
    oapp_off = engine.PEHCConfig("CONTROL_OAPP_HANDOFF_OFF", enabled=False)
    controls["oapp_full"] = run_candidate(engine=engine, risk=risk, context=context, config=oapp_off, window=FULL, retain=True)
    controls["oapp_pre_old_h"] = run_candidate(engine=engine, risk=risk, context=context, config=oapp_off, window=PRE_OLD_H)
    rows: list[dict[str, Any]] = []
    for arm_id in stage_b_payload["shortlist"]:
        config = configs[arm_id]
        full = run_candidate(engine=engine, risk=risk, context=context, config=config, window=FULL, retain=True)
        pre = run_candidate(engine=engine, risk=risk, context=context, config=config, window=PRE_OLD_H)
        handoff_off = controls["oapp_full"]
        shadow_only_config = replace(config, arm_id=f"{arm_id}_SHADOW_ONLY", entry_enabled=False)
        shadow_only = run_candidate(engine=engine, risk=risk, context=context, config=shadow_only_config, window=FULL)
        no_rsi = run_candidate(engine=engine, risk=risk, context=context, config=replace(config, arm_id=f"{arm_id}_NO_RSI"), window=FULL, short_rsi_enabled=False)
        origins = accepted_origins(full)
        keep_one = [
            run_candidate(
                engine=engine,
                risk=risk,
                context=context,
                config=replace(config, arm_id=f"{arm_id}_KEEP_{origin}", allowed_origin_indices=(origin,)),
                window=FULL,
            )
            for origin in origins
        ]
        winner_origin = max_winner_origin(full)
        max_winner_removed = (
            run_candidate(
                engine=engine,
                risk=risk,
                context=context,
                config=replace(config, arm_id=f"{arm_id}_DROP_MAX", blocked_origin_indices=(winner_origin,)),
                window=FULL,
            )
            if winner_origin is not None
            else {"status": "NOT_APPLICABLE"}
        )
        neighbors = [
            {
                "config": neighbor.canonical(),
                "full": run_candidate(engine=engine, risk=risk, context=context, config=neighbor, window=FULL),
                "pre_old_h": run_candidate(engine=engine, risk=risk, context=context, config=neighbor, window=PRE_OLD_H),
            }
            for neighbor in neighbor_configs(engine, config)
        ]
        full_compare = comparison(full, controls["v4_full"])
        pre_compare = comparison(pre, controls["v4_pre_old_h"])
        max_removed_vs_oapp = (
            comparison(max_winner_removed, controls["oapp_full"])
            if max_winner_removed.get("status") == "PASS"
            else {"status": "NOT_APPLICABLE"}
        )
        neighbor_passes = sum(
            comparison(row["full"], controls["v4_full"])["dual_improvement"]
            and comparison(row["pre_old_h"], controls["v4_pre_old_h"])["dual_improvement"]
            for row in neighbors
        )
        blocks_covered = len({origin // 54 for origin in origins})
        stage_b_row = next(row for row in stage_b_payload["rows"] if row["arm_id"] == arm_id)
        qualification = {
            "full_dual": full_compare["dual_improvement"],
            "pre_old_h_dual": pre_compare["dual_improvement"],
            "material": full_compare["material"],
            "opportunities_ge_3": full["activation_counts"].get("handoff_opportunity", 0) >= 3,
            "accepts_ge_2": len(origins) >= 2,
            "accepts_cross_2_blocks": blocks_covered >= 2,
            "handoff_changes_path": full["trades_sha256"] != handoff_off["trades_sha256"],
            "max_winner_removed_increment_positive": max_removed_vs_oapp.get("return_delta_pp", -math.inf) > 0.0,
            "neighbor_pass": neighbor_passes > 0,
            "stress_not_double_worse": not stage_b_row["stress_comparison"].get("double_worse", True),
            "funding_off_solvent": stage_b_row["funding_off"].get("status") == "PASS",
        }
        qualification["status"] = "PASS" if all(qualification.values()) else "FAIL"
        rows.append(
            {
                "status": "PASS",
                "arm_id": arm_id,
                "config": config.canonical(),
                "full": full,
                "pre_old_h": pre,
                "full_comparison": full_compare,
                "pre_old_h_comparison": pre_compare,
                "handoff_off": handoff_off,
                "shadow_only": shadow_only,
                "no_rsi": no_rsi,
                "accepted_origins": origins,
                "accepted_blocks": blocks_covered,
                "keep_one": keep_one,
                "max_winner_origin": winner_origin,
                "max_winner_removed": max_winner_removed,
                "max_winner_removed_vs_oapp": max_removed_vs_oapp,
                "neighbors": neighbors,
                "neighbor_passes": neighbor_passes,
                "qualification": qualification,
            }
        )
    eligible = [row for row in rows if row["qualification"]["status"] == "PASS"]
    shadow_candidate = eligible[0]["arm_id"] if eligible else None
    payload = {
        "schema": "hype-pehc-stage-c-v1",
        "status": "PASS",
        "manifest_sha256": sha256(MANIFEST_PATH),
        "stage_b_sha256": stage_b_sha,
        "controls": controls,
        "trial_count": len(rows),
        "eligible_count": len(eligible),
        "shadow_candidate": shadow_candidate,
        "rows": rows,
        "external_transfer": {
            "BTCUSDT": {"status": "NOT_APPLICABLE", "reason": "no pinned exact-V4 identity and same-family event source"},
            "ETHUSDT": {"status": "NOT_APPLICABLE", "reason": "no pinned exact-V4 identity and same-family event source"},
        },
    }
    assert_pins(manifest["pins"])
    write_locked(STAGE_C_PATH, payload)
    return payload


def stage_freeze() -> dict[str, Any]:
    manifest = assert_manifest()
    stage_c_payload, stage_c_sha = read_locked(STAGE_C_PATH)
    if SHADOW_PATH.exists() or sidecar(SHADOW_PATH).exists() or HTML_PATH.exists() or sidecar(HTML_PATH).exists():
        raise RuntimeError("PEHC shadow/HTML artifact already exists")
    arm_id = stage_c_payload.get("shadow_candidate")
    if not arm_id:
        payload = {
            "schema": "hype-pehc-shadow-freeze-v1",
            "status": "NO_SHADOW_CANDIDATE",
            "stage_c_sha256": stage_c_sha,
            "registered": False,
            "promoted": False,
            "live_ready": False,
            "leverage_locked": True,
        }
        write_locked(SHADOW_PATH, payload)
        return payload
    engine, risk, _, context = load_runtime()
    config = _config_by_id(engine)[arm_id]
    candidate = run_candidate(engine=engine, risk=risk, context=context, config=config, window=FULL, retain=True)
    control = run_exact(risk=risk, context=context, window=FULL, retain=True)
    renderer = load_module(RENDERER_PATH, "hype_pehc_renderer_runtime")
    html_document, html_audit = renderer.build_document(
        title="HYPE 1D MA7 PEHC Shadow Candidate vs exact V4 — exposed history",
        candles=renderer.candles_from_context(context),
        candidate=candidate,
        control=control,
    )
    recent: dict[str, Any] = {}
    for label, days in (("1d", 1), ("7d", 7), ("1m", 30), ("3m", 90), ("6m", 180), ("1y", 365)):
        window = (max(0, FULL[1] - days), FULL[1])
        recent[label] = {
            "window": window,
            "candidate": safe(lambda window=window: run_candidate(engine=engine, risk=risk, context=context, config=config, window=window)),
            "control": safe(lambda window=window: run_exact(risk=risk, context=context, window=window)),
            "selection_use": False,
        }
    payload = {
        "schema": "hype-pehc-shadow-freeze-v1",
        "status": "SHADOW_FROZEN",
        "stage_c_sha256": stage_c_sha,
        "config": config.canonical(),
        "config_sha256": engine.config_sha256(config),
        "implementation_pins": manifest["pins"],
        "candidate": candidate,
        "exact_v4": control,
        "recent_slices_audit_only": recent,
        "research_state": "registered=false / shadow-only / not promoted / not live-ready",
        "registered": False,
        "promoted": False,
        "live_ready": False,
        "leverage_locked": True,
        "prospective_start": PROSPECTIVE_START,
        "html_audit": html_audit,
    }
    assert_pins(manifest["pins"])
    payload["html"] = renderer.write_locked(HTML_PATH, html_document)
    write_locked(SHADOW_PATH, payload)
    return payload


def stage_prospective() -> dict[str, Any]:
    manifest = assert_manifest()
    shadow, shadow_sha = read_locked(SHADOW_PATH)
    status = "WAITING_FOR_SHADOW_CANDIDATE" if shadow.get("status") != "SHADOW_FROZEN" else "INSUFFICIENT_FUTURE_DATA"
    payload = {
        "schema": "hype-pehc-prospective-protocol-v1",
        "status": status,
        "shadow_sha256": shadow_sha,
        "prospective_start": PROSPECTIVE_START,
        "minimum_complete_utc_days": 90,
        "sample_gates": {
            "candidate_closed_trades": 5,
            "control_closed_trades": 5,
            "long_trades_each": 2,
            "short_trades_each": 2,
            "handoff_opportunities": 2,
            "handoff_accepts": 1,
        },
        "performance_gates": {
            "net_return_strictly_higher": True,
            "chronological_1h_mdd_strictly_smaller": True,
            "return_delta_pp_or_mdd_delta_pp": [5.0, 2.0],
            "stress_8bps_not_double_worse": True,
            "funding_off_solvent": True,
            "ledger_and_path_parity": True,
        },
        "old_history_reuse_for_selection": False,
        "leverage_locked_until_1x_pass": True,
        "as_of_frozen_terminal": manifest["market_audit"].get("daily_end"),
    }
    write_locked(PROSPECTIVE_PATH, payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("self-test", "manifest", "stage-a", "stage-b", "stage-c", "freeze", "prospective", "all"), required=True)
    args = parser.parse_args()
    if args.stage == "self-test":
        engine, _, _, _ = load_runtime()
        assert len(engine.grid_configs()) == 490
        assert len(BLOCKS) == 8 and BLOCKS[-1] == (378, 432)
        print("PEHC self-test PASS: 490 configs, 8 blocked windows")
        return
    stages = {
        "manifest": stage_manifest,
        "stage-a": stage_a,
        "stage-b": stage_b,
        "stage-c": stage_c,
        "freeze": stage_freeze,
        "prospective": stage_prospective,
    }
    if args.stage == "all":
        for name in ("manifest", "stage-a", "stage-b", "stage-c", "freeze", "prospective"):
            result = stages[name]()
            print(name, result["status"])
        return
    result = stages[args.stage]()
    print(json.dumps({"stage": args.stage, "status": result["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
