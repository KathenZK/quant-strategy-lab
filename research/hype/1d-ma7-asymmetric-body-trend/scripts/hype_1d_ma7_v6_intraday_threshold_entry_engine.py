"""Intraday ATR-threshold entry overlays for frozen HYPE MA7 ABT V6."""

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


_PEHC = _load_module(PEHC_PATH, "hype_v6_intraday_threshold_pehc")
_BASE = _PEHC._BASE


@dataclass(frozen=True, slots=True)
class IntradayThresholdEntryConfig:
    arm_id: str
    threshold_atr: float
    fresh_only: bool = True

    def __post_init__(self) -> None:
        allowed = {0.25, 0.50, 0.65, 0.80, 1.00}
        if self.threshold_atr not in allowed:
            raise ValueError(f"invalid threshold_atr: {self.threshold_atr}")
        if not self.fresh_only:
            raise ValueError("only fresh threshold crossings are frozen for this diagnostic")

    def canonical(self) -> dict[str, Any]:
        return asdict(self)


def config_sha256(config: IntradayThresholdEntryConfig) -> str:
    payload = json.dumps(
        config.canonical(), sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def grid_configs() -> list[IntradayThresholdEntryConfig]:
    return [
        IntradayThresholdEntryConfig(
            arm_id=f"ITE_K{int(round(threshold * 100)):03d}",
            threshold_atr=threshold,
        )
        for threshold in (0.25, 0.50, 0.65, 0.80, 1.00)
    ]


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


class ThresholdRecorder:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def __call__(self, event: dict[str, Any]) -> None:
        self.events.append(dict(event))


def _finite(*values: float) -> bool:
    return all(math.isfinite(float(value)) for value in values)


def _fill_price_for_touch(
    *,
    side: int,
    level: float,
    hour_open: float,
) -> float:
    if not math.isfinite(hour_open) or hour_open <= 0.0:
        return float(level)
    if side > 0:
        return float(hour_open if hour_open >= level else level)
    return float(hour_open if hour_open <= level else level)


def intraday_threshold_entry(
    *,
    config: IntradayThresholdEntryConfig,
    long_config: Any | None,
    short_config: Any | None,
    book: Any,
    features: Any,
    index: int,
    signal_index: int,
    record: Callable[[dict[str, Any]], None],
) -> dict[str, Any] | None:
    if signal_index < 0 or index < 0:
        return None
    ma7 = float(features.ma7[signal_index])
    atr7 = float(features.atr7[signal_index])
    previous_close = float(book.close[signal_index])
    if not _finite(ma7, atr7, previous_close) or atr7 <= 0.0:
        record(
            {
                "event": "threshold_skip_nonfinite",
                "index": int(index),
                "signal_index": int(signal_index),
            }
        )
        return None

    threshold = float(config.threshold_atr)
    upper = ma7 + threshold * atr7
    lower = ma7 - threshold * atr7
    long_fresh = long_config is not None and previous_close < upper
    short_fresh = short_config is not None and previous_close > lower
    if not long_fresh and not short_fresh:
        return None

    long_hit: tuple[int, float] | None = None
    short_hit: tuple[int, float] | None = None
    hourly_high = features.hourly_high[index]
    hourly_low = features.hourly_low[index]
    hourly_open = features.hourly_open[index]
    for hour in range(24):
        open_price = float(hourly_open[hour])
        high = float(hourly_high[hour])
        low = float(hourly_low[hour])
        if long_hit is None and long_fresh and math.isfinite(high) and high >= upper:
            long_hit = (
                hour,
                _fill_price_for_touch(side=1, level=upper, hour_open=open_price),
            )
        if short_hit is None and short_fresh and math.isfinite(low) and low <= lower:
            short_hit = (
                hour,
                _fill_price_for_touch(side=-1, level=lower, hour_open=open_price),
            )
        if long_hit is not None and short_hit is not None:
            break

    if long_hit is None and short_hit is None:
        return None
    if long_hit is not None and short_hit is not None and long_hit[0] == short_hit[0]:
        record(
            {
                "event": "threshold_skip_same_hour_ambiguous",
                "index": int(index),
                "signal_index": int(signal_index),
                "hour": int(long_hit[0]),
                "upper": float(upper),
                "lower": float(lower),
                "previous_close": previous_close,
            }
        )
        return None

    if short_hit is None or (long_hit is not None and long_hit[0] < short_hit[0]):
        side = 1
        hour, fill_price = long_hit
        selected = long_config
        level = upper
    else:
        side = -1
        hour, fill_price = short_hit
        selected = short_config
        level = lower

    if selected is None:
        return None
    ts = pd.Timestamp(book.ts[index]) + pd.Timedelta(hours=hour)
    record(
        {
            "event": "threshold_entry",
            "index": int(index),
            "signal_index": int(signal_index),
            "ts": ts.isoformat(),
            "side": int(side),
            "hour": int(hour),
            "threshold_atr": threshold,
            "ma7": ma7,
            "atr7": atr7,
            "previous_close": previous_close,
            "level": float(level),
            "fill_price": float(fill_price),
        }
    )
    return {
        "config": selected,
        "ts": ts,
        "price": float(fill_price),
        "hour": int(hour),
    }


def _replace_once(source: str, old: str, new: str, label: str) -> str:
    return _BASE._replace_once(source, old, new, label)


def _apply_threshold_entry(source: str) -> str:
    old = """\
        if index < terminal_index and side == 0:
            if cooldown_left > 0:
                if not exited_at_open:
                    cooldown_left -= 1
            else:
                selected: Config | None = None
                signal_index = max(0, decision_index)
                if long_config is not None and close_entry_signal(
                    long_config,
                    book,
                    features,
                    signal_index,
                ):
                    selected = long_config
                elif short_config is not None and close_entry_signal(
                    short_config,
                    book,
                    features,
                    signal_index,
                ):
                    selected = short_config
                elif (
                    short_config is not None
                    and open_entry_signal(
                        short_config,
                        book,
                        features,
                        index - signal_lag,
                    )
                ):
                    selected = short_config
                if selected is not None:
                    fill_ts = ts
                    fill_price = current_open
                    if selected.entry_mode == "open_regime" and signal_lag == 0:
                        fill_ts = ts + pd.Timedelta(hours=1)
                        fill_price = float(book.short_entry_open[index])
                        entered_after_open = True
                        pehc_entry_start_hour = 1
                    enter(selected, fill_ts, fill_price, index, signal_index)
                    action = "enter_long" if selected.side > 0 else "enter_short"
"""
    new = """\
        if index < terminal_index and side == 0:
            if cooldown_left > 0:
                if not exited_at_open:
                    cooldown_left -= 1
            else:
                signal_index = max(0, decision_index)
                threshold_fill = intraday_threshold_entry(
                    config=threshold_config,
                    long_config=long_config,
                    short_config=short_config,
                    book=book,
                    features=features,
                    index=index,
                    signal_index=signal_index,
                    record=threshold_record,
                )
                if threshold_fill is not None:
                    selected = threshold_fill["config"]
                    fill_ts = threshold_fill["ts"]
                    fill_price = float(threshold_fill["price"])
                    entered_after_open = True
                    pehc_entry_start_hour = int(threshold_fill["hour"])
                    enter(selected, fill_ts, fill_price, index, signal_index)
                    action = "threshold_enter_long" if selected.side > 0 else "threshold_enter_short"
"""
    return _replace_once(source, old, new, "intraday threshold entry block")


def build_variant_function(
    context: Any,
    config: IntradayThresholdEntryConfig,
    *,
    pehc_config: Any,
    oapp_config: Any,
    entry_signal: Any,
    leverage_policy: Any,
    rsi6: np.ndarray,
    pehc_recorder: Any,
    threshold_recorder: ThresholdRecorder,
) -> tuple[Callable[..., Any], str]:
    source = _BASE._capture_exact_source(context)
    digest = hashlib.sha256(config.arm_id.encode()).hexdigest()[:12]
    function_name = f"threshold_{digest}_backtest"
    source = _replace_once(
        source, "def v3_ma_only_backtest(", f"def {function_name}(", "threshold function name"
    )
    source = _BASE._apply_state(source)
    source = _BASE._apply_exits(source)
    source = _PEHC._apply_pehc_state(source)
    source = _PEHC._apply_pehc_arm(source)
    source = _PEHC._apply_pehc_daily(source)
    source = _PEHC._apply_pehc_intraday(source)
    source = _apply_threshold_entry(source)
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
            "threshold_config": config,
            "threshold_record": threshold_recorder,
            "intraday_threshold_entry": intraday_threshold_entry,
        }
    )
    compiled = compile(source, f"<v6-intraday-threshold-{config.arm_id}>", "exec")
    exec(compiled, namespace)
    return namespace[function_name], hashlib.sha256(source.encode()).hexdigest()


