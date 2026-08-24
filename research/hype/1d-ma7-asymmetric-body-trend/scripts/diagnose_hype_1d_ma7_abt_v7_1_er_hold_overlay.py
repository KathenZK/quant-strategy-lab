"""Measure long-hold ER7 vs OAPP locks; gate OAPP only if they separate."""

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
    / "specs/hype-1d-ma7-abt-v7-1-er-hold-overlay-diagnostic-contract-2026-08-20.md"
)
OUTPUT_PATH = (
    ARTIFACT_DIR / "hype_1d_ma7_abt_v7_1_er_hold_overlay_2026-08-20.json"
)
V7_ABLATION_ARTIFACT = (
    ARTIFACT_DIR / "hype_1d_ma7_abt_v7_full_parameter_cleanup_ablation_2026-08-11.json"
)
INCIDENT_CONFIRM_TS = pd.Timestamp("2026-08-15T00:00:00Z")
INCIDENT_FIRST_CONFIRM_TS = pd.Timestamp("2026-08-14T00:00:00Z")
REQUIRED_CANONICAL_OAPP_DAYS = 8


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


def close_timestamp(book: Any, index: int) -> pd.Timestamp:
    if index + 1 < book.count:
        return pd.Timestamp(book.ts[index + 1])
    return pd.Timestamp(book.terminal_ts)


def efficiency_ratio(closes: np.ndarray, index: int, lookback: int = 7) -> float:
    start = index - lookback
    if start < 0:
        return math.nan
    net = float(closes[index] - closes[start])
    path = float(np.abs(np.diff(closes[start : index + 1])).sum())
    if not math.isfinite(net) or not math.isfinite(path) or path <= 0.0:
        return math.nan
    return abs(net) / path


def signed_efficiency_ratio(closes: np.ndarray, index: int, lookback: int = 7) -> float:
    start = index - lookback
    if start < 0:
        return math.nan
    net = float(closes[index] - closes[start])
    path = float(np.abs(np.diff(closes[start : index + 1])).sum())
    if not math.isfinite(net) or not math.isfinite(path) or path <= 0.0:
        return math.nan
    return net / path


def sma_at(closes: np.ndarray, index: int, window: int) -> float:
    start = index - window + 1
    if start < 0:
        return math.nan
    chunk = closes[start : index + 1]
    if chunk.size != window or not np.isfinite(chunk).all():
        return math.nan
    return float(chunk.mean())


def slope_sign(current: float, previous: float) -> int | None:
    if not math.isfinite(current) or not math.isfinite(previous):
        return None
    delta = current - previous
    if delta > 0.0:
        return 1
    if delta < 0.0:
        return -1
    return 0


def compact_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "net_return_pct",
        "chronological_1h_mdd_pct",
        "win_rate",
        "profit_factor",
        "closed_trades",
        "source_sha256",
    )
    return {key: metrics.get(key) for key in keys if key in metrics}


