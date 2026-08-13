"""Chronological risk replay and leverage-frontier helpers for TPR research."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Callable

import pandas as pd


@dataclass(frozen=True, slots=True)
class ReplayPoint:
    ts: str
    equity: float
    kind: str
    trade_index: int | None
    price: float | None
    side: int


@dataclass(frozen=True, slots=True)
class ReplayResult:
    terminal_equity: float
    chronological_1h_mdd_pct: float
    worst_ts: str | None
    worst_trade_index: int | None
    turnover_multiple: float
    cost_equity_units: float
    funding_equity_units: float
    max_marked_leverage: float
    points: tuple[ReplayPoint, ...]
    parity: dict[str, Any]

    def canonical(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["points"] = [asdict(point) for point in self.points]
        return payload


def target_quantity(
    equity: float,
    old_qty: float,
    target_side: int,
    price: float,
    cost_rate: float,
    leverage: float,
) -> tuple[float, float, float]:
    values = (equity, old_qty, price, cost_rate, leverage)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("target quantity inputs must be finite")
    if price <= 0.0 or equity < 0.0 or cost_rate < 0.0:
        raise ValueError("invalid target quantity inputs")
    if target_side not in (-1, 0, 1):
        raise ValueError("target_side must be -1, 0, or 1")
    if target_side != 0 and not 0.0 < leverage <= 3.0:
        raise ValueError("entry leverage must be within (0, 3]")
    post_equity = equity
    target_qty = old_qty
    turnover = 0.0
    for _ in range(20):
        target_qty = (
            target_side * leverage * post_equity / price
            if target_side
            else 0.0
        )
        turnover = abs(target_qty - old_qty) * price
        updated = equity - turnover * cost_rate
        if math.isclose(updated, post_equity, rel_tol=0.0, abs_tol=1e-14):
            post_equity = updated
            break
        post_equity = updated
    return float(target_qty), float(post_equity), float(turnover)


def _hourly_marks(context: Any) -> list[tuple[pd.Timestamp, float]]:
    marks: list[tuple[pd.Timestamp, float]] = []
    for index, day in enumerate(context.book.ts):
        day_ts = pd.Timestamp(day)
        for hour in range(24):
            value = float(context.features.hourly_open[index, hour])
            if not math.isfinite(value) or value <= 0.0:
                raise RuntimeError("nonfinite hourly open in frozen market")
            marks.append((day_ts + pd.Timedelta(hours=hour), value))
    terminal = pd.Timestamp(context.book.terminal_ts)
    terminal_open = float(context.book.quality["terminal_open"])
    marks.append((terminal, terminal_open))
    marks.sort(key=lambda item: item[0])
    return marks


def _funding_events(context: Any) -> list[Any]:
    events = [event for daily in context.features.funding_events for event in daily]
    return sorted(events, key=lambda event: pd.Timestamp(event.ts))


def replay_chronological_1h(
    context: Any,
    raw: Any,
    *,
    slippage: float = 0.0004,
    default_leverage: float = 1.0,
    include_funding: bool = True,
    retain_points: bool = False,
    leverage_getter: Callable[[dict[str, Any], int], float] | None = None,
    tolerance: float = 2e-10,
) -> ReplayResult:
    """Replay a closed-trade ledger on ordered hourly opens and funding events."""

    cost_rate = float(context.engine.FEE) + float(slippage)
    trades = list(raw.trades)
    hourly = _hourly_marks(context)
    funding = _funding_events(context) if include_funding else []
    equity = 1.0
    peak = 1.0
    mdd = 0.0
    worst_ts: str | None = None
    worst_trade: int | None = None
    total_turnover = 0.0
    total_cost = 0.0
    total_funding = 0.0
    max_leverage = 0.0
    points: list[ReplayPoint] = []

    def observe(
        ts: pd.Timestamp,
        marked_equity: float,
        kind: str,
        trade_index: int | None,
        price: float | None,
        side: int,
        qty: float = 0.0,
    ) -> None:
        nonlocal peak, mdd, worst_ts, worst_trade, max_leverage
        if not math.isfinite(marked_equity):
            raise RuntimeError("nonfinite marked equity")
        peak = max(peak, marked_equity)
        drawdown = -1.0 if marked_equity <= 0.0 else marked_equity / peak - 1.0
        if drawdown < mdd:
            mdd = drawdown
            worst_ts = ts.isoformat()
            worst_trade = trade_index
        if price is not None and marked_equity > 0.0:
            max_leverage = max(max_leverage, abs(qty) * price / marked_equity)
        if retain_points:
            points.append(
                ReplayPoint(
                    ts=ts.isoformat(),
                    equity=float(marked_equity),
                    kind=kind,
                    trade_index=trade_index,
                    price=float(price) if price is not None else None,
                    side=side,
                )
            )

    observe(pd.Timestamp(context.book.ts[0]), equity, "start", None, None, 0)
    previous_exit: pd.Timestamp | None = None
    for trade_index, trade in enumerate(trades):
        entry_ts = pd.Timestamp(trade["entry_ts"])
        exit_ts = pd.Timestamp(trade["exit_ts"])
        if entry_ts > exit_ts:
            raise RuntimeError("negative trade duration")
        if previous_exit is not None and entry_ts < previous_exit:
            raise RuntimeError("overlapping trades are not supported")
        side = 1 if str(trade["side"]) == "long" else -1
        entry_price = float(trade["entry_price"])
        exit_price = float(trade["exit_price"])
        leverage = (
            float(leverage_getter(trade, trade_index))
            if leverage_getter is not None
            else float(trade.get("entry_leverage", default_leverage))
        )
        entry_equity = equity
        qty, equity, turnover = target_quantity(
            equity,
            0.0,
            side,
            entry_price,
            cost_rate,
            leverage,
        )
        total_turnover += turnover
        total_cost += entry_equity - equity
        observe(entry_ts, entry_equity, "entry_pre_cost", trade_index, entry_price, side)
        observe(entry_ts, equity, "entry_post_cost", trade_index, entry_price, side, qty)
        base_equity = equity
        cumulative_funding = 0.0
        event_rows: list[tuple[pd.Timestamp, int, str, float, Any | None]] = []
        for ts, price in hourly:
            if entry_ts < ts < exit_ts:
                event_rows.append((ts, 0, "hourly_open", price, None))
        for event in funding:
            event_ts = pd.Timestamp(event.ts)
            if entry_ts <= event_ts < exit_ts:
                event_rows.append((event_ts, 1, "funding", float(event.price), event))
        event_rows.sort(key=lambda row: (row[0], row[1]))
        for event_ts, _, kind, price, event in event_rows:
            marked = base_equity + qty * (price - entry_price) - cumulative_funding
            if kind == "funding":
                observe(event_ts, marked, "funding_pre", trade_index, price, side, qty)
                if event is None:
                    raise RuntimeError("missing funding event")
                payment = qty * price * float(event.rate)
                cumulative_funding += payment
                total_funding += payment
                marked -= payment
                observe(event_ts, marked, "funding_post", trade_index, price, side, qty)
            else:
                observe(event_ts, marked, kind, trade_index, price, side, qty)
            if marked <= 0.0:
                raise RuntimeError("chronological replay bankruptcy")
        before_exit = base_equity + qty * (exit_price - entry_price) - cumulative_funding
        observe(exit_ts, before_exit, "exit_pre_cost", trade_index, exit_price, side, qty)
        old_equity = before_exit
        _, equity, turnover = target_quantity(
            before_exit,
            qty,
            0,
            exit_price,
            cost_rate,
            1.0,
        )
        total_turnover += turnover
        total_cost += old_equity - equity
        observe(exit_ts, equity, "exit_post_cost", trade_index, exit_price, 0)
        expected_equity = entry_equity + float(trade["net_pnl"])
        if not math.isclose(equity, expected_equity, rel_tol=tolerance, abs_tol=tolerance):
            raise RuntimeError(
                f"trade {trade_index} replay drift: {equity} != {expected_equity}"
            )
        previous_exit = exit_ts
    terminal_equity = float(raw.metrics["equity_multiple"])
    metric_turnover = float(raw.metrics["turnover_multiple"])
    metric_cost = float(raw.metrics["cost_pct_initial"]) / 100.0
    metric_funding = float(raw.metrics["funding_pct_initial"]) / 100.0
    parity = {
        "terminal_equity": math.isclose(
            equity, terminal_equity, rel_tol=tolerance, abs_tol=tolerance
        ),
        "turnover": math.isclose(
            total_turnover, metric_turnover, rel_tol=tolerance, abs_tol=tolerance
        ),
        "cost": math.isclose(total_cost, metric_cost, rel_tol=tolerance, abs_tol=tolerance),
        "funding": math.isclose(
            total_funding, metric_funding, rel_tol=tolerance, abs_tol=tolerance
        ),
        "trade_count": len(trades) == int(raw.metrics["closed_trades"]),
    }
    if not all(parity.values()):
        raise RuntimeError(f"chronological ledger parity failed: {parity}")
    return ReplayResult(
        terminal_equity=equity,
        chronological_1h_mdd_pct=mdd * 100.0,
        worst_ts=worst_ts,
        worst_trade_index=worst_trade,
        turnover_multiple=total_turnover,
        cost_equity_units=total_cost,
        funding_equity_units=total_funding,
        max_marked_leverage=max_leverage,
        points=tuple(points),
        parity=parity,
    )


def pareto_frontier(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep rows not dominated on higher return and more-positive MDD."""

    frontier = []
    for row in rows:
        ret = float(row["net_return_pct"])
        mdd = float(row["chronological_1h_mdd_pct"])
        dominated = any(
            float(other["net_return_pct"]) >= ret
            and float(other["chronological_1h_mdd_pct"]) >= mdd
            and (
                float(other["net_return_pct"]) > ret
                or float(other["chronological_1h_mdd_pct"]) > mdd
            )
            for other in rows
            if other is not row
        )
        if not dominated:
            frontier.append(row)
    return sorted(
        frontier,
        key=lambda row: (
            abs(float(row["chronological_1h_mdd_pct"])),
            -float(row["net_return_pct"]),
            str(row.get("id", "")),
        ),
    )


def best_by_mdd_caps(
    rows: list[dict[str, Any]],
    caps: tuple[float, ...] = (20.0, 25.0, 30.0, 35.0, 40.0, 50.0),
) -> dict[str, dict[str, Any] | None]:
    result: dict[str, dict[str, Any] | None] = {}
    for cap in caps:
        eligible = [
            row
            for row in rows
            if abs(float(row["chronological_1h_mdd_pct"])) <= cap
            and not bool(row.get("bankrupt", False))
        ]
        result[str(int(cap))] = (
            max(
                eligible,
                key=lambda row: (
                    float(row["net_return_pct"]),
                    float(row["chronological_1h_mdd_pct"]),
                    -float(row.get("max_marked_leverage", 0.0)),
                ),
            )
            if eligible
            else None
        )
    return result
