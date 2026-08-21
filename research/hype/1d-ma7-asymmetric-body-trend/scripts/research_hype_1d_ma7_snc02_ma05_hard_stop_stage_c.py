"""Run frozen SNC02 MA05 plus fixed-ATR hard-stop Stage C."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import math
from pathlib import Path
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
    / "specs/hype-1d-ma7-snc02-ma05-hard-stop-stage-c-contract-2026-08-20.md"
)
CONTROL_SCRIPT_PATH = (
    SCRIPT_DIR / "research_hype_1d_ma7_symmetric_naked_cross_slope.py"
)
STAGE_A_SCRIPT_PATH = (
    SCRIPT_DIR / "research_hype_1d_ma7_snc02_risk_overlay_oat.py"
)
STAGE_A_ARTIFACT_PATH = (
    ARTIFACT_DIR / "hype_1d_ma7_snc02_risk_overlay_oat_2026-08-20.json"
)
RISK_PATH = SCRIPT_DIR / "hype_1d_ma7_trend_phase_risk_metrics.py"
OUTPUT_PATH = (
    ARTIFACT_DIR / "hype_1d_ma7_snc02_ma05_hard_stop_stage_c_2026-08-20.json"
)

BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
CANONICAL_RIGHT = 432
MA_EXIT_BUFFER_ATR = 0.5
RETURN_RETENTION_FRACTION = 0.50
LATEST_CAPTURE_FRACTION = 0.60
RECENT_SLICES = {"1d": 1, "7d": 7, "1m": 30, "3m": 90, "6m": 180, "1y": 365}


@dataclass(frozen=True, slots=True)
class StageCArm:
    arm_id: str
    hard_stop_atr: float | None


ARMS = (
    StageCArm("MA05_CTRL", None),
    StageCArm("MA05_HS10", 1.0),
    StageCArm("MA05_HS15", 1.5),
    StageCArm("MA05_HS20", 2.0),
)


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


def arm_config(arm: StageCArm) -> dict[str, Any]:
    return {
        "arm_id": arm.arm_id,
        "ma_exit_buffer_atr": MA_EXIT_BUFFER_ATR,
        "hard_stop_atr": arm.hard_stop_atr,
        "entry_leverage": 1.0,
    }


def stage_a_arm(stage_a: ModuleType, arm: StageCArm) -> Any:
    return stage_a.Arm(
        arm_id=arm.arm_id,
        ma_exit_buffer_atr=MA_EXIT_BUFFER_ATR,
        hard_stop_atr=arm.hard_stop_atr,
    )


def hard_stop_reason(arm: StageCArm) -> str | None:
    if arm.hard_stop_atr is None:
        return None
    token = f"{arm.hard_stop_atr:.1f}".replace(".", "p")
    return f"hard_stop_{token}atr"


def normalize_stop_labels(result: dict[str, Any], arm: StageCArm) -> dict[str, Any]:
    """Replace the Stage A generic stop label with the pinned arm level."""

    reason = hard_stop_reason(arm)
    if reason is None:
        return result
    generic = "hard_stop_2p5atr"
    counts = result["metrics"]["exit_counts"]
    if generic in counts:
        counts[reason] = counts.pop(generic)
    for trade in result["trades"]:
        if trade["exit_reason"] == generic:
            trade["exit_reason"] = reason
    for action in result["actions"]:
        if action.get("reason") == generic:
            action["reason"] = reason
    return result


def index_at_or_after(context: Any, ts: str) -> int:
    target = pd.Timestamp(ts)
    return next(
        index
        for index, value in enumerate(context.book.ts)
        if pd.Timestamp(value) >= target
    )


def run(force: bool = False) -> dict[str, Any]:
    control = load_module(CONTROL_SCRIPT_PATH, "snc02_stage_c_control")
    stage_a = load_module(STAGE_A_SCRIPT_PATH, "snc02_stage_c_engine")
    risk = load_module(RISK_PATH, "snc02_stage_c_risk")
    context = stage_a.load_context(control)
    retained_stage_a = json.loads(STAGE_A_ARTIFACT_PATH.read_text(encoding="utf-8"))

    primary: dict[str, Any] = {}
    canonical: dict[str, Any] = {}
    stress: dict[str, Any] = {}
    recent: dict[str, Any] = {}
    calendar: dict[str, Any] = {}
    ledgers: dict[str, Any] = {}
    for arm in ARMS:
        engine_arm = stage_a_arm(stage_a, arm)
        extended_run = normalize_stop_labels(
            stage_a.run_arm(
                context,
                control,
                risk,
                engine_arm,
                start=0,
                right=context.book.count,
            ),
            arm,
        )
        canonical_run = normalize_stop_labels(
            stage_a.run_arm(
                context,
                control,
                risk,
                engine_arm,
                start=0,
                right=CANONICAL_RIGHT,
            ),
            arm,
        )
        primary[arm.arm_id] = extended_run["metrics"]
        canonical[arm.arm_id] = canonical_run["metrics"]
        ledgers[arm.arm_id] = {
            "trades": extended_run["trades"],
            "actions": extended_run["actions"],
        }

        stress[arm.arm_id] = {}
        for label, slippage, lag, funding in (
            ("slippage_8bps", STRESS_SLIPPAGE, 0, True),
            ("lag_1d", BASE_SLIPPAGE, 1, True),
            ("funding_off", BASE_SLIPPAGE, 0, False),
        ):
            result = normalize_stop_labels(
                stage_a.run_arm(
                    context,
                    control,
                    risk,
                    engine_arm,
                    start=0,
                    right=context.book.count,
                    slippage=slippage,
                    daily_action_lag=lag,
                    include_funding=funding,
                ),
                arm,
            )
            stress[arm.arm_id][label] = result["metrics"]

        recent[arm.arm_id] = {}
        for label, days in RECENT_SLICES.items():
            result = normalize_stop_labels(
                stage_a.run_arm(
                    context,
                    control,
                    risk,
                    engine_arm,
                    start=max(0, context.book.count - days),
                    right=context.book.count,
                ),
                arm,
            )
            recent[arm.arm_id][label] = result["metrics"]

        calendar[arm.arm_id] = {}
        for label, (left, right) in {
            "2025_partial": (
                0,
                index_at_or_after(context, "2026-01-01T00:00:00Z"),
            ),
            "2026_ytd": (
                index_at_or_after(context, "2026-01-01T00:00:00Z"),
                context.book.count,
            ),
        }.items():
            result = normalize_stop_labels(
                stage_a.run_arm(
                    context,
                    control,
                    risk,
                    engine_arm,
                    start=left,
                    right=right,
                ),
                arm,
            )
            calendar[arm.arm_id][label] = result["metrics"]

    parity: dict[str, dict[str, bool]] = {}
    for label, actual, expected in (
        (
            "extended",
            primary["MA05_CTRL"],
            retained_stage_a["primary_extended"]["MA05"],
        ),
        (
            "canonical",
            canonical["MA05_CTRL"],
            retained_stage_a["canonical"]["MA05"],
        ),
    ):
        checks = {
            key: math.isclose(
                float(actual[key]),
                float(expected[key]),
                rel_tol=0.0,
                abs_tol=2e-10,
            )
            for key in (
                "net_return_pct",
                "chronological_1h_mdd_pct",
                "closed_trades",
                "cost_pct_initial",
                "funding_pct_initial",
            )
        }
        if not all(checks.values()):
            raise RuntimeError(f"{label} MA05 parity failed: {checks}")
        parity[label] = checks

    baseline_return = float(primary["MA05_CTRL"]["net_return_pct"])
    baseline_latest = next(
        row
        for row in ledgers["MA05_CTRL"]["trades"]
        if row["entry_ts"] == "2026-08-09T00:00:00+00:00"
    )
    baseline_latest_return = float(baseline_latest["net_return_pct"])
    verdict: dict[str, Any] = {}
    for arm in ARMS:
        arm_id = arm.arm_id
        metrics = primary[arm_id]
        latest_trade = next(
            (
                row
                for row in reversed(ledgers[arm_id]["trades"])
                if row["entry_ts"] == "2026-08-09T00:00:00+00:00"
            ),
            None,
        )
        mdd20 = float(metrics["chronological_1h_mdd_pct"]) >= -20.0
        robust = (
            float(metrics["net_return_pct"]) > 0.0
            and float(metrics["profit_factor"]) >= 1.0
            and float(stress[arm_id]["slippage_8bps"]["net_return_pct"]) > 0.0
            and float(stress[arm_id]["lag_1d"]["net_return_pct"]) > 0.0
        )
        return_retention = (
            float(metrics["net_return_pct"])
            >= RETURN_RETENTION_FRACTION * baseline_return
        )
        latest_capture = (
            latest_trade is not None
            and latest_trade["exit_reason"] == "terminal_flatten"
            and float(latest_trade["net_return_pct"])
            >= LATEST_CAPTURE_FRACTION * baseline_latest_return
        )
        verdict[arm_id] = {
            "mdd20_pass": mdd20,
            "robustness_pass": robust,
            "return_retention_pass": return_retention,
            "latest_trend_capture_pass": latest_capture,
            "continuation_candidate": (
                mdd20 and robust and return_retention and latest_capture
            ),
            "latest_august_long": latest_trade,
            "hard_stop_count": int(
                metrics["exit_counts"].get(hard_stop_reason(arm) or "", 0)
            ),
            "status": "POST_REVEAL_DIAGNOSTIC_ONLY",
        }

    payload = {
        "schema": "hype-1d-ma7-snc02-ma05-hard-stop-stage-c-v1",
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "status": "DIAGNOSTIC_ONLY_EXPLORE_NOT_PROMOTED_NOT_LIVE_READY",
        "strategy_id": "HYPE-1D-MA7-SNC02-MA05-HARD-STOP-STAGE-C",
        "arms": {arm.arm_id: arm_config(arm) for arm in ARMS},
        "execution": {
            "daily_conditions": "closed UTC day, next UTC open",
            "stop_path": "1h OHLC; adverse gap open else fixed stop reference",
            "fee_per_fill": float(context.engine.FEE),
            "base_slippage_per_fill": BASE_SLIPPAGE,
            "stress_slippage_per_fill": STRESS_SLIPPAGE,
            "funding": "actual Binance event timestamp/rate",
        },
        "gates": {
            "mdd_floor_pct": -20.0,
            "return_retention_fraction_of_ma05_control": RETURN_RETENTION_FRACTION,
            "latest_capture_fraction_of_ma05_control": LATEST_CAPTURE_FRACTION,
            "baseline_return_pct": baseline_return,
            "baseline_latest_august_long_return_pct": baseline_latest_return,
        },
        "data_audit": sanitize(context.market.audit),
        "primary_extended": primary,
        "canonical": canonical,
        "stress": stress,
        "recent_slices": recent,
        "calendar_flat_start": calendar,
        "ledgers": ledgers,
        "ma05_parity": parity,
        "verdict": verdict,
        "decision": {
            "stage_c_hard_stop_only": True,
            "stop_grid_extended_after_reveal": False,
            "registered_version": None,
            "changes_v7_1": False,
            "runner_change_authorized": False,
        },
        "pins": {
            "contract_sha256": sha256(CONTRACT_PATH),
            "script_sha256": sha256(Path(__file__).resolve()),
            "control_script_sha256": sha256(CONTROL_SCRIPT_PATH),
            "stage_a_engine_sha256": sha256(STAGE_A_SCRIPT_PATH),
            "stage_a_artifact_sha256": sha256(STAGE_A_ARTIFACT_PATH),
            "risk_engine_sha256": sha256(RISK_PATH),
        },
        "notes": [
            "All outcomes are revealed-history diagnostic evidence.",
            "The three ATR levels were frozen before the first Stage C result.",
            "A stop exit remains flat until a fresh qualified SNC02 signal.",
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
                    "arms": [arm_config(arm) for arm in ARMS],
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
                "primary_extended": payload["primary_extended"],
                "stress": payload["stress"],
                "verdict": payload["verdict"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