class FeatureBook:
    def __init__(self, context: Any) -> None:
        self.context = context
        self.closes = np.asarray(context.book.close, dtype=float)
        self.ma7 = np.asarray(context.features.ma7, dtype=float)
        self.atr7 = np.asarray(context.features.atr7, dtype=float)
        count = int(context.book.count)
        self.er7 = np.array(
            [efficiency_ratio(self.closes, index) for index in range(count)],
            dtype=float,
        )
        self.signed_er7 = np.array(
            [signed_efficiency_ratio(self.closes, index) for index in range(count)],
            dtype=float,
        )
        self.sma14 = np.array(
            [sma_at(self.closes, index, 14) for index in range(count)], dtype=float
        )
        self.sma30 = np.array(
            [sma_at(self.closes, index, 30) for index in range(count)], dtype=float
        )
        self.slope_atr = np.full(count, math.nan, dtype=float)
        self.delta_slope_atr = np.full(count, math.nan, dtype=float)
        for index in range(1, count):
            atr = float(self.atr7[index])
            prev_ma = float(self.ma7[index - 1])
            ma = float(self.ma7[index])
            if math.isfinite(atr) and atr > 0.0 and math.isfinite(ma) and math.isfinite(prev_ma):
                self.slope_atr[index] = (ma - prev_ma) / atr
            if math.isfinite(self.slope_atr[index]) and math.isfinite(self.slope_atr[index - 1]):
                self.delta_slope_atr[index] = (
                    float(self.slope_atr[index]) - float(self.slope_atr[index - 1])
                )

    def row(self, index: int, *, highest_close: float, entry_price: float) -> dict[str, Any]:
        close = float(self.closes[index])
        atr = float(self.atr7[index])
        pullback = (
            (highest_close - close) / atr
            if math.isfinite(highest_close) and math.isfinite(atr) and atr > 0.0
            else math.nan
        )
        return {
            "index": int(index),
            "ts": pd.Timestamp(self.context.book.ts[index]).isoformat(),
            "close": close,
            "atr7": atr,
            "sma7": float(self.ma7[index]),
            "er7": float(self.er7[index]) if math.isfinite(self.er7[index]) else None,
            "signed_er7": (
                float(self.signed_er7[index]) if math.isfinite(self.signed_er7[index]) else None
            ),
            "slope_atr": (
                float(self.slope_atr[index]) if math.isfinite(self.slope_atr[index]) else None
            ),
            "delta_slope_atr": (
                float(self.delta_slope_atr[index])
                if math.isfinite(self.delta_slope_atr[index])
                else None
            ),
            "pullback_atr": pullback if math.isfinite(pullback) else None,
            "highest_close": float(highest_close) if math.isfinite(highest_close) else None,
            "sma14_slope_sign": slope_sign(
                float(self.sma14[index]),
                float(self.sma14[index - 1]) if index > 0 else math.nan,
            ),
            "sma30_slope_sign": slope_sign(
                float(self.sma30[index]),
                float(self.sma30[index - 1]) if index > 0 else math.nan,
            ),
            "gross_profit_fraction": (
                close / entry_price - 1.0 if entry_price > 0.0 else None
            ),
        }


def held_indices(book: Any, trade: dict[str, Any]) -> list[int]:
    entry_ts = pd.Timestamp(trade["entry_ts"])
    exit_ts = pd.Timestamp(trade["exit_ts"])
    held: list[int] = []
    for index in range(book.count):
        close_ts = close_timestamp(book, index)
        if entry_ts < close_ts and exit_ts >= close_ts:
            held.append(index)
    return held


def simulate_oapp_on_trade(
    engine: ModuleType,
    features: FeatureBook,
    trade: dict[str, Any],
    held: list[int],
) -> list[dict[str, Any]]:
    long_exit = engine._OAPP.TrailExit("fraction", 0.5, 0.10, 2)
    entry_price = float(trade["entry_price"])
    highest = entry_price
    count = 0
    days_since_high = 0
    rows: list[dict[str, Any]] = []
    for index in held:
        close = float(features.closes[index])
        if close >= highest:
            highest = close
            days_since_high = 0
        else:
            days_since_high += 1
        atr = float(features.atr7[index])
        active = engine._BASE._trail_trigger(
            side=1,
            spec=long_exit,
            peak_close=highest,
            signal_close=close,
            entry_price=entry_price,
            atr=atr,
            guard=0.0028,
        )
        count = count + 1 if active else 0
        payload = features.row(index, highest_close=highest, entry_price=entry_price)
        payload.update(
            {
                "entry_ts": pd.Timestamp(trade["entry_ts"]).isoformat(),
                "exit_ts": pd.Timestamp(trade["exit_ts"]).isoformat(),
                "exit_reason": str(trade["exit_reason"]),
                "oapp_active": bool(active),
                "oapp_count": int(count),
                "oapp_mature_signal": bool(active and count >= 2),
                "days_since_highest_close": int(days_since_high),
            }
        )
        rows.append(payload)
    return rows


def later_higher_high(days: list[dict[str, Any]], position: int) -> bool:
    current = days[position].get("highest_close")
    if current is None:
        return False
    for later in days[position + 1 :]:
        peak = later.get("highest_close")
        if peak is not None and float(peak) > float(current) + 1e-12:
            return True
    return False


