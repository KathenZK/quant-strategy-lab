"""Stage-locked hierarchical WTL search on top of the registered exact V4."""

from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import subprocess
import sys
from types import ModuleType
from typing import Any, Callable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CONTRACT_PATH = FAMILY_DIR / "specs/hype-1d-ma7-wide-trend-lifecycle-preregistration-2026-08-10.md"
ENGINE_PATH = SCRIPT_DIR / "hype_1d_ma7_wide_trend_lifecycle_engine.py"
METRICS_PATH = SCRIPT_DIR / "hype_1d_ma7_trend_phase_risk_metrics.py"
ADAPTER_PATH = SCRIPT_DIR / "hype_1d_ma7_v4_fair_adapter.py"
RENDERER_PATH = SCRIPT_DIR / "render_hype_1d_ma7_wide_trend_lifecycle.py"
ORCHESTRATOR_PATH = Path(__file__).resolve()
ENGINE_TEST_PATH = ROOT / "tests/test_hype_1d_ma7_wide_trend_lifecycle_engine.py"
RESEARCH_TEST_PATH = ROOT / "tests/test_hype_1d_ma7_wide_trend_lifecycle_research.py"
RENDERER_TEST_PATH = ROOT / "tests/test_hype_1d_ma7_wide_trend_lifecycle_trade_path.py"
ADAPTER_TEST_PATH = ROOT / "tests/test_hype_1d_ma7_v4_fair_adapter.py"
HARNESS_TEST_PATH = ROOT / "tests/test_hype_1d_ma7_intent_harness.py"
FAIR_TEST_PATH = ROOT / "tests/test_hype_1d_ma7_intent_fair_metrics.py"
METRICS_TEST_PATH = ROOT / "tests/test_hype_1d_ma7_trend_phase_risk.py"
TEST_PATHS = (
    ENGINE_TEST_PATH,
    RESEARCH_TEST_PATH,
    RENDERER_TEST_PATH,
    ADAPTER_TEST_PATH,
    HARNESS_TEST_PATH,
    FAIR_TEST_PATH,
    METRICS_TEST_PATH,
)
EXPECTED_TEST_COUNT = 57

PREFIX = ARTIFACT_DIR / "hype_1d_ma7_wide_trend_lifecycle_2026-08-10"
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

D_FULL = (0, 259)
V_FULL = (269, 346)
ROLLING_FOLDS = (
    (130, 173),
    (173, 216),
    (216, 259),
    (270, 295),
    (295, 320),
    (320, 346),
)
H_EVAL = (356, 432)
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
MATERIAL_RETURN_PP = 5.0
MATERIAL_MDD_PP = 2.0


