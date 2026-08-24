"""Full active-parameter ablation for frozen HYPE MA7 ABT V6."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from types import ModuleType
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
ENGINE_PATH = SCRIPT_DIR / "hype_1d_ma7_profit_exit_handoff_continuity_engine.py"
ADAPTER_PATH = SCRIPT_DIR / "hype_1d_ma7_v4_fair_adapter.py"
SELF_PATH = Path(__file__).resolve()
OUTPUT_PATH = ARTIFACT_DIR / "hype_1d_ma7_abt_v6_full_parameter_ablation_2026-08-11.json"

FULL = (0, 432)
BLOCKS = tuple((left, left + 54) for left in range(0, 432, 54))
RECENT_SLICES = {
    "1d": 1,
    "7d": 7,
    "1m": 30,
    "3m": 90,
    "6m": 180,
    "1y": 365,
}
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
EXPECTED_V6_RETURN = 617.1070876096234
EXPECTED_V6_1H_MDD = -18.391735672691034
EXPECTED_V6_TRADES = 19
MDD_TOLERANCE = 1e-8
NO_SLOPE_GATE = -1_000_000_000.0
NO_NATURAL_ENTRY = 1_000_000_000.0


@dataclass(frozen=True, slots=True)
class Variant:
    name: str
    group: str
    change: str
    long_config: Any
    short_config: Any
    oapp_config: Any
    pehc_config: Any


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
    if hasattr(value, "item"):
        return sanitize(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        sanitize(value), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def write_json(path: Path, payload: dict[str, Any], *, force: bool) -> str:
    sidecar = Path(f"{path}.sha256")
    if (path.exists() or sidecar.exists()) and not force:
        raise RuntimeError(f"locked artifact exists: {path.name}")
    document = (
        json.dumps(sanitize(payload), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    )
    digest = hashlib.sha256(document.encode()).hexdigest()
    path.write_text(document, encoding="utf-8")
    sidecar.write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    return digest


def start_for(window: tuple[int, int]) -> int:
    left, right = window
    return left if left == 0 or right - left == 1 else left + 1


def target_quantity(
    equity: float,
    old_qty: float,
    target_side: int,
    price: float,
    cost_rate: float,
    leverage: float = 1.0,
) -> tuple[float, float, float]:
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


def chronological_replay(context: Any, raw: Any, *, slippage: float, include_funding: bool) -> dict[str, Any]:
    fee = float(context.engine.FEE)
    cost_rate = fee + slippage
    marks: list[tuple[pd.Timestamp, str, Any]] = []
    for index, day in enumerate(context.book.ts):
        day_ts = pd.Timestamp(day)
        for hour in range(24):
            marks.append((day_ts + pd.Timedelta(hours=hour), "mark", float(context.features.hourly_open[index, hour])))
    marks.append((pd.Timestamp(context.book.terminal_ts), "mark", float(context.book.quality["terminal_open"])))
    if include_funding:
        for daily in context.features.funding_events:
            for event in daily:
                marks.append((pd.Timestamp(event.ts), "funding", event))
    for idx, trade in enumerate(raw.trades):
        marks.append((pd.Timestamp(trade["entry_ts"]), "entry", (idx, trade)))
        marks.append((pd.Timestamp(trade["exit_ts"]), "exit", (idx, trade)))
    order = {"mark": 0, "funding": 1, "exit": 2, "entry": 3}
    marks.sort(key=lambda row: (row[0], order[row[1]]))

    equity = 1.0
    peak = 1.0
    mdd = 0.0
    qty = 0.0
    mark_price: float | None = None
    total_turnover = 0.0
    total_cost = 0.0
    total_funding = 0.0
    max_marked_leverage = 0.0
    worst_ts: str | None = None
    worst_trade: int | None = None
    active_trade: int | None = None

    def observe(ts: pd.Timestamp, trade_index: int | None = None) -> None:
        nonlocal peak, mdd, worst_ts, worst_trade, max_marked_leverage
        peak = max(peak, equity)
        drawdown = -1.0 if equity <= 0.0 else equity / peak - 1.0
        if drawdown < mdd:
            mdd = drawdown
            worst_ts = ts.isoformat()
            worst_trade = trade_index
        if qty and mark_price and equity > 0:
            max_marked_leverage = max(max_marked_leverage, abs(qty) * mark_price / equity)

    for ts, kind, payload in marks:
        if kind == "mark":
            price = float(payload)
            if qty and mark_price is not None:
                equity += qty * (price - mark_price)
            if math.isfinite(price) and price > 0:
                mark_price = price
            observe(ts, active_trade)
        elif kind == "funding" and qty:
            event = payload
            payment = qty * float(event.price) * float(event.rate)
            equity -= payment
            total_funding += payment
            observe(ts, active_trade)
        elif kind == "entry":
            trade_index, trade = payload
            if qty:
                raise RuntimeError("overlapping replay entry")
            price = float(trade["entry_price"])
            leverage = float(trade.get("entry_leverage", 1.0))
            target_side = 1 if str(trade["side"]) == "long" else -1
            old_equity = equity
            qty, equity, turnover = target_quantity(equity, qty, target_side, price, cost_rate, leverage)
            total_turnover += turnover
            total_cost += old_equity - equity
            mark_price = price
            active_trade = int(trade_index)
            observe(ts, active_trade)
        elif kind == "exit":
            trade_index, trade = payload
            price = float(trade["exit_price"])
            if qty and mark_price is not None:
                equity += qty * (price - mark_price)
            mark_price = price
            observe(ts, int(trade_index))
            old_equity = equity
            qty, equity, turnover = target_quantity(equity, qty, 0, price, cost_rate, 1.0)
            total_turnover += turnover
            total_cost += old_equity - equity
            qty = 0.0
            active_trade = None
            observe(ts, int(trade_index))
    return {
        "terminal_equity": equity,
        "chronological_1h_mdd_pct": mdd * 100.0,
        "worst_ts": worst_ts,
        "worst_trade_index": worst_trade,
        "turnover_multiple": total_turnover,
        "cost_pct_initial": total_cost * 100.0,
        "funding_pct_initial": total_funding * 100.0,
        "max_marked_leverage": max_marked_leverage,
        "parity": {
            "terminal_equity": math.isclose(
                equity, float(raw.metrics["equity_multiple"]), rel_tol=0.0, abs_tol=5e-4
            ),
        },
    }


def normalize(raw: Any, replay: dict[str, Any], result: Any, *, days: int) -> dict[str, Any]:
    metrics = raw.metrics
    equity_multiple = float(replay["terminal_equity"])
    counts = getattr(result, "activation_counts", {})
    return {
        "start_ts": metrics["start_ts"],
        "end_ts": metrics["end_ts"],
        "days": days,
        "equity_multiple": equity_multiple,
        "net_return_pct": (equity_multiple - 1.0) * 100.0,
        "raw_engine_net_return_pct": float(metrics["net_return_pct"]),
        "replay_engine_equity_delta": equity_multiple - float(metrics["equity_multiple"]),
        "raw_engine_mdd_pct": float(metrics["max_drawdown_pct"]),
        "chronological_1h_mdd_pct": float(replay["chronological_1h_mdd_pct"]),
        "closed_trades": int(metrics["closed_trades"]),
        "long_trades": int(metrics["long_trades"]),
        "short_trades": int(metrics["short_trades"]),
        "win_rate": float(metrics["win_rate"]),
        "profit_factor": float(metrics["profit_factor"]),
        "turnover_multiple": float(replay["turnover_multiple"]),
        "cost_pct_initial": float(replay["cost_pct_initial"]),
        "funding_pct_initial": float(replay["funding_pct_initial"]),
        "max_marked_leverage": float(replay["max_marked_leverage"]),
        "worst_ts": replay["worst_ts"],
        "worst_trade_index": replay["worst_trade_index"],
        "long_trail_exit": int(counts.get("long_trail_exit", 0)),
        "short_rsi_exit": int(counts.get("short_rsi_exit", 0)),
        "protective_stop": int(counts.get("protective_stop", 0)),
        "handoff_accept": int(counts.get("handoff_accept", 0)),
        "shadow_start": int(counts.get("shadow_start", 0)),
    }


def fixed_pehc(engine: ModuleType, *, arm_id: str = "PEHC_294", **changes: Any) -> Any:
    row = {
        "arm_id": arm_id,
        "expiry_days": 8,
        "slope_threshold": None,
        "chase_cap_atr": math.inf,
        "execution": "next_utc_open",
        "enabled": True,
        "entry_enabled": True,
    }
    row.update(changes)
    return engine.PEHCConfig(**row)


def oapp_config(engine: ModuleType, *, arm_id: str = "OAPP", **changes: Any) -> Any:
    oapp = engine._OAPP
    row = {
        "arm_id": arm_id,
        "entry": oapp.EntryFilter(),
        "long_exit": oapp.TrailExit("fraction", 0.5, 0.10, 2),
        "short_exit": oapp.TrailExit(),
        "short_rsi": oapp.ShortRSIExit(20.0, 2),
        "roundtrip_guard": 0.0028,
    }
    row.update(changes)
    return oapp.WTLConfig(**row)


def variant_config(value: Any) -> Any:
    if hasattr(value, "canonical"):
        return value.canonical()
    if hasattr(value, "__dataclass_fields__"):
        return {
            key: variant_config(getattr(value, key))
            for key in value.__dataclass_fields__
        }
    return value


def value_slug(value: Any) -> str:
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if math.isinf(value):
            return "inf"
        text = f"{value:g}".replace("-", "m").replace(".", "p")
        return text
    return str(value).replace("-", "m").replace(".", "p")


def add_unique_variant(rows: list[Variant], seen: set[str], variant: Variant) -> None:
    key = canonical_hash(
        {
            "long": variant_config(variant.long_config),
            "short": variant_config(variant.short_config),
            "oapp": variant_config(variant.oapp_config),
            "pehc": variant_config(variant.pehc_config),
        }
    )
    if key in seen:
        return
    seen.add(key)
    rows.append(variant)


def build_variants(engine: ModuleType, context: Any) -> list[Variant]:
    long = context.long_config
    short = context.short_config
    oapp = engine._OAPP
    base_oapp = oapp_config(engine, arm_id="V6_OAPP")
    base_pehc = fixed_pehc(engine, arm_id="PEHC_294")

    def make(
        name: str,
        group: str,
        change: str,
        *,
        long_config: Any = long,
        short_config: Any = short,
        oapp_row: Any = base_oapp,
        pehc_row: Any = base_pehc,
    ) -> Variant:
        return Variant(name, group, change, long_config, short_config, oapp_row, pehc_row)

    rows = [
        make("exact_v6", "baseline", "registered V6"),
        make(
            "v5_no_pehc",
            "module",
            "disable PEHC actual handoff",
            pehc_row=fixed_pehc(engine, arm_id="NO_PEHC", enabled=False),
        ),
        make(
            "v4_no_oapp_no_pehc",
            "module",
            "disable OAPP and PEHC",
            oapp_row=oapp_config(engine, arm_id="NO_OAPP", long_exit=oapp.TrailExit(), short_rsi=oapp.ShortRSIExit()),
            pehc_row=fixed_pehc(engine, arm_id="NO_OAPP_NO_PEHC", enabled=False),
        ),
        make(
            "pehc_shadow_only_no_actual_entry",
            "pehc",
            "PEHC shadows only; entry_enabled=false",
            pehc_row=fixed_pehc(engine, arm_id="PEHC_SHADOW_ONLY", entry_enabled=False),
        ),
        make("long_entry_slope_direction_only", "entry_slope", "long slope_min_atr 0.02 -> 0", long_config=replace(long, slope_min_atr=0.0)),
        make("long_entry_slope_removed", "entry_slope", "bypass long entry slope gate", long_config=replace(long, slope_min_atr=NO_SLOPE_GATE)),
        make("short_entry_slope_direction_only", "entry_slope", "short slope_min_atr 0.02 -> 0", short_config=replace(short, slope_min_atr=0.0)),
        make("short_entry_slope_removed", "entry_slope", "bypass short natural-entry slope gate", short_config=replace(short, slope_min_atr=NO_SLOPE_GATE)),
        make(
            "both_entry_slopes_removed",
            "entry_slope",
            "bypass both natural-entry slope gates",
            long_config=replace(long, slope_min_atr=NO_SLOPE_GATE),
            short_config=replace(short, slope_min_atr=NO_SLOPE_GATE),
        ),
        make(
            "short_slope_exit_removed",
            "exit_slope",
            "short slope_exit_lookback 1 -> 0",
            short_config=replace(short, slope_exit_lookback=0),
        ),
        make(
            "all_slopes_removed",
            "entry_slope",
            "bypass both entry slopes and remove short slope exit",
            long_config=replace(long, slope_min_atr=NO_SLOPE_GATE),
            short_config=replace(short, slope_min_atr=NO_SLOPE_GATE, slope_exit_lookback=0),
        ),
        make("long_reclaim_removed_regime", "entry_event", "long entry_mode reclaim -> regime", long_config=replace(long, entry_mode="regime")),
        make("short_reclaim_removed_regime", "entry_event", "short entry_mode reclaim -> regime", short_config=replace(short, entry_mode="regime")),
        make(
            "both_reclaims_removed_regime",
            "entry_event",
            "both entry_mode reclaim -> regime",
            long_config=replace(long, entry_mode="regime"),
            short_config=replace(short, entry_mode="regime"),
        ),
        make("short_entry_buffer_removed", "entry_buffer", "short entry_buffer_atr 0.10 -> 0", short_config=replace(short, entry_buffer_atr=0.0)),
        make("short_entry_buffer_025", "entry_buffer", "short entry_buffer_atr 0.10 -> 0.25", short_config=replace(short, entry_buffer_atr=0.25)),
        make("natural_long_entry_removed", "component", "disable natural long entries", long_config=replace(long, slope_min_atr=NO_NATURAL_ENTRY)),
        make("natural_short_entry_removed", "component", "disable natural short entries; keep handoff/forced shorts", short_config=replace(short, slope_min_atr=NO_NATURAL_ENTRY)),
        make("long_exit_hysteresis_buffer_removed", "exit_buffer", "long exit_buffer_atr 0.75 -> 0", long_config=replace(long, exit_buffer_atr=0.0)),
        make("long_exit_hysteresis_buffer_025", "exit_buffer", "long exit_buffer_atr 0.75 -> 0.25", long_config=replace(long, exit_buffer_atr=0.25)),
        make("long_exit_hysteresis_buffer_100", "exit_buffer", "long exit_buffer_atr 0.75 -> 1.00", long_config=replace(long, exit_buffer_atr=1.0)),
        make("short_exit_hysteresis_buffer_removed", "exit_buffer", "short exit_buffer_atr 0.75 -> 0", short_config=replace(short, exit_buffer_atr=0.0)),
        make("short_exit_hysteresis_buffer_025", "exit_buffer", "short exit_buffer_atr 0.75 -> 0.25", short_config=replace(short, exit_buffer_atr=0.25)),
        make("short_exit_hysteresis_buffer_100", "exit_buffer", "short exit_buffer_atr 0.75 -> 1.00", short_config=replace(short, exit_buffer_atr=1.0)),
        make("long_trailing_stop_removed", "protection", "long trail_atr 1.5 -> 0", long_config=replace(long, trail_atr=0.0)),
        make("long_trailing_stop_100", "protection", "long trail_atr 1.5 -> 1.0", long_config=replace(long, trail_atr=1.0)),
        make("long_trailing_stop_200", "protection", "long trail_atr 1.5 -> 2.0", long_config=replace(long, trail_atr=2.0)),
        make("short_hard_stop_removed", "protection", "short hard_stop_atr 1.5 -> 0", short_config=replace(short, hard_stop_atr=0.0)),
        make("short_hard_stop_100", "protection", "short hard_stop_atr 1.5 -> 1.0", short_config=replace(short, hard_stop_atr=1.0)),
        make("short_hard_stop_200", "protection", "short hard_stop_atr 1.5 -> 2.0", short_config=replace(short, hard_stop_atr=2.0)),
        make("short_trailing_stop_removed", "protection", "short trail_atr 4.0 -> 0", short_config=replace(short, trail_atr=0.0)),
        make("short_trailing_stop_300", "protection", "short trail_atr 4.0 -> 3.0", short_config=replace(short, trail_atr=3.0)),
        make("short_trailing_stop_500", "protection", "short trail_atr 4.0 -> 5.0", short_config=replace(short, trail_atr=5.0)),
        make("long_max_hold_removed", "max_hold", "long max_hold_days 90 -> 0", long_config=replace(long, max_hold_days=0)),
        make("short_max_hold_removed", "max_hold", "short max_hold_days 20 -> 0", short_config=replace(short, max_hold_days=0)),
        make("short_max_hold_10", "max_hold", "short max_hold_days 20 -> 10", short_config=replace(short, max_hold_days=10)),
        make("short_max_hold_30", "max_hold", "short max_hold_days 20 -> 30", short_config=replace(short, max_hold_days=30)),
        make("long_cooldown_removed", "cooldown", "long cooldown_days 2 -> 0", long_config=replace(long, cooldown_days=0)),
        make("long_cooldown_1", "cooldown", "long cooldown_days 2 -> 1", long_config=replace(long, cooldown_days=1)),
        make("long_cooldown_3", "cooldown", "long cooldown_days 2 -> 3", long_config=replace(long, cooldown_days=3)),
        make("short_cooldown_removed", "cooldown", "short cooldown_days 5 -> 0", short_config=replace(short, cooldown_days=0)),
        make("short_cooldown_2", "cooldown", "short cooldown_days 5 -> 2", short_config=replace(short, cooldown_days=2)),
        make("short_cooldown_8", "cooldown", "short cooldown_days 5 -> 8", short_config=replace(short, cooldown_days=8)),
        make("both_cooldowns_removed", "cooldown", "both cooldown_days -> 0", long_config=replace(long, cooldown_days=0), short_config=replace(short, cooldown_days=0)),
        make("oapp_long_exit_off", "oapp_long", "OAPP long MFE fraction exit off", oapp_row=oapp_config(engine, arm_id="OAPP_LONG_OFF", long_exit=oapp.TrailExit())),
        make("oapp_long_activation_075", "oapp_long", "long OAPP activation 0.5 -> 0.75", oapp_row=oapp_config(engine, arm_id="OAPP_L_ACT075", long_exit=oapp.TrailExit("fraction", 0.75, 0.10, 2))),
        make("oapp_long_activation_100", "oapp_long", "long OAPP activation 0.5 -> 1.0", oapp_row=oapp_config(engine, arm_id="OAPP_L_ACT100", long_exit=oapp.TrailExit("fraction", 1.0, 0.10, 2))),
        make("oapp_long_giveback_015", "oapp_long", "long OAPP giveback 0.10 -> 0.15", oapp_row=oapp_config(engine, arm_id="OAPP_L_GB015", long_exit=oapp.TrailExit("fraction", 0.5, 0.15, 2))),
        make("oapp_long_giveback_020", "oapp_long", "long OAPP giveback 0.10 -> 0.20", oapp_row=oapp_config(engine, arm_id="OAPP_L_GB020", long_exit=oapp.TrailExit("fraction", 0.5, 0.20, 2))),
        make("oapp_long_confirm_1", "oapp_long", "long OAPP confirm_days 2 -> 1", oapp_row=oapp_config(engine, arm_id="OAPP_L_C1", long_exit=oapp.TrailExit("fraction", 0.5, 0.10, 1))),
        make("oapp_long_confirm_3", "oapp_long", "long OAPP confirm_days 2 -> 3", oapp_row=oapp_config(engine, arm_id="OAPP_L_C3", long_exit=oapp.TrailExit("fraction", 0.5, 0.10, 3))),
        make("short_rsi_exit_off", "oapp_short_rsi", "short RSI6 profit exit off", oapp_row=oapp_config(engine, arm_id="OAPP_RSI_OFF", short_rsi=oapp.ShortRSIExit())),
        make("short_rsi_threshold_15", "oapp_short_rsi", "short RSI6 threshold 20 -> 15", oapp_row=oapp_config(engine, arm_id="OAPP_RSI_T15", short_rsi=oapp.ShortRSIExit(15.0, 2))),
        make("short_rsi_threshold_25", "oapp_short_rsi", "short RSI6 threshold 20 -> 25", oapp_row=oapp_config(engine, arm_id="OAPP_RSI_T25", short_rsi=oapp.ShortRSIExit(25.0, 2))),
        make("short_rsi_threshold_30", "oapp_short_rsi", "short RSI6 threshold 20 -> 30", oapp_row=oapp_config(engine, arm_id="OAPP_RSI_T30", short_rsi=oapp.ShortRSIExit(30.0, 2))),
        make("short_rsi_days_1", "oapp_short_rsi", "short RSI6 days 2 -> 1", oapp_row=oapp_config(engine, arm_id="OAPP_RSI_D1", short_rsi=oapp.ShortRSIExit(20.0, 1))),
        make("short_rsi_days_3", "oapp_short_rsi", "short RSI6 days 2 -> 3", oapp_row=oapp_config(engine, arm_id="OAPP_RSI_D3", short_rsi=oapp.ShortRSIExit(20.0, 3))),
        make("pehc_expiry_5", "pehc", "PEHC expiry_days 8 -> 5", pehc_row=fixed_pehc(engine, arm_id="PEHC_EXP5", expiry_days=5)),
        make("pehc_expiry_13", "pehc", "PEHC expiry_days 8 -> 13", pehc_row=fixed_pehc(engine, arm_id="PEHC_EXP13", expiry_days=13)),
        make("pehc_expiry_21", "pehc", "PEHC expiry_days 8 -> 21", pehc_row=fixed_pehc(engine, arm_id="PEHC_EXP21", expiry_days=21)),
        make("pehc_slope_000", "pehc", "PEHC handoff slope_threshold None -> 0.0", pehc_row=fixed_pehc(engine, arm_id="PEHC_S000", slope_threshold=0.0)),
        make("pehc_slope_002", "pehc", "PEHC handoff slope_threshold None -> 0.02", pehc_row=fixed_pehc(engine, arm_id="PEHC_S002", slope_threshold=0.02)),
        make("pehc_chase_cap_075", "pehc", "PEHC chase_cap INF -> 0.75 ATR", pehc_row=fixed_pehc(engine, arm_id="PEHC_CH075", chase_cap_atr=0.75)),
        make("pehc_chase_cap_150", "pehc", "PEHC chase_cap INF -> 1.50 ATR", pehc_row=fixed_pehc(engine, arm_id="PEHC_CH150", chase_cap_atr=1.50)),
        make("pehc_chase_cap_200", "pehc", "PEHC chase_cap INF -> 2.00 ATR", pehc_row=fixed_pehc(engine, arm_id="PEHC_CH200", chase_cap_atr=2.00)),
        make("pehc_same_1h_open", "pehc", "PEHC execution next_utc_open -> same_1h_open", pehc_row=fixed_pehc(engine, arm_id="PEHC_SAME1H", execution="same_1h_open")),
    ]
    output: list[Variant] = []
    seen: set[str] = set()
    for row in rows:
        add_unique_variant(output, seen, row)

    config_domains: dict[str, tuple[Any, ...]] = {
        "slope_lookback": (1, 2, 3, 5, 7),
        "slope_min_atr": (NO_SLOPE_GATE, 0.0, 0.02, 0.05, 0.10, 0.20, NO_NATURAL_ENTRY),
        "confirm_days": (1, 2, 3),
        "entry_buffer_atr": (0.0, 0.10, 0.25, 0.50),
        "pullback_lookback": (2, 3, 5, 7, 10),
        "pullback_touch_atr": (-0.50, -0.25, 0.0, 0.10, 0.25),
        "breakout_lookback": (2, 3, 5, 7, 10, 14),
        "exit_confirm_days": (1, 2, 3),
        "exit_buffer_atr": (0.0, 0.10, 0.25, 0.50, 0.75, 1.0),
        "slope_exit_lookback": (0, 1, 2, 3, 5),
        "hard_stop_atr": (0.0, 1.5, 2.0, 3.0, 4.0, 5.0),
        "trail_atr": (0.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0),
        "max_hold_days": (0, 10, 20, 30, 60, 90),
        "cooldown_days": (0, 1, 2, 3, 5, 8, 10),
    }
    entry_modes = {
        "long": ("regime", "reclaim", "pullback_reclaim", "breakout"),
        "short": ("regime", "reclaim", "pullback_reclaim", "breakout", "open_regime"),
    }
    for side_name, side_config in (("long", long), ("short", short)):
        for mode in entry_modes[side_name]:
            if mode == side_config.entry_mode:
                continue
            changed = replace(side_config, entry_mode=mode)
            add_unique_variant(
                output,
                seen,
                make(
                    f"n_{side_name}_entry_mode_{mode}",
                    f"neighborhood_{side_name}_config",
                    f"{side_name} entry_mode {side_config.entry_mode} -> {mode}",
                    long_config=changed if side_name == "long" else long,
                    short_config=changed if side_name == "short" else short,
                ),
            )
        for field, values in config_domains.items():
            base_value = getattr(side_config, field)
            for value in values:
                if value == base_value:
                    continue
                changed = replace(side_config, **{field: value})
                add_unique_variant(
                    output,
                    seen,
                    make(
                        f"n_{side_name}_{field}_{value_slug(value)}",
                        f"neighborhood_{side_name}_config",
                        f"{side_name} {field} {base_value} -> {value}",
                        long_config=changed if side_name == "long" else long,
                        short_config=changed if side_name == "short" else short,
                    ),
                )

    for value in engine._OAPP.TRAIL_ACTIVATIONS:
        add_unique_variant(
            output,
            seen,
            make(
                f"n_oapp_long_activation_{value_slug(value)}",
                "neighborhood_oapp_long",
                f"OAPP long activation 0.5 -> {value}",
                oapp_row=oapp_config(
                    engine,
                    arm_id=f"N_OAPP_L_ACT_{value_slug(value)}",
                    long_exit=oapp.TrailExit("fraction", value, 0.10, 2),
                ),
            ),
        )
    for value in engine._OAPP.TRAIL_FRACTIONS:
        add_unique_variant(
            output,
            seen,
            make(
                f"n_oapp_long_giveback_{value_slug(value)}",
                "neighborhood_oapp_long",
                f"OAPP long giveback 0.10 -> {value}",
                oapp_row=oapp_config(
                    engine,
                    arm_id=f"N_OAPP_L_GB_{value_slug(value)}",
                    long_exit=oapp.TrailExit("fraction", 0.5, value, 2),
                ),
            ),
        )
    for value in engine._OAPP.TRAIL_CONFIRM_DAYS:
        add_unique_variant(
            output,
            seen,
            make(
                f"n_oapp_long_confirm_{value_slug(value)}",
                "neighborhood_oapp_long",
                f"OAPP long confirm_days 2 -> {value}",
                oapp_row=oapp_config(
                    engine,
                    arm_id=f"N_OAPP_L_C_{value_slug(value)}",
                    long_exit=oapp.TrailExit("fraction", 0.5, 0.10, value),
                ),
            ),
        )
    add_unique_variant(
        output,
        seen,
        make(
            "n_oapp_long_mode_off",
            "neighborhood_oapp_long",
            "OAPP long exit fraction -> off",
            oapp_row=oapp_config(engine, arm_id="N_OAPP_L_OFF", long_exit=oapp.TrailExit()),
        ),
    )
    for value in engine._OAPP.RSI_THRESHOLDS:
        add_unique_variant(
            output,
            seen,
            make(
                f"n_short_rsi_threshold_{value_slug(value)}",
                "neighborhood_oapp_short_rsi",
                f"short RSI6 threshold 20 -> {value}",
                oapp_row=oapp_config(
                    engine,
                    arm_id=f"N_OAPP_RSI_T_{value_slug(value)}",
                    short_rsi=oapp.ShortRSIExit(value, 2),
                ),
            ),
        )
    for value in engine._OAPP.RSI_DAYS:
        add_unique_variant(
            output,
            seen,
            make(
                f"n_short_rsi_days_{value_slug(value)}",
                "neighborhood_oapp_short_rsi",
                f"short RSI6 days 2 -> {value}",
                oapp_row=oapp_config(
                    engine,
                    arm_id=f"N_OAPP_RSI_D_{value_slug(value)}",
                    short_rsi=oapp.ShortRSIExit(20.0, value),
                ),
            ),
        )
    add_unique_variant(
        output,
        seen,
        make(
            "n_short_rsi_off",
            "neighborhood_oapp_short_rsi",
            "short RSI6 exit -> off",
            oapp_row=oapp_config(engine, arm_id="N_OAPP_RSI_OFF", short_rsi=oapp.ShortRSIExit()),
        ),
    )

    for value in engine.EXPIRY_DAYS:
        add_unique_variant(
            output,
            seen,
            make(
                f"n_pehc_expiry_{value_slug(value)}",
                "neighborhood_pehc",
                f"PEHC expiry_days 8 -> {value}",
                pehc_row=fixed_pehc(engine, arm_id=f"N_PEHC_EXP_{value_slug(value)}", expiry_days=value),
            ),
        )
    for value in engine.SLOPE_THRESHOLDS:
        add_unique_variant(
            output,
            seen,
            make(
                f"n_pehc_slope_{value_slug(value)}",
                "neighborhood_pehc",
                f"PEHC slope_threshold None -> {value}",
                pehc_row=fixed_pehc(engine, arm_id=f"N_PEHC_S_{value_slug(value)}", slope_threshold=value),
            ),
        )
    for value in engine.CHASE_CAPS:
        add_unique_variant(
            output,
            seen,
            make(
                f"n_pehc_chase_{value_slug(value)}",
                "neighborhood_pehc",
                f"PEHC chase_cap_atr INF -> {value}",
                pehc_row=fixed_pehc(engine, arm_id=f"N_PEHC_CH_{value_slug(value)}", chase_cap_atr=value),
            ),
        )
    for value in engine.EXECUTIONS:
        add_unique_variant(
            output,
            seen,
            make(
                f"n_pehc_execution_{value}",
                "neighborhood_pehc",
                f"PEHC execution next_utc_open -> {value}",
                pehc_row=fixed_pehc(engine, arm_id=f"N_PEHC_EX_{value}", execution=value),
            ),
        )
    for field, value in (("enabled", False), ("entry_enabled", False)):
        add_unique_variant(
            output,
            seen,
            make(
                f"n_pehc_{field}_false",
                "neighborhood_pehc",
                f"PEHC {field} True -> False",
                pehc_row=fixed_pehc(engine, arm_id=f"N_PEHC_{field.upper()}_FALSE", **{field: value}),
            ),
        )

    if len({row.name for row in output}) != len(output):
        raise RuntimeError("duplicate variant name")
    return output


def run_variant(
    engine: ModuleType,
    context: Any,
    variant: Variant,
    *,
    window: tuple[int, int],
    slippage: float,
    signal_lag: int,
    include_funding: bool,
    retain: bool,
) -> tuple[dict[str, Any], Any]:
    rsi6 = engine._BASE.wilder_rsi6(context.book.close)
    entry_signal = engine._BASE.EntryQualitySignal(context.engine, variant.oapp_config.entry)
    leverage_policy = engine._BASE.LeveragePolicy(context, None)
    recorder = engine.HandoffRecorder()
    function, source_hash = engine.build_variant_function(
        context,
        variant.pehc_config,
        oapp_config=variant.oapp_config,
        entry_signal=entry_signal,
        leverage_policy=leverage_policy,
        rsi6=rsi6,
        recorder=recorder,
    )
    left, right = window
    raw = function(
        context.book,
        context.features,
        long_config=variant.long_config,
        short_config=variant.short_config,
        start_index=start_for(window),
        terminal_index=right,
        slippage=slippage,
        signal_lag=signal_lag,
        include_funding=include_funding,
        retain=retain,
    )
    if bool(raw.metrics.get("bankrupt_intraday")):
        raise RuntimeError(f"{variant.name} became bankrupt")
    handoff_events = list(recorder.events)
    result = engine.PEHCExecutionResult(
        config=variant.pehc_config,
        raw=raw,
        source_sha256=source_hash,
        entry_events=list(entry_signal.events),
        leverage_events=list(leverage_policy.events),
        handoff_events=handoff_events,
        activation_counts={
            "shadow_start": sum(row["event"] == "shadow_start" for row in handoff_events),
            "handoff_accept": sum(row["event"] == "handoff_accept" for row in handoff_events),
            "long_trail_exit": sum(
                str(trade.get("exit_reason", "")).startswith("long_mfe_")
                for trade in raw.trades
            ),
            "short_rsi_exit": sum(
                str(trade.get("exit_reason", "")) == "short_rsi_take_profit"
                for trade in raw.trades
            ),
            "protective_stop": sum(
                str(trade.get("exit_reason", "")) == "protective_stop"
                for trade in raw.trades
            ),
        },
        rsi6=rsi6,
    )
    replay = chronological_replay(context, raw, slippage=slippage, include_funding=include_funding)
    row = normalize(raw, replay, result, days=right - left)
    row["source_sha256"] = source_hash
    return row, result


def verdict(control: dict[str, Any], stress: dict[str, dict[str, Any]]) -> dict[str, Any]:
    full = stress["base_full"]
    high_cost = stress["slippage_8bps"]
    lag = stress["lag_1d"]
    blocks = [row for key, row in stress.items() if key.startswith("block_")]
    ret_delta = full["net_return_pct"] - control["net_return_pct"]
    mdd_delta = full["chronological_1h_mdd_pct"] - control["chronological_1h_mdd_pct"]
    block_positive = sum(row["net_return_pct"] > 0.0 for row in blocks)
    mdd_not_worse = mdd_delta >= -MDD_TOLERANCE
    return {
        "ret_delta_vs_v6_pp": ret_delta,
        "mdd_delta_vs_v6_pp": mdd_delta,
        "full_ret_better": ret_delta > 0.0,
        "full_mdd_better": mdd_not_worse,
        "full_dual_better": ret_delta > 0.0 and mdd_not_worse,
        "stress_8bps_positive": high_cost["net_return_pct"] > 0.0,
        "lag_1d_positive": lag["net_return_pct"] > 0.0,
        "block_positive_count": block_positive,
        "block_count": len(blocks),
        "decision": (
            "DIAGNOSTIC_CANDIDATE"
            if ret_delta > 0.0
            and mdd_not_worse
            and high_cost["net_return_pct"] > 0.0
            and lag["net_return_pct"] > 0.0
            and block_positive == len(blocks)
            else "FAIL"
        ),
    }


def summarize_by_group(ranking: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in ranking:
        groups.setdefault(str(row["group"]), []).append(row)
    return {
        group: {
            "count": len(rows),
            "best_by_return": max(rows, key=lambda row: row["net_return_pct"])["name"],
            "best_return_pct": max(row["net_return_pct"] for row in rows),
            "best_mdd_pct": max(row["chronological_1h_mdd_pct"] for row in rows),
            "dual_better_count": sum(bool(row["full_dual_better"]) for row in rows),
        }
        for group, rows in sorted(groups.items())
    }


def run(force: bool) -> dict[str, Any]:
    engine = load_module(ENGINE_PATH, "v6_full_ablation_engine")
    adapter = load_module(ADAPTER_PATH, "v6_full_ablation_adapter")
    context = adapter.load_context()
    variants = build_variants(engine, context)
    candidates: dict[str, Any] = {}
    control_base: dict[str, Any] | None = None
    for index, variant in enumerate(variants, 1):
        print(f"[{index:02d}/{len(variants)}] {variant.name}")
        stress: dict[str, dict[str, Any]] = {}
        base_full, retained = run_variant(
            engine,
            context,
            variant,
            window=FULL,
            slippage=BASE_SLIPPAGE,
            signal_lag=0,
            include_funding=True,
            retain=True,
        )
        stress["base_full"] = base_full
        stress["slippage_8bps"], _ = run_variant(
            engine,
            context,
            variant,
            window=FULL,
            slippage=STRESS_SLIPPAGE,
            signal_lag=0,
            include_funding=True,
            retain=False,
        )
        stress["funding_off"], _ = run_variant(
            engine,
            context,
            variant,
            window=FULL,
            slippage=BASE_SLIPPAGE,
            signal_lag=0,
            include_funding=False,
            retain=False,
        )
        stress["lag_1d"], _ = run_variant(
            engine,
            context,
            variant,
            window=FULL,
            slippage=BASE_SLIPPAGE,
            signal_lag=1,
            include_funding=True,
            retain=False,
        )
        for block_index, window in enumerate(BLOCKS):
            stress[f"block_{block_index:02d}"], _ = run_variant(
                engine,
                context,
                variant,
                window=window,
                slippage=BASE_SLIPPAGE,
                signal_lag=0,
                include_funding=True,
                retain=False,
            )
        for label, days in RECENT_SLICES.items():
            left = max(0, FULL[1] - days)
            stress[f"recent_{label}"], _ = run_variant(
                engine,
                context,
                variant,
                window=(left, FULL[1]),
                slippage=BASE_SLIPPAGE,
                signal_lag=0,
                include_funding=True,
                retain=False,
            )
        if variant.name == "exact_v6":
            control_base = base_full
            if not math.isclose(base_full["net_return_pct"], EXPECTED_V6_RETURN, abs_tol=0.05):
                raise RuntimeError("V6 return anchor drift")
            if not math.isclose(base_full["chronological_1h_mdd_pct"], EXPECTED_V6_1H_MDD, abs_tol=0.01):
                raise RuntimeError("V6 chronological MDD anchor drift")
            if base_full["closed_trades"] != EXPECTED_V6_TRADES:
                raise RuntimeError("V6 trade-count anchor drift")
        if control_base is None:
            control_for_verdict = base_full
        else:
            control_for_verdict = control_base
        candidates[variant.name] = {
            "name": variant.name,
            "group": variant.group,
            "change": variant.change,
            "config": {
                "long_config": variant_config(variant.long_config),
                "short_config": variant_config(variant.short_config),
                "oapp_config": variant_config(variant.oapp_config),
                "pehc_config": variant_config(variant.pehc_config),
            },
            "config_sha256": canonical_hash(
                {
                    "long": variant_config(variant.long_config),
                    "short": variant_config(variant.short_config),
                    "oapp": variant_config(variant.oapp_config),
                    "pehc": variant_config(variant.pehc_config),
                }
            ),
            "source_sha256": retained.source_sha256,
            "stress": stress,
            "verdict": verdict(control_for_verdict, stress),
            "trades": retained.raw.trades,
            "handoff_events": retained.handoff_events,
            "entry_events": retained.entry_events,
        }

    assert control_base is not None
    # Recompute all verdicts against the final exact_v6 control.
    for row in candidates.values():
        row["verdict"] = verdict(control_base, row["stress"])

    ranking = sorted(
        (
            {
                "name": name,
                "group": row["group"],
                "change": row["change"],
                **row["stress"]["base_full"],
                **row["verdict"],
            }
            for name, row in candidates.items()
        ),
        key=lambda row: (row["decision"] != "DIAGNOSTIC_CANDIDATE", -row["net_return_pct"], row["chronological_1h_mdd_pct"]),
    )
    payload = {
        "study": "HYPE-1D-MA7-ABT-V6 full active-parameter ablation",
        "role": "diagnostic-only / post-reveal / not promoted / not live-ready",
        "market": "Binance USD-M HYPEUSDT perpetual",
        "timeframes": {"decision": "1d UTC", "risk_replay": "1h"},
        "data_range": {
            "start": str(context.book.ts[FULL[0]]),
            "end": str(context.book.ts[FULL[1] - 1]),
            "terminal_ts": str(context.book.terminal_ts),
            "daily_bars": FULL[1] - FULL[0],
        },
        "cost_model": {
            "fee_per_fill": 0.001,
            "base_slippage_per_fill": BASE_SLIPPAGE,
            "stress_slippage_per_fill": STRESS_SLIPPAGE,
            "funding": "actual Binance funding events when include_funding=true",
        },
        "scope": {
            "variant_count": len(variants),
            "method": "one-at-a-time active-parameter ablation plus small local-neighborhood perturbations around registered V6",
            "no_version_registration": True,
            "no_html": True,
        },
        "implementation_sha256": {
            "audit_script": sha256(SELF_PATH),
            "pehc_engine": sha256(ENGINE_PATH),
            "adapter": sha256(ADAPTER_PATH),
        },
        "control": control_base,
        "ranking": ranking,
        "group_summary": summarize_by_group(ranking),
        "candidates": candidates,
    }
    payload["payload_sha256"] = canonical_hash(payload)
    payload["artifact_sha256"] = write_json(OUTPUT_PATH, payload, force=force)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    payload = run(force=args.force)
    print(json.dumps(sanitize(payload["ranking"][:20]), ensure_ascii=False, indent=2, allow_nan=False))
    print(f"wrote {OUTPUT_PATH}")
    print(f"sha256 {payload['artifact_sha256']}")


if __name__ == "__main__":
    main()
