"""Causal delayed-cross episode overlay on frozen HYPE MA7 ABT V6."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import importlib.util
from itertools import product
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

PERSISTENCE_DAYS = (2, 3, 4, 5)
SLOPE_LOOKBACKS = (2, 3, 5)
SLOPE_MIN_ATR = (0.0, 0.01, 0.02, 0.04)
MAX_DISTANCE_ATR = (0.75, 1.0, 1.5)
MAX_AGE_DAYS = (5, 10, 20, 0)


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_PEHC = _load_module(PEHC_PATH, "hype_dtec_pehc_engine")
_BASE = _PEHC._BASE


@dataclass(frozen=True, slots=True)
class EpisodeParams:
    persistence_days: int
    slope_lookback: int
    slope_min_atr: float
    max_distance_atr: float
    max_age_days: int

    def __post_init__(self) -> None:
        if self.persistence_days not in PERSISTENCE_DAYS:
            raise ValueError("persistence_days outside frozen grid")
        if self.slope_lookback not in SLOPE_LOOKBACKS:
            raise ValueError("slope_lookback outside frozen grid")
        if self.slope_min_atr not in SLOPE_MIN_ATR:
            raise ValueError("slope_min_atr outside frozen grid")
        if self.max_distance_atr not in MAX_DISTANCE_ATR:
            raise ValueError("max_distance_atr outside frozen grid")
        if self.max_age_days not in MAX_AGE_DAYS:
            raise ValueError("max_age_days outside frozen grid")


@dataclass(frozen=True, slots=True)
class DTECConfig:
    arm_id: str
    long: EpisodeParams | None = None
    short: EpisodeParams | None = None

    def __post_init__(self) -> None:
        if not self.arm_id:
            raise ValueError("arm_id is required")

    def canonical(self) -> dict[str, Any]:
        return {
            "arm_id": self.arm_id,
            "long": asdict(self.long) if self.long is not None else None,
            "short": asdict(self.short) if self.short is not None else None,
        }


def config_sha256(config: DTECConfig) -> str:
    payload = json.dumps(
        config.canonical(), sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _param_grid() -> list[EpisodeParams]:
    rows = [
        EpisodeParams(*values)
        for values in product(
            PERSISTENCE_DAYS,
            SLOPE_LOOKBACKS,
            SLOPE_MIN_ATR,
            MAX_DISTANCE_ATR,
            MAX_AGE_DAYS,
        )
    ]
    if len(rows) != 576:
        raise RuntimeError("DTEC parameter grid cardinality drift")
    return rows


def single_side_configs(side: int) -> list[DTECConfig]:
    if side not in (-1, 1):
        raise ValueError("side must be -1 or 1")
    label = "L" if side > 0 else "S"
    rows = []
    for index, params in enumerate(_param_grid(), 1):
        rows.append(
            DTECConfig(
                arm_id=f"DTEC_{label}{index:03d}",
                long=params if side > 0 else None,
                short=params if side < 0 else None,
            )
        )
    return rows


def combine_config(
    long_config: DTECConfig,
    short_config: DTECConfig,
    *,
    arm_id: str,
) -> DTECConfig:
    if long_config.long is None or long_config.short is not None:
        raise ValueError("long parent must be long-only")
    if short_config.short is None or short_config.long is not None:
        raise ValueError("short parent must be short-only")
    return DTECConfig(
        arm_id=arm_id,
        long=long_config.long,
        short=short_config.short,
    )


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


class DelayedEpisodeSignal:
    """Wrap V6's native daily entry signal with one causal cross episode."""

    def __init__(
        self,
        engine: Any,
        native_signal: Callable[[Any, Any, Any, int], bool],
        long_config: Any,
        short_config: Any,
        config: DTECConfig,
    ) -> None:
        self.engine = engine
        self.native_signal = native_signal
        self.long_config = long_config
        self.short_config = short_config
        self.config = config
        self.events: list[dict[str, Any]] = []
        self.active_side = 0
        self.armed_at: int | None = None
        self.same_side_run = 0
        self.last_index: int | None = None
        self.cached_index: int | None = None
        self.cached_decisions = {1: False, -1: False}

    @staticmethod
    def _finite(*values: float) -> bool:
        return all(math.isfinite(float(value)) for value in values)

    def _params(self, side: int) -> EpisodeParams | None:
        return self.config.long if side > 0 else self.config.short

    @staticmethod
    def _side_name(side: int) -> str:
        return "long" if side > 0 else "short"

    def _record(self, event: str, index: int, side: int, **extra: Any) -> None:
        self.events.append(
            {
                "event": event,
                "signal_index": int(index),
                "side": self._side_name(side),
                **extra,
            }
        )

    def _clear(self) -> None:
        self.active_side = 0
        self.armed_at = None
        self.same_side_run = 0

    def _snapshot(self, book: Any, features: Any, index: int) -> dict[str, float]:
        return {
            "close": float(book.close[index]),
            "ma7": float(features.ma7[index]),
            "atr7": float(features.atr7[index]),
            "prior_close": float(book.close[index - 1]),
            "prior_ma7": float(features.ma7[index - 1]),
        }

    def _natural_decisions(self, book: Any, features: Any, index: int) -> dict[int, bool]:
        return {
            1: bool(self.native_signal(self.long_config, book, features, index)),
            -1: bool(self.native_signal(self.short_config, book, features, index)),
        }

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
                self._record(
                    "cancel_nonfinite",
                    index,
                    self.active_side,
                    armed_at_index=self.armed_at,
                )
            self._clear()
            self.last_index = index
            return
        long_cross = snap["prior_close"] <= snap["prior_ma7"] and snap["close"] > snap["ma7"]
        short_cross = snap["prior_close"] >= snap["prior_ma7"] and snap["close"] < snap["ma7"]
        cross_side = 1 if long_cross else (-1 if short_cross else 0)
        if cross_side and self._params(cross_side) is not None:
            if self.active_side and self.active_side != cross_side:
                self._record(
                    "cancel_opposite_cross",
                    index,
                    self.active_side,
                    armed_at_index=self.armed_at,
                )
            self.active_side = cross_side
            self.armed_at = index
            self.same_side_run = 1
            self._record(
                "arm_raw_cross",
                index,
                cross_side,
                close=snap["close"],
                ma7=snap["ma7"],
                atr7=snap["atr7"],
            )
        elif self.active_side:
            signed_distance = self.active_side * (snap["close"] - snap["ma7"])
            if signed_distance <= 0.0:
                self._record(
                    "cancel_recross_ma7",
                    index,
                    self.active_side,
                    armed_at_index=self.armed_at,
                )
                self._clear()
            else:
                self.same_side_run += 1
        if not self.active_side or self.armed_at is None:
            self.last_index = index
            return
        params = self._params(self.active_side)
        if params is None:
            self._clear()
            self.last_index = index
            return
        age = index - self.armed_at
        if params.max_age_days > 0 and age > params.max_age_days:
            self._record(
                "expire_max_age",
                index,
                self.active_side,
                armed_at_index=self.armed_at,
                age=age,
                max_age_days=params.max_age_days,
            )
            self._clear()
            self.last_index = index
            return
        prior = index - params.slope_lookback
        if prior < 0:
            self.last_index = index
            return
        prior_ma7 = float(features.ma7[prior])
        if not self._finite(prior_ma7):
            self.last_index = index
            return
        side = self.active_side
        distance_atr = side * (snap["close"] - snap["ma7"]) / snap["atr7"]
        slope_atr = side * (snap["ma7"] - prior_ma7) / snap["atr7"]
        passed = bool(
            age >= 1
            and self.same_side_run >= params.persistence_days
            and slope_atr >= params.slope_min_atr
            and distance_atr > 0.0
            and distance_atr <= params.max_distance_atr
        )
        if passed:
            self.cached_decisions[side] = True
            self._record(
                "confirm_delayed_episode",
                index,
                side,
                armed_at_index=self.armed_at,
                age=age,
                same_side_run=self.same_side_run,
                distance_atr=distance_atr,
                slope_atr=slope_atr,
                params=asdict(params),
            )
            self._clear()
        self.last_index = index

    def __call__(self, config: Any, book: Any, features: Any, index: int) -> bool:
        if self.cached_index != index:
            self._evaluate(book, features, index)
        return bool(self.cached_decisions[int(config.side)])


