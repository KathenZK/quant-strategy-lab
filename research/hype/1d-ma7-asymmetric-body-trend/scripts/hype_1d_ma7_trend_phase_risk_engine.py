"""Exact-V4-derived trend phase and leverage engine for TPR research."""

from __future__ import annotations

import builtins
from dataclasses import asdict, dataclass
import hashlib
import math
from types import ModuleType
from typing import Any, Callable

import numpy as np


Q_VALUES = (None, 0.20, 0.30, 0.40)
E_VALUES = (0, 2, 3)
ROUNDTRIP_GUARD = 0.0028


def candidate_id(q_threshold: float | None, e_days: int) -> str:
    q = "OFF" if q_threshold is None else str(int(round(q_threshold * 100)))
    e = "OFF" if e_days == 0 else str(e_days)
    return f"Q{q}_E{e}_T25X2"


@dataclass(frozen=True, slots=True)
class TPRConfig:
    arm_id: str
    q_threshold: float | None
    e_days: int
    t_enabled: bool = True
    er_lookback: int = 7
    rsi_threshold: float = 25.0
    rsi_days: int = 2
    roundtrip_guard: float = ROUNDTRIP_GUARD

    def __post_init__(self) -> None:
        if self.q_threshold not in Q_VALUES:
            raise ValueError("q_threshold is outside the frozen grid")
        if self.e_days not in E_VALUES:
            raise ValueError("e_days is outside the frozen grid")
        if self.er_lookback != 7:
            raise ValueError("ER lookback is frozen at 7")
        if self.rsi_threshold != 25.0 or self.rsi_days != 2:
            raise ValueError("T is frozen at RSI6 25x2")
        if not math.isclose(self.roundtrip_guard, ROUNDTRIP_GUARD):
            raise ValueError("roundtrip guard is frozen at 0.0028")

    def canonical(self) -> dict[str, Any]:
        return asdict(self)


def ranked_configs() -> list[TPRConfig]:
    return [
        TPRConfig(
            arm_id=candidate_id(q_threshold, e_days),
            q_threshold=q_threshold,
            e_days=e_days,
        )
        for q_threshold in Q_VALUES
        for e_days in E_VALUES
    ]


def oat_config(config: TPRConfig, module: str) -> TPRConfig:
    if module == "Q":
        return TPRConfig(
            arm_id=f"{config.arm_id}_OAT_NO_Q",
            q_threshold=None,
            e_days=config.e_days,
            t_enabled=config.t_enabled,
        )
    if module == "E":
        return TPRConfig(
            arm_id=f"{config.arm_id}_OAT_NO_E",
            q_threshold=config.q_threshold,
            e_days=0,
            t_enabled=config.t_enabled,
        )
    if module == "T":
        return TPRConfig(
            arm_id=f"{config.arm_id}_OAT_NO_T",
            q_threshold=config.q_threshold,
            e_days=config.e_days,
            t_enabled=False,
        )
    raise ValueError(f"unknown module: {module}")


