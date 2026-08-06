from __future__ import annotations

import importlib.util
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path("research/asset-portfolios/1h-price-impulse-campaign")
ARTIFACT_DIR = ROOT / "artifacts"
V0_SCRIPT = ROOT / "scripts/research_binance_1h_pic_v0.py"
RUN_DATE = "2026-08-03"
ASSETS = ("ETH", "BTC", "HYPE", "SOL")

FEE_RATE = 0.001
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
RISK_BUDGET = 0.01
MAX_LEVERAGE = 3.0
PROBE_FRACTION = 0.25
LAYER_THRESHOLDS = (0.5, 1.0, 2.0)
LAYER_FRACTIONS = (0.50, 0.75, 1.00)
ADD_COOLDOWN_HOURS = 4
VALIDATION_HOURS = 24
MAX_HOLD_HOURS = 336
EPSILON = 1e-12


@dataclass(slots=True)
class Lot:
    quantity: float
    fill: float
    layer_fraction: float


@dataclass(slots=True)
class LayeredPosition:
    side: int
    signal_ts: pd.Timestamp
    entry_ts: pd.Timestamp
    raw_entry: float
    initial_fill: float
    entry_equity: float
    r_log: float
    r_price: float
    initial_stop: float
    stop: float
    planned_full_quantity: float
    initial_probe_quantity: float
    lots: list[Lot]
    hours_held: int = 0
    max_mfe_price: float = 0.0
    max_mae_price: float = 0.0
    reached_one_r: bool = False
    last_add_hour: int = -10_000
    next_layer_index: int = 0
    add_count: int = 0
    reduce_count: int = 0
    funding_pnl: float = 0.0
    fees: float = 0.0
    realized_price_pnl: float = 0.0
    risk_violation_bars: int = 0
    max_stopout_loss_pct: float = 0.0
    max_effective_leverage: float = 0.0
    half_giveback_reduced: bool = False
    pending_add_index: int | None = None
    pending_reduce_to_probe: bool = False

    @property
    def quantity(self) -> float:
        return float(sum(lot.quantity for lot in self.lots))

    @property
    def average_fill(self) -> float:
        quantity = self.quantity
        if quantity <= EPSILON:
            return math.nan
        return float(sum(lot.quantity * lot.fill for lot in self.lots) / quantity)


@dataclass(frozen=True, slots=True)
class V1Config:
    fee_rate: float = FEE_RATE
    slippage: float = BASE_SLIPPAGE
    include_funding: bool = True
    allow_adds: bool = True
    allow_half_reduce: bool = True
    full_entry: bool = False
    side_filter: int = 0
    operational_risk_budget: float = RISK_BUDGET
    maintain_risk_after_funding: bool = False


@dataclass(frozen=True, slots=True)
class V1Result:
    metrics: dict[str, Any]
    campaigns: pd.DataFrame
    actions: pd.DataFrame
    equity: pd.DataFrame