def sidecar(path: Path) -> Path:
    return path.with_suffix(".sha256")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: Any) -> Any:
    if is_dataclass(value):
        return canonical(asdict(value))
    if isinstance(value, dict):
        return {str(key): canonical(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [canonical(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.generic):
        return canonical(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        canonical(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def write_locked(path: Path, payload: Any) -> str:
    hash_path = sidecar(path)
    if path.exists() or hash_path.exists():
        raise RuntimeError(f"locked artifact already exists: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(
            canonical(payload),
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    with path.open("xb") as handle:
        handle.write(encoded)
    with hash_path.open("x", encoding="utf-8") as handle:
        handle.write(f"{digest}  {path.name}\n")
    return digest


def read_locked(path: Path) -> tuple[dict[str, Any], str]:
    hash_path = sidecar(path)
    if not path.is_file() or not hash_path.is_file():
        raise RuntimeError(f"missing locked artifact: {path.name}")
    fields = hash_path.read_text(encoding="utf-8").strip().split()
    actual = sha256(path)
    if len(fields) != 2 or fields[0] != actual or fields[1] != path.name:
        raise RuntimeError(f"invalid sidecar: {path.name}")
    return json.loads(path.read_text(encoding="utf-8")), actual


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def implementation_paths() -> dict[str, Path]:
    return {
        "contract": CONTRACT_PATH,
        "engine": ENGINE_PATH,
        "metrics": METRICS_PATH,
        "adapter": ADAPTER_PATH,
        "renderer": RENDERER_PATH,
        "orchestrator": ORCHESTRATOR_PATH,
        "engine_test": ENGINE_TEST_PATH,
        "research_test": RESEARCH_TEST_PATH,
        "renderer_test": RENDERER_TEST_PATH,
        "adapter_test": ADAPTER_TEST_PATH,
        "harness_test": HARNESS_TEST_PATH,
        "fair_test": FAIR_TEST_PATH,
        "metrics_test": METRICS_TEST_PATH,
    }


def current_pins() -> dict[str, dict[str, str]]:
    return {
        label: {"path": str(path), "sha256": sha256(path)}
        for label, path in implementation_paths().items()
    }


def assert_pins(pins: dict[str, dict[str, str]]) -> None:
    if current_pins() != pins:
        raise RuntimeError("implementation pin drift")


def load_runtime() -> tuple[ModuleType, ModuleType, ModuleType, ModuleType, Any]:
    engine = load_module(ENGINE_PATH, "hype_wtl_engine_runtime")
    risk = load_module(METRICS_PATH, "hype_wtl_metrics_runtime")
    adapter = load_module(ADAPTER_PATH, "hype_wtl_adapter_runtime")
    renderer = load_module(RENDERER_PATH, "hype_wtl_renderer_runtime")
    return engine, risk, adapter, renderer, adapter.load_context()


def run_preflight() -> dict[str, Any]:
    if EXPECTED_TEST_COUNT <= 0:
        raise RuntimeError("EXPECTED_TEST_COUNT is not frozen")
    command = [str(ROOT / ".venv/bin/pytest"), "-q", *map(str, TEST_PATHS)]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
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
    return (
        STAGE_A_PATH,
        STAGE_B_PATH,
        STAGE_C_PATH,
        CHAMPION_PATH,
        LEVERAGE_PATH,
        HOLDOUT_LOCK_PATH,
        HOLDOUT_PATH,
        FINAL_PATH,
        HTML_PATH,
    )


def engine_start(window: tuple[int, int]) -> int:
    return window[0] if window[0] == 0 else window[0] + 1


def normalize_metrics(raw: Any, replay: Any) -> dict[str, Any]:
    metrics = raw.metrics
    return {
        "start_ts": metrics["start_ts"],
        "end_ts": metrics["end_ts"],
        "days": metrics["days"],
        "equity_multiple": metrics["equity_multiple"],
        "net_return_pct": metrics["net_return_pct"],
        "chronological_1h_mdd_pct": replay.chronological_1h_mdd_pct,
        "chronological_worst_ts": replay.worst_ts,
        "chronological_worst_trade_index": replay.worst_trade_index,
        "daily_extreme_mdd_pct": metrics["max_drawdown_pct"],
        "closed_trades": metrics["closed_trades"],
        "long_trades": metrics["long_trades"],
        "short_trades": metrics["short_trades"],
        "win_rate": metrics["win_rate"],
        "profit_factor": metrics["profit_factor"],
        "turnover_multiple": metrics["turnover_multiple"],
        "cost_pct_initial": metrics["cost_pct_initial"],
        "funding_pct_initial": metrics["funding_pct_initial"],
        "max_intraday_leverage": metrics["max_intraday_leverage"],
        "max_marked_leverage": replay.max_marked_leverage,
        "bankrupt_intraday": metrics["bankrupt_intraday"],
    }


def economic_trades(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = (
        "side",
        "entry_ts",
        "exit_ts",
        "entry_price",
        "exit_price",
        "entry_leverage",
        "exit_reason",
        "net_return",
        "net_pnl",
    )
    return [
        {key: trade.get(key, 1.0 if key == "entry_leverage" else None) for key in fields}
        for trade in trades
    ]


def economic_path(path: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = ("ts", "pre_action_equity", "post_action_equity", "close_equity", "position", "action")
    return [{key: row.get(key) for key in fields} for row in path]


def run_one(
    *,
    engine: ModuleType,
    risk: ModuleType,
    adapter: ModuleType,
    context: Any,
    window: tuple[int, int],
    config: Any | None,
    slippage: float = BASE_SLIPPAGE,
    retain: bool = False,
    leverage_spec: Any | None = None,
    include_funding: bool = True,
) -> dict[str, Any]:
    start = engine_start(window)
    if config is None:
        if leverage_spec is not None or not include_funding:
            raise ValueError("exact control supports only frozen 1x funding")
        raw = adapter.run_v4(start, window[1], slippage=slippage, retain=retain)
        source_hash = "exact-v4-adapter"
        entry_events: list[dict[str, Any]] = []
        leverage_events: list[dict[str, Any]] = []
        counts: dict[str, int] = {}
        arm_id = "C000_EXACT_V4"
    else:
        result = engine.run_variant(
            context,
            config,
            start_index=start,
            terminal_index=window[1],
            slippage=slippage,
            include_funding=include_funding,
            retain=retain,
            leverage_spec=leverage_spec,
        )
        raw = result.raw
        source_hash = result.source_sha256
        entry_events = result.entry_events
        leverage_events = result.leverage_events
        counts = result.activation_counts
        arm_id = config.arm_id
    replay = risk.replay_chronological_1h(
        context,
        raw,
        slippage=slippage,
        include_funding=include_funding,
        retain_points=retain,
    )
    if not all(replay.parity.values()) or bool(raw.metrics["bankrupt_intraday"]):
        raise RuntimeError(f"ledger/solvency failure: {arm_id}")
    payload = {
        "status": "PASS",
        "arm_id": arm_id,
        "requested_window": window,
        "engine_window": (start, window[1]),
        "slippage": slippage,
        "include_funding": include_funding,
        "leverage_spec": asdict(leverage_spec) if leverage_spec else None,
        "metrics": normalize_metrics(raw, replay),
        "replay_parity": replay.parity,
        "source_sha256": source_hash,
        "activation_counts": counts,
        "entry_events": entry_events,
        "leverage_events": leverage_events,
        "trades_sha256": canonical_hash(economic_trades(raw.trades)),
        "path_sha256": canonical_hash(economic_path(raw.path)) if retain else None,
    }
    if retain:
        payload.update(
            {
                "trades": raw.trades,
                "path": raw.path,
                "chronological_points": [asdict(point) for point in replay.points],
            }
        )
    return payload


def safe_run(**kwargs: Any) -> dict[str, Any]:
    try:
        return run_one(**kwargs)
    except Exception as exc:  # Every failure row is evidence.
        return {
            "status": "ERROR",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "requested_window": kwargs.get("window"),
            "arm_id": getattr(kwargs.get("config"), "arm_id", "C000_EXACT_V4"),
        }


def compare(candidate: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    return_delta = float(candidate["net_return_pct"]) - float(control["net_return_pct"])
    mdd_delta = float(candidate["chronological_1h_mdd_pct"]) - float(control["chronological_1h_mdd_pct"])
    daily_delta = float(candidate["daily_extreme_mdd_pct"]) - float(control["daily_extreme_mdd_pct"])
    return {
        "return_delta_pp": return_delta,
        "chronological_mdd_delta_pp": mdd_delta,
        "daily_extreme_mdd_delta_pp": daily_delta,
        "return_higher": return_delta > 0.0,
        "mdd_smaller": mdd_delta > 0.0,
        "material": return_delta >= MATERIAL_RETURN_PP or mdd_delta >= MATERIAL_MDD_PP,
        "double_worse": return_delta < 0.0 and mdd_delta < 0.0,
        "daily_double_worse": return_delta < 0.0 and daily_delta < 0.0,
    }


def aggregate_folds(folds: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = [row["metrics"] for row in folds]
    equity = math.prod(float(row["equity_multiple"]) for row in metrics)
    return {
        "equity_multiple": equity,
        "net_return_pct": (equity - 1.0) * 100.0,
        "chronological_1h_mdd_pct": min(float(row["chronological_1h_mdd_pct"]) for row in metrics),
        "daily_extreme_mdd_pct": min(float(row["daily_extreme_mdd_pct"]) for row in metrics),
        "closed_trades": sum(int(row["closed_trades"]) for row in metrics),
        "long_trades": sum(int(row["long_trades"]) for row in metrics),
        "short_trades": sum(int(row["short_trades"]) for row in metrics),
        "bankrupt_intraday": any(bool(row["bankrupt_intraday"]) for row in metrics),
    }


def module_family(config: Any) -> str:
    modules = config.enabled_modules()
    if len(modules) != 1:
        raise ValueError("Stage A config must have exactly one module")
    return modules[0]


def module_active(module: str, counts: dict[str, int]) -> bool:
    mapping = {
        "entry": "entry_filter_reject",
        "long_exit": "long_trail_exit",
        "short_exit": "short_trail_exit",
        "short_rsi": "short_rsi_exit",
    }
    return int(counts.get(mapping[module], 0)) > 0


def metrics_equal(left: dict[str, Any], right: dict[str, Any], tolerance: float = 1e-12) -> bool:
    keys = ("equity_multiple", "net_return_pct", "chronological_1h_mdd_pct", "closed_trades")
    return all(math.isclose(float(left[key]), float(right[key]), rel_tol=0.0, abs_tol=tolerance) for key in keys)


def stage_manifest() -> dict[str, Any]:
    if MANIFEST_PATH.exists() or sidecar(MANIFEST_PATH).exists():
        raise RuntimeError("manifest exists")
    present = [path.name for path in downstream_paths() if path.exists() or sidecar(path).exists()]
    if present:
        raise RuntimeError(f"early downstream artifacts: {present}")
    preflight = run_preflight()
    pins = current_pins()
    engine, risk, adapter, _, context = load_runtime()
    grid = engine.stage_a_configs()
    if len(grid) != 555 or len(engine.leverage_specs()) != 9:
        raise RuntimeError("frozen grid drift")
    full = adapter.verify_full_baseline(retain=True)
    replay = risk.replay_chronological_1h(context, full)
    audit = context.market.audit
    blockers = (
        int(audit["trusted_hourly_audit"]["blocker_count"])
        + int(audit["trusted_funding_audit"]["blocker_count"])
        + int(context.book.quality["daily"]["blocker_count"])
    )
    if blockers:
        raise RuntimeError("market audit blocker")
    payload = {
        "schema": "hype-wtl-manifest-v1",
        "status": "PASS",
        "research_state": "explore / not promoted / not live-ready",
        "pins": pins,
        "preflight": preflight,
        "market_audit": audit,
        "book_quality": context.book.quality,
        "windows": {"D": D_FULL, "V_exposed": V_FULL, "rolling": ROLLING_FOLDS, "H_final": H_EVAL},
        "stage_a_count": len(grid),
        "stage_a_grid": [row.canonical() for row in grid],
        "stage_a_hashes": {row.arm_id: engine.config_sha256(row) for row in grid},
        "max_combo_count": 624,
        "leverage_grid": [asdict(row) for row in engine.leverage_specs()],
        "exact_v4_full_anchor": {
            "metrics": full.metrics,
            "chronological_replay": replay.canonical(),
            "trades_sha256": canonical_hash(full.trades),
        },
        "wtl_candidate_h_unrevealed": True,
    }
    assert_pins(pins)
    write_locked(MANIFEST_PATH, payload)
    return payload


def assert_manifest() -> dict[str, Any]:
    manifest, _ = read_locked(MANIFEST_PATH)
    if manifest.get("status") != "PASS" or not manifest.get("wtl_candidate_h_unrevealed"):
        raise RuntimeError("invalid manifest")
    assert_pins(manifest["pins"])
    return manifest


def _stage_a_key(row: dict[str, Any]) -> tuple[Any, ...]:
    comparisons = (row["comparisons"]["D"], row["comparisons"]["V"])
    return (
        -sum(item["return_higher"] and item["mdd_smaller"] for item in comparisons),
        -min(item["return_delta_pp"] for item in comparisons),
        -min(item["chronological_mdd_delta_pp"] for item in comparisons),
        -row["compound_equity"],
        row["arm_id"],
    )


def stage_a() -> dict[str, Any]:
    manifest = assert_manifest()
    if STAGE_A_PATH.exists() or sidecar(STAGE_A_PATH).exists():
        raise RuntimeError("Stage A exists")
    if any(path.exists() for path in downstream_paths()[1:]):
        raise RuntimeError("downstream artifact exists")
    engine, risk, adapter, _, context = load_runtime()
    controls = {
        "D": run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=D_FULL, config=None),
        "V": run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=V_FULL, config=None),
    }
    rows = []
    for index, config in enumerate(engine.stage_a_configs(), 1):
        domains = {
            "D": safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=D_FULL, config=config),
            "V": safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=V_FULL, config=config),
        }
        row: dict[str, Any] = {
            "arm_id": config.arm_id,
            "family": module_family(config),
            "config": config.canonical(),
            "config_sha256": engine.config_sha256(config),
            "domains": domains,
            "status": "ERROR" if any(item["status"] != "PASS" for item in domains.values()) else "PASS",
        }
        if row["status"] == "PASS":
            row["comparisons"] = {
                label: compare(domains[label]["metrics"], controls[label]["metrics"])
                for label in ("D", "V")
            }
            active = any(module_active(row["family"], domains[label]["activation_counts"]) for label in ("D", "V"))
            changed = any(domains[label]["trades_sha256"] != controls[label]["trades_sha256"] for label in ("D", "V"))
            not_double = all(not item["double_worse"] for item in row["comparisons"].values())
            row["compound_equity"] = math.prod(float(domains[label]["metrics"]["equity_multiple"]) for label in ("D", "V"))
            row["eligible"] = active and changed and not_double
            row["checks"] = {"active": active, "economic_path_changed": changed, "both_domains_not_double_worse": not_double}
        else:
            row.update({"comparisons": {}, "compound_equity": None, "eligible": False, "checks": {}})
        rows.append(row)
        if index % 25 == 0:
            print(f"WTL Stage A {index}/555", file=sys.stderr, flush=True)
    shortlists: dict[str, list[str]] = {}
    for family in ("entry", "long_exit", "short_exit", "short_rsi"):
        eligible = [row for row in rows if row["family"] == family and row["eligible"]]
        shortlists[family] = [row["arm_id"] for row in sorted(eligible, key=_stage_a_key)[:8]]
    payload = {
        "schema": "hype-wtl-stage-a-v1",
        "status": "PASS" if any(shortlists.values()) else "FAIL",
        "manifest_sha256": sha256(MANIFEST_PATH),
        "controls": controls,
        "trial_count": len(rows),
        "error_count": sum(row["status"] == "ERROR" for row in rows),
        "shortlists": shortlists,
        "rows": rows,
        "h_accessed": False,
    }
    assert_pins(manifest["pins"])
    write_locked(STAGE_A_PATH, payload)
    return payload


def _stage_b_key(row: dict[str, Any]) -> tuple[Any, ...]:
    fold_comparisons = row["fold_comparisons"]
    return (
        -sum(not item["double_worse"] for item in fold_comparisons),
        -row["rolling_comparison"]["return_delta_pp"],
        -row["rolling_comparison"]["chronological_mdd_delta_pp"],
        -min(row["full_comparisons"][label]["return_delta_pp"] for label in ("D", "V")),
        -min(row["full_comparisons"][label]["chronological_mdd_delta_pp"] for label in ("D", "V")),
        row["arm_id"],
    )


def stage_b() -> dict[str, Any]:
    manifest = assert_manifest()
    stage_a_payload, _ = read_locked(STAGE_A_PATH)
    if stage_a_payload.get("status") != "PASS":
        raise RuntimeError("Stage A did not pass")
    if STAGE_B_PATH.exists() or sidecar(STAGE_B_PATH).exists():
        raise RuntimeError("Stage B exists")
    if any(path.exists() for path in downstream_paths()[2:]):
        raise RuntimeError("downstream artifact exists")
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
    rows = []
    for family, arm_ids in stage_a_payload["shortlists"].items():
        for arm_id in arm_ids:
            config = engine.config_from_dict(by_id[arm_id]["config"])
            stress = {
                "D": safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=D_FULL, config=config, slippage=STRESS_SLIPPAGE),
                "V": safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=V_FULL, config=config, slippage=STRESS_SLIPPAGE),
            }
            folds = [safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=fold, config=config) for fold in ROLLING_FOLDS]
            status = "PASS" if all(item["status"] == "PASS" for item in (*stress.values(), *folds)) else "ERROR"
            row: dict[str, Any] = {
                "arm_id": arm_id,
                "family": family,
                "config": config.canonical(),
                "base": by_id[arm_id]["domains"],
                "stress": stress,
                "folds": folds,
                "status": status,
            }
            if status == "PASS":
                row["rolling"] = aggregate_folds(folds)
                row["rolling_comparison"] = compare(row["rolling"], controls["rolling"])
                row["fold_comparisons"] = [compare(item["metrics"], base["metrics"]) for item, base in zip(folds, controls["folds"])]
                row["full_comparisons"] = {
                    label: compare(row["base"][label]["metrics"], controls[label]["metrics"])
                    for label in ("D", "V")
                }
                row["eligible"] = all(not compare(stress[label]["metrics"], controls[f"stress_{label}"]["metrics"])["double_worse"] for label in ("D", "V"))
            else:
                row["eligible"] = False
            rows.append(row)
    survivors: dict[str, list[str]] = {}
    survivor_specs: dict[str, list[dict[str, Any]]] = {}
    for family in ("entry", "long_exit", "short_exit", "short_rsi"):
        ranked = sorted([row for row in rows if row["family"] == family and row["eligible"]], key=_stage_b_key)[:4]
        survivors[family] = [row["arm_id"] for row in ranked]
        key = family if family != "short_rsi" else "short_rsi"
        survivor_specs[family] = [row["config"][key] for row in ranked]
    payload = {
        "schema": "hype-wtl-stage-b-v1",
        "status": "PASS" if any(survivors.values()) else "FAIL",
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


def strict_domain_gate(
    candidate: dict[str, Any],
    control: dict[str, Any],
) -> dict[str, Any]:
    comparison = compare(candidate["metrics"], control["metrics"])
    return {
        "status": "PASS" if comparison["return_higher"] and comparison["mdd_smaller"] and comparison["material"] else "FAIL",
        "comparison": comparison,
    }


def prepass_gate(row: dict[str, Any], controls: dict[str, Any]) -> dict[str, Any]:
    if any(row[label]["status"] != "PASS" for label in ("D", "V")):
        return {"status": "ERROR", "checks": {}}
    domains = {label: strict_domain_gate(row[label], controls[label]) for label in ("D", "V")}
    checks = {
        "D_strict_dual": domains["D"]["status"] == "PASS",
        "V_strict_dual": domains["V"]["status"] == "PASS",
        "D_path_changed": row["D"]["trades_sha256"] != controls["D"]["trades_sha256"],
        "V_path_changed": row["V"]["trades_sha256"] != controls["V"]["trades_sha256"],
        "D_trade_floor": int(row["D"]["metrics"]["closed_trades"]) >= 8,
        "D_long_floor": int(row["D"]["metrics"]["long_trades"]) >= 3,
        "D_short_floor": int(row["D"]["metrics"]["short_trades"]) >= 3,
        "V_candidate_floor": int(row["V"]["metrics"]["closed_trades"]) >= 3,
        "V_control_floor": int(controls["V"]["metrics"]["closed_trades"]) >= 3,
        "V_exit_activation": sum(int(row["V"]["activation_counts"].get(key, 0)) for key in ("long_trail_exit", "short_trail_exit", "short_rsi_exit")) > 0,
    }
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "domains": domains}


def _combo_key(row: dict[str, Any]) -> tuple[Any, ...]:
    gates = row["prepass_gate"]["domains"]
    config = row["config"]
    enabled = sum(
        (
            config["entry"]["kind"] != "off",
            config["long_exit"]["mode"] != "off",
            config["short_exit"]["mode"] != "off",
            config["short_rsi"]["days"] > 0,
        )
    )
    return (
        -min(gates[label]["comparison"]["return_delta_pp"] for label in ("D", "V")),
        -min(gates[label]["comparison"]["chronological_mdd_delta_pp"] for label in ("D", "V")),
        enabled,
        row["arm_id"],
    )


def deep_gate(row: dict[str, Any], controls: dict[str, Any]) -> dict[str, Any]:
    stress_comparisons = {
        label: compare(row["stress"][label]["metrics"], controls[f"stress_{label}"]["metrics"])
        for label in ("D", "V")
    }
    fold_comparisons = [compare(item["metrics"], base["metrics"]) for item, base in zip(row["folds"], controls["folds"])]
    rolling = aggregate_folds(row["folds"])
    rolling_comparison = compare(rolling, controls["rolling"])
    checks = {
        "stress_not_double_worse": all(not item["double_worse"] for item in stress_comparisons.values()),
        "funding_off_solved": all(row["funding_off"][label]["status"] == "PASS" for label in ("D", "V")),
        "rolling_strict_dual": rolling_comparison["return_higher"] and rolling_comparison["mdd_smaller"] and rolling_comparison["material"],
        "folds_not_double_worse": all(not item["double_worse"] for item in fold_comparisons),
        "four_active_fold_pairs": sum(int(item["metrics"]["closed_trades"]) > 0 and int(base["metrics"]["closed_trades"]) > 0 for item, base in zip(row["folds"], controls["folds"])) >= 4,
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "stress_comparisons": stress_comparisons,
        "fold_comparisons": fold_comparisons,
        "rolling": rolling,
        "rolling_comparison": rolling_comparison,
    }


def _deep_key(row: dict[str, Any]) -> tuple[Any, ...]:
    base = _combo_key(row)
    deep = row["deep_gate"]
    return (
        base[0],
        base[1],
        -deep["rolling_comparison"]["return_delta_pp"],
        -deep["rolling_comparison"]["chronological_mdd_delta_pp"],
        base[2],
        sum(int(row[label]["metrics"]["closed_trades"]) for label in ("D", "V")),
        row["arm_id"],
    )


def _ablation_gate(
    *,
    config: Any,
    candidate: dict[str, Any],
    leave_one_out: list[dict[str, Any]],
    neighbors: list[dict[str, Any]],
    controls: dict[str, Any],
) -> dict[str, Any]:
    modules = config.enabled_modules()
    by_module = {row["module"]: row for row in leave_one_out}
    activation = {
        module: any(module_active(module, candidate[label]["activation_counts"]) for label in ("D", "V"))
        for module in modules
    }
    path_change = {
        module: any(
            by_module[module][label]["trades_sha256"] != candidate[label]["trades_sha256"]
            for label in ("D", "V")
        )
        for module in modules
    }
    negative_module = {}
    for module in modules:
        negative_module[module] = all(
            (comparison := compare(by_module[module][label]["metrics"], candidate[label]["metrics"]))["return_higher"]
            and comparison["mdd_smaller"]
            for label in ("D", "V")
        )
    exit_total = sum(
        int(candidate[label]["activation_counts"].get(key, 0))
        for label in ("D", "V")
        for key in ("long_trail_exit", "short_trail_exit", "short_rsi_exit")
    )
    v_exit = sum(
        int(candidate["V"]["activation_counts"].get(key, 0))
        for key in ("long_trail_exit", "short_trail_exit", "short_rsi_exit")
    )
    neighbor_pass = any(
        row["D"]["status"] == "PASS"
        and row["V"]["status"] == "PASS"
        and prepass_gate(row, controls)["status"] == "PASS"
        for row in neighbors
    )
    checks = {
        "all_modules_active": all(activation.values()),
        "all_leave_one_out_paths_change": all(path_change.values()),
        "no_module_dominates_when_disabled": not any(negative_module.values()),
        "at_least_two_exits": exit_total >= 2,
        "v_exit_present": v_exit >= 1,
        "adjacent_neighbor_pass": neighbor_pass,
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "activation": activation,
        "path_change": path_change,
        "disabled_module_dominates": negative_module,
        "exit_total": exit_total,
        "v_exit_total": v_exit,
    }


def stage_c() -> dict[str, Any]:
    manifest = assert_manifest()
    stage_b_payload, _ = read_locked(STAGE_B_PATH)
    if stage_b_payload.get("status") != "PASS":
        raise RuntimeError("Stage B did not pass")
    if STAGE_C_PATH.exists() or sidecar(STAGE_C_PATH).exists() or CHAMPION_PATH.exists():
        raise RuntimeError("Stage C exists")
    if any(path.exists() for path in downstream_paths()[4:]):
        raise RuntimeError("downstream artifact exists")
    engine, risk, adapter, _, context = load_runtime()
    specs = stage_b_payload["survivor_specs"]
    combos = engine.build_combo_configs(
        [engine.EntryFilter(**row) for row in specs["entry"]],
        [engine.TrailExit(**row) for row in specs["long_exit"]],
        [engine.TrailExit(**row) for row in specs["short_exit"]],
        [engine.ShortRSIExit(**row) for row in specs["short_rsi"]],
    )
    if len(combos) > 624:
        raise RuntimeError("combo grid exceeds frozen maximum")
    controls = stage_b_payload["controls"]
    rows = []
    for index, config in enumerate(combos, 1):
        row = {
            "arm_id": config.arm_id,
            "config": config.canonical(),
            "config_sha256": engine.config_sha256(config),
            "D": safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=D_FULL, config=config),
            "V": safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=V_FULL, config=config),
        }
        row["prepass_gate"] = prepass_gate(row, controls)
        rows.append(row)
        if index % 25 == 0:
            print(f"WTL Stage C prepass {index}/{len(combos)}", file=sys.stderr, flush=True)
    shortlist = sorted([row for row in rows if row["prepass_gate"]["status"] == "PASS"], key=_combo_key)[:64]
    for index, row in enumerate(shortlist, 1):
        config = engine.config_from_dict(row["config"])
        row["stress"] = {
            "D": safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=D_FULL, config=config, slippage=STRESS_SLIPPAGE),
            "V": safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=V_FULL, config=config, slippage=STRESS_SLIPPAGE),
        }
        row["funding_off"] = {
            "D": safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=D_FULL, config=config, include_funding=False),
            "V": safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=V_FULL, config=config, include_funding=False),
        }
        row["folds"] = [safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=fold, config=config) for fold in ROLLING_FOLDS]
        if all(item["status"] == "PASS" for item in (*row["stress"].values(), *row["funding_off"].values(), *row["folds"])):
            row["deep_gate"] = deep_gate(row, controls)
        else:
            row["deep_gate"] = {"status": "ERROR", "checks": {}}
        print(f"WTL Stage C deep {index}/{len(shortlist)}", file=sys.stderr, flush=True)
    deep_passers = sorted([row for row in shortlist if row["deep_gate"]["status"] == "PASS"], key=_deep_key)
    all_off = engine.WTLConfig("ALL_OFF")
    all_off_evidence = {
        label: run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=window, config=all_off)
        for label, window in (("D", D_FULL), ("V", V_FULL))
    }
    all_off_parity = all(
        all_off_evidence[label]["trades_sha256"] == controls[label]["trades_sha256"]
        and metrics_equal(all_off_evidence[label]["metrics"], controls[label]["metrics"])
        for label in ("D", "V")
    )
    ablations = []
    for index, row in enumerate(deep_passers[:20], 1):
        config = engine.config_from_dict(row["config"])
        leave_one_out = []
        keep_one_only = []
        for module in config.enabled_modules():
            disabled = engine.disable_module(config, module)
            leave_one_out.append(
                {
                    "module": module,
                    "config": disabled.canonical(),
                    "D": safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=D_FULL, config=disabled),
                    "V": safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=V_FULL, config=disabled),
                }
            )
            only = engine.keep_only_module(config, module)
            keep_one_only.append(
                {
                    "module": module,
                    "config": only.canonical(),
                    "D": safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=D_FULL, config=only),
                    "V": safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=V_FULL, config=only),
                }
            )
        neighbors = []
        for neighbor in engine.adjacent_neighbors(config):
            neighbors.append(
                {
                    "arm_id": neighbor.arm_id,
                    "config": neighbor.canonical(),
                    "D": safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=D_FULL, config=neighbor),
                    "V": safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=V_FULL, config=neighbor),
                }
            )
        evidence = {
            "arm_id": row["arm_id"],
            "leave_one_out": leave_one_out,
            "keep_one_only": keep_one_only,
            "adjacent_neighbors": neighbors,
        }
        valid = all(item[label]["status"] == "PASS" for item in (*leave_one_out, *keep_one_only) for label in ("D", "V")) and all(item[label]["status"] == "PASS" for item in neighbors for label in ("D", "V"))
        evidence["gate"] = _ablation_gate(config=config, candidate=row, leave_one_out=leave_one_out, neighbors=neighbors, controls=controls) if valid and all_off_parity else {"status": "ERROR", "checks": {"all_off_parity": all_off_parity}}
        ablations.append(evidence)
        row["ablation_gate"] = evidence["gate"]
        print(f"WTL Stage C ablation {index}/{min(20, len(deep_passers))}", file=sys.stderr, flush=True)
    finalists = sorted([row for row in deep_passers[:20] if row.get("ablation_gate", {}).get("status") == "PASS"], key=_deep_key)
    champion = finalists[0] if finalists else None
    payload = {
        "schema": "hype-wtl-stage-c-v1",
        "status": "PASS" if champion else "FAIL",
        "hard_gate": "PASS" if champion else "FAIL",
        "manifest_sha256": sha256(MANIFEST_PATH),
        "stage_b_sha256": sha256(STAGE_B_PATH),
        "combo_count": len(combos),
        "prepass_pass_count": len([row for row in rows if row["prepass_gate"]["status"] == "PASS"]),
        "deep_count": len(shortlist),
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
        retained = {
            label: run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=window, config=engine.config_from_dict(champion["config"]), retain=True)
            for label, window in (("D", D_FULL), ("V", V_FULL))
        }
        assert_pins(manifest["pins"])
        write_locked(
            CHAMPION_PATH,
            {
                "schema": "hype-wtl-champion-v1",
                "arm_id": champion["arm_id"],
                "config": champion["config"],
                "config_sha256": champion["config_sha256"],
                "prepass_gate": champion["prepass_gate"],
                "deep_gate": champion["deep_gate"],
                "ablation_gate": champion["ablation_gate"],
                "retained_exposed_evidence": retained,
                "manifest_sha256": sha256(MANIFEST_PATH),
                "stage_c_sha256": stage_c_digest,
                "implementation_pins": manifest["pins"],
                "h_accessed": False,
            },
        )
    return payload


