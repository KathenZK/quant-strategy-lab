"""Stage-locked DTEC search on frozen HYPE MA7 ABT V6 / PEHC_294."""

from __future__ import annotations

import argparse
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

ENGINE_PATH = SCRIPT_DIR / "hype_1d_ma7_v6_delayed_episode_engine.py"
ADAPTER_PATH = SCRIPT_DIR / "hype_1d_ma7_v4_fair_adapter.py"
RISK_PATH = SCRIPT_DIR / "hype_1d_ma7_trend_phase_risk_metrics.py"
PEHC_PATH = SCRIPT_DIR / "hype_1d_ma7_profit_exit_handoff_continuity_engine.py"
OAPP_PATH = SCRIPT_DIR / "hype_1d_ma7_opportunity_aware_profit_protection_engine.py"
SELF_PATH = Path(__file__).resolve()
TEST_PATHS = (
    ROOT / "tests/test_hype_1d_ma7_v6_delayed_episode_engine.py",
    ROOT / "tests/test_hype_1d_ma7_v6_delayed_episode_research.py",
    ROOT / "tests/test_hype_1d_ma7_profit_exit_handoff_continuity_engine.py",
    ROOT / "tests/test_hype_1d_ma7_opportunity_aware_profit_protection_engine.py",
    ROOT / "tests/test_hype_1d_ma7_trend_phase_risk.py",
)

PREFIX = ARTIFACT_DIR / "hype_1d_ma7_v6_delayed_episode_2026-08-10"
MANIFEST_PATH = Path(f"{PREFIX}_manifest.json")
STAGE_A_PATH = Path(f"{PREFIX}_stage_a.json")
STAGE_B_PATH = Path(f"{PREFIX}_stage_b.json")
EVALUATION_PATH = Path(f"{PREFIX}_evaluation.json")
FINAL_PATH = Path(f"{PREFIX}_final.json")

D_FULL = (0, 324)
D_BLOCKS = tuple((left, left + 54) for left in range(0, 324, 54))
EVALUATION = (324, 432)
FULL = (0, 432)
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
FORWARD_DAYS = 5
ROUNDTRIP_GUARD = 0.0028
EXPECTED_V6_EQUITY = 7.171070876096227
EXPECTED_V6_MDD = -18.391735672691034
EXPECTED_V6_TRADES = 19


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        sanitize(value), sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    if hasattr(value, "item"):
        return sanitize(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def sidecar(path: Path) -> Path:
    return Path(f"{path}.sha256")


def write_locked(path: Path, payload: dict[str, Any]) -> str:
    document = json.dumps(sanitize(payload), indent=2, sort_keys=True, allow_nan=False) + "\n"
    digest = hashlib.sha256(document.encode()).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(document)
    with sidecar(path).open("x", encoding="utf-8") as handle:
        handle.write(f"{digest}  {path.name}\n")
    return digest


def read_locked(path: Path) -> tuple[dict[str, Any], str]:
    digest = sha256(path)
    expected = sidecar(path).read_text(encoding="utf-8").split()[0]
    if digest != expected:
        raise RuntimeError(f"sidecar mismatch: {path.name}")
    return json.loads(path.read_text(encoding="utf-8")), digest


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_runtime() -> tuple[ModuleType, ModuleType, ModuleType, Any]:
    adapter = load_module(ADAPTER_PATH, "hype_dtec_adapter_runtime")
    engine = load_module(ENGINE_PATH, "hype_dtec_engine_runtime")
    risk = load_module(RISK_PATH, "hype_dtec_risk_runtime")
    return engine, risk, adapter, adapter.load_context()


def pins() -> dict[str, str]:
    paths = {
        "orchestrator": SELF_PATH,
        "engine": ENGINE_PATH,
        "adapter": ADAPTER_PATH,
        "risk": RISK_PATH,
        "pehc": PEHC_PATH,
        "oapp": OAPP_PATH,
    }
    paths.update({f"test_{index}": path for index, path in enumerate(TEST_PATHS, 1)})
    return {name: sha256(path) for name, path in paths.items()}


def assert_pins(expected: dict[str, str]) -> None:
    current = pins()
    if current != expected:
        raise RuntimeError("DTEC implementation pin drift")


def run_preflight() -> dict[str, Any]:
    command = [str(ROOT / ".venv/bin/python"), "-m", "pytest", "-q", *map(str, TEST_PATHS)]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"DTEC preflight failed:\n{completed.stdout}\n{completed.stderr}")
    return {
        "status": "PASS",
        "command": command,
        "stdout": completed.stdout.strip(),
        "test_hashes": {path.name: sha256(path) for path in TEST_PATHS},
    }


