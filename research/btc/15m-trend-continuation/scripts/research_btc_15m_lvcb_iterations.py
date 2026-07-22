from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import importlib.util
from itertools import product
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/btc/15m-trend-continuation"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
BASE_SCRIPT = FAMILY_DIR / "scripts/research_btc_15m_low_vol_compression_breakout.py"
BASE_SCRIPT_SHA256 = "581326b35f376a4e5d397bd8255dad0425eab763939f707f5ed1eaf7b1c3c026"
BASE_SUMMARY_PATH = ARTIFACT_DIR / "btc_15m_lvcb_summary_2026-07-20.json"
SUMMARY_PATH = ARTIFACT_DIR / "btc_15m_lvcb_iterations_summary_2026-07-20.json"
CANDIDATES_PATH = ARTIFACT_DIR / "btc_15m_lvcb_iterations_candidates_2026-07-20.csv"
COMPARISON_PATH = ARTIFACT_DIR / "btc_15m_lvcb_iterations_comparison_2026-07-20.csv"


@dataclass(frozen=True, slots=True)
class Variant:
    round_name: str
    role: str
    momentum_lookback: int = 0
    momentum_threshold: float = 0.0
    ema_spread_min: float = 0.0
    slow_slope_atr_min: float = 0.0
    rvol_min: float = 0.0
    body_atr_min: float = -100.0
    close_location_min: float = 0.0
    atr_floor: float = 0.0
    atr_cap: float = 0.0035
    stop_atr: float = 4.0
    max_hold_bars: int = 192
    take_profit_atr: float = 0.0
    cooldown_bars: int = 0


@dataclass(frozen=True, slots=True)
class SimulationResult:
    metrics: dict[str, Any]
    trades: pd.DataFrame
    equity: pd.Series


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def payload_sha256(payload: dict[str, Any]) -> str:
    body = {key: value for key, value in payload.items() if key != "payload_sha256"}
    return sha256_bytes(canonical_json_bytes(body))


