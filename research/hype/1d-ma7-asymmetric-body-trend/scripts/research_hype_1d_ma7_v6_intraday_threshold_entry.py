"""Backtest intraday ATR-threshold entry overlays on HYPE MA7 ABT V6."""

from __future__ import annotations

import argparse
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
ENGINE_PATH = SCRIPT_DIR / "hype_1d_ma7_v6_intraday_threshold_entry_engine.py"
ADAPTER_PATH = SCRIPT_DIR / "hype_1d_ma7_v4_fair_adapter.py"
SELF_PATH = Path(__file__).resolve()
OUTPUT_PATH = ARTIFACT_DIR / "hype_1d_ma7_v6_intraday_threshold_entry_2026-08-11.json"

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


def load_runtime() -> tuple[ModuleType, Any]:
    engine = load_module(ENGINE_PATH, "v6_intraday_threshold_engine")
    adapter = load_module(ADAPTER_PATH, "v6_intraday_threshold_adapter")
    return engine, adapter.load_context()


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
                raise RuntimeError("overlapping threshold replay entry")
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


def normalize(
    raw: Any,
    replay: dict[str, Any],
    *,
    result: Any | None = None,
    days: int,
) -> dict[str, Any]:
    metrics = raw.metrics
    equity_multiple = float(replay["terminal_equity"])
    counts = getattr(result, "activation_counts", {}) if result is not None else {}
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
        "threshold_entry": int(counts.get("threshold_entry", 0)),
        "threshold_ambiguous": int(counts.get("threshold_ambiguous", 0)),
        "long_trail_exit": int(counts.get("long_trail_exit", 0)),
        "short_rsi_exit": int(counts.get("short_rsi_exit", 0)),
        "protective_stop": int(counts.get("protective_stop", 0)),
        "handoff_accept": int(counts.get("handoff_accept", 0)),
        "shadow_start": int(counts.get("shadow_start", 0)),
    }


def summarize_events(result: Any) -> dict[str, Any]:
    events = [row for row in result.threshold_events if row.get("event") == "threshold_entry"]
    hours = [int(row["hour"]) for row in events]
    long_count = sum(int(row["side"]) > 0 for row in events)
    short_count = sum(int(row["side"]) < 0 for row in events)
    return {
        "entries": len(events),
        "long_entries": long_count,
        "short_entries": short_count,
        "median_hour": None if not hours else float(pd.Series(hours).median()),
        "mean_hour": None if not hours else float(pd.Series(hours).mean()),
        "early_0_6h": sum(hour <= 6 for hour in hours),
        "events": events,
    }


def evaluate_control(
    engine: ModuleType,
    context: Any,
    *,
    window: tuple[int, int],
    slippage: float,
    signal_lag: int,
    include_funding: bool,
    retain: bool,
) -> dict[str, Any]:
    left, right = window
    raw_result = engine.run_v6(
        context,
        start_index=start_for(window),
        terminal_index=right,
        slippage=slippage,
        signal_lag=signal_lag,
        include_funding=include_funding,
        retain=retain,
    )
    replay = chronological_replay(context, raw_result.raw, slippage=slippage, include_funding=include_funding)
    return normalize(raw_result.raw, replay, result=raw_result, days=right - left)


def evaluate_candidate(
    engine: ModuleType,
    context: Any,
    config: Any,
    *,
    window: tuple[int, int],
    slippage: float,
    signal_lag: int,
    include_funding: bool,
    retain: bool,
) -> tuple[dict[str, Any], Any]:
    left, right = window
    result = engine.run_variant(
        context,
        config,
        start_index=start_for(window),
        terminal_index=right,
        slippage=slippage,
        signal_lag=signal_lag,
        include_funding=include_funding,
        retain=retain,
    )
    replay = chronological_replay(context, result.raw, slippage=slippage, include_funding=include_funding)
    return normalize(result.raw, replay, result=result, days=right - left), result


def verdict(control: dict[str, Any], stress: dict[str, dict[str, Any]]) -> dict[str, Any]:
    full = stress["base_full"]
    lag = stress["lag_1d"]
    high_cost = stress["slippage_8bps"]
    blocks = [row for key, row in stress.items() if key.startswith("block_")]
    ret_delta = full["net_return_pct"] - control["net_return_pct"]
    mdd_delta = full["chronological_1h_mdd_pct"] - control["chronological_1h_mdd_pct"]
    block_positive = sum(row["net_return_pct"] > 0.0 for row in blocks)
    return {
        "ret_delta_vs_v6_pp": ret_delta,
        "mdd_delta_vs_v6_pp": mdd_delta,
        "full_dual_better": ret_delta > 0.0 and mdd_delta >= 0.0,
        "stress_8bps_positive": high_cost["net_return_pct"] > 0.0,
        "lag_1d_positive": lag["net_return_pct"] > 0.0,
        "block_positive_count": block_positive,
        "block_count": len(blocks),
        "decision": (
            "PASS_DIAGNOSTIC"
            if ret_delta > 0.0
            and mdd_delta >= 0.0
            and high_cost["net_return_pct"] > 0.0
            and lag["net_return_pct"] > 0.0
            and block_positive == len(blocks)
            else "FAIL"
        ),
    }


