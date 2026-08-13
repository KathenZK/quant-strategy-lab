"""Stage-locked exact-V4 P/F/T repair research orchestrator."""

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
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CONTRACT_PATH = (
    FAMILY_DIR
    / "specs/hype-1d-ma7-abt-v4-pft-repair-preregistration-2026-08-09.md"
)
ENGINE_PATH = SCRIPT_DIR / "hype_1d_ma7_v4_pft_engine.py"
ADAPTER_PATH = SCRIPT_DIR / "hype_1d_ma7_v4_fair_adapter.py"
ORCHESTRATOR_PATH = Path(__file__).resolve()
ENGINE_TEST_PATH = ROOT / "tests/test_hype_1d_ma7_v4_pft_engine.py"
ADAPTER_TEST_PATH = ROOT / "tests/test_hype_1d_ma7_v4_fair_adapter.py"
HARNESS_TEST_PATH = ROOT / "tests/test_hype_1d_ma7_intent_harness.py"
FAIR_TEST_PATH = ROOT / "tests/test_hype_1d_ma7_intent_fair_metrics.py"
ORCHESTRATOR_TEST_PATH = ROOT / "tests/test_hype_1d_ma7_v4_pft_repair.py"
TEST_PATHS = (
    ENGINE_TEST_PATH,
    ADAPTER_TEST_PATH,
    HARNESS_TEST_PATH,
    FAIR_TEST_PATH,
    ORCHESTRATOR_TEST_PATH,
)
EXPECTED_TEST_COUNT = 38

PREFIX = ARTIFACT_DIR / "hype_1d_ma7_v4_pft_repair_2026-08-09"
MANIFEST_PATH = Path(f"{PREFIX}_manifest.json")
TRIALS_PATH = Path(f"{PREFIX}_development_trials.json")
DEVELOPMENT_PATH = Path(f"{PREFIX}_development.json")
CHAMPION_PATH = Path(f"{PREFIX}_champion.json")
VALIDATION_PATH = Path(f"{PREFIX}_validation.json")
HOLDOUT_PATH = Path(f"{PREFIX}_holdout.json")
FINAL_PATH = Path(f"{PREFIX}_final.json")

BOOK_COUNT = 432
D_FULL = (0, 259)
WFO_FOLDS = ((130, 173), (173, 216), (216, 259))
V_EVAL = (269, 346)
H_EVAL = (356, 432)
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
MATERIAL_RETURN_PP = 5.0
MATERIAL_MDD_PP = 2.0


def sha_path(path: Path) -> Path:
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


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            canonical(value),
            sort_keys=True,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        canonical(value),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def write_locked(path: Path, payload: Any) -> str:
    sidecar = sha_path(path)
    if path.exists() or sidecar.exists():
        raise RuntimeError(f"locked artifact already exists: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = canonical_bytes(payload)
    digest = hashlib.sha256(encoded).hexdigest()
    with path.open("xb") as handle:
        handle.write(encoded)
    with sidecar.open("x", encoding="utf-8") as handle:
        handle.write(f"{digest}  {path.name}\n")
    return digest


def read_locked(path: Path) -> tuple[dict[str, Any], str]:
    sidecar = sha_path(path)
    if not path.is_file() or not sidecar.is_file():
        raise RuntimeError(f"missing locked artifact: {path.name}")
    fields = sidecar.read_text(encoding="utf-8").strip().split()
    actual = sha256(path)
    if len(fields) != 2 or fields[0] != actual or fields[1] != path.name:
        raise RuntimeError(f"invalid sidecar for {path.name}")
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
        "adapter": ADAPTER_PATH,
        "orchestrator": ORCHESTRATOR_PATH,
        "engine_test": ENGINE_TEST_PATH,
        "adapter_test": ADAPTER_TEST_PATH,
        "harness_test": HARNESS_TEST_PATH,
        "fair_metrics_test": FAIR_TEST_PATH,
        "orchestrator_test": ORCHESTRATOR_TEST_PATH,
    }


def implementation_pins() -> dict[str, dict[str, str]]:
    return {
        label: {"path": str(path), "sha256": sha256(path)}
        for label, path in implementation_paths().items()
    }


def assert_pins(pins: dict[str, dict[str, str]]) -> None:
    current = implementation_pins()
    if current != pins:
        raise RuntimeError("implementation pin drift")


