"""Frozen RSI6-memory MA7-cross entry ablation on exact HYPE V6."""

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
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"

ENGINE_PATH = SCRIPT_DIR / "hype_1d_ma7_v6_rsi6_memory_cross_engine.py"
ADAPTER_PATH = SCRIPT_DIR / "hype_1d_ma7_v4_fair_adapter.py"
RISK_PATH = SCRIPT_DIR / "hype_1d_ma7_trend_phase_risk_metrics.py"
PEHC_PATH = SCRIPT_DIR / "hype_1d_ma7_profit_exit_handoff_continuity_engine.py"
CONTRACT_PATH = (
    FAMILY_DIR
    / "specs/hype-1d-ma7-v6-rsi6-memory-cross-entry-contract-2026-08-10.md"
)
TEST_PATH = ROOT / "tests/test_hype_1d_ma7_v6_rsi6_memory_cross_engine.py"
SELF_PATH = Path(__file__).resolve()
OUTPUT_PATH = (
    ARTIFACT_DIR / "hype_1d_ma7_v6_rsi6_memory_cross_2026-08-10_v2.json"
)

FULL = (0, 432)
BLOCKS = tuple((left, left + 54) for left in range(0, 432, 54))
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
EXPECTED_V6_RETURN = 617.1070876096234
EXPECTED_V6_MDD = -18.391735672691034
EXPECTED_V6_TRADES = 19
COMPARISON_TOLERANCE = 1e-10


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        sanitize(value), sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_runtime() -> tuple[ModuleType, ModuleType, Any]:
    adapter = load_module(ADAPTER_PATH, "rsi_memory_adapter_runtime")
    engine = load_module(ENGINE_PATH, "rsi_memory_engine_runtime")
    risk = load_module(RISK_PATH, "rsi_memory_risk_runtime")
    return engine, risk, adapter.load_context()


def annualized_return(equity_multiple: float, days: int) -> float:
    return (equity_multiple ** (365.0 / days) - 1.0) * 100.0


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


def start_for(window: tuple[int, int]) -> int:
    left, right = window
    return left if left == 0 or right - left == 1 else left + 1


def run_once(
    engine: ModuleType,
    risk: ModuleType,
    context: Any,
    config: Any | None,
    window: tuple[int, int],
    *,
    slippage: float = BASE_SLIPPAGE,
) -> dict[str, Any]:
    start = start_for(window)
    if config is None:
        result = engine.run_v6(
            context,
            start_index=start,
            terminal_index=window[1],
            slippage=slippage,
        )
        arm_id = "A0_EXACT_V6"
        memory_events: list[dict[str, Any]] = []
    else:
        result = engine.run_variant(
            context,
            config,
            start_index=start,
            terminal_index=window[1],
            slippage=slippage,
        )
        arm_id = config.arm_id
        memory_events = list(result.memory_events)
    replay = risk.replay_chronological_1h(
        context,
        result.raw,
        slippage=slippage,
    )
    if not all(replay.parity.values()):
        raise RuntimeError(f"ledger parity failed: {arm_id}")
    metrics = result.raw.metrics
    days = window[1] - start
    trades = economic_trades(result.raw.trades)
    return {
        "arm_id": arm_id,
        "requested_window": list(window),
        "engine_window": [start, window[1]],
        "metrics": {
            "equity_multiple": float(metrics["equity_multiple"]),
            "net_return_pct": float(metrics["net_return_pct"]),
            "annualized_return_pct": annualized_return(
                float(metrics["equity_multiple"]), days
            ),
            "chronological_1h_mdd_pct": float(
                replay.chronological_1h_mdd_pct
            ),
            "daily_extreme_mdd_pct": float(metrics["max_drawdown_pct"]),
            "closed_trades": int(metrics["closed_trades"]),
            "long_trades": int(metrics["long_trades"]),
            "short_trades": int(metrics["short_trades"]),
            "win_rate": float(metrics["win_rate"]),
            "profit_factor": float(metrics["profit_factor"]),
            "turnover_multiple": float(metrics["turnover_multiple"]),
            "cost_pct_initial": float(metrics["cost_pct_initial"]),
            "funding_pct_initial": float(metrics["funding_pct_initial"]),
            "bankrupt_intraday": bool(metrics["bankrupt_intraday"]),
            "worst_ts": replay.worst_ts,
        },
        "activation_counts": dict(result.activation_counts),
        "memory_events": memory_events,
        "handoff_events": list(result.handoff_events),
        "trades": trades,
        "trades_sha256": canonical_hash(trades),
        "source_sha256": result.source_sha256,
    }