def summarize_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    er_values = [float(row["er7"]) for row in rows if row.get("er7") is not None]
    slope_values = [
        float(row["slope_atr"]) for row in rows if row.get("slope_atr") is not None
    ]
    return {
        "n": len(rows),
        "er7_median": float(np.median(er_values)) if er_values else None,
        "er7_mean": float(np.mean(er_values)) if er_values else None,
        "er7_min": float(np.min(er_values)) if er_values else None,
        "er7_max": float(np.max(er_values)) if er_values else None,
        "slope_atr_median": float(np.median(slope_values)) if slope_values else None,
        "positive_sma14_slope": sum(row.get("sma14_slope_sign") == 1 for row in rows),
        "positive_sma30_slope": sum(row.get("sma30_slope_sign") == 1 for row in rows),
    }


class ERGatedOAPPPolicy:
    """First OAPP confirm is ungated; the second requires ER7 < frozen median."""

    def __init__(self, engine: ModuleType, context: Any, features: FeatureBook, threshold: float) -> None:
        if not math.isfinite(threshold):
            raise RuntimeError("ER gate threshold must be finite")
        self.engine = engine
        self.context = context
        self.features = features
        self.threshold = float(threshold)
        self.entry_identity: tuple[int, float] | None = None
        self.events: list[dict[str, Any]] = []
        self.index_by_values = {
            (float(close), float(atr)): index
            for index, (close, atr) in enumerate(
                zip(context.book.close, context.features.atr7, strict=True)
            )
        }
        if len(self.index_by_values) != context.book.count:
            raise RuntimeError("close/ATR pair is not unique enough for policy audit")

    def __call__(self, **kwargs: Any) -> tuple[str | None, int, int, int]:
        side = int(kwargs["side"])
        if side <= 0:
            return self.engine._BASE.lifecycle_exit_decision(**kwargs)
        close = float(kwargs["signal_close"])
        atr = float(kwargs["atr"])
        index = self.index_by_values[(close, atr)]
        identity = (side, float(kwargs["entry_price"]))
        if identity != self.entry_identity:
            self.entry_identity = identity
        long_exit = kwargs["long_exit"]
        active = self.engine._BASE._trail_trigger(
            side=1,
            spec=long_exit,
            peak_close=float(kwargs["highest_close"]),
            signal_close=close,
            entry_price=float(kwargs["entry_price"]),
            atr=atr,
            guard=float(kwargs["roundtrip_guard"]),
        )
        er7 = float(self.features.er7[index])
        er_weak = math.isfinite(er7) and er7 < self.threshold
        prior = int(kwargs["long_run"])
        if not active:
            long_run = 0
        elif prior <= 0:
            long_run = 1
        elif er_weak:
            long_run = prior + 1
        else:
            long_run = prior
        reason = (
            f"long_mfe_{long_exit.mode}_trail_exit"
            if long_exit.enabled and long_run >= long_exit.confirm_days
            else None
        )
        self.events.append(
            {
                "index": index,
                "ts": pd.Timestamp(self.context.book.ts[index]).isoformat(),
                "close": close,
                "er7": er7 if math.isfinite(er7) else None,
                "er_weak": bool(er_weak),
                "active": bool(active),
                "prior_count": prior,
                "new_count": long_run,
                "reason": reason,
            }
        )
        return reason, long_run, 0, 0


def run_er_gate(
    base: ModuleType,
    v6: ModuleType,
    engine: ModuleType,
    context: Any,
    features: FeatureBook,
    threshold: float,
    *,
    window: tuple[int, int],
    slippage: float = 0.0004,
    signal_lag: int = 0,
    include_funding: bool = True,
    retain: bool = False,
) -> tuple[dict[str, Any], Any, ERGatedOAPPPolicy]:
    variant = base.fixed_variant(v6, engine, context, "CONTROL")
    rsi6 = engine._BASE.wilder_rsi6(context.book.close)
    entry_signal = engine._BASE.EntryQualitySignal(context.engine, variant.oapp_config.entry)
    leverage_policy = engine._BASE.LeveragePolicy(context, None)
    recorder = engine.HandoffRecorder()
    function, source_hash = engine.build_variant_function(
        context,
        variant.pehc_config,
        oapp_config=variant.oapp_config,
        entry_signal=entry_signal,
        leverage_policy=leverage_policy,
        rsi6=rsi6,
        recorder=recorder,
    )
    policy = ERGatedOAPPPolicy(engine, context, features, threshold)
    function.__globals__["wtl_exit_decision"] = policy
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
        raise RuntimeError("ER-gated OAPP became bankrupt")
    handoff_events = list(recorder.events)
    result = engine.PEHCExecutionResult(
        config=variant.pehc_config,
        raw=raw,
        source_sha256=source_hash,
        entry_events=list(entry_signal.events),
        leverage_events=list(leverage_policy.events),
        handoff_events=handoff_events,
        activation_counts={
            "shadow_start": sum(row["event"] == "shadow_start" for row in handoff_events),
            "handoff_accept": sum(row["event"] == "handoff_accept" for row in handoff_events),
            "long_trail_exit": sum(
                str(trade.get("exit_reason", "")).startswith("long_mfe_")
                for trade in raw.trades
            ),
            "short_rsi_exit": sum(
                str(trade.get("exit_reason", "")) == "short_rsi_take_profit"
                for trade in raw.trades
            ),
            "protective_stop": sum(
                str(trade.get("exit_reason", "")) == "protective_stop"
                for trade in raw.trades
            ),
        },
        rsi6=rsi6,
    )
    replay = v6.chronological_replay(
        context, raw, slippage=slippage, include_funding=include_funding
    )
    metrics = v6.normalize(raw, replay, result, days=right - left)
    metrics["source_sha256"] = source_hash
    return metrics, result, policy


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


