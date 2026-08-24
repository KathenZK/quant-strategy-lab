"""Replace V7.1 long OAPP with a 7-day half-range market trail, diagnostic-only."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from types import ModuleType
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
BASE_DIAGNOSTIC_PATH = (
    SCRIPT_DIR / "diagnose_hype_1d_ma7_abt_v7_1_oapp_rebound_reset.py"
)
CONTRACT_PATH = (
    FAMILY_DIR
    / "specs/hype-1d-ma7-abt-v7-1-oapp-range7-half-trail-diagnostic-contract-2026-08-20.md"
)
OUTPUT_PATH = (
    ARTIFACT_DIR / "hype_1d_ma7_abt_v7_1_oapp_range7_half_trail_2026-08-20.json"
)
V7_ABLATION_ARTIFACT = (
    ARTIFACT_DIR / "hype_1d_ma7_abt_v7_full_parameter_cleanup_ablation_2026-08-11.json"
)
R7H_REASON = "long_range7_half_trail_exit"


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


def closed_range7(book: Any, index: int) -> float:
    start = index - 7
    if start < 0:
        return math.nan
    highs = np.asarray(book.high[start:index], dtype=float)
    lows = np.asarray(book.low[start:index], dtype=float)
    if highs.size != 7 or lows.size != 7:
        return math.nan
    if not np.isfinite(highs).all() or not np.isfinite(lows).all():
        return math.nan
    span = float(highs.max() - lows.min())
    return span if span > 0.0 else math.nan


def r7h_scan_long_day(
    *,
    book: Any,
    features: Any,
    index: int,
    start_hour: int,
    ts: pd.Timestamp,
    holding_start: pd.Timestamp,
    position_mark: float,
    atr_stop: float,
    highest_high: float,
    recorder: list[dict[str, Any]],
) -> dict[str, Any]:
    range7 = closed_range7(book, index)
    highest = float(highest_high) if math.isfinite(highest_high) else -math.inf
    hit: dict[str, Any] | None = None
    for hour in range(int(start_hour), 24):
        hour_open = float(features.hourly_open[index, hour])
        hour_high = float(features.hourly_high[index, hour])
        hour_low = float(features.hourly_low[index, hour])
        r7h_stop = (
            highest - 0.5 * range7
            if math.isfinite(range7) and math.isfinite(highest) and highest > 0.0
            else math.nan
        )
        candidates: list[tuple[str, float]] = []
        if math.isfinite(atr_stop):
            candidates.append(("protective_stop", float(atr_stop)))
        if math.isfinite(r7h_stop):
            candidates.append((R7H_REASON, float(r7h_stop)))
        if candidates:
            binding_reason, binding_stop = max(
                candidates,
                key=lambda item: (item[1], item[0] == "protective_stop"),
            )
            gap = hour == int(start_hour) and position_mark <= binding_stop
            hour_gap = hour_open <= binding_stop
            touch = hour_low <= binding_stop
            if gap or hour_gap or touch:
                if gap:
                    fill = float(position_mark)
                    fill_ts = holding_start
                    kind = "gap"
                elif hour_gap:
                    fill = hour_open
                    fill_ts = ts + pd.Timedelta(hours=hour)
                    kind = "hour_gap"
                else:
                    fill = float(binding_stop)
                    fill_ts = ts + pd.Timedelta(hours=hour + 1)
                    kind = "touch"
                hit = {
                    "reason": binding_reason,
                    "binding_stop": float(binding_stop),
                    "r7h_stop": float(r7h_stop) if math.isfinite(r7h_stop) else None,
                    "atr_stop": float(atr_stop) if math.isfinite(atr_stop) else None,
                    "range7": float(range7) if math.isfinite(range7) else None,
                    "highest_high_at_signal": float(highest),
                    "hour": int(hour),
                    "kind": kind,
                    "fill": float(fill),
                    "fill_ts": fill_ts,
                }
                recorder.append(
                    {
                        "index": int(index),
                        "ts": pd.Timestamp(ts).isoformat(),
                        "hour": int(hour),
                        "range7": hit["range7"],
                        "highest_high": hit["highest_high_at_signal"],
                        "r7h_stop": hit["r7h_stop"],
                        "atr_stop": hit["atr_stop"],
                        "reason": binding_reason,
                        "kind": kind,
                        "fill": float(fill),
                    }
                )
                break
        highest = max(highest, hour_high)
    return {"hit": hit, "highest_high": float(highest), "range7": range7}


def apply_r7h_source(engine: ModuleType, source: str) -> str:
    replace_once = engine._replace_once
    source = replace_once(
        source,
        "        nonlocal bars_held, stop_price, highest_close, lowest_close, mark_price\n",
        "        nonlocal bars_held, stop_price, highest_close, lowest_close, highest_high, mark_price\n",
        "R7H enter nonlocal",
    )
    source = replace_once(
        source,
        "        nonlocal bars_held, stop_price, highest_close, lowest_close\n",
        "        nonlocal bars_held, stop_price, highest_close, lowest_close, highest_high\n",
        "R7H close nonlocal",
    )
    source = replace_once(
        source,
        "        highest_close = -math.inf\n        lowest_close = math.inf\n        atr = features.atr7[signal_index]\n",
        "        highest_close = -math.inf\n        lowest_close = math.inf\n        highest_high = price\n        atr = features.atr7[signal_index]\n",
        "R7H enter reset",
    )
    source = replace_once(
        source,
        "        stop_price = math.nan\n        highest_close = -math.inf\n        lowest_close = math.inf\n        wtl_long_run = 0\n",
        "        stop_price = math.nan\n        highest_close = -math.inf\n        lowest_close = math.inf\n        highest_high = -math.inf\n        wtl_long_run = 0\n",
        "R7H close reset",
    )
    source = replace_once(
        source,
        "    stop_price = math.nan\n    highest_close = -math.inf\n    lowest_close = math.inf\n",
        "    stop_price = math.nan\n    highest_close = -math.inf\n    lowest_close = math.inf\n    highest_high = -math.inf\n",
        "R7H function init",
    )
    old_hold = """\
            holding_start = (
                max(ts, entry_ts)
                if entry_ts is not None
                else ts
            )
            if gap_hit or intraday_hit:
