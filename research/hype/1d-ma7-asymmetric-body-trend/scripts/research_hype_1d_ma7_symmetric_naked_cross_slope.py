"""Backtest the frozen symmetric naked MA7 cross+slope diagnostic."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import math
from pathlib import Path
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
    / "specs/hype-1d-ma7-symmetric-naked-cross-slope-diagnostic-contract-2026-08-20.md"
)
ADAPTER_PATH = SCRIPT_DIR / "hype_1d_ma7_v4_fair_adapter.py"
RISK_PATH = SCRIPT_DIR / "hype_1d_ma7_trend_phase_risk_metrics.py"
OUTPUT_PATH = (
    ARTIFACT_DIR / "hype_1d_ma7_symmetric_naked_cross_slope_2026-08-20.json"
)
V7_RR_ARTIFACT = (
    ARTIFACT_DIR / "hype_1d_ma7_abt_v7_1_oapp_rebound_reset_2026-08-20.json"
)

SLOPE_MIN_ATR = 0.02
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
CANONICAL_RIGHT = 432
RECENT_SLICES = {"1d": 1, "7d": 7, "1m": 30, "3m": 90, "6m": 180, "1y": 365}


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


@dataclass(frozen=True, slots=True)
class Signal:
    index: int
    ts: pd.Timestamp
    target_side: int
    slope_atr: float
    close: float
    ma7: float
    previous_close: float
    previous_ma7: float

    def canonical(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "signal_ts": self.ts.isoformat(),
            "target_side": "long" if self.target_side > 0 else "short",
            "slope_atr": self.slope_atr,
            "close": self.close,
            "ma7": self.ma7,
            "previous_close": self.previous_close,
            "previous_ma7": self.previous_ma7,
        }


def qualified_signal(context: Any, index: int) -> Signal | None:
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
    slope_atr = (ma7 - previous_ma7) / atr7
    target = 0
    if (
        previous_close < previous_ma7
        and close > ma7
        and slope_atr >= SLOPE_MIN_ATR
    ):
        target = 1
    elif (
        previous_close > previous_ma7
        and close < ma7
        and -slope_atr >= SLOPE_MIN_ATR
    ):
        target = -1
    if not target:
        return None
    return Signal(
        index=index,
        ts=pd.Timestamp(context.book.ts[index]),
        target_side=target,
        slope_atr=slope_atr,
        close=close,
        ma7=ma7,
        previous_close=previous_close,
        previous_ma7=previous_ma7,
    )


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
    risk: ModuleType,
    *,
    start: int,
    right: int,
    slippage: float = BASE_SLIPPAGE,
    signal_lag: int = 0,
    include_funding: bool = True,
) -> tuple[dict[str, Any], Any, list[dict[str, Any]], list[dict[str, Any]]]:
    if not 0 <= start < right <= context.book.count:
        raise ValueError("invalid backtest window")
    if signal_lag < 0:
        raise ValueError("signal lag must be nonnegative")
    cost_rate = float(context.engine.FEE) + slippage
    events = funding_events(context) if include_funding else []
    equity = 1.0
    side = 0
    quantity = 0.0
    entry_ts: pd.Timestamp | None = None
    entry_price = math.nan
    entry_equity = math.nan
    pending: tuple[int, Signal] | None = None
    total_turnover = 0.0
    total_cost = 0.0
    total_funding = 0.0
    trades: list[dict[str, Any]] = []
    signals: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []

    def enter(ts: pd.Timestamp, price: float, target_side: int, signal: Signal) -> None:
        nonlocal equity, side, quantity, entry_ts, entry_price, entry_equity
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
        actions.append(
            {
                "action": "enter_long" if side > 0 else "enter_short",
                "ts": ts.isoformat(),
                "price": price,
                "signal_ts": signal.ts.isoformat(),
                "signal_index": signal.index,
            }
        )

    def close(ts: pd.Timestamp, price: float, reason: str) -> None:
        nonlocal equity, side, quantity, entry_ts, entry_price, entry_equity
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
                "bars": int((ts - entry_ts) / pd.Timedelta(days=1)),
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

    for index in range(start, right):
        ts = pd.Timestamp(context.book.ts[index])
        price = float(context.book.open[index])
        if pending is not None and pending[0] == index:
            _, signal = pending
            if side != signal.target_side:
                if side:
                    close(ts, price, "opposite_qualified_cross")
                enter(ts, price, signal.target_side, signal)
            actions.append(
                {
                    "action": "execute_signal",
                    "ts": ts.isoformat(),
                    "target_side": signal.target_side,
                    "signal_ts": signal.ts.isoformat(),
                }
            )
            pending = None
        if pending is None:
            signal = qualified_signal(context, index)
            if signal is not None:
                row = signal.canonical()
                row["side_at_signal"] = side
                due_index = index + 1 + signal_lag
                row["due_ts"] = (
                    pd.Timestamp(context.book.ts[due_index]).isoformat()
                    if due_index < right
                    else None
                )
                row["scheduled"] = due_index < right and signal.target_side != side
                signals.append(row)
                if row["scheduled"]:
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
    best = sorted(trades, key=lambda row: float(row["net_pnl"]), reverse=True)
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
        "qualified_signal_count": len(signals),
        "best_trade": best[0] if best else None,
        "top3_positive_pnl_share": (
            sum(max(0.0, float(row["net_pnl"])) for row in best[:3]) / positive
            if positive > 0.0
            else 0.0
        ),
        "ledger_parity": replay.parity,
    }
    return metrics, raw, signals, actions


def index_at_or_after(context: Any, ts: str) -> int:
    target = pd.Timestamp(ts)
    return next(
        index
        for index, value in enumerate(context.book.ts)
        if pd.Timestamp(value) >= target
    )


def run(force: bool = False) -> dict[str, Any]:
    adapter = load_module(ADAPTER_PATH, "snc02_v4_adapter")
    risk = load_module(RISK_PATH, "snc02_risk_metrics")
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

    canonical, canonical_raw, canonical_signals, _ = run_backtest(
        context,
        risk,
        start=0,
        right=CANONICAL_RIGHT,
    )
    extended, extended_raw, extended_signals, actions = run_backtest(
        context,
        risk,
        start=0,
        right=context.book.count,
    )
    stress: dict[str, Any] = {}
    for label, slippage, lag, funding in (
        ("slippage_8bps", STRESS_SLIPPAGE, 0, True),
        ("lag_1d", BASE_SLIPPAGE, 1, True),
        ("funding_off", BASE_SLIPPAGE, 0, False),
    ):
        metrics, _, _, _ = run_backtest(
            context,
            risk,
            start=0,
            right=context.book.count,
            slippage=slippage,
            signal_lag=lag,
            include_funding=funding,
        )
        stress[label] = metrics

    recent: dict[str, Any] = {}
    for label, days in RECENT_SLICES.items():
        metrics, _, _, _ = run_backtest(
            context,
            risk,
            start=max(0, context.book.count - days),
            right=context.book.count,
        )
        recent[label] = metrics

    yearly: dict[str, Any] = {}
    windows = {
        "2025_partial": (0, index_at_or_after(context, "2026-01-01T00:00:00Z")),
        "2026_ytd": (
            index_at_or_after(context, "2026-01-01T00:00:00Z"),
            context.book.count,
        ),
    }
    for label, (left, right) in windows.items():
        metrics, _, _, _ = run_backtest(
            context,
            risk,
            start=left,
            right=right,
        )
        yearly[label] = metrics

    latest_trade = extended_raw.trades[-1] if extended_raw.trades else None
    august_signal = next(
        (
            row
            for row in extended_signals
            if row["signal_ts"] == "2026-08-08T00:00:00+00:00"
        ),
        None,
    )
    v7_evidence = json.loads(V7_RR_ARTIFACT.read_text(encoding="utf-8"))
    payload = {
        "schema": "hype-1d-ma7-symmetric-naked-cross-slope-diagnostic-v1",
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "status": "INDEPENDENT_DIAGNOSTIC_EXPLORE_NOT_PROMOTED_NOT_LIVE_READY",
        "strategy_id": "HYPE-1D-MA7-SNC02",
        "rule": {
            "ma": "SMA7",
            "atr": "simple ATR7",
            "slope_lookback": 1,
            "slope_min_atr": SLOPE_MIN_ATR,
            "entry": "strict fresh cross plus symmetric directional slope",
            "exit": "only opposite qualified signal; otherwise terminal flatten",
            "excluded_modules": [
                "buffers",
                "armed/hysteresis",
                "hard/trailing stop",
                "OAPP",
                "short RSI",
                "PEHC",
                "max hold",
                "cooldown",
            ],
        },
        "data_audit": sanitize(context.market.audit),
        "canonical": canonical,
        "extended": extended,
        "stress": stress,
        "recent_slices": recent,
        "calendar_flat_start": yearly,
        "latest_trend": {
            "august_08_signal": august_signal,
            "latest_trade": latest_trade,
            "entered_2026_08_09_long": bool(
                latest_trade
                and latest_trade["side"] == "long"
                and latest_trade["entry_ts"] == "2026-08-09T00:00:00+00:00"
            ),
            "terminal_censored": bool(
                latest_trade and latest_trade["exit_reason"] == "terminal_flatten"
            ),
        },
        "trades": extended_raw.trades,
        "signals": extended_signals,
        "actions": actions,
        "canonical_trade_count": len(canonical_raw.trades),
        "canonical_signal_count": len(canonical_signals),
        "v7_1_same_window_comparison": {
            "canonical": v7_evidence["canonical_path"]["CONTROL"],
            "extended": v7_evidence["full_path"]["CONTROL"],
        },
        "verdict": {
            "return_positive": extended["net_return_pct"] > 0.0,
            "mdd_20_gate_pass": extended["chronological_1h_mdd_pct"] >= -20.0,
            "decision": "PENDING",
            "changes_v7_1": False,
            "runner_change_authorized": False,
        },
        "pins": {
            "contract_sha256": sha256(CONTRACT_PATH),
            "script_sha256": sha256(Path(__file__).resolve()),
            "adapter_sha256": sha256(ADAPTER_PATH),
            "risk_replay_sha256": sha256(RISK_PATH),
            "v7_comparison_artifact_sha256": sha256(V7_RR_ARTIFACT),
        },
        "notes": [
            "All history is revealed diagnostic evidence, not clean OOS.",
            "No protective stop is present; the 1h MDD is the relevant risk measure.",
            "Terminal flatten is mark-to-market censoring, not a mature opposite signal.",
        ],
    }
    payload["verdict"]["decision"] = (
        "NO_GO_MDD_GATE_FAILED"
        if not payload["verdict"]["mdd_20_gate_pass"]
        else "DIAGNOSTIC_ONLY"
    )
    document = (
        json.dumps(sanitize(payload), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
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
                "stress": payload["stress"],
                "recent_slices": payload["recent_slices"],
                "calendar_flat_start": payload["calendar_flat_start"],
                "latest_trend": payload["latest_trend"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