def compare(candidate: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    candidate_metrics = candidate["metrics"]
    control_metrics = control["metrics"]
    return_delta = (
        float(candidate_metrics["net_return_pct"])
        - float(control_metrics["net_return_pct"])
    )
    mdd_delta = (
        float(candidate_metrics["chronological_1h_mdd_pct"])
        - float(control_metrics["chronological_1h_mdd_pct"])
    )
    return {
        "return_delta_pp": return_delta,
        "mdd_delta_pp": mdd_delta,
        "comparison_tolerance": COMPARISON_TOLERANCE,
        "return_higher": return_delta > COMPARISON_TOLERANCE,
        "return_equal": abs(return_delta) <= COMPARISON_TOLERANCE,
        "mdd_smaller": mdd_delta > COMPARISON_TOLERANCE,
        "mdd_equal": abs(mdd_delta) <= COMPARISON_TOLERANCE,
        "dual_improvement": return_delta > COMPARISON_TOLERANCE
        and mdd_delta > COMPARISON_TOLERANCE,
        "double_worse": return_delta < -COMPARISON_TOLERANCE
        and mdd_delta < -COMPARISON_TOLERANCE,
        "trade_count_delta": int(candidate_metrics["closed_trades"])
        - int(control_metrics["closed_trades"]),
        "economic_path_changed": candidate["trades_sha256"]
        != control["trades_sha256"],
    }


def trade_diff(candidate: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    def key(row: dict[str, Any]) -> tuple[str, str]:
        return str(row["entry_ts"]), str(row["side"])

    candidate_map = {key(row): row for row in candidate["trades"]}
    control_map = {key(row): row for row in control["trades"]}
    added = [row for item, row in candidate_map.items() if item not in control_map]
    removed = [row for item, row in control_map.items() if item not in candidate_map]
    changed = []
    for item, row in candidate_map.items():
        if item not in control_map:
            continue
        prior = control_map[item]
        fields = ("exit_ts", "exit_price", "exit_reason", "net_return")
        if any(row.get(field) != prior.get(field) for field in fields):
            changed.append({"control": prior, "candidate": row})
    return {
        "added_count": len(added),
        "removed_count": len(removed),
        "changed_count": len(changed),
        "added": added,
        "removed": removed,
        "changed": changed,
    }


def block_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    equity = math.prod(float(row["metrics"]["equity_multiple"]) for row in rows)
    return {
        "equity_multiple": equity,
        "net_return_pct": (equity - 1.0) * 100.0,
        "worst_block_mdd_pct": min(
            float(row["metrics"]["chronological_1h_mdd_pct"]) for row in rows
        ),
        "closed_trades": sum(int(row["metrics"]["closed_trades"]) for row in rows),
        "positive_blocks": sum(
            float(row["metrics"]["net_return_pct"]) > 0.0 for row in rows
        ),
    }


def block_compare(candidate: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    return_delta = float(candidate["net_return_pct"]) - float(
        control["net_return_pct"]
    )
    mdd_delta = float(candidate["worst_block_mdd_pct"]) - float(
        control["worst_block_mdd_pct"]
    )
    return {
        "return_delta_pp": return_delta,
        "mdd_delta_pp": mdd_delta,
        "double_worse": return_delta < 0.0 and mdd_delta < 0.0,
    }


def recent_windows(count: int) -> dict[str, tuple[int, int]]:
    return {
        label: (max(0, count - days), count)
        for label, days in (
            ("1d", 1),
            ("7d", 7),
            ("1m", 30),
            ("3m", 90),
            ("6m", 180),
            ("1y", 365),
        )
    }


def configs(engine: ModuleType) -> list[Any]:
    cls = engine.RSIMemoryCrossConfig
    return [
        cls("A1_PRIOR5_BOTH"),
        cls("A2_PRIOR5_LONG_ONLY", short_enabled=False),
        cls("A3_PRIOR5_SHORT_ONLY", long_enabled=False),
        cls("A4_INCLUSIVE5_BOTH", window_mode="INCLUSIVE5"),
        cls("A5_PRIOR5_BOTH_NO_NATIVE", native_enabled=False),
    ]


def evaluate_arm(
    engine: ModuleType,
    risk: ModuleType,
    context: Any,
    config: Any,
    control: dict[str, Any],
) -> dict[str, Any]:
    full = run_once(engine, risk, context, config, FULL)
    stress = run_once(
        engine,
        risk,
        context,
        config,
        FULL,
        slippage=STRESS_SLIPPAGE,
    )
    blocks = [run_once(engine, risk, context, config, window) for window in BLOCKS]
    recent = {
        label: run_once(engine, risk, context, config, window)
        for label, window in recent_windows(context.book.count).items()
    }
    block_metrics = block_summary(blocks)
    full_comparison = compare(full, control["full"])
    stress_comparison = compare(stress, control["stress"])
    block_comparison = block_compare(block_metrics, control["block_summary"])
    diff = trade_diff(full, control["full"])
    checks = {
        "full_return_higher": bool(full_comparison["return_higher"]),
        "full_mdd_smaller": bool(full_comparison["mdd_smaller"]),
        "added_trades_ge_2": int(diff["added_count"]) >= 2,
        "stress_not_double_worse": not bool(stress_comparison["double_worse"]),
        "blocks_not_double_worse": not bool(block_comparison["double_worse"]),
        "nonbankrupt": not bool(full["metrics"]["bankrupt_intraday"]),
        "oapp_wired": int(full["activation_counts"].get("long_trail_exit", 0)) > 0,
        "rsi_tp_wired": int(full["activation_counts"].get("short_rsi_exit", 0)) > 0,
        "pehc_wired": int(full["activation_counts"].get("handoff_accept", 0)) > 0,
    }
    return {
        "arm_id": config.arm_id,
        "config": config.canonical(),
        "config_sha256": engine.config_sha256(config),
        "full": full,
        "stress": stress,
        "blocks": blocks,
        "block_summary": block_metrics,
        "recent": recent,
        "full_comparison": full_comparison,
        "stress_comparison": stress_comparison,
        "block_comparison": block_comparison,
        "trade_diff": diff,
        "gate": {
            "status": "POST-REVEAL_DIAGNOSTIC_PASS"
            if all(checks.values())
            else "FAIL",
            "checks": checks,
        },
    }


def preflight() -> dict[str, Any]:
    command = [
        str(ROOT / ".venv/bin/python"),
        "-m",
        "pytest",
        "-q",
        str(TEST_PATH),
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"preflight failed:\n{completed.stdout}\n{completed.stderr}")
    return {"status": "PASS", "command": command, "stdout": completed.stdout.strip()}


def write_locked(payload: dict[str, Any]) -> str:
    document = json.dumps(sanitize(payload), indent=2, sort_keys=True) + "\n"
    digest = hashlib.sha256(document.encode()).hexdigest()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("x", encoding="utf-8") as handle:
        handle.write(document)
    sidecar = Path(f"{OUTPUT_PATH}.sha256")
    with sidecar.open("x", encoding="utf-8") as handle:
        handle.write(f"{digest}  {OUTPUT_PATH.name}\n")
    return digest


def implementation_pins() -> dict[str, str]:
    return {
        "orchestrator": sha256(SELF_PATH),
        "engine": sha256(ENGINE_PATH),
        "adapter": sha256(ADAPTER_PATH),
        "risk": sha256(RISK_PATH),
        "pehc": sha256(PEHC_PATH),
        "contract": sha256(CONTRACT_PATH),
        "test": sha256(TEST_PATH),
    }


def run_research() -> dict[str, Any]:
    if OUTPUT_PATH.exists() or Path(f"{OUTPUT_PATH}.sha256").exists():
        raise RuntimeError("RSI-memory artifact already exists")
    test_result = preflight()
    pins = implementation_pins()
    engine, risk, context = load_runtime()
    control_full = run_once(engine, risk, context, None, FULL)
    control_stress = run_once(
        engine,
        risk,
        context,
        None,
        FULL,
        slippage=STRESS_SLIPPAGE,
    )
    control_blocks = [run_once(engine, risk, context, None, window) for window in BLOCKS]
    control_recent = {
        label: run_once(engine, risk, context, None, window)
        for label, window in recent_windows(context.book.count).items()
    }
    metrics = control_full["metrics"]
    if not math.isclose(
        float(metrics["net_return_pct"]), EXPECTED_V6_RETURN, abs_tol=1e-10
    ):
        raise RuntimeError("exact V6 return anchor drift")
    if not math.isclose(
        float(metrics["chronological_1h_mdd_pct"]), EXPECTED_V6_MDD, abs_tol=1e-10
    ):
        raise RuntimeError("exact V6 MDD anchor drift")
    if int(metrics["closed_trades"]) != EXPECTED_V6_TRADES:
        raise RuntimeError("exact V6 trade-count anchor drift")
    off = run_once(
        engine,
        risk,
        context,
        engine.RSIMemoryCrossConfig(
            "OFF",
            long_enabled=False,
            short_enabled=False,
        ),
        FULL,
    )
    parity = {
        "metrics": off["metrics"] == control_full["metrics"],
        "trades": off["trades"] == control_full["trades"],
        "trades_sha256": off["trades_sha256"] == control_full["trades_sha256"],
    }
    if not all(parity.values()):
        raise RuntimeError(f"RSI-memory OFF parity failed: {parity}")
    control = {
        "full": control_full,
        "stress": control_stress,
        "blocks": control_blocks,
        "block_summary": block_summary(control_blocks),
        "recent": control_recent,
    }
    rows = [
        evaluate_arm(engine, risk, context, config, control)
        for config in configs(engine)
    ]
    primary = next(row for row in rows if row["arm_id"] == "A1_PRIOR5_BOTH")
    payload = {
        "schema": "hype-v6-rsi6-memory-cross-v2",
        "supersedes": "hype_1d_ma7_v6_rsi6_memory_cross_2026-08-10.json",
        "correction": (
            "strict return/MDD comparisons use a 1e-10 tolerance so "
            "path-identical floating-point tails are classified as equal"
        ),
        "status": primary["gate"]["status"],
        "research_state": "all 432d exposed / diagnostic-only / not promoted / not live-ready",
        "preflight": test_result,
        "pins": pins,
        "market_audit": context.market.audit,
        "book_quality": context.book.quality,
        "windows": {
            "full": FULL,
            "cold_flat_blocks": BLOCKS,
            "recent": recent_windows(context.book.count),
        },
        "costs": {
            "fee_per_fill": float(context.engine.FEE),
            "base_slippage_per_fill": BASE_SLIPPAGE,
            "stress_slippage_per_fill": STRESS_SLIPPAGE,
            "funding": True,
        },
        "off_parity": parity,
        "control": control,
        "primary_arm": "A1_PRIOR5_BOTH",
        "arms": rows,
        "registered": False,
        "promoted": False,
        "live_ready": False,
        "leverage_run": False,
        "exact_v6_unchanged": True,
        "clean_oos_claim": False,
    }
    if implementation_pins() != pins:
        raise RuntimeError("implementation pin drift during RSI-memory research")
    write_locked(payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if not args.run:
        raise SystemExit("use --run to execute the frozen post-reveal ablation")
    payload = run_research()
    primary = next(
        row for row in payload["arms"] if row["arm_id"] == payload["primary_arm"]
    )
    print(
        json.dumps(
            {
                "status": payload["status"],
                "primary_metrics": primary["full"]["metrics"],
                "artifact": str(OUTPUT_PATH),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
