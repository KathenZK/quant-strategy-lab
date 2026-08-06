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
from scipy.stats import skew
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from strategy_lab.data import DataLakeLayout, DuckDBWarehouse
from strategy_lab.data.settings import load_settings


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/multi-timeframe-pullback-trend-campaign"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
ENTRY_PATH = FAMILY_DIR / "scripts/diagnose_pullback_entry_v0.py"
SYMBOLS = {"BTC": "BTC/USDT:USDT", "ETH": "ETH/USDT:USDT", "HYPE": "HYPE/USDT:USDT"}
SELECTED = {
    "BTC": {"onset": 24, "quantile": 0.80, "min_atr": 0.50, "max_retrace": 0.50, "restart": 4, "stop_buffer": 0.25},
    "ETH": {"onset": 24, "quantile": 0.90, "min_atr": 0.50, "max_retrace": 0.60, "restart": 1, "stop_buffer": 0.25},
    "HYPE": {"onset": 24, "quantile": 0.60, "min_atr": 0.75, "max_retrace": 0.60, "restart": 1, "stop_buffer": 0.25},
}
LAYER_THRESHOLDS = (0.5, 1.0, 2.0)
LAYER_RISK = 0.0025
OPERATIONAL_RISK = 0.009
HARD_RISK = 0.010
MAX_LEVERAGE = 3.0
VALIDATION_HOURS = 24
MAX_HOLD_HOURS = 336
EPSILON = 1e-12


@dataclass(frozen=True, slots=True)
class Config:
    name: str
    fee_rate: float = 0.001
    slippage: float = 0.0004
    include_funding: bool = True
    allow_adds: bool = True
    allow_half_reduce: bool = True
    allow_opposite_reduce: bool = True
    max_layers: int = 3
    layer_risk: float = LAYER_RISK
    operational_risk: float = OPERATIONAL_RISK
    hard_risk: float = HARD_RISK


@dataclass(slots=True)
class Lot:
    layer: int
    quantity: float
    fill: float
    stop: float
    entry_ts: pd.Timestamp
    entry_fee: float


@dataclass(slots=True)
class Campaign:
    campaign_id: int
    side: int
    candidate_ts: pd.Timestamp
    entry_ts: pd.Timestamp
    entry_equity: float
    initial_fill: float
    initial_stop: float
    initial_r: float
    lots: list[Lot]
    entry_intrabar: bool = False
    max_mfe_price: float = 0.0
    max_mae_price: float = 0.0
    reached_one_r: bool = False
    eligibility_ts: dict[int, pd.Timestamp] = field(default_factory=dict)
    next_layer: int = 1
    attempt_counts: dict[int, int] = field(default_factory=lambda: {1: 0, 2: 0, 3: 0})
    pending_add: dict[str, Any] | None = None
    pending_reduce_reason: str | None = None
    adds_disabled: bool = False
    half_reduced: bool = False
    funding_pnl: float = 0.0
    fees: float = 0.0
    max_effective_leverage: float = 0.0
    max_stop_risk_pct: float = 0.0
    score_observations: int = 0
    last_probability: float = math.nan

    @property
    def quantity(self) -> float:
        return float(sum(lot.quantity for lot in self.lots))


@dataclass(frozen=True, slots=True)
class Result:
    metrics: dict[str, Any]
    campaigns: pd.DataFrame
    actions: pd.DataFrame
    equity: pd.DataFrame


def load_path(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def adverse_fill(price: float, order_side: int, slippage: float) -> float:
    return price * (1.0 + order_side * slippage)


def fit_score_frame(meter: Any, hourly: pd.DataFrame, params: dict[str, Any], dev_end: pd.Timestamp, start: pd.Timestamp, end: pd.Timestamp) -> tuple[pd.DataFrame, float]:
    events = meter.build_events(hourly, int(params["onset"]))
    events["label"] = meter.label_events(events, hourly, 72)
    train = events.loc[(events.index <= dev_end - pd.Timedelta(days=14)) & events["label"].notna()].copy()
    target = events.loc[(events.index >= start) & (events.index <= end)].copy()
    if len(train) < 100 or len(target) < 10 or train["label"].nunique() < 2:
        return pd.DataFrame(), math.nan
    model = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000))
    model.fit(train[list(meter.FEATURES)], train["label"].astype(int))
    train_probability = model.predict_proba(train[list(meter.FEATURES)])[:, 1]
    threshold = float(np.quantile(train_probability, float(params["quantile"])))
    target["probability"] = model.predict_proba(target[list(meter.FEATURES)])[:, 1]
    target["strong"] = target["probability"].ge(threshold)
    return target, threshold