"""
    new_hold = """\
            holding_start = (
                max(ts, entry_ts)
                if entry_ts is not None
                else ts
            )
            r7h_scan = (
                r7h_scan_long_day(
                    book=book,
                    features=features,
                    index=int(index),
                    start_hour=int(start_hour),
                    ts=ts,
                    holding_start=holding_start,
                    position_mark=float(position_mark),
                    atr_stop=stop_price,
                    highest_high=highest_high,
                    recorder=r7h_recorder,
                )
                if side > 0
                else {"hit": None, "highest_high": highest_high, "range7": math.nan}
            )
            highest_high = float(r7h_scan["highest_high"])
            r7h_hit = r7h_scan["hit"]
            if r7h_hit is not None and r7h_hit["reason"] == "long_range7_half_trail_exit":
                fill = float(r7h_hit["fill"])
                stop_fill_ts = r7h_hit["fill_ts"]
                hit_hour = int(r7h_hit["hour"])
                gap_hit = r7h_hit["kind"] == "gap"
                settle_funding(index, holding_start, stop_fill_ts)
                position_qty = qty
                funded_open_equity = equity
                completed_end = 0 if gap_hit else hit_hour
                completed_high = features.hourly_high[index, start_hour:completed_end]
                completed_low = features.hourly_low[index, start_hour:completed_end]
                if len(completed_high):
                    favorable = max(position_mark, fill, float(completed_high.max()))
                    adverse = min(position_mark, fill, float(completed_low.min()))
                    favorable_equity = funded_open_equity + position_qty * (
                        favorable - position_mark
                    )
                    adverse_equity = funded_open_equity + position_qty * (
                        adverse - position_mark
                    )
                else:
                    favorable_equity = adverse_equity = funded_open_equity
                equity += qty * (fill - position_mark)
                r7h_entry_ts = entry_ts
                r7h_entry_price = float(entry_price)
                r7h_bars_held = int(bars_held)
                close(stop_fill_ts, fill, "long_range7_half_trail_exit", index)
                if pehc_enabled:
                    if pehc_shadow_active:
                        pehc_record({
                            "event": "shadow_start_rejected_already_active",
                            "index": int(index),
                            "ts": stop_fill_ts.isoformat(),
                            "origin_index": int(pehc_shadow_origin_index),
                            "reason": "long_range7_half_trail_exit",
                        })
                    else:
                        pehc_shadow_active = True
                        pehc_shadow_origin_index = int(index)
                        pehc_shadow_entry_ts = r7h_entry_ts
                        pehc_shadow_entry_price = r7h_entry_price
                        pehc_shadow_stop_price = float(r7h_hit["binding_stop"])
                        pehc_shadow_highest_close = float(r7h_hit["highest_high_at_signal"])
                        pehc_shadow_bars_held = r7h_bars_held
                        pehc_record({
                            "event": "shadow_start",
                            "index": int(index),
                            "ts": stop_fill_ts.isoformat(),
                            "origin_index": int(index),
                            "entry_ts": r7h_entry_ts.isoformat() if r7h_entry_ts is not None else None,
                            "entry_price": r7h_entry_price,
                            "stop_price": float(r7h_hit["binding_stop"]),
                            "highest_close": float(r7h_hit["highest_high_at_signal"]),
                            "bars_held": r7h_bars_held,
                            "reason": "long_range7_half_trail_exit",
                        })
                cooldown_left = config.cooldown_days
                mark_price = fill
                action = "long_range7_half_trail_exit"
                favorable_equity = max(favorable_equity, equity)
                adverse_equity = min(adverse_equity, equity)
                close_equity = equity
            elif gap_hit or intraday_hit:
