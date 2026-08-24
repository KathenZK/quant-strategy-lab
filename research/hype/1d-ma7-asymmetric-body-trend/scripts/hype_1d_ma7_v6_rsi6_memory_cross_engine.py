"""RSI6 extreme-memory MA7-cross entry overlay on frozen exact V6."""

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


PEHC_PATH = Path(__file__).with_name(
    "hype_1d_ma7_profit_exit_handoff_continuity_engine.py"
)
V6_CONFIG_SHA256 = (
    "b155a35133224e77266ba0c22fb84ba1657ab89212a700e9f551b3fa3431af00"
)
WINDOW_MODES = ("PRIOR5", "INCLUSIVE5")


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_PEHC = _load_module(PEHC_PATH, "hype_v6_rsi_memory_pehc")
_BASE = _PEHC._BASE


@dataclass(frozen=True, slots=True)
class RSIMemoryCrossConfig:
    arm_id: str
    window_mode: str = "PRIOR5"
    long_enabled: bool = True
    short_enabled: bool = True
    native_enabled: bool = True
    lookback_days: int = 5
    required_days: int = 3
    oversold_threshold: float = 30.0
    overbought_threshold: float = 70.0

    def __post_init__(self) -> None:
        if not self.arm_id:
            raise ValueError("arm_id is required")
        if self.window_mode not in WINDOW_MODES:
            raise ValueError("unknown RSI memory window mode")
        if self.lookback_days != 5 or self.required_days != 3:
            raise ValueError("RSI memory lookback/count are frozen at 5/3")
        if self.oversold_threshold != 30.0 or self.overbought_threshold != 70.0:
            raise ValueError("RSI memory thresholds are frozen at 30/70")

    def canonical(self) -> dict[str, Any]:
        return asdict(self)


