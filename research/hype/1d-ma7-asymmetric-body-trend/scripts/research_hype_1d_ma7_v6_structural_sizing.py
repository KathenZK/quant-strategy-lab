"""Run the preregistered exact-V6 structural sizing diagnostic."""

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
ENGINE_PATH = SCRIPT_DIR / "hype_1d_ma7_v6_structural_sizing_engine.py"
ADAPTER_PATH = SCRIPT_DIR / "hype_1d_ma7_v4_fair_adapter.py"
RISK_PATH = SCRIPT_DIR / "hype_1d_ma7_trend_phase_risk_metrics.py"
CONTRACT_PATH = (
    FAMILY_DIR / "specs/hype-1d-ma7-v6-structural-sizing-contract-2026-08-10.md"
)
TEST_PATHS = (
    ROOT / "tests/test_hype_1d_ma7_v6_structural_sizing_engine.py",
    ROOT / "tests/test_hype_1d_ma7_v6_rsi6_memory_cross_engine.py",
)
SELF_PATH = Path(__file__).resolve()
OUTPUT_PATH = ARTIFACT_DIR / "hype_1d_ma7_v6_structural_sizing_2026-08-10_v2.json"

FULL = (0, 432)
BLOCKS = tuple((left, left + 54) for left in range(0, 432, 54))
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
EXPECTED_V6_RETURN = 617.1070876096234
EXPECTED_V6_MDD = -18.391735672691034
EXPECTED_V6_TRADES = 19
TOLERANCE = 1e-10


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
    encoded = json.dumps(
        sanitize(value), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_runtime() -> tuple[ModuleType, ModuleType, Any]:
    adapter = load_module(ADAPTER_PATH, "v6_structural_adapter_runtime")
    engine = load_module(ENGINE_PATH, "v6_structural_engine_runtime")
    risk = load_module(RISK_PATH, "v6_structural_risk_runtime")
    return engine, risk, adapter.load_context()


def annualized_return(equity_multiple: float, days: int) -> float:
    return (equity_multiple ** (365.0 / days) - 1.0) * 100.0


def economic_trades(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = (
        "entry_ts",
        "exit_ts",
        "side",
        "entry_price",
        "entry_leverage",
        "structural_probe",
        "structural_promoted",
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
        result = engine.run_exact_v6(
            context,
            start_index=start,
            terminal_index=window[1],
            slippage=slippage,
        )
        arm_id = "CTRL_EXACT_V6"
        memory_events: list[dict[str, Any]] = []
        leverage_events: list[dict[str, Any]] = []
        structural_events: list[dict[str, Any]] = []
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
        leverage_events = list(result.leverage_events)
        structural_events = list(result.structural_events)
    replay = (
        risk.replay_chronological_1h(context, result.raw, slippage=slippage)
        if config is None
        else engine.replay_structural_chronological_1h(
            context, result, slippage=slippage
        )
    )
    if not all(replay.parity.values()):
        raise RuntimeError(f"1h ledger parity failed: {arm_id} {window}")
    metrics = result.raw.metrics
    trades = economic_trades(result.raw.trades)
    return {
        "arm_id": arm_id,
        "requested_window": list(window),
        "engine_window": [start, window[1]],
        "metrics": {
            "equity_multiple": float(metrics["equity_multiple"]),
            "net_return_pct": float(metrics["net_return_pct"]),
            "annualized_return_pct": annualized_return(
                float(metrics["equity_multiple"]), window[1] - start
            ),
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
            "bankrupt_intraday": bool(metrics["bankrupt_intraday"]),
            "worst_ts": replay.worst_ts,
        },
        "activation_counts": dict(result.activation_counts),
        "memory_events": memory_events,
        "leverage_events": leverage_events,
        "structural_events": structural_events,
        "handoff_events": list(result.handoff_events),
        "trades": trades,
        "trades_sha256": canonical_hash(trades),
        "source_sha256": result.source_sha256,
    }


def compare(candidate: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    left = candidate["metrics"]
    right = control["metrics"]
    return_delta = float(left["net_return_pct"]) - float(right["net_return_pct"])
    mdd_delta = float(left["chronological_1h_mdd_pct"]) - float(
        right["chronological_1h_mdd_pct"]
    )
    return {
        "return_delta_pp": return_delta,
        "mdd_delta_pp": mdd_delta,
        "return_higher": return_delta > TOLERANCE,
        "mdd_smaller": mdd_delta > TOLERANCE,
        "dual_improvement": return_delta > TOLERANCE and mdd_delta > TOLERANCE,
        "double_worse": return_delta < -TOLERANCE and mdd_delta < -TOLERANCE,
        "trade_count_delta": int(left["closed_trades"]) - int(right["closed_trades"]),
        "economic_path_changed": candidate["trades_sha256"] != control["trades_sha256"],
    }


def trade_diff(candidate: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    def key(row: dict[str, Any]) -> tuple[str, str]:
        return str(row["entry_ts"]), str(row["side"])

    candidate_map = {key(row): row for row in candidate["trades"]}
    control_map = {key(row): row for row in control["trades"]}
    added = [row for item, row in candidate_map.items() if item not in control_map]
    removed = [row for item, row in control_map.items() if item not in candidate_map]
    changed = []
    episode_deltas = []
    for item in sorted(set(candidate_map) | set(control_map)):
        candidate_row = candidate_map.get(item)
        control_row = control_map.get(item)
        delta = float(candidate_row.get("net_pnl", 0.0) if candidate_row else 0.0) - float(
            control_row.get("net_pnl", 0.0) if control_row else 0.0
        )
        episode_deltas.append(
            {
                "entry_ts": item[0],
                "side": item[1],
                "net_pnl_delta": delta,
                "candidate": candidate_row,
                "control": control_row,
            }
        )
        if candidate_row is not None and control_row is not None:
            fields = (
                "exit_ts",
                "exit_price",
                "exit_reason",
                "net_return",
                "entry_leverage",
                "structural_promoted",
            )
            if any(candidate_row.get(field) != control_row.get(field) for field in fields):
                changed.append({"control": control_row, "candidate": candidate_row})
    positive = [row for row in episode_deltas if row["net_pnl_delta"] > TOLERANCE]
    positive_sum = sum(float(row["net_pnl_delta"]) for row in positive)
    largest_share = (
        max(float(row["net_pnl_delta"]) for row in positive) / positive_sum
        if positive_sum > 0.0
        else 1.0
    )
    causal_episodes = []
    for item in sorted(set(candidate_map) & set(control_map)):
        candidate_row = candidate_map[item]
        control_row = control_map[item]
        candidate_leverage = float(candidate_row.get("entry_leverage") or 1.0)
        control_leverage = float(control_row.get("entry_leverage") or 1.0)
        mechanism_changed = (
            not math.isclose(candidate_leverage, control_leverage, abs_tol=TOLERANCE)
            or bool(candidate_row.get("structural_promoted"))
            != bool(control_row.get("structural_promoted"))
            or candidate_row.get("exit_ts") != control_row.get("exit_ts")
            or candidate_row.get("exit_reason") != control_row.get("exit_reason")
            or not math.isclose(
                float(candidate_row.get("exit_price") or 0.0),
                float(control_row.get("exit_price") or 0.0),
                abs_tol=TOLERANCE,
            )
        )
        if mechanism_changed:
            causal_episodes.append(
                {
                    "kind": "matched_path_changed",
                    "candidate": candidate_row,
                    "control": control_row,
                    "net_pnl_delta": float(candidate_row.get("net_pnl") or 0.0)
                    - float(control_row.get("net_pnl") or 0.0),
                }
            )
    unmatched_added = list(added)
    unmatched_removed = list(removed)
    paired_added: set[int] = set()
    paired_removed: set[int] = set()
    for added_index, added_row in enumerate(unmatched_added):
        added_start = str(added_row["entry_ts"])
        added_end = str(added_row["exit_ts"])
        for removed_index, removed_row in enumerate(unmatched_removed):
            if removed_index in paired_removed or added_row["side"] != removed_row["side"]:
                continue
            removed_start = str(removed_row["entry_ts"])
            removed_end = str(removed_row["exit_ts"])
            overlaps = max(added_start, removed_start) <= min(added_end, removed_end)
            if not overlaps:
                continue
            paired_added.add(added_index)
            paired_removed.add(removed_index)
            causal_episodes.append(
                {
                    "kind": "replaced_overlapping_episode",
                    "candidate": added_row,
                    "control": removed_row,
                    "net_pnl_delta": float(added_row.get("net_pnl") or 0.0)
                    - float(removed_row.get("net_pnl") or 0.0),
                }
            )
            break
    causal_episodes.extend(
        {
            "kind": "added_episode",
            "candidate": row,
            "control": None,
            "net_pnl_delta": float(row.get("net_pnl") or 0.0),
        }
        for index, row in enumerate(unmatched_added)
        if index not in paired_added
    )
    causal_episodes.extend(
        {
            "kind": "removed_episode",
            "candidate": None,
            "control": row,
            "net_pnl_delta": -float(row.get("net_pnl") or 0.0),
        }
        for index, row in enumerate(unmatched_removed)
        if index not in paired_removed
    )
    causal_positive = [
        row for row in causal_episodes if float(row["net_pnl_delta"]) > TOLERANCE
    ]
    causal_positive_sum = sum(float(row["net_pnl_delta"]) for row in causal_positive)
    largest_causal_share = (
        max(float(row["net_pnl_delta"]) for row in causal_positive)
        / causal_positive_sum
        if causal_positive_sum > 0.0
        else 1.0
    )
    return {
        "added_count": len(added),
        "removed_count": len(removed),
        "changed_count": len(changed),
        "added": added,
        "removed": removed,
        "changed": changed,
        "episode_deltas": episode_deltas,
        "positive_episode_count": len(positive),
        "largest_positive_episode_share": largest_share,
        "causal_episodes": causal_episodes,
        "causal_modified_episode_count": len(causal_episodes),
        "causal_positive_episode_count": len(causal_positive),
        "largest_causal_positive_episode_share": largest_causal_share,
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
        "positive_blocks": sum(float(row["metrics"]["net_return_pct"]) > 0.0 for row in rows),
    }


def block_compare(candidate: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    return_delta = float(candidate["net_return_pct"]) - float(control["net_return_pct"])
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


def evaluate_arm(
    engine: ModuleType,
    risk: ModuleType,
    context: Any,
    config: Any,
    control: dict[str, Any],
) -> dict[str, Any]:
    full = run_once(engine, risk, context, config, FULL)
    stress = run_once(
        engine, risk, context, config, FULL, slippage=STRESS_SLIPPAGE
    )
    blocks = [run_once(engine, risk, context, config, window) for window in BLOCKS]
    recent = {
        label: run_once(engine, risk, context, config, window)
        for label, window in recent_windows(context.book.count).items()
    }
    full_comparison = compare(full, control["full"])
    stress_comparison = compare(stress, control["stress"])
    blocks_total = block_summary(blocks)
    blocks_comparison = block_compare(blocks_total, control["block_summary"])
    diff = trade_diff(full, control["full"])
    checks = {
        "full_return_higher": bool(full_comparison["return_higher"]),
        "full_mdd_smaller": bool(full_comparison["mdd_smaller"]),
        "stress_not_double_worse": not bool(stress_comparison["double_worse"]),
        "blocks_not_double_worse": not bool(blocks_comparison["double_worse"]),
        "causal_modified_episodes_ge_5": int(diff["causal_modified_episode_count"]) >= 5,
        "largest_causal_positive_episode_share_le_35pct": float(
            diff["largest_causal_positive_episode_share"]
        )
        <= 0.35,
        "nonbankrupt": not bool(full["metrics"]["bankrupt_intraday"]),
    }
    return {
        "arm_id": config.arm_id,
        "config": config.canonical(),
        "config_sha256": engine.config_sha256(config),
        "full": full,
        "stress": stress,
        "blocks": blocks,
        "block_summary": blocks_total,
        "recent": recent,
        "full_comparison": full_comparison,
        "stress_comparison": stress_comparison,
        "block_comparison": blocks_comparison,
        "trade_diff": diff,
        "gate": {"status": "DIAGNOSTIC_PASS" if all(checks.values()) else "FAIL", "checks": checks},
    }


def preflight() -> dict[str, Any]:
    command = [
        str(ROOT / ".venv/bin/python"),
        "-m",
        "pytest",
        "-q",
        *[str(path) for path in TEST_PATHS],
    ]
    completed = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        raise RuntimeError(f"preflight failed:\n{completed.stdout}\n{completed.stderr}")
    return {"status": "PASS", "command": command, "stdout": completed.stdout.strip()}


def implementation_pins() -> dict[str, str]:
    return {
        "orchestrator": sha256(SELF_PATH),
        "engine": sha256(ENGINE_PATH),
        "adapter": sha256(ADAPTER_PATH),
        "risk": sha256(RISK_PATH),
        "contract": sha256(CONTRACT_PATH),
        **{f"test_{index}": sha256(path) for index, path in enumerate(TEST_PATHS, 1)},
    }


def write_locked(payload: dict[str, Any]) -> str:
    if OUTPUT_PATH.exists() or Path(f"{OUTPUT_PATH}.sha256").exists():
        raise RuntimeError(f"locked artifact exists: {OUTPUT_PATH.name}")
    document = json.dumps(sanitize(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    digest = hashlib.sha256(document.encode()).hexdigest()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("x", encoding="utf-8") as handle:
        handle.write(document)
    with Path(f"{OUTPUT_PATH}.sha256").open("x", encoding="utf-8") as handle:
        handle.write(f"{digest}  {OUTPUT_PATH.name}\n")
    return digest


def run_research() -> dict[str, Any]:
    tests = preflight()
    pins = implementation_pins()
    engine, risk, context = load_runtime()
    if context.book.count != 432:
        raise RuntimeError("frozen 432-day book drift")
    control_full = run_once(engine, risk, context, None, FULL)
    control_stress = run_once(
        engine, risk, context, None, FULL, slippage=STRESS_SLIPPAGE
    )
    control_blocks = [run_once(engine, risk, context, None, window) for window in BLOCKS]
    control_recent = {
        label: run_once(engine, risk, context, None, window)
        for label, window in recent_windows(context.book.count).items()
    }
    metrics = control_full["metrics"]
    anchors = {
        "return": math.isclose(float(metrics["net_return_pct"]), EXPECTED_V6_RETURN, abs_tol=TOLERANCE),
        "mdd": math.isclose(float(metrics["chronological_1h_mdd_pct"]), EXPECTED_V6_MDD, abs_tol=TOLERANCE),
        "trades": int(metrics["closed_trades"]) == EXPECTED_V6_TRADES,
    }
    if not all(anchors.values()):
        raise RuntimeError(f"exact V6 anchor drift: {anchors}")
    configs = engine.frozen_configs()
    off = run_once(engine, risk, context, configs[0], FULL)
    def parity_trade(row: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in row.items()
            if key not in {"structural_probe", "structural_promoted"}
        }

    def parity_metrics(left: dict[str, Any], right: dict[str, Any]) -> bool:
        if set(left) != set(right):
            return False
        return all(
            math.isclose(float(left[key]), float(right[key]), abs_tol=TOLERANCE)
            if isinstance(left[key], (int, float)) and isinstance(right[key], (int, float))
            else left[key] == right[key]
            for key in left
        )

    off_parity = {
        "metrics": parity_metrics(off["metrics"], control_full["metrics"]),
        "trades": [parity_trade(row) for row in off["trades"]]
        == [parity_trade(row) for row in control_full["trades"]],
        "source_is_distinct": off["source_sha256"] != control_full["source_sha256"],
    }
    if not all(off_parity.values()):
        raise RuntimeError(f"structural OFF parity failed: {off_parity}")
    control = {
        "full": control_full,
        "stress": control_stress,
        "blocks": control_blocks,
        "block_summary": block_summary(control_blocks),
        "recent": control_recent,
    }
    rows = [
        evaluate_arm(engine, risk, context, config, control)
        for config in configs[1:]
    ]
    retained = [row["arm_id"] for row in rows if row["gate"]["status"] == "DIAGNOSTIC_PASS"]
    dual = [row for row in rows if row["full_comparison"]["dual_improvement"]]
    if dual:
        best = max(dual, key=lambda row: float(row["full"]["metrics"]["net_return_pct"]))
    else:
        best = max(rows, key=lambda row: float(row["full"]["metrics"]["net_return_pct"]))
    payload = {
        "schema": "hype-v6-structural-sizing-v2",
        "supersedes": "hype_1d_ma7_v6_structural_sizing_2026-08-10.json",
        "correction": (
            "causal episode gate excludes downstream trades whose only difference is "
            "the compounded equity base from an earlier modified episode"
        ),
        "status": "DIAGNOSTIC_PASS" if retained else "FAIL",
        "research_state": "all 432d exposed / diagnostic-only / not promoted / not live-ready",
        "preflight": tests,
        "pins": pins,
        "market_audit": context.market.audit,
        "book_quality": context.book.quality,
        "windows": {"full": FULL, "cold_flat_blocks": BLOCKS, "recent": recent_windows(context.book.count)},
        "costs": {
            "fee_per_fill": float(context.engine.FEE),
            "base_slippage_per_fill": BASE_SLIPPAGE,
            "stress_slippage_per_fill": STRESS_SLIPPAGE,
            "funding": True,
        },
        "exact_v6_anchors": anchors,
        "off_parity": off_parity,
        "control": control,
        "arms": rows,
        "retained_arms": retained,
        "best_diagnostic_arm": best["arm_id"],
        "registered": False,
        "promoted": False,
        "live_ready": False,
        "clean_oos_claim": False,
        "exact_v6_unchanged": True,
    }
    if implementation_pins() != pins:
        raise RuntimeError("implementation pin drift during structural research")
    write_locked(payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if not args.run:
        raise SystemExit("use --run to execute the frozen post-reveal diagnostic")
    payload = run_research()
    summary = [
        {
            "arm_id": row["arm_id"],
            "return": row["full"]["metrics"]["net_return_pct"],
            "mdd": row["full"]["metrics"]["chronological_1h_mdd_pct"],
            "trades": row["full"]["metrics"]["closed_trades"],
            "gate": row["gate"]["status"],
        }
        for row in payload["arms"]
    ]
    print(
        json.dumps(
            {
                "status": payload["status"],
                "best_diagnostic_arm": payload["best_diagnostic_arm"],
                "retained_arms": payload["retained_arms"],
                "arms": summary,
                "artifact": str(OUTPUT_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
