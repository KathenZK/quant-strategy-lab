"""Causal transition-repair overlay on frozen HYPE MA7 ABT V6.

The overlay changes only natural flat-entry observation/cooldown semantics.  The
frozen OAPP exits, PEHC_294 shadow handoff, forced reversal, sizing, costs and
funding ledger remain sourced from the exact V6 implementation.
"""

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
COOLDOWN_MODES = ("GLOBAL_BASE", "NONE", "DIRECTIONAL")
MATURITY_MODES = ("NONE", "BUFFER", "SLOPE", "BOTH")


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_PEHC = _load_module(PEHC_PATH, "hype_v6_transition_repair_pehc")
_BASE = _PEHC._BASE


@dataclass(frozen=True, slots=True)
class TransitionRepairConfig:
    arm_id: str
    cooldown_mode: str = "GLOBAL_BASE"
    same_side_cooldown_days: int = 2
    episode_enabled: bool = False
    episode_max_age_days: int = 5
    maturity_mode: str = "NONE"
    recross_cancels: bool = True
    anti_chase_cap_atr: float = math.inf
    rsi_reobserve_enabled: bool = False
    rsi_reset_threshold: float = 30.0
    rsi_reobserve_max_age_days: int = 5

    def __post_init__(self) -> None:
        if not self.arm_id:
            raise ValueError("arm_id is required")
        if self.cooldown_mode not in COOLDOWN_MODES:
            raise ValueError("unknown cooldown mode")
        if self.same_side_cooldown_days not in (1, 2):
            raise ValueError("same-side cooldown must be 1d or 2d")
        if self.episode_max_age_days not in (3, 5):
            raise ValueError("episode max age must be 3d or 5d")
        if self.maturity_mode not in MATURITY_MODES:
            raise ValueError("unknown maturity mode")
        if self.anti_chase_cap_atr not in (0.75, 1.0, 1.5, math.inf):
            raise ValueError("anti-chase cap outside frozen grid")
        if self.rsi_reset_threshold not in (20.0, 30.0):
            raise ValueError("RSI reset outside frozen grid")
        if self.rsi_reobserve_max_age_days != 5:
            raise ValueError("RSI reobserve max age is frozen at 5d")

    def canonical(self) -> dict[str, Any]:
        row = asdict(self)
        if math.isinf(self.anti_chase_cap_atr):
            row["anti_chase_cap_atr"] = "INF"
        return row


def config_sha256(config: TransitionRepairConfig) -> str:
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


