"""Exact-V4-derived engine for the WTL hierarchical trend lifecycle search."""

from __future__ import annotations

import builtins
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
from itertools import product
from types import ModuleType
from typing import Any, Callable, Iterable

import numpy as np


ROUNDTRIP_GUARD = 0.0028
ENTRY_SCOPES = ("both", "long", "short")
ER_LOOKBACKS = (3, 5, 7, 10, 14)
ER_THRESHOLDS = (-0.25, -0.10, 0.0, 0.10, 0.20, 0.30, 0.40)
CHASE_CAPS = (0.25, 0.50, 0.75, 1.00, 1.50, 2.00, 3.00)
SLOPE_THRESHOLDS = (0.0, 0.01, 0.02, 0.04, 0.06, 0.08, 0.10)
PERSISTENCE_LOOKBACKS = (3, 5, 7, 10)
PERSISTENCE_THRESHOLDS = (0.50, 0.60, 0.70, 0.80)
TRAIL_ACTIVATIONS = (0.5, 1.0, 1.5, 2.0, 3.0, 4.0)
TRAIL_ATR_GIVEBACKS = (0.25, 0.50, 0.75, 1.0, 1.25, 1.50, 2.0, 2.50)
TRAIL_FRACTIONS = (0.15, 0.25, 0.35, 0.50, 0.65, 0.80)
TRAIL_CONFIRM_DAYS = (1, 2)
RSI_THRESHOLDS = (15.0, 20.0, 25.0, 30.0, 35.0, 40.0)
RSI_DAYS = (1, 2, 3, 4)


@dataclass(frozen=True, slots=True)
class EntryFilter:
    kind: str = "off"
    scope: str = "both"
    lookback: int = 0
    threshold: float = 0.0

    def __post_init__(self) -> None:
        if self.kind not in {"off", "er", "chase", "slope", "persistence"}:
            raise ValueError("unknown entry filter")
        if self.scope not in ENTRY_SCOPES:
            raise ValueError("unknown entry scope")
        if self.kind == "off":
            if self.lookback != 0 or self.threshold != 0.0:
                raise ValueError("off entry filter must be canonical")
        elif self.kind == "er":
            if self.lookback not in ER_LOOKBACKS or self.threshold not in ER_THRESHOLDS:
                raise ValueError("ER entry parameter outside frozen grid")
        elif self.kind == "chase":
            if self.lookback != 0 or self.threshold not in CHASE_CAPS:
                raise ValueError("chase parameter outside frozen grid")
        elif self.kind == "slope":
            if self.lookback != 1 or self.threshold not in SLOPE_THRESHOLDS:
                raise ValueError("slope parameter outside frozen grid")
        elif (
            self.lookback not in PERSISTENCE_LOOKBACKS
            or self.threshold not in PERSISTENCE_THRESHOLDS
        ):
            raise ValueError("persistence parameter outside frozen grid")

    @property
    def enabled(self) -> bool:
        return self.kind != "off"

    def applies_to(self, side: int) -> bool:
        return self.scope == "both" or self.scope == ("long" if side > 0 else "short")


@dataclass(frozen=True, slots=True)
class TrailExit:
    mode: str = "off"
    activation_atr: float = 0.0
    giveback: float = 0.0
    confirm_days: int = 0

    def __post_init__(self) -> None:
        if self.mode not in {"off", "atr", "fraction"}:
            raise ValueError("unknown trail mode")
        if self.mode == "off":
            if (self.activation_atr, self.giveback, self.confirm_days) != (0.0, 0.0, 0):
                raise ValueError("off trail must be canonical")
            return
        if self.activation_atr not in TRAIL_ACTIVATIONS:
            raise ValueError("trail activation outside frozen grid")
        grid = TRAIL_ATR_GIVEBACKS if self.mode == "atr" else TRAIL_FRACTIONS
        if self.giveback not in grid or self.confirm_days not in TRAIL_CONFIRM_DAYS:
            raise ValueError("trail parameter outside frozen grid")

    @property
    def enabled(self) -> bool:
        return self.mode != "off"