@dataclass(slots=True)
class DTECExecutionResult:
    config: DTECConfig
    raw: Any
    source_sha256: str
    episode_events: list[dict[str, Any]]
    native_entry_events: list[dict[str, Any]]
    handoff_events: list[dict[str, Any]]
    activation_counts: dict[str, int]
    rsi6: np.ndarray


def _pehc_counts(raw: Any, events: list[dict[str, Any]]) -> dict[str, int]:
    exits = [str(trade.get("exit_reason", "")) for trade in raw.trades]
    return {
        "shadow_start": sum(row["event"] == "shadow_start" for row in events),
        "shadow_hold": sum(row["event"] == "shadow_hold" for row in events),
        "shadow_expire": sum(row["event"] == "shadow_expire" for row in events),
        "shadow_native_cancel": sum(
            row["event"] == "shadow_cancel_native_exit" for row in events
        ),
        "handoff_opportunity": sum(
            row["event"] == "handoff_opportunity" for row in events
        ),
        "handoff_accept": sum(row["event"] == "handoff_accept" for row in events),
        "handoff_filter_reject": sum(
            row["event"] == "handoff_reject_filter" for row in events
        ),
        "handoff_nonflat_reject": sum(
            row["event"] == "handoff_reject_actual_nonflat" for row in events
        ),
        "long_trail_exit": sum(reason.startswith("long_mfe_") for reason in exits),
        "short_rsi_exit": sum(reason == "short_rsi_take_profit" for reason in exits),
        "protective_stop": sum(reason == "protective_stop" for reason in exits),
    }