"""
    source = replace_once(source, old_hold, new_hold, "R7H hourly override")
    return source


def build_r7h_function(
    engine: ModuleType,
    context: Any,
    variant: Any,
    *,
    rsi6: Any,
    entry_signal: Any,
    leverage_policy: Any,
    recorder: Any,
    r7h_recorder: list[dict[str, Any]],
) -> tuple[Any, str]:
    source = engine._BASE._capture_exact_source(context)
    function_name = "pehc_r7h_diagnostic_backtest"
    source = engine._replace_once(
        source, "def v3_ma_only_backtest(", f"def {function_name}(", "R7H function name"
    )
    source = engine._BASE._apply_state(source)
    source = engine._BASE._apply_exits(source)
    source = engine._apply_pehc_state(source)
    source = engine._apply_pehc_arm(source)
    source = engine._apply_pehc_daily(source)
    source = engine._apply_pehc_intraday(source)
    source = apply_r7h_source(engine, source)
    namespace = dict(context.engine.__dict__)
    pehc_config = variant.pehc_config
    oapp_config = variant.oapp_config
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
            "wtl_exit_decision": engine._BASE.lifecycle_exit_decision,
            "pehc_enabled": pehc_config.enabled,
            "pehc_entry_enabled": pehc_config.entry_enabled,
            "pehc_blocked_origin_indices": frozenset(pehc_config.blocked_origin_indices),
            "pehc_allowed_origin_indices": frozenset(pehc_config.allowed_origin_indices),
            "pehc_expiry_days": pehc_config.expiry_days,
            "pehc_slope_threshold": pehc_config.slope_threshold,
            "pehc_chase_cap_atr": pehc_config.chase_cap_atr,
            "pehc_execution": pehc_config.execution,
            "pehc_handoff_eligibility": engine.handoff_eligibility,
            "pehc_record": recorder,
            "r7h_scan_long_day": r7h_scan_long_day,
            "r7h_recorder": r7h_recorder,
        }
    )
    compiled = compile(source, "<pehc-r7h-diagnostic>", "exec")
    exec(compiled, namespace)
    return namespace[function_name], hashlib.sha256(source.encode()).hexdigest()


def r7h_variant(v6: ModuleType, engine: ModuleType, context: Any) -> Any:
    return v6.Variant(
        name="R7H",
        group="oapp_replacement_diagnostic",
        change="replace long OAPP with 7-day half-range market trail",
        long_config=context.long_config,
        short_config=context.short_config,
        oapp_config=v6.oapp_config(
            engine,
            arm_id="V7_1_R7H_LONG_OAPP_OFF",
            long_exit=engine._OAPP.TrailExit(),
        ),
        pehc_config=v6.fixed_pehc(engine, arm_id="PEHC_294"),
    )


def off_variant(v6: ModuleType, engine: ModuleType, context: Any) -> Any:
    return v6.Variant(
        name="OAPP_OFF",
        group="known_comparator",
        change="disable long OAPP",
        long_config=context.long_config,
        short_config=context.short_config,
        oapp_config=v6.oapp_config(
            engine,
            arm_id="V7_1_LONG_OAPP_OFF",
            long_exit=engine._OAPP.TrailExit(),
        ),
        pehc_config=v6.fixed_pehc(engine, arm_id="PEHC_294"),
    )


def activation_counts(raw: Any, handoff_events: list[dict[str, Any]]) -> dict[str, int]:
    exits = [str(trade.get("exit_reason", "")) for trade in raw.trades]
    return {
        "shadow_start": sum(row["event"] == "shadow_start" for row in handoff_events),
        "handoff_accept": sum(row["event"] == "handoff_accept" for row in handoff_events),
        "long_trail_exit": sum(reason.startswith("long_mfe_") for reason in exits),
        "long_range7_half_trail_exit": sum(reason == R7H_REASON for reason in exits),
        "short_rsi_exit": sum(reason == "short_rsi_take_profit" for reason in exits),
        "protective_stop": sum(reason == "protective_stop" for reason in exits),
    }


def run_r7h(
    v6: ModuleType,
    engine: ModuleType,
    context: Any,
    *,
    window: tuple[int, int],
    slippage: float = 0.0004,
    signal_lag: int = 0,
    include_funding: bool = True,
    retain: bool = False,
) -> tuple[dict[str, Any], Any, list[dict[str, Any]]]:
    variant = r7h_variant(v6, engine, context)
    rsi6 = engine._BASE.wilder_rsi6(context.book.close)
    entry_signal = engine._BASE.EntryQualitySignal(context.engine, variant.oapp_config.entry)
    leverage_policy = engine._BASE.LeveragePolicy(context, None)
    recorder = engine.HandoffRecorder()
    r7h_recorder: list[dict[str, Any]] = []
    function, source_hash = build_r7h_function(
        engine,
        context,
        variant,
        rsi6=rsi6,
        entry_signal=entry_signal,
        leverage_policy=leverage_policy,
        recorder=recorder,
        r7h_recorder=r7h_recorder,
    )
    left, right = window
    raw = function(
        context.book,
        context.features,
        long_config=variant.long_config,
        short_config=variant.short_config,
        start_index=v6.start_for(window),
        terminal_index=right,
        slippage=slippage,
        signal_lag=signal_lag,
        include_funding=include_funding,
        retain=retain,
    )
    if bool(raw.metrics.get("bankrupt_intraday")):
        raise RuntimeError("R7H became bankrupt")
    handoff_events = list(recorder.events)
    result = engine.PEHCExecutionResult(
        config=variant.pehc_config,
        raw=raw,
        source_sha256=source_hash,
        entry_events=list(entry_signal.events),
        leverage_events=list(leverage_policy.events),
        handoff_events=handoff_events,
        activation_counts=activation_counts(raw, handoff_events),
        rsi6=rsi6,
    )
    replay = v6.chronological_replay(
        context, raw, slippage=slippage, include_funding=include_funding
    )
    metrics = v6.normalize(raw, replay, result, days=right - left)
    metrics["source_sha256"] = source_hash
    metrics["long_range7_half_trail_exit"] = int(
        result.activation_counts["long_range7_half_trail_exit"]
    )
    return metrics, result, r7h_recorder


def run_off(
    v6: ModuleType,
    engine: ModuleType,
    context: Any,
    *,
    window: tuple[int, int],
    retain: bool = False,
) -> tuple[dict[str, Any], Any]:
    return v6.run_variant(
        engine,
        context,
        off_variant(v6, engine, context),
        window=window,
        slippage=0.0004,
        signal_lag=0,
        include_funding=True,
        retain=retain,
    )


def signatures(base: ModuleType, result: Any) -> list[tuple[Any, ...]]:
    return [base.trade_signature(row) for row in result.raw.trades]


def incident_trade(base: ModuleType, result: Any) -> dict[str, Any] | None:
    row = next(
        (
            trade
            for trade in result.raw.trades
            if pd.Timestamp(trade["entry_ts"]) == base.INCIDENT_ENTRY_TS
        ),
        None,
    )
    return base.compact_trade(row) if row is not None else None


def decide(control: dict[str, Any], candidate: dict[str, Any], equal_off: bool) -> str:
    if equal_off:
        return "NO_GO_R7H_PATH_EQUIVALENT_TO_OAPP_OFF"
    lower_return = float(candidate["net_return_pct"]) < float(control["net_return_pct"])
    failed_mdd = float(candidate["chronological_1h_mdd_pct"]) < -20.0
    worse_mdd = float(candidate["chronological_1h_mdd_pct"]) < float(
        control["chronological_1h_mdd_pct"]
    )
    if lower_return and (failed_mdd or worse_mdd):
        return "NO_GO_R7H_RETURN_LOWER_OR_MDD_WORSE"
    if lower_return:
        return "NO_GO_R7H_RETURN_LOWER"
    return "SHADOW_R7H_ONLY"


def run(force: bool = False) -> dict[str, Any]:
    base = load_module(BASE_DIAGNOSTIC_PATH, "r7h_base_diagnostic")
    v6 = base.load_module(base.V6_ABLATION_PATH, "r7h_v6_ablation")
    engine = base.load_module(base.ENGINE_PATH, "r7h_pehc_engine")
    adapter = base.load_module(base.ADAPTER_PATH, "r7h_v4_adapter")
    canonical_context, context = base.extended_context(adapter)

    control_canonical, control_canonical_result, _ = base.run_arm(
        v6,
        engine,
        canonical_context,
        "CONTROL",
        window=(0, base.CANONICAL_RIGHT),
        retain=True,
    )
    base.assert_control_anchor(control_canonical, control_canonical_result)
    r7h_canonical, r7h_canonical_result, r7h_canonical_events = run_r7h(
        v6,
        engine,
        canonical_context,
        window=(0, base.CANONICAL_RIGHT),
        retain=True,
    )
    off_canonical, off_canonical_result = run_off(
        v6,
        engine,
        canonical_context,
        window=(0, base.CANONICAL_RIGHT),
        retain=True,
    )

    control_extended, control_extended_result, _ = base.run_arm(
        v6,
        engine,
        context,
        "CONTROL",
        window=(0, context.book.count),
        retain=True,
    )
    base.assert_incident_trade(control_extended_result.raw.trades[-1])
    r7h_extended, r7h_extended_result, r7h_extended_events = run_r7h(
        v6,
        engine,
        context,
        window=(0, context.book.count),
        retain=True,
    )
    off_extended, off_extended_result = run_off(
        v6,
        engine,
        context,
        window=(0, context.book.count),
        retain=True,
    )

    stress: dict[str, Any] = {}
    for label, slippage, lag, funding in (
        ("slippage_8bps", 0.0008, 0, True),
        ("lag_1d", 0.0004, 1, True),
        ("funding_off", 0.0004, 0, False),
    ):
        metrics, _, _ = run_r7h(
            v6,
            engine,
            context,
            window=(0, context.book.count),
            slippage=slippage,
            signal_lag=lag,
            include_funding=funding,
        )
        stress[label] = metrics

    recent: dict[str, Any] = {}
    for label, days in base.RECENT_SLICES.items():
        metrics, _, _ = run_r7h(
            v6,
            engine,
            context,
            window=(max(0, context.book.count - days), context.book.count),
        )
        recent[label] = metrics

    r7h_incident = incident_trade(base, r7h_extended_result)
    off_incident = incident_trade(base, off_extended_result)
    equal_off_canonical = signatures(base, r7h_canonical_result) == signatures(
        base, off_canonical_result
    )
    equal_off_extended = signatures(base, r7h_extended_result) == signatures(
        base, off_extended_result
    )
    existing_ablation = json.loads(V7_ABLATION_ARTIFACT.read_text(encoding="utf-8"))
    existing_off = existing_ablation["candidates"]["n_oapp_long_mode_off"]["stress"][
        "base_full"
    ]
    if not math.isclose(
        float(off_canonical["net_return_pct"]),
        float(existing_off["net_return_pct"]),
        abs_tol=1e-10,
    ):
        raise RuntimeError("OAPP-off comparator drift")

    binding_hits = [
        row
        for row in r7h_extended_events
        if row.get("reason") == R7H_REASON
    ]
    payload = {
        "schema": "hype-1d-ma7-abt-v7-1-oapp-range7-half-trail-diagnostic-v1",
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "status": "DIAGNOSTIC_ONLY_NOT_PROMOTED_NOT_LIVE_READY",
        "strategy_id": "HYPE-1D-MA7-ABT-V7.1",
        "candidate": {
            "id": "R7H",
            "rule": (
                "disable long OAPP; market-exit a long when price falls from the "
                "completed-hour holding high by half of the prior 7 closed-day high-low range"
            ),
        },
        "verdict": {
            "decision": "PENDING_MECHANICAL_EVALUATION",
            "runner_change_authorized": False,
        },
        "data_audit": base.sanitize(context.market.audit),
        "canonical": {
            "CONTROL": control_canonical,
            "R7H": r7h_canonical,
            "OAPP_OFF": off_canonical,
        },
        "extended": {
            "CONTROL": control_extended,
            "R7H": r7h_extended,
            "OAPP_OFF": off_extended,
        },
        "stress": stress,
        "recent_slices": recent,
        "incident": {
            "control": incident_trade(base, control_extended_result),
            "r7h": r7h_incident,
            "oapp_off": off_incident,
            "r7h_prevents_2026_08_16_exit": bool(
                r7h_incident
                and pd.Timestamp(r7h_incident["exit_ts"]) != base.INCIDENT_EXIT_TS
            ),
            "r7h_terminal_censored": bool(
                r7h_incident and r7h_incident.get("exit_reason") == "terminal_flatten"
            ),
        },
        "path_equivalence": {
            "r7h_equals_oapp_off_canonical": equal_off_canonical,
            "r7h_equals_oapp_off_extended": equal_off_extended,
        },
        "changed_long_episodes_vs_control": base.changed_long_episodes(
            list(control_extended_result.raw.trades),
            list(r7h_extended_result.raw.trades),
        ),
        "canonical_trades": {
            "CONTROL": [base.compact_trade(row) for row in control_canonical_result.raw.trades],
            "R7H": [base.compact_trade(row) for row in r7h_canonical_result.raw.trades],
        },
        "r7h_binding_events": binding_hits,
        "canonical_r7h_binding_events": [
            row for row in r7h_canonical_events if row.get("reason") == R7H_REASON
        ],
        "pins": {
            "contract_sha256": sha256(CONTRACT_PATH),
            "script_sha256": sha256(Path(__file__).resolve()),
            "base_diagnostic_sha256": sha256(BASE_DIAGNOSTIC_PATH),
            "v7_ablation_artifact_sha256": sha256(V7_ABLATION_ARTIFACT),
        },
        "notes": [
            "R7H uses completed-hour highs only; the triggering 1h bar cannot both set a new high and hit the new stop.",
            "R7H flats the long and may start PEHC; it does not use MA-only forced short.",
            "The August event is revealed and cannot promote the candidate.",
        ],
    }
    payload["verdict"] = {
        "decision": decide(control_canonical, r7h_canonical, equal_off_canonical),
        "production_action": "KEEP_V7_1",
        "runner_change_authorized": False,
    }
    document = (
        json.dumps(
            base.sanitize(payload),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
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
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    result = run(force=args.force)
    payload = result["payload"]
    print(
        json.dumps(
            {
                "output": result["output"],
                "sha256": result["sha256"],
                "verdict": payload["verdict"],
                "canonical": payload["canonical"],
                "extended": payload["extended"],
                "incident": payload["incident"],
                "path_equivalence": payload["path_equivalence"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
