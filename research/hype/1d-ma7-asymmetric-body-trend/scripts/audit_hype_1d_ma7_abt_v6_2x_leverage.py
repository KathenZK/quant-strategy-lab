"""Audit registered HYPE-1D-MA7-ABT-V6 with fixed 2x entry leverage."""

from __future__ import annotations

from dataclasses import replace
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from statistics import median
import sys
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CONTRACT_PATH = (
    FAMILY_DIR / "specs/hype-1d-ma7-abt-v6-2x-leverage-contract-2026-08-10.md"
)
THREE_X_AUDIT_PATH = SCRIPT_DIR / "audit_hype_1d_ma7_abt_v6_3x_leverage.py"
OUTPUT_PATH = ARTIFACT_DIR / "hype_1d_ma7_abt_v6_2x_leverage_2026-08-10.json"

FULL = (0, 432)
BLOCKS = tuple((left, left + 54) for left in range(0, 432, 54))
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
TARGET_LEVERAGE = 2.0
EXPECTED_V6_RETURN = 617.1070876096234
EXPECTED_V6_MDD = -18.391735672691034
EXPECTED_V6_TRADES = 19
TOLERANCE = 1e-10


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


def write_locked(payload: dict[str, Any]) -> None:
    sidecar = Path(f"{OUTPUT_PATH}.sha256")
    if OUTPUT_PATH.exists() or sidecar.exists():
        raise RuntimeError(f"locked artifact exists: {OUTPUT_PATH.name}")
    encoded = (
        json.dumps(sanitize(payload), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    ).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    with OUTPUT_PATH.open("xb") as handle:
        handle.write(encoded)
    with sidecar.open("x", encoding="utf-8") as handle:
        handle.write(f"{digest}  {OUTPUT_PATH.name}\n")


def load_runtime() -> tuple[ModuleType, ModuleType, ModuleType, Any, Any]:
    audit3 = load_module(THREE_X_AUDIT_PATH, "v6_2x_reused_audit")
    audit3.TARGET_LEVERAGE = TARGET_LEVERAGE
    research = audit3.load_module(audit3.PEHC_RESEARCH_PATH, "v6_2x_pehc_research")
    engine, risk, _, context = research.load_runtime()
    config = audit3.fixed_v6_config(engine)
    return audit3, research, engine, risk, context, config


def scenario(
    *,
    audit3: ModuleType,
    research: ModuleType,
    engine: ModuleType,
    risk: ModuleType,
    context: Any,
    config: Any,
    target_leverage: float,
    window: tuple[int, int],
    slippage: float = BASE_SLIPPAGE,
    include_funding: bool = True,
    signal_lag: int = 0,
    retain: bool = False,
) -> dict[str, Any]:
    row = audit3.scenario(
        research=research,
        engine=engine,
        risk=risk,
        context=context,
        config=config,
        target_leverage=target_leverage,
        window=window,
        slippage=slippage,
        include_funding=include_funding,
        signal_lag=signal_lag,
        retain=retain,
    )
    if row.get("status") == "PASS":
        row["arm_id"] = "V6_EXACT_1X" if math.isclose(target_leverage, 1.0) else "V6_FIXED_2X"
    return row


def safe(call: Any) -> dict[str, Any]:
    try:
        return call()
    except Exception as exc:  # noqa: BLE001 - diagnostics retain failures explicitly
        return {"status": "ERROR", "error_type": type(exc).__name__, "error": str(exc)}


def comparison(two_x: dict[str, Any], one_x: dict[str, Any], audit3: ModuleType) -> dict[str, Any]:
    row = audit3.comparison(two_x, one_x)
    row["candidate_label"] = "two_x"
    return row


def pair(
    *,
    audit3: ModuleType,
    research: ModuleType,
    engine: ModuleType,
    risk: ModuleType,
    context: Any,
    config: Any,
    window: tuple[int, int],
    slippage: float = BASE_SLIPPAGE,
    include_funding: bool = True,
    signal_lag: int = 0,
    retain: bool = False,
) -> dict[str, Any]:
    one_x = safe(
        lambda: scenario(
            audit3=audit3,
            research=research,
            engine=engine,
            risk=risk,
            context=context,
            config=config,
            target_leverage=1.0,
            window=window,
            slippage=slippage,
            include_funding=include_funding,
            signal_lag=signal_lag,
            retain=retain,
        )
    )
    two_x = safe(
        lambda: scenario(
            audit3=audit3,
            research=research,
            engine=engine,
            risk=risk,
            context=context,
            config=config,
            target_leverage=TARGET_LEVERAGE,
            window=window,
            slippage=slippage,
            include_funding=include_funding,
            signal_lag=signal_lag,
            retain=retain,
        )
    )
    return {
        "one_x": one_x,
        "two_x": two_x,
        "comparison": comparison(two_x, one_x, audit3),
    }


def rolling_windows() -> tuple[tuple[int, int], ...]:
    windows = [(left, left + 90) for left in range(0, FULL[1] - 89, 30)]
    anchored = (FULL[1] - 90, FULL[1])
    if anchored not in windows:
        windows.append(anchored)
    return tuple(windows)


def summarize_windows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [row for row in rows if row["one_x"].get("status") == row["two_x"].get("status") == "PASS"]
    if not valid:
        return {"valid": 0, "total": len(rows)}
    one_equity = math.prod(float(row["one_x"]["metrics"]["equity_multiple"]) for row in valid)
    two_equity = math.prod(float(row["two_x"]["metrics"]["equity_multiple"]) for row in valid)
    return {
        "valid": len(valid),
        "total": len(rows),
        "one_x_compound_return_pct": (one_equity - 1.0) * 100.0,
        "two_x_compound_return_pct": (two_equity - 1.0) * 100.0,
        "one_x_worst_mdd_pct": min(float(row["one_x"]["metrics"]["chronological_1h_mdd_pct"]) for row in valid),
        "two_x_worst_mdd_pct": min(float(row["two_x"]["metrics"]["chronological_1h_mdd_pct"]) for row in valid),
        "one_x_positive_windows": sum(float(row["one_x"]["metrics"]["net_return_pct"]) > 0.0 for row in valid),
        "two_x_positive_windows": sum(float(row["two_x"]["metrics"]["net_return_pct"]) > 0.0 for row in valid),
        "two_x_bankrupt_windows": sum(row["two_x"].get("status") == "BANKRUPT_INTRADAY" for row in rows),
    }


def phase_audit(
    *,
    audit3: ModuleType,
    research: ModuleType,
    engine: ModuleType,
    risk: ModuleType,
    context: Any,
    config: Any,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for phase in range(24):
        try:
            market = context.original_harness.load_market(phase)
            phase_context = replace(context, market=market)
            rows.append(
                {
                    "phase_hours": phase,
                    "market_audit": market.audit,
                    **pair(
                        audit3=audit3,
                        research=research,
                        engine=engine,
                        risk=risk,
                        context=phase_context,
                        config=config,
                        window=(0, phase_context.book.count),
                    ),
                }
            )
        except Exception as exc:  # noqa: BLE001 - invalid phases stay explicit
            rows.append({"phase_hours": phase, "status": "ERROR", "error_type": type(exc).__name__, "error": str(exc)})
    valid = [row for row in rows if row.get("one_x", {}).get("status") == row.get("two_x", {}).get("status") == "PASS"]
    summary: dict[str, Any] = {"valid_phases": len(valid), "invalid_phases": 24 - len(valid)}
    if valid:
        metrics = [row["two_x"]["metrics"] for row in valid]
        summary.update(
            {
                "two_x_positive_phases": sum(float(row["net_return_pct"]) > 0.0 for row in metrics),
                "two_x_worst_return_pct": min(float(row["net_return_pct"]) for row in metrics),
                "two_x_median_return_pct": median(float(row["net_return_pct"]) for row in metrics),
                "two_x_worst_mdd_pct": min(float(row["chronological_1h_mdd_pct"]) for row in metrics),
                "two_x_max_marked_leverage": max(float(row["max_marked_leverage"]) for row in metrics),
            }
        )
    return {"rows": rows, "summary": summary}


def risk_screen(full_two_x: dict[str, Any], phases: dict[str, Any]) -> dict[str, Any]:
    if full_two_x.get("status") != "PASS":
        return {"status": "FAILED_TO_EVALUATE", "adoption_eligible": False}
    metrics = full_two_x["metrics"]
    minimum_ratio = float(metrics["minimum_marked_margin_ratio"])
    maintenance = {
        f"{ratio * 100:g}%": {
            "assumed_maintenance_margin_ratio": ratio,
            "breached_on_hourly_mark_screen": minimum_ratio <= ratio,
        }
        for ratio in (0.005, 0.01, 0.025, 0.05)
    }
    mdd = abs(float(metrics["chronological_1h_mdd_pct"]))
    budgets = {str(budget): mdd <= budget for budget in (20, 25, 30, 35, 40, 50)}
    high_tail_risk = (
        mdd > 50.0
        or float(metrics["max_marked_leverage"]) > 4.0
        or any(row["breached_on_hourly_mark_screen"] for row in maintenance.values())
        or int(phases["summary"].get("two_x_positive_phases", 0)) < int(phases["summary"].get("valid_phases", 0)) / 2
    )
    return {
        "status": "HIGH_TAIL_RISK" if high_tail_risk else "HISTORICAL_SCREEN_ONLY",
        "hourly_open_and_funding_bankruptcy": False,
        "raw_intraday_bankruptcy": bool(metrics["bankrupt_intraday"]),
        "minimum_marked_margin_ratio": minimum_ratio,
        "maintenance_sensitivity": maintenance,
        "mdd_budget_pass": budgets,
        "exact_binance_tiers_modeled": False,
        "liquidation_fee_modeled": False,
        "intrahour_liquidation_path_modeled": False,
        "adoption_eligible": False,
        "reason": (
            "V6 remains shadow-only and 1x prospective has not passed; "
            "this run is an explicitly authorized exposed-history diagnostic."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if not args.run:
        raise SystemExit("use --run to execute the frozen diagnostic")
    audit3, research, engine, risk, context, config = load_runtime()
    tests = audit3.preflight()

    full = pair(audit3=audit3, research=research, engine=engine, risk=risk, context=context, config=config, window=FULL, retain=True)
    one_metrics = full["one_x"].get("metrics", {})
    if not (
        full["one_x"].get("status") == "PASS"
        and math.isclose(float(one_metrics["net_return_pct"]), EXPECTED_V6_RETURN, abs_tol=TOLERANCE)
        and math.isclose(float(one_metrics["chronological_1h_mdd_pct"]), EXPECTED_V6_MDD, abs_tol=TOLERANCE)
        and int(one_metrics["closed_trades"]) == EXPECTED_V6_TRADES
    ):
        raise RuntimeError("exact V6 1x anchor drift")
    if full["two_x"].get("status") != "PASS":
        raise RuntimeError(f"V6 2x full run failed: {full['two_x']}")
    if not full["comparison"]["same_trade_behavior"]:
        raise RuntimeError("2x changed V6 trade behavior")
    if not full["comparison"]["same_handoff_events"]:
        raise RuntimeError("2x changed V6 handoff behavior")
    two_x_trades = full["two_x"]["trades"]
    if not all(math.isclose(float(row.get("entry_leverage", math.nan)), TARGET_LEVERAGE, abs_tol=TOLERANCE) for row in two_x_trades):
        raise RuntimeError("not every V6 2x trade has fixed 2x entry leverage")

    stress = pair(audit3=audit3, research=research, engine=engine, risk=risk, context=context, config=config, window=FULL, slippage=STRESS_SLIPPAGE)
    funding_off = pair(audit3=audit3, research=research, engine=engine, risk=risk, context=context, config=config, window=FULL, include_funding=False)
    delayed = pair(audit3=audit3, research=research, engine=engine, risk=risk, context=context, config=config, window=FULL, signal_lag=1)
    recent = {
        label: {
            "window": [max(0, FULL[1] - days), FULL[1]],
            "selection_use": False,
            **pair(audit3=audit3, research=research, engine=engine, risk=risk, context=context, config=config, window=(max(0, FULL[1] - days), FULL[1])),
        }
        for label, days in (("1d", 1), ("7d", 7), ("1m", 30), ("3m", 90), ("6m", 180), ("1y", 365))
    }
    block_rows = [
        {"window": list(window), **pair(audit3=audit3, research=research, engine=engine, risk=risk, context=context, config=config, window=window)}
        for window in BLOCKS
    ]
    rolling_rows = [
        {"window": list(window), **pair(audit3=audit3, research=research, engine=engine, risk=risk, context=context, config=config, window=window)}
        for window in rolling_windows()
    ]
    phases = phase_audit(audit3=audit3, research=research, engine=engine, risk=risk, context=context, config=config)
    screen = risk_screen(full["two_x"], phases)

    payload = {
        "schema": "hype-1d-ma7-abt-v6-fixed-2x-diagnostic-v1",
        "status": "COMPLETED_DIAGNOSTIC",
        "conclusion": screen["status"],
        "research_state": "registered V6 unchanged / shadow-only / diagnostic-only / not promoted / not live-ready",
        "governance_deviation": {
            "original_rule": "no leverage before V6 1x clean prospective PASS",
            "authorization": "user explicitly requested V6 fixed 2x diagnostic on 2026-08-10",
            "scope": "researcher-exposed history only; cannot unlock or select leverage",
        },
        "preflight": tests,
        "identity": {
            "family": "HYPE-1D-MA7-Asymmetric-Body-Trend",
            "version": "V6",
            "arm_id": config.arm_id,
            "config": config.canonical(),
            "config_sha256": engine.config_sha256(config),
            "one_x_anchor": {
                "net_return_pct": EXPECTED_V6_RETURN,
                "chronological_1h_mdd_pct": EXPECTED_V6_MDD,
                "closed_trades": EXPECTED_V6_TRADES,
            },
        },
        "leverage_contract": {
            "control": "target 1x post-cost equity at every actual entry",
            "candidate": "target 2x post-cost equity at every actual entry",
            "quantity": "fixed until exit or reversal; no periodic rebalance",
            "shadow": "capital-free until accepted handoff becomes an actual short",
            "marked_leverage_may_exceed_target": True,
        },
        "market_audit": context.market.audit,
        "book_quality": context.book.quality,
        "costs": {
            "fee_per_fill": float(context.engine.FEE),
            "base_slippage_per_fill": BASE_SLIPPAGE,
            "stress_slippage_per_fill": STRESS_SLIPPAGE,
            "funding": "actual Binance event timestamp/rate",
        },
        "windows": {
            "full": list(FULL),
            "cold_flat_blocks": [list(row) for row in BLOCKS],
            "rolling_90d_30d": [list(row) for row in rolling_windows()],
        },
        "full": full,
        "stress_8bps": stress,
        "funding_off": funding_off,
        "signal_lag_plus_1d": delayed,
        "recent_slices_audit_only": recent,
        "cold_flat_blocks": {"rows": block_rows, "summary": summarize_windows(block_rows)},
        "rolling_90d_30d": {"rows": rolling_rows, "summary": summarize_windows(rolling_rows)},
        "phases_0h_to_23h": phases,
        "risk_screen": screen,
        "pins": {
            "contract": sha256(CONTRACT_PATH),
            "audit": sha256(Path(__file__).resolve()),
            "reused_3x_audit_helpers": sha256(THREE_X_AUDIT_PATH),
        },
        "registered": False,
        "promoted": False,
        "live_ready": False,
        "exact_v6_changed": False,
        "leverage_unlocked": False,
        "clean_oos_claim": False,
    }
    write_locked(payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "conclusion": payload["conclusion"],
                "one_x": full["one_x"]["metrics"],
                "two_x": full["two_x"]["metrics"],
                "phase_summary": phases["summary"],
                "artifact": str(OUTPUT_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
