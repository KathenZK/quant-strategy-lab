"""Backtest the frozen strict non-ML continuation overlay on V6."""

from __future__ import annotations

from collections import Counter
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"

CONTRACT_PATH = (
    FAMILY_DIR
    / "specs/hype-1d-ma7-v6-strict-continuation-overlay-contract-2026-08-10.md"
)
ENGINE_PATH = SCRIPT_DIR / "hype_1d_ma7_v6_strict_continuation_overlay_engine.py"
ADAPTER_PATH = SCRIPT_DIR / "hype_1d_ma7_v4_fair_adapter.py"
RISK_PATH = SCRIPT_DIR / "hype_1d_ma7_trend_phase_risk_metrics.py"
SELF_PATH = Path(__file__).resolve()
OUTPUT_PATH = (
    ARTIFACT_DIR
    / "hype_1d_ma7_v6_strict_continuation_overlay_2026-08-10.json"
)

FULL = (0, 432)
BLOCKS = tuple((left, left + 54) for left in range(0, 432, 54))
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
EXPECTED_V6_RETURN = 617.1070876096227
EXPECTED_V6_MDD = -18.391735672691034
EXPECTED_V6_TRADES = 19


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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
    document = json.dumps(
        sanitize(value), sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(document.encode()).hexdigest()


def sidecar(path: Path) -> Path:
    return Path(f"{path}.sha256")


def write_json(path: Path, payload: dict[str, Any], *, force: bool) -> str:
    if path.exists() and not force:
        raise RuntimeError(f"refusing to overwrite {path}")
    document = json.dumps(sanitize(payload), indent=2, sort_keys=True, allow_nan=False)
    digest = hashlib.sha256((document + "\n").encode()).hexdigest()
    path.write_text(document + "\n", encoding="utf-8")
    sidecar(path).write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    return digest


def load_runtime() -> tuple[ModuleType, ModuleType, Any]:
    adapter = load_module(ADAPTER_PATH, "strict_cto_adapter")
    risk = load_module(RISK_PATH, "strict_cto_risk")
    engine = load_module(ENGINE_PATH, "strict_cto_engine")
    return engine, risk, adapter.load_context()


def start_for(window: tuple[int, int]) -> int:
    left, right = window
    return left if left == 0 or right - left == 1 else left + 1


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
        "bars_held",
    )
    return [{field: row.get(field) for field in fields} for row in trades]


def normalize_metrics(raw: Any, replay: Any, *, days: int) -> dict[str, Any]:
    metrics = raw.metrics
    equity_multiple = float(metrics["equity_multiple"])
    return {
        "equity_multiple": equity_multiple,
        "net_return_pct": float(metrics["net_return_pct"]),
        "annualized_return_pct": annualized_return(equity_multiple, days),
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
        "bankrupt_intraday": bool(metrics["bankrupt_intraday"]),
        "worst_ts": replay.worst_ts,
        "worst_trade_index": replay.worst_trade_index,
    }


def run_once(
    *,
    engine: ModuleType,
    risk: ModuleType,
    context: Any,
    config: Any | None,
    window: tuple[int, int],
    slippage: float = BASE_SLIPPAGE,
    signal_lag: int = 0,
    include_funding: bool = True,
    retain: bool = False,
) -> dict[str, Any]:
    start = start_for(window)
    if config is None:
        result = engine.run_v6(
            context,
            start_index=start,
            terminal_index=window[1],
            slippage=slippage,
            signal_lag=signal_lag,
            include_funding=include_funding,
            retain=retain,
        )
        arm_id = "C000_EXACT_V6"
        signal_events: list[dict[str, Any]] = []
    else:
        result = engine.run_variant(
            context,
            config,
            start_index=start,
            terminal_index=window[1],
            slippage=slippage,
            signal_lag=signal_lag,
            include_funding=include_funding,
            retain=retain,
        )
        arm_id = config.arm_id
        signal_events = list(result.signal_events)
    replay = risk.replay_chronological_1h(
        context,
        result.raw,
        slippage=slippage,
        include_funding=include_funding,
        retain_points=retain,
    )
    if not all(replay.parity.values()) or bool(result.raw.metrics["bankrupt_intraday"]):
        raise RuntimeError(f"ledger failure: {arm_id}")
    trades = economic_trades(result.raw.trades)
    return {
        "status": "PASS",
        "arm_id": arm_id,
        "requested_window": list(window),
        "engine_window": [start, window[1]],
        "slippage": slippage,
        "signal_lag": signal_lag,
        "include_funding": include_funding,
        "config": config.canonical() if config is not None else None,
        "metrics": normalize_metrics(result.raw, replay, days=window[1] - start),
        "activation_counts": dict(result.activation_counts),
        "signal_events": signal_events,
        "handoff_events": list(result.handoff_events),
        "trades": trades,
        "trades_sha256": canonical_hash(trades),
        "source_sha256": result.source_sha256,
        "replay_parity": dict(replay.parity),
        **({"path": list(result.raw.path), "replay": replay.canonical()} if retain else {}),
    }