def config_sha256(config: RSIMemoryCrossConfig) -> str:
    payload = json.dumps(
        config.canonical(), sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(payload.encode()).hexdigest()


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


class RSIMemoryCrossSignal:
    """OR exact-V6 native entries with a causal RSI-memory cross signal."""

    def __init__(
        self,
        native_signal: Callable[[Any, Any, Any, int], bool],
        config: RSIMemoryCrossConfig,
        rsi6: np.ndarray,
    ) -> None:
        self.native_signal = native_signal
        self.config = config
        self.rsi6 = rsi6
        self.events: list[dict[str, Any]] = []
        self.cache: dict[tuple[int, int], bool] = {}

    @staticmethod
    def _finite(*values: float) -> bool:
        return all(math.isfinite(float(value)) for value in values)

    @staticmethod
    def _side_name(side: int) -> str:
        return "long" if side > 0 else "short"

    def _enabled(self, side: int) -> bool:
        return self.config.long_enabled if side > 0 else self.config.short_enabled

    def _window(self, index: int) -> tuple[int, int]:
        if self.config.window_mode == "PRIOR5":
            return index - self.config.lookback_days, index
        return index - self.config.lookback_days + 1, index + 1

    def _memory_signal(
        self, side: int, book: Any, features: Any, index: int
    ) -> tuple[bool, dict[str, Any] | None]:
        if not self._enabled(side) or index < 1:
            return False, None
        start, end = self._window(index)
        if start < 0 or end > len(self.rsi6) or end - start != 5:
            return False, None
        prior_close = float(book.close[index - 1])
        prior_ma7 = float(features.ma7[index - 1])
        close = float(book.close[index])
        ma7 = float(features.ma7[index])
        if not self._finite(prior_close, prior_ma7, close, ma7):
            return False, None
        cross = (
            prior_close <= prior_ma7 and close > ma7
            if side > 0
            else prior_close >= prior_ma7 and close < ma7
        )
        if not cross:
            return False, None
        values = np.asarray(self.rsi6[start:end], dtype=float)
        finite = bool(np.isfinite(values).all())
        extreme_days = (
            int(np.sum(values < self.config.oversold_threshold))
            if side > 0 and finite
            else int(np.sum(values > self.config.overbought_threshold))
            if finite
            else 0
        )
        passed = finite and extreme_days >= self.config.required_days
        return bool(passed), {
            "event": "rsi_memory_cross_pass" if passed else "rsi_memory_cross_reject",
            "signal_index": int(index),
            "side": self._side_name(side),
            "window_mode": self.config.window_mode,
            "window_start_index": int(start),
            "window_end_exclusive": int(end),
            "extreme_days": int(extreme_days),
            "required_days": self.config.required_days,
            "rsi6_values": values.tolist() if finite else None,
        }

    def __call__(self, config: Any, book: Any, features: Any, index: int) -> bool:
        side = int(config.side)
        key = (int(index), side)
        if key in self.cache:
            return self.cache[key]
        native = bool(
            self.config.native_enabled
            and self.native_signal(config, book, features, index)
        )
        memory, event = self._memory_signal(side, book, features, index)
        if event is not None:
            event["native_also_passed"] = native
            self.events.append(event)
        result = bool(native or memory)
        self.cache[key] = result
        return result


@dataclass(slots=True)
class RSIMemoryCrossExecutionResult:
    config: RSIMemoryCrossConfig
    raw: Any
    source_sha256: str
    memory_events: list[dict[str, Any]]
    native_entry_events: list[dict[str, Any]]
    handoff_events: list[dict[str, Any]]
    activation_counts: dict[str, int]
    rsi6: np.ndarray


def _counts(
    raw: Any,
    memory_events: list[dict[str, Any]],
    handoff_events: list[dict[str, Any]],
) -> dict[str, int]:
    exits = [str(row.get("exit_reason", "")) for row in raw.trades]
    return {
        "memory_pass": sum(
            row["event"] == "rsi_memory_cross_pass" for row in memory_events
        ),
        "memory_reject": sum(
            row["event"] == "rsi_memory_cross_reject" for row in memory_events
        ),
        "memory_long_pass": sum(
            row["event"] == "rsi_memory_cross_pass" and row["side"] == "long"
            for row in memory_events
        ),
        "memory_short_pass": sum(
            row["event"] == "rsi_memory_cross_pass" and row["side"] == "short"
            for row in memory_events
        ),
        "memory_pass_native_overlap": sum(
            row["event"] == "rsi_memory_cross_pass"
            and bool(row["native_also_passed"])
            for row in memory_events
        ),
        "handoff_accept": sum(
            row.get("event") == "handoff_accept" for row in handoff_events
        ),
        "long_trail_exit": sum(reason.startswith("long_mfe_") for reason in exits),
        "short_rsi_exit": sum(reason == "short_rsi_take_profit" for reason in exits),
        "protective_stop": sum(reason == "protective_stop" for reason in exits),
    }


def run_variant(
    context: Any,
    config: RSIMemoryCrossConfig,
    *,
    start_index: int,
    terminal_index: int,
    slippage: float = 0.0004,
    include_funding: bool = True,
    retain: bool = False,
) -> RSIMemoryCrossExecutionResult:
    if not (0 <= start_index < terminal_index <= context.book.count):
        raise ValueError("invalid RSI-memory window")
    pehc_config = fixed_v6_config()
    oapp_config = _PEHC.fixed_oapp_config(short_rsi_enabled=True)
    rsi6 = _BASE.wilder_rsi6(context.book.close)
    native_entry_signal = _BASE.EntryQualitySignal(
        context.engine, oapp_config.entry
    )
    entry_signal = RSIMemoryCrossSignal(native_entry_signal, config, rsi6)
    leverage_policy = _BASE.LeveragePolicy(context, None)
    recorder = _PEHC.HandoffRecorder()
    function, source_hash = _PEHC.build_variant_function(
        context,
        pehc_config,
        oapp_config=oapp_config,
        entry_signal=entry_signal,
        leverage_policy=leverage_policy,
        rsi6=rsi6,
        recorder=recorder,
    )
    raw = function(
        context.book,
        context.features,
        long_config=context.long_config,
        short_config=context.short_config,
        start_index=start_index,
        terminal_index=terminal_index,
        slippage=slippage,
        signal_lag=0,
        include_funding=include_funding,
        retain=retain,
    )
    if bool(raw.metrics.get("bankrupt_intraday")):
        raise RuntimeError(f"{config.arm_id} became bankrupt")
    memory_events = list(entry_signal.events)
    handoff_events = list(recorder.events)
    return RSIMemoryCrossExecutionResult(
        config=config,
        raw=raw,
        source_sha256=source_hash,
        memory_events=memory_events,
        native_entry_events=list(native_entry_signal.events),
        handoff_events=handoff_events,
        activation_counts=_counts(raw, memory_events, handoff_events),
        rsi6=rsi6,
    )


def run_v6(
    context: Any,
    *,
    start_index: int,
    terminal_index: int,
    slippage: float = 0.0004,
    include_funding: bool = True,
    retain: bool = False,
) -> Any:
    return _PEHC.run_variant(
        context,
        fixed_v6_config(),
        start_index=start_index,
        terminal_index=terminal_index,
        slippage=slippage,
        include_funding=include_funding,
        retain=retain,
        short_rsi_enabled=True,
    )