def layer0_event_study(
    engine: ModuleType,
    context: Any,
    features: FeatureBook,
    trades: list[dict[str, Any]],
    canonical_trades: list[dict[str, Any]],
) -> dict[str, Any]:
    long_trades = [row for row in trades if str(row["side"]) == "long"]
    canonical_long_entries = {
        pd.Timestamp(row["entry_ts"]).isoformat()
        for row in canonical_trades
        if str(row["side"]) == "long"
    }
    canonical_oapp_entries = {
        pd.Timestamp(row["entry_ts"]).isoformat()
        for row in canonical_trades
        if str(row["side"]) == "long"
        and str(row["exit_reason"]).startswith("long_mfe_")
    }
    if len(canonical_oapp_entries) != REQUIRED_CANONICAL_OAPP_DAYS:
        raise RuntimeError(
            f"expected {REQUIRED_CANONICAL_OAPP_DAYS} canonical OAPP longs, "
            f"got {len(canonical_oapp_entries)}"
        )
    all_days: list[dict[str, Any]] = []
    for trade in long_trades:
        held = held_indices(context.book, trade)
        days = simulate_oapp_on_trade(engine, features, trade, held)
        for position, row in enumerate(days):
            row["later_higher_high"] = later_higher_high(days, position)
            row["canonical"] = row["entry_ts"] in canonical_long_entries
            all_days.append(row)

    canonical_mature = [
        row
        for row in all_days
        if row["oapp_mature_signal"] and row["entry_ts"] in canonical_oapp_entries
    ]
    if len(canonical_mature) != REQUIRED_CANONICAL_OAPP_DAYS:
        raise RuntimeError(
            f"expected {REQUIRED_CANONICAL_OAPP_DAYS} canonical OAPP mature days, "
            f"got {len(canonical_mature)}"
        )
    incident_days = [
        row
        for row in all_days
        if pd.Timestamp(row["ts"]) in {INCIDENT_FIRST_CONFIRM_TS, INCIDENT_CONFIRM_TS}
    ]
    incident_second = next(
        (row for row in incident_days if pd.Timestamp(row["ts"]) == INCIDENT_CONFIRM_TS),
        None,
    )
    er_values = [float(row["er7"]) for row in canonical_mature if row.get("er7") is not None]
    if len(er_values) != REQUIRED_CANONICAL_OAPP_DAYS:
        raise RuntimeError("canonical OAPP mature days missing finite ER7")
    threshold = float(np.median(er_values))
    incident_er = None if incident_second is None else incident_second.get("er7")
    separable = (
        incident_er is not None
        and math.isfinite(float(incident_er))
        and float(incident_er) > threshold
    )
    continuation = [
        row
        for row in all_days
        if row["later_higher_high"] and not row["oapp_mature_signal"]
    ]
    destroyed = [
        row
        for row in all_days
        if str(row["exit_reason"]) in {"protective_stop", "ma7_hysteresis_exit"}
    ]
    return {
        "threshold_median_er7": threshold,
        "separable": bool(separable),
        "incident_2026_08_15_er7": incident_er,
        "canonical_oapp_mature_days": canonical_mature,
        "incident_days": incident_days,
        "summaries": {
            "canonical_oapp_mature": summarize_group(canonical_mature),
            "incident_days": summarize_group(incident_days),
            "continuation_held_not_mature": summarize_group(continuation),
            "protective_or_hysteresis_trade_days": summarize_group(destroyed),
            "all_long_held_days": summarize_group(all_days),
        },
        "held_day_count": len(all_days),
        "long_trade_count": len(long_trades),
    }