def engine_start(window: tuple[int, int]) -> int:
    return window[0] if window[0] == 0 else window[0] + 1


def normalize_metrics(raw: Any, replay: Any) -> dict[str, Any]:
    metrics = raw.metrics
    return {
        "equity_multiple": float(metrics["equity_multiple"]),
        "net_return_pct": float(metrics["net_return_pct"]),
        "chronological_1h_mdd_pct": float(replay.chronological_1h_mdd_pct),
        "daily_extreme_mdd_pct": float(metrics["max_drawdown_pct"]),
        "closed_trades": int(metrics["closed_trades"]),
        "long_trades": int(metrics["long_trades"]),
        "short_trades": int(metrics["short_trades"]),
        "win_rate": float(metrics["win_rate"]),
        "profit_factor": float(metrics["profit_factor"]),
        "turnover_multiple": float(metrics["turnover_multiple"]),
        "cost_pct_initial": float(metrics["cost_pct_initial"]),
        "funding_pct_initial": float(metrics["funding_pct_initial"]),
        "max_marked_leverage": float(replay.max_marked_leverage),
        "worst_ts": replay.worst_ts,
        "bankrupt_intraday": bool(metrics["bankrupt_intraday"]),
    }


def economic_trades(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = (
        "entry_ts",
        "exit_ts",
        "side",
        "entry_price",
        "exit_price",
        "exit_reason",
        "net_return",
        "net_pnl",
    )
    return [{field: row.get(field) for field in fields} for row in trades]


def episode_accuracy(
    events: list[dict[str, Any]],
    context: Any,
    *,
    start_index: int,
    terminal_index: int,
) -> dict[str, Any]:
    labels: list[dict[str, Any]] = []
    arms = [
        row
        for row in events
        if row.get("event") == "arm_raw_cross"
        and start_index <= int(row["signal_index"])
        and int(row["signal_index"]) + FORWARD_DAYS < terminal_index
    ]
    confirms = [
        row
        for row in events
        if row.get("event") == "confirm_delayed_episode"
        and start_index <= int(row["signal_index"])
        and int(row["signal_index"]) + FORWARD_DAYS < terminal_index
    ]
    for event in confirms:
        index = int(event["signal_index"])
        side = 1 if event["side"] == "long" else -1
        close = float(context.book.close[index])
        future = float(context.book.close[index + FORWARD_DAYS])
        direction_return = side * (future / close - 1.0)
        same_side = 0
        for offset in range(index + 1, index + FORWARD_DAYS + 1):
            offset_close = float(context.book.close[offset])
            offset_ma = float(context.features.ma7[offset])
            if math.isfinite(offset_close) and math.isfinite(offset_ma) and side * (offset_close - offset_ma) > 0.0:
                same_side += 1
        direction_hit = direction_return > ROUNDTRIP_GUARD
        persistence_hit = same_side >= 3
        labels.append(
            {
                "signal_index": index,
                "side": event["side"],
                "direction_return_5d": direction_return,
                "same_side_closes_5d": same_side,
                "direction_hit": direction_hit,
                "persistence_hit": persistence_hit,
                "trend_hit": bool(direction_hit and persistence_hit),
            }
        )

    def summary(side: str | None) -> dict[str, Any]:
        rows = labels if side is None else [row for row in labels if row["side"] == side]
        hits = sum(bool(row["trend_hit"]) for row in rows)
        return {
            "evaluable": len(rows),
            "hits": hits,
            "precision": hits / len(rows) if rows else None,
        }

    return {
        "horizon_days": FORWARD_DAYS,
        "roundtrip_guard": ROUNDTRIP_GUARD,
        "evaluable_arms": len(arms),
        "evaluable_confirms": len(labels),
        "capture_rate": len(labels) / len(arms) if arms else None,
        "combined": summary(None),
        "long": summary("long"),
        "short": summary("short"),
        "labels": labels,
    }


def run_once(
    *,
    engine: ModuleType,
    risk: ModuleType,
    context: Any,
    window: tuple[int, int],
    config: Any | None,
    slippage: float = BASE_SLIPPAGE,
    retain: bool = False,
) -> dict[str, Any]:
    start = engine_start(window)
    if config is None:
        result = engine.run_v6(
            context,
            start_index=start,
            terminal_index=window[1],
            slippage=slippage,
            retain=retain,
        )
        arm_id = "C000_EXACT_V6"
        episode_events: list[dict[str, Any]] = []
        source_sha = result.source_sha256
    else:
        result = engine.run_variant(
            context,
            config,
            start_index=start,
            terminal_index=window[1],
            slippage=slippage,
            retain=retain,
        )
        arm_id = config.arm_id
        episode_events = result.episode_events
        source_sha = result.source_sha256
    replay = risk.replay_chronological_1h(
        context,
        result.raw,
        slippage=slippage,
        retain_points=retain,
    )
    if not all(replay.parity.values()) or bool(result.raw.metrics["bankrupt_intraday"]):
        raise RuntimeError(f"ledger failure: {arm_id}")
    payload = {
        "status": "PASS",
        "arm_id": arm_id,
        "requested_window": list(window),
        "engine_window": [start, window[1]],
        "metrics": normalize_metrics(result.raw, replay),
        "accuracy": episode_accuracy(
            episode_events,
            context,
            start_index=start,
            terminal_index=window[1],
        ),
        "activation_counts": dict(result.activation_counts),
        "episode_events": episode_events,
        "handoff_events": list(result.handoff_events),
        "source_sha256": source_sha,
        "trades_sha256": canonical_hash(economic_trades(result.raw.trades)),
    }
    if retain:
        payload["trades"] = list(result.raw.trades)
        payload["path"] = list(result.raw.path)
        payload["replay"] = replay.canonical()
    return payload


def safe(call: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        return call()
    except Exception as exc:  # noqa: BLE001 - every trial error is retained
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
        "dual_improvement": return_delta > 0.0 and mdd_delta > 0.0,
        "double_worse": return_delta < 0.0 and mdd_delta < 0.0,
        "material": return_delta >= 5.0 or mdd_delta >= 2.0,
    }


def aggregate_blocks(rows: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = [row["metrics"] for row in rows]
    equity = math.prod(float(row["equity_multiple"]) for row in metrics)
    return {
        "equity_multiple": equity,
        "net_return_pct": (equity - 1.0) * 100.0,
        "chronological_1h_mdd_pct": min(float(row["chronological_1h_mdd_pct"]) for row in metrics),
        "closed_trades": sum(int(row["closed_trades"]) for row in metrics),
        "long_trades": sum(int(row["long_trades"]) for row in metrics),
        "short_trades": sum(int(row["short_trades"]) for row in metrics),
    }


def config_complexity(config: dict[str, Any]) -> tuple[Any, ...]:
    rows = [row for row in (config.get("long"), config.get("short")) if row is not None]
    return (
        sum(int(row["persistence_days"]) for row in rows),
        sum(int(row["slope_lookback"]) for row in rows),
        sum(float(row["slope_min_atr"]) for row in rows),
        sum(float(row["max_distance_atr"]) for row in rows),
        sum(99 if int(row["max_age_days"]) == 0 else int(row["max_age_days"]) for row in rows),
    )


def precision_value(run: dict[str, Any], side: str | None = None) -> float:
    key = side if side is not None else "combined"
    value = run["accuracy"][key]["precision"]
    return -1.0 if value is None else float(value)


def a1_rank(row: dict[str, Any], side: str) -> tuple[Any, ...]:
    compare = row["comparison"]
    return (
        -int(bool(compare.get("dual_improvement"))),
        -precision_value(row["run"], side),
        -float(compare.get("return_delta_pp", -math.inf)),
        -float(compare.get("mdd_delta_pp", -math.inf)),
        config_complexity(row["config"]),
        row["arm_id"],
    )


def a2_rank(row: dict[str, Any], side: str) -> tuple[Any, ...]:
    block_comparisons = row["block_comparisons"]
    full = row["full_comparison"]
    wfo = row["wfo_comparison"]
    no_double_worse = not full["double_worse"] and not wfo["double_worse"]
    worst_return = min(float(item["return_delta_pp"]) for item in block_comparisons)
    return (
        -int(no_double_worse),
        -precision_value(row["full"], side),
        -worst_return,
        -float(wfo["return_delta_pp"]),
        -float(wfo["mdd_delta_pp"]),
        config_complexity(row["config"]),
        row["arm_id"],
    )


def stage_b_gate(row: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    full = row["full_comparison"]
    wfo = row["wfo_comparison"]
    stress = row["stress_comparison"]
    accuracy = row["full"]["accuracy"]
    blocks = row["blocks"]
    block_comparisons = row["block_comparisons"]
    active_blocks = sum(
        int(block["accuracy"]["combined"]["evaluable"] > 0) for block in blocks
    )
    counts = row["full"]["activation_counts"]
    control_counts = control["full"]["activation_counts"]
    checks = {
        "d_full_dual_improvement": bool(full["dual_improvement"]),
        "d_wfo_dual_improvement": bool(wfo["dual_improvement"]),
        "material": bool(full["material"] or wfo["material"]),
        "stress_not_double_worse": not bool(stress["double_worse"]),
        "combined_evaluable_ge_4": int(accuracy["combined"]["evaluable"]) >= 4,
        "long_evaluable_ge_2": int(accuracy["long"]["evaluable"]) >= 2,
        "short_evaluable_ge_2": int(accuracy["short"]["evaluable"]) >= 2,
        "combined_precision_ge_055": precision_value(row["full"]) >= 0.55,
        "long_precision_ge_050": precision_value(row["full"], "long") >= 0.50,
        "short_precision_ge_050": precision_value(row["full"], "short") >= 0.50,
        "active_blocks_ge_4": active_blocks >= 4,
        "blocks_not_double_worse": all(not item["double_worse"] for item in block_comparisons),
        "economic_path_changed": row["full"]["trades_sha256"] != control["full"]["trades_sha256"],
        "v6_long_trail_wired": int(counts.get("long_trail_exit", 0)) > 0 if int(control_counts.get("long_trail_exit", 0)) > 0 else True,
        "v6_short_rsi_wired": int(counts.get("short_rsi_exit", 0)) > 0 if int(control_counts.get("short_rsi_exit", 0)) > 0 else True,
        "v6_shadow_wired": int(counts.get("shadow_start", 0)) > 0 if int(control_counts.get("shadow_start", 0)) > 0 else True,
        "nonbankrupt": not bool(row["full"]["metrics"]["bankrupt_intraday"]),
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "active_blocks": active_blocks,
    }


def b_rank(row: dict[str, Any]) -> tuple[Any, ...]:
    worst_return = min(float(item["return_delta_pp"]) for item in row["block_comparisons"])
    return (
        -worst_return,
        -float(row["wfo_comparison"]["mdd_delta_pp"]),
        -float(row["full_comparison"]["return_delta_pp"]),
        -precision_value(row["full"]),
        config_complexity(row["config"]),
        row["arm_id"],
    )


def stage_manifest() -> dict[str, Any]:
    if MANIFEST_PATH.exists() or sidecar(MANIFEST_PATH).exists():
        raise RuntimeError("DTEC manifest already exists")
    implementation_pins = pins()
    preflight = run_preflight()
    engine, risk, _, context = load_runtime()
    v6 = run_once(engine=engine, risk=risk, context=context, window=FULL, config=None, retain=True)
    metrics = v6["metrics"]
    if not math.isclose(metrics["equity_multiple"], EXPECTED_V6_EQUITY, rel_tol=1e-12, abs_tol=1e-12):
        raise RuntimeError("V6 equity anchor drift")
    if not math.isclose(metrics["chronological_1h_mdd_pct"], EXPECTED_V6_MDD, rel_tol=1e-12, abs_tol=1e-12):
        raise RuntimeError("V6 MDD anchor drift")
    if metrics["closed_trades"] != EXPECTED_V6_TRADES:
        raise RuntimeError("V6 trade-count anchor drift")
    off = run_once(
        engine=engine,
        risk=risk,
        context=context,
        window=FULL,
        config=engine.DTECConfig("DTEC_OFF"),
        retain=True,
    )
    parity = {
        "metrics": off["metrics"] == v6["metrics"],
        "trades": off["trades"] == v6["trades"],
        "path": off["path"] == v6["path"],
        "handoff_accept": off["activation_counts"].get("handoff_accept") == 5,
        "episode_events_empty": len(off["episode_events"]) == 0,
    }
    if not all(parity.values()):
        raise RuntimeError(f"DTEC-off V6 parity failed: {parity}")
    payload = {
        "schema": "hype-v6-dtec-manifest-v1",
        "status": "PASS",
        "research_state": "all 432d researcher-exposed / explore / not promoted / not live-ready",
        "pins": implementation_pins,
        "preflight": preflight,
        "market_audit": context.market.audit,
        "book_quality": context.book.quality,
        "windows": {"D": D_FULL, "D_blocks": D_BLOCKS, "evaluation": EVALUATION, "full": FULL},
        "grid": {
            "long_count": len(engine.single_side_configs(1)),
            "short_count": len(engine.single_side_configs(-1)),
            "stage_a2_per_side": 24,
            "stage_b_parents_per_side": 4,
            "stage_b_combinations": 16,
        },
        "exact_v6_anchor": v6,
        "dtec_off_parity": parity,
        "evaluation_not_accessed": True,
    }
    assert_pins(implementation_pins)
    write_locked(MANIFEST_PATH, payload)
    return payload


def assert_manifest() -> dict[str, Any]:
    manifest, _ = read_locked(MANIFEST_PATH)
    if manifest.get("status") != "PASS":
        raise RuntimeError("DTEC manifest is not PASS")
    assert_pins(manifest["pins"])
    return manifest


def config_lookup(engine: ModuleType) -> dict[str, Any]:
    rows = [*engine.single_side_configs(1), *engine.single_side_configs(-1)]
    return {row.arm_id: row for row in rows}


def stage_a() -> dict[str, Any]:
    manifest = assert_manifest()
    if STAGE_A_PATH.exists() or sidecar(STAGE_A_PATH).exists():
        raise RuntimeError("DTEC Stage A already exists")
    engine, risk, _, context = load_runtime()
    control_full = run_once(engine=engine, risk=risk, context=context, window=D_FULL, config=None)
    control_blocks = [run_once(engine=engine, risk=risk, context=context, window=window, config=None) for window in D_BLOCKS]
    control_stress = run_once(
        engine=engine,
        risk=risk,
        context=context,
        window=D_FULL,
        config=None,
        slippage=STRESS_SLIPPAGE,
    )
    a1: dict[str, list[dict[str, Any]]] = {"long": [], "short": []}
    selected_a1: dict[str, list[str]] = {"long": [], "short": []}
    for side, label in ((1, "long"), (-1, "short")):
        for config in engine.single_side_configs(side):
            run = safe(lambda config=config: run_once(engine=engine, risk=risk, context=context, window=D_FULL, config=config))
            row = {
                "arm_id": config.arm_id,
                "config": config.canonical(),
                "config_sha256": engine.config_sha256(config),
                "run": run,
                "comparison": comparison(run, control_full),
            }
            a1[label].append(row)
        eligible = [row for row in a1[label] if row["run"].get("status") == "PASS" and int(row["run"]["accuracy"][label]["evaluable"]) >= 1]
        eligible.sort(key=lambda row, label=label: a1_rank(row, label))
        selected_a1[label] = [row["arm_id"] for row in eligible[:24]]
    lookup = config_lookup(engine)
    a2: dict[str, list[dict[str, Any]]] = {"long": [], "short": []}
    selected_a2: dict[str, list[str]] = {"long": [], "short": []}
    for label in ("long", "short"):
        for arm_id in selected_a1[label]:
            config = lookup[arm_id]
            full = next(row["run"] for row in a1[label] if row["arm_id"] == arm_id)
            blocks = [safe(lambda window=window, config=config: run_once(engine=engine, risk=risk, context=context, window=window, config=config)) for window in D_BLOCKS]
            stress = safe(lambda config=config: run_once(engine=engine, risk=risk, context=context, window=D_FULL, config=config, slippage=STRESS_SLIPPAGE))
            if any(row.get("status") != "PASS" for row in blocks) or stress.get("status") != "PASS":
                row = {"arm_id": arm_id, "config": config.canonical(), "status": "ERROR", "blocks": blocks, "stress": stress}
            else:
                wfo = {"status": "PASS", "metrics": aggregate_blocks(blocks)}
                control_wfo = {"status": "PASS", "metrics": aggregate_blocks(control_blocks)}
                row = {
                    "arm_id": arm_id,
                    "config": config.canonical(),
                    "status": "PASS",
                    "full": full,
                    "blocks": blocks,
                    "stress": stress,
                    "full_comparison": comparison(full, control_full),
                    "wfo": wfo,
                    "wfo_comparison": comparison(wfo, control_wfo),
                    "stress_comparison": comparison(stress, control_stress),
                    "block_comparisons": [comparison(item, control) for item, control in zip(blocks, control_blocks, strict=True)],
                }
            a2[label].append(row)
        eligible = [row for row in a2[label] if row.get("status") == "PASS"]
        eligible.sort(key=lambda row, label=label: a2_rank(row, label))
        selected_a2[label] = [row["arm_id"] for row in eligible[:4]]
    payload = {
        "schema": "hype-v6-dtec-stage-a-v1",
        "status": "PASS",
        "manifest_sha256": sha256(MANIFEST_PATH),
        "control": {"full": control_full, "blocks": control_blocks, "stress": control_stress},
        "a1": a1,
        "selected_a1": selected_a1,
        "a2": a2,
        "selected_a2": selected_a2,
        "evaluation_not_accessed": True,
    }
    assert_pins(manifest["pins"])
    write_locked(STAGE_A_PATH, payload)
    return payload


def stage_b() -> dict[str, Any]:
    manifest = assert_manifest()
    stage_a_payload, stage_a_sha = read_locked(STAGE_A_PATH)
    if STAGE_B_PATH.exists() or sidecar(STAGE_B_PATH).exists():
        raise RuntimeError("DTEC Stage B already exists")
    engine, risk, _, context = load_runtime()
    lookup = config_lookup(engine)
    control = stage_a_payload["control"]
    control_wfo = {"status": "PASS", "metrics": aggregate_blocks(control["blocks"])}
    rows: list[dict[str, Any]] = []
    for long_index, long_id in enumerate(stage_a_payload["selected_a2"]["long"], 1):
        for short_index, short_id in enumerate(stage_a_payload["selected_a2"]["short"], 1):
            arm_id = f"DTEC_B{long_index}{short_index}_{long_id}_{short_id}"
            config = engine.combine_config(lookup[long_id], lookup[short_id], arm_id=arm_id)
            full = safe(lambda config=config: run_once(engine=engine, risk=risk, context=context, window=D_FULL, config=config))
            blocks = [safe(lambda window=window, config=config: run_once(engine=engine, risk=risk, context=context, window=window, config=config)) for window in D_BLOCKS]
            stress = safe(lambda config=config: run_once(engine=engine, risk=risk, context=context, window=D_FULL, config=config, slippage=STRESS_SLIPPAGE))
            if full.get("status") != "PASS" or stress.get("status") != "PASS" or any(item.get("status") != "PASS" for item in blocks):
                rows.append({"arm_id": arm_id, "config": config.canonical(), "status": "ERROR", "full": full, "blocks": blocks, "stress": stress})
                continue
            wfo = {"status": "PASS", "metrics": aggregate_blocks(blocks)}
            row = {
                "arm_id": arm_id,
                "config": config.canonical(),
                "config_sha256": engine.config_sha256(config),
                "status": "PASS",
                "full": full,
                "blocks": blocks,
                "stress": stress,
                "wfo": wfo,
                "full_comparison": comparison(full, control["full"]),
                "wfo_comparison": comparison(wfo, control_wfo),
                "stress_comparison": comparison(stress, control["stress"]),
                "block_comparisons": [comparison(item, base) for item, base in zip(blocks, control["blocks"], strict=True)],
            }
            row["gate"] = stage_b_gate(row, control)
            rows.append(row)
    passers = [row for row in rows if row.get("gate", {}).get("status") == "PASS"]
    passers.sort(key=b_rank)
    champion = passers[0]["arm_id"] if passers else None
    payload = {
        "schema": "hype-v6-dtec-stage-b-v1",
        "status": "PASS",
        "manifest_sha256": sha256(MANIFEST_PATH),
        "stage_a_sha256": stage_a_sha,
        "trial_count": len(rows),
        "passing_count": len(passers),
        "champion": champion,
        "rows": rows,
        "evaluation_not_accessed": True,
    }
    assert_pins(manifest["pins"])
    write_locked(STAGE_B_PATH, payload)
    return payload


def evaluation_gate(candidate: dict[str, Any], control: dict[str, Any], stress_candidate: dict[str, Any], stress_control: dict[str, Any]) -> dict[str, Any]:
    base = comparison(candidate, control)
    stress = comparison(stress_candidate, stress_control)
    accuracy = candidate["accuracy"]["combined"]
    checks = {
        "candidate_trades_ge_2": int(candidate["metrics"]["closed_trades"]) >= 2,
        "control_trades_ge_2": int(control["metrics"]["closed_trades"]) >= 2,
        "return_higher": bool(base["return_higher"]),
        "mdd_smaller": bool(base["mdd_smaller"]),
        "stress_not_double_worse": not bool(stress["double_worse"]),
        "dtec_evaluable_ge_1": int(accuracy["evaluable"]) >= 1,
        "dtec_precision_ge_050": (accuracy["precision"] is not None and float(accuracy["precision"]) >= 0.50),
        "path_changed": candidate["trades_sha256"] != control["trades_sha256"],
        "nonbankrupt": not bool(candidate["metrics"]["bankrupt_intraday"]),
    }
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "base": base, "stress": stress}


def stage_evaluation() -> dict[str, Any]:
    manifest = assert_manifest()
    stage_b_payload, stage_b_sha = read_locked(STAGE_B_PATH)
    if EVALUATION_PATH.exists() or sidecar(EVALUATION_PATH).exists():
        raise RuntimeError("DTEC evaluation already exists")
    champion_id = stage_b_payload.get("champion")
    if champion_id is None:
        payload = {
            "schema": "hype-v6-dtec-evaluation-v1",
            "status": "SKIPPED_NO_D_CHAMPION",
            "stage_b_sha256": stage_b_sha,
            "evaluation_accessed": False,
        }
        write_locked(EVALUATION_PATH, payload)
        return payload
    row = next(item for item in stage_b_payload["rows"] if item["arm_id"] == champion_id)
    engine, risk, _, context = load_runtime()
    long_parent = engine.DTECConfig("L_PARENT", long=engine.EpisodeParams(**row["config"]["long"]))
    short_parent = engine.DTECConfig("S_PARENT", short=engine.EpisodeParams(**row["config"]["short"]))
    config = engine.combine_config(long_parent, short_parent, arm_id=champion_id)
    candidate = run_once(engine=engine, risk=risk, context=context, window=EVALUATION, config=config, retain=True)
    control = run_once(engine=engine, risk=risk, context=context, window=EVALUATION, config=None, retain=True)
    stress_candidate = run_once(engine=engine, risk=risk, context=context, window=EVALUATION, config=config, slippage=STRESS_SLIPPAGE)
    stress_control = run_once(engine=engine, risk=risk, context=context, window=EVALUATION, config=None, slippage=STRESS_SLIPPAGE)
    gate = evaluation_gate(candidate, control, stress_candidate, stress_control)
    payload = {
        "schema": "hype-v6-dtec-evaluation-v1",
        "status": gate["status"],
        "stage_b_sha256": stage_b_sha,
        "champion": champion_id,
        "config": config.canonical(),
        "candidate": candidate,
        "exact_v6": control,
        "stress_candidate": stress_candidate,
        "stress_exact_v6": stress_control,
        "gate": gate,
        "evaluation_accessed": True,
        "researcher_exposed_not_clean_oos": True,
    }
    assert_pins(manifest["pins"])
    write_locked(EVALUATION_PATH, payload)
    return payload


def stage_finalize() -> dict[str, Any]:
    manifest = assert_manifest()
    stage_b_payload, stage_b_sha = read_locked(STAGE_B_PATH)
    evaluation, evaluation_sha = read_locked(EVALUATION_PATH)
    if FINAL_PATH.exists() or sidecar(FINAL_PATH).exists():
        raise RuntimeError("DTEC final already exists")
    payload = {
        "schema": "hype-v6-dtec-final-v1",
        "status": "PASS_OBSERVATION" if evaluation.get("status") == "PASS" else "HARD-GATE-FAILED",
        "manifest_sha256": sha256(MANIFEST_PATH),
        "stage_b_sha256": stage_b_sha,
        "evaluation_sha256": evaluation_sha,
        "d_champion": stage_b_payload.get("champion"),
        "evaluation_status": evaluation.get("status"),
        "registered": False,
        "promoted": False,
        "live_ready": False,
        "leverage_run": False,
        "exact_v6_unchanged": True,
        "research_state": "explore / not promoted / not live-ready",
    }
    assert_pins(manifest["pins"])
    write_locked(FINAL_PATH, payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("self-test", "manifest", "stage-a", "stage-b", "evaluation", "finalize"), required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    handlers = {
        "self-test": run_preflight,
        "manifest": stage_manifest,
        "stage-a": stage_a,
        "stage-b": stage_b,
        "evaluation": stage_evaluation,
        "finalize": stage_finalize,
    }
    print(json.dumps(sanitize(handlers[args.stage]()), indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
