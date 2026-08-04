from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from dstc_data import AssetData


FEE_RATE = 0.001
BASE_SLIPPAGE = 0.0004
EPSILON = 1e-12


@dataclass(frozen=True, slots=True)
class Config:
    name: str
    ma_length: int = 7
    slope_days: int = 2
    candidate_band_atr: float = 0.5
    invalidation: str = "band_structure"
    wrong_side_atr: float = 1.0
    invalid_days: int = 2
    pullback_min_atr: float = 0.5
    max_retracement: float = 0.5
    structure_bars: int = 6
    stop_buffer_atr: float = 0.0
    min_stop_pct: float = 0.015
    max_stop_pct: float = 0.15
    entry_style: str = "restart2"
    wait_hours: int = 24
    layer_risk: float = 0.0025
    max_layers: int = 1
    add_thresholds_r: tuple[float, ...] = (0.5, 1.0, 2.0)
    max_retry_per_layer: int = 1
    campaign_loss_budget: float = 0.02
    total_plan_risk: float = 0.01
    mfe_mode: str = "no_mfe"
    max_hold_days: int = 0
    fee_rate: float = FEE_RATE
    slippage: float = BASE_SLIPPAGE
    max_leverage: float = 3.0


@dataclass(slots=True)
class Lot:
    lot_id: int
    layer: int
    attempt: int
    side: int
    entry_ts: pd.Timestamp
    entry_fill: float
    quantity: float
    initial_stop: float
    stop: float
    entry_fee: float
    planned_risk: float
    entry_equity: float
    active: bool = True
    max_mfe_r: float = 0.0
    max_mae_r: float = 0.0
    funding_pnl: float = 0.0


@dataclass(slots=True)
class Campaign:
    campaign_id: int
    side: int
    start_ts: pd.Timestamp
    start_equity: float
    wrong_days: int = 0
    structure_broken: bool = False
    realized_pnl: float = 0.0
    layer_attempts: dict[int, int] = field(default_factory=dict)
    retired_layers: set[int] = field(default_factory=set)
    first_entry_fill: float | None = None
    anchor_r_price: float | None = None
    best_hourly_progress: float = 0.0
    episode_mfe_r: float = 0.0
    max_mfe_r: float = 0.0
    traded: bool = False


@dataclass(frozen=True, slots=True)
class RunResult:
    config: Config
    metrics: dict[str, Any]
    campaigns: pd.DataFrame
    lots: pd.DataFrame
    actions: pd.DataFrame
    equity: pd.DataFrame


def true_range(frame: pd.DataFrame) -> pd.Series:
    previous_close = frame["close"].shift(1)
    return pd.concat(
        (
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ),
        axis=1,
    ).max(axis=1)


def _directional_persistence(values: pd.Series, days: int) -> pd.Series:
    sign = np.sign(values).astype(float)
    if days <= 1:
        return sign
    same_positive = sign.gt(0).rolling(days, min_periods=days).sum().eq(days)
    same_negative = sign.lt(0).rolling(days, min_periods=days).sum().eq(days)
    return pd.Series(
        np.where(same_positive, 1.0, np.where(same_negative, -1.0, 0.0)),
        index=values.index,
    )