def decide_verdict(payload: dict[str, Any]) -> dict[str, Any]:
    layer0 = payload["layer0"]
    if not layer0["separable"]:
        return {
            "decision": "LAYER0_NOT_SEPARABLE_KEEP_V7_1",
            "production_action": "KEEP_V7_1",
            "runner_change_authorized": False,
            "layer1_ran": False,
        }
    control = payload["canonical"]["CONTROL"]
    candidate = payload["canonical"]["ER_GATED"]
    incident = payload["incident"]
    still_exits = bool(incident.get("er_gated_still_exits_2026_08_16"))
    lower_return = float(candidate["net_return_pct"]) < float(control["net_return_pct"])
    mdd_gate_failed = float(candidate["chronological_1h_mdd_pct"]) < -20.0
    worse_mdd = float(candidate["chronological_1h_mdd_pct"]) < float(
        control["chronological_1h_mdd_pct"]
    )
    if still_exits:
        decision = "NO_GO_ER_GATE_DID_NOT_BLOCK_AUGUST_OAPP"
    elif lower_return and (mdd_gate_failed or worse_mdd):
        decision = "NO_GO_ER_GATE_RETURN_OR_MDD_FAILED"
    elif lower_return:
        decision = "NO_GO_ER_GATE_RETURN_LOWER"
    else:
        decision = "SHADOW_ER_GATE_ONLY"
    return {
        "decision": decision,
        "production_action": "KEEP_V7_1",
        "runner_change_authorized": False,
        "layer1_ran": True,
        "august_terminal_censored": bool(incident.get("er_gated_terminal_censored")),
    }