def load_champion() -> tuple[dict[str, Any], dict[str, Any], Any]:
    manifest = assert_manifest()
    stage_c_payload, _ = read_locked(STAGE_C_PATH)
    if stage_c_payload.get("status") != "PASS":
        raise RuntimeError("Stage C did not pass")
    champion, _ = read_locked(CHAMPION_PATH)
    if champion["implementation_pins"] != manifest["pins"]:
        raise RuntimeError("champion pin drift")
    engine = load_module(ENGINE_PATH, "hype_wtl_champion_engine")
    return manifest, champion, engine.config_from_dict(champion["config"])


def leverage_eligible(row: dict[str, Any], one_x: dict[str, Any], cap: float) -> bool:
    return bool(
        all(row[label]["base"]["status"] == "PASS" and float(row[label]["base"]["metrics"]["net_return_pct"]) > float(one_x[label]["metrics"]["net_return_pct"]) for label in ("D", "V"))
        and all(abs(float(row[label]["base"]["metrics"]["chronological_1h_mdd_pct"])) <= cap for label in ("D", "V"))
        and all(row[label][variant]["status"] == "PASS" for label in ("D", "V") for variant in ("base", "stress", "funding_off"))
    )


def leverage_rank(row: dict[str, Any], one_x: dict[str, Any]) -> tuple[Any, ...]:
    deltas = [float(row[label]["base"]["metrics"]["net_return_pct"]) - float(one_x[label]["metrics"]["net_return_pct"]) for label in ("D", "V")]
    compound = math.prod(float(row[label]["base"]["metrics"]["equity_multiple"]) for label in ("D", "V"))
    worst_mdd = min(float(row[label]["base"]["metrics"]["chronological_1h_mdd_pct"]) for label in ("D", "V"))
    max_leverage = max(float(row[label]["base"]["metrics"]["max_marked_leverage"]) for label in ("D", "V"))
    return (-min(deltas), -compound, -worst_mdd, max_leverage, row["spec"]["id"])