def build_feature_panel(data: AssetData, config: Config) -> pd.DataFrame:
    daily = data.bars1d.copy()
    daily["atr"] = true_range(daily).rolling(7, min_periods=7).mean()
    daily["ma"] = daily["close"].rolling(config.ma_length, min_periods=config.ma_length).mean()
    daily["ma_slope"] = daily["ma"].diff()
    daily["candidate_side"] = _directional_persistence(daily["ma_slope"], config.slope_days)
    signed_alignment = daily["candidate_side"] * (daily["close"] - daily["ma"])
    daily.loc[
        signed_alignment.lt(-config.candidate_band_atr * daily["atr"]), "candidate_side"
    ] = 0.0
    daily["new"] = True

    four = data.bars4h.copy()
    four["atr"] = true_range(four).rolling(18, min_periods=18).mean()
    four["direction"] = np.sign(four["close"] - four["close"].shift(config.structure_bars))
    four["prior_low"] = four["low"].rolling(config.structure_bars, min_periods=config.structure_bars).min().shift(1)
    four["prior_high"] = four["high"].rolling(config.structure_bars, min_periods=config.structure_bars).max().shift(1)
    four["wide_prior_low"] = four["low"].rolling(12, min_periods=12).min().shift(1)
    four["wide_prior_high"] = four["high"].rolling(12, min_periods=12).max().shift(1)
    four["new"] = True

    hourly = data.bars1h.copy()
    hourly["atr"] = true_range(hourly).rolling(24, min_periods=24).mean()
    hourly["prior_peak"] = hourly["high"].rolling(12, min_periods=12).max().shift(1)
    hourly["prior_trough"] = hourly["low"].rolling(12, min_periods=12).min().shift(1)
    hourly["impulse_base"] = hourly["close"].shift(12)
    hourly["new"] = True

    bars = data.bars15.copy()
    bars["tr"] = true_range(bars)
    bars["tr_median20"] = bars["tr"].rolling(20, min_periods=20).median().shift(1)
    for prefix, source in (("d", daily), ("h4", four), ("h1", hourly)):
        aligned = source.reindex(bars.index, method="ffill")
        for column in source.columns:
            bars[f"{prefix}_{column}"] = aligned[column]
        bars[f"{prefix}_event"] = bars.index.isin(source.index)
    return bars


def adverse_fill(raw_price: float, order_side: int, slippage: float) -> float:
    return raw_price * (1.0 + order_side * slippage)


def pullback_qualified(row: pd.Series, side: int, config: Config) -> bool:
    atr = float(row["h1_atr"])
    if not np.isfinite(atr) or atr <= EPSILON:
        return False
    close = float(row["h1_close"])
    base = float(row["h1_impulse_base"])
    if side > 0:
        extreme = float(row["h1_prior_peak"])
        depth = extreme - close
        impulse = extreme - base
    else:
        extreme = float(row["h1_prior_trough"])
        depth = close - extreme
        impulse = base - extreme
    if not np.isfinite(depth) or not np.isfinite(impulse) or impulse <= EPSILON:
        return False
    retracement = depth / impulse
    return bool(
        depth >= config.pullback_min_atr * atr
        and depth > 0.0
        and retracement <= config.max_retracement
    )


def restart_qualified(panel: pd.DataFrame, location: int, side: int, lookback: int) -> bool:
    if location < max(lookback, 20):
        return False
    row = panel.iloc[location]
    prior = panel.iloc[location - lookback : location]
    breakout = (
        float(row["close"]) > float(prior["high"].max())
        if side > 0
        else float(row["close"]) < float(prior["low"].min())
    )
    return bool(
        breakout
        and np.isfinite(float(row["tr_median20"]))
        and float(row["tr"]) > float(row["tr_median20"])
    )


def structure_stop(row: pd.Series, side: int, entry_fill: float, config: Config) -> float | None:
    structure = float(row["h4_prior_low"] if side > 0 else row["h4_prior_high"])
    atr1h = float(row["h1_atr"])
    if not np.isfinite(structure) or not np.isfinite(atr1h):
        return None
    raw_stop = structure - side * config.stop_buffer_atr * atr1h
    distance = side * (entry_fill - raw_stop)
    distance = max(distance, config.min_stop_pct * entry_fill)
    if distance > config.max_stop_pct * entry_fill:
        return None
    return entry_fill - side * distance


def requested_quantity(
    equity: float,
    entry_fill: float,
    stop: float,
    side: int,
    config: Config,
) -> tuple[float, float]:
    stop_fill = adverse_fill(stop, -side, config.slippage)
    unit_price_loss = max(0.0, side * (entry_fill - stop_fill))
    unit_fees = config.fee_rate * (entry_fill + stop_fill)
    unit_loss = unit_price_loss + unit_fees
    if unit_loss <= EPSILON:
        return 0.0, 0.0
    risk_qty = config.layer_risk * equity / unit_loss
    leverage_qty = config.max_leverage * equity / entry_fill
    quantity = max(0.0, min(risk_qty, leverage_qty))
    return quantity, quantity * unit_loss


