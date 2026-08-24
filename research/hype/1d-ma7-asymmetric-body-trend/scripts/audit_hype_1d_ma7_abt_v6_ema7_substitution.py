"""Audit registered HYPE-1D-MA7-ABT-V6 with EMA7 replacing MA7."""

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

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CONTRACT_PATH = (
    FAMILY_DIR
    / "specs/hype-1d-ma7-abt-v6-ema7-substitution-contract-2026-08-10.md"
)
LEVERAGE_AUDIT_PATH = SCRIPT_DIR / "audit_hype_1d_ma7_abt_v6_3x_leverage.py"
OUTPUT_PATH = ARTIFACT_DIR / "hype_1d_ma7_abt_v6_ema7_substitution_2026-08-10.json"

FULL = (0, 432)
BLOCKS = tuple((left, left + 54) for left in range(0, 432, 54))
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
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


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        sanitize(value), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


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


def ema7(values: Any) -> Any:
    return (
        pd.Series(values, dtype=float)
        .ewm(span=7, adjust=False, min_periods=7)
        .mean()
        .to_numpy("float64")
    )


def replace_ma7_with_ema7(context: Any) -> Any:
    features = context.features
    replacement = context.engine.Features(
        ma7=ema7(context.book.close),
        atr7=features.atr7,
        prior_high=features.prior_high,
        prior_low=features.prior_low,
        hourly_open=features.hourly_open,
        hourly_high=features.hourly_high,
        hourly_low=features.hourly_low,
        funding_events=features.funding_events,
    )
    market = replace(context.market, features=replacement)
    return replace(context, market=market)


def load_runtime() -> tuple[ModuleType, ModuleType, ModuleType, Any, Any]:
    audit = load_module(LEVERAGE_AUDIT_PATH, "v6_ema7_audit_helpers")
    research = audit.load_module(audit.PEHC_RESEARCH_PATH, "v6_ema7_pehc_research")
    engine, risk, _, context = research.load_runtime()
    config = audit.fixed_v6_config(engine)
    return audit, research, engine, risk, context, config