def config_sha256(config: TPRConfig) -> str:
    import json

    payload = json.dumps(
        config.canonical(), sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def signed_efficiency(
    close: Any,
    index: int,
    side: int,
    lookback: int = 7,
) -> float:
    values = np.asarray(close, dtype=float)
    if values.ndim != 1:
        raise ValueError("close must be one-dimensional")
    if side not in (-1, 1):
        raise ValueError("side must be -1 or 1")
    if lookback < 1 or index < lookback or index >= len(values):
        return math.nan
    window = values[index - lookback : index + 1]
    if not np.isfinite(window).all():
        return math.nan
    path = float(np.abs(np.diff(window)).sum())
    if path <= 0.0:
        return math.nan
    return float(side * (window[-1] - window[0]) / path)


def wilder_rsi6(close: Any, period: int = 6) -> np.ndarray:
    values = np.asarray(close, dtype=float)
    result = np.full(len(values), np.nan, dtype=float)
    if values.ndim != 1:
        raise ValueError("close must be one-dimensional")
    if period < 1 or len(values) <= period or not np.isfinite(values).all():
        return result
    delta = np.diff(values)
    gain = np.maximum(delta, 0.0)
    loss = np.maximum(-delta, 0.0)
    avg_gain = float(gain[:period].mean())
    avg_loss = float(loss[:period].mean())

    def rsi(up: float, down: float) -> float:
        if up == 0.0 and down == 0.0:
            return 50.0
        if down == 0.0:
            return 100.0
        if up == 0.0:
            return 0.0
        return 100.0 - 100.0 / (1.0 + up / down)

    result[period] = rsi(avg_gain, avg_loss)
    for index in range(period + 1, len(values)):
        avg_gain = (avg_gain * (period - 1) + float(gain[index - 1])) / period
        avg_loss = (avg_loss * (period - 1) + float(loss[index - 1])) / period
        result[index] = rsi(avg_gain, avg_loss)
    return result


def phase_exit_decision(
    *,
    side: int,
    long_decay_run: int,
    short_rsi_run: int,
    current_ma: float,
    prior_ma: float,
    current_atr: float,
    current_rsi: float,
    signal_close: float,
    entry_price: float,
    e_days: int,
    t_enabled: bool,
    rsi_threshold: float = 25.0,
    rsi_days: int = 2,
    roundtrip_guard: float = ROUNDTRIP_GUARD,
) -> tuple[str | None, int, int]:
    """Advance held-position counters and return the phase exit, if any."""

    if side > 0:
        short_rsi_run = 0
        slope_atr = (
            (current_ma - prior_ma) / current_atr
            if all(math.isfinite(value) for value in (current_ma, prior_ma, current_atr))
            and current_atr > 0.0
            else math.nan
        )
        long_decay_run = (
            long_decay_run + 1
            if math.isfinite(slope_atr) and slope_atr <= 0.0
            else 0
        )
        gross_profit = (
            (signal_close - entry_price) / entry_price
            if math.isfinite(entry_price) and entry_price > 0.0
            else -math.inf
        )
        reason = (
            "long_slope_decay_exit"
            if e_days > 0
            and long_decay_run >= e_days
            and gross_profit - roundtrip_guard > 1e-15
            else None
        )
        return reason, long_decay_run, short_rsi_run
    if side < 0:
        long_decay_run = 0
        short_rsi_run = (
            short_rsi_run + 1
            if math.isfinite(current_rsi) and current_rsi < rsi_threshold
            else 0
        )
        gross_profit = (
            (entry_price - signal_close) / entry_price
            if math.isfinite(entry_price) and entry_price > 0.0
            else -math.inf
        )
        reason = (
            "short_rsi_take_profit"
            if t_enabled
            and short_rsi_run >= rsi_days
            and gross_profit - roundtrip_guard > 1e-15
            else None
        )
        return reason, long_decay_run, short_rsi_run
    return None, 0, 0


class EntryQualitySignal:
    def __init__(self, engine: ModuleType, close: Any, threshold: float | None) -> None:
        self.engine = engine
        self.close = np.asarray(close, dtype=float)
        self.threshold = threshold
        self.events: list[dict[str, Any]] = []

    def __call__(self, config: Any, book: Any, features: Any, index: int) -> bool:
        exact = bool(self.engine.close_entry_signal(config, book, features, index))
        if not exact:
            return False
        value = signed_efficiency(self.close, index, int(config.side), 7)
        passed = bool(
            self.threshold is None
            or (math.isfinite(value) and value > self.threshold)
        )
        self.events.append(
            {
                "event": "q_pass" if passed else "q_reject",
                "signal_index": int(index),
                "side": "long" if config.side > 0 else "short",
                "signed_er7": value,
                "threshold": self.threshold,
            }
        )
        return passed


@dataclass(frozen=True, slots=True)
class LeverageSpec:
    id: str
    mode: str
    value: float
    quality_adjusted: bool = False

    def __post_init__(self) -> None:
        if self.mode not in {"fixed", "atr_risk"}:
            raise ValueError("unknown leverage mode")
        if self.mode == "fixed" and not 0.0 < self.value <= 3.0:
            raise ValueError("fixed leverage must be within (0, 3]")
        if self.mode == "atr_risk" and self.value not in {0.10, 0.15, 0.20}:
            raise ValueError("risk budget outside frozen grid")


def leverage_specs() -> list[LeverageSpec]:
    return [
        *[
            LeverageSpec(f"FIXED_{value:.2f}X", "fixed", value)
            for value in (1.25, 1.50, 2.00, 2.50, 3.00)
        ],
        LeverageSpec("ATR_R10", "atr_risk", 0.10),
        LeverageSpec("ATR_R15", "atr_risk", 0.15),
        LeverageSpec("ATR_R20", "atr_risk", 0.20),
        LeverageSpec("ATRER_R15", "atr_risk", 0.15, True),
    ]


class LeveragePolicy:
    def __init__(self, context: Any, spec: LeverageSpec | None) -> None:
        self.context = context
        self.spec = spec
        self.pending_leverage = 1.0
        self.last_entry_leverage = 1.0
        self.events: list[dict[str, Any]] = []

    def set_entry_context(self, side: int, price: float, signal_index: int) -> None:
        if self.spec is None:
            leverage = 1.0
            er = signed_efficiency(self.context.book.close, signal_index, side, 7)
            atr = float(self.context.features.atr7[signal_index])
        elif self.spec.mode == "fixed":
            leverage = self.spec.value
            er = signed_efficiency(self.context.book.close, signal_index, side, 7)
            atr = float(self.context.features.atr7[signal_index])
        else:
            atr = float(self.context.features.atr7[signal_index])
            er = signed_efficiency(self.context.book.close, signal_index, side, 7)
            if not math.isfinite(atr) or atr <= 0.0 or price <= 0.0:
                leverage = 0.5
            else:
                leverage = self.spec.value / (1.5 * atr / price)
            if self.spec.quality_adjusted:
                multiplier = (
                    min(1.5, max(0.75, 0.75 + er))
                    if math.isfinite(er)
                    else 0.75
                )
                leverage *= multiplier
            leverage = min(3.0, max(0.5, leverage))
        self.pending_leverage = float(leverage)
        self.last_entry_leverage = float(leverage)
        self.events.append(
            {
                "event": "entry_leverage",
                "side": "long" if side > 0 else "short",
                "signal_index": int(signal_index),
                "entry_price": float(price),
                "atr7": atr,
                "signed_er7": er,
                "target_leverage": float(leverage),
                "spec_id": self.spec.id if self.spec else "ONE_X",
            }
        )

    def __call__(
        self,
        equity: float,
        old_qty: float,
        target_side: int,
        price: float,
        cost_rate: float,
    ) -> tuple[float, float, float]:
        leverage = self.pending_leverage if target_side else 1.0
        post_equity = equity
        target_qty = old_qty
        turnover = 0.0
        for _ in range(20):
            target_qty = (
                target_side * leverage * post_equity / price
                if target_side
                else 0.0
            )
            turnover = abs(target_qty - old_qty) * price
            updated = equity - turnover * cost_rate
            if math.isclose(updated, post_equity, rel_tol=0.0, abs_tol=1e-14):
                post_equity = updated
                break
            post_equity = updated
        if target_side:
            self.pending_leverage = 1.0
        return float(target_qty), float(post_equity), float(turnover)


@dataclass(slots=True)
class TPRExecutionResult:
    config: TPRConfig
    raw: Any
    source_sha256: str
    entry_events: list[dict[str, Any]]
    leverage_events: list[dict[str, Any]]
    activation_counts: dict[str, int]
    rsi6: np.ndarray


def _capture_exact_source(context: Any) -> str:
    expected_name = "def v3_ma_only_backtest("
    captured: dict[str, str] = {}
    original_compile = builtins.compile

    def capture(source: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(source, str) and expected_name in source:
            captured["source"] = source
        return original_compile(source, *args, **kwargs)

    builtins.compile = capture
    try:
        context.confirmation.build_filtered_backtest(
            context.formation,
            context.engine,
            context.confirmation.MA_ONLY,
        )
    finally:
        builtins.compile = original_compile
    if "source" not in captured:
        raise RuntimeError("failed to capture exact V4 source")
    return captured["source"]


def _replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label} source marker drift: expected 1, got {count}")
    return source.replace(old, new, 1)


def _apply_state(source: str) -> str:
    source = _replace_once(
        source,
        "    cooldown_left = 0\n    bars_held = 0\n",
        (
            "    cooldown_left = 0\n"
            "    long_decay_run = 0\n"
            "    short_rsi_run = 0\n"
            "    active_entry_leverage = 1.0\n"
            "    bars_held = 0\n"
        ),
        "state initialization",
    )
    enter_nonlocal = (
        "        nonlocal entry_ts, entry_price, entry_equity, entry_side\n"
        "        nonlocal bars_held, stop_price, highest_close, lowest_close, mark_price\n"
    )
    source = _replace_once(
        source,
        enter_nonlocal,
        enter_nonlocal
        + "        nonlocal long_decay_run, short_rsi_run, active_entry_leverage\n",
        "enter nonlocal",
    )
    source = _replace_once(
        source,
        "        before = equity\n        trade_to(config.side, price)\n",
        (
            "        before = equity\n"
            "        v4_tpr_set_entry_context(config.side, price, signal_index)\n"
            "        trade_to(config.side, price)\n"
            "        active_entry_leverage = v4_tpr_last_entry_leverage()\n"
        ),
        "entry leverage",
    )
    source = _replace_once(
        source,
        "        mark_price = price\n\n    def settle_funding(",
        (
            "        mark_price = price\n"
            "        long_decay_run = 0\n"
            "        short_rsi_run = 0\n\n"
            "    def settle_funding("
        ),
        "entry reset",
    )
    close_nonlocal = (
        "        nonlocal entry_ts, entry_price, entry_equity, entry_side\n"
        "        nonlocal bars_held, stop_price, highest_close, lowest_close\n"
    )
    source = _replace_once(
        source,
        close_nonlocal,
        close_nonlocal
        + "        nonlocal long_decay_run, short_rsi_run, active_entry_leverage\n",
        "close nonlocal",
    )
    source = _replace_once(
        source,
        '                "entry_price": entry_price,\n',
        (
            '                "entry_price": entry_price,\n'
            '                "entry_leverage": active_entry_leverage,\n'
        ),
        "trade leverage field",
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
            "        long_decay_run = 0\n"
            "        short_rsi_run = 0\n"
            "        active_entry_leverage = 1.0\n\n"
            "    for index in range(start_index, terminal_index + 1):"
        ),
        "close reset",
    )
    source = _replace_once(
        source,
        '                        "action": "terminal",\n',
        (
            '                        "action": "terminal",\n'
            '                        "tpr_long_decay_run": long_decay_run,\n'
            '                        "tpr_short_rsi_run": short_rsi_run,\n'
            '                        "tpr_entry_leverage": active_entry_leverage,\n'
        ),
        "terminal trace",
    )
    source = _replace_once(
        source,
        '                    "action": action,\n',
        (
            '                    "action": action,\n'
            '                    "tpr_long_decay_run": long_decay_run,\n'
            '                    "tpr_short_rsi_run": short_rsi_run,\n'
            '                    "tpr_entry_leverage": active_entry_leverage,\n'
        ),
        "daily trace",
    )
    return source