@dataclass(frozen=True, slots=True)
class ShortRSIExit:
    threshold: float = 0.0
    days: int = 0

    def __post_init__(self) -> None:
        if self.days == 0:
            if self.threshold != 0.0:
                raise ValueError("off RSI must be canonical")
        elif self.threshold not in RSI_THRESHOLDS or self.days not in RSI_DAYS:
            raise ValueError("RSI parameter outside frozen grid")

    @property
    def enabled(self) -> bool:
        return self.days > 0


@dataclass(frozen=True, slots=True)
class WTLConfig:
    arm_id: str
    entry: EntryFilter = EntryFilter()
    long_exit: TrailExit = TrailExit()
    short_exit: TrailExit = TrailExit()
    short_rsi: ShortRSIExit = ShortRSIExit()
    roundtrip_guard: float = ROUNDTRIP_GUARD

    def __post_init__(self) -> None:
        if not self.arm_id:
            raise ValueError("arm_id is required")
        if not math.isclose(self.roundtrip_guard, ROUNDTRIP_GUARD):
            raise ValueError("roundtrip guard is frozen")

    def canonical(self) -> dict[str, Any]:
        return asdict(self)

    def enabled_modules(self) -> list[str]:
        modules = []
        if self.entry.enabled:
            modules.append("entry")
        if self.long_exit.enabled:
            modules.append("long_exit")
        if self.short_exit.enabled:
            modules.append("short_exit")
        if self.short_rsi.enabled:
            modules.append("short_rsi")
        return modules


def config_from_dict(row: dict[str, Any]) -> WTLConfig:
    return WTLConfig(
        arm_id=str(row["arm_id"]),
        entry=EntryFilter(**row["entry"]),
        long_exit=TrailExit(**row["long_exit"]),
        short_exit=TrailExit(**row["short_exit"]),
        short_rsi=ShortRSIExit(**row["short_rsi"]),
        roundtrip_guard=float(row.get("roundtrip_guard", ROUNDTRIP_GUARD)),
    )