def _campaign_invalid(campaign: Campaign, row: pd.Series, config: Config) -> bool:
    side = campaign.side
    if config.invalidation == "cross1":
        return bool(row["d_event"] and side * (float(row["d_close"]) - float(row["d_ma"])) < 0.0)
    if config.invalidation == "structure_only":
        broken = (
            float(row["h4_close"]) < float(row["h4_wide_prior_low"])
            if side > 0
            else float(row["h4_close"]) > float(row["h4_wide_prior_high"])
        )
        return bool(row["h4_event"] and broken)
    if config.invalidation == "slope_structure":
        slope_reversed = side * float(row["d_ma_slope"]) < 0.0
        return bool(slope_reversed and campaign.structure_broken)
    return bool(campaign.wrong_days >= config.invalid_days and campaign.structure_broken)


def _next_layer(campaign: Campaign, lots: list[Lot], config: Config) -> int | None:
    active_layers = {lot.layer for lot in lots if lot.active}
    for layer in range(config.max_layers):
        if layer in campaign.retired_layers or layer in active_layers:
            continue
        attempts = campaign.layer_attempts.get(layer, 0)
        if attempts > config.max_retry_per_layer:
            continue
        if layer > 0:
            prior_layers = set(range(layer))
            if not prior_layers.issubset(active_layers | campaign.retired_layers):
                continue
            threshold = config.add_thresholds_r[min(layer - 1, len(config.add_thresholds_r) - 1)]
            if campaign.episode_mfe_r + EPSILON < threshold:
                continue
        return layer
    return None


def _marked_equity(balance: float, lots: list[Lot], mark: float) -> float:
    return balance + sum(
        lot.quantity * lot.side * (mark - lot.entry_fill) for lot in lots if lot.active
    )


def summarize(
    equity: pd.DataFrame,
    campaigns: pd.DataFrame,
    lots: pd.DataFrame,
    max_leverage: float,
    risk_violations: int,
    config: Config,
) -> dict[str, Any]:
    values = equity["equity"].astype(float)
    elapsed_days = max(
        (equity.index[-1] - equity.index[0]).total_seconds() / 86400.0,
        1.0,
    )
    end_multiple = float(values.iloc[-1] / values.iloc[0])
    annual_multiple = end_multiple ** (365.0 / elapsed_days) if end_multiple > 0.0 else 0.0
    closed = campaigns.loc[campaigns["traded"]].copy() if not campaigns.empty else campaigns
    pnl = closed["net_pnl"] if not closed.empty else pd.Series(dtype=float)
    gains = float(pnl[pnl > 0.0].sum())
    losses = float(-pnl[pnl < 0.0].sum())
    profitable = closed.loc[closed["net_pnl"] > 0.0, "net_pnl"].sort_values(ascending=False)
    top1 = float(profitable.iloc[:1].sum() / gains) if gains > EPSILON else 0.0
    top3 = float(profitable.iloc[:3].sum() / gains) if gains > EPSILON else 0.0
    remove_top3 = float(pnl.sum() - profitable.iloc[:3].sum()) if not pnl.empty else 0.0
    recent: dict[str, float] = {}
    for name, delta in (
        ("1d", pd.Timedelta(days=1)),
        ("7d", pd.Timedelta(days=7)),
        ("1m", pd.Timedelta(days=30)),
        ("3m", pd.Timedelta(days=90)),
        ("6m", pd.Timedelta(days=180)),
        ("1y", pd.Timedelta(days=365)),
    ):
        start = equity.index[-1] - delta
        window = values.loc[values.index >= start]
        recent[name] = float(window.iloc[-1] / window.iloc[0] - 1.0) if len(window) >= 2 else 0.0
    return {
        "config": asdict(config),
        "start_equity": float(values.iloc[0]),
        "end_equity": float(values.iloc[-1]),
        "total_return_pct": (end_multiple - 1.0) * 100.0,
        "annual_equity_multiple": float(annual_multiple),
        "max_drawdown_pct": float(equity["intrabar_drawdown"].min() * 100.0),
        "campaigns": int(len(closed)),
        "lots": int(len(lots)),
        "win_rate_pct": float(pnl.gt(0.0).mean() * 100.0) if not pnl.empty else 0.0,
        "profit_factor": gains / losses if losses > EPSILON else (math.inf if gains > 0.0 else 0.0),
        "top1_gross_profit_share": top1,
        "top3_gross_profit_share": top3,
        "remove_top3_net_pnl": remove_top3,
        "max_effective_leverage": float(max_leverage),
        "risk_violations": int(risk_violations),
        "recent_returns": recent,
    }


