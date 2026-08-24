"""Independent PEHC shadow-handoff engine built from the exact-V4 source.

The engine keeps the frozen OAPP profit exits in the funded ledger, while a
quantity-free shadow continues the original long's exact-V4 stop state.  A
short handoff can only be created by the shadow stop event that exact V4 would
have used for a forced reversal.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from itertools import product
import math
from pathlib import Path
from typing import Any, Callable

import numpy as np

import importlib.util
import sys


OAPP_PATH = Path(__file__).with_name(
    "hype_1d_ma7_opportunity_aware_profit_protection_engine.py"
)


def _load_oapp() -> Any:
    spec = importlib.util.spec_from_file_location("hype_pehc_oapp_engine", OAPP_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {OAPP_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_OAPP = _load_oapp()
_BASE = _OAPP._BASE

EXPIRY_DAYS = (1, 2, 3, 5, 8, 13, 21)
SLOPE_THRESHOLDS: tuple[float | None, ...] = (None, 0.0, 0.01, 0.02, 0.04)
CHASE_CAPS = (0.25, 0.50, 0.75, 1.00, 1.50, 2.00, math.inf)
EXECUTIONS = ("same_1h_open", "next_utc_open")


@dataclass(frozen=True, slots=True)
class PEHCConfig:
    arm_id: str
    expiry_days: int = 3
    slope_threshold: float | None = None
    chase_cap_atr: float = math.inf
    execution: str = "same_1h_open"
    enabled: bool = True
    entry_enabled: bool = True
    blocked_origin_indices: tuple[int, ...] = ()
    allowed_origin_indices: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if self.expiry_days not in EXPIRY_DAYS:
            raise ValueError("expiry_days is outside the frozen PEHC grid")
        if self.slope_threshold not in SLOPE_THRESHOLDS:
            raise ValueError("slope_threshold is outside the frozen PEHC grid")
        if self.chase_cap_atr not in CHASE_CAPS:
            raise ValueError("chase_cap_atr is outside the frozen PEHC grid")
        if self.execution not in EXECUTIONS:
            raise ValueError("unknown PEHC execution timing")
        if any(index < 0 for index in self.blocked_origin_indices):
            raise ValueError("blocked origin indices must be nonnegative")
        if any(index < 0 for index in self.allowed_origin_indices):
            raise ValueError("allowed origin indices must be nonnegative")
        if set(self.blocked_origin_indices) & set(self.allowed_origin_indices):
            raise ValueError("an origin cannot be both blocked and allowed")

    def canonical(self) -> dict[str, Any]:
        row = asdict(self)
        if math.isinf(self.chase_cap_atr):
            row["chase_cap_atr"] = "INF"
        return row


def config_sha256(config: PEHCConfig) -> str:
    import json

    payload = json.dumps(
        config.canonical(), sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def grid_configs() -> list[PEHCConfig]:
    rows: list[PEHCConfig] = []
    for index, values in enumerate(
        product(EXPIRY_DAYS, SLOPE_THRESHOLDS, CHASE_CAPS, EXECUTIONS), 1
    ):
        expiry, slope, chase, execution = values
        rows.append(
            PEHCConfig(
                arm_id=f"PEHC_{index:03d}",
                expiry_days=expiry,
                slope_threshold=slope,
                chase_cap_atr=chase,
                execution=execution,
            )
        )
    if len(rows) != 490:
        raise RuntimeError("frozen PEHC grid cardinality drift")
    return rows


def fixed_oapp_config(*, short_rsi_enabled: bool = True) -> Any:
    return _OAPP.WTLConfig(
        "PEHC_FIXED_OAPP",
        long_exit=_OAPP.TrailExit("fraction", 0.5, 0.10, 2),
        short_rsi=(
            _OAPP.ShortRSIExit(20.0, 2)
            if short_rsi_enabled
            else _OAPP.ShortRSIExit()
        ),
    )


def handoff_eligibility(
    *,
    price: float,
    ma7: float,
    previous_ma7: float,
    atr7: float,
    slope_threshold: float | None,
    chase_cap_atr: float,
) -> dict[str, Any]:
    values = (price, ma7, atr7)
    finite = all(math.isfinite(value) for value in values) and atr7 > 0.0
    ma_pass = finite and price < ma7
    chase = (ma7 - price) / atr7 if finite else math.nan
    chase_pass = ma_pass and chase < chase_cap_atr
    if slope_threshold is None:
        slope = None
        slope_pass = True
    else:
        slope_finite = finite and math.isfinite(previous_ma7)
        slope = -(ma7 - previous_ma7) / atr7 if slope_finite else math.nan
        slope_pass = slope_finite and slope > slope_threshold
    passed = finite and ma_pass and chase_pass and slope_pass
    return {
        "passed": bool(passed),
        "finite": bool(finite),
        "ma_pass": bool(ma_pass),
        "chase_atr": chase,
        "chase_pass": bool(chase_pass),
        "slope_atr": slope,
        "slope_pass": bool(slope_pass),
    }


class HandoffRecorder:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def __call__(self, event: dict[str, Any]) -> None:
        self.events.append(dict(event))


@dataclass(slots=True)
class PEHCExecutionResult:
    config: PEHCConfig
    raw: Any
    source_sha256: str
    entry_events: list[dict[str, Any]]
    leverage_events: list[dict[str, Any]]
    handoff_events: list[dict[str, Any]]
    activation_counts: dict[str, int]
    rsi6: np.ndarray


def _replace_once(source: str, old: str, new: str, label: str) -> str:
    return _BASE._replace_once(source, old, new, label)


def _apply_pehc_state(source: str) -> str:
    source = _replace_once(
        source,
        "    bankrupt = False\n    pending_short_reversal = False\n\n    def trade_to(",
        """\
    bankrupt = False
    pending_short_reversal = False
    pehc_shadow_active = False
    pehc_shadow_origin_index = -1
    pehc_shadow_entry_ts = None
    pehc_shadow_entry_price = math.nan
    pehc_shadow_stop_price = math.nan
    pehc_shadow_highest_close = -math.inf
    pehc_shadow_bars_held = 0
    pehc_pending_kind = None
    pehc_pending_due_index = -1
    pehc_pending_origin_index = -1
    pehc_entry_start_hour = 0

    def trade_to(
""",
        "PEHC state initialization",
    )
    marker = (
        "        nonlocal bars_held, stop_price, highest_close, lowest_close, mark_price\n"
        "        nonlocal wtl_long_run, wtl_short_run, wtl_rsi_run, wtl_entry_leverage\n"
    )
    source = _replace_once(
        source,
        marker,
        marker
        + "        nonlocal pehc_shadow_active, pehc_pending_kind, pehc_pending_due_index\n"
        + "        nonlocal pehc_pending_origin_index\n",
        "PEHC enter nonlocal",
    )
    source = _replace_once(
        source,
        "        wtl_rsi_run = 0\n\n    def settle_funding(",
        """\
        wtl_rsi_run = 0
        if config.side > 0 and pehc_shadow_active:
            pehc_record({
                "event": "shadow_cancel_actual_new_long",
                "index": int(index),
                "ts": ts.isoformat(),
                "origin_index": int(pehc_shadow_origin_index),
            })
            pehc_shadow_active = False
            pehc_pending_kind = None
            pehc_pending_due_index = -1
            pehc_pending_origin_index = -1

    def settle_funding(""",
        "PEHC actual-long cancellation",
    )
    return source


def _apply_pehc_arm(source: str) -> str:
    source = _replace_once(
        source,
        "            reason = wtl_reason or native_reason\n",
        """\
            reason = wtl_reason or native_reason
            if (
                pehc_enabled
                and wtl_reason == "long_mfe_fraction_trail_exit"
                and not native_reason
            ):
                if pehc_shadow_active:
                    pehc_record({
                        "event": "shadow_start_rejected_already_active",
                        "index": int(index),
                        "ts": ts.isoformat(),
                        "origin_index": int(pehc_shadow_origin_index),
                    })
                else:
                    pehc_shadow_active = True
                    pehc_shadow_origin_index = int(index)
                    pehc_shadow_entry_ts = entry_ts
                    pehc_shadow_entry_price = float(entry_price)
                    pehc_shadow_stop_price = float(stop_price)
                    pehc_shadow_highest_close = float(highest_close)
                    pehc_shadow_bars_held = int(bars_held)
                    pehc_record({
                        "event": "shadow_start",
                        "index": int(index),
                        "ts": ts.isoformat(),
                        "origin_index": int(index),
                        "entry_ts": entry_ts.isoformat() if entry_ts is not None else None,
                        "entry_price": float(entry_price),
                        "stop_price": float(stop_price),
                        "highest_close": float(highest_close),
                        "bars_held": int(bars_held),
                    })
            elif pehc_enabled and wtl_reason == "long_mfe_fraction_trail_exit":
                pehc_record({
                    "event": "shadow_start_blocked_native_exit",
                    "index": int(index),
                    "ts": ts.isoformat(),
                    "native_reason": native_reason,
                })
""",
        "PEHC shadow arm",
    )
    return source


def _apply_pehc_daily(source: str) -> str:
    source = _replace_once(
        source,
        "        entered_pending_reversal = False\n        decision_index = index - 1 - signal_lag\n",
        """\
        entered_pending_reversal = False
        pehc_entry_start_hour = 0
        decision_index = index - 1 - signal_lag
        if (
            pehc_pending_kind is not None
            and index == pehc_pending_due_index
            and index < terminal_index
        ):
            pending_kind = pehc_pending_kind
            pending_origin = pehc_pending_origin_index
            pehc_pending_kind = None
            pehc_pending_due_index = -1
            pehc_pending_origin_index = -1
            signal_index = max(0, decision_index)
            eligibility = pehc_handoff_eligibility(
                price=current_open,
                ma7=float(features.ma7[signal_index]),
                previous_ma7=(
                    float(features.ma7[signal_index - 1])
                    if signal_index >= 1
                    else math.nan
                ),
                atr7=float(features.atr7[signal_index]),
                slope_threshold=pehc_slope_threshold,
                chase_cap_atr=pehc_chase_cap_atr,
            )
            pehc_record({
                "event": "handoff_opportunity" if pending_kind == "opportunity" else "handoff_delayed_recheck",
                "index": int(index),
                "ts": ts.isoformat(),
                "origin_index": int(pending_origin),
                "price": current_open,
                "actual_side": int(side),
                "execution": pehc_execution,
                **eligibility,
            })
            origin_permitted = (
                pending_origin not in pehc_blocked_origin_indices
                and (
                    not pehc_allowed_origin_indices
                    or pending_origin in pehc_allowed_origin_indices
                )
            )
            if not origin_permitted:
                pehc_record({
                    "event": "handoff_reject_episode_ablation",
                    "index": int(index),
                    "ts": ts.isoformat(),
                    "origin_index": int(pending_origin),
                })
            elif not pehc_entry_enabled:
                pehc_record({
                    "event": "handoff_reject_shadow_only_control",
                    "index": int(index),
                    "ts": ts.isoformat(),
                    "origin_index": int(pending_origin),
                })
            elif side != 0:
                pehc_record({
                    "event": "handoff_reject_actual_nonflat",
                    "index": int(index),
                    "ts": ts.isoformat(),
                    "origin_index": int(pending_origin),
                    "actual_side": int(side),
                })
            elif not eligibility["passed"]:
                pehc_record({
                    "event": "handoff_reject_filter",
                    "index": int(index),
                    "ts": ts.isoformat(),
                    "origin_index": int(pending_origin),
                    **eligibility,
                })
            elif pending_kind == "opportunity" and pehc_execution == "next_utc_open":
                pehc_pending_kind = "entry"
                pehc_pending_due_index = int(index + 1)
                pehc_pending_origin_index = int(pending_origin)
                pehc_record({
                    "event": "handoff_delay_scheduled",
                    "index": int(index),
                    "ts": ts.isoformat(),
                    "due_index": int(index + 1),
                    "origin_index": int(pending_origin),
                })
            elif short_config is None:
                pehc_record({
                    "event": "handoff_reject_no_short_config",
                    "index": int(index),
                    "ts": ts.isoformat(),
                    "origin_index": int(pending_origin),
                })
            else:
                enter(short_config, ts, current_open, index, signal_index)
                entered_pending_reversal = True
                cooldown_left = 0
                action = "pehc_handoff_enter_short"
                pehc_record({
                    "event": "handoff_accept",
                    "index": int(index),
                    "ts": ts.isoformat(),
                    "origin_index": int(pending_origin),
                    "price": current_open,
                    "execution": pehc_execution,
                })
""",
        "PEHC pending processing",
    )
    source = _replace_once(
        source,
        "        if pending_short_reversal and index < terminal_index:\n",
        "        if pending_short_reversal and not entered_pending_reversal and index < terminal_index:\n",
        "PEHC pending precedence",
    )
    source = _replace_once(
        source,
        "\n        if index < terminal_index and side == 0:\n",
        """
        if pehc_shadow_active and index > pehc_shadow_origin_index:
            shadow_age = int(index - pehc_shadow_origin_index)
            if shadow_age > pehc_expiry_days:
                pehc_record({
                    "event": "shadow_expire",
                    "index": int(index),
                    "ts": ts.isoformat(),
                    "origin_index": int(pehc_shadow_origin_index),
                    "age_days": shadow_age,
                })
                pehc_shadow_active = False
            elif decision_index >= 0 and long_config is not None:
                shadow_native_reason = signal_exit(
                    long_config,
                    book,
                    features,
                    decision_index,
                    pehc_shadow_bars_held,
                )
                if shadow_native_reason:
                    pehc_record({
                        "event": "shadow_cancel_native_exit",
                        "index": int(index),
                        "ts": ts.isoformat(),
                        "origin_index": int(pehc_shadow_origin_index),
                        "reason": shadow_native_reason,
                    })
                    pehc_shadow_active = False

        if index < terminal_index and side == 0:
""",
        "PEHC expiry and native cancellation",
    )
    source = _replace_once(
        source,
        "                        entered_after_open = True\n",
        "                        entered_after_open = True\n                        pehc_entry_start_hour = 1\n",
        "PEHC natural post-open entry hour",
    )
    return source


def _apply_pehc_intraday(source: str) -> str:
    source = _replace_once(
        source,
        "\n        post_action_equity = equity\n",
        """
        if (
            pehc_pending_kind is not None
            and index == pehc_pending_due_index
            and index >= terminal_index
        ):
            pehc_record({
                "event": "handoff_terminal_suppressed",
                "index": int(index),
                "ts": ts.isoformat(),
                "origin_index": int(pehc_pending_origin_index),
                "pending_kind": pehc_pending_kind,
            })
            pehc_pending_kind = None
            pehc_pending_due_index = -1
            pehc_pending_origin_index = -1

        if pehc_shadow_active and index < terminal_index:
            shadow_inputs_finite = (
                np.isfinite(pehc_shadow_stop_price)
                and np.isfinite(current_open)
                and np.isfinite(float(book.close[index]))
                and np.isfinite(float(features.atr7[index]))
                and np.isfinite(features.hourly_open[index]).all()
                and np.isfinite(features.hourly_low[index]).all()
            )
            if not shadow_inputs_finite:
                pehc_record({
                    "event": "shadow_cancel_nonfinite_data",
                    "index": int(index),
                    "ts": ts.isoformat(),
                    "origin_index": int(pehc_shadow_origin_index),
                })
                pehc_shadow_active = False
            else:
                shadow_gap_hit = current_open <= pehc_shadow_stop_price
                shadow_crossed = np.flatnonzero(
                    features.hourly_low[index] <= pehc_shadow_stop_price
                )
                shadow_hit_hour = int(shadow_crossed[0]) if len(shadow_crossed) else None
                shadow_intraday_hit = shadow_hit_hour is not None
                if shadow_gap_hit or shadow_intraday_hit:
                    shadow_hour_gap_hit = (
                        shadow_hit_hour is not None
                        and float(features.hourly_open[index, shadow_hit_hour])
                        <= pehc_shadow_stop_price
                    )
                    if shadow_gap_hit:
                        reversal_hour = 0
                        shadow_stop_ts = ts
                        shadow_stop_fill = current_open
                    elif shadow_hour_gap_hit:
                        reversal_hour = int(shadow_hit_hour)
                        shadow_stop_ts = ts + pd.Timedelta(hours=shadow_hit_hour)
                        shadow_stop_fill = float(features.hourly_open[index, shadow_hit_hour])
                    else:
                        reversal_hour = int(shadow_hit_hour) + 1
                        shadow_stop_ts = ts + pd.Timedelta(hours=shadow_hit_hour + 1)
                        shadow_stop_fill = float(pehc_shadow_stop_price)
                    origin_index = int(pehc_shadow_origin_index)
                    pehc_record({
                        "event": "shadow_protective_stop",
                        "index": int(index),
                        "ts": shadow_stop_ts.isoformat(),
                        "origin_index": origin_index,
                        "stop_price": float(pehc_shadow_stop_price),
                        "fill_price": shadow_stop_fill,
                        "reversal_hour": int(reversal_hour),
                    })
                    pehc_shadow_active = False
                    if reversal_hour >= 24:
                        pehc_pending_kind = "opportunity"
                        pehc_pending_due_index = int(index + 1)
                        pehc_pending_origin_index = origin_index
                        pehc_record({
                            "event": "handoff_opportunity_scheduled",
                            "index": int(index),
                            "ts": (ts + pd.Timedelta(days=1)).isoformat(),
                            "due_index": int(index + 1),
                            "origin_index": origin_index,
                        })
                    else:
                        opportunity_ts = ts + pd.Timedelta(hours=reversal_hour)
                        opportunity_price = float(features.hourly_open[index, reversal_hour])
                        signal_index = max(0, decision_index)
                        eligibility = pehc_handoff_eligibility(
                            price=opportunity_price,
                            ma7=float(features.ma7[signal_index]),
                            previous_ma7=(
                                float(features.ma7[signal_index - 1])
                                if signal_index >= 1
                                else math.nan
                            ),
                            atr7=float(features.atr7[signal_index]),
                            slope_threshold=pehc_slope_threshold,
                            chase_cap_atr=pehc_chase_cap_atr,
                        )
                        pehc_record({
                            "event": "handoff_opportunity",
                            "index": int(index),
                            "ts": opportunity_ts.isoformat(),
                            "origin_index": origin_index,
                            "price": opportunity_price,
                            "actual_side": int(side),
                            "execution": pehc_execution,
                            **eligibility,
                        })
                        origin_permitted = (
                            origin_index not in pehc_blocked_origin_indices
                            and (
                                not pehc_allowed_origin_indices
                                or origin_index in pehc_allowed_origin_indices
                            )
                        )
                        if not origin_permitted:
                            pehc_record({
                                "event": "handoff_reject_episode_ablation",
                                "index": int(index),
                                "ts": opportunity_ts.isoformat(),
                                "origin_index": origin_index,
                            })
                        elif not pehc_entry_enabled:
                            pehc_record({
                                "event": "handoff_reject_shadow_only_control",
                                "index": int(index),
                                "ts": opportunity_ts.isoformat(),
                                "origin_index": origin_index,
                            })
                        elif side != 0:
                            pehc_record({
                                "event": "handoff_reject_actual_nonflat",
                                "index": int(index),
                                "ts": opportunity_ts.isoformat(),
                                "origin_index": origin_index,
                                "actual_side": int(side),
                            })
                        elif not eligibility["passed"]:
                            pehc_record({
                                "event": "handoff_reject_filter",
                                "index": int(index),
                                "ts": opportunity_ts.isoformat(),
                                "origin_index": origin_index,
                                **eligibility,
                            })
                        elif pehc_execution == "next_utc_open":
                            pehc_pending_kind = "entry"
                            pehc_pending_due_index = int(index + 1)
                            pehc_pending_origin_index = origin_index
                            pehc_record({
                                "event": "handoff_delay_scheduled",
                                "index": int(index),
                                "ts": opportunity_ts.isoformat(),
                                "due_index": int(index + 1),
                                "origin_index": origin_index,
                            })
                        elif short_config is None:
                            pehc_record({
                                "event": "handoff_reject_no_short_config",
                                "index": int(index),
                                "ts": opportunity_ts.isoformat(),
                                "origin_index": origin_index,
                            })
                        else:
                            enter(
                                short_config,
                                opportunity_ts,
                                opportunity_price,
                                index,
                                signal_index,
                            )
                            entered_after_open = True
                            pehc_entry_start_hour = int(reversal_hour)
                            cooldown_left = 0
                            action = "pehc_handoff_enter_short"
                            pehc_record({
                                "event": "handoff_accept",
                                "index": int(index),
                                "ts": opportunity_ts.isoformat(),
                                "origin_index": origin_index,
                                "price": opportunity_price,
                                "execution": pehc_execution,
                            })
                else:
                    pehc_shadow_bars_held += 1
                    pehc_shadow_highest_close = max(
                        pehc_shadow_highest_close,
                        float(book.close[index]),
                    )
                    shadow_atr = float(features.atr7[index])
                    shadow_candidate = (
                        pehc_shadow_highest_close + -1.0 * long_config.trail_atr * shadow_atr
                    )
                    pehc_shadow_stop_price = max(
                        pehc_shadow_stop_price,
                        shadow_candidate,
                    )
                    pehc_record({
                        "event": "shadow_hold",
                        "index": int(index),
                        "ts": ts.isoformat(),
                        "origin_index": int(pehc_shadow_origin_index),
                        "bars_held": int(pehc_shadow_bars_held),
                        "highest_close": float(pehc_shadow_highest_close),
                        "stop_price": float(pehc_shadow_stop_price),
                    })

        post_action_equity = equity
""",
        "PEHC shadow intraday processing",
    )
    source = _replace_once(
        source,
        "            day_high = (\n                float(book.post_short_entry_high[index])\n                if entered_after_open\n                else float(book.high[index])\n            )\n            day_low = (\n                float(book.post_short_entry_low[index])\n                if entered_after_open\n                else float(book.low[index])\n            )\n",
        """\
            day_high = (
                float(features.hourly_high[index, pehc_entry_start_hour:].max())
                if entered_after_open
                else float(book.high[index])
            )
            day_low = (
                float(features.hourly_low[index, pehc_entry_start_hour:].min())
                if entered_after_open
                else float(book.low[index])
            )
""",
        "PEHC arbitrary-hour extrema",
    )
    source = _replace_once(
        source,
        "            start_hour = 1 if entered_after_open else 0\n",
        "            start_hour = pehc_entry_start_hour if entered_after_open else 0\n",
        "PEHC arbitrary entry hour",
    )
    return source


def _apply_pehc_trace(source: str) -> str:
    source = _replace_once(
        source,
        '                        "wtl_entry_leverage": wtl_entry_leverage,\n',
        '                        "wtl_entry_leverage": wtl_entry_leverage,\n'
        '                        "pehc_shadow_active": pehc_shadow_active,\n'
        '                        "pehc_pending_kind": pehc_pending_kind,\n',
        "PEHC terminal trace",
    )
    source = _replace_once(
        source,
        '                    "wtl_entry_leverage": wtl_entry_leverage,\n',
        '                    "wtl_entry_leverage": wtl_entry_leverage,\n'
        '                    "pehc_shadow_active": pehc_shadow_active,\n'
        '                    "pehc_shadow_origin_index": pehc_shadow_origin_index,\n'
        '                    "pehc_shadow_stop_price": pehc_shadow_stop_price,\n'
        '                    "pehc_pending_kind": pehc_pending_kind,\n',
        "PEHC daily trace",
    )
    return source


def build_variant_function(
    context: Any,
    pehc_config: PEHCConfig,
    *,
    oapp_config: Any,
    entry_signal: Any,
    leverage_policy: Any,
    rsi6: np.ndarray,
    recorder: HandoffRecorder,
) -> tuple[Callable[..., Any], str]:
    source = _BASE._capture_exact_source(context)
    digest = hashlib.sha256(pehc_config.arm_id.encode()).hexdigest()[:12]
    function_name = f"pehc_{digest}_backtest"
    source = _replace_once(
        source, "def v3_ma_only_backtest(", f"def {function_name}(", "PEHC function name"
    )
    source = _BASE._apply_state(source)
    source = _BASE._apply_exits(source)
    source = _apply_pehc_state(source)
    source = _apply_pehc_arm(source)
    source = _apply_pehc_daily(source)
    source = _apply_pehc_intraday(source)
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
            "pehc_handoff_eligibility": handoff_eligibility,
            "pehc_record": recorder,
        }
    )
    compiled = compile(source, f"<pehc-{pehc_config.arm_id}>", "exec")
    exec(compiled, namespace)
    return namespace[function_name], hashlib.sha256(source.encode()).hexdigest()


def run_variant(
    context: Any,
    config: PEHCConfig,
    *,
    start_index: int,
    terminal_index: int,
    slippage: float = 0.0004,
    signal_lag: int = 0,
    include_funding: bool = True,
    retain: bool = False,
    short_rsi_enabled: bool = True,
) -> PEHCExecutionResult:
    oapp_config = fixed_oapp_config(short_rsi_enabled=short_rsi_enabled)
    rsi6 = _BASE.wilder_rsi6(context.book.close)
    entry_signal = _BASE.EntryQualitySignal(context.engine, oapp_config.entry)
    leverage_policy = _BASE.LeveragePolicy(context, None)
    recorder = HandoffRecorder()
    function, source_hash = build_variant_function(
        context,
        config,
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
    events = list(recorder.events)
    exits = [str(trade.get("exit_reason", "")) for trade in raw.trades]
    counts = {
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
    return PEHCExecutionResult(
        config=config,
        raw=raw,
        source_sha256=source_hash,
        entry_events=list(entry_signal.events),
        leverage_events=list(leverage_policy.events),
        handoff_events=events,
        activation_counts=counts,
        rsi6=rsi6,
    )