def run_variant(
    context: Any,
    config: DTECConfig,
    *,
    start_index: int,
    terminal_index: int,
    slippage: float = 0.0004,
    signal_lag: int = 0,
    include_funding: bool = True,
    retain: bool = False,
) -> DTECExecutionResult:
    if not (0 <= start_index < terminal_index <= context.book.count):
        raise ValueError("invalid DTEC window")
    pehc_config = fixed_v6_config()
    oapp_config = _PEHC.fixed_oapp_config(short_rsi_enabled=True)
    rsi6 = _BASE.wilder_rsi6(context.book.close)
    native_entry_signal = _BASE.EntryQualitySignal(context.engine, oapp_config.entry)
    episode_signal = DelayedEpisodeSignal(
        context.engine,
        native_entry_signal,
        context.long_config,
        context.short_config,
        config,
    )
    leverage_policy = _BASE.LeveragePolicy(context, None)
    recorder = _PEHC.HandoffRecorder()
    function, source_sha = _PEHC.build_variant_function(
        context,
        pehc_config,
        oapp_config=oapp_config,
        entry_signal=episode_signal,
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
    handoff_events = list(recorder.events)
    counts = _pehc_counts(raw, handoff_events)
    for event_name in (
        "arm_raw_cross",
        "confirm_delayed_episode",
        "cancel_recross_ma7",
        "cancel_opposite_cross",
        "cancel_native_precedence",
        "cancel_call_gap",
        "cancel_nonfinite",
        "expire_max_age",
    ):
        counts[f"dtec_{event_name}"] = sum(
            row["event"] == event_name for row in episode_signal.events
        )
    counts["dtec_long_confirm"] = sum(
        row["event"] == "confirm_delayed_episode" and row["side"] == "long"
        for row in episode_signal.events
    )
    counts["dtec_short_confirm"] = sum(
        row["event"] == "confirm_delayed_episode" and row["side"] == "short"
        for row in episode_signal.events
    )
    return DTECExecutionResult(
        config=config,
        raw=raw,
        source_sha256=source_sha,
        episode_events=list(episode_signal.events),
        native_entry_events=list(native_entry_signal.events),
        handoff_events=handoff_events,
        activation_counts=counts,
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