def stage_leverage() -> dict[str, Any]:
    manifest, champion, config = load_champion()
    if LEVERAGE_PATH.exists() or sidecar(LEVERAGE_PATH).exists():
        raise RuntimeError("leverage artifact exists")
    if HOLDOUT_LOCK_PATH.exists() or HOLDOUT_PATH.exists() or FINAL_PATH.exists():
        raise RuntimeError("holdout/final exists")
    engine, risk, adapter, _, context = load_runtime()
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
        row["eligible_35"] = leverage_eligible(row, one_x, 35.0)
        row["eligible_50"] = leverage_eligible(row, one_x, 50.0)
        rows.append(row)
    primary = sorted([row for row in rows if row["eligible_35"]], key=lambda row: leverage_rank(row, one_x))
    aggressive = sorted([row for row in rows if row["eligible_50"]], key=lambda row: leverage_rank(row, one_x))
    payload = {
        "schema": "hype-wtl-leverage-freeze-v1",
        "status": "PASS",
        "signal_arm_id": champion["arm_id"],
        "manifest_sha256": sha256(MANIFEST_PATH),
        "champion_sha256": sha256(CHAMPION_PATH),
        "rows": rows,
        "primary_spec_id": primary[0]["spec"]["id"] if primary else None,
        "aggressive_spec_id": aggressive[0]["spec"]["id"] if aggressive else None,
        "all_nine_frozen_before_h": len(rows) == 9,
        "h_accessed": False,
    }
    assert_pins(manifest["pins"])
    write_locked(LEVERAGE_PATH, payload)
    return payload