@dataclass(slots=True)
class IntradayThresholdEntryResult:
    config: IntradayThresholdEntryConfig
    raw: Any
    source_sha256: str
    threshold_events: list[dict[str, Any]]
    native_entry_events: list[dict[str, Any]]
    handoff_events: list[dict[str, Any]]
    activation_counts: dict[str, int]
    rsi6: np.ndarray


def _counts(
    raw: Any, threshold_events: list[dict[str, Any]], handoff_events: list[dict[str, Any]]
) -> dict[str, int]:
    exits = [str(row.get("exit_reason", "")) for row in raw.trades]
    return {
        "threshold_entry": sum(row.get("event") == "threshold_entry" for row in threshold_events),
        "threshold_ambiguous": sum(
            row.get("event") == "threshold_skip_same_hour_ambiguous"
            for row in threshold_events
        ),
        "long_trail_exit": sum(reason.startswith("long_mfe_") for reason in exits),
        "short_rsi_exit": sum(reason == "short_rsi_take_profit" for reason in exits),
        "protective_stop": sum(reason == "protective_stop" for reason in exits),
        "handoff_accept": sum(row.get("event") == "handoff_accept" for row in handoff_events),
        "shadow_start": sum(row.get("event") == "shadow_start" for row in handoff_events),
    }