def finite(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): finite(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        if math.isfinite(number):
            return number
        return "inf" if number > 0 else "-inf"
    return value


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    complete = finite(payload)
    complete["payload_sha256"] = payload_sha256(complete)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(complete, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def atomic_write_csv(path: Path, frame: pd.DataFrame) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    frame.to_csv(temporary, index=False)
    temporary.replace(path)


def load_base_module() -> Any:
    actual = sha256_bytes(BASE_SCRIPT.read_bytes())
    if actual != BASE_SCRIPT_SHA256:
        raise RuntimeError(
            f"base script SHA mismatch: expected {BASE_SCRIPT_SHA256}, got {actual}"
        )
    module_name = "btc_15m_lvcb_frozen_base"
    spec = importlib.util.spec_from_file_location(module_name, BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load base script: {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def variant_id(variant: Variant) -> str:
    return "iter-" + sha256_bytes(canonical_json_bytes(asdict(variant)))[:12]


def adverse_fill(
    raw_price: float,
    direction: int,
    *,
    is_entry: bool,
    slippage: float,
) -> float:
    order_side = direction if is_entry else -direction
    return raw_price * (1.0 + order_side * slippage)


def simulate(
    base: Any,
    frame: pd.DataFrame,
    funding_path: np.ndarray,
    atr: np.ndarray,
    signals: tuple[np.ndarray, np.ndarray],
    variant: Variant,
    start: pd.Timestamp,
    end: pd.Timestamp,
    *,
    fee_per_fill: float,
    slippage_per_fill: float,
    label: str,
) -> SimulationResult:
    index = frame.index
    start_i = int(index.searchsorted(start))
    end_i = int(index.searchsorted(end))
    open_ = frame["open"].to_numpy(float)
    high = frame["high"].to_numpy(float)
    low = frame["low"].to_numpy(float)
    close = frame["close"].to_numpy(float)
    long_signal, short_signal = signals
    realized_equity = 1.0
    position: dict[str, Any] | None = None
    pending_direction = 0
    pending_atr = math.nan
    earliest_entry_i = start_i
    trades: list[dict[str, Any]] = []
    curve_index: list[pd.Timestamp] = []
    curve_values: list[float] = []

    def close_position(i: int, raw_exit: float, reason: str) -> None:
        nonlocal realized_equity, position, earliest_entry_i
        if position is None:
            raise AssertionError("cannot close empty position")
        direction = int(position["direction"])
        exit_fill = adverse_fill(
            raw_exit,
            direction,
            is_entry=False,
            slippage=slippage_per_fill,
        )
        ratio = exit_fill / float(position["entry_fill"])
        funding_return = -direction * (
            funding_path[i] - float(position["funding_at_entry"])
        )
        trade_return = (
            direction * (ratio - 1.0)
            - fee_per_fill
            - ratio * fee_per_fill
            + funding_return
        )
        equity_before = float(position["equity_before"])
        equity_after = equity_before * (1.0 + trade_return)
        trades.append(
            {
                "label": label,
                "direction": "long" if direction == 1 else "short",
                "signal_ts": position["signal_ts"],
                "entry_ts": position["entry_ts"],
                "exit_ts": index[i],
                "entry_fill": position["entry_fill"],
                "exit_fill": exit_fill,
                "signal_atr": position["signal_atr"],
                "exit_reason": reason,
                "hold_bars": i - int(position["entry_i"]),
                "funding_return": funding_return,
                "trade_return": trade_return,
                "equity_before": equity_before,
                "equity_after": equity_after,
            }
        )
        realized_equity = equity_after
        earliest_entry_i = i + 1 + variant.cooldown_bars
        position = None

    for i in range(start_i, end_i):
        if position is None and pending_direction:
            if i >= earliest_entry_i:
                entry_fill = adverse_fill(
                    open_[i],
                    pending_direction,
                    is_entry=True,
                    slippage=slippage_per_fill,
                )
                target = (
                    math.nan
                    if variant.take_profit_atr <= 0.0
                    else entry_fill
                    + pending_direction * variant.take_profit_atr * pending_atr
                )
                position = {
                    "direction": pending_direction,
                    "signal_ts": index[i - 1],
                    "entry_i": i,
                    "entry_ts": index[i],
                    "entry_fill": entry_fill,
                    "signal_atr": pending_atr,
                    "stop": entry_fill
                    - pending_direction * variant.stop_atr * pending_atr,
                    "target": target,
                    "funding_at_entry": funding_path[i],
                    "equity_before": realized_equity,
                }
            pending_direction = 0
            pending_atr = math.nan

        if position is not None:
            direction = int(position["direction"])
            stop = float(position["stop"])
            target = float(position["target"])
            hold_bars = i - int(position["entry_i"])
            reason: str | None = None
            raw_exit = math.nan
            if hold_bars >= variant.max_hold_bars:
                reason = "time_open"
                raw_exit = open_[i]
            elif direction == 1:
                if open_[i] <= stop:
                    reason = "stop_gap"
                    raw_exit = open_[i]
                elif low[i] <= stop:
                    reason = "stop"
                    raw_exit = stop
                elif not math.isnan(target) and open_[i] >= target:
                    reason = "take_profit_gap"
                    raw_exit = open_[i]
                elif not math.isnan(target) and high[i] >= target:
                    reason = "take_profit"
                    raw_exit = target
            else:
                if open_[i] >= stop:
                    reason = "stop_gap"
                    raw_exit = open_[i]
                elif high[i] >= stop:
                    reason = "stop"
                    raw_exit = stop
                elif not math.isnan(target) and open_[i] <= target:
                    reason = "take_profit_gap"
                    raw_exit = open_[i]
                elif not math.isnan(target) and low[i] <= target:
                    reason = "take_profit"
                    raw_exit = target
            if reason is not None:
                close_position(i, raw_exit, reason)

        if position is None and i + 1 >= earliest_entry_i:
            if long_signal[i]:
                pending_direction = 1
                pending_atr = atr[i]
            elif short_signal[i]:
                pending_direction = -1
                pending_atr = atr[i]

        if position is None:
            marked = realized_equity
        else:
            direction = int(position["direction"])
            ratio = close[i] / float(position["entry_fill"])
            open_return = (
                direction * (ratio - 1.0)
                - fee_per_fill
                - direction
                * (funding_path[i] - float(position["funding_at_entry"]))
            )
            marked = float(position["equity_before"]) * (1.0 + open_return)
        curve_index.append(index[i])
        curve_values.append(marked)

    if position is not None:
        final_i = end_i - 1
        close_position(final_i, close[final_i], "window_end")
        curve_values[-1] = realized_equity
    equity = pd.Series(curve_values, index=pd.DatetimeIndex(curve_index), name=label)
    trades_frame = pd.DataFrame(trades)
    return SimulationResult(
        metrics=base.metrics(equity, trades_frame, start, end),
        trades=trades_frame,
        equity=equity,
    )


def build_context(
    base: Any,
    frame: pd.DataFrame,
    features: dict[str, Any],
) -> dict[str, Any]:
    close = frame["close"]
    atr = features["atr"]
    atr_pct = features["atr_pct"]
    fast = features["emas"][96]
    slow = features["emas"][384]
    compression = atr_pct.lt(features["compression_thresholds"][0.4])
    compressed_recently = (
        compression.rolling(16, min_periods=1)
        .max()
        .shift(1)
        .fillna(0.0)
        .gt(0.0)
    )
    long_raw = (
        compressed_recently
        & close.gt(features["donchian_highs"][96])
        & fast.gt(slow)
        & slow.gt(slow.shift(16))
    ).fillna(False)
    short_raw = (
        compressed_recently
        & close.lt(features["donchian_lows"][96])
        & fast.lt(slow)
        & slow.lt(slow.shift(16))
    ).fillna(False)
    high_low = (frame["high"] - frame["low"]).replace(0.0, np.nan)
    return {
        "atr_pct": atr_pct,
        "ema_spread": fast / slow - 1.0,
        "slow_slope_atr": (slow - slow.shift(16)) / atr,
        "rvol96": frame["volume"]
        / frame["volume"].rolling(96, min_periods=96).mean().shift(1),
        "body_atr": (frame["close"] - frame["open"]) / atr,
        "close_location": (frame["close"] - frame["low"]) / high_low,
        "momentum": {
            lookback: close / close.shift(lookback) - 1.0
            for lookback in (384, 768, 1536, 2880, 5760, 11520)
        },
        "long_raw": long_raw,
        "short_raw": short_raw,
        "base_module": base,
    }


def build_signals(
    context: dict[str, Any],
    variant: Variant,
) -> tuple[np.ndarray, np.ndarray]:
    long_signal = context["long_raw"].copy()
    short_signal = context["short_raw"].copy()
    atr_allowed = context["atr_pct"].between(
        variant.atr_floor,
        variant.atr_cap,
        inclusive="both",
    )
    long_signal &= atr_allowed
    short_signal &= atr_allowed
    if variant.momentum_lookback:
        momentum = context["momentum"][variant.momentum_lookback]
        long_signal &= momentum.gt(variant.momentum_threshold)
        short_signal &= momentum.lt(-variant.momentum_threshold)
    long_signal &= context["ema_spread"].ge(variant.ema_spread_min)
    short_signal &= context["ema_spread"].le(-variant.ema_spread_min)
    long_signal &= context["slow_slope_atr"].ge(variant.slow_slope_atr_min)
    short_signal &= context["slow_slope_atr"].le(-variant.slow_slope_atr_min)
    long_signal &= context["rvol96"].ge(variant.rvol_min)
    short_signal &= context["rvol96"].ge(variant.rvol_min)
    long_signal &= context["body_atr"].ge(variant.body_atr_min)
    short_signal &= context["body_atr"].le(-variant.body_atr_min)
    long_signal &= context["close_location"].ge(variant.close_location_min)
    short_signal &= context["close_location"].le(1.0 - variant.close_location_min)
    return (
        long_signal.fillna(False).to_numpy(bool),
        np.zeros(len(short_signal), dtype=bool),
    )


def parent_variant() -> Variant:
    return Variant(round_name="parent", role="frozen_parent")


def round_universes() -> dict[str, list[Variant]]:
    rounds: dict[str, list[Variant]] = {}
    rounds["R1_macro_momentum"] = [
        Variant(
            round_name="R1_macro_momentum",
            role="child",
            momentum_lookback=lookback,
            momentum_threshold=threshold,
        )
        for lookback, threshold in product(
            (384, 768, 1536, 2880, 5760, 11520),
            (0.0, 0.05, 0.10, 0.20),
        )
    ]
    rounds["R2_trend_quality"] = [
        Variant(
            round_name="R2_trend_quality",
            role="child",
            ema_spread_min=spread,
            slow_slope_atr_min=slope,
        )
        for spread, slope in product(
            (0.0, 0.0025, 0.0050, 0.0075, 0.0100),
            (0.0, 0.20, 0.30, 0.40, 0.50),
        )
    ]
    rounds["R3_breakout_quality"] = [
        Variant(
            round_name="R3_breakout_quality",
            role="child",
            rvol_min=rvol,
            body_atr_min=body,
            close_location_min=location,
        )
        for rvol, body, location in product(
            (0.0, 3.0, 4.0, 5.0, 6.0),
            (-100.0, 1.0, 1.5, 2.0, 2.5),
            (0.0, 0.70, 0.80, 0.90),
        )
    ]
    rounds["R4_volatility_band"] = [
        Variant(
            round_name="R4_volatility_band",
            role="child",
            atr_floor=floor,
            atr_cap=cap,
        )
        for floor, cap in product(
            (0.0, 0.0015, 0.00175, 0.0020, 0.00225, 0.0025),
            (0.00325, 0.0035, 0.00375, 0.0040, 0.00425),
        )
        if floor < cap
    ]
    rounds["R5_exit_structure"] = [
        Variant(
            round_name="R5_exit_structure",
            role="child",
            stop_atr=stop,
            max_hold_bars=hold,
            take_profit_atr=target,
        )
        for stop, hold, target in product(
            (3.0, 4.0, 5.0),
            (96, 144, 192, 288, 384),
            (0.0, 8.0, 12.0, 16.0, 20.0),
        )
    ]
    rounds["R6_cooldown"] = [
        Variant(
            round_name="R6_cooldown",
            role="child",
            cooldown_bars=cooldown,
        )
        for cooldown in (0, 1, 2, 4, 8, 16, 32)
    ]
    return rounds


def evaluate_development(
    base: Any,
    frame: pd.DataFrame,
    funding_path: np.ndarray,
    atr: np.ndarray,
    signals: tuple[np.ndarray, np.ndarray],
    variant: Variant,
) -> dict[str, Any]:
    train = simulate(
        base,
        frame,
        funding_path,
        atr,
        signals,
        variant,
        base.TRAIN_START,
        base.VALIDATION_START,
        fee_per_fill=base.FEE_PER_FILL,
        slippage_per_fill=base.SLIPPAGE_PER_FILL,
        label=f"{variant_id(variant)}_train",
    ).metrics
    validation = simulate(
        base,
        frame,
        funding_path,
        atr,
        signals,
        variant,
        base.VALIDATION_START,
        base.DIAGNOSTIC_START,
        fee_per_fill=base.FEE_PER_FILL,
        slippage_per_fill=base.SLIPPAGE_PER_FILL,
        label=f"{variant_id(variant)}_validation",
    ).metrics
    development_pass, failures = base.development_gate(train, validation)
    return {
        "variant_id": variant_id(variant),
        "variant": asdict(variant),
        "train": train,
        "validation": validation,
        "development_pass": development_pass,
        "gate_failures": failures,
    }


def add_development_stress(
    base: Any,
    frame: pd.DataFrame,
    funding_path: np.ndarray,
    atr: np.ndarray,
    signals: tuple[np.ndarray, np.ndarray],
    variant: Variant,
    row: dict[str, Any],
) -> None:
    stress_train = simulate(
        base,
        frame,
        funding_path,
        atr,
        signals,
        variant,
        base.TRAIN_START,
        base.VALIDATION_START,
        fee_per_fill=base.FEE_PER_FILL * 2.0,
        slippage_per_fill=base.SLIPPAGE_PER_FILL * 2.0,
        label=f"{variant_id(variant)}_stress_train",
    ).metrics
    stress_validation = simulate(
        base,
        frame,
        funding_path,
        atr,
        signals,
        variant,
        base.VALIDATION_START,
        base.DIAGNOSTIC_START,
        fee_per_fill=base.FEE_PER_FILL * 2.0,
        slippage_per_fill=base.SLIPPAGE_PER_FILL * 2.0,
        label=f"{variant_id(variant)}_stress_validation",
    ).metrics
    row["stress_2x_train"] = stress_train
    row["stress_2x_validation"] = stress_validation
    row["complete_development_pass"] = bool(
        row["development_pass"]
        and stress_train["return_pct"] > 0.0
        and stress_validation["return_pct"] > 0.0
    )
    if not row["complete_development_pass"]:
        row["gate_failures"] = [
            *row["gate_failures"],
            "double_cost_return",
        ]


def audit_variant(
    base: Any,
    frame: pd.DataFrame,
    funding_path: np.ndarray,
    atr: np.ndarray,
    signals: tuple[np.ndarray, np.ndarray],
    variant: Variant,
    end: pd.Timestamp,
) -> dict[str, Any]:
    diagnostic = simulate(
        base,
        frame,
        funding_path,
        atr,
        signals,
        variant,
        base.DIAGNOSTIC_START,
        end,
        fee_per_fill=base.FEE_PER_FILL,
        slippage_per_fill=base.SLIPPAGE_PER_FILL,
        label=f"{variant_id(variant)}_diagnostic",
    ).metrics
    diagnostic_2x = simulate(
        base,
        frame,
        funding_path,
        atr,
        signals,
        variant,
        base.DIAGNOSTIC_START,
        end,
        fee_per_fill=base.FEE_PER_FILL * 2.0,
        slippage_per_fill=base.SLIPPAGE_PER_FILL * 2.0,
        label=f"{variant_id(variant)}_diagnostic_2x",
    ).metrics
    recent: dict[str, Any] = {}
    for name, days in (("3m", 90), ("6m", 180), ("1y", 365)):
        recent[name] = simulate(
            base,
            frame,
            funding_path,
            atr,
            signals,
            variant,
            end - pd.Timedelta(days=days),
            end,
            fee_per_fill=base.FEE_PER_FILL,
            slippage_per_fill=base.SLIPPAGE_PER_FILL,
            label=f"{variant_id(variant)}_recent_{name}",
        ).metrics
    rolling_rows: list[dict[str, Any]] = []
    cursor = base.TRAIN_START
    while cursor < end:
        window_end = min(cursor + pd.Timedelta(days=180), end)
        if window_end - cursor < pd.Timedelta(days=60):
            break
        result = simulate(
            base,
            frame,
            funding_path,
            atr,
            signals,
            variant,
            cursor,
            window_end,
            fee_per_fill=base.FEE_PER_FILL,
            slippage_per_fill=base.SLIPPAGE_PER_FILL,
            label=f"{variant_id(variant)}_rolling",
        )
        rolling_rows.append(result.metrics)
        cursor = window_end
    rolling = {
        "count": len(rolling_rows),
        "positive_count": sum(row["return_pct"] > 0.0 for row in rolling_rows),
        "positive_ratio": float(
            np.mean([row["return_pct"] > 0.0 for row in rolling_rows])
        ),
        "zero_trade_count": sum(row["trades"] == 0 for row in rolling_rows),
    }
    return {
        "reused_diagnostic": diagnostic,
        "reused_diagnostic_2x": diagnostic_2x,
        "recent": recent,
        "rolling_180d": rolling,
    }


def development_rank(row: dict[str, Any]) -> tuple[float, float, float]:
    return (
        min(row["train"]["return_pct"], row["validation"]["return_pct"]),
        min(row["train"]["profit_factor"], row["validation"]["profit_factor"]),
        -max(
            abs(row["train"]["max_drawdown_pct"]),
            abs(row["validation"]["max_drawdown_pct"]),
        ),
    )


def adoption_decision(
    parent: dict[str, Any],
    child: dict[str, Any],
) -> tuple[bool, list[str], dict[str, Any]]:
    reasons: list[str] = []
    primary_improvements = sum(
        child[name]["return_pct"] > parent[name]["return_pct"]
        for name in ("train", "validation", "reused_diagnostic")
    )
    recent_improvements = sum(
        child["recent"][name]["return_pct"] > parent["recent"][name]["return_pct"]
        for name in ("3m", "6m", "1y")
    )
    if not child["complete_development_pass"]:
        reasons.append("development_or_2x_gate")
    if child["reused_diagnostic"]["return_pct"] <= 0.0:
        reasons.append("diagnostic_return")
    if child["reused_diagnostic_2x"]["return_pct"] <= 0.0:
        reasons.append("diagnostic_2x_return")
    if (
        child["reused_diagnostic"]["return_pct"]
        < parent["reused_diagnostic"]["return_pct"] - 10.0
    ):
        reasons.append("diagnostic_return_sacrifice")
    if abs(child["reused_diagnostic"]["max_drawdown_pct"]) > abs(
        parent["reused_diagnostic"]["max_drawdown_pct"]
    ) + 3.0:
        reasons.append("diagnostic_mdd")
    if primary_improvements < 2:
        reasons.append("insufficient_primary_improvement")
    if recent_improvements < 2:
        reasons.append("insufficient_recent_improvement")
    if child["rolling_180d"]["positive_ratio"] < (
        parent["rolling_180d"]["positive_ratio"] - 0.08
    ):
        reasons.append("rolling_stability")
    return (
        not reasons,
        reasons,
        {
            "primary_improvements": primary_improvements,
            "recent_improvements": recent_improvements,
        },
    )


def flatten_candidate(row: dict[str, Any]) -> dict[str, Any]:
    output = {
        "variant_id": row["variant_id"],
        "round_name": row["variant"]["round_name"],
        "variant_json": json.dumps(row["variant"], sort_keys=True),
        "signal_effective": row["signal_effective"],
        "development_pass": row["development_pass"],
        "complete_development_pass": row.get("complete_development_pass", False),
        "gate_failures": "|".join(row["gate_failures"]),
    }
    for period in (
        "train",
        "validation",
        "stress_2x_train",
        "stress_2x_validation",
    ):
        for key, value in row.get(period, {}).items():
            output[f"{period}_{key}"] = value
    return output


def flatten_comparison(row: dict[str, Any]) -> dict[str, Any]:
    output = {
        "round_name": row["round_name"],
        "selected_variant_id": row.get("selected_variant_id"),
        "adopted": row["adopted"],
        "rejection_reasons": "|".join(row["rejection_reasons"]),
        "effective_variants": row["effective_variants"],
        "complete_development_passes": row["complete_development_passes"],
    }
    for period in ("train", "validation", "reused_diagnostic"):
        metrics = row.get("selected", {}).get(period, {})
        for key in ("return_pct", "max_drawdown_pct", "trades", "profit_factor"):
            output[f"{period}_{key}"] = metrics.get(key)
    for name in ("3m", "6m", "1y"):
        output[f"recent_{name}_return_pct"] = (
            row.get("selected", {}).get("recent", {}).get(name, {}).get("return_pct")
        )
    return output


def expanding_walk_forward(
    base: Any,
    frame: pd.DataFrame,
    funding_path: np.ndarray,
    atr: np.ndarray,
    context: dict[str, Any],
    variants: list[Variant],
    end: pd.Timestamp,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for year in range(2022, end.year + 1):
        selection_end = pd.Timestamp(year=year, month=1, day=1, tz="UTC")
        test_end = min(
            pd.Timestamp(year=year + 1, month=1, day=1, tz="UTC"),
            end,
        )
        if selection_end >= end:
            continue
        eligible: list[tuple[Variant, dict[str, Any]]] = []
        for variant in variants:
            signals = build_signals(context, variant)
            selection = simulate(
                base,
                frame,
                funding_path,
                atr,
                signals,
                variant,
                base.TRAIN_START,
                selection_end,
                fee_per_fill=base.FEE_PER_FILL,
                slippage_per_fill=base.SLIPPAGE_PER_FILL,
                label=f"wf_select_{year}_{variant_id(variant)}",
            ).metrics
            if (
                selection["return_pct"] > 0.0
                and abs(selection["max_drawdown_pct"]) <= 25.0
                and selection["trades"] >= 20
                and selection["profit_factor"] >= 1.05
            ):
                eligible.append((variant, selection))
        if not eligible:
            rows.append(
                {
                    "test_year": year,
                    "selection_end": selection_end.isoformat(),
                    "test_end_exclusive": test_end.isoformat(),
                    "eligible_variants": 0,
                    "selected_variant_id": None,
                    "selection": {},
                    "test": {},
                    "test_2x": {},
                }
            )
            continue
        selected_variant, selection_metrics = max(
            eligible,
            key=lambda item: (
                item[1]["annual_return_pct"],
                item[1]["profit_factor"],
                -abs(item[1]["max_drawdown_pct"]),
            ),
        )
        signals = build_signals(context, selected_variant)
        test = simulate(
            base,
            frame,
            funding_path,
            atr,
            signals,
            selected_variant,
            selection_end,
            test_end,
            fee_per_fill=base.FEE_PER_FILL,
            slippage_per_fill=base.SLIPPAGE_PER_FILL,
            label=f"wf_test_{year}_{variant_id(selected_variant)}",
        ).metrics
        test_2x = simulate(
            base,
            frame,
            funding_path,
            atr,
            signals,
            selected_variant,
            selection_end,
            test_end,
            fee_per_fill=base.FEE_PER_FILL * 2.0,
            slippage_per_fill=base.SLIPPAGE_PER_FILL * 2.0,
            label=f"wf_test_2x_{year}_{variant_id(selected_variant)}",
        ).metrics
        rows.append(
            {
                "test_year": year,
                "selection_end": selection_end.isoformat(),
                "test_end_exclusive": test_end.isoformat(),
                "eligible_variants": len(eligible),
                "selected_variant_id": variant_id(selected_variant),
                "selected_variant": asdict(selected_variant),
                "selection": selection_metrics,
                "test": test,
                "test_2x": test_2x,
            }
        )
    nonempty = [row for row in rows if row["test"]]
    return {
        "protocol": (
            "expanding selection from 2020 start; at each year choose only among "
            "the frozen parent and six round finalists using prior data, then test "
            "the next calendar segment"
        ),
        "mechanism_contamination_warning": (
            "round mechanisms were designed with full-history knowledge, so these "
            "chronological tests are diagnostic walk-forward, not untouched OOS"
        ),
        "rows": rows,
        "test_count": len(nonempty),
        "positive_test_count": sum(
            row["test"]["return_pct"] > 0.0 for row in nonempty
        ),
        "positive_test_ratio": float(
            np.mean([row["test"]["return_pct"] > 0.0 for row in nonempty])
        ),
        "positive_2x_test_count": sum(
            row["test_2x"]["return_pct"] > 0.0 for row in nonempty
        ),
        "compounded_test_return_pct": float(
            (
                np.prod(
                    [1.0 + row["test"]["return_pct"] / 100.0 for row in nonempty]
                )
                - 1.0
            )
            * 100.0
        ),
        "compounded_2x_test_return_pct": float(
            (
                np.prod(
                    [
                        1.0 + row["test_2x"]["return_pct"] / 100.0
                        for row in nonempty
                    ]
                )
                - 1.0
            )
            * 100.0
        ),
        "total_test_trades": sum(row["test"]["trades"] for row in nonempty),
    }


def main() -> None:
    base = load_base_module()
    base_summary = json.loads(BASE_SUMMARY_PATH.read_text(encoding="utf-8"))
    frame, funding, data_metadata = base.load_data()
    end = pd.Timestamp(data_metadata["end_exclusive"])
    features = base.base_features(frame)
    context = build_context(base, frame, features)
    atr = features["atr"].to_numpy(float)
    funding_path = base.funding_cumulative(frame.index, funding)
    parent = parent_variant()
    parent_signals = build_signals(context, parent)

    frozen_config = base_summary["selected"]["config"]
    if frozen_config["signal"] != {
        "compression_quantile": 0.4,
        "compression_lookback": 16,
        "breakout_window": 96,
        "ema_fast": 96,
        "ema_slow": 384,
        "slope_lag": 16,
        "atr_cap": 0.0035,
    }:
        raise RuntimeError("frozen parent signal config changed")
    if (
        frozen_config["stop_atr"] != 4.0
        or frozen_config["max_hold_bars"] != 192
        or frozen_config["side_mode"] != "long"
    ):
        raise RuntimeError("frozen parent exit config changed")

    base_signal_config = base.SignalConfig(**frozen_config["signal"])
    expected_signals = base.build_signals(frame, features, base_signal_config)
    if not np.array_equal(parent_signals[0], expected_signals[0]):
        raise RuntimeError("iteration parent signal parity failed")
    parent_development = evaluate_development(
        base,
        frame,
        funding_path,
        atr,
        parent_signals,
        parent,
    )
    add_development_stress(
        base,
        frame,
        funding_path,
        atr,
        parent_signals,
        parent,
        parent_development,
    )
    parent_audit = audit_variant(
        base,
        frame,
        funding_path,
        atr,
        parent_signals,
        parent,
        end,
    )
    parent_full = {**parent_development, **parent_audit}
    expected_parent = base_summary["selected"]
    for period in ("train", "validation"):
        if (
            abs(
                parent_full[period]["return_pct"]
                - expected_parent[period]["return_pct"]
            )
            > 1e-10
        ):
            raise RuntimeError(f"parent metric parity failed: {period}")

    all_candidates: list[dict[str, Any]] = []
    round_results: list[dict[str, Any]] = []
    for round_name, variants in round_universes().items():
        print(f"running {round_name}: {len(variants)} variants", flush=True)
        rows: list[dict[str, Any]] = []
        for variant in variants:
            signals = build_signals(context, variant)
            signal_effective = not (
                np.array_equal(signals[0], parent_signals[0])
                and variant.stop_atr == parent.stop_atr
                and variant.max_hold_bars == parent.max_hold_bars
                and variant.take_profit_atr == parent.take_profit_atr
                and variant.cooldown_bars == parent.cooldown_bars
            )
            row = evaluate_development(
                base,
                frame,
                funding_path,
                atr,
                signals,
                variant,
            )
            row["signal_effective"] = signal_effective
            if row["development_pass"] and signal_effective:
                add_development_stress(
                    base,
                    frame,
                    funding_path,
                    atr,
                    signals,
                    variant,
                    row,
                )
            else:
                row["complete_development_pass"] = False
            rows.append(row)
            all_candidates.append(row)

        eligible = [
            row
            for row in rows
            if row["signal_effective"] and row["complete_development_pass"]
        ]
        selected_row = max(eligible, key=development_rank) if eligible else None
        if selected_row is None:
            round_results.append(
                {
                    "round_name": round_name,
                    "hypothesis": round_name.removeprefix("R").replace("_", " "),
                    "effective_variants": sum(row["signal_effective"] for row in rows),
                    "complete_development_passes": 0,
                    "selected_variant_id": None,
                    "selected": {},
                    "adopted": False,
                    "rejection_reasons": ["no_complete_development_pass"],
                    "comparison": {},
                }
            )
            continue

        selected_variant = Variant(**selected_row["variant"])
        selected_signals = build_signals(context, selected_variant)
        selected_audit = audit_variant(
            base,
            frame,
            funding_path,
            atr,
            selected_signals,
            selected_variant,
            end,
        )
        selected_full = {**selected_row, **selected_audit}
        adopted, rejection_reasons, comparison = adoption_decision(
            parent_full,
            selected_full,
        )
        round_results.append(
            {
                "round_name": round_name,
                "hypothesis": round_name.removeprefix("R").replace("_", " "),
                "effective_variants": sum(row["signal_effective"] for row in rows),
                "complete_development_passes": len(eligible),
                "selected_variant_id": selected_row["variant_id"],
                "selected": selected_full,
                "adopted": adopted,
                "rejection_reasons": rejection_reasons,
                "comparison": comparison,
            }
        )

    adopted_rounds = [row for row in round_results if row["adopted"]]
    finalist_variants = [parent] + [
        Variant(**row["selected"]["variant"])
        for row in round_results
        if row["selected"]
    ]
    walk_forward = expanding_walk_forward(
        base,
        frame,
        funding_path,
        atr,
        context,
        finalist_variants,
        end,
    )
    recent_positive = [
        row
        for row in adopted_rounds
        if row["selected"]["recent"]["3m"]["return_pct"] > 0.0
    ]
    if recent_positive:
        research_value = (
            "conditional_continue: a child survives historical gates; freeze it as "
            "a shadow observation and require prospective evidence"
        )
    elif adopted_rounds:
        research_value = (
            "limited_continue: structural improvement exists but recent regime is "
            "still weak; no further historical optimization"
        )
    else:
        research_value = (
            "low_incremental_value: no round survives parent-child adoption gates; "
            "stop historical iteration and retain only prospective observation"
        )

    candidate_frame = pd.DataFrame(
        [flatten_candidate(row) for row in all_candidates]
    )
    comparison_frame = pd.DataFrame(
        [flatten_comparison(row) for row in round_results]
    )
    atomic_write_csv(CANDIDATES_PATH, candidate_frame)
    atomic_write_csv(COMPARISON_PATH, comparison_frame)
    script_path = Path(__file__).resolve()
    summary = {
        "family": "BTC-15M-Trend-Continuation",
        "status": "explore / not promoted / not live-ready",
        "research_identity": "BTC-15M-LVCB-ITERATIONS-2026-07-20",
        "method": {
            "style": (
                "TB-style single-mechanism rounds; each child is selected only on "
                "train/validation, then compared with the frozen parent on reused "
                "diagnostic, 2x cost, recent slices and rolling windows"
            ),
            "parent_strategy_id": base_summary["selected"]["strategy_id"],
            "parent_script_sha256": BASE_SCRIPT_SHA256,
            "round_count": len(round_results),
            "candidate_count": len(all_candidates),
            "adoption_rule": {
                "complete_development_and_2x_gate": True,
                "diagnostic_and_diagnostic_2x_positive": True,
                "diagnostic_return_sacrifice_limit_pp": 10.0,
                "diagnostic_mdd_worsening_limit_pp": 3.0,
                "minimum_primary_improvements": 2,
                "minimum_recent_improvements": 2,
                "rolling_positive_ratio_tolerance": 0.08,
            },
        },
        "data": data_metadata,
        "contamination_disclosure": (
            "All mechanisms were designed after viewing the existing full history. "
            "Train/validation selection discipline reduces direct period selection "
            "leakage but does not create untouched OOS. Prospective evidence still "
            "starts after 2026-07-20 07:30 UTC."
        ),
        "failure_diagnosis": {
            "finding": (
                "recent degradation comes mainly from smaller time-exit winners, "
                "not larger stop losses"
            ),
            "historical_time_exit_mean_return_2020_2024_pct": 4.59,
            "recent_time_exit_mean_return_2025_2026_pct": 2.08,
            "recent_3m_trades": 16,
            "recent_3m_win_rate": 0.1875,
            "recent_3m_return_pct": -9.322739608982179,
        },
        "parent": parent_full,
        "rounds": round_results,
        "diagnostic_walk_forward": walk_forward,
        "adopted_round_count": len(adopted_rounds),
        "research_value": research_value,
        "decision": (
            "No result authorizes registration or promotion. An adopted child, if "
            "any, is only a shadow research observation; otherwise the frozen parent "
            "remains unchanged and historical optimization stops."
        ),
        "artifacts": {
            "candidates": str(CANDIDATES_PATH.relative_to(ROOT)),
            "comparison": str(COMPARISON_PATH.relative_to(ROOT)),
        },
        "provenance": {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "code_path": str(script_path.relative_to(ROOT)),
            "code_sha256": sha256_bytes(script_path.read_bytes()),
            "base_summary_path": str(BASE_SUMMARY_PATH.relative_to(ROOT)),
            "base_summary_sha256": sha256_bytes(BASE_SUMMARY_PATH.read_bytes()),
        },
    }
    atomic_write_json(SUMMARY_PATH, summary)
    print(json.dumps(finite(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