def compare(candidate: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    cm = candidate["metrics"]
    vm = control["metrics"]
    return_delta = float(cm["net_return_pct"]) - float(vm["net_return_pct"])
    mdd_delta = float(cm["chronological_1h_mdd_pct"]) - float(vm["chronological_1h_mdd_pct"])
    return {
        "return_delta_pp": return_delta,
        "mdd_delta_pp": mdd_delta,
        "return_higher": return_delta > 0.0,
        "mdd_smaller": mdd_delta > 0.0,
        "dual_improvement": return_delta > 0.0 and mdd_delta > 0.0,
        "double_worse": return_delta < 0.0 and mdd_delta < 0.0,
        "trade_count_delta": int(cm["closed_trades"]) - int(vm["closed_trades"]),
        "economic_path_changed": candidate["trades_sha256"] != control["trades_sha256"],
    }


def trade_identity(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("entry_ts"),
        row.get("exit_ts"),
        row.get("side"),
        row.get("entry_price"),
        row.get("exit_price"),
        row.get("exit_reason"),
    )


def opportunity_cost(candidate: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    candidate_counts = Counter(trade_identity(row) for row in candidate["trades"])
    control_counts = Counter(trade_identity(row) for row in control["trades"])
    added = [
        row
        for row in candidate["trades"]
        if candidate_counts[trade_identity(row)] > control_counts[trade_identity(row)]
    ]
    removed = [
        row
        for row in control["trades"]
        if control_counts[trade_identity(row)] > candidate_counts[trade_identity(row)]
    ]
    keys = ("long_trail_exit", "short_rsi_exit", "shadow_start", "handoff_accept")
    activation_delta = {
        key: int(candidate["activation_counts"].get(key, 0))
        - int(control["activation_counts"].get(key, 0))
        for key in keys
    }
    return {
        "added_trades": added,
        "removed_v6_trades": removed,
        "added_count": len(added),
        "removed_count": len(removed),
        "activation_delta": activation_delta,
        "core_chain_preserved": all(value >= 0 for value in activation_delta.values()),
    }


def aggregate_blocks(rows: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = [row["metrics"] for row in rows]
    equity = math.prod(float(row["equity_multiple"]) for row in metrics)
    return {
        "equity_multiple": equity,
        "net_return_pct": (equity - 1.0) * 100.0,
        "worst_block_mdd_pct": min(float(row["chronological_1h_mdd_pct"]) for row in metrics),
        "closed_trades": sum(int(row["closed_trades"]) for row in metrics),
        "positive_blocks": sum(float(row["net_return_pct"]) > 0.0 for row in metrics),
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


def run_all(*, force: bool) -> dict[str, Any]:
    engine, risk, context = load_runtime()
    config = engine.StrictOverlayConfig()
    control = run_once(engine=engine, risk=risk, context=context, config=None, window=FULL, retain=True)
    cm = control["metrics"]
    if not math.isclose(float(cm["net_return_pct"]), EXPECTED_V6_RETURN, rel_tol=1e-12, abs_tol=1e-12):
        raise RuntimeError("V6 return anchor drift")
    if not math.isclose(float(cm["chronological_1h_mdd_pct"]), EXPECTED_V6_MDD, rel_tol=1e-12, abs_tol=1e-12):
        raise RuntimeError("V6 MDD anchor drift")
    if int(cm["closed_trades"]) != EXPECTED_V6_TRADES:
        raise RuntimeError("V6 trade-count anchor drift")

    candidate = run_once(engine=engine, risk=risk, context=context, config=config, window=FULL, retain=True)
    stress_control = run_once(engine=engine, risk=risk, context=context, config=None, window=FULL, slippage=STRESS_SLIPPAGE)
    stress_candidate = run_once(engine=engine, risk=risk, context=context, config=config, window=FULL, slippage=STRESS_SLIPPAGE)
    funding_control = run_once(engine=engine, risk=risk, context=context, config=None, window=FULL, include_funding=False)
    funding_candidate = run_once(engine=engine, risk=risk, context=context, config=config, window=FULL, include_funding=False)
    lag_control = run_once(engine=engine, risk=risk, context=context, config=None, window=FULL, signal_lag=1)
    lag_candidate = run_once(engine=engine, risk=risk, context=context, config=config, window=FULL, signal_lag=1)
    block_control = [run_once(engine=engine, risk=risk, context=context, config=None, window=window) for window in BLOCKS]
    block_candidate = [run_once(engine=engine, risk=risk, context=context, config=config, window=window) for window in BLOCKS]
    recent = {
        label: run_once(engine=engine, risk=risk, context=context, config=config, window=window)
        for label, window in recent_windows(FULL[1]).items()
    }
    recent_control = {
        label: run_once(engine=engine, risk=risk, context=context, config=None, window=window)
        for label, window in recent_windows(FULL[1]).items()
    }
    cost = opportunity_cost(candidate, control)
    comparisons = {
        "full": compare(candidate, control),
        "stress_8bps": compare(stress_candidate, stress_control),
        "funding_off": compare(funding_candidate, funding_control),
        "signal_lag_plus_1d": compare(lag_candidate, lag_control),
        "blocks": [compare(row, base) for row, base in zip(block_candidate, block_control, strict=True)],
    }
    checks = {
        "full_return_higher": comparisons["full"]["return_higher"],
        "full_mdd_smaller": comparisons["full"]["mdd_smaller"],
        "stress_not_double_worse": not comparisons["stress_8bps"]["double_worse"],
        "funding_off_not_double_worse": not comparisons["funding_off"]["double_worse"],
        "lag_not_double_worse": not comparisons["signal_lag_plus_1d"]["double_worse"],
        "blocks_not_double_worse": all(not row["double_worse"] for row in comparisons["blocks"]),
        "core_chain_preserved": cost["core_chain_preserved"],
    }
    payload = {
        "schema": "hype-1d-ma7-v6-strict-continuation-overlay-v1",
        "status": "PASS_DIAGNOSTIC_ONLY" if all(checks.values()) else "HARD-GATE-FAILED",
        "research_state": "all 432d researcher-exposed / diagnostic-only / not promoted / not live-ready",
        "pins": {
            "contract": sha256(CONTRACT_PATH),
            "orchestrator": sha256(SELF_PATH),
            "engine": sha256(ENGINE_PATH),
            "adapter": sha256(ADAPTER_PATH),
            "risk": sha256(RISK_PATH),
        },
        "market_audit": context.market.audit,
        "book_quality": context.book.quality,
        "control": control,
        "candidate": candidate,
        "stress_8bps": {"control": stress_control, "candidate": stress_candidate},
        "funding_off": {"control": funding_control, "candidate": funding_candidate},
        "signal_lag_plus_1d": {"control": lag_control, "candidate": lag_candidate},
        "cold_flat_blocks": {
            "windows": [list(row) for row in BLOCKS],
            "control": block_control,
            "candidate": block_candidate,
            "control_summary": aggregate_blocks(block_control),
            "candidate_summary": aggregate_blocks(block_candidate),
        },
        "recent_slices_audit_only": {"control": recent_control, "candidate": recent},
        "opportunity_cost": cost,
        "comparisons": comparisons,
        "gate": {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks},
        "decision": "Do not change V6 unless PASS_DIAGNOSTIC_ONLY is followed by clean prospective validation.",
    }
    digest = write_json(OUTPUT_PATH, payload, force=force)
    payload["output_sha256"] = digest
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    payload = run_all(force=args.force)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": str(OUTPUT_PATH),
                "candidate_return": payload["candidate"]["metrics"]["net_return_pct"],
                "candidate_mdd": payload["candidate"]["metrics"]["chronological_1h_mdd_pct"],
                "gate": payload["gate"]["status"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
