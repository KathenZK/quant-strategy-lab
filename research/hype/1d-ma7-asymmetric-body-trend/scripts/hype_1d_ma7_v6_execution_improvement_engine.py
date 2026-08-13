"""Execution-improvement overlays for frozen HYPE MA7 ABT V6."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any, Callable

import numpy as np
import pandas as pd


PEHC_PATH = Path(__file__).with_name(
    "hype_1d_ma7_profit_exit_handoff_continuity_engine.py"
)
V6_CONFIG_SHA256 = (
    "b155a35133224e77266ba0c22fb84ba1657ab89212a700e9f551b3fa3431af00"
)


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_PEHC = _load_module(PEHC_PATH, "hype_v6_execution_pehc")
_BASE = _PEHC._BASE


@dataclass(frozen=True, slots=True)
class ExecutionImprovementConfig:
    arm_id: str
    mode: str
    distance_atr: float
    timeout_hours: int

    def __post_init__(self) -> None:
        if self.mode not in {"entry-only", "exit-only", "entry+exit"}:
            raise ValueError("invalid execution mode")
        if self.distance_atr not in {0.05, 0.10, 0.20}:
            raise ValueError("invalid distance_atr")
        if self.timeout_hours not in {6, 24}:
            raise ValueError("invalid timeout_hours")

    @property
    def entry_enabled(self) -> bool:
        return self.mode in {"entry-only", "entry+exit"}

    @property
    def exit_enabled(self) -> bool:
        return self.mode in {"exit-only", "entry+exit"}

    def canonical(self) -> dict[str, Any]:
        return asdict(self)


def config_sha256(config: ExecutionImprovementConfig) -> str:
    payload = json.dumps(
        config.canonical(), sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def grid_configs() -> list[ExecutionImprovementConfig]:
    rows: list[ExecutionImprovementConfig] = []
    for mode in ("entry-only", "exit-only", "entry+exit"):
        prefix = {"entry-only": "E", "exit-only": "X", "entry+exit": "EX"}[mode]
        for distance in (0.05, 0.10, 0.20):
            for timeout in (6, 24):
                rows.append(
                    ExecutionImprovementConfig(
                        arm_id=f"{prefix}_K{int(distance * 100):02d}_T{timeout:02d}",
                        mode=mode,
                        distance_atr=distance,
                        timeout_hours=timeout,
                    )
                )
    return rows


def fixed_v6_config() -> Any:
    config = _PEHC.PEHCConfig(
        arm_id="PEHC_294",
        expiry_days=8,
        slope_threshold=None,
        chase_cap_atr=math.inf,
        execution="next_utc_open",
        enabled=True,
        entry_enabled=True,
    )
    if _PEHC.config_sha256(config) != V6_CONFIG_SHA256:
        raise RuntimeError("frozen V6 PEHC_294 config drift")
    return config


class ExecutionRecorder:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def __call__(self, row: dict[str, Any]) -> None:
        self.events.append(dict(row))


def _finite(*values: float) -> bool:
    return all(math.isfinite(float(value)) for value in values)


def _fallback_hour(start_hour: int, timeout_hours: int) -> int:
    # A 24h timeout uses the last hour before the next daily decision boundary.
    return min(23, max(0, start_hour) + timeout_hours)


def _fill_from_limit_touch(
    *,
    side: int,
    kind: str,
    day_ts: pd.Timestamp,
    open_price: float,
    limit_price: float,
    hour: int,
    hourly_open: np.ndarray,
) -> tuple[pd.Timestamp, float]:
    hour_open = float(hourly_open[hour])
    if side > 0:
        fill_price = min(limit_price, hour_open) if kind == "entry" else max(limit_price, hour_open)
    else:
        fill_price = max(limit_price, hour_open) if kind == "entry" else min(limit_price, hour_open)
    if not math.isfinite(fill_price) or fill_price <= 0.0:
        fill_price = limit_price if math.isfinite(limit_price) else open_price
    return day_ts + pd.Timedelta(hours=hour), float(fill_price)


def execution_entry_fill(
    *,
    config: ExecutionImprovementConfig,
    side: int,
    ts: pd.Timestamp,
    price: float,
    index: int,
    signal_index: int,
    book: Any,
    features: Any,
    market_cost_rate: float,
    fee_rate: float,
    record: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    day_ts = pd.Timestamp(book.ts[index])
    start_hour = int(max(0, min(23, (pd.Timestamp(ts) - day_ts).components.hours)))
    atr = float(features.atr7[signal_index]) if signal_index >= 0 else math.nan
    if not config.entry_enabled or not _finite(price, atr) or atr <= 0.0:
        row = {
            "kind": "entry_market_original",
            "ts": pd.Timestamp(ts),
            "price": float(price),
            "cost_rate": float(market_cost_rate),
            "hour": start_hour,
        }
        record({"event": "entry_market_original", "index": int(index), "side": int(side), "price": float(price)})
        return row
    limit = float(price - side * config.distance_atr * atr)
    fallback_hour = _fallback_hour(start_hour, config.timeout_hours)
    hourly_low = features.hourly_low[index]
    hourly_high = features.hourly_high[index]
    hourly_open = features.hourly_open[index]
    touched_hour: int | None = None
    for hour in range(start_hour, fallback_hour + 1):
        low = float(hourly_low[hour])
        high = float(hourly_high[hour])
        if side > 0 and math.isfinite(low) and low <= limit:
            touched_hour = hour
            break
        if side < 0 and math.isfinite(high) and high >= limit:
            touched_hour = hour
            break
    if touched_hour is not None:
        fill_ts, fill_price = _fill_from_limit_touch(
            side=side,
            kind="entry",
            day_ts=day_ts,
            open_price=price,
            limit_price=limit,
            hour=touched_hour,
            hourly_open=hourly_open,
        )
        record(
            {
                "event": "entry_limit_fill",
                "index": int(index),
                "side": int(side),
                "hour": int(touched_hour),
                "original_price": float(price),
                "limit_price": float(limit),
                "fill_price": float(fill_price),
                "improvement": float(side * (price - fill_price)),
            }
        )
        return {
            "kind": "entry_limit_fill",
            "ts": fill_ts,
            "price": fill_price,
            "cost_rate": float(fee_rate),
            "hour": int(touched_hour),
        }
    fallback_price = float(hourly_open[fallback_hour])
    if not math.isfinite(fallback_price) or fallback_price <= 0.0:
        fallback_price = float(price)
        fallback_hour = start_hour
    fallback_ts = day_ts + pd.Timedelta(hours=fallback_hour)
    record(
        {
            "event": "entry_market_fallback",
            "index": int(index),
            "side": int(side),
            "hour": int(fallback_hour),
            "original_price": float(price),
            "limit_price": float(limit),
            "fill_price": float(fallback_price),
            "improvement": float(side * (price - fallback_price)),
        }
    )
    return {
        "kind": "entry_market_fallback",
        "ts": fallback_ts,
        "price": fallback_price,
        "cost_rate": float(market_cost_rate),
        "hour": int(fallback_hour),
    }


def execution_exit_fill(
    *,
    config: ExecutionImprovementConfig,
    side: int,
    ts: pd.Timestamp,
    price: float,
    reason: str,
    index: int,
    signal_index: int,
    stop_price: float,
    book: Any,
    features: Any,
    market_cost_rate: float,
    fee_rate: float,
    record: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    day_ts = pd.Timestamp(book.ts[index])
    start_hour = int(max(0, min(23, (pd.Timestamp(ts) - day_ts).components.hours)))
    atr = float(features.atr7[signal_index]) if signal_index >= 0 else math.nan
    if reason == "protective_stop" or not config.exit_enabled or not _finite(price, atr) or atr <= 0.0:
        record({"event": "exit_market_original", "index": int(index), "side": int(side), "reason": reason, "price": float(price)})
        return {
            "kind": "exit_market_original",
            "ts": pd.Timestamp(ts),
            "price": float(price),
            "reason": reason,
            "cost_rate": float(market_cost_rate),
        }
    limit = float(price + side * config.distance_atr * atr)
    fallback_hour = _fallback_hour(start_hour, config.timeout_hours)
    hourly_low = features.hourly_low[index]
    hourly_high = features.hourly_high[index]
    hourly_open = features.hourly_open[index]
    limit_hour: int | None = None
    stop_hour: int | None = None
    for hour in range(start_hour, fallback_hour + 1):
        high = float(hourly_high[hour])
        low = float(hourly_low[hour])
        if side > 0 and math.isfinite(high) and high >= limit:
            limit_hour = hour
            break
        if side < 0 and math.isfinite(low) and low <= limit:
            limit_hour = hour
            break
    if math.isfinite(stop_price):
        for hour in range(start_hour, fallback_hour + 1):
            high = float(hourly_high[hour])
            low = float(hourly_low[hour])
            if side > 0 and math.isfinite(low) and low <= stop_price:
                stop_hour = hour
                break
            if side < 0 and math.isfinite(high) and high >= stop_price:
                stop_hour = hour
                break
    if stop_hour is not None and (limit_hour is None or stop_hour <= limit_hour):
        stop_open = float(hourly_open[stop_hour])
        if side > 0:
            fill_price = min(stop_price, stop_open) if math.isfinite(stop_open) else stop_price
        else:
            fill_price = max(stop_price, stop_open) if math.isfinite(stop_open) else stop_price
        record(
            {
                "event": "exit_stop_during_wait",
                "index": int(index),
                "side": int(side),
                "hour": int(stop_hour),
                "original_reason": reason,
                "fill_price": float(fill_price),
            }
        )
        return {
            "kind": "exit_stop_during_wait",
            "ts": day_ts + pd.Timedelta(hours=stop_hour),
            "price": float(fill_price),
            "reason": "protective_stop",
            "cost_rate": float(market_cost_rate),
        }
    if limit_hour is not None:
        fill_ts, fill_price = _fill_from_limit_touch(
            side=side,
            kind="exit",
            day_ts=day_ts,
            open_price=price,
            limit_price=limit,
            hour=limit_hour,
            hourly_open=hourly_open,
        )
        record(
            {
                "event": "exit_limit_fill",
                "index": int(index),
                "side": int(side),
                "hour": int(limit_hour),
                "reason": reason,
                "original_price": float(price),
                "limit_price": float(limit),
                "fill_price": float(fill_price),
                "improvement": float(side * (fill_price - price)),
            }
        )
        return {
            "kind": "exit_limit_fill",
            "ts": fill_ts,
            "price": fill_price,
            "reason": reason,
            "cost_rate": float(fee_rate),
        }
    fallback_price = float(hourly_open[fallback_hour])
    if not math.isfinite(fallback_price) or fallback_price <= 0.0:
        fallback_price = float(price)
        fallback_hour = start_hour
    record(
        {
            "event": "exit_market_fallback",
            "index": int(index),
            "side": int(side),
            "hour": int(fallback_hour),
            "reason": reason,
            "original_price": float(price),
            "limit_price": float(limit),
            "fill_price": float(fallback_price),
            "improvement": float(side * (fallback_price - price)),
        }
    )
    return {
        "kind": "exit_market_fallback",
        "ts": day_ts + pd.Timedelta(hours=fallback_hour),
        "price": fallback_price,
        "reason": reason,
        "cost_rate": float(market_cost_rate),
    }


def _replace_once(source: str, old: str, new: str, label: str) -> str:
    return _BASE._replace_once(source, old, new, label)


def _apply_execution_state(source: str) -> str:
    source = _replace_once(
        source,
        "    pehc_entry_start_hour = 0\n\n    def trade_to(",
        "    pehc_entry_start_hour = 0\n    exec_last_entry_hour = -1\n    exec_entry_kind = \"\"\n    exec_entry_cost_rate = cost_rate\n\n    def trade_to(",
        "execution state init",
    )
    source = _replace_once(
        source,
        "    def trade_to(\ntarget_side: int, price: float) -> None:\n        nonlocal equity, qty, side, total_turnover, total_cost\n        old_equity = equity\n        qty, equity, turnover = _target_quantity(\n            equity, qty, target_side, price, cost_rate\n        )\n",
        "    def trade_to(\ntarget_side: int, price: float, execution_cost_rate: float = cost_rate) -> None:\n        nonlocal equity, qty, side, total_turnover, total_cost\n        old_equity = equity\n        qty, equity, turnover = _target_quantity(\n            equity, qty, target_side, price, execution_cost_rate\n        )\n",
        "execution cost-aware trade_to",
    )
    source = _replace_once(
        source,
        "        price: float,\n        index: int,\n        signal_index: int,\n    ) -> None:\n",
        "        price: float,\n        index: int,\n        signal_index: int,\n        execution_cost_rate: float = cost_rate,\n        execution_kind: str = \"market_original\",\n    ) -> None:\n",
        "execution enter signature",
    )
    source = _replace_once(
        source,
        "        nonlocal bars_held, stop_price, highest_close, lowest_close, mark_price\n",
        "        nonlocal bars_held, stop_price, highest_close, lowest_close, mark_price\n        nonlocal exec_last_entry_hour, exec_entry_kind, exec_entry_cost_rate\n",
        "execution enter nonlocal",
    )
    source = _replace_once(
        source,
        "        before = equity\n        wtl_set_entry_context(config.side, price, signal_index)\n        trade_to(config.side, price)\n        wtl_entry_leverage = wtl_last_entry_leverage()\n",
        "        fill = execution_entry_fill(\n            config=exec_config,\n            side=config.side,\n            ts=ts,\n            price=price,\n            index=index,\n            signal_index=signal_index,\n            book=book,\n            features=features,\n            market_cost_rate=cost_rate,\n            fee_rate=FEE,\n            record=exec_record,\n        )\n        ts = fill[\"ts\"]\n        price = float(fill[\"price\"])\n        execution_cost_rate = float(fill[\"cost_rate\"])\n        execution_kind = str(fill[\"kind\"])\n        exec_last_entry_hour = int(fill[\"hour\"])\n        exec_entry_kind = execution_kind\n        exec_entry_cost_rate = execution_cost_rate\n        before = equity\n        wtl_set_entry_context(config.side, price, signal_index)\n        trade_to(config.side, price, execution_cost_rate)\n        wtl_entry_leverage = wtl_last_entry_leverage()\n",
        "execution entry fill",
    )
    source = _replace_once(
        source,
        "        price: float,\n        reason: str,\n        index: int,\n    ) -> None:\n",
        "        price: float,\n        reason: str,\n        index: int,\n        execution_cost_rate: float = cost_rate,\n        execution_kind: str = \"market_original\",\n    ) -> None:\n",
        "execution close signature",
    )
    source = _replace_once(
        source,
        "        old_side = entry_side\n        trade_to(0, price)\n        trades.append(\n",
        "        old_side = entry_side\n        trade_to(0, price, execution_cost_rate)\n        exec_record({\n            \"event\": \"close_execution\",\n            \"index\": int(index),\n            \"side\": int(old_side),\n            \"reason\": reason,\n            \"kind\": execution_kind,\n            \"price\": float(price),\n        })\n        trades.append(\n",
        "execution close cost",
    )
    source = _replace_once(
        source,
        '                "exit_reason": reason,\n',
        '                "exit_reason": reason,\n                "entry_execution_kind": exec_entry_kind,\n                "entry_execution_cost_rate": exec_entry_cost_rate,\n                "exit_execution_kind": execution_kind,\n                "exit_execution_cost_rate": execution_cost_rate,\n',
        "execution trade field",
    )
    source = _replace_once(
        source,
        "        entered_pending_reversal = False\n        pehc_entry_start_hour = 0\n        decision_index = index - 1 - signal_lag\n",
        "        entered_pending_reversal = False\n        pehc_entry_start_hour = 0\n        exec_last_entry_hour = -1\n        decision_index = index - 1 - signal_lag\n",
        "execution daily reset",
    )
    source = _replace_once(
        source,
        "        post_action_equity = equity\n",
        "        if exec_last_entry_hour > 0:\n            entered_after_open = True\n            pehc_entry_start_hour = max(pehc_entry_start_hour, exec_last_entry_hour)\n        post_action_equity = equity\n",
        "execution entry hour propagation",
    )
    return source


def _apply_execution_exit(source: str) -> str:
    source = _replace_once(
        source,
        "            if reason:\n                close(ts, current_open, reason, index)\n                cooldown_left = config.cooldown_days\n",
        "            if reason:\n                exit_fill = execution_exit_fill(\n                    config=exec_config,\n                    side=side,\n                    ts=ts,\n                    price=current_open,\n                    reason=reason,\n                    index=index,\n                    signal_index=decision_index,\n                    stop_price=stop_price,\n                    book=book,\n                    features=features,\n                    market_cost_rate=cost_rate,\n                    fee_rate=FEE,\n                    record=exec_record,\n                )\n                close(\n                    exit_fill[\"ts\"],\n                    float(exit_fill[\"price\"]),\n                    str(exit_fill[\"reason\"]),\n                    index,\n                    float(exit_fill[\"cost_rate\"]),\n                    str(exit_fill[\"kind\"]),\n                )\n                cooldown_left = config.cooldown_days\n",
        "execution open exit fill",
    )
    return source


def build_variant_function(
    context: Any,
    config: ExecutionImprovementConfig,
    *,
    pehc_config: Any,
    oapp_config: Any,
    entry_signal: Any,
    leverage_policy: Any,
    rsi6: np.ndarray,
    pehc_recorder: Any,
    exec_recorder: ExecutionRecorder,
) -> tuple[Callable[..., Any], str]:
    source = _BASE._capture_exact_source(context)
    digest = hashlib.sha256(config.arm_id.encode()).hexdigest()[:12]
    function_name = f"exec_{digest}_backtest"
    source = _replace_once(source, "def v3_ma_only_backtest(", f"def {function_name}(", "execution function name")
    source = _BASE._apply_state(source)
    source = _BASE._apply_exits(source)
    source = _PEHC._apply_pehc_state(source)
    source = _PEHC._apply_pehc_arm(source)
    source = _PEHC._apply_pehc_daily(source)
    source = _PEHC._apply_pehc_intraday(source)
    source = _apply_execution_state(source)
    source = _apply_execution_exit(source)
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
            "wtl_exit_decision": _BASE.lifecycle_exit_decision,
            "pehc_enabled": pehc_config.enabled,
            "pehc_entry_enabled": pehc_config.entry_enabled,
            "pehc_blocked_origin_indices": frozenset(pehc_config.blocked_origin_indices),
            "pehc_allowed_origin_indices": frozenset(pehc_config.allowed_origin_indices),
            "pehc_expiry_days": pehc_config.expiry_days,
            "pehc_slope_threshold": pehc_config.slope_threshold,
            "pehc_chase_cap_atr": pehc_config.chase_cap_atr,
            "pehc_execution": pehc_config.execution,
            "pehc_handoff_eligibility": _PEHC.handoff_eligibility,
            "pehc_record": pehc_recorder,
            "exec_config": config,
            "exec_record": exec_recorder,
            "execution_entry_fill": execution_entry_fill,
            "execution_exit_fill": execution_exit_fill,
        }
    )
    compiled = compile(source, f"<v6-exec-{config.arm_id}>", "exec")
    exec(compiled, namespace)
    return namespace[function_name], hashlib.sha256(source.encode()).hexdigest()


@dataclass(slots=True)
class ExecutionImprovementResult:
    config: ExecutionImprovementConfig
    raw: Any
    source_sha256: str
    execution_events: list[dict[str, Any]]
    native_entry_events: list[dict[str, Any]]
    handoff_events: list[dict[str, Any]]
    activation_counts: dict[str, int]
    rsi6: np.ndarray


def _counts(raw: Any, execution_events: list[dict[str, Any]], handoff_events: list[dict[str, Any]]) -> dict[str, int]:
    exits = [str(row.get("exit_reason", "")) for row in raw.trades]
    counts = {
        "long_trail_exit": sum(reason.startswith("long_mfe_") for reason in exits),
        "short_rsi_exit": sum(reason == "short_rsi_take_profit" for reason in exits),
        "protective_stop": sum(reason == "protective_stop" for reason in exits),
        "handoff_accept": sum(row.get("event") == "handoff_accept" for row in handoff_events),
        "shadow_start": sum(row.get("event") == "shadow_start" for row in handoff_events),
    }
    for event in (
        "entry_limit_fill",
        "entry_market_fallback",
        "entry_market_original",
        "exit_limit_fill",
        "exit_market_fallback",
        "exit_market_original",
        "exit_stop_during_wait",
    ):
        counts[event] = sum(row.get("event") == event for row in execution_events)
    counts["limit_fill_total"] = counts["entry_limit_fill"] + counts["exit_limit_fill"]
    counts["fallback_total"] = counts["entry_market_fallback"] + counts["exit_market_fallback"]
    return counts


def run_variant(
    context: Any,
    config: ExecutionImprovementConfig,
    *,
    start_index: int,
    terminal_index: int,
    slippage: float = 0.0004,
    signal_lag: int = 0,
    include_funding: bool = True,
    retain: bool = False,
) -> ExecutionImprovementResult:
    if not (0 <= start_index < terminal_index <= context.book.count):
        raise ValueError("invalid execution-improvement window")
    pehc_config = fixed_v6_config()
    oapp_config = _PEHC.fixed_oapp_config(short_rsi_enabled=True)
    rsi6 = _BASE.wilder_rsi6(context.book.close)
    entry_signal = _BASE.EntryQualitySignal(context.engine, oapp_config.entry)
    leverage_policy = _BASE.LeveragePolicy(context, None)
    pehc_recorder = _PEHC.HandoffRecorder()
    exec_recorder = ExecutionRecorder()
    function, source_hash = build_variant_function(
        context,
        config,
        pehc_config=pehc_config,
        oapp_config=oapp_config,
        entry_signal=entry_signal,
        leverage_policy=leverage_policy,
        rsi6=rsi6,
        pehc_recorder=pehc_recorder,
        exec_recorder=exec_recorder,
    )
    raw = function(
        context.book,
        context.features,
        long_config=context.long_config,
        short_config=context.short_config,
        start_index=start_index,
        terminal_index=terminal_index,
        slippage=slippage,
        signal_lag=signal_lag,
        include_funding=include_funding,
        retain=retain,
    )
    if bool(raw.metrics.get("bankrupt_intraday")):
        raise RuntimeError(f"{config.arm_id} became bankrupt")
    execution_events = list(exec_recorder.events)
    handoff_events = list(pehc_recorder.events)
    return ExecutionImprovementResult(
        config=config,
        raw=raw,
        source_sha256=source_hash,
        execution_events=execution_events,
        native_entry_events=list(entry_signal.events),
        handoff_events=handoff_events,
        activation_counts=_counts(raw, execution_events, handoff_events),
        rsi6=rsi6,
    )


def run_v6(
    context: Any,
    *,
    start_index: int,
    terminal_index: int,
    slippage: float = 0.0004,
    signal_lag: int = 0,
    include_funding: bool = True,
    retain: bool = False,
) -> Any:
    return _PEHC.run_variant(
        context,
        fixed_v6_config(),
        start_index=start_index,
        terminal_index=terminal_index,
        slippage=slippage,
        signal_lag=signal_lag,
        include_funding=include_funding,
        retain=retain,
        short_rsi_enabled=True,
    )
