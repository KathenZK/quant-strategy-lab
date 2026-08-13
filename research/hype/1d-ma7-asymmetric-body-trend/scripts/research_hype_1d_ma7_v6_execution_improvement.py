"""Backtest frozen execution-improvement overlays on HYPE MA7 ABT V6."""

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
CONTRACT_PATH = (
    FAMILY_DIR
    / "specs/hype-1d-ma7-abt-v6-execution-improvement-contract-2026-08-10.md"
)
ENGINE_PATH = SCRIPT_DIR / "hype_1d_ma7_v6_execution_improvement_engine.py"
ADAPTER_PATH = SCRIPT_DIR / "hype_1d_ma7_v4_fair_adapter.py"
SELF_PATH = Path(__file__).resolve()
OUTPUT_PATH = ARTIFACT_DIR / "hype_1d_ma7_abt_v6_execution_improvement_2026-08-10.json"

FULL = (0, 432)
BLOCKS = tuple((left, left + 54) for left in range(0, 432, 54))
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
EXPECTED_V6_RETURN = 617.1070876096234
EXPECTED_V6_MDD = -18.391735672691034
EXPECTED_V6_TRADES = 19
TOLERANCE = 1e-8


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
    encoded = json.dumps(sanitize(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def write_json(path: Path, payload: dict[str, Any], *, force: bool) -> str:
    sidecar = Path(f"{path}.sha256")
    if (path.exists() or sidecar.exists()) and not force:
        raise RuntimeError(f"locked artifact exists: {path.name}")
    document = json.dumps(sanitize(payload), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    digest = hashlib.sha256(document.encode()).hexdigest()
    path.write_text(document, encoding="utf-8")
    sidecar.write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    return digest


def load_runtime() -> tuple[ModuleType, Any]:
    engine = load_module(ENGINE_PATH, "v6_exec_improvement_engine")
    adapter = load_module(ADAPTER_PATH, "v6_exec_improvement_adapter")
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
    default_cost = fee + slippage
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
    side = 0
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
                raise RuntimeError("overlapping execution replay entry")
            price = float(trade["entry_price"])
            cost = float(trade.get("entry_execution_cost_rate", default_cost))
            leverage = float(trade.get("entry_leverage", 1.0))
            target_side = 1 if str(trade["side"]) == "long" else -1
            old_equity = equity
            qty, equity, turnover = target_quantity(equity, qty, target_side, price, cost, leverage)
            total_turnover += turnover
            total_cost += old_equity - equity
            side = target_side
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
            cost = float(trade.get("exit_execution_cost_rate", default_cost))
            old_equity = equity
            qty, equity, turnover = target_quantity(equity, qty, 0, price, cost, 1.0)
            total_turnover += turnover
            total_cost += old_equity - equity
            side = 0
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
            "terminal_equity": math.isclose(equity, float(raw.metrics["equity_multiple"]), rel_tol=0.0, abs_tol=5e-4),
        },
    }


def annualized_return(equity_multiple: float, days: int) -> float:
    if equity_multiple <= 0.0 or days <= 0:
        return math.nan
    return (equity_multiple ** (365.0 / days) - 1.0) * 100.0


def economic_trades(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = ("entry_ts", "exit_ts", "side", "entry_price", "exit_price", "exit_reason", "net_return", "net_pnl", "bars_held")
    return [{field: row.get(field) for field in fields} for row in trades]


def normalize(raw: Any, replay: dict[str, Any], *, days: int) -> dict[str, Any]:
    metrics = raw.metrics
    equity_multiple = float(replay["terminal_equity"])
    return {
        "equity_multiple": equity_multiple,
        "net_return_pct": (equity_multiple - 1.0) * 100.0,
        "annualized_return_pct": annualized_return(equity_multiple, days),
        "chronological_1h_mdd_pct": float(replay["chronological_1h_mdd_pct"]),
        "daily_extreme_mdd_pct": float(metrics["max_drawdown_pct"]),
        "closed_trades": int(metrics["closed_trades"]),
        "long_trades": int(metrics["long_trades"]),
        "short_trades": int(metrics["short_trades"]),
        "win_rate": float(metrics["win_rate"]),
        "profit_factor": float(metrics["profit_factor"]),
        "turnover_multiple": float(replay["turnover_multiple"]),
        "cost_pct_initial": float(replay["cost_pct_initial"]),
        "funding_pct_initial": float(replay["funding_pct_initial"]),
        "max_marked_leverage": float(replay["max_marked_leverage"]),
        "bankrupt_intraday": bool(metrics["bankrupt_intraday"]),
        "worst_ts": replay["worst_ts"],
        "worst_trade_index": replay["worst_trade_index"],
        "raw_engine_equity_multiple": float(metrics["equity_multiple"]),
        "replay_engine_equity_delta": equity_multiple - float(metrics["equity_multiple"]),
    }


def counts_for_v6(raw: Any, handoff_events: list[dict[str, Any]]) -> dict[str, int]:
    exits = [str(row.get("exit_reason", "")) for row in raw.trades]
    return {
        "long_trail_exit": sum(reason.startswith("long_mfe_") for reason in exits),
        "short_rsi_exit": sum(reason == "short_rsi_take_profit" for reason in exits),
        "protective_stop": sum(reason == "protective_stop" for reason in exits),
        "handoff_accept": sum(row.get("event") == "handoff_accept" for row in handoff_events),
        "shadow_start": sum(row.get("event") == "shadow_start" for row in handoff_events),
    }


def run_once(
    *,
    engine: ModuleType,
    context: Any,
    config: Any | None,
    window: tuple[int, int],
    slippage: float = BASE_SLIPPAGE,
    signal_lag: int = 0,
    include_funding: bool = True,
    retain: bool = False,
) -> dict[str, Any]:
    start = start_for(window)
    if config is None:
        result = engine.run_v6(context, start_index=start, terminal_index=window[1], slippage=slippage, signal_lag=signal_lag, include_funding=include_funding, retain=retain)
        raw = result.raw
        execution_events: list[dict[str, Any]] = []
        activation_counts = {**counts_for_v6(raw, result.handoff_events), **{"limit_fill_total": 0, "fallback_total": 0}}
        arm_id = "C000_EXACT_V6"
        source = result.source_sha256
        handoff_events = list(result.handoff_events)
    else:
        result = engine.run_variant(context, config, start_index=start, terminal_index=window[1], slippage=slippage, signal_lag=signal_lag, include_funding=include_funding, retain=retain)
        raw = result.raw
        execution_events = list(result.execution_events)
        activation_counts = dict(result.activation_counts)
        arm_id = config.arm_id
        source = result.source_sha256
        handoff_events = list(result.handoff_events)
    replay = chronological_replay(context, raw, slippage=slippage, include_funding=include_funding)
    trades = economic_trades(raw.trades)
    return {
        "status": "PASS",
        "arm_id": arm_id,
        "requested_window": list(window),
        "engine_window": [start, window[1]],
        "slippage": slippage,
        "signal_lag": signal_lag,
        "include_funding": include_funding,
        "config": config.canonical() if config is not None else None,
        "metrics": normalize(raw, replay, days=window[1] - start),
        "activation_counts": activation_counts,
        "execution_events": execution_events,
        "handoff_events": handoff_events,
        "trades": trades if retain else [],
        "trades_sha256": canonical_hash(trades),
        "source_sha256": source,
        "replay": replay,
    }


def compare(candidate: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    cm = candidate["metrics"]
    vm = control["metrics"]
    ret = float(cm["net_return_pct"]) - float(vm["net_return_pct"])
    mdd = float(cm["chronological_1h_mdd_pct"]) - float(vm["chronological_1h_mdd_pct"])
    return {
        "return_delta_pp": ret,
        "mdd_delta_pp": mdd,
        "return_higher": ret > 0.0,
        "mdd_smaller_or_equal": mdd >= -1e-10,
        "dual_pass": ret > 0.0 and mdd >= -1e-10,
        "double_worse": ret < 0.0 and mdd < 0.0,
        "trade_count_delta": int(cm["closed_trades"]) - int(vm["closed_trades"]),
        "economic_path_changed": candidate["trades_sha256"] != control["trades_sha256"],
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = [row["metrics"] for row in rows]
    equity = math.prod(float(row["equity_multiple"]) for row in metrics)
    return {
        "equity_multiple": equity,
        "net_return_pct": (equity - 1.0) * 100.0,
        "worst_mdd_pct": min(float(row["chronological_1h_mdd_pct"]) for row in metrics),
        "positive_windows": sum(float(row["net_return_pct"]) > 0.0 for row in metrics),
        "closed_trades": sum(int(row["closed_trades"]) for row in metrics),
    }


def recent_windows(count: int) -> dict[str, tuple[int, int]]:
    return {label: (max(0, count - days), count) for label, days in (("1d", 1), ("7d", 7), ("1m", 30), ("3m", 90), ("6m", 180), ("1y", 365))}


def rolling_windows() -> tuple[tuple[int, int], ...]:
    windows = [(left, left + 90) for left in range(0, FULL[1] - 89, 30)]
    anchored = (FULL[1] - 90, FULL[1])
    if anchored not in windows:
        windows.append(anchored)
    return tuple(windows)


def run_all(*, force: bool) -> dict[str, Any]:
    engine, context = load_runtime()
    configs = engine.grid_configs()
    control = run_once(engine=engine, context=context, config=None, window=FULL, retain=True)
    cm = control["metrics"]
    if not math.isclose(float(cm["net_return_pct"]), EXPECTED_V6_RETURN, abs_tol=0.05):
        raise RuntimeError("V6 return anchor drift")
    if not math.isclose(float(cm["chronological_1h_mdd_pct"]), EXPECTED_V6_MDD, abs_tol=0.01):
        raise RuntimeError("V6 MDD anchor drift")
    if int(cm["closed_trades"]) != EXPECTED_V6_TRADES:
        raise RuntimeError("V6 trade count anchor drift")
    candidates = [run_once(engine=engine, context=context, config=config, window=FULL, retain=True) for config in configs]
    stress_control = run_once(engine=engine, context=context, config=None, window=FULL, slippage=STRESS_SLIPPAGE)
    stress = [run_once(engine=engine, context=context, config=config, window=FULL, slippage=STRESS_SLIPPAGE) for config in configs]
    funding_control = run_once(engine=engine, context=context, config=None, window=FULL, include_funding=False)
    funding = [run_once(engine=engine, context=context, config=config, window=FULL, include_funding=False) for config in configs]
    lag_control = run_once(engine=engine, context=context, config=None, window=FULL, signal_lag=1)
    lag = [run_once(engine=engine, context=context, config=config, window=FULL, signal_lag=1) for config in configs]
    summaries: list[dict[str, Any]] = []
    block_control = [run_once(engine=engine, context=context, config=None, window=window) for window in BLOCKS]
    rolling_control = [run_once(engine=engine, context=context, config=None, window=window) for window in rolling_windows()]
    recent_control = {label: run_once(engine=engine, context=context, config=None, window=window) for label, window in recent_windows(FULL[1]).items()}
    details: dict[str, Any] = {}
    for idx, (config, candidate) in enumerate(zip(configs, candidates, strict=True)):
        block_rows = [run_once(engine=engine, context=context, config=config, window=window) for window in BLOCKS]
        rolling_rows = [run_once(engine=engine, context=context, config=config, window=window) for window in rolling_windows()]
        recent_rows = {label: run_once(engine=engine, context=context, config=config, window=window) for label, window in recent_windows(FULL[1]).items()}
        full_cmp = compare(candidate, control)
        stress_cmp = compare(stress[idx], stress_control)
        funding_cmp = compare(funding[idx], funding_control)
        lag_cmp = compare(lag[idx], lag_control)
        block_cmp = [compare(row, base) for row, base in zip(block_rows, block_control, strict=True)]
        activation_delta = {
            key: int(candidate["activation_counts"].get(key, 0)) - int(control["activation_counts"].get(key, 0))
            for key in ("protective_stop", "handoff_accept", "long_trail_exit", "short_rsi_exit", "shadow_start")
        }
        checks = {
            "full_return_higher": full_cmp["return_higher"],
            "full_mdd_smaller_or_equal": full_cmp["mdd_smaller_or_equal"],
            "stress_not_double_worse": not stress_cmp["double_worse"],
            "funding_off_not_double_worse": not funding_cmp["double_worse"],
            "lag_not_double_worse": not lag_cmp["double_worse"],
            "blocks_not_double_worse": all(not row["double_worse"] for row in block_cmp),
            "core_chain_preserved": all(value >= 0 for key, value in activation_delta.items() if key != "protective_stop") and activation_delta["protective_stop"] <= 0,
            "enough_limit_fills": int(candidate["activation_counts"].get("limit_fill_total", 0)) >= 3,
        }
        summary = {
            "arm_id": config.arm_id,
            "config": config.canonical(),
            "status": "PASS_DIAGNOSTIC_ONLY" if all(checks.values()) else "FAIL",
            "metrics": candidate["metrics"],
            "compare_full": full_cmp,
            "compare_stress_8bps": stress_cmp,
            "compare_funding_off": funding_cmp,
            "compare_lag": lag_cmp,
            "activation_counts": candidate["activation_counts"],
            "activation_delta": activation_delta,
            "gate": checks,
            "block_summary": aggregate(block_rows),
            "rolling_summary": aggregate(rolling_rows),
        }
        summaries.append(summary)
        details[config.arm_id] = {
            "full": candidate,
            "stress_8bps": stress[idx],
            "funding_off": funding[idx],
            "signal_lag_plus_1d": lag[idx],
            "cold_flat_blocks": {"rows": block_rows, "summary": aggregate(block_rows), "comparisons": block_cmp},
            "rolling_90d_30d": {"rows": rolling_rows, "summary": aggregate(rolling_rows)},
            "recent_slices_audit_only": {"control": recent_control, "candidate": recent_rows},
            "gate": checks,
        }
    passers = [row for row in summaries if row["status"] == "PASS_DIAGNOSTIC_ONLY"]
    best = sorted(summaries, key=lambda row: (row["compare_full"]["return_delta_pp"], row["compare_full"]["mdd_delta_pp"]), reverse=True)[0]
    payload = {
        "schema": "hype-1d-ma7-abt-v6-execution-improvement-v1",
        "status": "PASS_DIAGNOSTIC_ONLY" if passers else "FAIL",
        "research_state": "registered V6 unchanged / diagnostic-only / not promoted / not live-ready",
        "market_audit": context.market.audit,
        "book_quality": context.book.quality,
        "pins": {"contract": sha256(CONTRACT_PATH), "engine": sha256(ENGINE_PATH), "audit": sha256(SELF_PATH), "adapter": sha256(ADAPTER_PATH)},
        "control": control,
        "summaries": summaries,
        "best_by_return_delta": best,
        "passers": passers,
        "details": details,
        "decision": "Do not change V6 unless a passer later survives clean prospective validation.",
    }
    digest = write_json(OUTPUT_PATH, payload, force=force)
    payload["output_sha256"] = digest
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    payload = run_all(force=args.force)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "artifact": str(OUTPUT_PATH),
                "best": payload["best_by_return_delta"]["arm_id"],
                "best_return": payload["best_by_return_delta"]["metrics"]["net_return_pct"],
                "best_mdd": payload["best_by_return_delta"]["metrics"]["chronological_1h_mdd_pct"],
                "passers": [row["arm_id"] for row in payload["passers"]],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
