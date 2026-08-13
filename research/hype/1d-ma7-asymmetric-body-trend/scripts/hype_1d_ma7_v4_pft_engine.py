from __future__ import annotations

import builtins
from dataclasses import asdict, dataclass
import hashlib
import math
from types import ModuleType
from typing import Any, Callable

import numpy as np


ARM_ORDER = (
    "A000_V4",
    "A001_T",
    "A010_F",
    "A011_FT",
    "A100_P",
    "A101_PT",
    "A110_PF",
    "A111_PFT",
)

_ARM_FLAGS = {
    "A000_V4": (False, False, False),
    "A001_T": (False, False, True),
    "A010_F": (False, True, False),
    "A011_FT": (False, True, True),
    "A100_P": (True, False, False),
    "A101_PT": (True, False, True),
    "A110_PF": (True, True, False),
    "A111_PFT": (True, True, True),
}


@dataclass(frozen=True, slots=True)
class PFTConfig:
    arm_id: str
    pending_enabled: bool
    forced_slope_enabled: bool
    rsi_take_profit_enabled: bool
    pending_days: int = 1
    pending_cap_atr: float = 0.75
    rsi_threshold: float = 25.0
    rsi_days: int = 2
    roundtrip_cost_rate: float = 0.0028

    def __post_init__(self) -> None:
        if self.arm_id not in _ARM_FLAGS:
            raise ValueError(f"unknown PFT arm: {self.arm_id}")
        expected = _ARM_FLAGS[self.arm_id]
        if (
            (
                self.pending_enabled,
                self.forced_slope_enabled,
                self.rsi_take_profit_enabled,
            )
            != expected
        ):
            raise ValueError(f"{self.arm_id} flags do not match frozen arm identity")
        if self.pending_days != 1:
            raise ValueError("P pending_days is frozen at 1")
        if not math.isclose(self.pending_cap_atr, 0.75):
            raise ValueError("P pending_cap_atr is frozen at 0.75")
        if self.rsi_days < 1:
            raise ValueError("rsi_days must be >= 1")
        if not 0.0 < self.rsi_threshold < 100.0:
            raise ValueError("rsi_threshold must be within (0, 100)")
        if self.roundtrip_cost_rate <= 0.0:
            raise ValueError("roundtrip_cost_rate must be positive")

    def canonical(self) -> dict[str, Any]:
        return asdict(self)


def arm_config(arm_id: str) -> PFTConfig:
    if arm_id not in _ARM_FLAGS:
        raise ValueError(f"unknown PFT arm: {arm_id}")
    pending, forced, rsi = _ARM_FLAGS[arm_id]
    return PFTConfig(
        arm_id=arm_id,
        pending_enabled=pending,
        forced_slope_enabled=forced,
        rsi_take_profit_enabled=rsi,
    )


def arm_configs() -> list[PFTConfig]:
    return [arm_config(arm_id) for arm_id in ARM_ORDER]


