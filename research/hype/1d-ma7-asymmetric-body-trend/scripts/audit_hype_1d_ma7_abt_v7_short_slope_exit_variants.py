"""Audit short MA7 slope-exit variants on registered HYPE-1D-MA7-ABT-V7."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from types import ModuleType
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CONTRACT_PATH = (
    FAMILY_DIR / "specs/hype-1d-ma7-abt-v7-short-slope-exit-variants-contract-2026-08-11.md"
)
OUTPUT_PATH = ARTIFACT_DIR / "hype_1d_ma7_abt_v7_short_slope_exit_variants_2026-08-11.json"

BASE_ABLATION_PATH = SCRIPT_DIR / "audit_hype_1d_ma7_abt_v7_four_mechanism_ablation.py"

FULL = (0, 432)
BLOCKS = tuple((left, left + 54) for left in range(0, 432, 54))
RECENT_SLICES = {"1d": 1, "7d": 7, "1m": 30, "3m": 90, "6m": 180, "1y": 365}
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
EXPECTED_V7_RETURN = 711.035936775286
EXPECTED_V7_1H_MDD = -18.395542229660567
EXPECTED_V7_TRADES = 20


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


@dataclass(frozen=True, slots=True)
class Variant:
    name: str
    mode: str
    short_slope_exit_lookback: int
    close_above_ma_buffer_atr: float | None
    description: str

    def canonical(self) -> dict[str, Any]:
        return asdict(self)


def variants() -> list[Variant]:
    return [
        Variant("CTRL_EXACT_V7", "native", 1, None, "exact registered V7"),
        Variant("SHORT_SLOPE_LOOKBACK_2", "native", 2, None, "short slope exit lookback 1 -> 2"),
        Variant("SHORT_SLOPE_LOOKBACK_3", "native", 3, None, "short slope exit lookback 1 -> 3"),
        Variant(
            "SHORT_SLOPE_UP_AND_CLOSE_ABOVE_MA",
            "slope_up_close_above_ma",
            1,
            0.0,
            "short exits only when MA7 rises and close is above MA7",
        ),
        Variant(
            "SHORT_SLOPE_UP_AND_CLOSE_ABOVE_MA_0P25ATR",
            "slope_up_close_above_ma",
            1,
            0.25,
            "short exits only when MA7 rises and close is at least 0.25ATR above MA7",
        ),
        Variant(
            "SHORT_SLOPE_UP_AND_CLOSE_ABOVE_MA_0P50ATR",
            "slope_up_close_above_ma",
            1,
            0.50,
            "short exits only when MA7 rises and close is at least 0.50ATR above MA7",
        ),
        Variant(
            "SHORT_SLOPE_UP_AND_CLOSE_ABOVE_MA_0P75ATR",
            "slope_up_close_above_ma",
            1,
            0.75,
            "short exits only when MA7 rises and close is at least 0.75ATR above MA7",
        ),
    ]


def start_for(window: tuple[int, int]) -> int:
    left, right = window
    return left if left == 0 or right - left == 1 else left + 1


def custom_signal_exit(variant: Variant) -> Any:
    def signal_exit(config: Any, book: Any, features: Any, index: int, bars_held: int) -> str:
        left = index - int(config.exit_confirm_days) + 1
        if left >= 0:
            crossed = True
            for offset in range(left, index + 1):
                ma = features.ma7[offset]
                atr = features.atr7[offset]
                if (
                    not np.isfinite(ma)
                    or not np.isfinite(atr)
                    or int(config.side) * (book.close[offset] - ma)
                    >= -float(config.exit_buffer_atr) * atr
                ):
                    crossed = False
                    break
            if crossed:
                return "ma7_hysteresis_exit"
        if int(config.slope_exit_lookback) > 0:
            prior = index - int(config.slope_exit_lookback)
            if prior >= 0 and np.isfinite(features.ma7[index]) and np.isfinite(features.ma7[prior]):
                if int(config.side) < 0 and variant.mode == "slope_up_close_above_ma":
                    atr = features.atr7[index]
                    close = book.close[index]
                    ma = features.ma7[index]
                    buffer = float(variant.close_above_ma_buffer_atr or 0.0)
                    if (
                        features.ma7[index] - features.ma7[prior] >= 0.0
                        and np.isfinite(atr)
                        and np.isfinite(close)
                        and np.isfinite(ma)
                        and close - ma >= buffer * atr
                    ):
                        return "ma7_slope_exit"
                elif int(config.side) * (features.ma7[index] - features.ma7[prior]) <= 0.0:
                    return "ma7_slope_exit"
        if int(config.max_hold_days) > 0 and bars_held >= int(config.max_hold_days):
            return "max_hold"
        return ""

    return signal_exit


def build_function(
    base: ModuleType,
    transition: ModuleType,
    context: Any,
    variant: Variant,
    *,
    entry_signal: Any,
    native_entry_signal: Any,
    leverage_policy: Any,
    rsi6: Any,
    handoff_recorder: Any,
    repair_recorder: Any,
) -> tuple[Any, str]:
    arm = base.Arm(
        name=variant.name,
        group="short_slope_exit_variant",
        description=variant.description,
        transition_config=transition.TransitionRepairConfig(variant.name),
    )
    pehc_config = transition.fixed_v6_config()
    oapp_config = base.make_oapp(transition, arm)
    source = transition._BASE._capture_exact_source(context)
    digest = hashlib.sha256(variant.name.encode()).hexdigest()[:12]
    function_name = f"v7_short_slope_exit_{digest}_backtest"
    source = transition._replace_once(
        source,
        "def v3_ma_only_backtest(",
        f"def {function_name}(",
        "function name",
    )
    source = transition._BASE._apply_state(source)
    source = transition._BASE._apply_exits(source)
    source = transition._PEHC._apply_pehc_state(source)
    source = transition._PEHC._apply_pehc_arm(source)
    source = transition._PEHC._apply_pehc_daily(source)
    source = transition._PEHC._apply_pehc_intraday(source)
    source = transition._apply_repair_state(source)
    source = transition._apply_repair_exits(source)
    source = transition._apply_repair_entry(source)
    namespace = dict(context.engine.__dict__)
    namespace.update(
        {
            "close_entry_signal": entry_signal,
            "_target_quantity": leverage_policy,
            "wtl_set_entry_context": leverage_policy.set_entry_context,
            "wtl_last_entry_leverage": lambda: leverage_policy.last_entry_leverage,
            "wtl_rsi6": rsi6,
            "wtl_long_exit": oapp_config.long_exit,
            "wtl_short_exit": oapp_config.short_exit,
            "wtl_short_rsi": oapp_config.short_rsi,
            "wtl_roundtrip_guard": oapp_config.roundtrip_guard,
            "wtl_exit_decision": transition._BASE.lifecycle_exit_decision,
            "pehc_enabled": pehc_config.enabled,
            "pehc_entry_enabled": pehc_config.entry_enabled,
            "pehc_blocked_origin_indices": frozenset(pehc_config.blocked_origin_indices),
            "pehc_allowed_origin_indices": frozenset(pehc_config.allowed_origin_indices),
            "pehc_expiry_days": pehc_config.expiry_days,
            "pehc_slope_threshold": pehc_config.slope_threshold,
            "pehc_chase_cap_atr": pehc_config.chase_cap_atr,
            "pehc_execution": pehc_config.execution,
            "pehc_handoff_eligibility": transition._PEHC.handoff_eligibility,
            "pehc_record": handoff_recorder,
            "repair_entry_signal": entry_signal,
            "repair_native_entry_signal": native_entry_signal,
            "repair_cooldown_mode": arm.transition_config.cooldown_mode,
            "repair_same_side_cooldown_days": arm.transition_config.same_side_cooldown_days,
            "repair_record": repair_recorder,
        }
    )
    compiled = compile(source, f"<v7-short-slope-exit-{variant.name}>", "exec")
    exec(compiled, namespace)
    if variant.mode == "slope_up_close_above_ma":
        namespace["signal_exit"] = custom_signal_exit(variant)
    hash_payload = source + "\n" + json.dumps(variant.canonical(), sort_keys=True)
    return namespace[function_name], hashlib.sha256(hash_payload.encode()).hexdigest()


def run_raw(
    base: ModuleType,
    transition: ModuleType,
    context: Any,
    variant: Variant,
    *,
    window: tuple[int, int],
    slippage: float,
    include_funding: bool,
    signal_lag: int,
    retain: bool,
) -> Any:
    if not (0 <= window[0] < window[1] <= context.book.count):
        raise ValueError("invalid window")
    rsi6 = transition._BASE.wilder_rsi6(context.book.close)
    short_config = replace(
        context.short_config,
        slope_exit_lookback=variant.short_slope_exit_lookback,
    )
    oapp_config = transition._PEHC.fixed_oapp_config(short_rsi_enabled=True)
    native_entry_signal = transition._BASE.EntryQualitySignal(context.engine, oapp_config.entry)
    entry_signal = transition.TransitionEntrySignal(
        native_entry_signal,
        context.long_config,
        short_config,
        transition.TransitionRepairConfig(variant.name),
        rsi6,
    )
    leverage_policy = transition._BASE.LeveragePolicy(context, None)
    handoff_recorder = transition._PEHC.HandoffRecorder()
    repair_recorder = transition.RepairRecorder()
    function, source_hash = build_function(
        base,
        transition,
        context,
        variant,
        entry_signal=entry_signal,
        native_entry_signal=native_entry_signal,
        leverage_policy=leverage_policy,
        rsi6=rsi6,
        handoff_recorder=handoff_recorder,
        repair_recorder=repair_recorder,
    )
    raw = function(
        context.book,
        context.features,
        long_config=context.long_config,
        short_config=short_config,
        start_index=start_for(window),
        terminal_index=window[1],
        slippage=slippage,
        signal_lag=signal_lag,
        include_funding=include_funding,
        retain=retain,
    )
    if bool(raw.metrics.get("bankrupt_intraday")):
        raise RuntimeError(f"{variant.name} became bankrupt")
    return transition.TransitionRepairExecutionResult(
        config=transition.TransitionRepairConfig(variant.name),
        raw=raw,
        source_sha256=source_hash,
        signal_events=list(entry_signal.events),
        cooldown_events=list(repair_recorder.events),
        native_entry_events=list(native_entry_signal.events),
        handoff_events=list(handoff_recorder.events),
        activation_counts=transition._counts(
            raw,
            list(entry_signal.events),
            list(repair_recorder.events),
            list(handoff_recorder.events),
        ),
        rsi6=rsi6,
    )


def focus_trades(raw: Any) -> dict[str, Any]:
    rows = {}
    for trade in raw.trades:
        entry = str(trade.get("entry_ts", ""))
        if entry.startswith("2025-11-03"):
            rows["short_2025_11_03"] = trade
        if entry.startswith("2026-07-12"):
            rows["short_2026_07_12"] = trade
    return rows


def normalize(
    full_ablation: ModuleType,
    context: Any,
    result: Any,
    *,
    days: int,
    slippage: float,
    include_funding: bool,
) -> dict[str, Any]:
    replay = full_ablation.chronological_replay(
        context,
        result.raw,
        slippage=slippage,
        include_funding=include_funding,
    )
    row = full_ablation.normalize(result.raw, replay, result, days=days)
    row["activation_counts"] = dict(result.activation_counts)
    row["source_sha256"] = result.source_sha256
    row["exit_reason_counts"] = {
        reason: sum(str(trade.get("exit_reason")) == reason for trade in result.raw.trades)
        for reason in sorted({str(trade.get("exit_reason")) for trade in result.raw.trades})
    }
    row["focus_trades"] = focus_trades(result.raw)
    return row


def run_once(
    base: ModuleType,
    transition: ModuleType,
    full_ablation: ModuleType,
    context: Any,
    variant: Variant,
    *,
    window: tuple[int, int],
    slippage: float,
    include_funding: bool,
    signal_lag: int,
    retain: bool,
) -> dict[str, Any]:
    result = run_raw(
        base,
        transition,
        context,
        variant,
        window=window,
        slippage=slippage,
        include_funding=include_funding,
        signal_lag=signal_lag,
        retain=retain,
    )
    return normalize(
        full_ablation,
        context,
        result,
        days=window[1] - window[0],
        slippage=slippage,
        include_funding=include_funding,
    )


def base_verdict(row: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    ret_delta = row["net_return_pct"] - control["net_return_pct"]
    mdd_delta = row["chronological_1h_mdd_pct"] - control["chronological_1h_mdd_pct"]
    return {
        "ret_delta_vs_v7_pp": ret_delta,
        "mdd_delta_vs_v7_pp": mdd_delta,
        "trade_delta_vs_v7": row["closed_trades"] - control["closed_trades"],
        "full_dual_better": ret_delta > 0.0 and mdd_delta >= -1e-8,
        "interesting": ret_delta > 0.0 or mdd_delta > 0.0,
    }


def stress_verdict(stress: dict[str, dict[str, Any]], control: dict[str, Any]) -> dict[str, Any]:
    base_row = stress["base_full"]
    ret_delta = base_row["net_return_pct"] - control["net_return_pct"]
    mdd_delta = base_row["chronological_1h_mdd_pct"] - control["chronological_1h_mdd_pct"]
    blocks = [row for key, row in stress.items() if key.startswith("block_")]
    block_positive = sum(row["net_return_pct"] > 0.0 for row in blocks)
    passed = (
        ret_delta > 0.0
        and mdd_delta >= -1e-8
        and stress["slippage_8bps"]["net_return_pct"] > 0.0
        and stress["lag_1d"]["net_return_pct"] > 0.0
        and block_positive == len(blocks)
    )
    if passed:
        decision = "POST_REVEAL_CANDIDATE_ONLY"
    elif ret_delta > 0.0 and mdd_delta < 0.0:
        decision = "FAIL / higher-return-higher-risk"
    elif base_row["closed_trades"] != control["closed_trades"]:
        decision = "FAIL / path-disruption"
    else:
        decision = "FAIL"
    return {
        "ret_delta_vs_v7_pp": ret_delta,
        "mdd_delta_vs_v7_pp": mdd_delta,
        "trade_delta_vs_v7": base_row["closed_trades"] - control["closed_trades"],
        "block_positive_count": block_positive,
        "block_count": len(blocks),
        "decision": decision,
    }


def run_stress(
    base: ModuleType,
    transition: ModuleType,
    full_ablation: ModuleType,
    context: Any,
    variant: Variant,
) -> dict[str, Any]:
    stress: dict[str, dict[str, Any]] = {}
    for key, window, slippage, include_funding, signal_lag in [
        ("base_full", FULL, BASE_SLIPPAGE, True, 0),
        ("slippage_8bps", FULL, STRESS_SLIPPAGE, True, 0),
        ("funding_off", FULL, BASE_SLIPPAGE, False, 0),
        ("lag_1d", FULL, BASE_SLIPPAGE, True, 1),
    ]:
        stress[key] = run_once(
            base,
            transition,
            full_ablation,
            context,
            variant,
            window=window,
            slippage=slippage,
            include_funding=include_funding,
            signal_lag=signal_lag,
            retain=False,
        )
    for block_index, window in enumerate(BLOCKS):
        stress[f"block_{block_index:02d}"] = run_once(
            base,
            transition,
            full_ablation,
            context,
            variant,
            window=window,
            slippage=BASE_SLIPPAGE,
            include_funding=True,
            signal_lag=0,
            retain=False,
        )
    terminal = FULL[1]
    for label, span in RECENT_SLICES.items():
        left = max(0, terminal - span)
        stress[f"recent_{label}"] = run_once(
            base,
            transition,
            full_ablation,
            context,
            variant,
            window=(left, terminal),
            slippage=BASE_SLIPPAGE,
            include_funding=True,
            signal_lag=0,
            retain=False,
        )
    return stress


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if not args.run:
        raise SystemExit("use --run to execute the frozen diagnostic")

    base = load_module(BASE_ABLATION_PATH, "short_slope_base")
    transition = load_module(base.TRANSITION_PATH, "short_slope_transition")
    full_ablation = load_module(base.FULL_ABLATION_PATH, "short_slope_full_ablation")
    v7_audit = load_module(base.V7_AUDIT_PATH, "short_slope_v7_context")
    base2 = v7_audit.load_module(v7_audit.BASE_2X_AUDIT_PATH, "short_slope_base2")
    _, _, _, _, context, _ = v7_audit.load_runtime(base2)

    rows: dict[str, Any] = {}
    varlist = variants()
    control_variant = varlist[0]
    control = run_once(
        base,
        transition,
        full_ablation,
        context,
        control_variant,
        window=FULL,
        slippage=BASE_SLIPPAGE,
        include_funding=True,
        signal_lag=0,
        retain=True,
    )
    if not (
        math.isclose(control["net_return_pct"], EXPECTED_V7_RETURN, abs_tol=0.08)
        and math.isclose(control["chronological_1h_mdd_pct"], EXPECTED_V7_1H_MDD, abs_tol=0.03)
        and int(control["closed_trades"]) == EXPECTED_V7_TRADES
    ):
        raise RuntimeError(f"V7 anchor drift: {control}")
    rows[control_variant.name] = {
        "variant": control_variant.canonical(),
        "base_full": control,
        "base_verdict": {
            "ret_delta_vs_v7_pp": 0.0,
            "mdd_delta_vs_v7_pp": 0.0,
            "trade_delta_vs_v7": 0,
            "full_dual_better": False,
            "interesting": False,
        },
    }
    selected: list[Variant] = []
    for variant in varlist[1:]:
        print(f"[base] {variant.name}")
        row = run_once(
            base,
            transition,
            full_ablation,
            context,
            variant,
            window=FULL,
            slippage=BASE_SLIPPAGE,
            include_funding=True,
            signal_lag=0,
            retain=True,
        )
        verdict = base_verdict(row, control)
        rows[variant.name] = {
            "variant": variant.canonical(),
            "base_full": row,
            "base_verdict": verdict,
        }
        if verdict["interesting"]:
            selected.append(variant)
    if not selected:
        selected = varlist[1:]

    stressed: dict[str, Any] = {}
    for variant in selected:
        print(f"[stress] {variant.name}")
        stress = run_stress(base, transition, full_ablation, context, variant)
        stressed[variant.name] = {
            "variant": variant.canonical(),
            "stress": stress,
            "verdict": stress_verdict(stress, control),
        }

    payload = {
        "schema": "hype-1d-ma7-abt-v7-short-slope-exit-variants-v1",
        "status": "COMPLETED_POST_REVEAL_DIAGNOSTIC",
        "research_state": "V7 unchanged / short slope exit variants diagnostic only / not promoted / not live-ready",
        "contract": str(CONTRACT_PATH.relative_to(FAMILY_DIR)),
        "control": rows[control_variant.name],
        "results": rows,
        "stressed": stressed,
        "market": "Binance USD-M HYPEUSDT perpetual",
        "timeframes": {"decision": "1d UTC", "risk_replay": "1h"},
        "data_range": {
            "start": str(context.book.ts[0]),
            "end": str(context.book.ts[431]),
            "terminal_ts": str(context.book.terminal_ts),
            "daily_bars": 432,
        },
        "cost_model": {
            "fee_per_fill": float(context.engine.FEE),
            "base_slippage_per_fill": BASE_SLIPPAGE,
            "stress_slippage_per_fill": STRESS_SLIPPAGE,
            "funding": "actual Binance funding events when include_funding=true",
        },
        "pins": {
            "contract_sha256": sha256(CONTRACT_PATH),
            "audit_script_sha256": sha256(Path(__file__).resolve()),
            "base_runner_sha256": sha256(BASE_ABLATION_PATH),
        },
        "registered": False,
        "promoted": False,
        "live_ready": False,
        "exact_v7_changed": False,
        "clean_oos_claim": False,
    }
    digest = write_locked(payload)
    summary = {
        "status": payload["status"],
        "artifact": str(OUTPUT_PATH),
        "artifact_sha256": digest,
        "base": [
            {
                "name": name,
                "ret": round(row["base_full"]["net_return_pct"], 2),
                "mdd": round(row["base_full"]["chronological_1h_mdd_pct"], 2),
                "trades": row["base_full"]["closed_trades"],
                "ma7_slope_exit": row["base_full"]["exit_reason_counts"].get("ma7_slope_exit", 0),
                "max_hold": row["base_full"]["exit_reason_counts"].get("max_hold", 0),
                "decision": stressed.get(name, {}).get("verdict", {}).get("decision"),
            }
            for name, row in rows.items()
        ],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