class TransitionEntrySignal:
    """Observe native entries, finite raw-cross episodes and RSI re-entry."""

    def __init__(
        self,
        native_signal: Callable[[Any, Any, Any, int], bool],
        long_config: Any,
        short_config: Any,
        config: TransitionRepairConfig,
        rsi6: np.ndarray,
    ) -> None:
        self.native_signal = native_signal
        self.long_config = long_config
        self.short_config = short_config
        self.config = config
        self.rsi6 = rsi6
        self.events: list[dict[str, Any]] = []
        self.active_side = 0
        self.armed_at: int | None = None
        self.cross_buffer_pass = False
        self.cross_slope_pass = False
        self.rsi_watch_active = False
        self.rsi_watch_exit_index: int | None = None
        self.rsi_reset_seen = False
        self.rsi_reset_index: int | None = None
        self.cached_index: int | None = None
        self.cached_decisions = {1: False, -1: False}
        self.cached_sources = {1: None, -1: None}

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

    def _clear_episode(self) -> None:
        self.active_side = 0
        self.armed_at = None
        self.cross_buffer_pass = False
        self.cross_slope_pass = False

    def _clear_rsi_watch(self) -> None:
        self.rsi_watch_active = False
        self.rsi_watch_exit_index = None
        self.rsi_reset_seen = False
        self.rsi_reset_index = None

    def notify_exit(self, side: int, index: int, reason: str) -> None:
        if (
            side < 0
            and reason == "short_rsi_take_profit"
            and self.config.rsi_reobserve_enabled
        ):
            self.rsi_watch_active = True
            self.rsi_watch_exit_index = int(index)
            self.rsi_reset_seen = False
            self.rsi_reset_index = None
            self._record("rsi_reobserve_arm", index, -1, exit_reason=reason)
        elif side < 0:
            self._clear_rsi_watch()

    def notify_entry(self, side: int, index: int, source: str) -> None:
        if self.active_side:
            self._record(
                "episode_cancel_external_entry",
                index,
                self.active_side,
                entry_side=self._side_name(side),
                source=source,
            )
        self._clear_episode()
        if self.rsi_watch_active:
            self._record(
                "rsi_reobserve_cancel_external_entry",
                index,
                -1,
                entry_side=self._side_name(side),
                source=source,
            )
        self._clear_rsi_watch()

    def _criteria(
        self, side: int, book: Any, features: Any, index: int
    ) -> dict[str, Any]:
        config = self.long_config if side > 0 else self.short_config
        if config is None or index < int(config.slope_lookback):
            return {"finite": False}
        close = float(book.close[index])
        ma7 = float(features.ma7[index])
        atr7 = float(features.atr7[index])
        prior_ma7 = float(features.ma7[index - int(config.slope_lookback)])
        finite = self._finite(close, ma7, atr7, prior_ma7) and atr7 > 0.0
        if not finite:
            return {"finite": False}
        distance_atr = side * (close - ma7) / atr7
        slope_atr = side * (ma7 - prior_ma7) / atr7
        lower_pass = distance_atr > float(config.entry_buffer_atr)
        cap_pass = distance_atr < self.config.anti_chase_cap_atr
        return {
            "finite": True,
            "distance_atr": distance_atr,
            "slope_atr": slope_atr,
            "buffer_pass": bool(lower_pass),
            "cap_pass": bool(cap_pass),
            "slope_pass": bool(slope_atr > float(config.slope_min_atr)),
        }

    def _native_decisions(self, book: Any, features: Any, index: int) -> dict[int, bool]:
        return {
            1: bool(self.native_signal(self.long_config, book, features, index)),
            -1: bool(self.native_signal(self.short_config, book, features, index)),
        }

    def _raw_cross(self, book: Any, features: Any, index: int) -> int:
        if index < 1:
            return 0
        values = (
            float(book.close[index - 1]),
            float(features.ma7[index - 1]),
            float(book.close[index]),
            float(features.ma7[index]),
        )
        if not self._finite(*values):
            return 0
        prior_close, prior_ma7, close, ma7 = values
        if prior_close <= prior_ma7 and close > ma7:
            return 1
        if prior_close >= prior_ma7 and close < ma7:
            return -1
        return 0

    def _maturity_allowed(self, criterion: str) -> bool:
        mode = self.config.maturity_mode
        return mode == "BOTH" or mode == criterion

    def _update_episode(
        self, book: Any, features: Any, index: int
    ) -> dict[int, bool]:
        decisions = {1: False, -1: False}
        if not self.config.episode_enabled:
            return decisions
        cross_side = self._raw_cross(book, features, index)
        if cross_side:
            if (
                self.config.recross_cancels
                and self.active_side
                and self.active_side != cross_side
            ):
                self._record(
                    "episode_cancel_recross",
                    index,
                    self.active_side,
                    armed_at_index=self.armed_at,
                )
                self._clear_episode()
            criteria = self._criteria(cross_side, book, features, index)
            if not criteria.get("finite"):
                self._clear_episode()
                return decisions
            buffer_can_wait = self._maturity_allowed("BUFFER")
            slope_can_wait = self._maturity_allowed("SLOPE")
            arm_allowed = (
                (bool(criteria["buffer_pass"]) or buffer_can_wait)
                and (bool(criteria["slope_pass"]) or slope_can_wait)
                and bool(criteria["cap_pass"])
            )
            if arm_allowed:
                self.active_side = cross_side
                self.armed_at = int(index)
                self.cross_buffer_pass = bool(criteria["buffer_pass"])
                self.cross_slope_pass = bool(criteria["slope_pass"])
                self._record(
                    "episode_arm_raw_cross",
                    index,
                    cross_side,
                    cross_buffer_pass=self.cross_buffer_pass,
                    cross_slope_pass=self.cross_slope_pass,
                    distance_atr=criteria["distance_atr"],
                    slope_atr=criteria["slope_atr"],
                )
            else:
                self._record(
                    "episode_reject_raw_cross",
                    index,
                    cross_side,
                    buffer_pass=bool(criteria["buffer_pass"]),
                    slope_pass=bool(criteria["slope_pass"]),
                    cap_pass=bool(criteria["cap_pass"]),
                )
                self._clear_episode()
        if not self.active_side or self.armed_at is None:
            return decisions
        side = self.active_side
        age = int(index - self.armed_at)
        if age > self.config.episode_max_age_days:
            self._record(
                "episode_expire",
                index,
                side,
                armed_at_index=self.armed_at,
                age=age,
            )
            self._clear_episode()
            return decisions
        close = float(book.close[index])
        ma7 = float(features.ma7[index])
        if not self._finite(close, ma7):
            self._record("episode_cancel_nonfinite", index, side)
            self._clear_episode()
            return decisions
        if self.config.recross_cancels and side * (close - ma7) <= 0.0:
            self._record(
                "episode_cancel_recross",
                index,
                side,
                armed_at_index=self.armed_at,
                age=age,
            )
            self._clear_episode()
            return decisions
        if age < 1:
            return decisions
        criteria = self._criteria(side, book, features, index)
        if not criteria.get("finite"):
            return decisions
        buffer_pass = bool(criteria["buffer_pass"])
        slope_pass = bool(criteria["slope_pass"])
        if not self._maturity_allowed("BUFFER"):
            buffer_pass = self.cross_buffer_pass and buffer_pass
        if not self._maturity_allowed("SLOPE"):
            slope_pass = self.cross_slope_pass and slope_pass
        if buffer_pass and slope_pass and bool(criteria["cap_pass"]):
            decisions[side] = True
            self._record(
                "episode_confirm",
                index,
                side,
                armed_at_index=self.armed_at,
                age=age,
                distance_atr=criteria["distance_atr"],
                slope_atr=criteria["slope_atr"],
            )
            self._clear_episode()
        return decisions

    def _update_rsi_reobserve(
        self, book: Any, features: Any, index: int
    ) -> dict[int, bool]:
        decisions = {1: False, -1: False}
        if not self.rsi_watch_active or self.rsi_watch_exit_index is None:
            return decisions
        age = int(index - self.rsi_watch_exit_index)
        if age > self.config.rsi_reobserve_max_age_days:
            self._record("rsi_reobserve_expire", index, -1, age=age)
            self._clear_rsi_watch()
            return decisions
        close = float(book.close[index])
        ma7 = float(features.ma7[index])
        rsi = float(self.rsi6[index])
        if not self._finite(close, ma7, rsi) or close >= ma7:
            self._record("rsi_reobserve_cancel_ma", index, -1, age=age)
            self._clear_rsi_watch()
            return decisions
        if not self.rsi_reset_seen and rsi >= self.config.rsi_reset_threshold:
            self.rsi_reset_seen = True
            self.rsi_reset_index = int(index)
            self._record(
                "rsi_reobserve_reset",
                index,
                -1,
                age=age,
                rsi6=rsi,
            )
            return decisions
        if not self.rsi_reset_seen or self.rsi_reset_index is None:
            return decisions
        if index <= self.rsi_reset_index or index < 1:
            return decisions
        prior_close = float(book.close[index - 1])
        criteria = self._criteria(-1, book, features, index)
        if (
            self._finite(prior_close)
            and close < prior_close
            and criteria.get("finite")
            and bool(criteria["buffer_pass"])
            and bool(criteria["slope_pass"])
            and bool(criteria["cap_pass"])
        ):
            decisions[-1] = True
            self._record(
                "rsi_reobserve_confirm",
                index,
                -1,
                age=age,
                reset_index=self.rsi_reset_index,
                rsi6=rsi,
                distance_atr=criteria["distance_atr"],
                slope_atr=criteria["slope_atr"],
            )
            self._clear_rsi_watch()
        return decisions

    def _evaluate(self, book: Any, features: Any, index: int) -> None:
        self.cached_index = int(index)
        self.cached_decisions = {1: False, -1: False}
        self.cached_sources = {1: None, -1: None}
        if index < 1:
            return
        native = self._native_decisions(book, features, index)
        if native[1] or native[-1]:
            side = 1 if native[1] else -1
            self._record("native_entry_signal", index, side)
            self.cached_decisions = native
            self.cached_sources[side] = "native"
            self._clear_episode()
            self._clear_rsi_watch()
            return
        episode = self._update_episode(book, features, index)
        if episode[1] or episode[-1]:
            self.cached_decisions = episode
            self.cached_sources[1 if episode[1] else -1] = "episode"
            self._clear_rsi_watch()
            return
        self.cached_decisions = self._update_rsi_reobserve(book, features, index)
        if self.cached_decisions[-1]:
            self.cached_sources[-1] = "rsi_reobserve"

    def __call__(self, config: Any, book: Any, features: Any, index: int) -> bool:
        if self.cached_index != index:
            self._evaluate(book, features, index)
        return bool(self.cached_decisions[int(config.side)])

    def decision_source(self, side: int) -> str | None:
        return self.cached_sources[int(side)]


