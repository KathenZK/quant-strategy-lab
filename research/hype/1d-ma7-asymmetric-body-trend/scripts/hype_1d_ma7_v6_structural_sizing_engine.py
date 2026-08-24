"""Frozen structural sizing overlays on exact HYPE 1D MA7 V6.

This post-reveal diagnostic engine keeps the exact-V6 signal, OAPP, PEHC,
execution, funding and cost ledger.  It adds only preregistered weak-signal
probe sizing, long confirmation, asymmetric cooldown and a causal ATR cap.
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
import pandas as pd


MEMORY_ENGINE_PATH = Path(__file__).with_name(
    "hype_1d_ma7_v6_rsi6_memory_cross_engine.py"
)
PROBE_LEVELS = (0.25, 0.50)
CONFIRM_DAYS = (2, 3)
VOLATILITY_CAP_ATR_PCT = 0.05


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_MEMORY = _load_module(MEMORY_ENGINE_PATH, "hype_v6_structural_memory")
_PEHC = _MEMORY._PEHC
_BASE = _MEMORY._BASE


@dataclass(frozen=True, slots=True)
class StructuralConfig:
    arm_id: str
    memory_long_enabled: bool = False
    memory_short_enabled: bool = False
    long_probe_leverage: float | None = None
    long_confirm_days: int = 0
    asymmetric_cooldown: bool = False
    short_probe_leverage: float | None = None
    volatility_cap_enabled: bool = False

    def __post_init__(self) -> None:
        if not self.arm_id:
            raise ValueError("arm_id is required")
        if self.long_probe_leverage is not None:
            if self.long_probe_leverage not in PROBE_LEVELS:
                raise ValueError("long probe leverage is outside the frozen set")
            if not self.memory_long_enabled or self.long_confirm_days not in CONFIRM_DAYS:
                raise ValueError("long probe requires memory long and 2d/3d confirmation")
        elif self.long_confirm_days != 0 or self.memory_long_enabled:
            raise ValueError("memory long requires a frozen probe rule")
        if self.short_probe_leverage is not None:
            if self.short_probe_leverage not in PROBE_LEVELS:
                raise ValueError("short probe leverage is outside the frozen set")
            if not self.memory_short_enabled:
                raise ValueError("short probe requires memory short")
        elif self.memory_short_enabled:
            raise ValueError("memory short requires a frozen probe leverage")

    def canonical(self) -> dict[str, Any]:
        return asdict(self)


def frozen_configs() -> list[StructuralConfig]:
    rows = [
        StructuralConfig("CTRL_EXACT_V6"),
        StructuralConfig(
            "A_LONG_P05_C2",
            memory_long_enabled=True,
            long_probe_leverage=0.50,
            long_confirm_days=2,
        ),
        StructuralConfig(
            "A_LONG_P025_C3",
            memory_long_enabled=True,
            long_probe_leverage=0.25,
            long_confirm_days=3,
        ),
        StructuralConfig("A_ASYM_CD", asymmetric_cooldown=True),
        StructuralConfig(
            "A_SHORT_P05",
            memory_short_enabled=True,
            short_probe_leverage=0.50,
        ),
        StructuralConfig(
            "A_SHORT_P025",
            memory_short_enabled=True,
            short_probe_leverage=0.25,
        ),
        StructuralConfig("A_VOL_CAP_5PCT", volatility_cap_enabled=True),
        StructuralConfig(
            "B_LONG_P05_C2_ASYM",
            memory_long_enabled=True,
            long_probe_leverage=0.50,
            long_confirm_days=2,
            asymmetric_cooldown=True,
        ),
        StructuralConfig(
            "B_LONG_P05_C2_ASYM_VOL",
            memory_long_enabled=True,
            long_probe_leverage=0.50,
            long_confirm_days=2,
            asymmetric_cooldown=True,
            volatility_cap_enabled=True,
        ),
        StructuralConfig(
            "B_CONSERVATIVE_ALL",
            memory_long_enabled=True,
            memory_short_enabled=True,
            long_probe_leverage=0.50,
            long_confirm_days=2,
            asymmetric_cooldown=True,
            short_probe_leverage=0.25,
            volatility_cap_enabled=True,
        ),
    ]
    if len(rows) != 10 or len({row.arm_id for row in rows}) != 10:
        raise RuntimeError("frozen structural arm cardinality drift")
    return rows


def config_sha256(config: StructuralConfig) -> str:
    encoded = json.dumps(
        config.canonical(), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


class ClassifiedMemorySignal(_MEMORY.RSIMemoryCrossSignal):
    """Exact native OR RSI-memory signal with causal per-call attribution."""

    def __init__(self, native_signal: Any, config: Any, rsi6: np.ndarray) -> None:
        super().__init__(native_signal, config, rsi6)
        self.classifications: dict[tuple[int, int], dict[str, bool]] = {}

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
        self.classifications[key] = {
            "native": native,
            "memory": bool(memory),
            "memory_only": bool(memory and not native),
        }
        result = bool(native or memory)
        self.cache[key] = result
        return result


class StructuralLeveragePolicy:
    """Entry-aware target quantity policy capped at one times equity."""

    def __init__(
        self,
        context: Any,
        config: StructuralConfig,
        signal: ClassifiedMemorySignal,
    ) -> None:
        self.context = context
        self.config = config
        self.signal = signal
        self.pending_leverage = 1.0
        self.last_entry_leverage = 1.0
        self.last_entry_is_probe = False
        self.events: list[dict[str, Any]] = []

    def _volatility_cap(self, price: float, signal_index: int) -> tuple[float, float]:
        atr = float(self.context.features.atr7[signal_index])
        atr_pct = atr / price if math.isfinite(atr) and atr > 0.0 and price > 0.0 else math.nan
        if not self.config.volatility_cap_enabled or not math.isfinite(atr_pct):
            return 1.0, atr_pct
        cap = max(0.50, min(1.0, VOLATILITY_CAP_ATR_PCT / atr_pct))
        return float(cap), float(atr_pct)

    def set_entry_context(
        self,
        side: int,
        price: float,
        signal_index: int,
        origin: str,
    ) -> None:
        classification = self.signal.classifications.get(
            (int(signal_index), int(side)),
            {"native": False, "memory": False, "memory_only": False},
        )
        memory_only = bool(origin == "natural" and classification["memory_only"])
        target = 1.0
        if memory_only and side > 0 and self.config.long_probe_leverage is not None:
            target = self.config.long_probe_leverage
        elif memory_only and side < 0 and self.config.short_probe_leverage is not None:
            target = self.config.short_probe_leverage
        cap, atr_pct = self._volatility_cap(price, signal_index)
        target = min(target, cap)
        self.pending_leverage = float(target)
        self.last_entry_leverage = float(target)
        self.last_entry_is_probe = bool(memory_only and target < 1.0)
        self.events.append(
            {
                "event": "structural_entry_target",
                "side": "long" if side > 0 else "short",
                "origin": origin,
                "signal_index": int(signal_index),
                "price": float(price),
                "native": bool(classification["native"]),
                "memory": bool(classification["memory"]),
                "memory_only": memory_only,
                "target_leverage": float(target),
                "volatility_cap": cap,
                "atr7_pct": atr_pct,
                "volatility_capped": bool(cap < 1.0 and target == cap),
            }
        )

    def set_promotion_context(self, price: float, signal_index: int) -> None:
        cap, atr_pct = self._volatility_cap(price, signal_index)
        self.pending_leverage = cap
        self.events.append(
            {
                "event": "long_probe_promotion_target",
                "signal_index": int(signal_index),
                "price": float(price),
                "target_leverage": cap,
                "atr7_pct": atr_pct,
                "volatility_capped": bool(cap < 1.0),
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
        if not 0.0 < leverage <= 1.0:
            raise RuntimeError("structural leverage outside (0, 1]")
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


class StructuralRecorder:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def __call__(self, event: dict[str, Any]) -> None:
        self.events.append(dict(event))


@dataclass(slots=True)
class StructuralExecutionResult:
    config: StructuralConfig
    raw: Any
    source_sha256: str
    memory_events: list[dict[str, Any]]
    leverage_events: list[dict[str, Any]]
    structural_events: list[dict[str, Any]]
    handoff_events: list[dict[str, Any]]
    activation_counts: dict[str, int]
    rsi6: np.ndarray


@dataclass(frozen=True, slots=True)
class StructuralReplayResult:
    terminal_equity: float
    chronological_1h_mdd_pct: float
    worst_ts: str | None
    turnover_multiple: float
    cost_equity_units: float
    funding_equity_units: float
    max_marked_leverage: float
    promotion_count: int
    parity: dict[str, bool]


def probe_confirmation(
    *, side: int, close: float, ma7: float, previous_ma7: float, atr7: float
) -> dict[str, Any]:
    finite = all(math.isfinite(value) for value in (close, ma7, previous_ma7, atr7)) and atr7 > 0.0
    directional_slope = side * (ma7 - previous_ma7) / atr7 if finite else math.nan
    regime_pass = finite and (close > ma7 if side > 0 else close < ma7)
    slope_pass = (
        finite
        and directional_slope > 0.02
        and not math.isclose(directional_slope, 0.02, rel_tol=0.0, abs_tol=1e-12)
    )
    return {
        "passed": bool(regime_pass and slope_pass),
        "finite": bool(finite),
        "regime_pass": bool(regime_pass),
        "slope_atr": float(directional_slope),
        "slope_pass": bool(slope_pass),
    }


def _replace_once(source: str, old: str, new: str, label: str) -> str:
    return _BASE._replace_once(source, old, new, label)


def _apply_structural_state(source: str) -> str:
    source = _replace_once(
        source,
        "    pehc_entry_start_hour = 0\n\n    def trade_to(\n",
        """    pehc_entry_start_hour = 0
    struct_probe_active = False
    struct_trade_was_probe = False
    struct_trade_promoted = False
    struct_probe_origin_signal_index = -1
    struct_last_exit_side = 0
    struct_entry_origin = "natural"

    def trade_to(
""",
        "structural state initialization",
    )
    source = _replace_once(
        source,
        "        nonlocal pehc_pending_origin_index\n",
        "        nonlocal pehc_pending_origin_index\n"
        "        nonlocal struct_probe_active, struct_trade_was_probe\n"
        "        nonlocal struct_trade_promoted, struct_probe_origin_signal_index\n",
        "structural enter nonlocal",
    )
    source = _replace_once(
        source,
        "        wtl_set_entry_context(config.side, price, signal_index)\n",
        "        wtl_set_entry_context(config.side, price, signal_index, struct_entry_origin)\n",
        "structural entry origin",
    )
    source = _replace_once(
        source,
        "        wtl_entry_leverage = wtl_last_entry_leverage()\n        entry_ts = ts\n",
        """        wtl_entry_leverage = wtl_last_entry_leverage()
        struct_trade_was_probe = struct_last_entry_is_probe()
        struct_probe_active = bool(
            struct_trade_was_probe
            and config.side > 0
            and struct_long_confirm_days > 0
        )
        struct_trade_promoted = False
        struct_probe_origin_signal_index = int(signal_index)
        entry_ts = ts
""",
        "structural probe entry state",
    )
    source = _replace_once(
        source,
        "        nonlocal wtl_long_run, wtl_short_run, wtl_rsi_run, wtl_entry_leverage\n        if entry_ts is None:\n",
        "        nonlocal wtl_long_run, wtl_short_run, wtl_rsi_run, wtl_entry_leverage\n"
        "        nonlocal struct_probe_active, struct_trade_was_probe\n"
        "        nonlocal struct_trade_promoted, struct_probe_origin_signal_index\n"
        "        nonlocal struct_last_exit_side\n"
        "        if entry_ts is None:\n",
        "structural close nonlocal",
    )
    source = _replace_once(
        source,
        "        old_side = entry_side\n        trade_to(0, price)\n",
        "        old_side = entry_side\n        struct_last_exit_side = int(old_side)\n        trade_to(0, price)\n",
        "structural last exit side",
    )
    source = _replace_once(
        source,
        '                "entry_leverage": wtl_entry_leverage,\n',
        '                "entry_leverage": wtl_entry_leverage,\n'
        '                "structural_probe": struct_trade_was_probe,\n'
        '                "structural_promoted": struct_trade_promoted,\n',
        "structural trade attribution",
    )
    source = _replace_once(
        source,
        "        wtl_entry_leverage = 1.0\n\n    for index in range(start_index, terminal_index + 1):",
        """        wtl_entry_leverage = 1.0
        struct_probe_active = False
        struct_trade_was_probe = False
        struct_trade_promoted = False
        struct_probe_origin_signal_index = -1

    for index in range(start_index, terminal_index + 1):""",
        "structural close reset",
    )
    return source


def _apply_entry_origins(source: str) -> str:
    source = _replace_once(
        source,
        "        decision_index = index - 1 - signal_lag\n",
        '        decision_index = index - 1 - signal_lag\n        struct_entry_origin = "natural"\n',
        "daily origin reset",
    )
    source = _replace_once(
        source,
        "            if reversal_allowed:\n                enter(\n",
        '            if reversal_allowed:\n                struct_entry_origin = "forced_reversal"\n                enter(\n',
        "forced reversal origin",
    )
    source = _replace_once(
        source,
        "            else:\n                enter(short_config, ts, current_open, index, signal_index)\n",
        '            else:\n                struct_entry_origin = "pehc_handoff"\n                enter(short_config, ts, current_open, index, signal_index)\n',
        "pending PEHC origin",
    )
    source = _replace_once(
        source,
        "                        else:\n                            enter(\n                                short_config,\n",
        '                        else:\n                            struct_entry_origin = "pehc_handoff"\n                            enter(\n                                short_config,\n',
        "intraday PEHC origin",
    )
    return source


def _apply_probe_decision(source: str) -> str:
    marker = "        if pehc_shadow_active and index > pehc_shadow_origin_index:\n"
    block = """        if (
            side > 0
            and struct_probe_active
            and decision_index > struct_probe_origin_signal_index
            and index < terminal_index
        ):
            probe_age = int(decision_index - struct_probe_origin_signal_index)
            confirmation = struct_probe_confirmation(
                side=side,
                close=float(book.close[decision_index]),
                ma7=float(features.ma7[decision_index]),
                previous_ma7=(
                    float(features.ma7[decision_index - 1])
                    if decision_index >= 1
                    else math.nan
                ),
                atr7=float(features.atr7[decision_index]),
            )
            struct_record({
                "event": "long_probe_confirmation_check",
                "index": int(index),
                "ts": ts.isoformat(),
                "signal_index": int(decision_index),
                "age_days": probe_age,
                **confirmation,
            })
            if confirmation["passed"]:
                struct_set_promotion_context(current_open, decision_index)
                trade_to(side, current_open)
                struct_probe_active = False
                struct_trade_promoted = True
                action = "long_probe_promoted"
                struct_record({
                    "event": "long_probe_promoted",
                    "index": int(index),
                    "ts": ts.isoformat(),
                    "signal_index": int(decision_index),
                    "age_days": probe_age,
                })
            elif probe_age >= struct_long_confirm_days:
                close(ts, current_open, "probe_confirmation_expired", index)
                cooldown_left = long_config.cooldown_days
                exited_at_open = True
                action = "probe_confirmation_expired"
                struct_record({
                    "event": "long_probe_expired",
                    "index": int(index),
                    "ts": ts.isoformat(),
                    "signal_index": int(decision_index),
                    "age_days": probe_age,
                })

"""
    return _replace_once(source, marker, block + marker, "probe confirmation block")


def _apply_asymmetric_cooldown(source: str) -> str:
    original = """        if index < terminal_index and side == 0:
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
    replacement = """        if index < terminal_index and side == 0:
            selected: Config | None = None
            signal_index = max(0, decision_index)
            if cooldown_left > 0:
                if (
                    struct_asymmetric_cooldown
                    and struct_last_exit_side < 0
                    and long_config is not None
                    and close_entry_signal(
                        long_config,
                        book,
                        features,
                        signal_index,
                    )
                ):
                    selected = long_config
                    cooldown_left = 0
                    struct_record({
                        "event": "short_cooldown_long_override",
                        "index": int(index),
                        "ts": ts.isoformat(),
                        "signal_index": int(signal_index),
                    })
                elif not exited_at_open:
                    cooldown_left -= 1
            else:
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
                struct_entry_origin = "natural"
                enter(selected, fill_ts, fill_price, index, signal_index)
                action = "enter_long" if selected.side > 0 else "enter_short"
"""
    return _replace_once(source, original, replacement, "asymmetric cooldown")


def _apply_structural_trace(source: str) -> str:
    source = _replace_once(
        source,
        '                        "wtl_entry_leverage": wtl_entry_leverage,\n'
        "                    }\n",
        '                        "wtl_entry_leverage": wtl_entry_leverage,\n'
        '                        "struct_probe_active": struct_probe_active,\n'
        '                        "struct_trade_was_probe": struct_trade_was_probe,\n'
        '                        "struct_trade_promoted": struct_trade_promoted,\n'
        '                        "struct_last_exit_side": struct_last_exit_side,\n'
        "                    }\n",
        "structural terminal trace",
    )
    source = _replace_once(
        source,
        '                    "wtl_entry_leverage": wtl_entry_leverage,\n'
        "                }\n",
        '                    "wtl_entry_leverage": wtl_entry_leverage,\n'
        '                    "struct_probe_active": struct_probe_active,\n'
        '                    "struct_trade_was_probe": struct_trade_was_probe,\n'
        '                    "struct_trade_promoted": struct_trade_promoted,\n'
        '                    "struct_last_exit_side": struct_last_exit_side,\n'
        "                }\n",
        "structural daily trace",
    )
    return source


def build_variant_function(
    context: Any,
    config: StructuralConfig,
    *,
    entry_signal: ClassifiedMemorySignal,
    leverage_policy: StructuralLeveragePolicy,
    rsi6: np.ndarray,
    pehc_recorder: Any,
    structural_recorder: StructuralRecorder,
) -> tuple[Callable[..., Any], str]:
    pehc_config = _MEMORY.fixed_v6_config()
    oapp_config = _PEHC.fixed_oapp_config(short_rsi_enabled=True)
    source = _BASE._capture_exact_source(context)
    function_name = f"struct_{hashlib.sha256(config.arm_id.encode()).hexdigest()[:12]}_backtest"
    source = _replace_once(
        source, "def v3_ma_only_backtest(", f"def {function_name}(", "function name"
    )
    source = _BASE._apply_state(source)
    source = _BASE._apply_exits(source)
    source = _PEHC._apply_pehc_state(source)
    source = _PEHC._apply_pehc_arm(source)
    source = _PEHC._apply_pehc_daily(source)
    source = _PEHC._apply_pehc_intraday(source)
    source = _apply_structural_state(source)
    source = _apply_entry_origins(source)
    source = _apply_probe_decision(source)
    source = _apply_asymmetric_cooldown(source)
    source = _apply_structural_trace(source)
    namespace = dict(context.engine.__dict__)
    namespace.update(
        {
            "close_entry_signal": entry_signal,
            "_target_quantity": leverage_policy,
            "wtl_set_entry_context": leverage_policy.set_entry_context,
            "wtl_last_entry_leverage": lambda: leverage_policy.last_entry_leverage,
            "struct_last_entry_is_probe": lambda: leverage_policy.last_entry_is_probe,
            "struct_set_promotion_context": leverage_policy.set_promotion_context,
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
            "struct_long_confirm_days": config.long_confirm_days,
            "struct_asymmetric_cooldown": config.asymmetric_cooldown,
            "struct_probe_confirmation": probe_confirmation,
            "struct_record": structural_recorder,
        }
    )
    compiled = compile(source, f"<structural-{config.arm_id}>", "exec")
    exec(compiled, namespace)
    return namespace[function_name], hashlib.sha256(source.encode()).hexdigest()


def _activation_counts(
    raw: Any,
    memory_events: list[dict[str, Any]],
    leverage_events: list[dict[str, Any]],
    structural_events: list[dict[str, Any]],
    handoff_events: list[dict[str, Any]],
) -> dict[str, int]:
    return {
        "memory_long_pass": sum(
            row.get("event") == "rsi_memory_cross_pass" and row.get("side") == "long"
            for row in memory_events
        ),
        "memory_short_pass": sum(
            row.get("event") == "rsi_memory_cross_pass" and row.get("side") == "short"
            for row in memory_events
        ),
        "long_probe_entries": sum(
            row.get("event") == "structural_entry_target"
            and row.get("side") == "long"
            and row.get("memory_only")
            for row in leverage_events
        ),
        "short_probe_entries": sum(
            row.get("event") == "structural_entry_target"
            and row.get("side") == "short"
            and row.get("memory_only")
            for row in leverage_events
        ),
        "volatility_capped_entries": sum(
            row.get("event") == "structural_entry_target" and row.get("volatility_capped")
            for row in leverage_events
        ),
        "volatility_capped_promotions": sum(
            row.get("event") == "long_probe_promotion_target" and row.get("volatility_capped")
            for row in leverage_events
        ),
        "long_probe_checks": sum(
            row.get("event") == "long_probe_confirmation_check" for row in structural_events
        ),
        "long_probe_promotions": sum(
            row.get("event") == "long_probe_promoted" for row in structural_events
        ),
        "long_probe_expiries": sum(
            row.get("event") == "long_probe_expired" for row in structural_events
        ),
        "short_cooldown_long_overrides": sum(
            row.get("event") == "short_cooldown_long_override" for row in structural_events
        ),
        "handoff_accepts": sum(row.get("event") == "handoff_accept" for row in handoff_events),
        "trade_count": len(raw.trades),
    }


def run_variant(
    context: Any,
    config: StructuralConfig,
    *,
    start_index: int,
    terminal_index: int,
    slippage: float = 0.0004,
    include_funding: bool = True,
    retain: bool = False,
) -> StructuralExecutionResult:
    if not 0 <= start_index < terminal_index <= context.book.count:
        raise ValueError("invalid structural window")
    rsi6 = _BASE.wilder_rsi6(context.book.close)
    oapp_config = _PEHC.fixed_oapp_config(short_rsi_enabled=True)
    native_signal = _BASE.EntryQualitySignal(context.engine, oapp_config.entry)
    memory_config = _MEMORY.RSIMemoryCrossConfig(
        arm_id=config.arm_id,
        window_mode="PRIOR5",
        long_enabled=config.memory_long_enabled,
        short_enabled=config.memory_short_enabled,
        native_enabled=True,
    )
    entry_signal = ClassifiedMemorySignal(native_signal, memory_config, rsi6)
    leverage_policy = StructuralLeveragePolicy(context, config, entry_signal)
    pehc_recorder = _PEHC.HandoffRecorder()
    structural_recorder = StructuralRecorder()
    function, source_hash = build_variant_function(
        context,
        config,
        entry_signal=entry_signal,
        leverage_policy=leverage_policy,
        rsi6=rsi6,
        pehc_recorder=pehc_recorder,
        structural_recorder=structural_recorder,
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
    leverage_events = list(leverage_policy.events)
    structural_events = list(structural_recorder.events)
    handoff_events = list(pehc_recorder.events)
    return StructuralExecutionResult(
        config=config,
        raw=raw,
        source_sha256=source_hash,
        memory_events=memory_events,
        leverage_events=leverage_events,
        structural_events=structural_events,
        handoff_events=handoff_events,
        activation_counts=_activation_counts(
            raw,
            memory_events,
            leverage_events,
            structural_events,
            handoff_events,
        ),
        rsi6=rsi6,
    )


def replay_structural_chronological_1h(
    context: Any,
    result: StructuralExecutionResult,
    *,
    slippage: float = 0.0004,
    include_funding: bool = True,
    tolerance: float = 2e-10,
) -> StructuralReplayResult:
    """Replay entry, promotion, funding and exit events on ordered 1h opens."""

    cost_rate = float(context.engine.FEE) + float(slippage)
    hourly: list[tuple[pd.Timestamp, float]] = []
    for index, day in enumerate(context.book.ts):
        day_ts = pd.Timestamp(day)
        for hour in range(24):
            price = float(context.features.hourly_open[index, hour])
            if not math.isfinite(price) or price <= 0.0:
                raise RuntimeError("nonfinite hourly open in frozen market")
            hourly.append((day_ts + pd.Timedelta(hours=hour), price))
    funding = (
        sorted(
            [event for daily in context.features.funding_events for event in daily],
            key=lambda event: pd.Timestamp(event.ts),
        )
        if include_funding
        else []
    )
    promoted = [
        row for row in result.structural_events if row.get("event") == "long_probe_promoted"
    ]
    promotion_targets = [
        row
        for row in result.leverage_events
        if row.get("event") == "long_probe_promotion_target"
    ]
    if len(promoted) != len(promotion_targets):
        raise RuntimeError("promotion event/target cardinality drift")
    promotions = []
    for event, target in zip(promoted, promotion_targets, strict=True):
        event_ts = pd.Timestamp(event["ts"])
        if int(event["signal_index"]) != int(target["signal_index"]):
            raise RuntimeError("promotion signal index drift")
        promotions.append(
            {
                "ts": event_ts,
                "price": float(target["price"]),
                "target_leverage": float(target["target_leverage"]),
            }
        )

    equity = 1.0
    peak = 1.0
    mdd = 0.0
    worst_ts: str | None = None
    total_turnover = 0.0
    total_cost = 0.0
    total_funding = 0.0
    max_leverage = 0.0
    used_promotions = 0

    def observe(ts: pd.Timestamp, marked: float, qty: float, price: float) -> None:
        nonlocal peak, mdd, worst_ts, max_leverage
        if not math.isfinite(marked):
            raise RuntimeError("nonfinite structural replay equity")
        peak = max(peak, marked)
        drawdown = -1.0 if marked <= 0.0 else marked / peak - 1.0
        if drawdown < mdd:
            mdd = drawdown
            worst_ts = ts.isoformat()
        if marked > 0.0:
            max_leverage = max(max_leverage, abs(qty) * price / marked)
        if marked <= 0.0:
            raise RuntimeError("structural chronological replay bankruptcy")

    previous_exit: pd.Timestamp | None = None
    for trade_index, trade in enumerate(result.raw.trades):
        entry_ts = pd.Timestamp(trade["entry_ts"])
        exit_ts = pd.Timestamp(trade["exit_ts"])
        if entry_ts > exit_ts or (previous_exit is not None and entry_ts < previous_exit):
            raise RuntimeError("invalid structural trade ordering")
        side = 1 if str(trade["side"]) == "long" else -1
        entry_price = float(trade["entry_price"])
        exit_price = float(trade["exit_price"])
        entry_leverage = float(trade.get("entry_leverage", 1.0))
        entry_equity = equity
        entry_policy = SimpleTargetPolicy(entry_leverage)
        qty, equity, turnover = entry_policy(
            equity, 0.0, side, entry_price, cost_rate
        )
        total_turnover += turnover
        total_cost += entry_equity - equity
        mark_price = entry_price
        observe(entry_ts, entry_equity, 0.0, entry_price)
        observe(entry_ts, equity, qty, entry_price)
        event_rows: list[tuple[pd.Timestamp, int, str, float, Any]] = []
        for event_ts, price in hourly:
            if entry_ts < event_ts < exit_ts:
                event_rows.append((event_ts, 0, "hourly", price, None))
        for event in funding:
            event_ts = pd.Timestamp(event.ts)
            if entry_ts <= event_ts < exit_ts:
                event_rows.append((event_ts, 2, "funding", float(event.price), event))
        for promotion in promotions:
            event_ts = promotion["ts"]
            if entry_ts < event_ts < exit_ts:
                event_rows.append((event_ts, 1, "promotion", promotion["price"], promotion))
        event_rows.sort(key=lambda row: (row[0], row[1]))
        for event_ts, _priority, kind, price, event in event_rows:
            equity += qty * (price - mark_price)
            mark_price = price
            observe(event_ts, equity, qty, price)
            if kind == "funding":
                payment = qty * price * float(event.rate)
                equity -= payment
                total_funding += payment
                observe(event_ts, equity, qty, price)
            elif kind == "promotion":
                old_equity = equity
                policy = SimpleTargetPolicy(float(event["target_leverage"]))
                qty, equity, turnover = policy(
                    equity, qty, side, price, cost_rate
                )
                total_turnover += turnover
                total_cost += old_equity - equity
                used_promotions += 1
                observe(event_ts, equity, qty, price)
        equity += qty * (exit_price - mark_price)
        observe(exit_ts, equity, qty, exit_price)
        old_equity = equity
        policy = SimpleTargetPolicy(1.0)
        qty, equity, turnover = policy(equity, qty, 0, exit_price, cost_rate)
        total_turnover += turnover
        total_cost += old_equity - equity
        observe(exit_ts, equity, qty, exit_price)
        expected_equity = entry_equity + float(trade["net_pnl"])
        if not math.isclose(equity, expected_equity, rel_tol=tolerance, abs_tol=tolerance):
            raise RuntimeError(
                f"trade {trade_index} structural replay drift: {equity} != {expected_equity}"
            )
        previous_exit = exit_ts

    metrics = result.raw.metrics
    parity = {
        "terminal_equity": math.isclose(
            equity, float(metrics["equity_multiple"]), rel_tol=tolerance, abs_tol=tolerance
        ),
        "turnover": math.isclose(
            total_turnover,
            float(metrics["turnover_multiple"]),
            rel_tol=tolerance,
            abs_tol=tolerance,
        ),
        "cost": math.isclose(
            total_cost,
            float(metrics["cost_pct_initial"]) / 100.0,
            rel_tol=tolerance,
            abs_tol=tolerance,
        ),
        "funding": math.isclose(
            total_funding,
            float(metrics["funding_pct_initial"]) / 100.0,
            rel_tol=tolerance,
            abs_tol=tolerance,
        ),
        "trade_count": len(result.raw.trades) == int(metrics["closed_trades"]),
        "promotion_count": used_promotions == len(promotions),
    }
    if not all(parity.values()):
        raise RuntimeError(f"structural chronological ledger parity failed: {parity}")
    return StructuralReplayResult(
        terminal_equity=float(equity),
        chronological_1h_mdd_pct=float(mdd * 100.0),
        worst_ts=worst_ts,
        turnover_multiple=float(total_turnover),
        cost_equity_units=float(total_cost),
        funding_equity_units=float(total_funding),
        max_marked_leverage=float(max_leverage),
        promotion_count=int(used_promotions),
        parity=parity,
    )


class SimpleTargetPolicy:
    """Minimal target-quantity policy used by the independent risk replay."""

    def __init__(self, leverage: float) -> None:
        self.leverage = leverage

    def __call__(
        self,
        equity: float,
        old_qty: float,
        target_side: int,
        price: float,
        cost_rate: float,
    ) -> tuple[float, float, float]:
        leverage = self.leverage if target_side else 1.0
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
        return float(target_qty), float(post_equity), float(turnover)


def run_exact_v6(
    context: Any,
    *,
    start_index: int,
    terminal_index: int,
    slippage: float = 0.0004,
    include_funding: bool = True,
    retain: bool = False,
) -> Any:
    return _MEMORY.run_v6(
        context,
        start_index=start_index,
        terminal_index=terminal_index,
        slippage=slippage,
        include_funding=include_funding,
        retain=retain,
    )