def build_attempts(entry: Any, scores: pd.DataFrame, hourly: pd.DataFrame, bars15: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    atr = entry.hourly_atr(hourly)
    rows: list[dict[str, Any]] = []
    for candidate_ts, event in scores.loc[scores["strong"]].iterrows():
        side = int(event["direction"])
        entry_ts, _, stop, status = entry.find_pullback_entry(
            candidate_ts,
            side,
            hourly,
            bars15,
            atr,
            onset_hours=int(params["onset"]),
            min_atr=float(params["min_atr"]),
            max_retrace=float(params["max_retrace"]),
            restart_lookback=int(params["restart"]),
            stop_buffer_atr=float(params["stop_buffer"]),
        )
        raw_entry = float(bars15.loc[entry_ts, "open"]) if entry_ts is not None and entry_ts in bars15.index else math.nan
        rows.append(
            {
                "candidate_ts": candidate_ts,
                "side": side,
                "probability": float(event["probability"]),
                "entry_ts": entry_ts,
                "resolved_ts": entry_ts if entry_ts is not None else candidate_ts + pd.Timedelta(hours=24),
                "raw_entry": raw_entry,
                "stop": stop,
                "status": status,
            }
        )
    return pd.DataFrame(rows)


def liquidation_equity(balance: float, campaign: Campaign | None, raw_mark: float, config: Config) -> float:
    if campaign is None:
        return balance
    total = balance
    for lot in campaign.lots:
        fill = adverse_fill(raw_mark, -campaign.side, config.slippage)
        total += lot.quantity * campaign.side * (fill - lot.fill) - lot.quantity * fill * config.fee_rate
    return float(total)


def projected_stopout(balance: float, campaign: Campaign, config: Config) -> float:
    total = balance
    for lot in campaign.lots:
        fill = adverse_fill(lot.stop, -campaign.side, config.slippage)
        total += lot.quantity * campaign.side * (fill - lot.fill) - lot.quantity * fill * config.fee_rate
    return float(total)


def requested_quantity(equity: float, fill: float, stop: float, side: int, config: Config) -> float:
    stop_fill = adverse_fill(stop, -side, config.slippage)
    loss_per_unit = side * (fill - stop_fill) + config.fee_rate * (fill + stop_fill)
    if loss_per_unit <= EPSILON:
        return 0.0
    return max(0.0, equity * config.layer_risk / loss_per_unit)


def safe_add_quantity(balance: float, campaign: Campaign, raw_open: float, fill: float, stop: float, desired: float, config: Config) -> float:
    if desired <= EPSILON:
        return 0.0
    stop_fill = adverse_fill(stop, -campaign.side, config.slippage)
    current_projected = projected_stopout(balance, campaign, config)
    floor = campaign.entry_equity * (1.0 - config.operational_risk)
    residual = max(0.0, current_projected - floor)
    incremental_loss = campaign.side * (fill - stop_fill) + config.fee_rate * (fill + stop_fill)
    risk_cap = residual / incremental_loss if incremental_loss > EPSILON else desired
    current_equity = liquidation_equity(balance, campaign, raw_open, config)
    leverage_cap = max(0.0, MAX_LEVERAGE * current_equity / fill - campaign.quantity)
    return max(0.0, min(desired, risk_cap, leverage_cap))


def summarize(equity: pd.DataFrame, campaigns: pd.DataFrame, actions: pd.DataFrame, config: Config, risk_violations: int, max_leverage: float, max_stop_risk: float) -> dict[str, Any]:
    values = equity["equity"].astype(float)
    drawdown = values / values.cummax() - 1.0
    adverse_drawdown = equity["intrabar_adverse_equity"].astype(float) / equity["running_peak_before_bar"].astype(float) - 1.0
    closed = campaigns.loc[campaigns["closed"]].copy() if not campaigns.empty else campaigns
    gains = float(closed.loc[closed["net_pnl"].gt(0), "net_pnl"].sum()) if len(closed) else 0.0
    losses = float(-closed.loc[closed["net_pnl"].lt(0), "net_pnl"].sum()) if len(closed) else 0.0
    positive = closed.loc[closed["net_pnl"].gt(0), "net_pnl"].sort_values(ascending=False) if len(closed) else pd.Series(dtype=float)
    daily = values.set_axis(pd.DatetimeIndex(equity["ts"])).resample("1D").last().pct_change().dropna()
    volatility = float(daily.std(ddof=0))
    elapsed_days = max((pd.Timestamp(equity.iloc[-1]["ts"]) - pd.Timestamp(equity.iloc[0]["ts"])) / pd.Timedelta(days=1), 1.0)
    annual_multiple = float((values.iloc[-1] / values.iloc[0]) ** (365.0 / elapsed_days))
    return {
        "config": config.name,
        "total_return_pct": float((values.iloc[-1] / values.iloc[0] - 1.0) * 100.0),
        "annual_equity_multiple": annual_multiple,
        "cagr_pct": (annual_multiple - 1.0) * 100.0,
        "max_drawdown_pct": float(drawdown.min() * 100.0),
        "intrabar_max_drawdown_pct": float(adverse_drawdown.min() * 100.0),
        "sharpe_daily": float(daily.mean() / volatility * math.sqrt(365.0)) if volatility > EPSILON else 0.0,
        "campaigns": int(len(closed)),
        "win_rate_pct": float(closed["net_pnl"].gt(0).mean() * 100.0) if len(closed) else 0.0,
        "profit_factor": gains / losses if losses > EPSILON else math.inf,
        "mean_pnl_r": float(closed["pnl_r"].mean()) if len(closed) else 0.0,
        "skew_pnl_r": float(skew(closed["pnl_r"], bias=False)) if len(closed) >= 3 else math.nan,
        "top1_gross_profit_concentration": float(positive.head(1).sum() / positive.sum()) if positive.sum() > 0 else math.nan,
        "top3_gross_profit_concentration": float(positive.head(3).sum() / positive.sum()) if positive.sum() > 0 else math.nan,
        "lots_added": int(actions["action"].eq("add").sum()) if len(actions) else 0,
        "reductions": int(((actions["action"].eq("lot_exit") & actions["reason"].isin(["half_giveback_reduce", "opposite_score_reduce", "risk_trim"])) | actions["action"].eq("risk_trim")).sum()) if len(actions) else 0,
        "fees": float(campaigns["fees"].sum()) if len(campaigns) else 0.0,
        "funding_pnl": float(campaigns["funding_pnl"].sum()) if len(campaigns) else 0.0,
        "max_effective_leverage": float(max_leverage),
        "max_projected_stop_risk_pct": float(max_stop_risk),
        "risk_violations": int(risk_violations),
        "fee_rate": config.fee_rate,
        "slippage": config.slippage,
        "include_funding": config.include_funding,
        "max_layers": config.max_layers,
        "layer_risk_pct": config.layer_risk * 100.0,
        "operational_risk_pct": config.operational_risk * 100.0,
        "hard_risk_pct": config.hard_risk * 100.0,
    }


def run_engine(asset: str, bars15: pd.DataFrame, funding: pd.Series, scores: pd.DataFrame, attempts: pd.DataFrame, threshold: float, start: pd.Timestamp, end: pd.Timestamp, config: Config) -> Result:
    bars = bars15.loc[(bars15.index >= start) & (bars15.index <= end)].copy()
    funding_aligned = funding.reindex(bars.index).fillna(0.0)
    attempt_candidates = {ts: part.to_dict(orient="records") for ts, part in attempts.groupby("candidate_ts")} if len(attempts) else {}
    score_map = scores.to_dict(orient="index") if len(scores) else {}

    balance = 1.0
    campaign: Campaign | None = None
    pending_probe: dict[str, Any] | None = None
    campaign_id = 0
    actions: list[dict[str, Any]] = []
    campaign_rows: list[dict[str, Any]] = []
    equity_rows: list[dict[str, Any]] = []
    risk_violations = 0
    max_leverage = 0.0
    max_stop_risk = 0.0
    running_peak = 1.0
    unavailable_until = start - pd.Timedelta(minutes=15)

    def record_action(ts: pd.Timestamp, action: str, **values: Any) -> None:
        actions.append({"asset": asset, "campaign_id": campaign_id, "ts": ts, "action": action, **values})

    def finalize(ts: pd.Timestamp, reason: str, closed: bool = True) -> None:
        nonlocal campaign, unavailable_until
        if campaign is None:
            return
        net_pnl = balance - campaign.entry_equity
        campaign_rows.append(
            {
                "asset": asset,
                "campaign_id": campaign.campaign_id,
                "candidate_ts": campaign.candidate_ts,
                "entry_ts": campaign.entry_ts,
                "exit_ts": ts,
                "side": campaign.side,
                "entry_equity": campaign.entry_equity,
                "exit_equity": balance,
                "initial_fill": campaign.initial_fill,
                "initial_stop": campaign.initial_stop,
                "max_mfe_r": campaign.max_mfe_price / campaign.initial_r,
                "max_mae_r": campaign.max_mae_price / campaign.initial_r,
                "attempts_add1": campaign.attempt_counts[1],
                "attempts_add2": campaign.attempt_counts[2],
                "attempts_add3": campaign.attempt_counts[3],
                "half_reduced": campaign.half_reduced,
                "score_observations": campaign.score_observations,
                "fees": campaign.fees,
                "funding_pnl": campaign.funding_pnl,
                "max_effective_leverage": campaign.max_effective_leverage,
                "max_stop_risk_pct": campaign.max_stop_risk_pct,
                "hold_hours": (ts - campaign.entry_ts) / pd.Timedelta(hours=1),
                "net_pnl": net_pnl,
                "pnl_r": net_pnl / (config.layer_risk * campaign.entry_equity),
                "exit_reason": reason,
                "closed": closed,
            }
        )
        unavailable_until = ts
        campaign = None

    def close_lot(ts: pd.Timestamp, lot_index: int, raw_price: float, reason: str) -> None:
        nonlocal balance, campaign
        if campaign is None:
            return
        lot = campaign.lots.pop(lot_index)
        fill = adverse_fill(raw_price, -campaign.side, config.slippage)
        price_pnl = lot.quantity * campaign.side * (fill - lot.fill)
        fee = lot.quantity * fill * config.fee_rate
        balance += price_pnl - fee
        campaign.fees += fee
        record_action(ts, "lot_exit", reason=reason, layer=lot.layer, fill=fill, quantity=lot.quantity, fee=fee, price_pnl=price_pnl, post_quantity=campaign.quantity)
        if not campaign.lots:
            finalize(ts, reason)

    def close_all(ts: pd.Timestamp, raw_price: float, reason: str, closed: bool = True) -> None:
        if campaign is None:
            return
        while campaign is not None and campaign.lots:
            close_lot(ts, len(campaign.lots) - 1, raw_price, reason)
        if campaign is not None:
            finalize(ts, reason, closed=closed)

    def reduce_added(ts: pd.Timestamp, raw_price: float, reason: str) -> None:
        nonlocal campaign
        if campaign is None:
            return
        indices = [i for i, lot in enumerate(campaign.lots) if lot.layer > 0]
        for index in reversed(indices):
            if campaign is None:
                return
            close_lot(ts, index, raw_price, reason)
        if campaign is not None:
            campaign.half_reduced = campaign.half_reduced or reason == "half_giveback_reduce"
            campaign.adds_disabled = True

    def risk_maintenance(ts: pd.Timestamp, raw_open: float) -> None:
        nonlocal balance, campaign
        if campaign is None:
            return
        floor = campaign.entry_equity * (1.0 - config.operational_risk)
        while campaign is not None and projected_stopout(balance, campaign, config) < floor - 1e-10:
            added = [i for i, lot in enumerate(campaign.lots) if lot.layer > 0]
            if not added:
                break
            index = added[-1]
            lot = campaign.lots[index]
            stop_fill = adverse_fill(lot.stop, -campaign.side, config.slippage)
            reduce_fill = adverse_fill(raw_open, -campaign.side, config.slippage)
            improvement = campaign.side * (reduce_fill - stop_fill) - config.fee_rate * reduce_fill + config.fee_rate * stop_fill
            deficit = floor - projected_stopout(balance, campaign, config)
            quantity = lot.quantity if improvement <= EPSILON else min(lot.quantity, deficit / improvement)
            if quantity <= EPSILON:
                break
            if quantity >= lot.quantity - EPSILON:
                close_lot(ts, index, raw_open, "risk_trim")
            else:
                fill = reduce_fill
                price_pnl = quantity * campaign.side * (fill - lot.fill)
                fee = quantity * fill * config.fee_rate
                balance += price_pnl - fee
                lot.quantity -= quantity
                campaign.fees += fee
                record_action(ts, "risk_trim", reason="restore_operational_risk", layer=lot.layer, fill=fill, quantity=quantity, fee=fee, price_pnl=price_pnl, post_quantity=campaign.quantity)
        if campaign is not None and projected_stopout(balance, campaign, config) < campaign.entry_equity * (1.0 - config.hard_risk) - 1e-10:
            record_action(ts, "risk_blocker", reason="hard_risk_exhausted")
            close_all(ts, raw_open, "hard_risk_exhausted")

    def enter_probe(ts: pd.Timestamp, plan: dict[str, Any], raw_open: float) -> None:
        nonlocal balance, campaign, campaign_id
        side = int(plan["side"])
        stop = float(plan["stop"])
        entry_style = str(plan.get("entry_style", "market"))
        execution_raw = float(plan.get("raw_entry", raw_open)) if pd.notna(plan.get("raw_entry", math.nan)) else raw_open
        fill = execution_raw if entry_style == "limit" else adverse_fill(execution_raw, side, config.slippage)
        quantity = requested_quantity(balance, fill, stop, side, config)
        quantity = min(quantity, MAX_LEVERAGE * balance / fill)
        if quantity <= EPSILON or side * (fill - stop) <= 0:
            return
        campaign_id += 1
        entry_equity = balance
        fee = quantity * fill * config.fee_rate
        balance -= fee
        lot = Lot(0, quantity, fill, stop, ts, fee)
        campaign = Campaign(campaign_id, side, pd.Timestamp(plan["candidate_ts"]), ts, entry_equity, fill, stop, abs(fill - stop), [lot], entry_intrabar=bool(plan.get("fill_intrabar", False)), fees=fee)
        record_action(ts, "probe_entry", reason="strong_continuation_pullback_restart", layer=0, probability=float(plan["probability"]), entry_style=entry_style, fill_intrabar=bool(plan.get("fill_intrabar", False)), fill=fill, stop=stop, quantity=quantity, fee=fee, post_quantity=quantity)

    def execute_add(ts: pd.Timestamp, raw_open: float) -> None:
        nonlocal balance, campaign
        if campaign is None or campaign.pending_add is None:
            return
        plan = campaign.pending_add
        if pd.isna(plan["entry_ts"]):
            if pd.Timestamp(plan["resolved_ts"]) <= ts:
                layer = int(plan["layer"])
                campaign.pending_add = None
                record_action(ts, "add_attempt_failed", reason=str(plan["status"]), layer=layer, probability=float(plan["probability"]), attempt=campaign.attempt_counts[layer])
                if campaign.attempt_counts[layer] >= 2:
                    campaign.adds_disabled = True
            return
        if pd.Timestamp(plan["entry_ts"]) != ts:
            return
        campaign.pending_add = None
        layer = int(plan["layer"])
        stop = float(plan["stop"])
        entry_style = str(plan.get("entry_style", "market"))
        execution_raw = float(plan.get("raw_entry", raw_open)) if pd.notna(plan.get("raw_entry", math.nan)) else raw_open
        fill = execution_raw if entry_style == "limit" else adverse_fill(execution_raw, campaign.side, config.slippage)
        current_equity = liquidation_equity(balance, campaign, execution_raw, config)
        desired = requested_quantity(campaign.entry_equity, fill, stop, campaign.side, config)
        safe = safe_add_quantity(balance, campaign, execution_raw, fill, stop, desired, config)
        if current_equity <= campaign.entry_equity or safe <= EPSILON or campaign.side * (fill - stop) <= 0:
            record_action(ts, "add_rejected", reason="not_profitable_or_risk_cap", layer=layer, probability=float(plan["probability"]), fill=fill, stop=stop, desired_quantity=desired)
            if campaign.attempt_counts[layer] >= 2:
                campaign.adds_disabled = True
            return
        fee = safe * fill * config.fee_rate
        balance -= fee
        campaign.fees += fee
        campaign.lots.append(Lot(layer, safe, fill, stop, ts, fee))
        campaign.next_layer = layer + 1
        if campaign.max_mfe_price >= 2.0 * campaign.initial_r:
            for old in campaign.lots[:-1]:
                if campaign.side > 0 and old.stop < stop < raw_open:
                    old.stop = stop
                elif campaign.side < 0 and old.stop > stop > raw_open:
                    old.stop = stop
        record_action(ts, "add", reason=f"mfe_{LAYER_THRESHOLDS[layer - 1]}r_then_new_pullback_restart", layer=layer, probability=float(plan["probability"]), entry_style=entry_style, fill_intrabar=bool(plan.get("fill_intrabar", False)), fill=fill, stop=stop, quantity=safe, desired_quantity=desired, fee=fee, post_quantity=campaign.quantity)

    for ts, bar in bars.iterrows():
        raw_open = float(bar["open"])
        high = float(bar["high"])
        low = float(bar["low"])
        close = float(bar["close"])
        peak_before = running_peak
        exited_this_bar = False

        if campaign is not None and ts > campaign.entry_ts and config.include_funding:
            funding_pnl = -campaign.side * campaign.quantity * raw_open * float(funding_aligned.loc[ts])
            balance += funding_pnl
            campaign.funding_pnl += funding_pnl

        if campaign is not None:
            for index in reversed(range(len(campaign.lots))):
                lot = campaign.lots[index]
                gap = raw_open <= lot.stop if campaign.side > 0 else raw_open >= lot.stop
                if gap:
                    close_lot(ts, index, raw_open, "stop_gap")
            exited_this_bar = campaign is None

        if campaign is not None:
            elapsed = (ts - campaign.entry_ts) / pd.Timedelta(hours=1)
            if elapsed >= VALIDATION_HOURS and not campaign.reached_one_r:
                close_all(ts, raw_open, "validation_failed_24h")
                exited_this_bar = True
            elif elapsed >= MAX_HOLD_HOURS:
                close_all(ts, raw_open, "timeout_336h")
                exited_this_bar = True

        if campaign is not None and campaign.pending_reduce_reason is not None:
            reason = campaign.pending_reduce_reason
            campaign.pending_reduce_reason = None
            reduce_added(ts, raw_open, reason)

        if campaign is not None:
            risk_maintenance(ts, raw_open)
            exited_this_bar = exited_this_bar or campaign is None

        if campaign is not None and ts in score_map:
            observation = score_map[ts]
            probability = float(observation["probability"])
            direction = int(observation["direction"])
            campaign.score_observations += 1
            campaign.last_probability = probability
            record_action(ts, "continuation_score", reason="four_hour_decision", probability=probability, score_direction=direction, threshold=threshold)
            if bool(observation["strong"]) and direction == -campaign.side:
                campaign.pending_add = None
                campaign.adds_disabled = True
                if config.allow_opposite_reduce:
                    reduce_added(ts, raw_open, "opposite_score_reduce")
            elif bool(observation["strong"]) and direction == campaign.side and config.allow_adds and not campaign.adds_disabled and campaign.pending_add is None and campaign.next_layer <= config.max_layers and campaign.next_layer in campaign.eligibility_ts:
                layer = campaign.next_layer
                candidate_rows = attempt_candidates.get(ts, [])
                plan = next((row for row in candidate_rows if int(row["side"]) == campaign.side), None)
                if plan is not None:
                    campaign.attempt_counts[layer] += 1
                    campaign.pending_add = {**plan, "layer": layer}
                    record_action(ts, "add_attempt", reason="qualified_structure_wait", layer=layer, probability=probability, planned_entry_ts=plan["entry_ts"], resolved_ts=plan["resolved_ts"], attempt=campaign.attempt_counts[layer])

        if campaign is None and ts in score_map:
            observation = score_map[ts]
            if bool(observation["strong"]):
                direction = int(observation["direction"])
                candidate_rows = attempt_candidates.get(ts, [])
                plan = next((row for row in candidate_rows if int(row["side"]) == direction), None)
                if pending_probe is not None and int(pending_probe["side"]) != direction:
                    record_action(ts, "probe_plan_cancel", reason="opposite_strong_candidate", old_candidate_ts=pending_probe["candidate_ts"], score_direction=direction, probability=float(observation["probability"]))
                    pending_probe = None
                if pending_probe is None and plan is not None:
                    pending_probe = plan
                    record_action(ts, "probe_plan", reason="await_pullback_restart", probability=float(plan["probability"]), planned_entry_ts=plan["entry_ts"], resolved_ts=plan["resolved_ts"], score_direction=direction)

        if campaign is not None:
            execute_add(ts, raw_open)

        if pending_probe is not None and pd.notna(pending_probe["entry_ts"]) and pd.Timestamp(pending_probe["entry_ts"]) < ts:
            pending_probe = None
        if pending_probe is not None and pd.isna(pending_probe["entry_ts"]) and pd.Timestamp(pending_probe["resolved_ts"]) <= ts:
            record_action(ts, "probe_plan_expired", reason=str(pending_probe["status"]), candidate_ts=pending_probe["candidate_ts"])
            pending_probe = None
        if campaign is None and pending_probe is not None and pd.notna(pending_probe["entry_ts"]) and not exited_this_bar and ts > unavailable_until and pd.Timestamp(pending_probe["entry_ts"]) == ts:
            plan = pending_probe
            pending_probe = None
            enter_probe(ts, plan, raw_open)

        if campaign is not None:
            for index in reversed(range(len(campaign.lots))):
                lot = campaign.lots[index]
                hit = low <= lot.stop if campaign.side > 0 else high >= lot.stop
                if hit:
                    close_lot(ts, index, lot.stop, "stop_intrabar")
            exited_this_bar = exited_this_bar or campaign is None

        if campaign is not None:
            if campaign.entry_ts == ts and campaign.entry_intrabar:
                favorable = campaign.side * (close - campaign.initial_fill)
            else:
                favorable = high - campaign.initial_fill if campaign.side > 0 else campaign.initial_fill - low
            adverse = campaign.initial_fill - low if campaign.side > 0 else high - campaign.initial_fill
            campaign.max_mfe_price = max(campaign.max_mfe_price, favorable, 0.0)
            campaign.max_mae_price = max(campaign.max_mae_price, adverse, 0.0)
            mfe_r = campaign.max_mfe_price / campaign.initial_r
            campaign.reached_one_r = campaign.reached_one_r or mfe_r >= 1.0
            for layer, threshold_r in enumerate(LAYER_THRESHOLDS, start=1):
                if layer not in campaign.eligibility_ts and mfe_r >= threshold_r:
                    campaign.eligibility_ts[layer] = ts + pd.Timedelta(minutes=15)
                    record_action(ts, "layer_eligible", reason=f"mfe_{threshold_r}r", layer=layer, mfe_r=mfe_r, eligible_after=campaign.eligibility_ts[layer])
            progress = campaign.side * (close - campaign.initial_fill)
            if config.allow_half_reduce and ts.minute == 45 and not campaign.half_reduced and any(lot.layer > 0 for lot in campaign.lots) and mfe_r >= 2.0 and progress < 0.5 * campaign.max_mfe_price:
                campaign.pending_reduce_reason = "half_giveback_reduce"
                campaign.pending_add = None

        current_equity = liquidation_equity(balance, campaign, close, config)
        adverse_raw = low if campaign is not None and campaign.side > 0 else high if campaign is not None else close
        adverse_equity = liquidation_equity(balance, campaign, float(adverse_raw), config)
        if campaign is not None:
            effective = campaign.quantity * close / max(current_equity, EPSILON)
            projected = projected_stopout(balance, campaign, config)
            stop_risk = max(0.0, (campaign.entry_equity - projected) / campaign.entry_equity)
            campaign.max_effective_leverage = max(campaign.max_effective_leverage, effective)
            campaign.max_stop_risk_pct = max(campaign.max_stop_risk_pct, stop_risk * 100.0)
            max_leverage = max(max_leverage, effective)
            max_stop_risk = max(max_stop_risk, stop_risk * 100.0)
            if stop_risk > config.hard_risk + 1e-9 or effective > MAX_LEVERAGE + 1e-9:
                risk_violations += 1
        equity_rows.append({"asset": asset, "config": config.name, "ts": ts, "equity": current_equity, "balance": balance, "intrabar_adverse_equity": adverse_equity, "running_peak_before_bar": peak_before, "side": 0 if campaign is None else campaign.side, "quantity": 0.0 if campaign is None else campaign.quantity, "mark": close})
        running_peak = max(running_peak, current_equity)

    if campaign is not None:
        close_all(bars.index[-1], float(bars.iloc[-1]["close"]), "period_end", closed=False)
        equity_rows[-1].update({"equity": balance, "balance": balance, "intrabar_adverse_equity": min(equity_rows[-1]["intrabar_adverse_equity"], balance), "side": 0, "quantity": 0.0})

    campaign_frame = pd.DataFrame(campaign_rows)
    action_frame = pd.DataFrame(actions)
    equity_frame = pd.DataFrame(equity_rows)
    metrics = summarize(equity_frame, campaign_frame, action_frame, config, risk_violations, max_leverage, max_stop_risk)
    metrics.update({"asset": asset, "threshold": threshold, "locked_evaluation_used": False})
    return Result(metrics, campaign_frame, action_frame, equity_frame)


def main() -> None:
    entry = load_path(ENTRY_PATH, "bin_mtf_ptc_campaign_entry")
    meter = entry.load_path(entry.METER_PATH, "bin_mtf_ptc_campaign_meter")
    data_module = entry.load_path(entry.DATA_PATH, "bin_mtf_ptc_campaign_data")
    hourly_frames, _ = meter.load_module().load_assets()
    warehouse = DuckDBWarehouse(DataLakeLayout.from_settings(load_settings(None)))
    configs = (
        Config("base_full"),
        Config("base_probe_only", allow_adds=False, allow_half_reduce=False, allow_opposite_reduce=False),
        Config("base_no_half_reduce", allow_half_reduce=False),
        Config("base_no_opposite_reduce", allow_opposite_reduce=False),
        Config("gross_full", fee_rate=0.0, slippage=0.0, include_funding=False),
        Config("stress_full", slippage=0.0008),
        Config("gross_no_half_reduce", fee_rate=0.0, slippage=0.0, include_funding=False, allow_half_reduce=False),
        Config("stress_no_half_reduce", slippage=0.0008, allow_half_reduce=False),
    )
    metrics_rows: list[dict[str, Any]] = []
    campaign_parts: list[pd.DataFrame] = []
    action_parts: list[pd.DataFrame] = []
    equity_parts: list[pd.DataFrame] = []
    signal_audit: dict[str, Any] = {}
    for asset, symbol in SYMBOLS.items():
        bars15, funding, _ = data_module.load_symbol_data(warehouse, symbol, require_raw_parity=True)
        hourly = hourly_frames[asset]
        dev_end, val_start, val_end = meter.SPLITS[asset]
        hourly_visible = hourly.loc[hourly.index <= val_end]
        bars_visible = bars15.loc[bars15.index <= val_end]
        scores, threshold = fit_score_frame(meter, hourly_visible, SELECTED[asset], dev_end, val_start, val_end)
        attempts = build_attempts(entry, scores, hourly_visible, bars_visible, SELECTED[asset])
        signal_audit[asset] = {"threshold": threshold, "scored_candidates": int(len(scores)), "strong_candidates": int(scores["strong"].sum()) if len(scores) else 0, "attempts": int(len(attempts)), "successful_restarts": int(attempts["entry_ts"].notna().sum()) if len(attempts) else 0}
        for config in configs:
            result = run_engine(asset, bars_visible, funding, scores, attempts, threshold, val_start, val_end, config)
            metrics_rows.append(result.metrics)
            if len(result.campaigns):
                frame = result.campaigns.copy()
                frame.insert(1, "config", config.name)
                campaign_parts.append(frame)
            if len(result.actions):
                frame = result.actions.copy()
                frame.insert(1, "config", config.name)
                action_parts.append(frame)
            if config.name in {"base_full", "base_probe_only", "base_no_half_reduce"} and len(result.equity):
                equity_parts.append(result.equity)
    metrics = pd.DataFrame(metrics_rows)
    campaigns = pd.concat(campaign_parts, ignore_index=True) if campaign_parts else pd.DataFrame()
    actions = pd.concat(action_parts, ignore_index=True) if action_parts else pd.DataFrame()
    equity = pd.concat(equity_parts, ignore_index=True) if equity_parts else pd.DataFrame()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(ARTIFACT_DIR / "binance_mtf_ptc_campaign_engine_v0_validation_metrics_2026-08-03.csv", index=False)
    campaigns.to_csv(ARTIFACT_DIR / "binance_mtf_ptc_campaign_engine_v0_validation_campaigns_2026-08-03.csv", index=False)
    actions.to_csv(ARTIFACT_DIR / "binance_mtf_ptc_campaign_engine_v0_validation_actions_2026-08-03.csv", index=False)
    equity.to_csv(ARTIFACT_DIR / "binance_mtf_ptc_campaign_engine_v0_validation_equity_2026-08-03.csv", index=False)
    (ARTIFACT_DIR / "binance_mtf_ptc_campaign_engine_v0_2026-08-03.json").write_text(json.dumps({"locked_evaluation_used": False, "selected": SELECTED, "signal_audit": signal_audit, "metrics": metrics.to_dict(orient="records")}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(metrics.to_string(index=False))


if __name__ == "__main__":
    main()