def run_preflight() -> dict[str, Any]:
    command = [
        str(ROOT / ".venv/bin/pytest"),
        "-q",
        *[str(path) for path in TEST_PATHS],
    ]
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
    status = (
        "PASS"
        if completed.returncode == 0 and passed == EXPECTED_TEST_COUNT
        else "FAIL"
    )
    record = {
        "status": status,
        "passed": passed,
        "expected": EXPECTED_TEST_COUNT,
        "returncode": completed.returncode,
        "tests": {str(path): sha256(path) for path in TEST_PATHS},
        "output_tail": output[-4000:],
    }
    if status != "PASS":
        raise RuntimeError(
            f"manifest preflight failed: expected {EXPECTED_TEST_COUNT}, got {passed}"
        )
    return record


def load_runtime() -> tuple[ModuleType, ModuleType, Any]:
    engine = load_module(ENGINE_PATH, "hype_v4_pft_engine_runtime")
    adapter = load_module(ADAPTER_PATH, "hype_v4_pft_adapter_runtime")
    return engine, adapter, adapter.load_context()


def assert_no_early_reveal() -> None:
    forbidden = (
        VALIDATION_PATH,
        HOLDOUT_PATH,
        FINAL_PATH,
        ARTIFACT_DIR
        / "hype_1d_ma7_intent_optimization_2026-08-09_validation.json",
        ARTIFACT_DIR
        / "hype_1d_ma7_intent_optimization_2026-08-09_holdout.json",
        ARTIFACT_DIR / "hype_1d_ma7_intent_optimization_2026-08-09_final.json",
    )
    present = [str(path) for path in forbidden if path.exists()]
    if present:
        raise RuntimeError(f"early V/H/final reveal detected: {present}")


def stage_manifest() -> dict[str, Any]:
    if MANIFEST_PATH.exists() or sha_path(MANIFEST_PATH).exists():
        raise RuntimeError("manifest already exists")
    assert_no_early_reveal()
    preflight = run_preflight()
    pins = implementation_pins()
    engine, adapter, context = load_runtime()
    baseline = adapter.verify_full_baseline(retain=True)
    audit = context.market.audit
    blockers = (
        int(audit["trusted_hourly_audit"]["blocker_count"])
        + int(audit["trusted_funding_audit"]["blocker_count"])
        + int(context.book.quality["daily"]["blocker_count"])
    )
    if blockers != 0 or context.book.count != BOOK_COUNT:
        raise RuntimeError("frozen market audit failed")
    if tuple(config.arm_id for config in engine.arm_configs()) != engine.ARM_ORDER:
        raise RuntimeError("frozen 8-arm order drift")
    manifest = {
        "schema": "hype-v4-pft-manifest-v1",
        "status": "PASS",
        "research_state": "explore / not promoted / not live-ready",
        "contract_sha256": sha256(CONTRACT_PATH),
        "pins": pins,
        "preflight": preflight,
        "market_audit": audit,
        "book_quality": context.book.quality,
        "windows": {
            "D": D_FULL,
            "WFO": WFO_FOLDS,
            "V": V_EVAL,
            "H": H_EVAL,
        },
        "arms": [config.canonical() for config in engine.arm_configs()],
        "arm_config_hashes": {
            config.arm_id: engine.config_sha256(config)
            for config in engine.arm_configs()
        },
        "exact_v4_full_anchor": baseline.metrics,
        "exact_v4_full_trade_hash": canonical_hash(baseline.trades),
        "no_early_reveal": True,
    }
    assert_pins(pins)
    write_locked(MANIFEST_PATH, manifest)
    return manifest


def assert_manifest() -> dict[str, Any]:
    manifest, _ = read_locked(MANIFEST_PATH)
    if manifest.get("status") != "PASS":
        raise RuntimeError("manifest is not PASS")
    assert_pins(manifest["pins"])
    return manifest


def engine_start(window: tuple[int, int]) -> int:
    return window[0] if window[0] == 0 else window[0] + 1


def normalized_metrics(raw: Any) -> dict[str, Any]:
    metrics = dict(raw.metrics)
    keys = (
        "start_ts",
        "end_ts",
        "days",
        "equity_multiple",
        "net_return_pct",
        "max_drawdown_pct",
        "closed_trades",
        "long_trades",
        "short_trades",
        "win_rate",
        "profit_factor",
        "turnover_multiple",
        "cost_pct_initial",
        "funding_pct_initial",
        "max_intraday_leverage",
        "bankrupt_intraday",
    )
    return {key: metrics.get(key) for key in keys}


