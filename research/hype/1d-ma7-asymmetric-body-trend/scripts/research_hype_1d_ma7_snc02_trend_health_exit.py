"""SNC02 entry plus frozen trend-health exits; diagnostic-only."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
BASE_PATH = SCRIPT_DIR / "research_hype_1d_ma7_symmetric_naked_cross_slope.py"
CONTRACT_PATH = (
    FAMILY_DIR
    / "specs/hype-1d-ma7-snc02-trend-health-exit-diagnostic-contract-2026-08-20.md"
)
OUTPUT_PATH = ARTIFACT_DIR / "hype_1d_ma7_snc02_trend_health_exit_2026-08-20.json"
SNC02_ARTIFACT = ARTIFACT_DIR / "hype_1d_ma7_symmetric_naked_cross_slope_2026-08-20.json"

PULLBACK_ATR = 3.0
STALE_EXTREME_DAYS = 7
SLOPE_DECAY_DAYS = 2
DAILY_REASON_PRIORITY = (
    "structure_hl_break",
    "signed_er_nonpositive",
    "slope_nonpositive",
    "slope_decay_2d",
    "no_new_extreme_7d",
    "health_nonfinite",
)


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


def efficiency(closes: np.ndarray, index: int, side: int) -> tuple[float, float]:
    start = index - 7
    if start < 0 or side == 0:
        return math.nan, math.nan
    net = float(closes[index] - closes[start])
    path = float(np.abs(np.diff(closes[start : index + 1])).sum())
    if not math.isfinite(net) or not math.isfinite(path) or path <= 0.0:
        return math.nan, math.nan
    unsigned = abs(net) / path
    return unsigned, side * net / path


def compact_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "net_return_pct",
        "chronological_1h_mdd_pct",
        "win_rate",
        "profit_factor",
        "closed_trades",
        "long_trades",
        "short_trades",
        "exposure_pct",
        "cost_pct_initial",
        "funding_pct_initial",
        "top3_positive_pnl_share",
        "long_net_pnl_equity_units",
        "short_net_pnl_equity_units",
    )
    return {key: metrics.get(key) for key in keys}


@dataclass
class HealthState:
    side: int
    entry_price: float
    highest_close: float
    lowest_close: float
    last_peak: float
    last_trough: float
    pullback_min: float | None = None
    bounce_max: float | None = None
    confirmed_hl: float | None = None
    confirmed_hh: float | None = None
    days_since_extreme: int = 0
    prev_side_slope: float | None = None
    decay_run: int = 0
    highest_high: float = math.nan
    lowest_low: float = math.nan
    events: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def start(cls, side: int, entry_price: float) -> HealthState:
        return cls(
            side=side,
            entry_price=entry_price,
            highest_close=entry_price,
            lowest_close=entry_price,
            last_peak=entry_price,
            last_trough=entry_price,
            highest_high=entry_price,
            lowest_low=entry_price,
        )


def daily_health_reasons(
    *,
    state: HealthState,
    index: int,
    close: float,
    side_slope: float,
    signed_er: float,
) -> list[str]:
    reasons: list[str] = []
    if not all(math.isfinite(value) for value in (close, side_slope, signed_er)):
        return ["health_nonfinite"]
    if state.side > 0:
        if close >= state.highest_close:
            if state.pullback_min is not None and state.pullback_min < state.last_peak:
                state.confirmed_hl = state.pullback_min
            state.last_peak = close
            state.highest_close = close
            state.pullback_min = None
            state.days_since_extreme = 0
        else:
            state.days_since_extreme += 1
            state.pullback_min = (
                close if state.pullback_min is None else min(state.pullback_min, close)
            )
            if state.confirmed_hl is not None and close < state.confirmed_hl:
                reasons.append("structure_hl_break")
    else:
        if close <= state.lowest_close:
            if state.bounce_max is not None and state.bounce_max > state.last_trough:
                state.confirmed_hh = state.bounce_max
            state.last_trough = close
            state.lowest_close = close
            state.bounce_max = None
            state.days_since_extreme = 0
        else:
            state.days_since_extreme += 1
            state.bounce_max = (
                close if state.bounce_max is None else max(state.bounce_max, close)
            )
            if state.confirmed_hh is not None and close > state.confirmed_hh:
                reasons.append("structure_hl_break")
    if signed_er <= 0.0:
        reasons.append("signed_er_nonpositive")
    if side_slope <= 0.0:
        reasons.append("slope_nonpositive")
        state.decay_run = 0
    else:
        if state.prev_side_slope is not None and side_slope < state.prev_side_slope:
            state.decay_run += 1
        else:
            state.decay_run = 0
        if state.decay_run >= SLOPE_DECAY_DAYS:
            reasons.append("slope_decay_2d")
    if state.days_since_extreme >= STALE_EXTREME_DAYS:
        reasons.append("no_new_extreme_7d")
    state.prev_side_slope = side_slope
    return reasons


def choose_daily_reason(reasons: list[str]) -> str | None:
    for reason in DAILY_REASON_PRIORITY:
        if reason in reasons:
            return reason
    return None


def scan_atr3_stop(
    context: Any,
    *,
    index: int,
    start_hour: int,
    state: HealthState,
    atr: float,
) -> dict[str, Any] | None:
    if not math.isfinite(atr) or atr <= 0.0:
        return None
    ts = pd.Timestamp(context.book.ts[index])
    for hour in range(int(start_hour), 24):
        hour_open = float(context.features.hourly_open[index, hour])
        hour_high = float(context.features.hourly_high[index, hour])
        hour_low = float(context.features.hourly_low[index, hour])
        if not all(math.isfinite(value) for value in (hour_open, hour_high, hour_low)):
            continue
        if state.side > 0:
            stop = float(state.highest_high) - PULLBACK_ATR * atr
            gap = hour_open <= stop
            touch = hour_low <= stop
            if math.isfinite(stop) and (gap or touch):
                fill = hour_open if gap else stop
                kind = "hour_gap" if gap else "touch"
                fill_ts = ts + pd.Timedelta(hours=hour if gap else hour + 1)
                return {
                    "reason": "atr3_structure_stop",
                    "fill": float(fill),
                    "fill_ts": fill_ts,
                    "hour": hour,
                    "kind": kind,
                    "stop": float(stop),
                    "atr": float(atr),
                }
            state.highest_high = max(float(state.highest_high), hour_high)
        else:
            stop = float(state.lowest_low) + PULLBACK_ATR * atr
            gap = hour_open >= stop
            touch = hour_high >= stop
            if math.isfinite(stop) and (gap or touch):
                fill = hour_open if gap else stop
                kind = "hour_gap" if gap else "touch"
                fill_ts = ts + pd.Timedelta(hours=hour if gap else hour + 1)
                return {
                    "reason": "atr3_structure_stop",
                    "fill": float(fill),
                    "fill_ts": fill_ts,
                    "hour": hour,
                    "kind": kind,
                    "stop": float(stop),
                    "atr": float(atr),
                }
            state.lowest_low = min(float(state.lowest_low), hour_low)
    return None


def run_thx(
    base: ModuleType,
    context: Any,
    risk: ModuleType,
    *,
    start: int,
    right: int,
    slippage: float = 0.0004,
    signal_lag: int = 0,
    include_funding: bool = True,
) -> tuple[dict[str, Any], Any, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if not 0 <= start < right <= context.book.count:
        raise ValueError("invalid backtest window")
    cost_rate = float(context.engine.FEE) + slippage
    events = base.funding_events(context) if include_funding else []
    closes = np.asarray(context.book.close, dtype=float)
    equity = 1.0
    side = 0
    quantity = 0.0
    entry_ts: pd.Timestamp | None = None
    entry_price = math.nan
    entry_equity = math.nan
    pending_signal: tuple[int, Any] | None = None
    pending_exit: tuple[int, str] | None = None
    health: HealthState | None = None
    total_turnover = 0.0
    total_cost = 0.0
    total_funding = 0.0
    trades: list[dict[str, Any]] = []
    signals: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    health_events: list[dict[str, Any]] = []

    def enter(ts: pd.Timestamp, price: float, target_side: int, signal: Any) -> None:
        nonlocal equity, side, quantity, entry_ts, entry_price, entry_equity, health
        nonlocal total_turnover, total_cost
        before = equity
        quantity, equity, turnover = risk.target_quantity(
            equity, 0.0, target_side, price, cost_rate, 1.0
        )
        total_turnover += turnover
        total_cost += before - equity
        side = target_side
        entry_ts = ts
        entry_price = price
        entry_equity = before
        health = HealthState.start(target_side, price)
        actions.append(
            {
                "action": "enter_long" if side > 0 else "enter_short",
                "ts": ts.isoformat(),
                "price": price,
                "signal_ts": signal.ts.isoformat(),
                "signal_index": signal.index,
            }
        )

    def close_trade(ts: pd.Timestamp, price: float, reason: str) -> None:
        nonlocal equity, side, quantity, entry_ts, entry_price, entry_equity, health
        nonlocal total_turnover, total_cost, total_funding
        if side == 0 or entry_ts is None:
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
            before_exit, quantity, 0, price, cost_rate, 1.0
        )
        total_turnover += turnover
        total_cost += before_cost - after
        total_funding += funding
        net_pnl = after - entry_equity
        trade_side = side
        trades.append(
            {
                "side": "long" if trade_side > 0 else "short",
                "entry_ts": entry_ts.isoformat(),
                "entry_price": entry_price,
                "exit_ts": ts.isoformat(),
                "exit_price": price,
                "exit_reason": reason,
                "entry_leverage": 1.0,
                "gross_return_pct": trade_side * (price / entry_price - 1.0) * 100.0,
                "net_return_pct": net_pnl / entry_equity * 100.0,
                "net_pnl": net_pnl,
                "funding_pnl": -funding,
                "bars": max(0, int((ts - entry_ts) / pd.Timedelta(days=1))),
            }
        )
        actions.append(
            {
                "action": "exit_long" if trade_side > 0 else "exit_short",
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
        health = None

    for index in range(start, right):
        ts = pd.Timestamp(context.book.ts[index])
        price = float(context.book.open[index])
        start_hour = 0
        if pending_exit is not None and pending_exit[0] == index:
            close_trade(ts, price, pending_exit[1])
            pending_exit = None
        if pending_signal is not None and pending_signal[0] == index:
            _, signal = pending_signal
            if side == 0:
                enter(ts, price, signal.target_side, signal)
            actions.append(
                {
                    "action": "execute_signal",
                    "ts": ts.isoformat(),
                    "target_side": signal.target_side,
                    "signal_ts": signal.ts.isoformat(),
                }
            )
            pending_signal = None
        if side and health is not None:
            atr_ref = float(context.features.atr7[index - 1]) if index > 0 else math.nan
            hit = scan_atr3_stop(
                context,
                index=index,
                start_hour=start_hour,
                state=health,
                atr=atr_ref,
            )
            if hit is not None:
                close_trade(hit["fill_ts"], float(hit["fill"]), str(hit["reason"]))
                health_events.append({"index": index, **{k: v for k, v in hit.items() if k != "fill_ts"}, "fill_ts": hit["fill_ts"].isoformat()})
                pending_exit = None
        if pending_signal is None and pending_exit is None:
            signal = base.qualified_signal(context, index)
            reasons: list[str] = []
            chosen = None
            if side and health is not None:
                atr = float(context.features.atr7[index])
                ma = float(context.features.ma7[index])
                prev_ma = float(context.features.ma7[index - 1]) if index > 0 else math.nan
                side_slope = (
                    side * (ma - prev_ma) / atr
                    if math.isfinite(atr) and atr > 0.0 and math.isfinite(ma) and math.isfinite(prev_ma)
                    else math.nan
                )
                _, signed_er = efficiency(closes, index, side)
                reasons = daily_health_reasons(
                    state=health,
                    index=index,
                    close=float(closes[index]),
                    side_slope=side_slope,
                    signed_er=signed_er,
                )
                chosen = choose_daily_reason(reasons)
                health_events.append(
                    {
                        "index": index,
                        "ts": ts.isoformat(),
                        "side": side,
                        "close": float(closes[index]),
                        "side_slope": side_slope if math.isfinite(side_slope) else None,
                        "signed_er": signed_er if math.isfinite(signed_er) else None,
                        "days_since_extreme": health.days_since_extreme,
                        "decay_run": health.decay_run,
                        "reasons": reasons,
                        "chosen": chosen,
                    }
                )
            due_index = index + 1 + signal_lag
            if chosen is not None and due_index < right:
                pending_exit = (due_index, chosen)
                if (
                    signal is not None
                    and signal.target_side != side
                    and due_index < right
                ):
                    pending_signal = (due_index, signal)
                    row = signal.canonical()
                    row["side_at_signal"] = side
                    row["scheduled"] = True
                    row["due_ts"] = pd.Timestamp(context.book.ts[due_index]).isoformat()
                    row["paired_health_exit"] = chosen
                    signals.append(row)
            elif signal is not None and side == 0:
                row = signal.canonical()
                row["side_at_signal"] = 0
                row["due_ts"] = (
                    pd.Timestamp(context.book.ts[due_index]).isoformat()
                    if due_index < right
                    else None
                )
                row["scheduled"] = due_index < right
                signals.append(row)
                if row["scheduled"]:
                    pending_signal = (due_index, signal)

    end_ts, end_price = base.terminal_point(context, right)
    close_trade(end_ts, end_price, "terminal_flatten")
    positive = sum(max(0.0, float(row["net_pnl"])) for row in trades)
    negative = -sum(min(0.0, float(row["net_pnl"])) for row in trades)
    raw = SimpleNamespace(
        metrics={
            "equity_multiple": equity,
            "closed_trades": len(trades),
            "turnover_multiple": total_turnover,
            "cost_pct_initial": total_cost * 100.0,
            "funding_pct_initial": total_funding * 100.0,
        },
        trades=trades,
    )
    replay = risk.replay_chronological_1h(
        context, raw, slippage=slippage, include_funding=include_funding
    )
    duration_days = right - start
    exposure_days = sum(
        max(0.0, (pd.Timestamp(row["exit_ts"]) - pd.Timestamp(row["entry_ts"])) / pd.Timedelta(days=1))
        for row in trades
    )
    side_pnl = {
        name: sum(float(row["net_pnl"]) for row in trades if row["side"] == name)
        for name in ("long", "short")
    }
    best = sorted(trades, key=lambda row: float(row["net_pnl"]), reverse=True)
    reason_counts: dict[str, int] = {}
    for row in trades:
        reason_counts[str(row["exit_reason"])] = reason_counts.get(str(row["exit_reason"]), 0) + 1
    metrics = {
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
            sum(float(row["net_pnl"]) > 0.0 for row in trades) / len(trades) if trades else 0.0
        ),
        "profit_factor": positive / negative if negative > 0.0 else math.inf,
        "turnover_multiple": total_turnover,
        "cost_pct_initial": total_cost * 100.0,
        "funding_pct_initial": total_funding * 100.0,
        "max_marked_leverage": replay.max_marked_leverage,
        "exposure_pct": exposure_days / duration_days * 100.0,
        "long_net_pnl_equity_units": side_pnl["long"],
        "short_net_pnl_equity_units": side_pnl["short"],
        "qualified_signal_count": len(signals),
        "best_trade": best[0] if best else None,
        "top3_positive_pnl_share": (
            sum(max(0.0, float(row["net_pnl"])) for row in best[:3]) / positive if positive > 0.0 else 0.0
        ),
        "exit_reason_counts": reason_counts,
        "ledger_parity": replay.parity,
    }
    return metrics, raw, signals, actions, health_events


def incident_trade(trades: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next(
        (
            row
            for row in trades
            if row["side"] == "long"
            and str(row["entry_ts"]).startswith("2026-08-09")
        ),
        None,
    )


def decide(payload: dict[str, Any]) -> dict[str, Any]:
    control = payload["canonical"]["SNC02"]
    candidate = payload["canonical"]["THX"]
    august = payload["august"]
    lower = float(candidate["net_return_pct"]) < float(control["net_return_pct"])
    worse_mdd = float(candidate["chronological_1h_mdd_pct"]) < float(
        control["chronological_1h_mdd_pct"]
    )
    mdd_gate = float(candidate["chronological_1h_mdd_pct"]) < -20.0
    cut_august = bool(august.get("thx_cut_before_terminal"))
    if mdd_gate and (lower or worse_mdd or cut_august):
        decision = "NO_GO_THX_RISK_OR_TREND_CUT"
    elif lower and worse_mdd:
        decision = "NO_GO_THX_DOMINATED_BY_SNC02"
    elif mdd_gate:
        decision = "NO_GO_THX_MDD_GATE_FAILED"
    else:
        decision = "SHADOW_THX_ONLY"
    return {
        "decision": decision,
        "production_action": "KEEP_V7_1",
        "snc02_status": "KEEP_SNC02_AS_SIGNAL_CORE_CONTROL",
        "runner_change_authorized": False,
        "register_version": False,
    }


def run(force: bool = False) -> dict[str, Any]:
    base = load_module(BASE_PATH, "snc02_thx_base")
    adapter = base.load_module(base.ADAPTER_PATH, "snc02_thx_adapter")
    risk = base.load_module(base.RISK_PATH, "snc02_thx_risk")
    frozen = adapter.load_context()
    original = frozen.original_harness
    original.HOURLY_CUTOFF = pd.Timestamp("2100-01-01T00:00:00Z")
    original.FUNDING_CUTOFF = pd.Timestamp("2100-01-01T00:00:00Z")
    market = original.load_market(0)
    context = SimpleNamespace(
        market=market,
        book=market.book,
        features=market.features,
        engine=frozen.engine,
    )
    control_canonical, control_canonical_raw, _, _ = base.run_backtest(
        context, risk, start=0, right=base.CANONICAL_RIGHT
    )
    control_extended, control_extended_raw, _, _ = base.run_backtest(
        context, risk, start=0, right=context.book.count
    )
    existing = json.loads(SNC02_ARTIFACT.read_text(encoding="utf-8"))
    if not math.isclose(
        float(control_extended["net_return_pct"]),
        float(existing["extended"]["net_return_pct"]),
        abs_tol=1e-8,
    ):
        raise RuntimeError("SNC02 control drift vs frozen artifact")

    thx_canonical, thx_canonical_raw, _, _, _ = run_thx(
        base, context, risk, start=0, right=base.CANONICAL_RIGHT
    )
    thx_extended, thx_extended_raw, _, _, health_events = run_thx(
        base, context, risk, start=0, right=context.book.count
    )
    stress: dict[str, Any] = {}
    for label, slippage, lag, funding in (
        ("slippage_8bps", base.STRESS_SLIPPAGE, 0, True),
        ("lag_1d", base.BASE_SLIPPAGE, 1, True),
        ("funding_off", base.BASE_SLIPPAGE, 0, False),
    ):
        metrics, _, _, _, _ = run_thx(
            base,
            context,
            risk,
            start=0,
            right=context.book.count,
            slippage=slippage,
            signal_lag=lag,
            include_funding=funding,
        )
        stress[label] = compact_metrics(metrics)
    recent: dict[str, Any] = {}
    for label, days in base.RECENT_SLICES.items():
        metrics, _, _, _, _ = run_thx(
            base,
            context,
            risk,
            start=max(0, context.book.count - days),
            right=context.book.count,
        )
        recent[label] = compact_metrics(metrics)

    snc02_august = incident_trade(list(control_extended_raw.trades))
    thx_august = incident_trade(list(thx_extended_raw.trades))
    payload = {
        "schema": "hype-1d-ma7-snc02-trend-health-exit-diagnostic-v1",
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "status": "INDEPENDENT_DIAGNOSTIC_EXPLORE_NOT_PROMOTED_NOT_LIVE_READY",
        "strategy_id": "HYPE-1D-MA7-SNC02-THX",
        "canonical": {
            "SNC02": compact_metrics(control_canonical),
            "THX": compact_metrics(thx_canonical),
        },
        "extended": {
            "SNC02": compact_metrics(control_extended),
            "THX": compact_metrics(thx_extended),
        },
        "stress": stress,
        "recent_slices": recent,
        "august": {
            "snc02": snc02_august,
            "thx": thx_august,
            "thx_entered_2026_08_09": bool(thx_august),
            "thx_cut_before_terminal": bool(
                thx_august and thx_august["exit_reason"] != "terminal_flatten"
            ),
            "thx_terminal_censored": bool(
                thx_august and thx_august["exit_reason"] == "terminal_flatten"
            ),
        },
        "exit_reason_counts": {
            "canonical": thx_canonical.get("exit_reason_counts"),
            "extended": thx_extended.get("exit_reason_counts"),
        },
        "trades": thx_extended_raw.trades,
        "canonical_trades": thx_canonical_raw.trades,
        "health_event_count": len(health_events),
        "pins": {
            "contract_sha256": sha256(CONTRACT_PATH),
            "script_sha256": sha256(Path(__file__).resolve()),
            "base_script_sha256": sha256(BASE_PATH),
            "snc02_artifact_sha256": sha256(SNC02_ARTIFACT),
        },
        "notes": [
            "Entry is exact SNC02; opposite qualified crosses do not exit by themselves.",
            "Daily health executes next UTC open; 3ATR structure stop executes on 1h.",
            "August is revealed and may be terminal-censored.",
        ],
    }
    payload["verdict"] = decide(payload)
    document = (
        json.dumps(
            base.sanitize(payload),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
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
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    result = run(force=args.force)
    payload = result["payload"]
    print(
        json.dumps(
            {
                "output": result["output"],
                "sha256": result["sha256"],
                "verdict": payload["verdict"],
                "canonical": payload["canonical"],
                "extended": payload["extended"],
                "august": payload["august"],
                "exit_reason_counts": payload["exit_reason_counts"],
                "stress": payload["stress"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