def _apply_exits(source: str) -> str:
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
            signal_close = float(book.close[decision_index])
            phase_reason, long_decay_run, short_rsi_run = (
                v4_tpr_phase_exit_decision(
                    side=side,
                    long_decay_run=long_decay_run,
                    short_rsi_run=short_rsi_run,
                    current_ma=float(features.ma7[decision_index]),
                    prior_ma=(
                        float(features.ma7[decision_index - 1])
                        if decision_index >= 1
                        else math.nan
                    ),
                    current_atr=float(features.atr7[decision_index]),
                    current_rsi=float(v4_tpr_rsi6[decision_index]),
                    signal_close=signal_close,
                    entry_price=entry_price,
                    e_days=v4_tpr_e_days,
                    t_enabled=v4_tpr_t_enabled,
                    rsi_threshold=v4_tpr_rsi_threshold,
                    rsi_days=v4_tpr_rsi_days,
                    roundtrip_guard=v4_tpr_roundtrip_guard,
                )
            )
            reason = phase_reason or native_reason
"""
    return _replace_once(source, original, replacement, "phase exits")


def build_variant_function(
    context: Any,
    config: TPRConfig,
    *,
    entry_signal: EntryQualitySignal,
    leverage_policy: LeveragePolicy,
    rsi6: np.ndarray,
) -> tuple[Callable[..., Any], str]:
    source = _capture_exact_source(context)
    function_name = f"tpr_{hashlib.sha256(config.arm_id.encode()).hexdigest()[:12]}_backtest"
    source = _replace_once(
        source,
        "def v3_ma_only_backtest(",
        f"def {function_name}(",
        "function name",
    )
    source = _apply_state(source)
    source = _apply_exits(source)
    namespace = dict(context.engine.__dict__)
    namespace.update(
        {
            "close_entry_signal": entry_signal,
            "_target_quantity": leverage_policy,
            "v4_tpr_set_entry_context": leverage_policy.set_entry_context,
            "v4_tpr_last_entry_leverage": lambda: leverage_policy.last_entry_leverage,
            "v4_tpr_rsi6": rsi6,
            "v4_tpr_rsi_threshold": config.rsi_threshold,
            "v4_tpr_rsi_days": config.rsi_days,
            "v4_tpr_t_enabled": config.t_enabled,
            "v4_tpr_e_days": config.e_days,
            "v4_tpr_roundtrip_guard": config.roundtrip_guard,
            "v4_tpr_phase_exit_decision": phase_exit_decision,
        }
    )
    compiled = compile(source, f"<tpr-{config.arm_id}>", "exec")
    exec(compiled, namespace)
    return namespace[function_name], hashlib.sha256(source.encode()).hexdigest()


def run_variant(
    context: Any,
    config: TPRConfig,
    *,
    start_index: int,
    terminal_index: int,
    slippage: float = 0.0004,
    include_funding: bool = True,
    retain: bool = False,
    leverage_spec: LeverageSpec | None = None,
) -> TPRExecutionResult:
    rsi6 = wilder_rsi6(context.book.close)
    entry_signal = EntryQualitySignal(
        context.engine,
        context.book.close,
        config.q_threshold,
    )
    leverage_policy = LeveragePolicy(context, leverage_spec)
    function, source_hash = build_variant_function(
        context,
        config,
        entry_signal=entry_signal,
        leverage_policy=leverage_policy,
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
        signal_lag=0,
        include_funding=include_funding,
        retain=retain,
    )
    if bool(raw.metrics.get("bankrupt_intraday")):
        raise RuntimeError(f"{config.arm_id} became bankrupt")
    exits = [str(trade.get("exit_reason", "")) for trade in raw.trades]
    counts = {
        "q_pass": sum(event["event"] == "q_pass" for event in entry_signal.events),
        "q_reject": sum(event["event"] == "q_reject" for event in entry_signal.events),
        "e_exit": sum(reason == "long_slope_decay_exit" for reason in exits),
        "t_exit": sum(reason == "short_rsi_take_profit" for reason in exits),
        "protective_stop": sum(reason == "protective_stop" for reason in exits),
        "leverage_entries": len(leverage_policy.events),
    }
    return TPRExecutionResult(
        config=config,
        raw=raw,
        source_sha256=source_hash,
        entry_events=list(entry_signal.events),
        leverage_events=list(leverage_policy.events),
        activation_counts=counts,
        rsi6=rsi6,
    )