def run_backtest(
    data: AssetData,
    config: Config,
    *,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> RunResult:
    panel = build_feature_panel(data, config)
    if start is not None:
        start = pd.Timestamp(start)
        start = start.tz_localize("UTC") if start.tzinfo is None else start.tz_convert("UTC")
    if end is not None:
        end = pd.Timestamp(end)
        end = end.tz_localize("UTC") if end.tzinfo is None else end.tz_convert("UTC")

    balance = 1.0
    campaign: Campaign | None = None
    lots: list[Lot] = []
    pending_plan: dict[str, Any] | None = None
    pending_entry: dict[str, Any] | None = None
    campaign_rows: list[dict[str, Any]] = []
    lot_rows: list[dict[str, Any]] = []
    action_rows: list[dict[str, Any]] = []
    equity_rows: list[dict[str, Any]] = []
    campaign_id = 0
    lot_id = 0
    max_effective_leverage = 0.0
    risk_violations = 0
    high_water = 1.0

    def active_lots() -> list[Lot]:
        return [lot for lot in lots if lot.active]

    def record_action(ts: pd.Timestamp, action: str, **details: Any) -> None:
        action_rows.append({"ts": ts, "action": action, **details})

    def close_lot(lot: Lot, ts: pd.Timestamp, raw_price: float, reason: str) -> None:
        nonlocal balance
        if not lot.active:
            return
        fill = adverse_fill(raw_price, -lot.side, config.slippage)
        exit_fee = lot.quantity * fill * config.fee_rate
        price_pnl = lot.quantity * lot.side * (fill - lot.entry_fill)
        balance += price_pnl - exit_fee
        net_pnl = price_pnl - lot.entry_fee - exit_fee + lot.funding_pnl
        lot.active = False
        if campaign is not None:
            campaign.realized_pnl += net_pnl
            if reason.startswith("mfe50_add"):
                campaign.retired_layers.add(lot.layer)
        lot_rows.append(
            {
                "campaign_id": campaign.campaign_id if campaign else None,
                "lot_id": lot.lot_id,
                "layer": lot.layer,
                "attempt": lot.attempt,
                "side": lot.side,
                "entry_ts": lot.entry_ts,
                "exit_ts": ts,
                "entry_fill": lot.entry_fill,
                "exit_fill": fill,
                "quantity": lot.quantity,
                "initial_stop": lot.initial_stop,
                "planned_risk": lot.planned_risk,
                "entry_fee": lot.entry_fee,
                "exit_fee": exit_fee,
                "funding_pnl": lot.funding_pnl,
                "price_pnl": price_pnl,
                "net_pnl": net_pnl,
                "max_mfe_r": lot.max_mfe_r,
                "max_mae_r": lot.max_mae_r,
                "exit_reason": reason,
            }
        )
        record_action(ts, "lot_exit", lot_id=lot.lot_id, layer=lot.layer, reason=reason, fill=fill)

    def end_campaign(ts: pd.Timestamp, raw_price: float, reason: str) -> None:
        nonlocal campaign, pending_plan, pending_entry
        if campaign is None:
            return
        current = campaign
        for lot in list(active_lots()):
            close_lot(lot, ts, raw_price, reason)
        campaign_rows.append(
            {
                "campaign_id": current.campaign_id,
                "side": current.side,
                "start_ts": current.start_ts,
                "end_ts": ts,
                "start_equity": current.start_equity,
                "end_equity": balance,
                "net_pnl": balance - current.start_equity,
                "max_mfe_r": current.max_mfe_r,
                "traded": current.traded,
                "exit_reason": reason,
            }
        )
        record_action(ts, "campaign_end", campaign_id=current.campaign_id, reason=reason)
        campaign = None
        pending_plan = None
        pending_entry = None

    first_processed = True
    last_ts: pd.Timestamp | None = None
    last_close = math.nan
    for location, (ts, row) in enumerate(panel.iterrows()):
        if start is not None and ts < start:
            continue
        if end is not None and ts > end:
            break
        raw_open = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        last_ts = ts
        last_close = close

        # Funding belongs to positions carried into this timestamp. New fills at
        # the same open do not receive or pay an already-settled funding event.
        rate = float(data.funding15.reindex([ts]).fillna(0.0).iloc[0])
        if abs(rate) > EPSILON:
            for lot in active_lots():
                funding_pnl = -lot.side * lot.quantity * raw_open * rate
                balance += funding_pnl
                lot.funding_pnl += funding_pnl

        if campaign is not None:
            if bool(row["d_event"]):
                signed_wrong = campaign.side * (float(row["d_close"]) - float(row["d_ma"]))
                threshold = -config.wrong_side_atr * float(row["d_atr"])
                campaign.wrong_days = campaign.wrong_days + 1 if signed_wrong < threshold else 0
            if bool(row["h4_event"]):
                campaign.structure_broken = bool(
                    float(row["h4_close"]) < float(row["h4_prior_low"])
                    if campaign.side > 0
                    else float(row["h4_close"]) > float(row["h4_prior_high"])
                )
            held_days = (ts - campaign.start_ts).total_seconds() / 86400.0
            if _campaign_invalid(campaign, row, config):
                end_campaign(ts, raw_open, "campaign_invalidation")
            elif config.max_hold_days > 0 and held_days >= config.max_hold_days:
                end_campaign(ts, raw_open, "campaign_timeout")

        # A completed 1h bar becomes visible exactly at this 15m open. MFE
        # protection therefore executes here, before this new 15m bar's range
        # is observed or any new entry is considered.
        if (
            campaign is not None
            and campaign.first_entry_fill is not None
            and campaign.anchor_r_price
            and active_lots()
            and bool(row["h1_event"])
        ):
            hourly_progress = campaign.side * (
                float(row["h1_close"]) - campaign.first_entry_fill
            )
            campaign.best_hourly_progress = max(
                campaign.best_hourly_progress, hourly_progress
            )
            if (
                config.mfe_mode != "no_mfe"
                and campaign.best_hourly_progress >= 2.0 * campaign.anchor_r_price
                and hourly_progress < 0.5 * campaign.best_hourly_progress
            ):
                if config.mfe_mode == "mfe50_all":
                    end_campaign(ts, raw_open, "mfe50_all")
                elif config.mfe_mode == "mfe50_adds":
                    for lot in list(active_lots()):
                        if lot.layer > 0:
                            close_lot(lot, ts, raw_open, "mfe50_add")

        if campaign is None and bool(row["h4_event"]):
            side = int(float(row["d_candidate_side"])) if np.isfinite(float(row["d_candidate_side"])) else 0
            if side != 0 and side == int(float(row["h4_direction"])):
                campaign_id += 1
                campaign = Campaign(campaign_id, side, ts, balance)
                record_action(ts, "campaign_start", campaign_id=campaign_id, side=side)

        if pending_plan is not None and campaign is not None:
            if ts > pending_plan["expires"]:
                record_action(ts, "entry_plan_expired", layer=pending_plan["layer"])
                pending_plan = None
            elif config.entry_style.startswith("restart"):
                lookback = int(config.entry_style.removeprefix("restart"))
                if restart_qualified(panel, location, campaign.side, lookback):
                    pending_entry = {
                        "execute_ts": ts + pd.Timedelta(minutes=15),
                        "layer": pending_plan["layer"],
                        "signal_ts": ts,
                    }
                    record_action(ts, "restart_signal", layer=pending_plan["layer"], lookback=lookback)
                    pending_plan = None

        if pending_entry is not None and campaign is not None and ts >= pending_entry["execute_ts"]:
            layer = int(pending_entry["layer"])
            entry_fill = adverse_fill(raw_open, campaign.side, config.slippage)
            stop = structure_stop(row, campaign.side, entry_fill, config)
            if stop is None:
                record_action(ts, "entry_rejected_stop", layer=layer)
            else:
                current_equity = _marked_equity(balance, lots, raw_open)
                quantity, planned_risk = requested_quantity(
                    current_equity, entry_fill, stop, campaign.side, config
                )
                existing_risk = sum(lot.planned_risk for lot in active_lots())
                projected_notional = sum(lot.quantity * raw_open for lot in active_lots()) + quantity * entry_fill
                projected_leverage = projected_notional / max(current_equity, EPSILON)
                loss_budget_used = max(0.0, -campaign.realized_pnl / max(campaign.start_equity, EPSILON))
                allowed = bool(
                    quantity > EPSILON
                    and existing_risk + planned_risk <= config.total_plan_risk * current_equity + 1e-9
                    and projected_leverage <= config.max_leverage + 1e-9
                    and loss_budget_used < config.campaign_loss_budget
                )
                if allowed:
                    was_flat = not active_lots()
                    entry_fee = quantity * entry_fill * config.fee_rate
                    balance -= entry_fee
                    lot_id += 1
                    attempt = campaign.layer_attempts.get(layer, 0) + 1
                    campaign.layer_attempts[layer] = attempt
                    lot = Lot(
                        lot_id,
                        layer,
                        attempt,
                        campaign.side,
                        ts,
                        entry_fill,
                        quantity,
                        stop,
                        stop,
                        entry_fee,
                        planned_risk,
                        current_equity,
                    )
                    lots.append(lot)
                    campaign.traded = True
                    if was_flat:
                        campaign.first_entry_fill = entry_fill
                        campaign.anchor_r_price = abs(entry_fill - stop)
                        campaign.best_hourly_progress = 0.0
                        campaign.episode_mfe_r = 0.0
                    max_effective_leverage = max(max_effective_leverage, projected_leverage)
                    record_action(
                        ts,
                        "lot_entry",
                        lot_id=lot_id,
                        layer=layer,
                        attempt=attempt,
                        fill=entry_fill,
                        stop=stop,
                        quantity=quantity,
                    )
                else:
                    risk_violations += int(projected_leverage > config.max_leverage + 1e-9)
                    record_action(
                        ts,
                        "entry_rejected_risk",
                        layer=layer,
                        projected_leverage=projected_leverage,
                        existing_stop_risk=existing_risk,
                    )
            pending_entry = None

        if campaign is not None and pending_plan is None and pending_entry is None and bool(row["h1_event"]):
            layer = _next_layer(campaign, lots, config)
            if layer is not None and pullback_qualified(row, campaign.side, config):
                if config.entry_style == "immediate_probe":
                    pending_entry = {"execute_ts": ts, "layer": layer, "signal_ts": ts}
                    # The just-completed 1h bar is visible at this 15m open. Execute
                    # immediately through the same guarded order path on next loop body.
                    entry_fill = adverse_fill(raw_open, campaign.side, config.slippage)
                    stop = structure_stop(row, campaign.side, entry_fill, config)
                    if stop is not None:
                        current_equity = _marked_equity(balance, lots, raw_open)
                        quantity, planned_risk = requested_quantity(
                            current_equity, entry_fill, stop, campaign.side, config
                        )
                        existing_risk = sum(lot.planned_risk for lot in active_lots())
                        projected_notional = sum(lot.quantity * raw_open for lot in active_lots()) + quantity * entry_fill
                        projected_leverage = projected_notional / max(current_equity, EPSILON)
                        if (
                            quantity > EPSILON
                            and existing_risk + planned_risk <= config.total_plan_risk * current_equity + 1e-9
                            and projected_leverage <= config.max_leverage + 1e-9
                        ):
                            was_flat = not active_lots()
                            entry_fee = quantity * entry_fill * config.fee_rate
                            balance -= entry_fee
                            lot_id += 1
                            attempt = campaign.layer_attempts.get(layer, 0) + 1
                            campaign.layer_attempts[layer] = attempt
                            lots.append(
                                Lot(
                                    lot_id,
                                    layer,
                                    attempt,
                                    campaign.side,
                                    ts,
                                    entry_fill,
                                    quantity,
                                    stop,
                                    stop,
                                    entry_fee,
                                    planned_risk,
                                    current_equity,
                                )
                            )
                            campaign.traded = True
                            if was_flat:
                                campaign.first_entry_fill = entry_fill
                                campaign.anchor_r_price = abs(entry_fill - stop)
                                campaign.best_hourly_progress = 0.0
                                campaign.episode_mfe_r = 0.0
                            max_effective_leverage = max(max_effective_leverage, projected_leverage)
                            record_action(ts, "lot_entry", lot_id=lot_id, layer=layer, attempt=attempt, fill=entry_fill, stop=stop, quantity=quantity)
                    pending_entry = None
                else:
                    pending_plan = {
                        "layer": layer,
                        "created": ts,
                        "expires": ts + pd.Timedelta(hours=config.wait_hours),
                    }
                    record_action(ts, "entry_plan", layer=layer, expires=pending_plan["expires"])

        # Stops are checked after all open orders. A gap fills at the worse open;
        # a newly opened lot can therefore stop in the same bar.
        for lot in list(active_lots()):
            r_price = max(abs(lot.entry_fill - lot.initial_stop), EPSILON)
            favorable = (
                high - lot.entry_fill if lot.side > 0 else lot.entry_fill - low
            )
            adverse = (
                lot.entry_fill - low if lot.side > 0 else high - lot.entry_fill
            )
            lot.max_mfe_r = max(lot.max_mfe_r, favorable / r_price)
            lot.max_mae_r = max(lot.max_mae_r, adverse / r_price)
            touched = low <= lot.stop if lot.side > 0 else high >= lot.stop
            if touched:
                stop_raw = min(raw_open, lot.stop) if lot.side > 0 else max(raw_open, lot.stop)
                close_lot(lot, ts, stop_raw, "position_stop")

        if (
            campaign is not None
            and campaign.first_entry_fill is not None
            and campaign.anchor_r_price
            and active_lots()
        ):
            progress_close = campaign.side * (close - campaign.first_entry_fill)
            current_mfe_r = progress_close / campaign.anchor_r_price
            campaign.episode_mfe_r = max(campaign.episode_mfe_r, current_mfe_r)
            campaign.max_mfe_r = max(campaign.max_mfe_r, current_mfe_r)

        adverse_mark = low if campaign is None or campaign.side > 0 else high
        close_equity = _marked_equity(balance, lots, close)
        adverse_equity = _marked_equity(balance, lots, adverse_mark)
        open_equity = _marked_equity(balance, lots, raw_open)
        drawdown = adverse_equity / max(high_water, EPSILON) - 1.0
        high_water = max(high_water, open_equity, close_equity)
        current_leverage = sum(lot.quantity * close for lot in active_lots()) / max(close_equity, EPSILON)
        max_effective_leverage = max(max_effective_leverage, current_leverage)
        equity_rows.append(
            {
                "ts": ts,
                "equity": close_equity,
                "adverse_equity": adverse_equity,
                "intrabar_drawdown": drawdown,
                "effective_leverage": current_leverage,
            }
        )
        if first_processed:
            first_processed = False

    if campaign is not None and last_ts is not None and np.isfinite(last_close):
        end_campaign(last_ts, last_close, "data_end")
        if equity_rows:
            equity_rows[-1]["equity"] = balance

    equity = pd.DataFrame(equity_rows).set_index("ts")
    campaign_frame = pd.DataFrame(campaign_rows)
    lot_frame = pd.DataFrame(lot_rows)
    action_frame = pd.DataFrame(action_rows)
    metrics = summarize(
        equity,
        campaign_frame,
        lot_frame,
        max_effective_leverage,
        risk_violations,
        config,
    )
    return RunResult(config, metrics, campaign_frame, lot_frame, action_frame, equity)