def run_variant(
    context: Any,
    config: IntradayThresholdEntryConfig,
    *,
    start_index: int,
    terminal_index: int,
    slippage: float = 0.0004,
    signal_lag: int = 0,
    include_funding: bool = True,
    retain: bool = False,
) -> IntradayThresholdEntryResult:
    if not (0 <= start_index < terminal_index <= context.book.count):
        raise ValueError("invalid intraday-threshold window")
    pehc_config = fixed_v6_config()
    oapp_config = _PEHC.fixed_oapp_config(short_rsi_enabled=True)
    rsi6 = _BASE.wilder_rsi6(context.book.close)
    entry_signal = _BASE.EntryQualitySignal(context.engine, oapp_config.entry)
    leverage_policy = _BASE.LeveragePolicy(context, None)
    pehc_recorder = _PEHC.HandoffRecorder()
    threshold_recorder = ThresholdRecorder()
    function, source_hash = build_variant_function(
        context,
        config,
        pehc_config=pehc_config,
        oapp_config=oapp_config,
        entry_signal=entry_signal,
        leverage_policy=leverage_policy,
        rsi6=rsi6,
        pehc_recorder=pehc_recorder,
        threshold_recorder=threshold_recorder,
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
    threshold_events = list(threshold_recorder.events)
    handoff_events = list(pehc_recorder.events)
    return IntradayThresholdEntryResult(
        config=config,
        raw=raw,
        source_sha256=source_hash,
        threshold_events=threshold_events,
        native_entry_events=list(entry_signal.events),
        handoff_events=handoff_events,
        activation_counts=_counts(raw, threshold_events, handoff_events),
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