def final_evaluation_gate(candidate: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    if candidate.get("status") != "PASS" or control.get("status") != "PASS":
        return {"status": "ERROR", "checks": {"runs_pass": False}}
    comparison = compare(candidate["metrics"], control["metrics"])
    checks = {
        "strict_dual_dominance": comparison["return_higher"] and comparison["mdd_smaller"] and comparison["material"],
        "candidate_trade_floor": int(candidate["metrics"]["closed_trades"]) >= 3,
        "control_trade_floor": int(control["metrics"]["closed_trades"]) >= 3,
        "economic_path_changed": candidate["trades_sha256"] != control["trades_sha256"],
        "daily_stress_not_double_worse": not comparison["daily_double_worse"],
    }
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "comparison": comparison}


def stage_holdout() -> dict[str, Any]:
    manifest, champion, config = load_champion()
    leverage, _ = read_locked(LEVERAGE_PATH)
    if not leverage.get("all_nine_frozen_before_h"):
        raise RuntimeError("leverage grid is not frozen")
    if HOLDOUT_LOCK_PATH.exists() or sidecar(HOLDOUT_LOCK_PATH).exists() or HOLDOUT_PATH.exists():
        raise RuntimeError("holdout already consumed")
    if FINAL_PATH.exists() or HTML_PATH.exists():
        raise RuntimeError("final exists")
    assert_pins(manifest["pins"])
    write_locked(
        HOLDOUT_LOCK_PATH,
        {
            "schema": "hype-wtl-holdout-access-lock-v1",
            "status": "CONSUMED",
            "window": H_EVAL,
            "manifest_sha256": sha256(MANIFEST_PATH),
            "champion_sha256": sha256(CHAMPION_PATH),
            "leverage_sha256": sha256(LEVERAGE_PATH),
            "pins": manifest["pins"],
        },
    )
    engine, risk, adapter, _, context = load_runtime()
    control = safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=H_EVAL, config=None, retain=True)
    one_x = safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=H_EVAL, config=config, retain=True)
    one_x_stress = safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=H_EVAL, config=config, slippage=STRESS_SLIPPAGE)
    by_id = {spec.id: spec for spec in engine.leverage_specs()}
    leverage_rows = []
    for frozen in leverage["rows"]:
        spec = by_id[frozen["spec"]["id"]]
        leverage_rows.append(
            {
                "spec": frozen["spec"],
                "frozen_eligible_35": frozen["eligible_35"],
                "frozen_eligible_50": frozen["eligible_50"],
                "base": safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=H_EVAL, config=config, leverage_spec=spec, retain=True),
                "stress": safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=H_EVAL, config=config, leverage_spec=spec, slippage=STRESS_SLIPPAGE),
            }
        )
    gate = final_evaluation_gate(one_x, control)
    payload = {
        "schema": "hype-wtl-holdout-v1",
        "status": gate["status"],
        "hard_gate": gate["status"],
        "research_state": "explore / not promoted / not live-ready",
        "manifest_sha256": sha256(MANIFEST_PATH),
        "champion_sha256": sha256(CHAMPION_PATH),
        "leverage_sha256": sha256(LEVERAGE_PATH),
        "holdout_lock_sha256": sha256(HOLDOUT_LOCK_PATH),
        "window": H_EVAL,
        "control": control,
        "one_x": one_x,
        "one_x_stress": one_x_stress,
        "one_x_gate": gate,
        "leverage_rows": leverage_rows,
        "all_frozen_arms_evaluated_once": len(leverage_rows) == 9,
    }
    assert_pins(manifest["pins"])
    write_locked(HOLDOUT_PATH, payload)
    return payload


