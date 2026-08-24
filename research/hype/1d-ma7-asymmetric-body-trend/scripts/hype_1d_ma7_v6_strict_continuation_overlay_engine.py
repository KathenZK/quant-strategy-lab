"""Strict non-ML continuation overlay on frozen HYPE MA7 ABT V6."""

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


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_PEHC = _load_module(PEHC_PATH, "hype_strict_cto_pehc")
_BASE = _PEHC._BASE


@dataclass(frozen=True, slots=True)
class StrictOverlayConfig:
    arm_id: str = "STRICT_CTO"
    max_age_days: int = 5
    persistence_days: int = 3
    slope_lookback: int = 2
    slope_min_atr: float = 0.04
    min_distance_atr: float = 0.25
    max_distance_atr: float = 1.00
    er_lookback: int = 5
    er_min: float = 0.35
    adverse_budget_atr: float = 0.75

    def canonical(self) -> dict[str, Any]:
        return asdict(self)


def config_sha256(config: StrictOverlayConfig) -> str:
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


class StrictContinuationSignal:
    def __init__(
        self,
        native_signal: Callable[[Any, Any, Any, int], bool],
        long_config: Any,
        short_config: Any,
        config: StrictOverlayConfig,
    ) -> None:
        self.native_signal = native_signal
        self.long_config = long_config
        self.short_config = short_config
        self.config = config
        self.events: list[dict[str, Any]] = []
        self.active_side = 0
        self.armed_at: int | None = None
        self.armed_close = math.nan
        self.armed_atr = math.nan
        self.same_side_run = 0
        self.last_index: int | None = None
        self.cached_index: int | None = None
        self.cached_decisions = {1: False, -1: False}

    @staticmethod
    def _side_name(side: int) -> str:
        return "long" if side > 0 else "short"

    @staticmethod
    def _finite(*values: float) -> bool:
        return all(math.isfinite(float(value)) for value in values)

    def _record(self, event: str, index: int, side: int = 0, **extra: Any) -> None:
        row: dict[str, Any] = {"event": event, "signal_index": int(index), **extra}
        if side:
            row["side"] = self._side_name(side)
        self.events.append(row)

    def _clear(self) -> None:
        self.active_side = 0
        self.armed_at = None
        self.armed_close = math.nan
        self.armed_atr = math.nan
        self.same_side_run = 0

    def _natural_decisions(self, book: Any, features: Any, index: int) -> dict[int, bool]:
        return {
            1: bool(self.native_signal(self.long_config, book, features, index)),
            -1: bool(self.native_signal(self.short_config, book, features, index)),
        }

    def _snapshot(self, book: Any, features: Any, index: int) -> dict[str, float]:
        return {
            "close": float(book.close[index]),
            "ma7": float(features.ma7[index]),
            "atr7": float(features.atr7[index]),
            "prior_close": float(book.close[index - 1]),
            "prior_ma7": float(features.ma7[index - 1]),
        }

    def _efficiency_ratio(self, book: Any, index: int) -> float:
        lookback = self.config.er_lookback
        if index < lookback:
            return math.nan
        closes = [float(book.close[offset]) for offset in range(index - lookback, index + 1)]
        if not self._finite(*closes):
            return math.nan
        denominator = sum(abs(closes[offset] - closes[offset - 1]) for offset in range(1, len(closes)))
        if denominator <= 0.0:
            return 0.0
        return abs(closes[-1] - closes[0]) / denominator

    def _adverse_atr(self, book: Any, index: int, side: int) -> float:
        if self.armed_at is None or not self._finite(self.armed_close, self.armed_atr) or self.armed_atr <= 0.0:
            return math.nan
        worst = 0.0
        for offset in range(self.armed_at, index + 1):
            close = float(book.close[offset])
            if not math.isfinite(close):
                return math.nan
            move = side * (close - self.armed_close) / self.armed_atr
            worst = min(worst, move)
        return worst

    def _evaluate(self, book: Any, features: Any, index: int) -> None:
        self.cached_index = index
        self.cached_decisions = {1: False, -1: False}
        if index < 1:
            self.last_index = index
            return
        if self.last_index is not None and index > self.last_index + 1 and self.active_side:
            self._record(
                "cancel_call_gap",
                index,
                self.active_side,
                armed_at_index=self.armed_at,
                gap_days=index - self.last_index,
            )
            self._clear()

        natural = self._natural_decisions(book, features, index)
        if natural[1] or natural[-1]:
            selected = 1 if natural[1] else -1
            if self.active_side:
                self._record(
                    "cancel_native_precedence",
                    index,
                    self.active_side,
                    armed_at_index=self.armed_at,
                    native_side=self._side_name(selected),
                )
            self._clear()
            self.cached_decisions = natural
            self.last_index = index
            return

        snap = self._snapshot(book, features, index)
        valid = self._finite(*snap.values()) and snap["atr7"] > 0.0
        if not valid:
            if self.active_side:
                self._record("cancel_nonfinite", index, self.active_side, armed_at_index=self.armed_at)
            self._clear()
            self.last_index = index
            return

        long_cross = snap["prior_close"] <= snap["prior_ma7"] and snap["close"] > snap["ma7"]
        short_cross = snap["prior_close"] >= snap["prior_ma7"] and snap["close"] < snap["ma7"]
        cross_side = 1 if long_cross else (-1 if short_cross else 0)
        if cross_side:
            if self.active_side and self.active_side != cross_side:
                self._record("cancel_opposite_cross", index, self.active_side, armed_at_index=self.armed_at)
            self.active_side = cross_side
            self.armed_at = index
            self.armed_close = snap["close"]
            self.armed_atr = snap["atr7"]
            self.same_side_run = 1
            self._record("arm_raw_cross", index, cross_side, close=snap["close"], ma7=snap["ma7"], atr7=snap["atr7"])
        elif self.active_side:
            signed_distance = self.active_side * (snap["close"] - snap["ma7"])
            if signed_distance <= 0.0:
                self._record("cancel_recross_ma7", index, self.active_side, armed_at_index=self.armed_at)
                self._clear()
            else:
                self.same_side_run += 1

        if not self.active_side or self.armed_at is None:
            self.last_index = index
            return

        side = self.active_side
        age = index - self.armed_at
        if age > self.config.max_age_days:
            self._record("expire_max_age", index, side, armed_at_index=self.armed_at, age=age)
            self._clear()
            self.last_index = index
            return

        prior = index - self.config.slope_lookback
        if prior < 0:
            self.last_index = index
            return
        prior_ma7 = float(features.ma7[prior])
        if not self._finite(prior_ma7):
            self.last_index = index
            return

        distance_atr = side * (snap["close"] - snap["ma7"]) / snap["atr7"]
        slope_atr = side * (snap["ma7"] - prior_ma7) / snap["atr7"]
        er5 = self._efficiency_ratio(book, index)
        adverse_atr = self._adverse_atr(book, index, side)
        checks = {
            "age_ge_2": age >= 2,
            "same_side_run_ge_3": self.same_side_run >= self.config.persistence_days,
            "slope_pass": slope_atr >= self.config.slope_min_atr,
            "distance_min_pass": distance_atr >= self.config.min_distance_atr,
            "distance_max_pass": distance_atr <= self.config.max_distance_atr,
            "er_pass": math.isfinite(er5) and er5 >= self.config.er_min,
            "adverse_budget_pass": math.isfinite(adverse_atr) and adverse_atr >= -self.config.adverse_budget_atr,
        }
        if all(checks.values()):
            self.cached_decisions[side] = True
            self._record(
                "confirm_strict_continuation",
                index,
                side,
                armed_at_index=self.armed_at,
                age=age,
                same_side_run=self.same_side_run,
                distance_atr=distance_atr,
                slope_atr=slope_atr,
                er5=er5,
                adverse_atr=adverse_atr,
                checks=checks,
            )
            self._clear()
        else:
            self._record(
                "reject_strict_gate",
                index,
                side,
                armed_at_index=self.armed_at,
                age=age,
                same_side_run=self.same_side_run,
                distance_atr=distance_atr,
                slope_atr=slope_atr,
                er5=er5,
                adverse_atr=adverse_atr,
                checks=checks,
            )
        self.last_index = index

    def __call__(self, config: Any, book: Any, features: Any, index: int) -> bool:
        if self.cached_index != index:
            self._evaluate(book, features, index)
        return bool(self.cached_decisions[int(config.side)])