def run(force: bool) -> dict[str, Any]:
    engine, context = load_runtime()
    configs = engine.grid_configs()
    control_base = evaluate_control(
        engine,
        context,
        window=FULL,
        slippage=BASE_SLIPPAGE,
        signal_lag=0,
        include_funding=True,
        retain=True,
    )
    if not math.isclose(control_base["net_return_pct"], EXPECTED_V6_RETURN, abs_tol=0.05):
        raise RuntimeError("V6 return anchor drift")
    if not math.isclose(control_base["chronological_1h_mdd_pct"], EXPECTED_V6_1H_MDD, abs_tol=0.01):
        raise RuntimeError("V6 chronological MDD anchor drift")
    if control_base["closed_trades"] != EXPECTED_V6_TRADES:
        raise RuntimeError("V6 trade-count anchor drift")

    controls = {
        "base_full": control_base,
        "slippage_8bps": evaluate_control(
            engine,
            context,
            window=FULL,
            slippage=STRESS_SLIPPAGE,
            signal_lag=0,
            include_funding=True,
            retain=False,
        ),
        "funding_off": evaluate_control(
            engine,
            context,
            window=FULL,
            slippage=BASE_SLIPPAGE,
            signal_lag=0,
            include_funding=False,
            retain=False,
        ),
        "lag_1d": evaluate_control(
            engine,
            context,
            window=FULL,
            slippage=BASE_SLIPPAGE,
            signal_lag=1,
            include_funding=True,
            retain=False,
        ),
    }
    for idx, window in enumerate(BLOCKS):
        controls[f"block_{idx:02d}"] = evaluate_control(
            engine,
            context,
            window=window,
            slippage=BASE_SLIPPAGE,
            signal_lag=0,
            include_funding=True,
            retain=False,
        )
    for label, days in RECENT_SLICES.items():
        left = max(0, FULL[1] - days)
        controls[f"recent_{label}"] = evaluate_control(
            engine,
            context,
            window=(left, FULL[1]),
            slippage=BASE_SLIPPAGE,
            signal_lag=0,
            include_funding=True,
            retain=False,
        )

    candidates: dict[str, Any] = {}
    for config in configs:
        stress: dict[str, dict[str, Any]] = {}
        base_full, retained = evaluate_candidate(
            engine,
            context,
            config,
            window=FULL,
            slippage=BASE_SLIPPAGE,
            signal_lag=0,
            include_funding=True,
            retain=True,
        )
        stress["base_full"] = base_full
        stress["slippage_8bps"], _ = evaluate_candidate(
            engine,
            context,
            config,
            window=FULL,
            slippage=STRESS_SLIPPAGE,
            signal_lag=0,
            include_funding=True,
            retain=False,
        )
        stress["funding_off"], _ = evaluate_candidate(
            engine,
            context,
            config,
            window=FULL,
            slippage=BASE_SLIPPAGE,
            signal_lag=0,
            include_funding=False,
            retain=False,
        )
        stress["lag_1d"], _ = evaluate_candidate(
            engine,
            context,
            config,
            window=FULL,
            slippage=BASE_SLIPPAGE,
            signal_lag=1,
            include_funding=True,
            retain=False,
        )
        for idx, window in enumerate(BLOCKS):
            stress[f"block_{idx:02d}"], _ = evaluate_candidate(
                engine,
                context,
                config,
                window=window,
                slippage=BASE_SLIPPAGE,
                signal_lag=0,
                include_funding=True,
                retain=False,
            )
        for label, days in RECENT_SLICES.items():
            left = max(0, FULL[1] - days)
            stress[f"recent_{label}"], _ = evaluate_candidate(
                engine,
                context,
                config,
                window=(left, FULL[1]),
                slippage=BASE_SLIPPAGE,
                signal_lag=0,
                include_funding=True,
                retain=False,
            )
        candidates[config.arm_id] = {
            "config": config.canonical(),
            "config_sha256": engine.config_sha256(config),
            "source_sha256": retained.source_sha256,
            "event_summary": summarize_events(retained),
            "stress": stress,
            "verdict": verdict(control_base, stress),
            "trades": retained.raw.trades,
            "threshold_events": retained.threshold_events,
            "handoff_events": retained.handoff_events,
        }

    ranking = sorted(
        (
            {
                "arm_id": arm_id,
                "threshold_atr": row["config"]["threshold_atr"],
                **row["stress"]["base_full"],
                **row["verdict"],
            }
            for arm_id, row in candidates.items()
        ),
        key=lambda row: (row["decision"] != "PASS_DIAGNOSTIC", -row["net_return_pct"], row["chronological_1h_mdd_pct"]),
    )

    payload = {
        "study": "HYPE-1D-MA7-ABT-V6 intraday ATR-threshold entry diagnostic",
        "role": "diagnostic-only / not promoted / not live-ready",
        "market": "Binance USD-M HYPEUSDT perpetual",
        "timeframes": {"execution": "1h", "decision": "1d UTC"},
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
        "entry_rule": {
            "description": "flat状态下使用上一完整UTC日 SMA7/ATR7；上一日未越过阈值，当天1h high/low首次触及 MA7 +/- k*ATR7 即入场；同小时双向触发视为歧义并跳过。",
            "thresholds_atr": [config.threshold_atr for config in configs],
            "fresh_only": True,
            "lookahead": "none: no current-day close, current-day MA7, or same-day ATR is used for entry trigger",
        },
        "implementation_sha256": {
            "audit_script": sha256(SELF_PATH),
            "engine": sha256(ENGINE_PATH),
            "adapter": sha256(ADAPTER_PATH),
        },
        "controls": controls,
        "candidates": candidates,
        "ranking": ranking,
    }
    payload["payload_sha256"] = canonical_hash(payload)
    payload["artifact_sha256"] = write_json(OUTPUT_PATH, payload, force=force)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    payload = run(force=args.force)
    print(json.dumps(sanitize(payload["ranking"]), ensure_ascii=False, indent=2, allow_nan=False))
    print(f"wrote {OUTPUT_PATH}")
    print(f"sha256 {payload['artifact_sha256']}")


if __name__ == "__main__":
    main()