class RepairRecorder:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def __call__(self, event: dict[str, Any]) -> None:
        self.events.append(dict(event))


@dataclass(slots=True)
class TransitionRepairExecutionResult:
    config: TransitionRepairConfig
    raw: Any
    source_sha256: str
    signal_events: list[dict[str, Any]]
    cooldown_events: list[dict[str, Any]]
    native_entry_events: list[dict[str, Any]]
    handoff_events: list[dict[str, Any]]
    activation_counts: dict[str, int]
    rsi6: np.ndarray


def _replace_once(source: str, old: str, new: str, label: str) -> str:
    return _BASE._replace_once(source, old, new, label)


def _apply_repair_state(source: str) -> str:
    return _replace_once(
        source,
        "    cooldown_left = 0\n    wtl_long_run = 0\n",
        """\
    cooldown_left = 0
    repair_global_cooldown_until = -1
    repair_side_cooldown_until = {1: -1, -1: -1}

    def repair_set_cooldown(exit_side, exit_index, native_days, reason):
        nonlocal cooldown_left, repair_global_cooldown_until
        mode = repair_cooldown_mode
        if mode == "NONE":
            days = 0
        elif mode == "DIRECTIONAL":
            days = repair_same_side_cooldown_days
        else:
            days = int(native_days)
        cooldown_left = int(days)
        if mode == "DIRECTIONAL":
            repair_side_cooldown_until[int(exit_side)] = int(exit_index + days)
        else:
            repair_global_cooldown_until = int(exit_index + days)
        repair_record({
            "event": "cooldown_set",
            "index": int(exit_index),
            "side": "long" if int(exit_side) > 0 else "short",
            "mode": mode,
            "days": int(days),
            "eligible_after_index": int(exit_index + days),
            "reason": str(reason),
        })

    def repair_entry_allowed(entry_side, entry_index):
        if repair_cooldown_mode == "NONE":
            return True
        if repair_cooldown_mode == "DIRECTIONAL":
            return int(entry_index) > repair_side_cooldown_until[int(entry_side)]
        return int(entry_index) > repair_global_cooldown_until

    wtl_long_run = 0
""",
        "repair state",
    )


