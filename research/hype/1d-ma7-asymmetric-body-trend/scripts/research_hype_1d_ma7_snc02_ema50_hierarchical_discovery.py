"""Run the frozen HCSM50 hierarchical trend-discovery diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from types import ModuleType
from typing import Any, Callable

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CONTRACT_PATH = (
    FAMILY_DIR
    / "specs/hype-1d-ma7-snc02-ema50-hierarchical-discovery-contract-2026-08-20.md"
)
BASE_SCRIPT_PATH = (
    SCRIPT_DIR / "research_hype_1d_ma7_snc02_trend_first_discovery_audit.py"
)
BASE_ARTIFACT_PATH = (
    ARTIFACT_DIR / "hype_1d_ma7_snc02_trend_first_discovery_audit_2026-08-20.json"
)
CONTROL_SCRIPT_PATH = (
    SCRIPT_DIR / "research_hype_1d_ma7_symmetric_naked_cross_slope.py"
)
STAGE_A_SCRIPT_PATH = (
    SCRIPT_DIR / "research_hype_1d_ma7_snc02_risk_overlay_oat.py"
)
RISK_PATH = SCRIPT_DIR / "hype_1d_ma7_trend_phase_risk_metrics.py"
OUTPUT_PATH = (
    ARTIFACT_DIR
    / "hype_1d_ma7_snc02_ema50_hierarchical_discovery_2026-08-20.json"
)

EMA_SPAN = 50
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
CANONICAL_RIGHT = 432


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
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        return sanitize(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def ema50_values(context: Any) -> list[float]:
    series = pd.Series([float(value) for value in context.book.close], dtype=float)
    return [
        float(value)
        for value in series.ewm(
            span=EMA_SPAN,
            adjust=False,
            min_periods=EMA_SPAN,
        ).mean()
    ]


def make_hcsm_signal(
    base: ModuleType,
    ema50: list[float],
) -> Callable[[Any, int, Any], Any | None]:
    def hcsm_signal(context: Any, index: int, seed: Any) -> Any | None:
        cross = base.raw_cross(context, index)
        if cross is not None:
            seed.side = int(cross["side"])
            seed.index = index
            seed.ts = pd.Timestamp(cross["ts"])
            seed.slope_atr = float(cross["directional_slope_atr"])

        if not seed.side:
            return None
        if not base.on_directional_ma_side(context, index, seed.side):
            seed.clear()
            return None
        slope = base.directional_slope_atr(context, index, seed.side)
        if not math.isfinite(slope) or slope < base.SLOPE_MIN_ATR:
            return None

        immediate = index == seed.index
        if not immediate:
            current_ema = ema50[index]
            previous_ema = ema50[index - 1] if index else math.nan
            close = float(context.book.close[index])
            aligned = (
                math.isfinite(current_ema)
                and math.isfinite(previous_ema)
                and seed.side * (close - current_ema) > 0.0
                and seed.side * (current_ema - previous_ema) > 0.0
            )
            if not aligned:
                return None

        if seed.ts is None:
            raise RuntimeError("seed timestamp missing")
        signal = base.Signal(
            index=index,
            ts=pd.Timestamp(context.book.ts[index]),
            target_side=seed.side,
            slope_atr=slope,
            signal_kind=(
                "qualified_fresh_cross"
                if immediate
                else "delayed_slope_maturation_ema50"
            ),
            seed_index=seed.index,
            seed_ts=seed.ts,
            seed_slope_atr=seed.slope_atr,
            maturation_days=index - seed.index,
        )
        seed.clear()
        return signal

    return hcsm_signal


def rename_mode(metrics: dict[str, Any]) -> dict[str, Any]:
    copied = dict(metrics)
    copied["mode"] = "hcsm50"
    return copied


def run(force: bool = False) -> dict[str, Any]:
    base = load_module(BASE_SCRIPT_PATH, "snc02_hcsm50_base")
    control = load_module(CONTROL_SCRIPT_PATH, "snc02_hcsm50_control")
    stage_a = load_module(STAGE_A_SCRIPT_PATH, "snc02_hcsm50_context")
    risk = load_module(RISK_PATH, "snc02_hcsm50_risk")
    context = stage_a.load_context(control)
    base_evidence = json.loads(BASE_ARTIFACT_PATH.read_text(encoding="utf-8"))
    ema50 = ema50_values(context)
    base.csm_signal = make_hcsm_signal(base, ema50)

    primary = base.run_backtest(
        context,
        control,
        risk,
        mode="csm02",
        start=0,
        right=context.book.count,
        slippage=BASE_SLIPPAGE,
    )
    canonical = base.run_backtest(
        context,
        control,
        risk,
        mode="csm02",
        start=0,
        right=CANONICAL_RIGHT,
        slippage=BASE_SLIPPAGE,
    )
    stress = base.run_backtest(
        context,
        control,
        risk,
        mode="csm02",
        start=0,
        right=context.book.count,
        slippage=STRESS_SLIPPAGE,
    )
    trades, trend_summary = base.augment_trade_paths(
        context,
        primary["trades"],
        context.book.count,
    )

    missed_major = base_evidence["opportunity_summary"]["missed_major_by_control"]
    delayed_signals = [
        row
        for row in primary["signals"]
        if row["signal_kind"] == "delayed_slope_maturation_ema50"
    ]
    scheduled_origins = {
        int(row["seed_index"]) for row in delayed_signals if row["scheduled"]
    }
    recovered_major = [
        row for row in missed_major if int(row["cross_index"]) in scheduled_origins
    ]
    delayed_trades = [
        row
        for row in trades
        if row["signal_kind"] == "delayed_slope_maturation_ema50"
    ]
    control_trend = base_evidence["trend_summaries"]["control"]
    unfiltered_trend = base_evidence["trend_summaries"]["csm02"]
    continuation = (
        len(recovered_major) >= 1
        and int(trend_summary["major_positive_exit_count"])
        >= int(control_trend["major_positive_exit_count"])
        and float(trend_summary["major_mfe_weighted_capture"])
        >= float(control_trend["major_mfe_weighted_capture"])
        and bool(trend_summary["august_09_long_to_terminal"])
        and any(float(row["gross_return_pct"]) > 0.0 for row in delayed_trades)
        and len(trades) <= int(unfiltered_trend["campaigns"])
    )

    payload = {
        "schema": "hype-1d-ma7-snc02-ema50-hierarchical-discovery-v1",
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "status": "POST_REVEAL_DIAGNOSTIC_TREND_FIRST_NOT_PROMOTED_NOT_LIVE_READY",
        "strategy_id": "HYPE-1D-MA7-SNC02-HCSM50",
        "mechanism": {
            "exact_snc02_priority": True,
            "ema": "EMA(close, span=50, adjust=False, min_periods=50)",
            "ema_applies_to": "delayed maturation signals only",
            "delayed_requirements": [
                "close remains on target SMA7 side",
                "directional SMA7 slope / ATR7 >= 0.02",
                "close on target EMA50 side",
                "EMA50 one-day slope aligned",
            ],
            "profit_or_risk_exit": False,
        },
        "extended": rename_mode(primary["metrics"]),
        "canonical": rename_mode(canonical["metrics"]),
        "stress_8bps": rename_mode(stress["metrics"]),
        "trend_summary": trend_summary,
        "opportunity_summary": {
            "missed_major_by_control_count": len(missed_major),
            "recovered_major_count": len(recovered_major),
            "recovered_major": recovered_major,
            "delayed_signal_count": len(delayed_signals),
            "scheduled_delayed_origin_count": len(scheduled_origins),
            "delayed_trade_count": len(delayed_trades),
            "profitable_delayed_trade_count": sum(
                float(row["gross_return_pct"]) > 0.0 for row in delayed_trades
            ),
        },
        "comparison": {
            "control_extended": base_evidence["extended"]["control"],
            "control_trend": control_trend,
            "unfiltered_csm02_extended": base_evidence["extended"]["csm02"],
            "unfiltered_csm02_trend": unfiltered_trend,
            "lag_screen_run": False,
            "mdd_primary_gate": False,
        },
        "ledger": {
            "trades": trades,
            "signals": primary["signals"],
            "actions": primary["actions"],
        },
        "verdict": {
            "continuation_worthy": continuation,
            "decision": (
                "CONTINUATION_WORTHY_POST_REVEAL"
                if continuation
                else "TREND_FIRST_GATE_FAILED"
            ),
            "registered_version": None,
            "changes_v7_1": False,
            "runner_change_authorized": False,
        },
        "pins": {
            "contract_sha256": sha256(CONTRACT_PATH),
            "script_sha256": sha256(Path(__file__).resolve()),
            "base_script_sha256": sha256(BASE_SCRIPT_PATH),
            "base_artifact_sha256": sha256(BASE_ARTIFACT_PATH),
            "control_script_sha256": sha256(CONTROL_SCRIPT_PATH),
            "stage_a_context_sha256": sha256(STAGE_A_SCRIPT_PATH),
            "risk_replay_sha256": sha256(RISK_PATH),
        },
        "notes": [
            "EMA50 is causal and only filters supplementary delayed tickets.",
            "No one-day lag screen or MDD-first selection was performed.",
            "All evidence is revealed-history diagnostic, not clean OOS.",
        ],
    }
    document = (
        json.dumps(sanitize(payload), ensure_ascii=False, sort_keys=True, indent=2)
        + "\n"
    )
    sidecar = Path(f"{OUTPUT_PATH}.sha256")
    if (OUTPUT_PATH.exists() or sidecar.exists()) and not force:
        raise RuntimeError(f"locked artifact exists: {OUTPUT_PATH.name}")
    OUTPUT_PATH.write_text(document, encoding="utf-8")
    digest = hashlib.sha256(document.encode()).hexdigest()
    sidecar.write_text(f"{digest}  {OUTPUT_PATH.name}\n", encoding="utf-8")
    return {"output": str(OUTPUT_PATH), "sha256": digest, "payload": payload}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if not args.run:
        print(
            json.dumps(
                {
                    "status": "CONTRACT_FROZEN_NOT_RUN",
                    "contract": str(CONTRACT_PATH),
                    "candidate": "HCSM50",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    result = run(force=args.force)
    payload = result["payload"]
    print(
        json.dumps(
            {
                "output": result["output"],
                "sha256": result["sha256"],
                "extended": payload["extended"],
                "trend_summary": payload["trend_summary"],
                "opportunity_summary": payload["opportunity_summary"],
                "verdict": payload["verdict"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
