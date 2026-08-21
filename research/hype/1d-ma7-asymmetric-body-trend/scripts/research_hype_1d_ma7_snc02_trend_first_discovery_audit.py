"""Audit trend discovery and complete holding for SNC02 and one CSM02 mechanism."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import sys
from types import ModuleType, SimpleNamespace
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CONTRACT_PATH = (
    FAMILY_DIR
    / "specs/hype-1d-ma7-snc02-trend-first-discovery-audit-contract-2026-08-20.md"
)
CONTROL_SCRIPT_PATH = (
    SCRIPT_DIR / "research_hype_1d_ma7_symmetric_naked_cross_slope.py"
)
STAGE_A_SCRIPT_PATH = (
    SCRIPT_DIR / "research_hype_1d_ma7_snc02_risk_overlay_oat.py"
)
CONTROL_ARTIFACT_PATH = (
    ARTIFACT_DIR / "hype_1d_ma7_symmetric_naked_cross_slope_2026-08-20.json"
)
RISK_PATH = SCRIPT_DIR / "hype_1d_ma7_trend_phase_risk_metrics.py"
OUTPUT_PATH = (
    ARTIFACT_DIR
    / "hype_1d_ma7_snc02_trend_first_discovery_audit_2026-08-20.json"
)

SLOPE_MIN_ATR = 0.02
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
CANONICAL_RIGHT = 432
FORWARD_HORIZONS = (3, 7, 14, 30)
MAJOR_MFE_PCT = 20.0
CAPTURE_COMPLETE_RATIO = 0.60


@dataclass(frozen=True, slots=True)
class Signal:
    index: int
    ts: pd.Timestamp
    target_side: int
    slope_atr: float
    signal_kind: str
    seed_index: int
    seed_ts: pd.Timestamp
    seed_slope_atr: float
    maturation_days: int

    def canonical(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "signal_ts": self.ts.isoformat(),
            "target_side": "long" if self.target_side > 0 else "short",
            "slope_atr": self.slope_atr,
            "signal_kind": self.signal_kind,
            "seed_index": self.seed_index,
            "seed_ts": self.seed_ts.isoformat(),
            "seed_slope_atr": self.seed_slope_atr,
            "maturation_days": self.maturation_days,
        }


@dataclass(slots=True)
class SeedState:
    side: int = 0
    index: int = -1
    ts: pd.Timestamp | None = None
    slope_atr: float = math.nan

    def clear(self) -> None:
        self.side = 0
        self.index = -1
        self.ts = None
        self.slope_atr = math.nan


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        return sanitize(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def raw_cross(context: Any, index: int) -> dict[str, Any] | None:
    if index < 1:
        return None
    close = float(context.book.close[index])
    previous_close = float(context.book.close[index - 1])
    ma7 = float(context.features.ma7[index])
    previous_ma7 = float(context.features.ma7[index - 1])
    atr7 = float(context.features.atr7[index])
    if not all(
        math.isfinite(value)
        for value in (close, previous_close, ma7, previous_ma7, atr7)
    ) or atr7 <= 0.0:
        return None
    side = 0
    if previous_close < previous_ma7 and close > ma7:
        side = 1
    elif previous_close > previous_ma7 and close < ma7:
        side = -1
    if not side:
        return None
    raw_slope_atr = (ma7 - previous_ma7) / atr7
    return {
        "index": index,
        "ts": pd.Timestamp(context.book.ts[index]),
        "side": side,
        "directional_slope_atr": side * raw_slope_atr,
        "close": close,
        "ma7": ma7,
        "atr7": atr7,
    }


def directional_slope_atr(context: Any, index: int, side: int) -> float:
    if index < 1:
        return math.nan
    ma7 = float(context.features.ma7[index])
    previous_ma7 = float(context.features.ma7[index - 1])
    atr7 = float(context.features.atr7[index])
    if not all(math.isfinite(value) for value in (ma7, previous_ma7, atr7)):
        return math.nan
    if atr7 <= 0.0:
        return math.nan
    return side * (ma7 - previous_ma7) / atr7


def on_directional_ma_side(context: Any, index: int, side: int) -> bool:
    close = float(context.book.close[index])
    ma7 = float(context.features.ma7[index])
    return math.isfinite(close) and math.isfinite(ma7) and side * (close - ma7) > 0.0


def control_signal(context: Any, control: ModuleType, index: int) -> Signal | None:
    source = control.qualified_signal(context, index)
    if source is None:
        return None
    return Signal(
        index=index,
        ts=pd.Timestamp(source.ts),
        target_side=int(source.target_side),
        slope_atr=abs(float(source.slope_atr)),
        signal_kind="qualified_fresh_cross",
        seed_index=index,
        seed_ts=pd.Timestamp(source.ts),
        seed_slope_atr=abs(float(source.slope_atr)),
        maturation_days=0,
    )


def csm_signal(context: Any, index: int, seed: SeedState) -> Signal | None:
    cross = raw_cross(context, index)
    if cross is not None:
        seed.side = int(cross["side"])
        seed.index = index
        seed.ts = pd.Timestamp(cross["ts"])
        seed.slope_atr = float(cross["directional_slope_atr"])

    if not seed.side:
        return None
    if not on_directional_ma_side(context, index, seed.side):
        seed.clear()
        return None
    slope = directional_slope_atr(context, index, seed.side)
    if not math.isfinite(slope) or slope < SLOPE_MIN_ATR:
        return None
    if seed.ts is None:
        raise RuntimeError("seed timestamp missing")
    signal = Signal(
        index=index,
        ts=pd.Timestamp(context.book.ts[index]),
        target_side=seed.side,
        slope_atr=slope,
        signal_kind=(
            "qualified_fresh_cross" if index == seed.index else "delayed_slope_maturation"
        ),
        seed_index=seed.index,
        seed_ts=seed.ts,
        seed_slope_atr=seed.slope_atr,
        maturation_days=index - seed.index,
    )
    seed.clear()
    return signal


def funding_events(context: Any) -> list[Any]:
    return sorted(
        (event for daily in context.features.funding_events for event in daily),
        key=lambda event: pd.Timestamp(event.ts),
    )


def terminal_point(context: Any, right: int) -> tuple[pd.Timestamp, float]:
    if right < context.book.count:
        return pd.Timestamp(context.book.ts[right]), float(context.book.open[right])
    return (
        pd.Timestamp(context.book.terminal_ts),
        float(context.book.quality["terminal_open"]),
    )


def run_backtest(
    context: Any,
    control: ModuleType,
    risk: ModuleType,
    *,
    mode: str,
    start: int,
    right: int,
    slippage: float = BASE_SLIPPAGE,
    include_funding: bool = True,
) -> dict[str, Any]:
    if mode not in {"control", "csm02"}:
        raise ValueError("unknown mode")
    if not 0 <= start < right <= context.book.count:
        raise ValueError("invalid backtest window")
    cost_rate = float(context.engine.FEE) + slippage
    events = funding_events(context) if include_funding else []
    equity = 1.0
    side = 0
    quantity = 0.0
    entry_ts: pd.Timestamp | None = None
    entry_price = math.nan
    entry_equity = math.nan
    entry_signal: Signal | None = None
    pending: tuple[int, Signal] | None = None
    seed = SeedState()
    total_turnover = 0.0
    total_cost = 0.0
    total_funding = 0.0
    trades: list[dict[str, Any]] = []
    signals: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []

    def enter(ts: pd.Timestamp, price: float, signal: Signal) -> None:
        nonlocal equity, side, quantity, entry_ts, entry_price, entry_equity
        nonlocal entry_signal, total_turnover, total_cost
        before = equity
        quantity, equity, turnover = risk.target_quantity(
            equity,
            0.0,
            signal.target_side,
            price,
            cost_rate,
            1.0,
        )
        total_turnover += turnover
        total_cost += before - equity
        side = signal.target_side
        entry_ts = ts
        entry_price = price
        entry_equity = before
        entry_signal = signal
        actions.append(
            {
                "action": "enter_long" if side > 0 else "enter_short",
                "ts": ts.isoformat(),
                "price": price,
                "signal": signal.canonical(),
            }
        )

    def close(ts: pd.Timestamp, price: float, reason: str) -> None:
        nonlocal equity, side, quantity, entry_ts, entry_price, entry_equity
        nonlocal entry_signal, total_turnover, total_cost, total_funding
        if side == 0 or entry_ts is None or entry_signal is None:
            return
        payments = [
            quantity * float(event.price) * float(event.rate)
            for event in events
            if entry_ts <= pd.Timestamp(event.ts) < ts
        ]
        funding = float(sum(payments))
        before_exit = equity + quantity * (price - entry_price) - funding
        before_cost = before_exit
        _, after, turnover = risk.target_quantity(
            before_exit,
            quantity,
            0,
            price,
            cost_rate,
            1.0,
        )
        total_turnover += turnover
        total_cost += before_cost - after
        total_funding += funding
        net_pnl = after - entry_equity
        old_side = side
        trades.append(
            {
                "side": "long" if old_side > 0 else "short",
                "entry_ts": entry_ts.isoformat(),
                "entry_price": entry_price,
                "exit_ts": ts.isoformat(),
                "exit_price": price,
                "exit_reason": reason,
                "entry_leverage": 1.0,
                "gross_return_pct": old_side * (price / entry_price - 1.0) * 100.0,
                "net_return_pct": net_pnl / entry_equity * 100.0,
                "net_pnl": net_pnl,
                "funding_pnl": -funding,
                "bars": int((ts - entry_ts) / pd.Timedelta(days=1)),
                "signal_kind": entry_signal.signal_kind,
                "signal_ts": entry_signal.ts.isoformat(),
                "seed_index": entry_signal.seed_index,
                "seed_ts": entry_signal.seed_ts.isoformat(),
                "seed_slope_atr": entry_signal.seed_slope_atr,
                "maturation_days": entry_signal.maturation_days,
            }
        )
        actions.append(
            {
                "action": "exit_long" if old_side > 0 else "exit_short",
                "ts": ts.isoformat(),
                "price": price,
                "reason": reason,
            }
        )
        equity = after
        side = 0
        quantity = 0.0
        entry_ts = None
        entry_price = math.nan
        entry_equity = math.nan
        entry_signal = None

    for index in range(start, right):
        ts = pd.Timestamp(context.book.ts[index])
        price = float(context.book.open[index])
        if pending is not None and pending[0] == index:
            _, signal = pending
            if side != signal.target_side:
                if side:
                    close(ts, price, "opposite_trend_signal")
                enter(ts, price, signal)
            actions.append(
                {
                    "action": "execute_signal",
                    "ts": ts.isoformat(),
                    "target_side": signal.target_side,
                    "signal": signal.canonical(),
                }
            )
            pending = None

        signal = (
            control_signal(context, control, index)
            if mode == "control"
            else csm_signal(context, index, seed)
        )
        if signal is None:
            continue
        row = signal.canonical()
        row["side_at_signal"] = side
        due_index = index + 1
        row["due_ts"] = (
            pd.Timestamp(context.book.ts[due_index]).isoformat()
            if due_index < right
            else None
        )
        row["scheduled"] = due_index < right and signal.target_side != side
        signals.append(row)
        if row["scheduled"]:
            if pending is not None:
                raise RuntimeError("multiple pending signals")
            pending = (due_index, signal)

    end_ts, end_price = terminal_point(context, right)
    close(end_ts, end_price, "terminal_flatten")
    positive = sum(max(0.0, float(row["net_pnl"])) for row in trades)
    negative = -sum(min(0.0, float(row["net_pnl"])) for row in trades)
    raw_metrics = {
        "equity_multiple": equity,
        "closed_trades": len(trades),
        "turnover_multiple": total_turnover,
        "cost_pct_initial": total_cost * 100.0,
        "funding_pct_initial": total_funding * 100.0,
    }
    raw = SimpleNamespace(metrics=raw_metrics, trades=trades)
    replay = risk.replay_chronological_1h(
        context,
        raw,
        slippage=slippage,
        include_funding=include_funding,
    )
    duration_days = right - start
    exposure_days = sum(float(row["bars"]) for row in trades)
    side_pnl = {
        name: sum(float(row["net_pnl"]) for row in trades if row["side"] == name)
        for name in ("long", "short")
    }
    metrics = {
        "mode": mode,
        "start_ts": pd.Timestamp(context.book.ts[start]).isoformat(),
        "end_ts": end_ts.isoformat(),
        "days": duration_days,
        "equity_multiple": equity,
        "net_return_pct": (equity - 1.0) * 100.0,
        "chronological_1h_mdd_pct": replay.chronological_1h_mdd_pct,
        "worst_ts": replay.worst_ts,
        "closed_trades": len(trades),
        "long_trades": sum(row["side"] == "long" for row in trades),
        "short_trades": sum(row["side"] == "short" for row in trades),
        "win_rate": (
            sum(float(row["net_pnl"]) > 0.0 for row in trades) / len(trades)
            if trades
            else 0.0
        ),
        "profit_factor": positive / negative if negative > 0.0 else math.inf,
        "turnover_multiple": total_turnover,
        "cost_pct_initial": total_cost * 100.0,
        "funding_pct_initial": total_funding * 100.0,
        "max_marked_leverage": replay.max_marked_leverage,
        "exposure_pct": exposure_days / duration_days * 100.0,
        "long_net_pnl_equity_units": side_pnl["long"],
        "short_net_pnl_equity_units": side_pnl["short"],
        "signal_count": len(signals),
        "scheduled_signal_count": sum(bool(row["scheduled"]) for row in signals),
        "delayed_maturation_signal_count": sum(
            row["signal_kind"] == "delayed_slope_maturation" for row in signals
        ),
        "ledger_parity": replay.parity,
    }
    return {
        "metrics": metrics,
        "raw": raw,
        "trades": trades,
        "signals": signals,
        "actions": actions,
    }


def ts_index_map(context: Any) -> dict[pd.Timestamp, int]:
    return {
        pd.Timestamp(value): index for index, value in enumerate(context.book.ts)
    }


def augment_trade_paths(
    context: Any,
    trades: list[dict[str, Any]],
    right: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    lookup = ts_index_map(context)
    augmented: list[dict[str, Any]] = []
    for source in trades:
        row = dict(source)
        side = 1 if row["side"] == "long" else -1
        entry_ts = pd.Timestamp(row["entry_ts"])
        exit_ts = pd.Timestamp(row["exit_ts"])
        entry_index = lookup[entry_ts]
        exit_index = lookup.get(exit_ts, right)
        end = min(exit_index, right)
        highs = [float(value) for value in context.book.high[entry_index:end]]
        lows = [float(value) for value in context.book.low[entry_index:end]]
        exit_price = float(row["exit_price"])
        entry_price = float(row["entry_price"])
        highs.append(exit_price)
        lows.append(exit_price)
        best_price = max(highs) if side > 0 else min(lows)
        worst_price = min(lows) if side > 0 else max(highs)
        mfe_pct = side * (best_price / entry_price - 1.0) * 100.0
        mae_pct = side * (worst_price / entry_price - 1.0) * 100.0
        gross_pct = float(row["gross_return_pct"])
        capture = gross_pct / mfe_pct if mfe_pct > 0.0 else math.nan
        giveback = (mfe_pct - gross_pct) / mfe_pct if mfe_pct > 0.0 else math.nan
        recrosses = sum(
            raw_cross(context, index) is not None
            for index in range(entry_index, min(exit_index, right))
        )
        row.update(
            {
                "mfe_pct": mfe_pct,
                "mae_pct": mae_pct,
                "best_price": best_price,
                "worst_price": worst_price,
                "capture_ratio": capture,
                "giveback_ratio": giveback,
                "raw_ma7_recross_count": recrosses,
                "major_trend": mfe_pct >= MAJOR_MFE_PCT,
                "capture_60pct": capture >= CAPTURE_COMPLETE_RATIO,
                "terminal_censored": row["exit_reason"] == "terminal_flatten",
            }
        )
        augmented.append(row)

    major = [row for row in augmented if row["major_trend"]]
    captures = [
        float(row["capture_ratio"])
        for row in major
        if math.isfinite(float(row["capture_ratio"]))
    ]
    mfe_sum = sum(float(row["mfe_pct"]) for row in major)
    weighted = (
        sum(max(0.0, float(row["gross_return_pct"])) for row in major) / mfe_sum
        if mfe_sum > 0.0
        else 0.0
    )
    august_ts = pd.Timestamp("2026-08-09T00:00:00Z")
    august_trade = next(
        (
            row
            for row in augmented
            if row["side"] == "long"
            and pd.Timestamp(row["entry_ts"]) <= august_ts
            and pd.Timestamp(row["exit_ts"]) > august_ts
        ),
        None,
    )
    summary = {
        "campaigns": len(augmented),
        "mfe_ge_10_count": sum(float(row["mfe_pct"]) >= 10.0 for row in augmented),
        "mfe_ge_20_count": len(major),
        "mfe_ge_30_count": sum(float(row["mfe_pct"]) >= 30.0 for row in augmented),
        "major_positive_exit_count": sum(
            float(row["gross_return_pct"]) > 0.0 for row in major
        ),
        "major_capture_60_count": sum(bool(row["capture_60pct"]) for row in major),
        "major_median_capture_ratio": statistics.median(captures) if captures else 0.0,
        "major_mfe_weighted_capture": weighted,
        "august_09_long_to_terminal": bool(
            august_trade and august_trade["terminal_censored"]
        ),
        "august_campaign": august_trade,
    }
    return augmented, summary


def control_side_on_close(
    context: Any,
    trades: list[dict[str, Any]],
    index: int,
) -> int:
    day_ts = pd.Timestamp(context.book.ts[index])
    for trade in trades:
        if pd.Timestamp(trade["entry_ts"]) <= day_ts < pd.Timestamp(trade["exit_ts"]):
            return 1 if trade["side"] == "long" else -1
    return 0


def forward_opportunity(
    context: Any,
    cross: dict[str, Any],
    control_trades: list[dict[str, Any]],
) -> dict[str, Any]:
    index = int(cross["index"])
    side = int(cross["side"])
    entry_index = index + 1
    if entry_index >= context.book.count:
        next_open = float(context.book.quality["terminal_open"])
    else:
        next_open = float(context.book.open[entry_index])
    row = {
        "cross_index": index,
        "cross_ts": pd.Timestamp(cross["ts"]).isoformat(),
        "side": "long" if side > 0 else "short",
        "directional_slope_atr": float(cross["directional_slope_atr"]),
        "accepted_by_snc02": float(cross["directional_slope_atr"])
        >= SLOPE_MIN_ATR,
        "control_side_at_cross_close": control_side_on_close(
            context,
            control_trades,
            index,
        ),
        "next_open": next_open,
    }
    row["missed_by_control"] = (
        not row["accepted_by_snc02"]
        and int(row["control_side_at_cross_close"]) != side
    )
    for horizon in FORWARD_HORIZONS:
        target_index = min(index + horizon, context.book.count - 1)
        target_close = float(context.book.close[target_index])
        row[f"close_return_{horizon}d_pct"] = (
            side * (target_close / next_open - 1.0) * 100.0
        )

    end = min(entry_index + 30, context.book.count)
    highs = [float(value) for value in context.book.high[entry_index:end]]
    lows = [float(value) for value in context.book.low[entry_index:end]]
    if not highs:
        highs = [next_open]
        lows = [next_open]
    best = max(highs) if side > 0 else min(lows)
    worst = min(lows) if side > 0 else max(highs)
    row["mfe_30d_pct"] = side * (best / next_open - 1.0) * 100.0
    row["mae_30d_pct"] = side * (worst / next_open - 1.0) * 100.0
    row["major_cross_opportunity"] = row["mfe_30d_pct"] >= MAJOR_MFE_PCT

    maturity_index: int | None = None
    if row["accepted_by_snc02"]:
        maturity_index = index
    else:
        for candidate_index in range(index + 1, context.book.count):
            if not on_directional_ma_side(context, candidate_index, side):
                break
            slope = directional_slope_atr(context, candidate_index, side)
            if math.isfinite(slope) and slope >= SLOPE_MIN_ATR:
                maturity_index = candidate_index
                break
    row["maturity_index"] = maturity_index
    row["maturity_ts"] = (
        pd.Timestamp(context.book.ts[maturity_index]).isoformat()
        if maturity_index is not None
        else None
    )
    row["maturation_days"] = (
        maturity_index - index if maturity_index is not None else None
    )
    row["matures_on_same_ma_side"] = maturity_index is not None
    if maturity_index is not None and maturity_index + 1 < context.book.count:
        maturity_open = float(context.book.open[maturity_index + 1])
        maturity_end = min(maturity_index + 31, context.book.count)
        maturity_highs = [
            float(value) for value in context.book.high[maturity_index + 1 : maturity_end]
        ]
        maturity_lows = [
            float(value) for value in context.book.low[maturity_index + 1 : maturity_end]
        ]
        maturity_best = (
            max(maturity_highs) if side > 0 else min(maturity_lows)
        )
        row["maturity_entry_open"] = maturity_open
        row["remaining_mfe_30d_pct"] = (
            side * (maturity_best / maturity_open - 1.0) * 100.0
        )
    else:
        row["maturity_entry_open"] = None
        row["remaining_mfe_30d_pct"] = None
    return row


def run(force: bool = False) -> dict[str, Any]:
    control = load_module(CONTROL_SCRIPT_PATH, "snc02_trend_first_control")
    stage_a = load_module(STAGE_A_SCRIPT_PATH, "snc02_trend_first_context")
    risk = load_module(RISK_PATH, "snc02_trend_first_risk")
    context = stage_a.load_context(control)
    retained_control = json.loads(CONTROL_ARTIFACT_PATH.read_text(encoding="utf-8"))

    extended: dict[str, Any] = {}
    canonical: dict[str, Any] = {}
    stress_8bps: dict[str, Any] = {}
    ledgers: dict[str, Any] = {}
    trend_summaries: dict[str, Any] = {}
    for mode in ("control", "csm02"):
        primary_run = run_backtest(
            context,
            control,
            risk,
            mode=mode,
            start=0,
            right=context.book.count,
        )
        canonical_run = run_backtest(
            context,
            control,
            risk,
            mode=mode,
            start=0,
            right=CANONICAL_RIGHT,
        )
        stress_run = run_backtest(
            context,
            control,
            risk,
            mode=mode,
            start=0,
            right=context.book.count,
            slippage=STRESS_SLIPPAGE,
        )
        augmented, trend_summary = augment_trade_paths(
            context,
            primary_run["trades"],
            context.book.count,
        )
        extended[mode] = primary_run["metrics"]
        canonical[mode] = canonical_run["metrics"]
        stress_8bps[mode] = stress_run["metrics"]
        ledgers[mode] = {
            "trades": augmented,
            "signals": primary_run["signals"],
            "actions": primary_run["actions"],
        }
        trend_summaries[mode] = trend_summary

    parity: dict[str, dict[str, bool]] = {}
    for label, actual, expected in (
        ("extended", extended["control"], retained_control["extended"]),
        ("canonical", canonical["control"], retained_control["canonical"]),
    ):
        checks = {
            key: math.isclose(
                float(actual[key]),
                float(expected[key]),
                rel_tol=0.0,
                abs_tol=2e-10,
            )
            for key in (
                "net_return_pct",
                "chronological_1h_mdd_pct",
                "closed_trades",
                "cost_pct_initial",
                "funding_pct_initial",
            )
        }
        if not all(checks.values()):
            raise RuntimeError(f"{label} control parity failed: {checks}")
        parity[label] = checks

    cross_audit = [
        forward_opportunity(context, cross, ledgers["control"]["trades"])
        for index in range(1, context.book.count)
        if (cross := raw_cross(context, index)) is not None
    ]
    rejected = [row for row in cross_audit if not row["accepted_by_snc02"]]
    rejected_sorted = sorted(
        rejected,
        key=lambda row: float(row["mfe_30d_pct"]),
        reverse=True,
    )
    missed_major = [
        row
        for row in cross_audit
        if row["missed_by_control"] and row["major_cross_opportunity"]
    ]
    scheduled_delayed_origins = {
        int(row["seed_index"])
        for row in ledgers["csm02"]["signals"]
        if row["signal_kind"] == "delayed_slope_maturation" and row["scheduled"]
    }
    recovered_major = [
        row for row in missed_major if int(row["cross_index"]) in scheduled_delayed_origins
    ]
    delayed_trades = [
        row
        for row in ledgers["csm02"]["trades"]
        if row["signal_kind"] == "delayed_slope_maturation"
    ]

    control_trend = trend_summaries["control"]
    candidate_trend = trend_summaries["csm02"]
    continuation = (
        len(recovered_major) >= 1
        and int(candidate_trend["major_positive_exit_count"])
        >= int(control_trend["major_positive_exit_count"])
        and float(candidate_trend["major_mfe_weighted_capture"])
        >= float(control_trend["major_mfe_weighted_capture"])
        and bool(candidate_trend["august_09_long_to_terminal"])
        and any(float(row["gross_return_pct"]) > 0.0 for row in delayed_trades)
    )

    payload = {
        "schema": "hype-1d-ma7-snc02-trend-first-discovery-audit-v1",
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "status": "DIAGNOSTIC_ONLY_TREND_FIRST_NOT_PROMOTED_NOT_LIVE_READY",
        "strategy_id": "HYPE-1D-MA7-SNC02-TREND-FIRST",
        "mechanisms": {
            "control": "strict fresh cross plus directional slope>=0.02ATR7",
            "csm02": "every fresh cross seeds same-side slope maturation; no max age",
            "exit": "only opposite mechanism signal; terminal is censored",
        },
        "evaluation": {
            "forward_horizons_days": list(FORWARD_HORIZONS),
            "major_cross_mfe_pct": MAJOR_MFE_PCT,
            "complete_capture_ratio": CAPTURE_COMPLETE_RATIO,
            "lag_screen_run": False,
            "mdd_primary_gate": False,
        },
        "data_audit": sanitize(context.market.audit),
        "extended": extended,
        "canonical": canonical,
        "stress_8bps": stress_8bps,
        "trend_summaries": trend_summaries,
        "cross_audit": cross_audit,
        "rejected_crosses_ranked_by_mfe30": rejected_sorted,
        "opportunity_summary": {
            "raw_cross_count": len(cross_audit),
            "accepted_cross_count": sum(
                bool(row["accepted_by_snc02"]) for row in cross_audit
            ),
            "rejected_cross_count": len(rejected),
            "rejected_major_count": sum(
                bool(row["major_cross_opportunity"]) for row in rejected
            ),
            "missed_major_by_control_count": len(missed_major),
            "missed_major_by_control": missed_major,
            "recovered_major_by_csm02_count": len(recovered_major),
            "recovered_major_by_csm02": recovered_major,
            "scheduled_delayed_origin_count": len(scheduled_delayed_origins),
            "delayed_maturation_trade_count": len(delayed_trades),
            "profitable_delayed_maturation_trade_count": sum(
                float(row["gross_return_pct"]) > 0.0 for row in delayed_trades
            ),
        },
        "ledgers": ledgers,
        "control_parity": parity,
        "verdict": {
            "csm02_continuation_worthy": continuation,
            "decision": (
                "CONTINUATION_WORTHY_POST_REVEAL"
                if continuation
                else "TREND_FIRST_GATE_FAILED"
            ),
            "registered_version": None,
            "changes_v7_1": False,
            "runner_change_authorized": False,
        },
        "pins": {
            "contract_sha256": sha256(CONTRACT_PATH),
            "script_sha256": sha256(Path(__file__).resolve()),
            "control_script_sha256": sha256(CONTROL_SCRIPT_PATH),
            "control_artifact_sha256": sha256(CONTROL_ARTIFACT_PATH),
            "stage_a_context_sha256": sha256(STAGE_A_SCRIPT_PATH),
            "risk_replay_sha256": sha256(RISK_PATH),
        },
        "notes": [
            "The 20% MFE label is hindsight-only evaluation and never enters signals.",
            "No extra one-day lag screen was run in this trend-first stage.",
            "All outcomes remain revealed-history diagnostic evidence.",
        ],
    }
    document = (
        json.dumps(sanitize(payload), ensure_ascii=False, sort_keys=True, indent=2)
        + "\n"
    )
    sidecar = Path(f"{OUTPUT_PATH}.sha256")
    if (OUTPUT_PATH.exists() or sidecar.exists()) and not force:
        raise RuntimeError(f"locked artifact exists: {OUTPUT_PATH.name}")
    OUTPUT_PATH.write_text(document, encoding="utf-8")
    digest = hashlib.sha256(document.encode()).hexdigest()
    sidecar.write_text(f"{digest}  {OUTPUT_PATH.name}\n", encoding="utf-8")
    return {"output": str(OUTPUT_PATH), "sha256": digest, "payload": payload}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if not args.run:
        print(
            json.dumps(
                {
                    "status": "CONTRACT_FROZEN_NOT_RUN",
                    "contract": str(CONTRACT_PATH),
                    "mechanisms": ["control", "csm02"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    result = run(force=args.force)
    payload = result["payload"]
    print(
        json.dumps(
            {
                "output": result["output"],
                "sha256": result["sha256"],
                "opportunity_summary": payload["opportunity_summary"],
                "trend_summaries": payload["trend_summaries"],
                "extended": payload["extended"],
                "verdict": payload["verdict"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