def frontier_row(
    identifier: str,
    kind: str,
    run: dict[str, Any],
    *,
    target_leverage: float,
    eligible_35: bool,
    eligible_50: bool,
) -> dict[str, Any]:
    if run.get("status") != "PASS":
        return {"id": identifier, "kind": kind, "status": "ERROR", "target_leverage": target_leverage}
    metrics = run["metrics"]
    return {
        "id": identifier,
        "kind": kind,
        "status": "PASS",
        "target_leverage": target_leverage,
        "max_marked_leverage": metrics["max_marked_leverage"],
        "net_return_pct": metrics["net_return_pct"],
        "chronological_1h_mdd_pct": metrics["chronological_1h_mdd_pct"],
        "daily_extreme_mdd_pct": metrics["daily_extreme_mdd_pct"],
        "closed_trades": metrics["closed_trades"],
        "bankrupt_intraday": metrics["bankrupt_intraday"],
        "frozen_eligible_35": eligible_35,
        "frozen_eligible_50": eligible_50,
    }


def stage_finalize() -> dict[str, Any]:
    manifest, champion, config = load_champion()
    holdout, _ = read_locked(HOLDOUT_PATH)
    leverage, _ = read_locked(LEVERAGE_PATH)
    if FINAL_PATH.exists() or sidecar(FINAL_PATH).exists() or HTML_PATH.exists():
        raise RuntimeError("final artifact exists")
    engine, risk, adapter, renderer, context = load_runtime()
    full_control = run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=(0, context.book.count), config=None, retain=True)
    full_one_x = run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=(0, context.book.count), config=config, retain=True)
    h_rows = [
        frontier_row("EXACT_V4_1X", "control", holdout["control"], target_leverage=1.0, eligible_35=True, eligible_50=True),
        frontier_row(f"{champion['arm_id']}_1X", "signal_1x", holdout["one_x"], target_leverage=1.0, eligible_35=holdout["one_x_gate"]["status"] == "PASS", eligible_50=holdout["one_x_gate"]["status"] == "PASS"),
    ]
    full_rows = [
        frontier_row("EXACT_V4_1X", "control", full_control, target_leverage=1.0, eligible_35=True, eligible_50=True),
        frontier_row(f"{champion['arm_id']}_1X", "signal_1x", full_one_x, target_leverage=1.0, eligible_35=holdout["one_x_gate"]["status"] == "PASS", eligible_50=holdout["one_x_gate"]["status"] == "PASS"),
    ]
    by_spec = {row["spec"]["id"]: row for row in leverage["rows"]}
    spec_objects = {spec.id: spec for spec in engine.leverage_specs()}
    full_leverage = []
    for h_row in holdout["leverage_rows"]:
        spec_id = h_row["spec"]["id"]
        frozen = by_spec[spec_id]
        spec = spec_objects[spec_id]
        h_rows.append(frontier_row(spec_id, spec.mode, h_row["base"], target_leverage=spec.value, eligible_35=frozen["eligible_35"], eligible_50=frozen["eligible_50"]))
        full_run = safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=(0, context.book.count), config=config, leverage_spec=spec)
        full_stress = safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=(0, context.book.count), config=config, leverage_spec=spec, slippage=STRESS_SLIPPAGE)
        full_leverage.append({"spec": h_row["spec"], "base": full_run, "stress": full_stress})
        full_rows.append(frontier_row(spec_id, spec.mode, full_run, target_leverage=spec.value, eligible_35=frozen["eligible_35"], eligible_50=frozen["eligible_50"]))
    valid_h = [row for row in h_rows if row.get("status") == "PASS"]
    valid_full = [row for row in full_rows if row.get("status") == "PASS"]
    caps = (20.0, 25.0, 30.0, 35.0, 40.0, 50.0)
    document, html_audit = renderer.build_document(
        title=f"HYPE 1D MA7 WTL {champion['arm_id']} vs exact V4",
        candles=renderer.candles_from_context(context),
        candidate=full_one_x,
        control=full_control,
    )
    html_record = renderer.write_locked(HTML_PATH, document)
    payload = {
        "schema": "hype-wtl-final-v1",
        "status": holdout["status"],
        "hard_gate": holdout["hard_gate"],
        "research_state": "explore / not promoted / not live-ready",
        "signal_arm_id": champion["arm_id"],
        "manifest_sha256": sha256(MANIFEST_PATH),
        "champion_sha256": sha256(CHAMPION_PATH),
        "leverage_sha256": sha256(LEVERAGE_PATH),
        "holdout_sha256": sha256(HOLDOUT_PATH),
        "html": {**html_record, "audit": html_audit},
        "h": {
            "rows": h_rows,
            "pareto_all_frozen_arms": risk.pareto_frontier(valid_h),
            "best_by_mdd_cap_all_frozen_arms": risk.best_by_mdd_caps(valid_h, caps),
        },
        "full_window": {
            "rows": full_rows,
            "pareto_all_frozen_arms": risk.pareto_frontier(valid_full),
            "best_by_mdd_cap_all_frozen_arms": risk.best_by_mdd_caps(valid_full, caps),
            "control": full_control,
            "one_x": full_one_x,
            "leverage_runs": full_leverage,
        },
        "interpretation_guard": "Only the frozen 1x H gate determines signal success; leverage does not create alpha.",
    }
    assert_pins(manifest["pins"])
    write_locked(FINAL_PATH, payload)
    return payload


def self_test() -> dict[str, Any]:
    engine = load_module(ENGINE_PATH, "hype_wtl_selftest_engine")
    assert len(engine.stage_a_configs()) == 555
    assert len(engine.build_combo_configs(engine.entry_specs()[:4], engine.trail_specs()[:4], engine.trail_specs()[4:8], engine.rsi_specs()[:4])) == 624
    assert len(engine.leverage_specs()) == 9
    assert engine_start((0, 10)) == 0 and engine_start((10, 20)) == 11
    return {"status": "PASS", "stage_a_count": 555, "max_combo_count": 624, "leverage_count": 9}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage",
        required=True,
        choices=("self-test", "manifest", "stage-a", "stage-b", "stage-c", "leverage", "holdout", "finalize"),
    )
    args = parser.parse_args()
    stages: dict[str, Callable[[], dict[str, Any]]] = {
        "self-test": self_test,
        "manifest": stage_manifest,
        "stage-a": stage_a,
        "stage-b": stage_b,
        "stage-c": stage_c,
        "leverage": stage_leverage,
        "holdout": stage_holdout,
        "finalize": stage_finalize,
    }
    print(json.dumps(canonical(stages[args.stage]()), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