def config_sha256(config: PFTConfig) -> str:
    import json

    payload = json.dumps(
        config.canonical(),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def wilder_rsi6(close: Any, period: int = 6) -> np.ndarray:
    values = np.asarray(close, dtype=float)
    if values.ndim != 1:
        raise ValueError("close must be one-dimensional")
    if period < 1:
        raise ValueError("period must be >= 1")
    result = np.full(len(values), np.nan, dtype=float)
    if len(values) <= period:
        return result
    if not np.isfinite(values).all():
        return result
    delta = np.diff(values)
    gain = np.maximum(delta, 0.0)
    loss = np.maximum(-delta, 0.0)
    avg_gain = float(gain[:period].mean())
    avg_loss = float(loss[:period].mean())

    def value(up: float, down: float) -> float:
        if up == 0.0 and down == 0.0:
            return 50.0
        if down == 0.0:
            return 100.0
        if up == 0.0:
            return 0.0
        rs = up / down
        return 100.0 - 100.0 / (1.0 + rs)

    result[period] = value(avg_gain, avg_loss)
    for index in range(period + 1, len(values)):
        avg_gain = (avg_gain * (period - 1) + float(gain[index - 1])) / period
        avg_loss = (avg_loss * (period - 1) + float(loss[index - 1])) / period
        result[index] = value(avg_gain, avg_loss)
    return result


def forced_reversal_eligible(
    *,
    open_price: float,
    ma7: float,
    prior_ma7: float,
    atr7: float,
    slope_min_atr: float,
) -> bool:
    values = (open_price, ma7, prior_ma7, atr7, slope_min_atr)
    if not all(math.isfinite(value) for value in values) or atr7 <= 0.0:
        return False
    down_slope_atr = (prior_ma7 - ma7) / atr7
    return bool(open_price < ma7 and down_slope_atr >= slope_min_atr)


@dataclass(slots=True)
class RSITracker:
    threshold: float = 25.0
    days: int = 2
    roundtrip_cost_rate: float = 0.0028
    side: int = 0
    entry_price: float | None = None
    streak: int = 0

    def on_fill(self, side: int, entry_price: float) -> None:
        if side not in (-1, 1):
            raise ValueError("fill side must be long or short")
        if not math.isfinite(entry_price) or entry_price <= 0.0:
            raise ValueError("entry_price must be finite and positive")
        self.side = side
        self.entry_price = entry_price
        self.streak = 0

    def on_flat(self) -> None:
        self.side = 0
        self.entry_price = None
        self.streak = 0

    def observe_close(self, rsi6: float, close: float) -> tuple[bool, bool]:
        if self.side != -1 or self.entry_price is None:
            self.streak = 0
            return False, False
        if not math.isfinite(rsi6) or not math.isfinite(close) or close <= 0.0:
            self.streak = 0
            return False, False
        self.streak = self.streak + 1 if rsi6 < self.threshold else 0
        streak_ready = self.streak >= self.days
        gross_profit = (self.entry_price - close) / self.entry_price
        guard_pass = bool(
            gross_profit > self.roundtrip_cost_rate
            and not math.isclose(
                gross_profit,
                self.roundtrip_cost_rate,
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
        )
        return bool(streak_ready and guard_pass), bool(guard_pass)


class QualityShortPendingSignal:
    def __init__(
        self,
        engine: ModuleType,
        *,
        enabled: bool,
        pending_days: int = 1,
        cap_atr: float = 0.75,
    ) -> None:
        self.engine = engine
        self.enabled = enabled
        self.pending_days = pending_days
        self.cap_atr = cap_atr
        self.events: list[dict[str, Any]] = []
        self.armed_at: int | None = None
        self.delayed_confirmations: set[tuple[int, int]] = set()

    def reset(self) -> None:
        self.events = []
        self.armed_at = None
        self.delayed_confirmations = set()

    @staticmethod
    def _finite(*values: float) -> bool:
        return all(np.isfinite(value) for value in values)

    def _snapshot(
        self,
        config: Any,
        book: Any,
        features: Any,
        index: int,
    ) -> dict[str, Any]:
        close = float(book.close[index])
        ma7 = float(features.ma7[index])
        atr7 = float(features.atr7[index])
        prior_close = float(book.close[index - 1])
        prior_ma7 = float(features.ma7[index - 1])
        prior_atr7 = float(features.atr7[index - 1])
        valid = bool(
            self._finite(close, ma7, atr7, prior_close, prior_ma7, prior_atr7)
            and atr7 > 0.0
            and prior_atr7 > 0.0
        )
        buffer_pass = bool(
            valid
            and self.engine._confirmed_side(config, book, features, index)
        )
        prior_touch = bool(
            valid
            and -1 * (prior_close - prior_ma7)
            <= config.pullback_touch_atr * prior_atr7
        )
        trend_pass = bool(
            valid and self.engine._trend_ok(config, book, features, index)
        )
        distance_atr = (
            float((ma7 - close) / atr7)
            if valid
            else math.nan
        )
        return {
            "close": close,
            "ma7": ma7,
            "atr7": atr7,
            "buffer_pass": buffer_pass,
            "prior_touch": prior_touch,
            "fresh_reclaim": buffer_pass and prior_touch,
            "trend_pass": trend_pass,
            "distance_atr": distance_atr,
            "valid": valid,
        }

    def _event(
        self,
        name: str,
        index: int,
        snapshot: dict[str, Any],
        **extra: Any,
    ) -> None:
        self.events.append(
            {
                "event": name,
                "signal_index": int(index),
                "side": "short",
                **snapshot,
                **extra,
            }
        )

    def __call__(
        self,
        config: Any,
        book: Any,
        features: Any,
        index: int,
    ) -> bool:
        if config.side != -1 or not self.enabled:
            return self.engine.close_entry_signal(config, book, features, index)
        if config.entry_mode != "reclaim":
            raise RuntimeError("P requires the frozen V4 short reclaim mode")
        if index < 1:
            return False
        snapshot = self._snapshot(config, book, features, index)
        if self.armed_at is not None and index - self.armed_at > self.pending_days:
            self._event(
                "expire_pending",
                index,
                snapshot,
                armed_at_index=self.armed_at,
            )
            self.armed_at = None
        if (
            self.armed_at is not None
            and snapshot["valid"]
            and snapshot["close"] >= snapshot["ma7"]
        ):
            self._event(
                "invalidate_across_ma7",
                index,
                snapshot,
                armed_at_index=self.armed_at,
            )
            self.armed_at = None
        if snapshot["fresh_reclaim"]:
            self.armed_at = index
            self._event(
                "arm_fresh_reclaim",
                index,
                snapshot,
                armed_at_index=index,
            )
        if self.armed_at is None:
            return False
        delayed = index > self.armed_at
        passed = bool(
            index - self.armed_at <= self.pending_days
            and snapshot["buffer_pass"]
            and snapshot["trend_pass"]
        )
        if not passed:
            return False
        if delayed and snapshot["distance_atr"] > self.cap_atr:
            self._event(
                "reject_overextended_pending",
                index,
                snapshot,
                armed_at_index=self.armed_at,
                cap_atr=self.cap_atr,
            )
            self.armed_at = None
            return False
        self._event(
            "confirm_pending_entry",
            index,
            snapshot,
            armed_at_index=self.armed_at,
            delayed=delayed,
        )
        if delayed:
            self.delayed_confirmations.add((-1, int(index)))
        self.armed_at = None
        return True

    def entry_was_delayed(self, side: int, signal_index: int) -> bool:
        return bool(self.enabled and (int(side), int(signal_index)) in self.delayed_confirmations)

    def on_position_entered(self, side: int, signal_index: int) -> None:
        if self.armed_at is None:
            return
        self.events.append(
            {
                "event": "cancel_pending_other_entry",
                "signal_index": int(signal_index),
                "side": "long" if side > 0 else "short",
                "armed_at_index": int(self.armed_at),
            }
        )
        self.armed_at = None

    def record_handoff(
        self,
        old_side: int,
        new_side: int,
        signal_index: int,
        exit_reason: str,
    ) -> None:
        self.events.append(
            {
                "event": "delayed_position_opposite_handoff",
                "signal_index": int(signal_index),
                "side": "long" if new_side > 0 else "short",
                "old_side": "long" if old_side > 0 else "short",
                "new_side": "long" if new_side > 0 else "short",
                "exit_reason": str(exit_reason),
            }
        )


@dataclass(slots=True)
class PFTExecutionResult:
    config: PFTConfig
    raw: Any
    pending_events: list[dict[str, Any]]
    source_sha256: str
    rsi6: np.ndarray
    activation_counts: dict[str, int]

    @property
    def metrics(self) -> dict[str, Any]:
        return self.raw.metrics

    @property
    def trades(self) -> list[dict[str, Any]]:
        return self.raw.trades

    @property
    def path(self) -> list[dict[str, Any]]:
        return self.raw.path


def _capture_filtered_source(context: Any, *, forced_slope: bool) -> str:
    confirmation = context.confirmation
    mode = confirmation.MA_AND_SLOPE if forced_slope else confirmation.MA_ONLY
    expected_name = f"def v3_{mode.lower()}_backtest("
    captured: dict[str, str] = {}
    original_compile = builtins.compile

    def capture(source: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(source, str) and expected_name in source:
            captured["source"] = source
        return original_compile(source, *args, **kwargs)

    builtins.compile = capture
    try:
        confirmation.build_filtered_backtest(
            context.formation,
            context.engine,
            mode,
        )
    finally:
        builtins.compile = original_compile
    if "source" not in captured:
        raise RuntimeError(f"failed to capture exact V4 {mode} source")
    return captured["source"]


def _replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label} source marker drift: expected 1, got {count}")
    return source.replace(old, new, 1)


def _apply_common_state(source: str) -> str:
    source = _replace_once(
        source,
        "    cooldown_left = 0\n    bars_held = 0\n",
        (
            "    cooldown_left = 0\n"
            "    active_entry_was_delayed_pending = False\n"
            "    short_rsi_run = 0\n"
            "    bars_held = 0\n"
        ),
        "common state",
    )
    enter_nonlocal = (
        "        nonlocal entry_ts, entry_price, entry_equity, entry_side\n"
        "        nonlocal bars_held, stop_price, highest_close, lowest_close, mark_price\n"
    )
    source = _replace_once(
        source,
        enter_nonlocal,
        (
            enter_nonlocal
            + "        nonlocal active_entry_was_delayed_pending, short_rsi_run\n"
        ),
        "enter nonlocal",
    )
    source = _replace_once(
        source,
        "        mark_price = price\n\n    def settle_funding(",
        (
            "        mark_price = price\n"
            "        active_entry_was_delayed_pending = (\n"
            "            v4_pft_pending_entry_was_delayed(\n"
            "                config.side, signal_index\n"
            "            )\n"
            "        )\n"
            "        v4_pft_on_position_entered(config.side, signal_index)\n"
            "        short_rsi_run = 0\n\n"
            "    def settle_funding("
        ),
        "enter state assignment",
    )
    close_nonlocal = (
        "        nonlocal entry_ts, entry_price, entry_equity, entry_side\n"
        "        nonlocal bars_held, stop_price, highest_close, lowest_close\n"
    )
    source = _replace_once(
        source,
        close_nonlocal,
        (
            close_nonlocal
            + "        nonlocal active_entry_was_delayed_pending, short_rsi_run\n"
        ),
        "close nonlocal",
    )
    source = _replace_once(
        source,
        (
            "        highest_close = -math.inf\n"
            "        lowest_close = math.inf\n\n"
            "    for index in range(start_index, terminal_index + 1):"
        ),
        (
            "        highest_close = -math.inf\n"
            "        lowest_close = math.inf\n"
            "        active_entry_was_delayed_pending = False\n"
            "        short_rsi_run = 0\n\n"
            "    for index in range(start_index, terminal_index + 1):"
        ),
        "close reset",
    )
    source = _replace_once(
        source,
        '                        "action": "terminal",\n',
        (
            '                        "action": "terminal",\n'
            '                        "pft_short_rsi_run": short_rsi_run,\n'
            '                        "pft_delayed_position": active_entry_was_delayed_pending,\n'
        ),
        "terminal trace",
    )
    source = _replace_once(
        source,
        '                    "action": action,\n',
        (
            '                    "action": action,\n'
            '                    "pft_short_rsi_run": short_rsi_run,\n'
            '                    "pft_delayed_position": active_entry_was_delayed_pending,\n'
        ),
        "daily trace",
    )
    return source


def _apply_handoff(source: str) -> str:
    exit_block = """\
            if reason:
                close(ts, current_open, reason, index)
                cooldown_left = config.cooldown_days
                exited_at_open = True
                action = reason
"""
    handoff_block = """\
            if reason:
                exiting_side = side
                was_delayed_pending = active_entry_was_delayed_pending
                close(ts, current_open, reason, index)
                cooldown_left = config.cooldown_days
                exited_at_open = True
                action = reason
                opposite_config = (
                    short_config if exiting_side > 0 else long_config
                )
                if (
                    reason != "short_rsi_take_profit"
                    and was_delayed_pending
                    and exiting_side < 0
                    and opposite_config is not None
                    and v4_pft_close_entry_signal(
                        opposite_config,
                        book,
                        features,
                        decision_index,
                    )
                ):
                    enter(
                        opposite_config,
                        ts,
                        current_open,
                        index,
                        decision_index,
                    )
                    cooldown_left = 0
                    v4_pft_record_handoff(
                        exiting_side,
                        opposite_config.side,
                        decision_index,
                        reason,
                    )
                    action = "handoff_short_to_long_v4_reclaim"
"""
    return _replace_once(source, exit_block, handoff_block, "P handoff")


def _apply_rsi_take_profit(source: str) -> str:
    original = """\
            reason = signal_exit(
                config,
                book,
                features,
                decision_index,
                bars_held,
            )
"""
    replacement = """\
            native_reason = signal_exit(
                config,
                book,
                features,
                decision_index,
                bars_held,
            )
            rsi_reason = None
            if side < 0:
                current_rsi = float(v4_pft_rsi6[decision_index])
                if np.isfinite(current_rsi) and current_rsi < v4_pft_rsi_threshold:
                    short_rsi_run += 1
                else:
                    short_rsi_run = 0
                signal_close = float(book.close[decision_index])
                gross_short_profit = (
                    (entry_price - signal_close) / entry_price
                    if np.isfinite(entry_price) and entry_price > 0.0
                    else -math.inf
                )
                if (
                    short_rsi_run >= v4_pft_rsi_days
                    and gross_short_profit > v4_pft_roundtrip_cost_rate
                    and not math.isclose(
                        gross_short_profit,
                        v4_pft_roundtrip_cost_rate,
                        rel_tol=1e-12,
                        abs_tol=1e-12,
                    )
                ):
                    rsi_reason = "short_rsi_take_profit"
            else:
                short_rsi_run = 0
            reason = rsi_reason or native_reason
"""
    return _replace_once(source, original, replacement, "T daily exit")


def _activation_counts(
    raw: Any,
    pending_events: list[dict[str, Any]],
) -> dict[str, int]:
    actions = [str(row.get("action", "")) for row in raw.path]
    exits = [str(row.get("exit_reason", "")) for row in raw.trades]

    def event_count(name: str) -> int:
        return sum(str(row.get("event")) == name for row in pending_events)

    return {
        "p_arm": event_count("arm_fresh_reclaim"),
        "p_delayed_confirm": sum(
            str(row.get("event")) == "confirm_pending_entry"
            and bool(row.get("delayed"))
            for row in pending_events
        ),
        "p_overextended_reject": event_count("reject_overextended_pending"),
        "p_expire": event_count("expire_pending"),
        "p_ma7_invalidate": event_count("invalidate_across_ma7"),
        "p_other_entry_cancel": event_count("cancel_pending_other_entry"),
        "p_handoff": event_count("delayed_position_opposite_handoff"),
        "f_accept": sum("reverse_long_trailing_stop_to_short" in action for action in actions)
        + sum("enter_pending_filtered_reversal_short" in action for action in actions),
        "f_reject": sum("reversal_filter_rejected" in action for action in actions),
        "t_exit": sum(reason == "short_rsi_take_profit" for reason in exits),
        "protective_stop": sum(reason == "protective_stop" for reason in exits),
        "terminal_flatten": sum(reason == "terminal_flatten" for reason in exits),
    }


def build_variant_function(
    context: Any,
    config: PFTConfig,
    *,
    pending_signal: QualityShortPendingSignal,
    rsi6: np.ndarray,
) -> tuple[Callable[..., Any], str]:
    source = _capture_filtered_source(
        context,
        forced_slope=config.forced_slope_enabled,
    )
    old_name = (
        "v3_ma_and_slope_backtest"
        if config.forced_slope_enabled
        else "v3_ma_only_backtest"
    )
    new_name = f"v4_pft_{config.arm_id.lower()}_backtest"
    source = _replace_once(
        source,
        f"def {old_name}(",
        f"def {new_name}(",
        "variant function name",
    )
    source = _apply_common_state(source)
    if config.rsi_take_profit_enabled:
        source = _apply_rsi_take_profit(source)
    if config.pending_enabled:
        source = _apply_handoff(source)
    namespace = dict(context.engine.__dict__)
    namespace.update(
        {
            "close_entry_signal": pending_signal,
            "v4_pft_pending_entry_was_delayed": pending_signal.entry_was_delayed,
            "v4_pft_on_position_entered": pending_signal.on_position_entered,
            "v4_pft_record_handoff": pending_signal.record_handoff,
            "v4_pft_close_entry_signal": context.engine.close_entry_signal,
            "v4_pft_rsi6": rsi6,
            "v4_pft_rsi_threshold": config.rsi_threshold,
            "v4_pft_rsi_days": config.rsi_days,
            "v4_pft_roundtrip_cost_rate": config.roundtrip_cost_rate,
        }
    )
    try:
        compiled = compile(source, f"<v4-pft-{config.arm_id}>", "exec")
    except SyntaxError as exc:
        lines = source.splitlines()
        left = max(0, (exc.lineno or 1) - 8)
        right = min(len(lines), (exc.lineno or 1) + 7)
        context_text = "\n".join(
            f"{index + 1}: {lines[index]}" for index in range(left, right)
        )
        raise RuntimeError(
            f"PFT source failed to compile:\n{context_text}"
        ) from exc
    exec(compiled, namespace)
    return namespace[new_name], hashlib.sha256(source.encode()).hexdigest()


def run_variant(
    context: Any,
    config: PFTConfig,
    *,
    start_index: int,
    terminal_index: int,
    slippage: float = 0.0004,
    signal_lag: int = 0,
    include_funding: bool = True,
    retain: bool = False,
) -> PFTExecutionResult:
    if not (0 <= start_index < terminal_index <= context.book.count):
        raise ValueError("invalid PFT window")
    rsi6 = wilder_rsi6(context.book.close, 6)
    pending_signal = QualityShortPendingSignal(
        context.engine,
        enabled=config.pending_enabled,
        pending_days=config.pending_days,
        cap_atr=config.pending_cap_atr,
    )
    function, source_sha = build_variant_function(
        context,
        config,
        pending_signal=pending_signal,
        rsi6=rsi6,
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
    activations = _activation_counts(raw, pending_signal.events)
    return PFTExecutionResult(
        config=config,
        raw=raw,
        pending_events=list(pending_signal.events),
        source_sha256=source_sha,
        rsi6=rsi6,
        activation_counts=activations,
    )
