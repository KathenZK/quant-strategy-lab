"""Audit registered HYPE-1D-MA7-ABT-V7 with fixed 2x entry leverage."""

from __future__ import annotations

import argparse
from dataclasses import replace
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
CONTRACT_PATH = FAMILY_DIR / "specs/hype-1d-ma7-abt-v7-2x-leverage-contract-2026-08-11.md"
BASE_2X_AUDIT_PATH = SCRIPT_DIR / "audit_hype_1d_ma7_abt_v6_2x_leverage.py"
THREE_X_AUDIT_PATH = SCRIPT_DIR / "audit_hype_1d_ma7_abt_v6_3x_leverage.py"
OUTPUT_PATH = ARTIFACT_DIR / "hype_1d_ma7_abt_v7_2x_leverage_2026-08-11.json"

FULL = (0, 432)
BLOCKS = tuple((left, left + 54) for left in range(0, 432, 54))
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
TARGET_LEVERAGE = 2.0
EXPECTED_V7_RETURN = 711.035936775286
EXPECTED_V7_MDD = -18.395542229660567
EXPECTED_V7_TRADES = 20
TOLERANCE = 1e-8


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


def write_locked(payload: dict[str, Any]) -> str:
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
    return digest


def load_runtime(base2: ModuleType) -> tuple[ModuleType, ModuleType, ModuleType, Any, Any, Any]:
    audit3 = load_module(THREE_X_AUDIT_PATH, "v7_2x_reused_3x_audit")
    audit3.TARGET_LEVERAGE = TARGET_LEVERAGE
    research = audit3.load_module(audit3.PEHC_RESEARCH_PATH, "v7_2x_pehc_research")
    engine, risk, _, context = research.load_runtime()
    pehc_config = audit3.fixed_v6_config(engine)
    context = replace(
        context,
        short_config=replace(context.short_config, cooldown_days=3),
    )
    return audit3, research, engine, risk, context, pehc_config


def relabel(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: relabel(item) for key, item in value.items()}
    if isinstance(value, list):
        return [relabel(item) for item in value]
    if value == "V6_EXACT_1X":
        return "V7_EXACT_1X"
    if value == "V6_FIXED_2X":
        return "V7_FIXED_2X"
    return value