def audit_ledger(raw: Any) -> dict[str, Any]:
    metrics = normalized_metrics(raw)
    numeric_gate = (
        "equity_multiple",
        "net_return_pct",
        "max_drawdown_pct",
        "turnover_multiple",
        "cost_pct_initial",
        "funding_pct_initial",
    )
    finite = all(math.isfinite(float(metrics[key])) for key in numeric_gate)
    durations = [
        (
            pd.Timestamp(trade["exit_ts"]) - pd.Timestamp(trade["entry_ts"])
        ).total_seconds()
        for trade in raw.trades
    ]
    checks = {
        "finite_gate_metrics": finite,
        "not_bankrupt": not bool(metrics["bankrupt_intraday"]),
        "trade_count_matches": int(metrics["closed_trades"]) == len(raw.trades),
        "nonnegative_holding_time": all(value >= 0.0 for value in durations),
        "terminal_flat": not raw.path or int(raw.path[-1]["position"]) == 0,
    }
    return {"status": "PASS" if all(checks.values()) else "FAIL", **checks}


def economic_trade_signatures(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = (
        "side",
        "entry_ts",
        "exit_ts",
        "entry_price",
        "exit_price",
        "exit_reason",
        "net_return",
        "net_pnl",
    )
    return [{key: trade.get(key) for key in fields} for trade in trades]


def economic_path(raw: Any) -> list[dict[str, Any]]:
    fields = (
        "ts",
        "pre_action_equity",
        "post_action_equity",
        "close_equity",
        "favorable_equity",
        "adverse_equity",
        "position",
        "action",
    )
    return [{key: row.get(key) for key in fields} for row in raw.path]


def run_one(
    *,
    engine: ModuleType,
    adapter: ModuleType,
    context: Any,
    arm_id: str,
    window: tuple[int, int],
    slippage: float,
    retain: bool,
) -> dict[str, Any]:
    start = engine_start(window)
    if arm_id == "A000_V4":
        raw = adapter.run_v4(start, window[1], slippage=slippage, retain=retain)
        source_hash = "exact-v4-adapter"
        events: list[dict[str, Any]] = []
        activation: dict[str, int] = {}
    else:
        result = engine.run_variant(
            context,
            engine.arm_config(arm_id),
            start_index=start,
            terminal_index=window[1],
            slippage=slippage,
            retain=retain,
        )
        raw = result.raw
        source_hash = result.source_sha256
        events = result.pending_events
        activation = result.activation_counts
    ledger = audit_ledger(raw)
    if ledger["status"] != "PASS":
        raise RuntimeError(f"{arm_id} ledger audit failed")
    payload = {
        "arm_id": arm_id,
        "requested_window": window,
        "engine_window": (start, window[1]),
        "slippage": slippage,
        "metrics": normalized_metrics(raw),
        "ledger_audit": ledger,
        "source_sha256": source_hash,
        "activation_counts": activation,
        "pending_events": events,
        "trades_sha256": canonical_hash(economic_trade_signatures(raw.trades)),
        "path_sha256": canonical_hash(economic_path(raw)),
    }
    if retain:
        payload["trades"] = raw.trades
        payload["path"] = raw.path
    return payload


def aggregate_folds(folds: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = [fold["metrics"] for fold in folds]
    equity = math.prod(float(item["equity_multiple"]) for item in metrics)
    return {
        "equity_multiple": equity,
        "net_return_pct": (equity - 1.0) * 100.0,
        "max_drawdown_pct": min(float(item["max_drawdown_pct"]) for item in metrics),
        "closed_trades": sum(int(item["closed_trades"]) for item in metrics),
        "long_trades": sum(int(item["long_trades"]) for item in metrics),
        "short_trades": sum(int(item["short_trades"]) for item in metrics),
        "bankrupt_intraday": any(bool(item["bankrupt_intraday"]) for item in metrics),
    }


def compare(candidate: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    return_delta = float(candidate["net_return_pct"]) - float(
        control["net_return_pct"]
    )
    mdd_delta = float(candidate["max_drawdown_pct"]) - float(
        control["max_drawdown_pct"]
    )
    return {
        "return_delta_pp": return_delta,
        "mdd_delta_pp": mdd_delta,
        "return_strictly_higher": return_delta > 0.0,
        "mdd_strictly_smaller": mdd_delta > 0.0,
        "material": return_delta >= MATERIAL_RETURN_PP
        or mdd_delta >= MATERIAL_MDD_PP,
        "double_worse": return_delta < 0.0 and mdd_delta < 0.0,
    }


def module_arm(arm_id: str, module: str) -> str:
    bits = list(arm_id[1:4])
    index = {"P": 0, "F": 1, "T": 2}[module]
    bits[index] = "0"
    target = "A" + "".join(bits)
    return next(name for name in (
        "A000_V4",
        "A001_T",
        "A010_F",
        "A011_FT",
        "A100_P",
        "A101_PT",
        "A110_PF",
        "A111_PFT",
    ) if name.startswith(target))


def enabled_modules(arm_id: str) -> list[str]:
    return [module for module, bit in zip("PFT", arm_id[1:4]) if bit == "1"]


def activation_pass(module: str, counts: dict[str, int]) -> bool:
    if module == "P":
        return int(counts.get("p_delayed_confirm", 0)) > 0
    if module == "F":
        return int(counts.get("f_reject", 0)) > 0
    if module == "T":
        return int(counts.get("t_exit", 0)) > 0
    raise ValueError(module)


def gate_trial(
    trial: dict[str, Any],
    control: dict[str, Any],
    trial_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    full_cmp = compare(trial["base_full"]["metrics"], control["base_full"]["metrics"])
    wfo_cmp = compare(trial["base_wfo"], control["base_wfo"])
    stress_full_cmp = compare(
        trial["stress_full"]["metrics"], control["stress_full"]["metrics"]
    )
    stress_wfo_cmp = compare(trial["stress_wfo"], control["stress_wfo"])
    fold_comparisons = [
        compare(item["metrics"], base["metrics"])
        for item, base in zip(trial["base_folds"], control["base_folds"])
    ]
    oat = []
    for module in enabled_modules(trial["arm_id"]):
        without = trial_by_id[module_arm(trial["arm_id"], module)]
        path_changed = (
            trial["base_full"]["trades_sha256"]
            != without["base_full"]["trades_sha256"]
            or trial["base_full"]["path_sha256"]
            != without["base_full"]["path_sha256"]
        )
        active = activation_pass(module, trial["base_full"]["activation_counts"])
        oat.append(
            {
                "module": module,
                "without_arm": without["arm_id"],
                "activation_pass": active,
                "economic_path_changed": path_changed,
                "status": "PASS" if active and path_changed else "FAIL",
            }
        )
    checks = {
        "full_dual_dominance": bool(
            full_cmp["return_strictly_higher"]
            and full_cmp["mdd_strictly_smaller"]
            and full_cmp["material"]
        ),
        "wfo_dual_dominance": bool(
            wfo_cmp["return_strictly_higher"]
            and wfo_cmp["mdd_strictly_smaller"]
            and wfo_cmp["material"]
        ),
        "stress_full_not_double_worse": not stress_full_cmp["double_worse"],
        "stress_wfo_not_double_worse": not stress_wfo_cmp["double_worse"],
        "folds_not_double_worse": all(not item["double_worse"] for item in fold_comparisons),
        "trade_floor": int(trial["base_full"]["metrics"]["closed_trades"]) >= 8,
        "short_trade_floor": int(trial["base_full"]["metrics"]["short_trades"]) >= 3,
        "wfo_trade_floor": int(trial["base_wfo"]["closed_trades"]) >= 3,
        "each_fold_trade_floor": all(
            int(item["metrics"]["closed_trades"]) >= 1 for item in trial["base_folds"]
        ),
        "module_wiring": all(item["status"] == "PASS" for item in oat),
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "full_comparison": full_cmp,
        "wfo_comparison": wfo_cmp,
        "stress_full_comparison": stress_full_cmp,
        "stress_wfo_comparison": stress_wfo_cmp,
        "fold_comparisons": fold_comparisons,
        "module_oat": oat,
    }


def rank_key(trial: dict[str, Any]) -> tuple[Any, ...]:
    gate = trial["gate"]
    worst_fold = min(item["return_delta_pp"] for item in gate["fold_comparisons"])
    return (
        -worst_fold,
        -gate["wfo_comparison"]["return_delta_pp"],
        -gate["wfo_comparison"]["mdd_delta_pp"],
        -gate["full_comparison"]["return_delta_pp"],
        -gate["full_comparison"]["mdd_delta_pp"],
        len(enabled_modules(trial["arm_id"])),
        trial["arm_id"],
    )


def stage_development() -> dict[str, Any]:
    manifest = assert_manifest()
    for path in (TRIALS_PATH, DEVELOPMENT_PATH, CHAMPION_PATH):
        if path.exists() or sha_path(path).exists():
            raise RuntimeError(f"development artifact already exists: {path.name}")
    assert_no_early_reveal()
    engine, adapter, context = load_runtime()
    trials = []
    for config in engine.arm_configs():
        arm_id = config.arm_id
        base_full = run_one(
            engine=engine,
            adapter=adapter,
            context=context,
            arm_id=arm_id,
            window=D_FULL,
            slippage=BASE_SLIPPAGE,
            retain=True,
        )
        base_folds = [
            run_one(
                engine=engine,
                adapter=adapter,
                context=context,
                arm_id=arm_id,
                window=fold,
                slippage=BASE_SLIPPAGE,
                retain=False,
            )
            for fold in WFO_FOLDS
        ]
        stress_full = run_one(
            engine=engine,
            adapter=adapter,
            context=context,
            arm_id=arm_id,
            window=D_FULL,
            slippage=STRESS_SLIPPAGE,
            retain=False,
        )
        stress_folds = [
            run_one(
                engine=engine,
                adapter=adapter,
                context=context,
                arm_id=arm_id,
                window=fold,
                slippage=STRESS_SLIPPAGE,
                retain=False,
            )
            for fold in WFO_FOLDS
        ]
        trials.append(
            {
                "arm_id": arm_id,
                "config": config.canonical(),
                "config_sha256": engine.config_sha256(config),
                "base_full": base_full,
                "base_folds": base_folds,
                "base_wfo": aggregate_folds(base_folds),
                "stress_full": stress_full,
                "stress_folds": stress_folds,
                "stress_wfo": aggregate_folds(stress_folds),
            }
        )
    trial_by_id = {trial["arm_id"]: trial for trial in trials}
    control = trial_by_id["A000_V4"]
    for trial in trials:
        trial["gate"] = (
            {"status": "CONTROL"}
            if trial["arm_id"] == "A000_V4"
            else gate_trial(trial, control, trial_by_id)
        )
    passers = [trial for trial in trials if trial["gate"]["status"] == "PASS"]
    ranked = sorted(passers, key=rank_key)
    champion = ranked[0] if ranked else None
    assert_pins(manifest["pins"])
    trials_payload = {
        "schema": "hype-v4-pft-development-trials-v1",
        "manifest_sha256": sha256(MANIFEST_PATH),
        "trial_count": len(trials),
        "trials": trials,
    }
    trials_digest = write_locked(TRIALS_PATH, trials_payload)
    development = {
        "schema": "hype-v4-pft-development-v1",
        "status": "PASS" if champion else "FAIL",
        "hard_gate": "PASS" if champion else "FAIL",
        "research_state": "explore / not promoted / not live-ready",
        "manifest_sha256": sha256(MANIFEST_PATH),
        "trials_sha256": trials_digest,
        "control": {
            "base_full": control["base_full"]["metrics"],
            "base_wfo": control["base_wfo"],
            "stress_full": control["stress_full"]["metrics"],
            "stress_wfo": control["stress_wfo"],
        },
        "passers": [trial["arm_id"] for trial in ranked],
        "champion_arm_id": champion["arm_id"] if champion else None,
        "ranking": [trial["arm_id"] for trial in ranked],
        "all_arm_summary": [
            {
                "arm_id": trial["arm_id"],
                "base_full": trial["base_full"]["metrics"],
                "base_wfo": trial["base_wfo"],
                "stress_full": trial["stress_full"]["metrics"],
                "stress_wfo": trial["stress_wfo"],
                "gate": trial["gate"],
            }
            for trial in trials
        ],
        "v_h_revealed": False,
    }
    development_digest = write_locked(DEVELOPMENT_PATH, development)
    if champion is not None:
        champion_payload = {
            "schema": "hype-v4-pft-champion-v1",
            "arm_id": champion["arm_id"],
            "config": champion["config"],
            "config_sha256": champion["config_sha256"],
            "manifest_sha256": sha256(MANIFEST_PATH),
            "trials_sha256": trials_digest,
            "development_sha256": development_digest,
            "gate": champion["gate"],
            "implementation_pins": manifest["pins"],
        }
        write_locked(CHAMPION_PATH, champion_payload)
    return development


def load_champion() -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = assert_manifest()
    development, _ = read_locked(DEVELOPMENT_PATH)
    if development.get("status") != "PASS":
        raise RuntimeError("development did not produce a champion")
    champion, _ = read_locked(CHAMPION_PATH)
    if champion["implementation_pins"] != manifest["pins"]:
        raise RuntimeError("champion pin chain drift")
    return manifest, champion


def evaluation_gate(candidate: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    comparison = compare(candidate["metrics"], control["metrics"])
    checks = {
        "dual_dominance": bool(
            comparison["return_strictly_higher"]
            and comparison["mdd_strictly_smaller"]
            and comparison["material"]
        ),
        "candidate_trade_floor": int(candidate["metrics"]["closed_trades"]) >= 3,
        "control_trade_floor": int(control["metrics"]["closed_trades"]) >= 3,
        "candidate_ledger": candidate["ledger_audit"]["status"] == "PASS",
        "control_ledger": control["ledger_audit"]["status"] == "PASS",
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "comparison": comparison,
    }


def stage_evaluation(stage: str) -> dict[str, Any]:
    manifest, champion = load_champion()
    if stage == "validation":
        window = V_EVAL
        output = VALIDATION_PATH
        if HOLDOUT_PATH.exists() or FINAL_PATH.exists():
            raise RuntimeError("downstream artifact exists before validation")
    elif stage == "holdout":
        validation, _ = read_locked(VALIDATION_PATH)
        if validation.get("status") != "PASS":
            raise RuntimeError("validation did not pass")
        window = H_EVAL
        output = HOLDOUT_PATH
        if FINAL_PATH.exists():
            raise RuntimeError("final artifact exists before holdout")
    else:
        raise ValueError(stage)
    if output.exists() or sha_path(output).exists():
        raise RuntimeError(f"one-shot {stage} already consumed")
    engine, adapter, context = load_runtime()
    control = run_one(
        engine=engine,
        adapter=adapter,
        context=context,
        arm_id="A000_V4",
        window=window,
        slippage=BASE_SLIPPAGE,
        retain=True,
    )
    candidate = run_one(
        engine=engine,
        adapter=adapter,
        context=context,
        arm_id=champion["arm_id"],
        window=window,
        slippage=BASE_SLIPPAGE,
        retain=True,
    )
    gate = evaluation_gate(candidate, control)
    payload = {
        "schema": f"hype-v4-pft-{stage}-v1",
        "status": gate["status"],
        "hard_gate": gate["status"],
        "research_state": "explore / not promoted / not live-ready",
        "manifest_sha256": sha256(MANIFEST_PATH),
        "champion_sha256": sha256(CHAMPION_PATH),
        "arm_id": champion["arm_id"],
        "window": window,
        "control": control,
        "candidate": candidate,
        "gate": gate,
    }
    assert_pins(manifest["pins"])
    write_locked(output, payload)
    return payload


def self_test() -> dict[str, Any]:
    engine = load_module(ENGINE_PATH, "hype_v4_pft_engine_self_test")
    assert len(engine.arm_configs()) == 8
    assert engine_start((0, 10)) == 0
    assert engine_start((10, 20)) == 11
    assert module_arm("A111_PFT", "P") == "A011_FT"
    assert module_arm("A111_PFT", "F") == "A101_PT"
    assert module_arm("A111_PFT", "T") == "A110_PF"
    return {"status": "PASS", "arms": 8}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage",
        required=True,
        choices=("self-test", "manifest", "development", "validation", "holdout"),
    )
    args = parser.parse_args()
    if args.stage == "self-test":
        payload = self_test()
    elif args.stage == "manifest":
        payload = stage_manifest()
    elif args.stage == "development":
        payload = stage_development()
    else:
        payload = stage_evaluation(args.stage)
    print(json.dumps(canonical(payload), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