def load_v0_module() -> Any:
    spec = importlib.util.spec_from_file_location("binance_pic_v0_shared", V0_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load V0 shared module: {V0_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def marked_equity(balance: float, position: LayeredPosition | None, mark: float) -> float:
    if position is None:
        return balance
    unrealized = sum(
        lot.quantity * position.side * (mark - lot.fill) for lot in position.lots
    )
    return float(balance + unrealized)


def stopout_equity(
    balance: float,
    position: LayeredPosition,
    stop_fill: float,
    fee_rate: float,
) -> float:
    price_pnl = sum(
        lot.quantity * position.side * (stop_fill - lot.fill)
        for lot in position.lots
    )
    exit_fee = position.quantity * stop_fill * fee_rate
    return float(balance + price_pnl - exit_fee)


def close_lifo(
    balance: float,
    position: LayeredPosition,
    close_quantity: float,
    fill: float,
    fee_rate: float,
) -> tuple[float, float, float]:
    remaining = min(close_quantity, position.quantity)
    price_pnl = 0.0
    closed = 0.0
    while remaining > EPSILON and position.lots:
        lot = position.lots[-1]
        take = min(remaining, lot.quantity)
        price_pnl += take * position.side * (fill - lot.fill)
        lot.quantity -= take
        remaining -= take
        closed += take
        if lot.quantity <= EPSILON:
            position.lots.pop()
    fee = closed * fill * fee_rate
    balance += price_pnl - fee
    position.realized_price_pnl += price_pnl
    position.fees += fee
    return balance, price_pnl, fee


def maximum_safe_add_quantity(
    balance: float,
    position: LayeredPosition,
    add_fill: float,
    raw_mark: float,
    desired_quantity: float,
    config: V1Config,
    adverse_fill: Any,
) -> float:
    if desired_quantity <= EPSILON:
        return 0.0
    stop_fill = adverse_fill(position.stop, -position.side, config.slippage)
    current_stopout = stopout_equity(balance, position, stop_fill, config.fee_rate)
    floor = position.entry_equity * (1.0 - config.operational_risk_budget)
    residual = max(0.0, current_stopout - floor)
    incremental_loss = (
        add_fill * config.fee_rate
        + position.side * (add_fill - stop_fill)
        + stop_fill * config.fee_rate
    )
    risk_cap = residual / incremental_loss if incremental_loss > EPSILON else desired_quantity
    current_equity = marked_equity(balance, position, raw_mark)
    leverage_cap = max(
        0.0,
        MAX_LEVERAGE * current_equity / add_fill - position.quantity,
    )
    return max(0.0, min(desired_quantity, risk_cap, leverage_cap))


def quantity_to_restore_stopout(
    balance: float,
    position: LayeredPosition,
    raw_open: float,
    config: V1Config,
    adverse_fill: Any,
) -> float:
    """Return added-layer quantity to close so projected stop-out meets the operating floor."""
    stop_fill = adverse_fill(position.stop, -position.side, config.slippage)
    projected = stopout_equity(balance, position, stop_fill, config.fee_rate)
    floor = position.entry_equity * (1.0 - config.operational_risk_budget)
    deficit = max(0.0, floor - projected)
    if deficit <= EPSILON:
        return 0.0
    reduce_fill = adverse_fill(raw_open, -position.side, config.slippage)
    improvement_per_quantity = (
        position.side * (reduce_fill - stop_fill)
        - reduce_fill * config.fee_rate
        + stop_fill * config.fee_rate
    )
    if improvement_per_quantity <= EPSILON:
        return max(0.0, position.quantity - position.initial_probe_quantity)
    required = deficit / improvement_per_quantity
    removable = max(0.0, position.quantity - position.initial_probe_quantity)
    return max(0.0, min(required, removable))


def _safe_sharpe(equity: pd.Series) -> float:
    returns = equity.pct_change().fillna(equity.iloc[0] - 1.0)
    volatility = float(returns.std(ddof=0))
    if volatility <= EPSILON:
        return 0.0
    return float(returns.mean() / volatility * math.sqrt(365.0 * 24.0))


def summarize(
    equity: pd.DataFrame,
    campaigns: pd.DataFrame,
    actions: pd.DataFrame,
    max_effective_leverage: float,
    risk_violations: int,
    risk_violation_campaigns: int,
    max_stopout_loss_pct: float,
    config: V1Config,
) -> dict[str, Any]:
    values = equity["equity"].astype(float)
    drawdown = values / values.cummax() - 1.0
    closed = campaigns.loc[campaigns["closed"]].copy() if not campaigns.empty else campaigns
    gains = float(closed.loc[closed["net_pnl"].gt(0.0), "net_pnl"].sum()) if not closed.empty else 0.0
    losses = float(-closed.loc[closed["net_pnl"].lt(0.0), "net_pnl"].sum()) if not closed.empty else 0.0
    return {
        "total_return_pct": float((values.iloc[-1] / values.iloc[0] - 1.0) * 100.0),
        "sharpe": _safe_sharpe(values),
        "max_drawdown_pct": float(drawdown.min() * 100.0),
        "campaigns": int(len(closed)),
        "win_rate_pct": float(closed["net_pnl"].gt(0.0).mean() * 100.0) if not closed.empty else 0.0,
        "profit_factor": gains / losses if losses > EPSILON else math.inf,
        "avg_hold_hours": float(closed["hold_hours"].mean()) if not closed.empty else 0.0,
        "avg_pnl_r": float(closed["pnl_r"].mean()) if not closed.empty else 0.0,
        "worst_pnl_r": float(closed["pnl_r"].min()) if not closed.empty else 0.0,
        "adds": int(actions["action"].eq("add").sum()) if not actions.empty else 0,
        "reductions": int(actions["action"].eq("reduce_to_probe").sum()) if not actions.empty else 0,
        "risk_trims": int(actions["action"].eq("risk_trim").sum()) if not actions.empty else 0,
        "max_effective_leverage": max_effective_leverage,
        "risk_violations": risk_violations,
        "risk_violation_campaigns": risk_violation_campaigns,
        "max_stopout_loss_pct": max_stopout_loss_pct,
        "fee_rate": config.fee_rate,
        "slippage": config.slippage,
        "include_funding": config.include_funding,
        "allow_adds": config.allow_adds,
        "allow_half_reduce": config.allow_half_reduce,
        "full_entry": config.full_entry,
        "side_filter": config.side_filter,
        "operational_risk_budget": config.operational_risk_budget,
        "maintain_risk_after_funding": config.maintain_risk_after_funding,
    }


def run_backtest(
    hourly: pd.DataFrame,
    config: V1Config,
    shared: Any,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> V1Result:
    frame = shared.build_features(hourly)
    if start is not None:
        start = pd.Timestamp(start)
        start = start.tz_localize("UTC") if start.tzinfo is None else start.tz_convert("UTC")
    if end is not None:
        end = pd.Timestamp(end)
        end = end.tz_localize("UTC") if end.tzinfo is None else end.tz_convert("UTC")

    balance = 1.0
    position: LayeredPosition | None = None
    pending_signal: dict[str, Any] | None = None
    campaigns: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    equity_rows: list[dict[str, Any]] = []
    campaign_id = 0
    max_effective_leverage = 0.0
    risk_violations = 0
    risk_violation_campaign_ids: set[int] = set()
    max_stopout_loss_pct = 0.0

    def close_all(ts: pd.Timestamp, raw_price: float, reason: str, closed: bool = True) -> None:
        nonlocal balance, position
        if position is None:
            return
        current = position
        fill = shared.adverse_fill(raw_price, -current.side, config.slippage)
        quantity = current.quantity
        balance, price_pnl, fee = close_lifo(
            balance, current, quantity, fill, config.fee_rate
        )
        actions.append(
            {
                "campaign_id": campaign_id,
                "ts": ts,
                "action": "exit",
                "reason": reason,
                "raw_price": raw_price,
                "fill": fill,
                "delta_quantity": -current.side * quantity,
                "post_quantity": 0.0,
                "fee": fee,
            }
        )
        net_pnl = balance - current.entry_equity
        campaigns.append(
            {
                "campaign_id": campaign_id,
                "signal_ts": current.signal_ts,
                "entry_ts": current.entry_ts,
                "exit_ts": ts,
                "side": current.side,
                "entry_equity": current.entry_equity,
                "exit_equity": balance,
                "raw_entry": current.raw_entry,
                "initial_fill": current.initial_fill,
                "exit_fill": fill,
                "planned_full_quantity": current.planned_full_quantity,
                "initial_probe_quantity": current.initial_probe_quantity,
                "initial_stop": current.initial_stop,
                "hold_hours": current.hours_held,
                "max_mfe_r": current.max_mfe_price / current.r_price,
                "max_mae_r": current.max_mae_price / current.r_price,
                "add_count": current.add_count,
                "reduce_count": current.reduce_count,
                "half_giveback_reduced": current.half_giveback_reduced,
                "fees": current.fees,
                "funding_pnl": current.funding_pnl,
                "realized_price_pnl": current.realized_price_pnl,
                "risk_violation_bars": current.risk_violation_bars,
                "max_stopout_loss_pct": current.max_stopout_loss_pct,
                "last_exit_price_pnl": price_pnl,
                "net_pnl": net_pnl,
                "pnl_r": net_pnl / (RISK_BUDGET * current.entry_equity),
                "exit_reason": reason,
                "max_effective_leverage": current.max_effective_leverage,
                "closed": closed,
            }
        )
        position = None

    def execute_reduce(ts: pd.Timestamp, raw_open: float) -> None:
        nonlocal balance
        if position is None or not position.pending_reduce_to_probe:
            return
        position.pending_reduce_to_probe = False
        excess = max(0.0, position.quantity - position.initial_probe_quantity)
        if excess <= EPSILON:
            position.half_giveback_reduced = True
            return
        fill = shared.adverse_fill(raw_open, -position.side, config.slippage)
        balance, _, fee = close_lifo(
            balance, position, excess, fill, config.fee_rate
        )
        position.reduce_count += 1
        position.half_giveback_reduced = True
        actions.append(
            {
                "campaign_id": campaign_id,
                "ts": ts,
                "action": "reduce_to_probe",
                "reason": "half_mfe_giveback_after_2r",
                "raw_price": raw_open,
                "fill": fill,
                "delta_quantity": -position.side * excess,
                "post_quantity": position.quantity,
                "fee": fee,
            }
        )

    def execute_add(ts: pd.Timestamp, raw_open: float) -> None:
        nonlocal balance
        if position is None or position.pending_add_index is None:
            return
        layer_index = position.pending_add_index
        position.pending_add_index = None
        if position.half_giveback_reduced or not config.allow_adds:
            return
        target_fraction = LAYER_FRACTIONS[layer_index]
        target_quantity = position.planned_full_quantity * target_fraction
        desired = max(0.0, target_quantity - position.quantity)
        add_fill = shared.adverse_fill(raw_open, position.side, config.slippage)
        safe = maximum_safe_add_quantity(
            balance,
            position,
            add_fill,
            raw_open,
            desired,
            config,
            shared.adverse_fill,
        )
        if safe <= EPSILON:
            return
        fee = safe * add_fill * config.fee_rate
        balance -= fee
        position.fees += fee
        position.lots.append(Lot(safe, add_fill, target_fraction))
        position.add_count += 1
        position.last_add_hour = position.hours_held
        position.next_layer_index = max(position.next_layer_index, layer_index + 1)
        actions.append(
            {
                "campaign_id": campaign_id,
                "ts": ts,
                "action": "add",
                "reason": f"mfe_{LAYER_THRESHOLDS[layer_index]}r",
                "raw_price": raw_open,
                "fill": add_fill,
                "delta_quantity": position.side * safe,
                "post_quantity": position.quantity,
                "fee": fee,
                "target_fraction": target_fraction,
            }
        )

    def execute_risk_maintenance(ts: pd.Timestamp, raw_open: float) -> None:
        nonlocal balance
        if position is None or not config.maintain_risk_after_funding:
            return
        quantity = quantity_to_restore_stopout(
            balance,
            position,
            raw_open,
            config,
            shared.adverse_fill,
        )
        if quantity > EPSILON:
            fill = shared.adverse_fill(raw_open, -position.side, config.slippage)
            balance, _, fee = close_lifo(
                balance, position, quantity, fill, config.fee_rate
            )
            position.reduce_count += 1
            actions.append(
                {
                    "campaign_id": campaign_id,
                    "ts": ts,
                    "action": "risk_trim",
                    "reason": "restore_operational_stopout_budget",
                    "raw_price": raw_open,
                    "fill": fill,
                    "delta_quantity": -position.side * quantity,
                    "post_quantity": position.quantity,
                    "fee": fee,
                }
            )
        stop_fill = shared.adverse_fill(position.stop, -position.side, config.slippage)
        projected = stopout_equity(balance, position, stop_fill, config.fee_rate)
        floor = position.entry_equity * (1.0 - config.operational_risk_budget)
        if projected < floor - 1e-9:
            close_all(ts, raw_open, "risk_budget_exhausted")

    for visible_ts, row in frame.iterrows():
        if start is not None and visible_ts < start:
            continue
        if end is not None and visible_ts > end:
            break
        raw_open = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        execution_ts = visible_ts - pd.Timedelta(hours=1)

        if position is not None:
            gap_hit = (position.side > 0 and raw_open <= position.stop) or (
                position.side < 0 and raw_open >= position.stop
            )
            if gap_hit:
                close_all(execution_ts, raw_open, "stop_gap")

        if position is not None:
            if position.hours_held >= VALIDATION_HOURS and not position.reached_one_r:
                close_all(execution_ts, raw_open, "validation_failed_24h")
            elif position.hours_held >= MAX_HOLD_HOURS:
                close_all(execution_ts, raw_open, "timeout_336h")

        if position is not None:
            execute_reduce(execution_ts, raw_open)
            execute_add(execution_ts, raw_open)

        if pending_signal is not None and position is None:
            side = int(pending_signal["side"])
            fill = shared.adverse_fill(raw_open, side, config.slippage)
            r_log = float(pending_signal["r_log"])
            stop = shared.initial_stop(fill, side, r_log)
            full_quantity, _ = shared.planned_quantity(
                balance,
                fill,
                stop,
                side,
                config.fee_rate,
                config.slippage,
            )
            entry_fraction = 1.0 if config.full_entry else PROBE_FRACTION
            quantity = full_quantity * entry_fraction
            if quantity > EPSILON:
                campaign_id += 1
                entry_equity = balance
                fee = quantity * fill * config.fee_rate
                balance -= fee
                r_price = abs(fill - stop)
                position = LayeredPosition(
                    side=side,
                    signal_ts=pending_signal["signal_ts"],
                    entry_ts=execution_ts,
                    raw_entry=raw_open,
                    initial_fill=fill,
                    entry_equity=entry_equity,
                    r_log=r_log,
                    r_price=r_price,
                    initial_stop=stop,
                    stop=stop,
                    planned_full_quantity=full_quantity,
                    initial_probe_quantity=quantity,
                    lots=[Lot(quantity, fill, entry_fraction)],
                    fees=fee,
                )
                actions.append(
                    {
                        "campaign_id": campaign_id,
                        "ts": execution_ts,
                        "action": "entry",
                        "reason": "scaled_impulse",
                        "raw_price": raw_open,
                        "fill": fill,
                        "delta_quantity": side * quantity,
                        "post_quantity": quantity,
                        "fee": fee,
                        "target_fraction": entry_fraction,
                    }
                )
            pending_signal = None

        if position is not None:
            funding_rate = float(row["funding_rate"]) if config.include_funding else 0.0
            funding_pnl = -position.side * position.quantity * raw_open * funding_rate
            balance += funding_pnl
            position.funding_pnl += funding_pnl
            execute_risk_maintenance(execution_ts, raw_open)

        if position is not None:
            stop_hit = (position.side > 0 and low <= position.stop) or (
                position.side < 0 and high >= position.stop
            )
            if stop_hit:
                close_all(visible_ts, position.stop, "stop_intrabar")

        if position is not None:
            favorable = high - position.initial_fill if position.side > 0 else position.initial_fill - low
            adverse = position.initial_fill - low if position.side > 0 else high - position.initial_fill
            position.max_mfe_price = max(position.max_mfe_price, favorable, 0.0)
            position.max_mae_price = max(position.max_mae_price, adverse, 0.0)
            mfe_r = position.max_mfe_price / position.r_price
            position.reached_one_r = position.reached_one_r or mfe_r >= 1.0
            current_progress = position.side * (close - position.initial_fill)
            estimated_exit = shared.adverse_fill(close, -position.side, config.slippage)
            estimated_equity = stopout_equity(
                balance, position, estimated_exit, config.fee_rate
            )
            net_marked_positive = estimated_equity > position.entry_equity

            if (
                config.allow_half_reduce
                and not position.half_giveback_reduced
                and position.quantity > position.initial_probe_quantity + EPSILON
                and mfe_r >= 2.0
                and current_progress < 0.5 * position.max_mfe_price
            ):
                position.pending_reduce_to_probe = True
                position.pending_add_index = None
            elif (
                config.allow_adds
                and not position.half_giveback_reduced
                and position.pending_add_index is None
                and position.next_layer_index < len(LAYER_THRESHOLDS)
                and mfe_r >= LAYER_THRESHOLDS[position.next_layer_index]
                and position.hours_held - position.last_add_hour >= ADD_COOLDOWN_HOURS
                and net_marked_positive
            ):
                position.pending_add_index = position.next_layer_index

            position.hours_held += 1
            current_equity = marked_equity(balance, position, close)
            effective = position.quantity * close / max(current_equity, EPSILON)
            position.max_effective_leverage = max(position.max_effective_leverage, effective)
            max_effective_leverage = max(max_effective_leverage, effective)

            stop_fill = shared.adverse_fill(position.stop, -position.side, config.slippage)
            projected_stopout = stopout_equity(
                balance, position, stop_fill, config.fee_rate
            )
            stopout_loss_pct = max(
                0.0,
                (position.entry_equity - projected_stopout)
                / position.entry_equity
                * 100.0,
            )
            max_stopout_loss_pct = max(max_stopout_loss_pct, stopout_loss_pct)
            position.max_stopout_loss_pct = max(
                position.max_stopout_loss_pct, stopout_loss_pct
            )
            if projected_stopout < position.entry_equity * (1.0 - RISK_BUDGET) - 1e-9:
                risk_violations += 1
                position.risk_violation_bars += 1
                risk_violation_campaign_ids.add(campaign_id)

        if position is None and bool(row["signal"]):
            side = int(row["signal_side"])
            if config.side_filter == 0 or side == config.side_filter:
                pending_signal = {
                    "signal_ts": visible_ts,
                    "side": side,
                    "r_log": float(row["past_rms"] * math.sqrt(24.0)),
                }

        equity_rows.append(
            {
                "ts": visible_ts,
                "equity": marked_equity(balance, position, close),
                "balance": balance,
                "side": 0 if position is None else position.side,
                "quantity": 0.0 if position is None else position.quantity,
                "mark": close,
                "stop": math.nan if position is None else position.stop,
            }
        )

    if position is not None:
        close_all(frame.index[-1], float(frame.iloc[-1]["close"]), "data_end", closed=False)
        equity_rows[-1].update(
            {"equity": balance, "balance": balance, "side": 0, "quantity": 0.0, "stop": math.nan}
        )

    campaign_frame = pd.DataFrame(campaigns)
    action_frame = pd.DataFrame(actions)
    equity_frame = pd.DataFrame(equity_rows)
    metrics = summarize(
        equity_frame,
        campaign_frame,
        action_frame,
        max_effective_leverage,
        risk_violations,
        len(risk_violation_campaign_ids),
        max_stopout_loss_pct,
        config,
    )
    return V1Result(metrics, campaign_frame, action_frame, equity_frame)


def recent_slice_starts(end: pd.Timestamp) -> dict[str, pd.Timestamp]:
    return {
        "1d": end - pd.Timedelta(days=1),
        "7d": end - pd.Timedelta(days=7),
        "1m": end - pd.DateOffset(months=1),
        "3m": end - pd.DateOffset(months=3),
        "6m": end - pd.DateOffset(months=6),
        "1y": end - pd.DateOffset(years=1),
    }


def rolling_windows(hourly: pd.DataFrame, config: V1Config, shared: Any) -> pd.DataFrame:
    earliest = hourly.index.min() + pd.Timedelta(hours=shared.PAST_RMS_HOURS + shared.IMPULSE_HOURS)
    latest = hourly.index.max()
    cursor = earliest.ceil("1D")
    rows: list[dict[str, Any]] = []
    while cursor + pd.Timedelta(days=120) <= latest:
        end = cursor + pd.Timedelta(days=120)
        result = run_backtest(hourly, config, shared, cursor, end)
        rows.append({"start": cursor, "end": end, **result.metrics})
        cursor += pd.Timedelta(days=30)
    return pd.DataFrame(rows)


def frame_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    return json.loads(frame.to_json(orient="records", date_format="iso"))


def decision(
    metrics: pd.DataFrame,
    slices: pd.DataFrame,
    rolling: pd.DataFrame,
    ablation: pd.DataFrame,
) -> dict[str, Any]:
    base = metrics.loc[
        metrics["asset"].eq("ETH")
        & metrics["cost_model"].eq("base")
        & metrics["arm"].eq("all")
    ].iloc[0]
    stress = metrics.loc[
        metrics["asset"].eq("ETH")
        & metrics["cost_model"].eq("stress_8bps")
        & metrics["arm"].eq("all")
    ].iloc[0]
    six_month = slices.loc[slices["slice"].eq("6m")].iloc[0]
    positive_ratio = float(rolling["total_return_pct"].gt(0.0).mean())
    probe_only = ablation.loc[ablation["variant"].eq("probe_only")].iloc[0]
    gates = {
        "base_return_positive": bool(base["total_return_pct"] > 0.0),
        "base_sharpe_positive": bool(base["sharpe"] > 0.0),
        "mdd_within_20pct": bool(base["max_drawdown_pct"] > -20.0),
        "campaigns_at_least_30": bool(base["campaigns"] >= 30),
        "recent_6m_non_negative": bool(six_month["total_return_pct"] >= 0.0),
        "rolling_positive_ratio_at_least_60pct": bool(positive_ratio >= 0.60),
        "stress_non_negative": bool(stress["total_return_pct"] >= 0.0),
        "no_risk_violation": bool(base["risk_violations"] == 0),
        "leverage_cap_respected": bool(base["max_effective_leverage"] <= 3.0 + 1e-9),
        "full_not_worse_than_probe_only": bool(
            base["total_return_pct"] >= probe_only["total_return_pct"]
        ),
    }
    return {
        "all_minimum_gates_pass": bool(all(gates.values())),
        "rolling_positive_ratio": positive_ratio,
        "gates": gates,
        "selection_boundary": (
            "V1 was designed after V0 full-history reveal; historical pass cannot "
            "authorize promotion without new prospective OOS"
        ),
    }


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    shared = load_v0_module()
    assets, quality = shared.load_assets()

    metrics_rows: list[dict[str, Any]] = []
    campaigns: list[pd.DataFrame] = []
    actions: list[pd.DataFrame] = []
    equities: list[pd.DataFrame] = []
    cost_models = {
        "gross": V1Config(fee_rate=0.0, slippage=0.0, include_funding=False),
        "base": V1Config(),
        "stress_8bps": V1Config(slippage=STRESS_SLIPPAGE),
    }
    arms = {"all": 0, "long": 1, "short": -1}
    for asset in ASSETS:
        for cost_name, base_config in cost_models.items():
            for arm, side_filter in arms.items():
                config = V1Config(
                    fee_rate=base_config.fee_rate,
                    slippage=base_config.slippage,
                    include_funding=base_config.include_funding,
                    side_filter=side_filter,
                )
                result = run_backtest(assets[asset], config, shared)
                metrics_rows.append(
                    {"asset": asset, "cost_model": cost_name, "arm": arm, **result.metrics}
                )
                if cost_name == "base" and arm == "all":
                    for frame, target in (
                        (result.campaigns, campaigns),
                        (result.actions, actions),
                        (result.equity, equities),
                    ):
                        if not frame.empty:
                            copy = frame.copy()
                            copy["asset"] = asset
                            target.append(copy)

    eth = assets["ETH"]
    slices_rows: list[dict[str, Any]] = []
    end = eth.index.max()
    for name, start in recent_slice_starts(end).items():
        result = run_backtest(eth, V1Config(), shared, start, end)
        slices_rows.append({"slice": name, "start": start, "end": end, **result.metrics})
    slices = pd.DataFrame(slices_rows)
    rolling = rolling_windows(eth, V1Config(), shared)

    variants = {
        "full": V1Config(),
        "probe_only": V1Config(allow_adds=False, allow_half_reduce=False),
        "no_half_reduce": V1Config(allow_half_reduce=False),
        "full_entry_no_add": V1Config(
            allow_adds=False,
            allow_half_reduce=False,
            full_entry=True,
        ),
    }
    ablation_rows: list[dict[str, Any]] = []
    for name, config in variants.items():
        result = run_backtest(eth, config, shared)
        ablation_rows.append({"variant": name, **result.metrics})
    ablation = pd.DataFrame(ablation_rows)

    metrics = pd.DataFrame(metrics_rows)
    campaign_frame = pd.concat(campaigns, ignore_index=True) if campaigns else pd.DataFrame()
    action_frame = pd.concat(actions, ignore_index=True) if actions else pd.DataFrame()
    equity_frame = pd.concat(equities, ignore_index=True) if equities else pd.DataFrame()
    verdict = decision(metrics, slices, rolling, ablation)
    outputs = {
        "metrics": metrics,
        "campaigns": campaign_frame,
        "actions": action_frame,
        "equity": equity_frame,
        "recent_slices": slices,
        "rolling_120d": rolling,
        "ablation": ablation,
    }
    for name, frame in outputs.items():
        suffix = "parquet" if name == "equity" else "csv"
        path = ARTIFACT_DIR / f"binance_1h_pic_v1_{name}_{RUN_DATE}.{suffix}"
        if suffix == "parquet":
            frame.to_parquet(path, index=False)
        else:
            frame.to_csv(path, index=False)

    payload = {
        "family": "Binance-1H-Price-Impulse-Campaign",
        "candidate_id": "BIN-1H-PIC-V1",
        "status": "explore / not promoted / not live-ready",
        "data_quality": quality,
        "verdict": verdict,
        "contract": {
            "probe_fraction": PROBE_FRACTION,
            "layer_thresholds_r": LAYER_THRESHOLDS,
            "layer_fractions": LAYER_FRACTIONS,
            "risk_budget": RISK_BUDGET,
            "max_leverage": MAX_LEVERAGE,
            "half_giveback_action": "reduce to original probe, no re-add",
        },
        "summaries": {
            name: frame_records(frame)
            for name, frame in outputs.items()
            if name != "equity"
        },
    }
    with (ARTIFACT_DIR / f"binance_1h_pic_v1_research_{RUN_DATE}.json").open(
        "w", encoding="utf-8"
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)

    print("V1 LAYERED METRICS")
    print(
        metrics.loc[
            metrics["arm"].eq("all"),
            [
                "asset",
                "cost_model",
                "total_return_pct",
                "sharpe",
                "max_drawdown_pct",
                "campaigns",
                "profit_factor",
                "adds",
                "reductions",
                "max_effective_leverage",
                "risk_violations",
                "risk_violation_campaigns",
                "max_stopout_loss_pct",
            ],
        ].to_string(index=False)
    )
    print("\nETH SLICES")
    print(slices[["slice", "total_return_pct", "sharpe", "max_drawdown_pct", "campaigns"]].to_string(index=False))
    print("\nETH ABLATION")
    print(ablation[["variant", "total_return_pct", "sharpe", "max_drawdown_pct", "campaigns", "adds", "reductions"]].to_string(index=False))
    print("\nVERDICT")
    print(json.dumps(verdict, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