def _apply_repair_exits(source: str) -> str:
    source = _replace_once(
        source,
        """\
            if reason:
                close(ts, current_open, reason, index)
                cooldown_left = config.cooldown_days
                exited_at_open = True
                action = reason
""",
        """\
            if reason:
                exit_side = int(config.side)
                repair_entry_signal.notify_exit(exit_side, index, reason)
                close(ts, current_open, reason, index)
                repair_set_cooldown(
                    exit_side,
                    index,
                    config.cooldown_days,
                    reason,
                )
                exited_at_open = True
                action = reason
""",
        "repair daily exit",
    )
    source = _replace_once(
        source,
        """\
            else:
                cooldown_left = (
                    long_config.cooldown_days
                    if long_config is not None
                    else 0
                )
                action = "pending_reversal_filter_rejected"
""",
        """\
            else:
                repair_set_cooldown(
                    1,
                    index,
                    long_config.cooldown_days if long_config is not None else 0,
                    "pending_reversal_filter_rejected",
                )
                action = "pending_reversal_filter_rejected"
""",
        "repair pending rejection",
    )
    source = _replace_once(
        source,
        """\
                                cooldown_left = short_config.cooldown_days
                                mark_price = short_fill
""",
        """\
                                repair_entry_signal.notify_exit(
                                    -1,
                                    index,
                                    "protective_stop",
                                )
                                repair_set_cooldown(
                                    -1,
                                    index,
                                    short_config.cooldown_days,
                                    "protective_stop",
                                )
                                mark_price = short_fill
""",
        "repair same-day reversal short stop",
    )
    source = _replace_once(
        source,
        """\
                        else:
                            cooldown_left = config.cooldown_days
                            mark_price = fill
                            action = "protective_stop_reversal_filter_rejected"
""",
        """\
                        else:
                            repair_set_cooldown(
                                1,
                                index,
                                config.cooldown_days,
                                "protective_stop_reversal_filter_rejected",
                            )
                            mark_price = fill
                            action = "protective_stop_reversal_filter_rejected"
""",
        "repair reversal rejection",
    )
    source = _replace_once(
        source,
        """\
                else:
                    cooldown_left = config.cooldown_days
                    mark_price = fill
                    action = "protective_stop"
""",
        """\
                else:
                    repair_entry_signal.notify_exit(
                        position_side,
                        index,
                        "protective_stop",
                    )
                    repair_set_cooldown(
                        position_side,
                        index,
                        config.cooldown_days,
                        "protective_stop",
                    )
                    mark_price = fill
                    action = "protective_stop"
""",
        "repair simple protective stop",
    )
    return source


