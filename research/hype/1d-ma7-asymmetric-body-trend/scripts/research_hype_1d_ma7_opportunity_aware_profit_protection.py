"""Stage-locked OAPP search with opportunity-aware evidence and one-shot H access."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import importlib.util
import json
import math
from pathlib import Path
import re
import subprocess
import sys
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CONTRACT_PATH = FAMILY_DIR / "specs/hype-1d-ma7-opportunity-aware-profit-protection-preregistration-2026-08-10.md"
ENGINE_PATH = SCRIPT_DIR / "hype_1d_ma7_opportunity_aware_profit_protection_engine.py"
BASE_ENGINE_PATH = SCRIPT_DIR / "hype_1d_ma7_wide_trend_lifecycle_engine.py"
BASE_RESEARCH_PATH = SCRIPT_DIR / "research_hype_1d_ma7_wide_trend_lifecycle.py"
METRICS_PATH = SCRIPT_DIR / "hype_1d_ma7_trend_phase_risk_metrics.py"
ADAPTER_PATH = SCRIPT_DIR / "hype_1d_ma7_v4_fair_adapter.py"
RENDERER_PATH = SCRIPT_DIR / "render_hype_1d_ma7_wide_trend_lifecycle.py"
ORCHESTRATOR_PATH = Path(__file__).resolve()
ENGINE_TEST_PATH = ROOT / "tests/test_hype_1d_ma7_opportunity_aware_profit_protection_engine.py"
RESEARCH_TEST_PATH = ROOT / "tests/test_hype_1d_ma7_opportunity_aware_profit_protection_research.py"
BASE_TEST_PATHS = (
    ROOT / "tests/test_hype_1d_ma7_wide_trend_lifecycle_engine.py",
    ROOT / "tests/test_hype_1d_ma7_wide_trend_lifecycle_research.py",
    ROOT / "tests/test_hype_1d_ma7_wide_trend_lifecycle_trade_path.py",
    ROOT / "tests/test_hype_1d_ma7_v4_fair_adapter.py",
    ROOT / "tests/test_hype_1d_ma7_intent_harness.py",
    ROOT / "tests/test_hype_1d_ma7_intent_fair_metrics.py",
    ROOT / "tests/test_hype_1d_ma7_trend_phase_risk.py",
)
TEST_PATHS = (*BASE_TEST_PATHS, ENGINE_TEST_PATH, RESEARCH_TEST_PATH)
EXPECTED_TEST_COUNT = 68

PREFIX = ARTIFACT_DIR / "hype_1d_ma7_opportunity_aware_profit_protection_2026-08-10"
MANIFEST_PATH = Path(f"{PREFIX}_manifest.json")
STAGE_A_PATH = Path(f"{PREFIX}_stage_a.json")
STAGE_B_PATH = Path(f"{PREFIX}_stage_b.json")
STAGE_C_PATH = Path(f"{PREFIX}_stage_c.json")
CHAMPION_PATH = Path(f"{PREFIX}_champion.json")
LEVERAGE_PATH = Path(f"{PREFIX}_leverage_freeze.json")
HOLDOUT_LOCK_PATH = Path(f"{PREFIX}_holdout_access_lock.json")
HOLDOUT_PATH = Path(f"{PREFIX}_holdout.json")
FINAL_PATH = Path(f"{PREFIX}_final.json")
HTML_PATH = Path(f"{PREFIX}_full_trade_path.html")
WTL_MANIFEST_PATH = ARTIFACT_DIR / "hype_1d_ma7_wide_trend_lifecycle_2026-08-10_manifest.json"

D_FULL = (0, 259)
V_FULL = (269, 346)
ROLLING_FOLDS = ((130, 173), (173, 216), (216, 259), (270, 295), (295, 320), (320, 346))
H_EVAL = (356, 432)
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
MATERIAL_RETURN_PP = 5.0
MATERIAL_MDD_PP = 2.0


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_BASE_RESEARCH = load_module(BASE_RESEARCH_PATH, "hype_oapp_base_research")
sha256 = _BASE_RESEARCH.sha256
sidecar = _BASE_RESEARCH.sidecar
canonical = _BASE_RESEARCH.canonical
canonical_hash = _BASE_RESEARCH.canonical_hash
write_locked = _BASE_RESEARCH.write_locked
read_locked = _BASE_RESEARCH.read_locked
compare = _BASE_RESEARCH.compare
aggregate_folds = _BASE_RESEARCH.aggregate_folds
metrics_equal = _BASE_RESEARCH.metrics_equal


def implementation_paths() -> dict[str, Path]:
    return {
        "contract": CONTRACT_PATH,
        "engine": ENGINE_PATH,
        "orchestrator": ORCHESTRATOR_PATH,
        "engine_test": ENGINE_TEST_PATH,
        "research_test": RESEARCH_TEST_PATH,
        "base_engine": BASE_ENGINE_PATH,
        "base_research": BASE_RESEARCH_PATH,
        "metrics": METRICS_PATH,
        "adapter": ADAPTER_PATH,
        "renderer": RENDERER_PATH,
        **{f"base_test_{index}": path for index, path in enumerate(BASE_TEST_PATHS, 1)},
    }


def current_pins() -> dict[str, dict[str, str]]:
    return {label: {"path": str(path), "sha256": sha256(path)} for label, path in implementation_paths().items()}


def assert_pins(pins: dict[str, dict[str, str]]) -> None:
    if current_pins() != pins:
        raise RuntimeError("OAPP implementation pin drift")


def load_runtime() -> tuple[ModuleType, ModuleType, ModuleType, ModuleType, Any]:
    engine = load_module(ENGINE_PATH, "hype_oapp_engine_runtime")
    risk = load_module(METRICS_PATH, "hype_oapp_metrics_runtime")
    adapter = load_module(ADAPTER_PATH, "hype_oapp_adapter_runtime")
    renderer = load_module(RENDERER_PATH, "hype_oapp_renderer_runtime")
    return engine, risk, adapter, renderer, adapter.load_context()


def run_one(**kwargs: Any) -> dict[str, Any]:
    return _BASE_RESEARCH.run_one(**kwargs)


def safe_run(**kwargs: Any) -> dict[str, Any]:
    return _BASE_RESEARCH.safe_run(**kwargs)


def run_preflight() -> dict[str, Any]:
    if EXPECTED_TEST_COUNT <= 0:
        raise RuntimeError("EXPECTED_TEST_COUNT is not frozen")
    command = [str(ROOT / ".venv/bin/pytest"), "-q", *map(str, TEST_PATHS)]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    output = f"{completed.stdout}\n{completed.stderr}".strip()
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
        raise RuntimeError(f"preflight expected {EXPECTED_TEST_COUNT}, got {passed}")
    return record


def downstream_paths() -> tuple[Path, ...]:
    return (STAGE_A_PATH, STAGE_B_PATH, STAGE_C_PATH, CHAMPION_PATH, LEVERAGE_PATH, HOLDOUT_LOCK_PATH, HOLDOUT_PATH, FINAL_PATH, HTML_PATH)


def assert_manifest() -> dict[str, Any]:
    manifest, _ = read_locked(MANIFEST_PATH)
    if manifest.get("status") != "PASS" or not manifest.get("oapp_candidate_h_unrevealed"):
        raise RuntimeError("invalid OAPP manifest")
    assert_pins(manifest["pins"])
    return manifest


def module_family(config: Any) -> str:
    modules = config.enabled_modules()
    if modules == ["long_exit"]:
        return "long_exit"
    if modules == ["short_rsi"]:
        return "short_rsi"
    raise ValueError("OAPP Stage A requires exactly one permitted module")


def module_active(module: str, counts: dict[str, int]) -> bool:
    key = "long_trail_exit" if module == "long_exit" else "short_rsi_exit"
    return int(counts.get(key, 0)) > 0


def strict_domain_gate(candidate: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    comparison = compare(candidate["metrics"], control["metrics"])
    passed = comparison["return_higher"] and comparison["mdd_smaller"] and comparison["material"]
    return {"status": "PASS" if passed else "FAIL", "comparison": comparison}


def economic_path_key(row: dict[str, Any]) -> str:
    return f"{row['domains']['D']['trades_sha256']}:{row['domains']['V']['trades_sha256']}"


def _stage_a_key(row: dict[str, Any]) -> tuple[Any, ...]:
    comparisons = [row["comparisons"][label] for label in ("D", "V")]
    config = row["config"]
    complexity = config["long_exit"].get("confirm_days", config["short_rsi"].get("days", 0))
    return (
        -sum(item["return_higher"] and item["mdd_smaller"] for item in comparisons),
        -min(item["return_delta_pp"] for item in comparisons),
        -min(item["chronological_mdd_delta_pp"] for item in comparisons),
        -row["compound_equity"],
        complexity,
        row["arm_id"],
    )


def stage_manifest() -> dict[str, Any]:
    if MANIFEST_PATH.exists() or sidecar(MANIFEST_PATH).exists() or any(path.exists() or sidecar(path).exists() for path in downstream_paths()):
        raise RuntimeError("OAPP artifact already exists")
    preflight = run_preflight()
    engine, risk, adapter, _, context = load_runtime()
    grid = engine.stage_a_configs()
    if len(grid) != 957 or len(engine.trail_specs()) != 912 or len(engine.rsi_specs()) != 45:
        raise RuntimeError("OAPP frozen grid drift")
    wtl_manifest, wtl_sha = read_locked(WTL_MANIFEST_PATH)
    if wtl_manifest.get("status") != "PASS" or wtl_manifest.get("market_audit", {}).get("trusted_hourly_audit", {}).get("blocker_count") != 0:
        raise RuntimeError("upstream market evidence invalid")
    full = run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=(0, 432), config=None)
    pins = current_pins()
    payload = {
        "schema": "hype-oapp-manifest-v1",
        "status": "PASS",
        "preflight": preflight,
        "pins": pins,
        "upstream_wtl_manifest_sha256": wtl_sha,
        "market_audit": wtl_manifest["market_audit"],
        "book_quality": wtl_manifest["book_quality"],
        "exact_v4_full_anchor": full,
        "windows": {"D": D_FULL, "V_exposed": V_FULL, "rolling": ROLLING_FOLDS, "H_final": H_EVAL},
        "stage_a_count": len(grid),
        "long_grid_count": len(engine.trail_specs()),
        "rsi_grid_count": len(engine.rsi_specs()),
        "stage_a_grid": [row.canonical() for row in grid],
        "stage_a_hashes": {row.arm_id: engine.config_sha256(row) for row in grid},
        "max_stage_c_count": 64,
        "leverage_grid": [asdict(row) for row in engine.leverage_specs()],
        "research_state": "D+V researcher-exposed Development; H sole one-shot final",
        "oapp_candidate_h_unrevealed": True,
    }
    assert_pins(pins)
    write_locked(MANIFEST_PATH, payload)
    return payload


def stage_a() -> dict[str, Any]:
    manifest = assert_manifest()
    if STAGE_A_PATH.exists() or sidecar(STAGE_A_PATH).exists() or any(path.exists() for path in downstream_paths()[1:]):
        raise RuntimeError("invalid Stage A artifact state")
    engine, risk, adapter, _, context = load_runtime()
    controls = {
        label: run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=window, config=None)
        for label, window in (("D", D_FULL), ("V", V_FULL))
    }
    rows: list[dict[str, Any]] = []
    for index, config in enumerate(engine.stage_a_configs(), 1):
        domains = {
            label: safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=window, config=config)
            for label, window in (("D", D_FULL), ("V", V_FULL))
        }
        row: dict[str, Any] = {
            "arm_id": config.arm_id,
            "family": module_family(config),
            "config": config.canonical(),
            "config_sha256": engine.config_sha256(config),
            "domains": domains,
            "status": "PASS" if all(item["status"] == "PASS" for item in domains.values()) else "ERROR",
        }
        if row["status"] == "PASS":
            row["comparisons"] = {label: compare(domains[label]["metrics"], controls[label]["metrics"]) for label in ("D", "V")}
            active = any(module_active(row["family"], domains[label]["activation_counts"]) for label in ("D", "V"))
            changed = any(domains[label]["trades_sha256"] != controls[label]["trades_sha256"] for label in ("D", "V"))
            not_double = all(not item["double_worse"] for item in row["comparisons"].values())
            row["compound_equity"] = math.prod(float(domains[label]["metrics"]["equity_multiple"]) for label in ("D", "V"))
            row["eligible"] = active and changed and not_double
            row["checks"] = {"active": active, "path_changed": changed, "both_domains_not_double_worse": not_double}
        else:
            row.update({"comparisons": {}, "compound_equity": None, "eligible": False, "checks": {}})
        rows.append(row)
        if index % 50 == 0:
            print(f"OAPP Stage A {index}/957", file=sys.stderr, flush=True)
    shortlists: dict[str, list[str]] = {}
    duplicate_paths: dict[str, int] = {}
    for family in ("long_exit", "short_rsi"):
        eligible = sorted([row for row in rows if row["family"] == family and row["eligible"]], key=_stage_a_key)
        unique: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in eligible:
            key = economic_path_key(row)
            if key in seen:
                duplicate_paths[family] = duplicate_paths.get(family, 0) + 1
                continue
            seen.add(key)
            unique.append(row)
        shortlists[family] = [row["arm_id"] for row in unique[:16]]
    payload = {
        "schema": "hype-oapp-stage-a-v1",
        "status": "PASS" if all(shortlists.values()) else "FAIL",
        "manifest_sha256": sha256(MANIFEST_PATH),
        "controls": controls,
        "trial_count": len(rows),
        "error_count": sum(row["status"] == "ERROR" for row in rows),
        "duplicate_economic_paths_removed": duplicate_paths,
        "shortlists": shortlists,
        "rows": rows,
        "h_accessed": False,
    }
    assert_pins(manifest["pins"])
    write_locked(STAGE_A_PATH, payload)
    return payload


def _stage_b_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -sum(not item["double_worse"] for item in row["fold_comparisons"]),
        -row["rolling_comparison"]["return_delta_pp"],
        -row["rolling_comparison"]["chronological_mdd_delta_pp"],
        -min(row["full_comparisons"][label]["return_delta_pp"] for label in ("D", "V")),
        -min(row["full_comparisons"][label]["chronological_mdd_delta_pp"] for label in ("D", "V")),
        row["arm_id"],
    )


def stage_b() -> dict[str, Any]:
    manifest = assert_manifest()
    stage_a_payload, _ = read_locked(STAGE_A_PATH)
    if stage_a_payload.get("status") != "PASS" or STAGE_B_PATH.exists() or sidecar(STAGE_B_PATH).exists() or any(path.exists() for path in downstream_paths()[2:]):
        raise RuntimeError("invalid Stage B state")
    engine, risk, adapter, _, context = load_runtime()
    controls = {
        "D": stage_a_payload["controls"]["D"],
        "V": stage_a_payload["controls"]["V"],
        "stress_D": run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=D_FULL, config=None, slippage=STRESS_SLIPPAGE),
        "stress_V": run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=V_FULL, config=None, slippage=STRESS_SLIPPAGE),
        "folds": [run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=fold, config=None) for fold in ROLLING_FOLDS],
    }
    controls["rolling"] = aggregate_folds(controls["folds"])
    by_id = {row["arm_id"]: row for row in stage_a_payload["rows"]}
    rows: list[dict[str, Any]] = []
    for family, arm_ids in stage_a_payload["shortlists"].items():
        for arm_id in arm_ids:
            config = engine.config_from_dict(by_id[arm_id]["config"])
            stress = {
                label: safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=window, config=config, slippage=STRESS_SLIPPAGE)
                for label, window in (("D", D_FULL), ("V", V_FULL))
            }
            folds = [safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=fold, config=config) for fold in ROLLING_FOLDS]
            status = "PASS" if all(item["status"] == "PASS" for item in (*stress.values(), *folds)) else "ERROR"
            row: dict[str, Any] = {"arm_id": arm_id, "family": family, "config": config.canonical(), "base": by_id[arm_id]["domains"], "stress": stress, "folds": folds, "status": status}
            if status == "PASS":
                row["rolling"] = aggregate_folds(folds)
                row["rolling_comparison"] = compare(row["rolling"], controls["rolling"])
                row["fold_comparisons"] = [compare(item["metrics"], base["metrics"]) for item, base in zip(folds, controls["folds"])]
                row["full_comparisons"] = {label: compare(row["base"][label]["metrics"], controls[label]["metrics"]) for label in ("D", "V")}
                stress_ok = all(not compare(stress[label]["metrics"], controls[f"stress_{label}"]["metrics"])["double_worse"] for label in ("D", "V"))
                folds_ok = all(not item["double_worse"] for item in row["fold_comparisons"])
                active_pairs = sum(int(item["metrics"]["closed_trades"]) > 0 and int(base["metrics"]["closed_trades"]) > 0 for item, base in zip(folds, controls["folds"]))
                row["eligible"] = stress_ok and folds_ok and active_pairs >= 4
                row["active_fold_pairs"] = active_pairs
            else:
                row["eligible"] = False
            rows.append(row)
    survivors: dict[str, list[str]] = {}
    survivor_specs: dict[str, list[dict[str, Any]]] = {}
    for family in ("long_exit", "short_rsi"):
        ranked = sorted([row for row in rows if row["family"] == family and row["eligible"]], key=_stage_b_key)
        unique: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in ranked:
            key = f"{row['base']['D']['trades_sha256']}:{row['base']['V']['trades_sha256']}"
            if key not in seen:
                seen.add(key)
                unique.append(row)
        chosen = unique[:8]
        survivors[family] = [row["arm_id"] for row in chosen]
        survivor_specs[family] = [row["config"][family] for row in chosen]
    payload = {
        "schema": "hype-oapp-stage-b-v1",
        "status": "PASS" if all(survivors.values()) else "FAIL",
        "manifest_sha256": sha256(MANIFEST_PATH),
        "stage_a_sha256": sha256(STAGE_A_PATH),
        "controls": controls,
        "trial_count": len(rows),
        "survivors": survivors,
        "survivor_specs": survivor_specs,
        "rows": rows,
        "h_accessed": False,
    }
    assert_pins(manifest["pins"])
    write_locked(STAGE_B_PATH, payload)
    return payload


def _trade_key(trade: dict[str, Any]) -> tuple[str, str]:
    return str(trade.get("side")), str(trade.get("entry_ts"))


def paired_episode_audit(candidate_domains: dict[str, dict[str, Any]], control_domains: dict[str, dict[str, Any]]) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    for label in ("D", "V"):
        candidate = {_trade_key(row): row for row in candidate_domains[label].get("trades", [])}
        control = {_trade_key(row): row for row in control_domains[label].get("trades", [])}
        for key in sorted(candidate.keys() | control.keys()):
            cand = candidate.get(key)
            base = control.get(key)
            cand_pnl = float(cand.get("net_pnl", 0.0)) if cand else 0.0
            base_pnl = float(base.get("net_pnl", 0.0)) if base else 0.0
            contribution = cand_pnl - base_pnl
            changed = cand is None or base is None or any(
                cand.get(field) != base.get(field)
                for field in ("exit_ts", "exit_price", "exit_reason")
            )
            if not changed and math.isclose(contribution, 0.0, abs_tol=1e-12):
                continue
            entry_reason = str((base or cand or {}).get("entry_reason", ""))
            events.append(
                {
                    "domain": label,
                    "side": key[0],
                    "entry_ts": key[1],
                    "candidate_exit_ts": cand.get("exit_ts") if cand else None,
                    "control_exit_ts": base.get("exit_ts") if base else None,
                    "candidate_exit_reason": cand.get("exit_reason") if cand else None,
                    "control_exit_reason": base.get("exit_reason") if base else None,
                    "candidate_net_pnl": cand_pnl if cand else None,
                    "control_net_pnl": base_pnl if base else None,
                    "incremental_net_pnl": contribution,
                    "control_only": cand is None,
                    "candidate_only": base is None,
                    "suppressed_forced_reversal": cand is None and ("revers" in entry_reason.lower() or "forced" in entry_reason.lower()),
                }
            )
    positives = [row for row in events if float(row["incremental_net_pnl"]) > 0.0]
    total = sum(float(row["incremental_net_pnl"]) for row in events)
    largest = max((float(row["incremental_net_pnl"]) for row in positives), default=0.0)
    return {
        "changed_episode_count": len(events),
        "positive_episode_count": len(positives),
        "incremental_net_pnl": total,
        "largest_positive_incremental_net_pnl": largest,
        "incremental_after_dropping_largest_positive": total - largest,
        "suppressed_forced_reversal_count": sum(row["suppressed_forced_reversal"] for row in events),
        "events": events,
    }


def opportunity_prepass(row: dict[str, Any], controls: dict[str, Any]) -> dict[str, Any]:
    if any(row[label]["status"] != "PASS" for label in ("D", "V")):
        return {"status": "ERROR", "checks": {}}
    domains = {label: strict_domain_gate(row[label], controls[label]) for label in ("D", "V")}
    d_metrics = row["D"]["metrics"]
    v_metrics = row["V"]["metrics"]
    long_total = sum(int(row[label]["activation_counts"].get("long_trail_exit", 0)) for label in ("D", "V"))
    rsi_total = sum(int(row[label]["activation_counts"].get("short_rsi_exit", 0)) for label in ("D", "V"))
    checks = {
        "D_strict_dual": domains["D"]["status"] == "PASS",
        "V_strict_dual": domains["V"]["status"] == "PASS",
        "D_path_changed": row["D"]["trades_sha256"] != controls["D"]["trades_sha256"],
        "V_path_changed": row["V"]["trades_sha256"] != controls["V"]["trades_sha256"],
        "D_trade_floor": int(d_metrics["closed_trades"]) >= 8,
        "D_long_floor": int(d_metrics["long_trades"]) >= 3,
        "D_short_floor": int(d_metrics["short_trades"]) >= 3,
        "DV_combined_trade_floor": int(d_metrics["closed_trades"]) + int(v_metrics["closed_trades"]) >= 12,
        "V_candidate_opportunity_floor": int(v_metrics["closed_trades"]) >= 1,
        "V_control_episode_floor": int(controls["V"]["metrics"]["closed_trades"]) >= 3,
        "long_exit_total": long_total >= 2,
        "long_exit_in_V": int(row["V"]["activation_counts"].get("long_trail_exit", 0)) >= 1,
        "rsi_exit_total": rsi_total >= 2,
    }
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "domains": domains, "long_exit_total": long_total, "rsi_exit_total": rsi_total}


def _combo_key(row: dict[str, Any]) -> tuple[Any, ...]:
    gates = row["prepass"]["domains"]
    return (
        -min(gates[label]["comparison"]["return_delta_pp"] for label in ("D", "V")),
        -min(gates[label]["comparison"]["chronological_mdd_delta_pp"] for label in ("D", "V")),
        row["arm_id"],
    )


def evaluate_deep(*, engine: Any, risk: Any, adapter: Any, context: Any, config: Any, controls: dict[str, Any], base_row: dict[str, Any]) -> dict[str, Any]:
    stress = {label: safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=window, config=config, slippage=STRESS_SLIPPAGE) for label, window in (("D", D_FULL), ("V", V_FULL))}
    funding_off = {label: safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=window, config=config, include_funding=False) for label, window in (("D", D_FULL), ("V", V_FULL))}
    folds = [safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=fold, config=config) for fold in ROLLING_FOLDS]
    retained = {label: safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=window, config=config, retain=True) for label, window in (("D", D_FULL), ("V", V_FULL))}
    control_retained = controls["retained"]
    if not all(item["status"] == "PASS" for item in (*stress.values(), *funding_off.values(), *folds, *retained.values())):
        return {"status": "ERROR", "checks": {}, "stress": stress, "funding_off": funding_off, "folds": folds, "retained": retained}
    stress_comparisons = {label: compare(stress[label]["metrics"], controls[f"stress_{label}"]["metrics"]) for label in ("D", "V")}
    fold_comparisons = [compare(item["metrics"], base["metrics"]) for item, base in zip(folds, controls["folds"])]
    rolling = aggregate_folds(folds)
    rolling_comparison = compare(rolling, controls["rolling"])
    episode = paired_episode_audit(retained, control_retained)
    changed_folds = sum(item["trades_sha256"] != base["trades_sha256"] for item, base in zip(folds, controls["folds"]))
    active_pairs = sum(int(item["metrics"]["closed_trades"]) > 0 and int(base["metrics"]["closed_trades"]) > 0 for item, base in zip(folds, controls["folds"]))
    checks = {
        "stress_not_double_worse": all(not item["double_worse"] for item in stress_comparisons.values()),
        "funding_off_solved": all(item["status"] == "PASS" for item in funding_off.values()),
        "rolling_strict_dual": rolling_comparison["return_higher"] and rolling_comparison["mdd_smaller"] and rolling_comparison["material"],
        "folds_not_double_worse": all(not item["double_worse"] for item in fold_comparisons),
        "four_active_fold_pairs": active_pairs >= 4,
        "two_changed_folds": changed_folds >= 2,
        "three_changed_episodes": episode["changed_episode_count"] >= 3,
        "three_positive_episodes": episode["positive_episode_count"] >= 3,
        "drop_largest_still_positive": episode["incremental_after_dropping_largest_positive"] > 0.0,
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "stress": stress,
        "funding_off": funding_off,
        "folds": folds,
        "rolling": rolling,
        "rolling_comparison": rolling_comparison,
        "stress_comparisons": stress_comparisons,
        "fold_comparisons": fold_comparisons,
        "changed_fold_count": changed_folds,
        "active_fold_pairs": active_pairs,
        "episode_audit": episode,
        "retained": retained,
        "base_prepass": base_row["prepass"],
    }


def _deep_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (*_combo_key(row)[:2], -row["deep"]["rolling_comparison"]["return_delta_pp"], -row["deep"]["rolling_comparison"]["chronological_mdd_delta_pp"], row["arm_id"])


def _ablation_gate(config: Any, candidate: dict[str, Any], leave_one: list[dict[str, Any]], neighbors: list[dict[str, Any]]) -> dict[str, Any]:
    by_module = {row["module"]: row for row in leave_one}
    activations = {
        "long_exit": sum(int(candidate[label]["activation_counts"].get("long_trail_exit", 0)) for label in ("D", "V")),
        "short_rsi": sum(int(candidate[label]["activation_counts"].get("short_rsi_exit", 0)) for label in ("D", "V")),
    }
    paths = {module: any(by_module[module][label]["trades_sha256"] != candidate[label]["trades_sha256"] for label in ("D", "V")) for module in config.enabled_modules()}
    disabled_dominates = {
        module: all((cmp := compare(by_module[module][label]["metrics"], candidate[label]["metrics"]))["return_higher"] and cmp["mdd_smaller"] for label in ("D", "V"))
        for module in config.enabled_modules()
    }
    neighbor_pass = any(row.get("prepass", {}).get("status") == "PASS" and row.get("deep", {}).get("status") == "PASS" for row in neighbors)
    checks = {
        "both_modules_active": activations["long_exit"] >= 2 and activations["short_rsi"] >= 2,
        "both_leave_one_paths_change": all(paths.values()),
        "no_disabled_module_dominates": not any(disabled_dominates.values()),
        "adjacent_neighbor_deep_pass": neighbor_pass,
    }
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "activation_totals": activations, "leave_one_path_change": paths, "disabled_module_dominates": disabled_dominates}


def stage_c() -> dict[str, Any]:
    manifest = assert_manifest()
    stage_b_payload, _ = read_locked(STAGE_B_PATH)
    if stage_b_payload.get("status") != "PASS" or STAGE_C_PATH.exists() or sidecar(STAGE_C_PATH).exists() or CHAMPION_PATH.exists() or any(path.exists() for path in downstream_paths()[4:]):
        raise RuntimeError("invalid Stage C state")
    engine, risk, adapter, _, context = load_runtime()
    specs = stage_b_payload["survivor_specs"]
    combos = engine.build_combo_configs([engine.TrailExit(**row) for row in specs["long_exit"]], [engine.ShortRSIExit(**row) for row in specs["short_rsi"]])
    if len(combos) > 64:
        raise RuntimeError("OAPP combo count exceeds frozen maximum")
    controls = dict(stage_b_payload["controls"])
    controls["retained"] = {label: run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=window, config=None, retain=True) for label, window in (("D", D_FULL), ("V", V_FULL))}
    rows: list[dict[str, Any]] = []
    for index, config in enumerate(combos, 1):
        row = {
            "arm_id": config.arm_id,
            "config": config.canonical(),
            "config_sha256": engine.config_sha256(config),
            "D": safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=D_FULL, config=config),
            "V": safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=V_FULL, config=config),
        }
        row["prepass"] = opportunity_prepass(row, controls)
        rows.append(row)
        print(f"OAPP Stage C prepass {index}/{len(combos)}", file=sys.stderr, flush=True)
    shortlist = sorted([row for row in rows if row["prepass"]["status"] == "PASS"], key=_combo_key)[:32]
    for index, row in enumerate(shortlist, 1):
        config = engine.config_from_dict(row["config"])
        row["deep"] = evaluate_deep(engine=engine, risk=risk, adapter=adapter, context=context, config=config, controls=controls, base_row=row)
        print(f"OAPP Stage C deep {index}/{len(shortlist)}", file=sys.stderr, flush=True)
    deep_passers = sorted([row for row in shortlist if row["deep"]["status"] == "PASS"], key=_deep_key)
    all_off = engine.WTLConfig("ALL_OFF")
    all_off_evidence = {label: run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=window, config=all_off) for label, window in (("D", D_FULL), ("V", V_FULL))}
    all_off_parity = all(all_off_evidence[label]["trades_sha256"] == controls[label]["trades_sha256"] and metrics_equal(all_off_evidence[label]["metrics"], controls[label]["metrics"]) for label in ("D", "V"))
    ablations: list[dict[str, Any]] = []
    for index, row in enumerate(deep_passers[:16], 1):
        config = engine.config_from_dict(row["config"])
        leave_one = []
        keep_one = []
        for module in config.enabled_modules():
            disabled = engine.disable_module(config, module, "OAPP_OAT")
            only = engine.keep_only_module(config, module)
            leave_one.append({"module": module, "config": disabled.canonical(), **{label: safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=window, config=disabled) for label, window in (("D", D_FULL), ("V", V_FULL))}})
            keep_one.append({"module": module, "config": only.canonical(), **{label: safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=window, config=only) for label, window in (("D", D_FULL), ("V", V_FULL))}})
        neighbors = []
        for neighbor in engine.adjacent_neighbors(config):
            neighbor_row = {
                "arm_id": neighbor.arm_id,
                "config": neighbor.canonical(),
                "D": safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=D_FULL, config=neighbor),
                "V": safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=V_FULL, config=neighbor),
            }
            neighbor_row["prepass"] = opportunity_prepass(neighbor_row, controls)
            if neighbor_row["prepass"]["status"] == "PASS":
                neighbor_row["deep"] = evaluate_deep(engine=engine, risk=risk, adapter=adapter, context=context, config=neighbor, controls=controls, base_row=neighbor_row)
            else:
                neighbor_row["deep"] = {"status": "SKIPPED", "checks": {}}
            neighbors.append(neighbor_row)
        valid = all(item[label]["status"] == "PASS" for item in (*leave_one, *keep_one) for label in ("D", "V"))
        gate = _ablation_gate(config, row, leave_one, neighbors) if valid and all_off_parity else {"status": "ERROR", "checks": {"all_off_parity": all_off_parity}}
        row["ablation_gate"] = gate
        ablations.append({"arm_id": row["arm_id"], "leave_one_out": leave_one, "keep_one_only": keep_one, "adjacent_neighbors": neighbors, "gate": gate})
        print(f"OAPP Stage C ablation {index}/{min(16, len(deep_passers))}", file=sys.stderr, flush=True)
    finalists = sorted([row for row in deep_passers[:16] if row.get("ablation_gate", {}).get("status") == "PASS"], key=_deep_key)
    champion = finalists[0] if finalists else None
    payload = {
        "schema": "hype-oapp-stage-c-v1",
        "status": "PASS" if champion else "FAIL",
        "hard_gate": "PASS" if champion else "FAIL",
        "manifest_sha256": sha256(MANIFEST_PATH),
        "stage_b_sha256": sha256(STAGE_B_PATH),
        "combo_count": len(combos),
        "prepass_pass_count": len(shortlist),
        "deep_pass_count": len(deep_passers),
        "ablation_count": len(ablations),
        "all_off_evidence": all_off_evidence,
        "all_off_parity": all_off_parity,
        "champion_arm_id": champion["arm_id"] if champion else None,
        "rows": rows,
        "ablations": ablations,
        "h_accessed": False,
    }
    assert_pins(manifest["pins"])
    stage_c_digest = write_locked(STAGE_C_PATH, payload)
    if champion:
        retained = {label: run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=window, config=engine.config_from_dict(champion["config"]), retain=True) for label, window in (("D", D_FULL), ("V", V_FULL))}
        write_locked(CHAMPION_PATH, {"schema": "hype-oapp-champion-v1", "arm_id": champion["arm_id"], "config": champion["config"], "config_sha256": champion["config_sha256"], "prepass": champion["prepass"], "deep": champion["deep"], "ablation_gate": champion["ablation_gate"], "retained_exposed_evidence": retained, "manifest_sha256": sha256(MANIFEST_PATH), "stage_c_sha256": stage_c_digest, "implementation_pins": manifest["pins"], "h_accessed": False})
    return payload


def load_champion() -> tuple[dict[str, Any], dict[str, Any], Any, Any]:
    manifest = assert_manifest()
    stage_c_payload, _ = read_locked(STAGE_C_PATH)
    if stage_c_payload.get("status") != "PASS":
        raise RuntimeError("OAPP Stage C did not pass")
    champion, _ = read_locked(CHAMPION_PATH)
    if champion["implementation_pins"] != manifest["pins"]:
        raise RuntimeError("OAPP champion pin drift")
    engine, risk, adapter, renderer, context = load_runtime()
    return manifest, champion, engine.config_from_dict(champion["config"]), (engine, risk, adapter, renderer, context)


def stage_leverage() -> dict[str, Any]:
    manifest, champion, config, runtime = load_champion()
    if LEVERAGE_PATH.exists() or sidecar(LEVERAGE_PATH).exists() or any(path.exists() for path in downstream_paths()[5:]):
        raise RuntimeError("invalid leverage artifact state")
    engine, risk, adapter, _, context = runtime
    one_x = champion["retained_exposed_evidence"]
    rows = []
    for spec in engine.leverage_specs():
        row = {"spec": asdict(spec)}
        for label, window in (("D", D_FULL), ("V", V_FULL)):
            row[label] = {
                "base": safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=window, config=config, leverage_spec=spec),
                "stress": safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=window, config=config, leverage_spec=spec, slippage=STRESS_SLIPPAGE),
                "funding_off": safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=window, config=config, leverage_spec=spec, include_funding=False),
            }
        valid = all(row[label][variant]["status"] == "PASS" for label in ("D", "V") for variant in ("base", "stress", "funding_off"))
        higher = valid and all(float(row[label]["base"]["metrics"]["net_return_pct"]) > float(one_x[label]["metrics"]["net_return_pct"]) for label in ("D", "V"))
        worst_mdd = max(abs(float(row[label]["base"]["metrics"]["chronological_1h_mdd_pct"])) for label in ("D", "V")) if valid else math.inf
        row.update({"status": "PASS" if valid else "ERROR", "returns_higher_than_1x": higher, "worst_exposed_mdd_pct": worst_mdd, "eligible_35": higher and worst_mdd <= 35.0, "eligible_50": higher and worst_mdd <= 50.0})
        rows.append(row)
    payload = {"schema": "hype-oapp-leverage-freeze-v1", "status": "PASS", "manifest_sha256": sha256(MANIFEST_PATH), "champion_sha256": sha256(CHAMPION_PATH), "champion_arm_id": champion["arm_id"], "rows": rows, "h_accessed": False}
    assert_pins(manifest["pins"])
    write_locked(LEVERAGE_PATH, payload)
    return payload


def final_gate(candidate: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    domain = strict_domain_gate(candidate, control)
    checks = {
        "strict_dual_material": domain["status"] == "PASS",
        "candidate_trade_floor": int(candidate["metrics"]["closed_trades"]) >= 1,
        "control_trade_floor": int(control["metrics"]["closed_trades"]) >= 3,
        "path_changed": candidate["trades_sha256"] != control["trades_sha256"],
        "candidate_solved": candidate["status"] == "PASS",
        "control_solved": control["status"] == "PASS",
    }
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "domain": domain}


def stage_holdout() -> dict[str, Any]:
    manifest, champion, config, runtime = load_champion()
    leverage, leverage_sha = read_locked(LEVERAGE_PATH)
    if leverage.get("status") != "PASS" or HOLDOUT_LOCK_PATH.exists() or HOLDOUT_PATH.exists() or sidecar(HOLDOUT_PATH).exists() or FINAL_PATH.exists() or HTML_PATH.exists():
        raise RuntimeError("invalid one-shot H state")
    lock = {"schema": "hype-oapp-h-access-lock-v1", "status": "CONSUMED_ON_WRITE", "manifest_sha256": sha256(MANIFEST_PATH), "champion_sha256": sha256(CHAMPION_PATH), "leverage_sha256": leverage_sha, "window": H_EVAL, "no_retry": True}
    write_locked(HOLDOUT_LOCK_PATH, lock)
    engine, risk, adapter, _, context = runtime
    control = safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=H_EVAL, config=None, retain=True)
    one_x = safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=H_EVAL, config=config, retain=True)
    leverage_rows = []
    for frozen in leverage["rows"]:
        spec = engine.LeverageSpec(**frozen["spec"])
        leverage_rows.append({"spec": frozen["spec"], "frozen_eligible_35": frozen["eligible_35"], "frozen_eligible_50": frozen["eligible_50"], "base": safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=H_EVAL, config=config, leverage_spec=spec, retain=True), "stress": safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=H_EVAL, config=config, leverage_spec=spec, slippage=STRESS_SLIPPAGE)})
    gate = final_gate(one_x, control) if one_x["status"] == control["status"] == "PASS" else {"status": "ERROR", "checks": {}}
    opportunity = paired_episode_audit({"D": one_x, "V": one_x}, {"D": control, "V": control}) if one_x["status"] == control["status"] == "PASS" else None
    payload = {"schema": "hype-oapp-holdout-v1", "status": "PASS" if gate["status"] == "PASS" else "FAIL", "hard_gate": gate["status"], "manifest_sha256": sha256(MANIFEST_PATH), "champion_sha256": sha256(CHAMPION_PATH), "leverage_sha256": leverage_sha, "control": control, "one_x": one_x, "one_x_gate": gate, "opportunity_audit": opportunity, "leverage_rows": leverage_rows, "h_accessed": True, "one_shot": True}
    assert_pins(manifest["pins"])
    write_locked(HOLDOUT_PATH, payload)
    return payload


def _frontier(rows: list[dict[str, Any]], caps: tuple[int, ...] = (20, 25, 30, 35, 40, 50)) -> dict[str, Any]:
    return {
        str(cap): max((row for row in rows if row["status"] == "PASS" and abs(float(row["metrics"]["chronological_1h_mdd_pct"])) <= cap), key=lambda row: float(row["metrics"]["net_return_pct"]), default=None)
        for cap in caps
    }


def stage_finalize() -> dict[str, Any]:
    manifest, champion, config, runtime = load_champion()
    holdout, _ = read_locked(HOLDOUT_PATH)
    leverage, _ = read_locked(LEVERAGE_PATH)
    if FINAL_PATH.exists() or sidecar(FINAL_PATH).exists() or HTML_PATH.exists() or sidecar(HTML_PATH).exists():
        raise RuntimeError("final artifact exists")
    engine, risk, adapter, renderer, context = runtime
    full_control = run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=(0, 432), config=None, retain=True)
    full_one_x = run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=(0, 432), config=config, retain=True)
    h_frontier_rows = [{"id": "EXACT_V4_1X", "status": holdout["control"]["status"], "metrics": holdout["control"].get("metrics")}, {"id": "OAPP_1X", "status": holdout["one_x"]["status"], "metrics": holdout["one_x"].get("metrics")}]
    full_frontier_rows = [{"id": "EXACT_V4_1X", "status": "PASS", "metrics": full_control["metrics"]}, {"id": "OAPP_1X", "status": "PASS", "metrics": full_one_x["metrics"]}]
    for frozen, hrow in zip(leverage["rows"], holdout["leverage_rows"]):
        spec = engine.LeverageSpec(**frozen["spec"])
        full = safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=(0, 432), config=config, leverage_spec=spec)
        h_frontier_rows.append({"id": spec.id, "status": hrow["base"]["status"], "metrics": hrow["base"].get("metrics")})
        full_frontier_rows.append({"id": spec.id, "status": full["status"], "metrics": full.get("metrics")})
    candles = renderer.candles_from_context(context)
    document, html_audit = renderer.build_document(title=f"OAPP {champion['arm_id']} vs exact V4 — full path", candles=candles, candidate=full_one_x, control=full_control)
    html_write = renderer.write_locked(HTML_PATH, document)
    payload = {"schema": "hype-oapp-final-v1", "status": holdout["status"], "hard_gate": holdout["hard_gate"], "champion_arm_id": champion["arm_id"], "holdout": {"control": holdout["control"]["metrics"], "one_x": holdout["one_x"]["metrics"], "gate": holdout["one_x_gate"], "opportunity_audit": holdout["opportunity_audit"]}, "full": {"control": full_control["metrics"], "one_x": full_one_x["metrics"]}, "h_frontier": _frontier(h_frontier_rows), "full_frontier": _frontier(full_frontier_rows), "h_frontier_rows": h_frontier_rows, "full_frontier_rows": full_frontier_rows, "html": {**html_audit, **html_write}, "h_accessed": True, "no_v5": True, "not_promoted": True}
    assert_pins(manifest["pins"])
    write_locked(FINAL_PATH, payload)
    return payload


def self_test() -> dict[str, Any]:
    engine = load_module(ENGINE_PATH, "hype_oapp_self_test_engine")
    assert len(engine.trail_specs()) == 912
    assert len(engine.rsi_specs()) == 45
    assert len(engine.stage_a_configs()) == 957
    assert len(engine.leverage_specs()) == 9
    return {"status": "PASS", "stage_a_count": 957, "long_count": 912, "rsi_count": 45, "max_combo_count": 64, "leverage_count": 9}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=("self-test", "manifest", "stage-a", "stage-b", "stage-c", "leverage", "holdout", "finalize"))
    args = parser.parse_args()
    actions = {"self-test": self_test, "manifest": stage_manifest, "stage-a": stage_a, "stage-b": stage_b, "stage-c": stage_c, "leverage": stage_leverage, "holdout": stage_holdout, "finalize": stage_finalize}
    result = actions[args.stage]()
    print(json.dumps(canonical({"stage": args.stage, "status": result.get("status"), "hard_gate": result.get("hard_gate"), "output": str({"manifest": MANIFEST_PATH, "stage-a": STAGE_A_PATH, "stage-b": STAGE_B_PATH, "stage-c": STAGE_C_PATH, "leverage": LEVERAGE_PATH, "holdout": HOLDOUT_PATH, "finalize": FINAL_PATH}.get(args.stage, ""))}), sort_keys=True))


if __name__ == "__main__":
    main()