def _config_digest_parts(
    entry: EntryFilter,
    long_exit: TrailExit,
    short_exit: TrailExit,
    short_rsi: ShortRSIExit,
) -> str:
    payload = json.dumps(
        {
            "entry": asdict(entry),
            "long_exit": asdict(long_exit),
            "short_exit": asdict(short_exit),
            "short_rsi": asdict(short_rsi),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()[:12].upper()


def config_sha256(config: WTLConfig) -> str:
    payload = json.dumps(config.canonical(), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def entry_specs() -> list[EntryFilter]:
    return [
        *[
            EntryFilter("er", scope, lookback, threshold)
            for lookback, threshold, scope in product(
                ER_LOOKBACKS, ER_THRESHOLDS, ENTRY_SCOPES
            )
        ],
        *[
            EntryFilter("chase", scope, 0, threshold)
            for threshold, scope in product(CHASE_CAPS, ENTRY_SCOPES)
        ],
        *[
            EntryFilter("slope", scope, 1, threshold)
            for threshold, scope in product(SLOPE_THRESHOLDS, ENTRY_SCOPES)
        ],
        *[
            EntryFilter("persistence", scope, lookback, threshold)
            for lookback, threshold, scope in product(
                PERSISTENCE_LOOKBACKS, PERSISTENCE_THRESHOLDS, ENTRY_SCOPES
            )
        ],
    ]


def trail_specs() -> list[TrailExit]:
    return [
        *[
            TrailExit("atr", activation, giveback, confirm)
            for activation, giveback, confirm in product(
                TRAIL_ACTIVATIONS, TRAIL_ATR_GIVEBACKS, TRAIL_CONFIRM_DAYS
            )
        ],
        *[
            TrailExit("fraction", activation, giveback, confirm)
            for activation, giveback, confirm in product(
                TRAIL_ACTIVATIONS, TRAIL_FRACTIONS, TRAIL_CONFIRM_DAYS
            )
        ],
    ]


def rsi_specs() -> list[ShortRSIExit]:
    return [
        ShortRSIExit(threshold, days)
        for threshold, days in product(RSI_THRESHOLDS, RSI_DAYS)
    ]


def stage_a_configs() -> list[WTLConfig]:
    configs: list[WTLConfig] = []
    configs.extend(
        WTLConfig(f"A_ENTRY_{index:03d}", entry=spec)
        for index, spec in enumerate(entry_specs(), 1)
    )
    configs.extend(
        WTLConfig(f"A_LONG_{index:03d}", long_exit=spec)
        for index, spec in enumerate(trail_specs(), 1)
    )
    configs.extend(
        WTLConfig(f"A_SHORT_{index:03d}", short_exit=spec)
        for index, spec in enumerate(trail_specs(), 1)
    )
    configs.extend(
        WTLConfig(f"A_RSI_{index:03d}", short_rsi=spec)
        for index, spec in enumerate(rsi_specs(), 1)
    )
    return configs


def build_combo_configs(
    entries: Iterable[EntryFilter],
    long_exits: Iterable[TrailExit],
    short_exits: Iterable[TrailExit],
    short_rsis: Iterable[ShortRSIExit],
) -> list[WTLConfig]:
    off_entry = EntryFilter()
    off_trail = TrailExit()
    off_rsi = ShortRSIExit()
    rows = []
    seen: set[str] = set()
    for entry, long_exit, short_exit, short_rsi in product(
        [off_entry, *entries],
        [off_trail, *long_exits],
        [off_trail, *short_exits],
        [off_rsi, *short_rsis],
    ):
        if not any((entry.enabled, long_exit.enabled, short_exit.enabled, short_rsi.enabled)):
            continue
        digest = _config_digest_parts(entry, long_exit, short_exit, short_rsi)
        if digest in seen:
            continue
        seen.add(digest)
        rows.append(
            WTLConfig(
                f"C_{digest}",
                entry=entry,
                long_exit=long_exit,
                short_exit=short_exit,
                short_rsi=short_rsi,
            )
        )
    return sorted(rows, key=lambda row: row.arm_id)


def disable_module(config: WTLConfig, module: str, suffix: str = "OAT") -> WTLConfig:
    kwargs: dict[str, Any] = {"arm_id": f"{config.arm_id}_{suffix}_NO_{module.upper()}"}
    if module == "entry":
        kwargs["entry"] = EntryFilter()
    elif module in {"long_exit", "short_exit"}:
        kwargs[module] = TrailExit()
    elif module == "short_rsi":
        kwargs["short_rsi"] = ShortRSIExit()
    else:
        raise ValueError(f"unknown module: {module}")
    return replace(config, **kwargs)


def keep_only_module(config: WTLConfig, module: str) -> WTLConfig:
    if module not in config.enabled_modules():
        raise ValueError("module is not enabled")
    return WTLConfig(
        f"{config.arm_id}_ONLY_{module.upper()}",
        entry=config.entry if module == "entry" else EntryFilter(),
        long_exit=config.long_exit if module == "long_exit" else TrailExit(),
        short_exit=config.short_exit if module == "short_exit" else TrailExit(),
        short_rsi=config.short_rsi if module == "short_rsi" else ShortRSIExit(),
    )


def _adjacent(value: Any, grid: tuple[Any, ...]) -> list[Any]:
    index = grid.index(value)
    return [grid[i] for i in (index - 1, index + 1) if 0 <= i < len(grid)]


def adjacent_neighbors(config: WTLConfig) -> list[WTLConfig]:
    rows: list[WTLConfig] = []
    if config.entry.enabled:
        if config.entry.kind == "er":
            fields = (("lookback", ER_LOOKBACKS), ("threshold", ER_THRESHOLDS))
        elif config.entry.kind == "chase":
            fields = (("threshold", CHASE_CAPS),)
        elif config.entry.kind == "slope":
            fields = (("threshold", SLOPE_THRESHOLDS),)
        else:
            fields = (
                ("lookback", PERSISTENCE_LOOKBACKS),
                ("threshold", PERSISTENCE_THRESHOLDS),
            )
        for field, grid in fields:
            for value in _adjacent(getattr(config.entry, field), grid):
                rows.append(
                    replace(
                        config,
                        arm_id=f"{config.arm_id}_N_ENTRY_{field}_{value}",
                        entry=replace(config.entry, **{field: value}),
                    )
                )
    for module in ("long_exit", "short_exit"):
        spec = getattr(config, module)
        if not spec.enabled:
            continue
        giveback_grid = TRAIL_ATR_GIVEBACKS if spec.mode == "atr" else TRAIL_FRACTIONS
        for field, grid in (
            ("activation_atr", TRAIL_ACTIVATIONS),
            ("giveback", giveback_grid),
            ("confirm_days", TRAIL_CONFIRM_DAYS),
        ):
            for value in _adjacent(getattr(spec, field), grid):
                rows.append(
                    replace(
                        config,
                        arm_id=f"{config.arm_id}_N_{module}_{field}_{value}",
                        **{module: replace(spec, **{field: value})},
                    )
                )
    if config.short_rsi.enabled:
        for field, grid in (("threshold", RSI_THRESHOLDS), ("days", RSI_DAYS)):
            for value in _adjacent(getattr(config.short_rsi, field), grid):
                rows.append(
                    replace(
                        config,
                        arm_id=f"{config.arm_id}_N_RSI_{field}_{value}",
                        short_rsi=replace(config.short_rsi, **{field: value}),
                    )
                )
    unique = {config_sha256(replace(row, arm_id="neighbor")): row for row in rows}
    return sorted(unique.values(), key=lambda row: row.arm_id)


def signed_efficiency(close: Any, index: int, side: int, lookback: int) -> float:
    values = np.asarray(close, dtype=float)
    if values.ndim != 1 or side not in (-1, 1):
        raise ValueError("invalid signed efficiency input")
    if index < lookback or index >= len(values):
        return math.nan
    window = values[index - lookback : index + 1]
    if not np.isfinite(window).all():
        return math.nan
    distance = float(np.abs(np.diff(window)).sum())
    if distance <= 0.0:
        return math.nan
    return float(side * (window[-1] - window[0]) / distance)


def directional_persistence(close: Any, index: int, side: int, lookback: int) -> float:
    values = np.asarray(close, dtype=float)
    if values.ndim != 1 or side not in (-1, 1):
        raise ValueError("invalid persistence input")
    if index < lookback or index >= len(values):
        return math.nan
    window = values[index - lookback : index + 1]
    if not np.isfinite(window).all():
        return math.nan
    return float(np.mean(side * np.diff(window) > 0.0))


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

    def value(up: float, down: float) -> float:
        if up == 0.0 and down == 0.0:
            return 50.0
        if down == 0.0:
            return 100.0
        if up == 0.0:
            return 0.0
        return 100.0 - 100.0 / (1.0 + up / down)

    result[period] = value(avg_gain, avg_loss)
    for index in range(period + 1, len(values)):
        avg_gain = (avg_gain * (period - 1) + float(gain[index - 1])) / period
        avg_loss = (avg_loss * (period - 1) + float(loss[index - 1])) / period
        result[index] = value(avg_gain, avg_loss)
    return result


class EntryQualitySignal:
    def __init__(self, exact_engine: ModuleType, spec: EntryFilter) -> None:
        self.exact_engine = exact_engine
        self.spec = spec
        self.events: list[dict[str, Any]] = []

    def __call__(self, config: Any, book: Any, features: Any, index: int) -> bool:
        exact = bool(self.exact_engine.close_entry_signal(config, book, features, index))
        if not exact or not self.spec.enabled or not self.spec.applies_to(int(config.side)):
            return exact
        side = int(config.side)
        if self.spec.kind == "er":
            metric = signed_efficiency(book.close, index, side, self.spec.lookback)
            passed = math.isfinite(metric) and metric > self.spec.threshold
        elif self.spec.kind == "chase":
            atr = float(features.atr7[index])
            metric = (
                side * (float(book.close[index]) - float(features.ma7[index])) / atr
                if math.isfinite(atr) and atr > 0.0
                else math.nan
            )
            passed = math.isfinite(metric) and metric < self.spec.threshold
        elif self.spec.kind == "slope":
            atr = float(features.atr7[index])
            metric = (
                side
                * (float(features.ma7[index]) - float(features.ma7[index - 1]))
                / atr
                if index >= 1 and math.isfinite(atr) and atr > 0.0
                else math.nan
            )
            passed = math.isfinite(metric) and metric > self.spec.threshold
        else:
            metric = directional_persistence(book.close, index, side, self.spec.lookback)
            passed = math.isfinite(metric) and metric > self.spec.threshold
        self.events.append(
            {
                "event": "entry_filter_pass" if passed else "entry_filter_reject",
                "signal_index": int(index),
                "side": "long" if side > 0 else "short",
                "kind": self.spec.kind,
                "scope": self.spec.scope,
                "metric": metric,
                "threshold": self.spec.threshold,
                "lookback": self.spec.lookback,
            }
        )
        return bool(passed)


def _trail_trigger(
    *,
    side: int,
    spec: TrailExit,
    peak_close: float,
    signal_close: float,
    entry_price: float,
    atr: float,
    guard: float,
) -> bool:
    if not spec.enabled or not all(
        math.isfinite(value) for value in (peak_close, signal_close, entry_price, atr)
    ):
        return False
    if entry_price <= 0.0 or atr <= 0.0:
        return False
    peak_profit = side * (peak_close - entry_price)
    current_profit = side * (signal_close - entry_price)
    if peak_profit / atr < spec.activation_atr or current_profit / entry_price <= guard:
        return False
    giveback = side * (peak_close - signal_close)
    if spec.mode == "atr":
        return giveback / atr >= spec.giveback
    return peak_profit > 0.0 and giveback / peak_profit >= spec.giveback


def lifecycle_exit_decision(
    *,
    side: int,
    long_run: int,
    short_run: int,
    rsi_run: int,
    long_exit: TrailExit,
    short_exit: TrailExit,
    short_rsi: ShortRSIExit,
    highest_close: float,
    lowest_close: float,
    signal_close: float,
    entry_price: float,
    atr: float,
    rsi6: float,
    roundtrip_guard: float = ROUNDTRIP_GUARD,
) -> tuple[str | None, int, int, int]:
    if side > 0:
        short_run = 0
        rsi_run = 0
        active = _trail_trigger(
            side=1,
            spec=long_exit,
            peak_close=highest_close,
            signal_close=signal_close,
            entry_price=entry_price,
            atr=atr,
            guard=roundtrip_guard,
        )
        long_run = long_run + 1 if active else 0
        reason = (
            f"long_mfe_{long_exit.mode}_trail_exit"
            if long_exit.enabled and long_run >= long_exit.confirm_days
            else None
        )
        return reason, long_run, short_run, rsi_run
    if side < 0:
        long_run = 0
        rsi_run = (
            rsi_run + 1
            if short_rsi.enabled and math.isfinite(rsi6) and rsi6 < short_rsi.threshold
            else 0
        )
        gross_profit = (entry_price - signal_close) / entry_price if entry_price > 0.0 else -math.inf
        rsi_reason = (
            "short_rsi_take_profit"
            if short_rsi.enabled
            and rsi_run >= short_rsi.days
            and gross_profit > roundtrip_guard
            else None
        )
        active = _trail_trigger(
            side=-1,
            spec=short_exit,
            peak_close=lowest_close,
            signal_close=signal_close,
            entry_price=entry_price,
            atr=atr,
            guard=roundtrip_guard,
        )
        short_run = short_run + 1 if active else 0
        trail_reason = (
            f"short_mfe_{short_exit.mode}_trail_exit"
            if short_exit.enabled and short_run >= short_exit.confirm_days
            else None
        )
        return rsi_reason or trail_reason, long_run, short_run, rsi_run
    return None, 0, 0, 0


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
            raise ValueError("fixed leverage outside cap")
        if self.mode == "atr_risk" and self.value not in {0.10, 0.15, 0.20}:
            raise ValueError("risk budget outside grid")


def leverage_specs() -> list[LeverageSpec]:
    return [
        *[LeverageSpec(f"FIXED_{value:.2f}X", "fixed", value) for value in (1.25, 1.50, 2.00, 2.50, 3.00)],
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
        atr = float(self.context.features.atr7[signal_index])
        er = signed_efficiency(self.context.book.close, signal_index, side, 7)
        if self.spec is None:
            leverage = 1.0
        elif self.spec.mode == "fixed":
            leverage = self.spec.value
        else:
            leverage = (
                self.spec.value / (1.5 * atr / price)
                if math.isfinite(atr) and atr > 0.0 and price > 0.0
                else 0.5
            )
            if self.spec.quality_adjusted:
                leverage *= min(1.50, max(0.75, 0.75 + er)) if math.isfinite(er) else 0.75
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
            target_qty = target_side * leverage * post_equity / price if target_side else 0.0
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
class WTLExecutionResult:
    config: WTLConfig
    raw: Any
    source_sha256: str
    entry_events: list[dict[str, Any]]
    leverage_events: list[dict[str, Any]]
    activation_counts: dict[str, int]
    rsi6: np.ndarray


def _capture_exact_source(context: Any) -> str:
    captured: dict[str, str] = {}
    original_compile = builtins.compile

    def capture(source: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(source, str) and "def v3_ma_only_backtest(" in source:
            captured["source"] = source
        return original_compile(source, *args, **kwargs)

    builtins.compile = capture
    try:
        context.confirmation.build_filtered_backtest(
            context.formation, context.engine, context.confirmation.MA_ONLY
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
        "    cooldown_left = 0\n    wtl_long_run = 0\n    wtl_short_run = 0\n    wtl_rsi_run = 0\n    wtl_entry_leverage = 1.0\n    bars_held = 0\n",
        "state initialization",
    )
    enter_nonlocal = (
        "        nonlocal entry_ts, entry_price, entry_equity, entry_side\n"
        "        nonlocal bars_held, stop_price, highest_close, lowest_close, mark_price\n"
    )
    source = _replace_once(
        source,
        enter_nonlocal,
        enter_nonlocal + "        nonlocal wtl_long_run, wtl_short_run, wtl_rsi_run, wtl_entry_leverage\n",
        "enter nonlocal",
    )
    source = _replace_once(
        source,
        "        before = equity\n        trade_to(config.side, price)\n",
        "        before = equity\n        wtl_set_entry_context(config.side, price, signal_index)\n        trade_to(config.side, price)\n        wtl_entry_leverage = wtl_last_entry_leverage()\n",
        "entry leverage",
    )
    source = _replace_once(
        source,
        "        mark_price = price\n\n    def settle_funding(",
        "        mark_price = price\n        wtl_long_run = 0\n        wtl_short_run = 0\n        wtl_rsi_run = 0\n\n    def settle_funding(",
        "entry reset",
    )
    close_nonlocal = (
        "        nonlocal entry_ts, entry_price, entry_equity, entry_side\n"
        "        nonlocal bars_held, stop_price, highest_close, lowest_close\n"
    )
    source = _replace_once(
        source,
        close_nonlocal,
        close_nonlocal + "        nonlocal wtl_long_run, wtl_short_run, wtl_rsi_run, wtl_entry_leverage\n",
        "close nonlocal",
    )
    source = _replace_once(
        source,
        '                "entry_price": entry_price,\n',
        '                "entry_price": entry_price,\n                "entry_leverage": wtl_entry_leverage,\n',
        "trade leverage",
    )
    source = _replace_once(
        source,
        "        highest_close = -math.inf\n        lowest_close = math.inf\n\n    for index in range(start_index, terminal_index + 1):",
        "        highest_close = -math.inf\n        lowest_close = math.inf\n        wtl_long_run = 0\n        wtl_short_run = 0\n        wtl_rsi_run = 0\n        wtl_entry_leverage = 1.0\n\n    for index in range(start_index, terminal_index + 1):",
        "close reset",
    )
    source = _replace_once(
        source,
        '                        "action": "terminal",\n',
        '                        "action": "terminal",\n                        "wtl_long_run": wtl_long_run,\n                        "wtl_short_run": wtl_short_run,\n                        "wtl_rsi_run": wtl_rsi_run,\n                        "wtl_entry_leverage": wtl_entry_leverage,\n',
        "terminal trace",
    )
    source = _replace_once(
        source,
        '                    "action": action,\n',
        '                    "action": action,\n                    "wtl_long_run": wtl_long_run,\n                    "wtl_short_run": wtl_short_run,\n                    "wtl_rsi_run": wtl_rsi_run,\n                    "wtl_entry_leverage": wtl_entry_leverage,\n',
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
            wtl_reason, wtl_long_run, wtl_short_run, wtl_rsi_run = (
                wtl_exit_decision(
                    side=side,
                    long_run=wtl_long_run,
                    short_run=wtl_short_run,
                    rsi_run=wtl_rsi_run,
                    long_exit=wtl_long_exit,
                    short_exit=wtl_short_exit,
                    short_rsi=wtl_short_rsi,
                    highest_close=highest_close,
                    lowest_close=lowest_close,
                    signal_close=float(book.close[decision_index]),
                    entry_price=entry_price,
                    atr=float(features.atr7[decision_index]),
                    rsi6=float(wtl_rsi6[decision_index]),
                    roundtrip_guard=wtl_roundtrip_guard,
                )
            )
            reason = wtl_reason or native_reason
"""
    return _replace_once(source, original, replacement, "lifecycle exits")


def build_variant_function(
    context: Any,
    config: WTLConfig,
    *,
    entry_signal: EntryQualitySignal,
    leverage_policy: LeveragePolicy,
    rsi6: np.ndarray,
) -> tuple[Callable[..., Any], str]:
    source = _capture_exact_source(context)
    function_name = f"wtl_{hashlib.sha256(config.arm_id.encode()).hexdigest()[:12]}_backtest"
    source = _replace_once(source, "def v3_ma_only_backtest(", f"def {function_name}(", "function name")
    source = _apply_state(source)
    source = _apply_exits(source)
    namespace = dict(context.engine.__dict__)
    namespace.update(
        {
            "close_entry_signal": entry_signal,
            "_target_quantity": leverage_policy,
            "wtl_set_entry_context": leverage_policy.set_entry_context,
            "wtl_last_entry_leverage": lambda: leverage_policy.last_entry_leverage,
            "wtl_rsi6": rsi6,
            "wtl_long_exit": config.long_exit,
            "wtl_short_exit": config.short_exit,
            "wtl_short_rsi": config.short_rsi,
            "wtl_roundtrip_guard": config.roundtrip_guard,
            "wtl_exit_decision": lifecycle_exit_decision,
        }
    )
    compiled = compile(source, f"<wtl-{config.arm_id}>", "exec")
    exec(compiled, namespace)
    return namespace[function_name], hashlib.sha256(source.encode()).hexdigest()


def run_variant(
    context: Any,
    config: WTLConfig,
    *,
    start_index: int,
    terminal_index: int,
    slippage: float = 0.0004,
    include_funding: bool = True,
    retain: bool = False,
    leverage_spec: LeverageSpec | None = None,
) -> WTLExecutionResult:
    rsi6 = wilder_rsi6(context.book.close)
    entry_signal = EntryQualitySignal(context.engine, config.entry)
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
        "entry_filter_pass": sum(event["event"] == "entry_filter_pass" for event in entry_signal.events),
        "entry_filter_reject": sum(event["event"] == "entry_filter_reject" for event in entry_signal.events),
        "long_trail_exit": sum(reason.startswith("long_mfe_") for reason in exits),
        "short_trail_exit": sum(reason.startswith("short_mfe_") for reason in exits),
        "short_rsi_exit": sum(reason == "short_rsi_take_profit" for reason in exits),
        "protective_stop": sum(reason == "protective_stop" for reason in exits),
        "leverage_entries": len(leverage_policy.events),
    }
    return WTLExecutionResult(
        config=config,
        raw=raw,
        source_sha256=source_hash,
        entry_events=list(entry_signal.events),
        leverage_events=list(leverage_policy.events),
        activation_counts=counts,
        rsi6=rsi6,
    )