def scenario(
    *,
    audit: ModuleType,
    research: ModuleType,
    engine: ModuleType,
    risk: ModuleType,
    context: Any,
    config: Any,
    label: str,
    window: tuple[int, int],
    slippage: float = BASE_SLIPPAGE,
    include_funding: bool = True,
    signal_lag: int = 0,
    retain: bool = False,
) -> dict[str, Any]:
    row = audit.scenario(
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
    if row.get("status") == "PASS":
        row["arm_id"] = label
    return row


def safe(call: Any) -> dict[str, Any]:
    try:
        return call()
    except Exception as exc:  # noqa: BLE001 - diagnostics retain failures explicitly
        return {"status": "ERROR", "error_type": type(exc).__name__, "error": str(exc)}


def compare(candidate: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
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
        "trade_count_delta": int(cm["closed_trades"]) - int(vm["closed_trades"]),
        "same_trade_behavior": candidate["behavior_sha256"] == control["behavior_sha256"],
        "same_handoff_events": canonical_hash(candidate["handoff_events"]) == canonical_hash(control["handoff_events"]),
    }


def pair(
    *,
    audit: ModuleType,
    research: ModuleType,
    engine: ModuleType,
    risk: ModuleType,
    control_context: Any,
    ema_context: Any,
    config: Any,
    window: tuple[int, int],
    slippage: float = BASE_SLIPPAGE,
    include_funding: bool = True,
    signal_lag: int = 0,
    retain: bool = False,
) -> dict[str, Any]:
    control = safe(
        lambda: scenario(
            audit=audit,
            research=research,
            engine=engine,
            risk=risk,
            context=control_context,
            config=config,
            label="V6_SMA7_CONTROL",
            window=window,
            slippage=slippage,
            include_funding=include_funding,
            signal_lag=signal_lag,
            retain=retain,
        )
    )
    ema = safe(
        lambda: scenario(
            audit=audit,
            research=research,
            engine=engine,
            risk=risk,
            context=ema_context,
            config=config,
            label="V6_EMA7_SUBSTITUTION",
            window=window,
            slippage=slippage,
            include_funding=include_funding,
            signal_lag=signal_lag,
            retain=retain,
        )
    )
    return {"sma7": control, "ema7": ema, "comparison": compare(ema, control)}


def rolling_windows() -> tuple[tuple[int, int], ...]:
    windows = [(left, left + 90) for left in range(0, FULL[1] - 89, 30)]
    anchored = (FULL[1] - 90, FULL[1])
    if anchored not in windows:
        windows.append(anchored)
    return tuple(windows)


def summarize_windows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [row for row in rows if row["sma7"].get("status") == row["ema7"].get("status") == "PASS"]
    if not valid:
        return {"valid": 0, "total": len(rows)}
    sma_equity = math.prod(float(row["sma7"]["metrics"]["equity_multiple"]) for row in valid)
    ema_equity = math.prod(float(row["ema7"]["metrics"]["equity_multiple"]) for row in valid)
    return {
        "valid": len(valid),
        "total": len(rows),
        "sma7_compound_return_pct": (sma_equity - 1.0) * 100.0,
        "ema7_compound_return_pct": (ema_equity - 1.0) * 100.0,
        "sma7_worst_mdd_pct": min(float(row["sma7"]["metrics"]["chronological_1h_mdd_pct"]) for row in valid),
        "ema7_worst_mdd_pct": min(float(row["ema7"]["metrics"]["chronological_1h_mdd_pct"]) for row in valid),
        "sma7_positive_windows": sum(float(row["sma7"]["metrics"]["net_return_pct"]) > 0.0 for row in valid),
        "ema7_positive_windows": sum(float(row["ema7"]["metrics"]["net_return_pct"]) > 0.0 for row in valid),
        "ema7_double_worse_windows": sum(row["comparison"].get("double_worse") for row in valid),
    }


def phase_audit(
    *,
    audit: ModuleType,
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
            ema_context = replace_ma7_with_ema7(phase_context)
            rows.append(
                {
                    "phase_hours": phase,
                    "market_audit": market.audit,
                    **pair(
                        audit=audit,
                        research=research,
                        engine=engine,
                        risk=risk,
                        control_context=phase_context,
                        ema_context=ema_context,
                        config=config,
                        window=(0, phase_context.book.count),
                    ),
                }
            )
        except Exception as exc:  # noqa: BLE001 - invalid phases stay explicit
            rows.append({"phase_hours": phase, "status": "ERROR", "error_type": type(exc).__name__, "error": str(exc)})
    valid = [row for row in rows if row.get("sma7", {}).get("status") == row.get("ema7", {}).get("status") == "PASS"]
    summary: dict[str, Any] = {"valid_phases": len(valid), "invalid_phases": 24 - len(valid)}
    if valid:
        metrics = [row["ema7"]["metrics"] for row in valid]
        summary.update(
            {
                "ema7_positive_phases": sum(float(row["net_return_pct"]) > 0.0 for row in metrics),
                "ema7_worst_return_pct": min(float(row["net_return_pct"]) for row in metrics),
                "ema7_median_return_pct": median(float(row["net_return_pct"]) for row in metrics),
                "ema7_worst_mdd_pct": min(float(row["chronological_1h_mdd_pct"]) for row in metrics),
                "ema7_max_marked_leverage": max(float(row["max_marked_leverage"]) for row in metrics),
                "ema7_double_worse_phases": sum(row["comparison"].get("double_worse") for row in valid),
            }
        )
    return {"rows": rows, "summary": summary}


def activation_delta(ema: dict[str, Any], control: dict[str, Any]) -> dict[str, int]:
    keys = ("long_trail_exit", "short_rsi_exit", "shadow_start", "handoff_accept", "protective_stop")
    return {
        key: int(ema["activation_counts"].get(key, 0)) - int(control["activation_counts"].get(key, 0))
        for key in keys
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if not args.run:
        raise SystemExit("use --run to execute the frozen diagnostic")
    audit, research, engine, risk, context, config = load_runtime()
    tests = audit.preflight()
    ema_context = replace_ma7_with_ema7(context)

    full = pair(
        audit=audit,
        research=research,
        engine=engine,
        risk=risk,
        control_context=context,
        ema_context=ema_context,
        config=config,
        window=FULL,
        retain=True,
    )
    control_metrics = full["sma7"].get("metrics", {})
    if not (
        full["sma7"].get("status") == "PASS"
        and math.isclose(float(control_metrics["net_return_pct"]), EXPECTED_V6_RETURN, abs_tol=TOLERANCE)
        and math.isclose(float(control_metrics["chronological_1h_mdd_pct"]), EXPECTED_V6_MDD, abs_tol=TOLERANCE)
        and int(control_metrics["closed_trades"]) == EXPECTED_V6_TRADES
    ):
        raise RuntimeError("exact V6 SMA7 anchor drift")
    if full["ema7"].get("status") != "PASS":
        raise RuntimeError(f"V6 EMA7 full run failed: {full['ema7']}")

    stress = pair(audit=audit, research=research, engine=engine, risk=risk, control_context=context, ema_context=ema_context, config=config, window=FULL, slippage=STRESS_SLIPPAGE)
    funding_off = pair(audit=audit, research=research, engine=engine, risk=risk, control_context=context, ema_context=ema_context, config=config, window=FULL, include_funding=False)
    delayed = pair(audit=audit, research=research, engine=engine, risk=risk, control_context=context, ema_context=ema_context, config=config, window=FULL, signal_lag=1)
    recent = {
        label: {
            "window": [max(0, FULL[1] - days), FULL[1]],
            "selection_use": False,
            **pair(
                audit=audit,
                research=research,
                engine=engine,
                risk=risk,
                control_context=context,
                ema_context=ema_context,
                config=config,
                window=(max(0, FULL[1] - days), FULL[1]),
            ),
        }
        for label, days in (("1d", 1), ("7d", 7), ("1m", 30), ("3m", 90), ("6m", 180), ("1y", 365))
    }
    block_rows = [
        {
            "window": list(window),
            **pair(audit=audit, research=research, engine=engine, risk=risk, control_context=context, ema_context=ema_context, config=config, window=window),
        }
        for window in BLOCKS
    ]
    rolling_rows = [
        {
            "window": list(window),
            **pair(audit=audit, research=research, engine=engine, risk=risk, control_context=context, ema_context=ema_context, config=config, window=window),
        }
        for window in rolling_windows()
    ]
    phases = phase_audit(audit=audit, research=research, engine=engine, risk=risk, context=context, config=config)
    checks = {
        "full_return_higher": full["comparison"]["return_higher"],
        "full_mdd_smaller": full["comparison"]["mdd_smaller"],
        "stress_not_double_worse": not stress["comparison"]["double_worse"],
        "funding_off_not_double_worse": not funding_off["comparison"]["double_worse"],
        "lag_not_double_worse": not delayed["comparison"]["double_worse"],
        "blocks_not_double_worse": all(not row["comparison"]["double_worse"] for row in block_rows),
        "core_chain_preserved": all(value >= 0 for value in activation_delta(full["ema7"], full["sma7"]).values()),
    }
    status = "PASS_DIAGNOSTIC_ONLY" if all(checks.values()) else "FAIL"
    payload = {
        "schema": "hype-1d-ma7-abt-v6-ema7-substitution-diagnostic-v1",
        "status": "COMPLETED_DIAGNOSTIC",
        "conclusion": status,
        "research_state": "registered V6 unchanged / shadow-only / diagnostic-only / not promoted / not live-ready",
        "indicator_contract": {
            "control": "SMA7",
            "candidate": "EMA(span=7, adjust=False, min_periods=7)",
            "changed_field": "features.ma7",
            "other_rules_unchanged": True,
        },
        "preflight": tests,
        "identity": {
            "family": "HYPE-1D-MA7-Asymmetric-Body-Trend",
            "version": "V6",
            "arm_id": config.arm_id,
            "config": config.canonical(),
            "config_sha256": engine.config_sha256(config),
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
        "activation_delta": activation_delta(full["ema7"], full["sma7"]),
        "gate": {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks},
        "pins": {
            "contract": sha256(CONTRACT_PATH),
            "audit": sha256(Path(__file__).resolve()),
            "reused_audit_helpers": sha256(LEVERAGE_AUDIT_PATH),
        },
        "registered": False,
        "promoted": False,
        "live_ready": False,
        "exact_v6_changed": False,
        "clean_oos_claim": False,
    }
    write_locked(payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "conclusion": payload["conclusion"],
                "sma7": full["sma7"]["metrics"],
                "ema7": full["ema7"]["metrics"],
                "comparison": full["comparison"],
                "phase_summary": phases["summary"],
                "artifact": str(OUTPUT_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