def run(force: bool = False) -> dict[str, Any]:
    base = load_module(BASE_DIAGNOSTIC_PATH, "er_hold_base_diagnostic")
    v6 = base.load_module(base.V6_ABLATION_PATH, "er_hold_v6_ablation")
    engine = base.load_module(base.ENGINE_PATH, "er_hold_pehc_engine")
    adapter = base.load_module(base.ADAPTER_PATH, "er_hold_v4_adapter")
    canonical_context, context = base.extended_context(adapter)
    features = FeatureBook(context)
    canonical_features = FeatureBook(canonical_context)

    control_canonical, control_canonical_result, _ = base.run_arm(
        v6,
        engine,
        canonical_context,
        "CONTROL",
        window=(0, base.CANONICAL_RIGHT),
        retain=True,
    )
    base.assert_control_anchor(control_canonical, control_canonical_result)
    control_extended, control_extended_result, _ = base.run_arm(
        v6,
        engine,
        context,
        "CONTROL",
        window=(0, context.book.count),
        retain=True,
    )
    base.assert_incident_trade(control_extended_result.raw.trades[-1])

    layer0 = layer0_event_study(
        engine,
        context,
        features,
        list(control_extended_result.raw.trades),
        list(control_canonical_result.raw.trades),
    )
    payload: dict[str, Any] = {
        "schema": "hype-1d-ma7-abt-v7-1-er-hold-overlay-diagnostic-v1",
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "status": "DIAGNOSTIC_ONLY_NOT_PROMOTED_NOT_LIVE_READY",
        "strategy_id": "HYPE-1D-MA7-ABT-V7.1",
        "candidate": {
            "id": "ER_GATED_OAPP",
            "rule": (
                "keep exact V7.1 OAPP activation; first confirm ungated; "
                "second confirm requires ER7 < median ER7 of canonical mature OAPP days"
            ),
        },
        "layer0": layer0,
        "canonical": {"CONTROL": compact_metrics(control_canonical)},
        "extended": {"CONTROL": compact_metrics(control_extended)},
        "stress": {},
        "recent_slices": {},
        "incident": {"control": incident_trade(base, control_extended_result)},
        "changed_long_episodes_vs_control": {},
        "pins": {
            "contract_sha256": sha256(CONTRACT_PATH),
            "script_sha256": sha256(Path(__file__).resolve()),
            "base_diagnostic_sha256": sha256(BASE_DIAGNOSTIC_PATH),
            "v7_ablation_artifact_sha256": sha256(V7_ABLATION_ARTIFACT),
        },
        "notes": [
            "Layer 0 uses unsigned Kaufman ER7 with lookback 7.",
            "Layer 1 runs only if 2026-08-15 ER7 is strictly above the canonical OAPP median.",
            "August results are revealed and may be terminal-censored.",
        ],
    }

    if layer0["separable"]:
        threshold = float(layer0["threshold_median_er7"])
        er_canonical, er_canonical_result, _ = run_er_gate(
            base,
            v6,
            engine,
            canonical_context,
            canonical_features,
            threshold,
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
        er_extended, er_extended_result, _ = run_er_gate(
            base,
            v6,
            engine,
            context,
            features,
            threshold,
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
            metrics, _, _ = run_er_gate(
                base,
                v6,
                engine,
                context,
                features,
                threshold,
                window=(0, context.book.count),
                slippage=slippage,
                signal_lag=lag,
                include_funding=funding,
            )
            stress[label] = compact_metrics(metrics)
        recent: dict[str, Any] = {}
        for label, days in base.RECENT_SLICES.items():
            metrics, _, _ = run_er_gate(
                base,
                v6,
                engine,
                context,
                features,
                threshold,
                window=(max(0, context.book.count - days), context.book.count),
            )
            recent[label] = compact_metrics(metrics)
        er_incident = incident_trade(base, er_extended_result)
        off_incident = incident_trade(base, off_extended_result)
        payload["canonical"]["ER_GATED"] = compact_metrics(er_canonical)
        payload["canonical"]["OAPP_OFF"] = compact_metrics(off_canonical)
        payload["extended"]["ER_GATED"] = compact_metrics(er_extended)
        payload["extended"]["OAPP_OFF"] = compact_metrics(off_extended)
        payload["stress"] = stress
        payload["recent_slices"] = recent
        payload["incident"].update(
            {
                "er_gated": er_incident,
                "oapp_off": off_incident,
                "er_gated_still_exits_2026_08_16": bool(
                    er_incident
                    and pd.Timestamp(er_incident["exit_ts"]) == base.INCIDENT_EXIT_TS
                    and str(er_incident["exit_reason"]).startswith("long_mfe_")
                ),
                "er_gated_terminal_censored": bool(
                    er_incident and er_incident["exit_reason"] == "terminal_flatten"
                ),
            }
        )
        payload["changed_long_episodes_vs_control"] = base.changed_long_episodes(
            list(control_extended_result.raw.trades),
            list(er_extended_result.raw.trades),
        )
        payload["activation_counts"] = {
            "CONTROL": dict(control_extended_result.activation_counts),
            "ER_GATED": dict(er_extended_result.activation_counts),
            "OAPP_OFF": dict(off_extended_result.activation_counts),
        }

    payload["verdict"] = decide_verdict(payload)
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
                "layer0": {
                    "separable": payload["layer0"]["separable"],
                    "threshold_median_er7": payload["layer0"]["threshold_median_er7"],
                    "incident_2026_08_15_er7": payload["layer0"]["incident_2026_08_15_er7"],
                    "summaries": payload["layer0"]["summaries"],
                    "canonical_oapp_mature_days": [
                        {
                            "ts": row["ts"],
                            "er7": row["er7"],
                            "signed_er7": row["signed_er7"],
                            "slope_atr": row["slope_atr"],
                            "pullback_atr": row["pullback_atr"],
                            "exit_reason": row["exit_reason"],
                        }
                        for row in payload["layer0"]["canonical_oapp_mature_days"]
                    ],
                    "incident_days": [
                        {
                            "ts": row["ts"],
                            "er7": row["er7"],
                            "signed_er7": row["signed_er7"],
                            "slope_atr": row["slope_atr"],
                            "oapp_count": row["oapp_count"],
                            "later_higher_high": row["later_higher_high"],
                        }
                        for row in payload["layer0"]["incident_days"]
                    ],
                },
                "canonical": payload.get("canonical"),
                "extended": payload.get("extended"),
                "incident": payload.get("incident"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