def risk_screen(base2: ModuleType, full_two_x: dict[str, Any], phases: dict[str, Any]) -> dict[str, Any]:
    screen = base2.risk_screen(full_two_x, phases)
    screen["reason"] = (
        "V7 remains a registered 1x research version; this run is an explicitly "
        "authorized exposed-history 2x diagnostic and does not unlock leverage."
    )
    return screen


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if not args.run:
        raise SystemExit("use --run to execute the frozen diagnostic")

    base2 = load_module(BASE_2X_AUDIT_PATH, "v7_2x_base_audit")
    base2.TARGET_LEVERAGE = TARGET_LEVERAGE
    audit3, research, engine, risk, context, config = load_runtime(base2)
    tests = audit3.preflight()

    full = relabel(
        base2.pair(
            audit3=audit3,
            research=research,
            engine=engine,
            risk=risk,
            context=context,
            config=config,
            window=FULL,
            retain=True,
        )
    )
    one_metrics = full["one_x"].get("metrics", {})
    if not (
        full["one_x"].get("status") == "PASS"
        and math.isclose(float(one_metrics["net_return_pct"]), EXPECTED_V7_RETURN, abs_tol=0.05)
        and math.isclose(float(one_metrics["chronological_1h_mdd_pct"]), EXPECTED_V7_MDD, abs_tol=0.01)
        and int(one_metrics["closed_trades"]) == EXPECTED_V7_TRADES
    ):
        raise RuntimeError("exact V7 1x anchor drift")
    if full["two_x"].get("status") != "PASS":
        raise RuntimeError(f"V7 2x full run failed: {full['two_x']}")
    if not full["comparison"]["same_trade_behavior"]:
        raise RuntimeError("2x changed V7 trade behavior")
    if not full["comparison"]["same_handoff_events"]:
        raise RuntimeError("2x changed V7 handoff behavior")
    if not all(
        math.isclose(float(row.get("entry_leverage", math.nan)), TARGET_LEVERAGE, abs_tol=TOLERANCE)
        for row in full["two_x"]["trades"]
    ):
        raise RuntimeError("not every V7 2x trade has fixed 2x entry leverage")

    stress = relabel(base2.pair(audit3=audit3, research=research, engine=engine, risk=risk, context=context, config=config, window=FULL, slippage=STRESS_SLIPPAGE))
    funding_off = relabel(base2.pair(audit3=audit3, research=research, engine=engine, risk=risk, context=context, config=config, window=FULL, include_funding=False))
    delayed = relabel(base2.pair(audit3=audit3, research=research, engine=engine, risk=risk, context=context, config=config, window=FULL, signal_lag=1))
    recent = {
        label: {
            "window": [max(0, FULL[1] - days), FULL[1]],
            "selection_use": False,
            **relabel(base2.pair(audit3=audit3, research=research, engine=engine, risk=risk, context=context, config=config, window=(max(0, FULL[1] - days), FULL[1]))),
        }
        for label, days in (("1d", 1), ("7d", 7), ("1m", 30), ("3m", 90), ("6m", 180), ("1y", 365))
    }
    block_rows = [
        {"window": list(window), **relabel(base2.pair(audit3=audit3, research=research, engine=engine, risk=risk, context=context, config=config, window=window))}
        for window in BLOCKS
    ]
    rolling_rows = [
        {"window": list(window), **relabel(base2.pair(audit3=audit3, research=research, engine=engine, risk=risk, context=context, config=config, window=window))}
        for window in base2.rolling_windows()
    ]
    phases = relabel(base2.phase_audit(audit3=audit3, research=research, engine=engine, risk=risk, context=context, config=config))
    screen = risk_screen(base2, full["two_x"], phases)
    artifact_sha = None
    payload = {
        "schema": "hype-1d-ma7-abt-v7-fixed-2x-diagnostic-v1",
        "status": "COMPLETED_DIAGNOSTIC",
        "conclusion": screen["status"],
        "research_state": "registered V7 unchanged / diagnostic-only / not promoted / not live-ready",
        "governance_deviation": {
            "authorization": "user explicitly requested V7 fixed 2x diagnostic on 2026-08-11",
            "scope": "researcher-exposed history only; cannot unlock or select leverage",
        },
        "preflight": tests,
        "identity": {
            "family": "HYPE-1D-MA7-Asymmetric-Body-Trend",
            "version": "V7",
            "arm_id": "V7_SHORT_COOLDOWN_3D_PLUS_PEHC_294",
            "pehc_config": config.canonical(),
            "v7_short_cooldown_days": 3,
            "one_x_anchor": {
                "net_return_pct": EXPECTED_V7_RETURN,
                "chronological_1h_mdd_pct": EXPECTED_V7_MDD,
                "closed_trades": EXPECTED_V7_TRADES,
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
            "rolling_90d_30d": [list(row) for row in base2.rolling_windows()],
        },
        "full": full,
        "stress_8bps": stress,
        "funding_off": funding_off,
        "signal_lag_plus_1d": delayed,
        "recent_slices_audit_only": recent,
        "cold_flat_blocks": {"rows": block_rows, "summary": base2.summarize_windows(block_rows)},
        "rolling_90d_30d": {"rows": rolling_rows, "summary": base2.summarize_windows(rolling_rows)},
        "phases_0h_to_23h": phases,
        "risk_screen": screen,
        "pins": {
            "contract": sha256(CONTRACT_PATH),
            "audit": sha256(Path(__file__).resolve()),
            "reused_v6_2x_audit": sha256(BASE_2X_AUDIT_PATH),
            "reused_3x_audit_helpers": sha256(THREE_X_AUDIT_PATH),
        },
        "registered": False,
        "promoted": False,
        "live_ready": False,
        "exact_v7_changed": False,
        "leverage_unlocked": False,
        "clean_oos_claim": False,
    }
    artifact_sha = write_locked(payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "conclusion": payload["conclusion"],
                "one_x": full["one_x"]["metrics"],
                "two_x": full["two_x"]["metrics"],
                "phase_summary": phases["summary"],
                "artifact": str(OUTPUT_PATH),
                "artifact_sha256": artifact_sha,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