@dataclass(slots=True)
class StrictOverlayResult:
    config: StrictOverlayConfig
    raw: Any
    source_sha256: str
    signal_events: list[dict[str, Any]]
    native_entry_events: list[dict[str, Any]]
    handoff_events: list[dict[str, Any]]
    activation_counts: dict[str, int]
    rsi6: np.ndarray


def _counts(raw: Any, signal_events: list[dict[str, Any]], handoff_events: list[dict[str, Any]]) -> dict[str, int]:
    exits = [str(row.get("exit_reason", "")) for row in raw.trades]
    counts = {
        "long_trail_exit": sum(reason.startswith("long_mfe_") for reason in exits),
        "short_rsi_exit": sum(reason == "short_rsi_take_profit" for reason in exits),
        "protective_stop": sum(reason == "protective_stop" for reason in exits),
        "handoff_accept": sum(row.get("event") == "handoff_accept" for row in handoff_events),
        "shadow_start": sum(row.get("event") == "shadow_start" for row in handoff_events),
    }
    for event in (
        "arm_raw_cross",
        "reject_strict_gate",
        "confirm_strict_continuation",
        "cancel_recross_ma7",
        "cancel_opposite_cross",
        "cancel_native_precedence",
        "expire_max_age",
        "cancel_nonfinite",
    ):
        counts[event] = sum(row.get("event") == event for row in signal_events)
    counts["strict_long_confirm"] = sum(
        row.get("event") == "confirm_strict_continuation" and row.get("side") == "long"
        for row in signal_events
    )
    counts["strict_short_confirm"] = sum(
        row.get("event") == "confirm_strict_continuation" and row.get("side") == "short"
        for row in signal_events
    )
    return counts


