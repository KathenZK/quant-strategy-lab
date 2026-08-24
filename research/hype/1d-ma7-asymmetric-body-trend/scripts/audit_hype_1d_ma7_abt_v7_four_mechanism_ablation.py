"""Audit four fixed repair mechanisms on registered HYPE-1D-MA7-ABT-V7."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
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
    FAMILY_DIR
    / "specs/hype-1d-ma7-abt-v7-four-mechanism-ablation-contract-2026-08-11.md"
)
OUTPUT_PATH = ARTIFACT_DIR / "hype_1d_ma7_abt_v7_four_mechanism_ablation_2026-08-11.json"

V7_AUDIT_PATH = SCRIPT_DIR / "audit_hype_1d_ma7_abt_v7_2x_leverage.py"
TRANSITION_PATH = SCRIPT_DIR / "hype_1d_ma7_v6_transition_repair_engine.py"
FULL_ABLATION_PATH = SCRIPT_DIR / "audit_hype_1d_ma7_abt_v6_full_parameter_ablation.py"

FULL = (0, 432)
BLOCKS = tuple((left, left + 54) for left in range(0, 432, 54))
RECENT_SLICES = {"1d": 1, "7d": 7, "1m": 30, "3m": 90, "6m": 180, "1y": 365}
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
EXPECTED_V7_RETURN = 711.0509737173086
EXPECTED_V7_1H_MDD = -18.391735672691013
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
class Arm:
    name: str
    group: str
    description: str
    transition_config: Any
    short_rsi_threshold: float = 20.0
    short_rsi_days: int = 2
    overbought_exhaustion_short: bool = False


class OverboughtEntrySignal:
    """TransitionEntrySignal wrapper with one flat-only overbought short rule."""

    def __init__(self, base: Any, *, enabled: bool, rsi6: np.ndarray) -> None:
        self.base = base
        self.enabled = enabled
        self.rsi6 = rsi6
        self.events = base.events

    def __getattr__(self, name: str) -> Any:
        return getattr(self.base, name)

    @staticmethod
    def _finite(*values: float) -> bool:
        return all(math.isfinite(float(value)) for value in values)

    def _overbought_short(self, book: Any, features: Any, index: int) -> bool:
        if not self.enabled or index < 5:
            return False
        close = float(book.close[index])
        prior_close = float(book.close[index - 1])
        ma7 = float(features.ma7[index])
        atr7 = float(features.atr7[index])
        if not self._finite(close, prior_close, ma7, atr7) or atr7 <= 0.0:
            return False
        recent = [float(self.rsi6[offset]) for offset in range(index - 4, index + 1)]
        if sum(math.isfinite(value) and value >= 70.0 for value in recent) < 3:
            return False
        distance = (ma7 - close) / atr7
        if not (distance > 0.10 and close < prior_close):
            return False
        self.base._record(
            "overbought_exhaustion_short",
            index,
            -1,
            rsi70_days=sum(math.isfinite(value) and value >= 70.0 for value in recent),
            distance_atr=distance,
            close=close,
            ma7=ma7,
        )
        return True

    def __call__(self, config: Any, book: Any, features: Any, index: int) -> bool:
        result = bool(self.base(config, book, features, index))
        if result or int(config.side) > 0:
            return result
        if self.base.cached_index != index:
            self.base._evaluate(book, features, index)
        if self.base.cached_decisions[-1]:
            return True
        if self._overbought_short(book, features, index):
            self.base.cached_decisions[-1] = True
            self.base.cached_sources[-1] = "overbought_exhaustion"
            return True
        return False


def make_oapp(transition: ModuleType, arm: Arm) -> Any:
    oapp = transition._PEHC.fixed_oapp_config(short_rsi_enabled=True)
    if arm.short_rsi_threshold == 20.0 and arm.short_rsi_days == 2:
        return oapp
    short_rsi = replace(
        oapp.short_rsi,
        threshold=arm.short_rsi_threshold,
        days=arm.short_rsi_days,
    )
    return replace(oapp, arm_id=f"{oapp.arm_id}_{arm.name}", short_rsi=short_rsi)


def build_variant_function(
    transition: ModuleType,
    context: Any,
    arm: Arm,
    *,
    entry_signal: Any,
    native_entry_signal: Any,
    leverage_policy: Any,
    rsi6: np.ndarray,
    handoff_recorder: Any,
    repair_recorder: Any,
) -> tuple[Any, str]:
    pehc_config = transition.fixed_v6_config()
    oapp_config = make_oapp(transition, arm)
    source = transition._BASE._capture_exact_source(context)
    digest = hashlib.sha256(arm.name.encode()).hexdigest()[:12]
    function_name = f"v7_four_mechanism_{digest}_backtest"
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
    compiled = compile(source, f"<v7-four-mechanism-{arm.name}>", "exec")
    exec(compiled, namespace)
    return namespace[function_name], hashlib.sha256(source.encode()).hexdigest()


def run_raw(transition: ModuleType, context: Any, arm: Arm, *, window: tuple[int, int], slippage: float, include_funding: bool, signal_lag: int, retain: bool) -> Any:
    if not (0 <= window[0] < window[1] <= context.book.count):
        raise ValueError("invalid window")
    rsi6 = transition._BASE.wilder_rsi6(context.book.close)
    native_entry_signal = transition._BASE.EntryQualitySignal(
        context.engine,
        make_oapp(transition, arm).entry,
    )
    base_entry_signal = transition.TransitionEntrySignal(
        native_entry_signal,
        context.long_config,
        context.short_config,
        arm.transition_config,
        rsi6,
    )
    entry_signal = OverboughtEntrySignal(
        base_entry_signal,
        enabled=arm.overbought_exhaustion_short,
        rsi6=rsi6,
    )
    leverage_policy = transition._BASE.LeveragePolicy(context, None)
    handoff_recorder = transition._PEHC.HandoffRecorder()
    repair_recorder = transition.RepairRecorder()
    function, source_hash = build_variant_function(
        transition,
        context,
        arm,
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
        short_config=context.short_config,
        start_index=window[0] if window[0] == 0 or window[1] - window[0] == 1 else window[0] + 1,
        terminal_index=window[1],
        slippage=slippage,
        signal_lag=signal_lag,
        include_funding=include_funding,
        retain=retain,
    )
    if bool(raw.metrics.get("bankrupt_intraday")):
        raise RuntimeError(f"{arm.name} became bankrupt")
    signal_events = list(base_entry_signal.events)
    cooldown_events = list(repair_recorder.events)
    handoff_events = list(handoff_recorder.events)
    result = transition.TransitionRepairExecutionResult(
        config=arm.transition_config,
        raw=raw,
        source_sha256=source_hash,
        signal_events=signal_events,
        cooldown_events=cooldown_events,
        native_entry_events=list(native_entry_signal.events),
        handoff_events=handoff_events,
        activation_counts=transition._counts(raw, signal_events, cooldown_events, handoff_events),
        rsi6=rsi6,
    )
    result.activation_counts["overbought_exhaustion_short"] = sum(
        row.get("event") == "overbought_exhaustion_short" for row in signal_events
    )
    return result


def normalize(full_ablation: ModuleType, context: Any, result: Any, *, days: int, slippage: float, include_funding: bool) -> dict[str, Any]:
    replay = full_ablation.chronological_replay(
        context,
        result.raw,
        slippage=slippage,
        include_funding=include_funding,
    )
    row = full_ablation.normalize(result.raw, replay, result, days=days)
    counts = result.activation_counts
    row.update(
        {
            "max_hold_exit": sum(str(trade.get("exit_reason", "")) == "max_hold" for trade in result.raw.trades),
            "ma7_slope_exit": sum(str(trade.get("exit_reason", "")) == "ma7_slope_exit" for trade in result.raw.trades),
            "overbought_exhaustion_short": counts.get("overbought_exhaustion_short", 0),
            "cooldown_blocked_long": sum(
                row.get("event") == "entry_blocked_cooldown" and row.get("side") == "long"
                for row in result.cooldown_events
            ),
            "cooldown_blocked_short": sum(
                row.get("event") == "entry_blocked_cooldown" and row.get("side") == "short"
                for row in result.cooldown_events
            ),
            "source_sha256": result.source_sha256,
        }
    )
    return row


def verdict(candidate: dict[str, Any], control: dict[str, Any], stress: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ret_delta = candidate["net_return_pct"] - control["net_return_pct"]
    mdd_delta = candidate["chronological_1h_mdd_pct"] - control["chronological_1h_mdd_pct"]
    blocks = [row for key, row in stress.items() if key.startswith("block_")]
    dual = ret_delta > 0.0 and mdd_delta >= -1e-8
    block_positive = sum(row["net_return_pct"] > 0.0 for row in blocks)
    passed = (
        dual
        and stress["slippage_8bps"]["net_return_pct"] > 0.0
        and stress["lag_1d"]["net_return_pct"] > 0.0
        and block_positive == len(blocks)
    )
    if passed:
        decision = "DIAGNOSTIC_CANDIDATE"
    elif ret_delta > 0.0 and mdd_delta < 0.0:
        decision = "FAIL / higher-return-higher-risk"
    elif candidate["closed_trades"] > control["closed_trades"] + 5:
        decision = "FAIL / noise-releasing"
    else:
        decision = "FAIL"
    return {
        "ret_delta_vs_v7_pp": ret_delta,
        "mdd_delta_vs_v7_pp": mdd_delta,
        "trade_delta_vs_v7": candidate["closed_trades"] - control["closed_trades"],
        "full_dual_better": dual,
        "block_positive_count": block_positive,
        "block_count": len(blocks),
        "decision": decision,
    }


def arms(transition: ModuleType) -> list[Arm]:
    cfg = transition.TransitionRepairConfig
    return [
        Arm("CTRL_EXACT_V7", "control", "exact V7", cfg("CTRL_EXACT_V7")),
        Arm(
            "M1_PENDING_RECLAIM_MATURITY",
            "M1",
            "raw cross pending up to 3d until buffer and slope mature",
            cfg(
                "M1_PENDING_RECLAIM_MATURITY",
                episode_enabled=True,
                episode_max_age_days=3,
                maturity_mode="BOTH",
                anti_chase_cap_atr=1.5,
            ),
        ),
        Arm(
            "M2_SHORT_RSI_RELAXED_TP",
            "M2",
            "short RSI take profit relaxed to RSI6<25 for 1d",
            cfg("M2_SHORT_RSI_RELAXED_TP"),
            short_rsi_threshold=25.0,
            short_rsi_days=1,
        ),
        Arm(
            "M3_OVERBOUGHT_EXHAUSTION_SHORT",
            "M3",
            "flat-only overbought exhaustion short with directional cooldown",
            cfg("M3_OVERBOUGHT_EXHAUSTION_SHORT", cooldown_mode="DIRECTIONAL"),
            overbought_exhaustion_short=True,
        ),
        Arm(
            "M4_POST_EXIT_COOLDOWN_OVERRIDE",
            "M4",
            "directional cooldown only; no new signal",
            cfg("M4_POST_EXIT_COOLDOWN_OVERRIDE", cooldown_mode="DIRECTIONAL"),
        ),
        Arm(
            "COMBO_ALL_FOUR",
            "combo",
            "M1+M2+M3+M4 interaction observation",
            cfg(
                "COMBO_ALL_FOUR",
                cooldown_mode="DIRECTIONAL",
                episode_enabled=True,
                episode_max_age_days=3,
                maturity_mode="BOTH",
                anti_chase_cap_atr=1.5,
            ),
            short_rsi_threshold=25.0,
            short_rsi_days=1,
            overbought_exhaustion_short=True,
        ),
    ]


def run_arm(transition: ModuleType, full_ablation: ModuleType, context: Any, arm: Arm, *, retain: bool) -> dict[str, Any]:
    stress: dict[str, dict[str, Any]] = {}
    retained_result = None
    for key, window, slippage, include_funding, signal_lag, keep in [
        ("base_full", FULL, BASE_SLIPPAGE, True, 0, retain),
        ("slippage_8bps", FULL, STRESS_SLIPPAGE, True, 0, False),
        ("funding_off", FULL, BASE_SLIPPAGE, False, 0, False),
        ("lag_1d", FULL, BASE_SLIPPAGE, True, 1, False),
    ]:
        result = run_raw(
            transition,
            context,
            arm,
            window=window,
            slippage=slippage,
            include_funding=include_funding,
            signal_lag=signal_lag,
            retain=keep,
        )
        if keep:
            retained_result = result
        stress[key] = normalize(
            full_ablation,
            context,
            result,
            days=window[1] - window[0],
            slippage=slippage,
            include_funding=include_funding,
        )
    for block_index, window in enumerate(BLOCKS):
        result = run_raw(
            transition,
            context,
            arm,
            window=window,
            slippage=BASE_SLIPPAGE,
            include_funding=True,
            signal_lag=0,
            retain=False,
        )
        stress[f"block_{block_index:02d}"] = normalize(
            full_ablation,
            context,
            result,
            days=window[1] - window[0],
            slippage=BASE_SLIPPAGE,
            include_funding=True,
        )
    recent: dict[str, dict[str, Any]] = {}
    for label, days in RECENT_SLICES.items():
        window = (max(0, FULL[1] - days), FULL[1])
        result = run_raw(
            transition,
            context,
            arm,
            window=window,
            slippage=BASE_SLIPPAGE,
            include_funding=True,
            signal_lag=0,
            retain=False,
        )
        recent[label] = normalize(
            full_ablation,
            context,
            result,
            days=window[1] - window[0],
            slippage=BASE_SLIPPAGE,
            include_funding=True,
        )
    if retained_result is None:
        raise RuntimeError("retained result missing")
    return {
        "arm": {
            "name": arm.name,
            "group": arm.group,
            "description": arm.description,
            "transition_config": arm.transition_config.canonical(),
            "short_rsi_threshold": arm.short_rsi_threshold,
            "short_rsi_days": arm.short_rsi_days,
            "overbought_exhaustion_short": arm.overbought_exhaustion_short,
        },
        "stress": stress,
        "recent": recent,
        "activation_counts": retained_result.activation_counts,
        "signal_events": retained_result.signal_events,
        "cooldown_events": retained_result.cooldown_events,
        "handoff_events": retained_result.handoff_events,
        "trades": retained_result.raw.trades,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if not args.run:
        raise SystemExit("use --run to execute the frozen diagnostic")

    v7_audit = load_module(V7_AUDIT_PATH, "v7_four_mech_context")
    base2 = v7_audit.load_module(v7_audit.BASE_2X_AUDIT_PATH, "v7_four_mech_base2")
    _, _, _, _, context, _ = v7_audit.load_runtime(base2)
    transition = load_module(TRANSITION_PATH, "v7_four_mech_transition")
    full_ablation = load_module(FULL_ABLATION_PATH, "v7_four_mech_full_ablation")

    rows: dict[str, Any] = {}
    for index, arm in enumerate(arms(transition), 1):
        print(f"[{index}/6] {arm.name}")
        rows[arm.name] = run_arm(transition, full_ablation, context, arm, retain=True)
    control = rows["CTRL_EXACT_V7"]["stress"]["base_full"]
    if not (
        math.isclose(control["net_return_pct"], EXPECTED_V7_RETURN, abs_tol=0.05)
        and math.isclose(control["chronological_1h_mdd_pct"], EXPECTED_V7_1H_MDD, abs_tol=0.02)
        and int(control["closed_trades"]) == EXPECTED_V7_TRADES
    ):
        raise RuntimeError(f"V7 anchor drift: {control}")
    for name, row in rows.items():
        row["verdict"] = (
            {"decision": "CONTROL"}
            if name == "CTRL_EXACT_V7"
            else verdict(row["stress"]["base_full"], control, row["stress"])
        )

    ranking = sorted(
        [
            {
                "name": name,
                "group": row["arm"]["group"],
                "net_return_pct": row["stress"]["base_full"]["net_return_pct"],
                "chronological_1h_mdd_pct": row["stress"]["base_full"]["chronological_1h_mdd_pct"],
                "closed_trades": row["stress"]["base_full"]["closed_trades"],
                "decision": row["verdict"]["decision"],
                "ret_delta_vs_v7_pp": row["verdict"].get("ret_delta_vs_v7_pp"),
                "mdd_delta_vs_v7_pp": row["verdict"].get("mdd_delta_vs_v7_pp"),
            }
            for name, row in rows.items()
        ],
        key=lambda item: item["net_return_pct"],
        reverse=True,
    )
    payload = {
        "schema": "hype-1d-ma7-abt-v7-four-mechanism-ablation-v1",
        "status": "COMPLETED_DIAGNOSTIC",
        "research_state": "V7 unchanged / diagnostic-only / not promoted / not live-ready",
        "contract": str(CONTRACT_PATH.relative_to(FAMILY_DIR)),
        "market": "Binance USD-M HYPEUSDT perpetual",
        "timeframes": {"decision": "1d UTC", "risk_replay": "1h"},
        "data_range": {
            "start": str(context.book.ts[FULL[0]]),
            "end": str(context.book.ts[FULL[1] - 1]),
            "terminal_ts": str(context.book.terminal_ts),
            "daily_bars": FULL[1] - FULL[0],
        },
        "cost_model": {
            "fee_per_fill": float(context.engine.FEE),
            "base_slippage_per_fill": BASE_SLIPPAGE,
            "stress_slippage_per_fill": STRESS_SLIPPAGE,
            "funding": "actual Binance funding events when include_funding=true",
        },
        "control": "CTRL_EXACT_V7",
        "ranking": ranking,
        "arms": rows,
        "pins": {
            "contract_sha256": sha256(CONTRACT_PATH),
            "audit_script_sha256": sha256(Path(__file__).resolve()),
            "transition_engine_sha256": sha256(TRANSITION_PATH),
            "full_ablation_helpers_sha256": sha256(FULL_ABLATION_PATH),
            "v7_context_loader_sha256": sha256(V7_AUDIT_PATH),
        },
        "registered": False,
        "promoted": False,
        "live_ready": False,
        "exact_v7_changed": False,
        "clean_oos_claim": False,
    }
    digest = write_locked(payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "ranking": ranking,
                "artifact": str(OUTPUT_PATH),
                "artifact_sha256": digest,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