def _apply_repair_entry(source: str) -> str:
    original = """\
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
    replacement = """\
        if index < terminal_index and side == 0:
            selected: Config | None = None
            signal_index = max(0, decision_index)
            long_signal = bool(
                long_config is not None
                and close_entry_signal(
                    long_config,
                    book,
                    features,
                    signal_index,
                )
            )
            short_signal = bool(
                short_config is not None
                and close_entry_signal(
                    short_config,
                    book,
                    features,
                    signal_index,
                )
            )
            long_allowed = bool(
                long_signal and repair_entry_allowed(1, index)
            )
            short_allowed = bool(
                short_signal
                and (
                    repair_entry_allowed(-1, index)
                    or repair_entry_signal.decision_source(-1)
                    == "rsi_reobserve"
                )
            )
            if long_signal and not long_allowed:
                repair_record({
                    "event": "entry_blocked_cooldown",
                    "index": int(index),
                    "signal_index": int(signal_index),
                    "side": "long",
                    "mode": repair_cooldown_mode,
                })
            if short_signal and not short_allowed:
                repair_record({
                    "event": "entry_blocked_cooldown",
                    "index": int(index),
                    "signal_index": int(signal_index),
                    "side": "short",
                    "mode": repair_cooldown_mode,
                })
            if long_allowed:
                selected = long_config
            elif short_allowed:
                selected = short_config
            elif (
                short_config is not None
                and repair_entry_allowed(-1, index)
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
                repair_entry_signal.notify_entry(
                    int(selected.side),
                    index,
                    "natural_entry",
                )
                action = "enter_long" if selected.side > 0 else "enter_short"
"""
    return _replace_once(source, original, replacement, "repair natural entry")


def build_variant_function(
    context: Any,
    config: TransitionRepairConfig,
    *,
    entry_signal: TransitionEntrySignal,
    native_entry_signal: Any,
    leverage_policy: Any,
    rsi6: np.ndarray,
    handoff_recorder: Any,
    repair_recorder: RepairRecorder,
) -> tuple[Callable[..., Any], str]:
    pehc_config = fixed_v6_config()
    oapp_config = _PEHC.fixed_oapp_config(short_rsi_enabled=True)
    source = _BASE._capture_exact_source(context)
    digest = hashlib.sha256(config.arm_id.encode()).hexdigest()[:12]
    function_name = f"transition_repair_{digest}_backtest"
    source = _replace_once(
        source,
        "def v3_ma_only_backtest(",
        f"def {function_name}(",
        "repair function name",
    )
    source = _BASE._apply_state(source)
    source = _BASE._apply_exits(source)
    source = _PEHC._apply_pehc_state(source)
    source = _PEHC._apply_pehc_arm(source)
    source = _PEHC._apply_pehc_daily(source)
    source = _PEHC._apply_pehc_intraday(source)
    source = _apply_repair_state(source)
    source = _apply_repair_exits(source)
    source = _apply_repair_entry(source)
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
            "pehc_blocked_origin_indices": frozenset(
                pehc_config.blocked_origin_indices
            ),
            "pehc_allowed_origin_indices": frozenset(
                pehc_config.allowed_origin_indices
            ),
            "pehc_expiry_days": pehc_config.expiry_days,
            "pehc_slope_threshold": pehc_config.slope_threshold,
            "pehc_chase_cap_atr": pehc_config.chase_cap_atr,
            "pehc_execution": pehc_config.execution,
            "pehc_handoff_eligibility": _PEHC.handoff_eligibility,
            "pehc_record": handoff_recorder,
            "repair_entry_signal": entry_signal,
            "repair_native_entry_signal": native_entry_signal,
            "repair_cooldown_mode": config.cooldown_mode,
            "repair_same_side_cooldown_days": config.same_side_cooldown_days,
            "repair_record": repair_recorder,
        }
    )
    compiled = compile(source, f"<transition-repair-{config.arm_id}>", "exec")
    exec(compiled, namespace)
    return namespace[function_name], hashlib.sha256(source.encode()).hexdigest()


def _counts(
    raw: Any,
    signal_events: list[dict[str, Any]],
    cooldown_events: list[dict[str, Any]],
    handoff_events: list[dict[str, Any]],
) -> dict[str, int]:
    exits = [str(row.get("exit_reason", "")) for row in raw.trades]
    counts = {
        "long_trail_exit": sum(reason.startswith("long_mfe_") for reason in exits),
        "short_rsi_exit": sum(reason == "short_rsi_take_profit" for reason in exits),
        "protective_stop": sum(reason == "protective_stop" for reason in exits),
        "handoff_accept": sum(
            row.get("event") == "handoff_accept" for row in handoff_events
        ),
        "cooldown_set": sum(
            row.get("event") == "cooldown_set" for row in cooldown_events
        ),
        "entry_blocked_cooldown": sum(
            row.get("event") == "entry_blocked_cooldown"
            for row in cooldown_events
        ),
    }
    for event_name in (
        "native_entry_signal",
        "episode_arm_raw_cross",
        "episode_reject_raw_cross",
        "episode_confirm",
        "episode_cancel_recross",
        "episode_expire",
        "rsi_reobserve_arm",
        "rsi_reobserve_reset",
        "rsi_reobserve_confirm",
        "rsi_reobserve_expire",
        "rsi_reobserve_cancel_ma",
    ):
        counts[event_name] = sum(
            row.get("event") == event_name for row in signal_events
        )
    counts["episode_long_confirm"] = sum(
        row.get("event") == "episode_confirm" and row.get("side") == "long"
        for row in signal_events
    )
    counts["episode_short_confirm"] = sum(
        row.get("event") == "episode_confirm" and row.get("side") == "short"
        for row in signal_events
    )
    return counts


def run_variant(
    context: Any,
    config: TransitionRepairConfig,
    *,
    start_index: int,
    terminal_index: int,
    slippage: float = 0.0004,
    signal_lag: int = 0,
    include_funding: bool = True,
    retain: bool = False,
) -> TransitionRepairExecutionResult:
    if not (0 <= start_index < terminal_index <= context.book.count):
        raise ValueError("invalid transition-repair window")
    oapp_config = _PEHC.fixed_oapp_config(short_rsi_enabled=True)
    rsi6 = _BASE.wilder_rsi6(context.book.close)
    native_entry_signal = _BASE.EntryQualitySignal(
        context.engine, oapp_config.entry
    )
    entry_signal = TransitionEntrySignal(
        native_entry_signal,
        context.long_config,
        context.short_config,
        config,
        rsi6,
    )
    leverage_policy = _BASE.LeveragePolicy(context, None)
    handoff_recorder = _PEHC.HandoffRecorder()
    repair_recorder = RepairRecorder()
    function, source_hash = build_variant_function(
        context,
        config,
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
    cooldown_events = list(repair_recorder.events)
    handoff_events = list(handoff_recorder.events)
    return TransitionRepairExecutionResult(
        config=config,
        raw=raw,
        source_sha256=source_hash,
        signal_events=signal_events,
        cooldown_events=cooldown_events,
        native_entry_events=list(native_entry_signal.events),
        handoff_events=handoff_events,
        activation_counts=_counts(
            raw, signal_events, cooldown_events, handoff_events
        ),
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