def run_variant(
    context: Any,
    config: StrictOverlayConfig,
    *,
    start_index: int,
    terminal_index: int,
    slippage: float = 0.0004,
    signal_lag: int = 0,
    include_funding: bool = True,
    retain: bool = False,
) -> StrictOverlayResult:
    if not (0 <= start_index < terminal_index <= context.book.count):
        raise ValueError("invalid strict overlay window")
    pehc_config = fixed_v6_config()
    oapp_config = _PEHC.fixed_oapp_config(short_rsi_enabled=True)
    rsi6 = _BASE.wilder_rsi6(context.book.close)
    native_entry_signal = _BASE.EntryQualitySignal(context.engine, oapp_config.entry)
    entry_signal = StrictContinuationSignal(
        native_entry_signal,
        context.long_config,
        context.short_config,
        config,
    )
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
        signal_lag=signal_lag,
        include_funding=include_funding,
        retain=retain,
    )
    if bool(raw.metrics.get("bankrupt_intraday")):
        raise RuntimeError(f"{config.arm_id} became bankrupt")
    signal_events = list(entry_signal.events)
    handoff_events = list(recorder.events)
    return StrictOverlayResult(
        config=config,
        raw=raw,
        source_sha256=source_hash,
        signal_events=signal_events,
        native_entry_events=list(native_entry_signal.events),
        handoff_events=handoff_events,
        activation_counts=_counts(raw, signal_events, handoff_events),
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
