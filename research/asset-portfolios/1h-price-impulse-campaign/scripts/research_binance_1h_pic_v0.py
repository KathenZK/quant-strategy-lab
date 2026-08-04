from __future__ import annotations

import importlib.util
import json
import math
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path("research/asset-portfolios/1h-price-impulse-campaign")
ARTIFACT_DIR = ROOT / "artifacts"
DATA_SCRIPT = Path(
    "research/asset-portfolios/1h-four-asset-trend-habitat-audit/scripts/"
    "research_binance_1h_fatha.py"
)
RUN_DATE = "2026-08-03"
ASSETS = ("ETH", "BTC", "HYPE", "SOL")

PAST_RMS_HOURS = 720
IMPULSE_HOURS = 4
IMPULSE_THRESHOLD = 1.0
RISK_BUDGET = 0.01
MAX_LEVERAGE = 3.0
VALIDATION_HOURS = 24
MAX_HOLD_HOURS = 336
FEE_RATE = 0.001
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
SHADOW_THRESHOLDS = (0.5, 1.0, 2.0)
EPSILON = 1e-12


@dataclass(slots=True)
class Position:
    side: int
    signal_ts: pd.Timestamp
    entry_ts: pd.Timestamp
    raw_entry: float
    entry_fill: float
    quantity: float
    entry_equity: float
    entry_fee: float
    r_log: float
    r_price: float
    initial_stop: float
    stop: float
    hours_held: int = 0
    max_mfe_price: float = 0.0
    max_mae_price: float = 0.0
    reached_one_r: bool = False
    funding_pnl: float = 0.0
    max_effective_leverage: float = 0.0
    shadow_reached: dict[str, bool] = field(
        default_factory=lambda: {str(value): False for value in SHADOW_THRESHOLDS}
    )


@dataclass(frozen=True, slots=True)
class RunConfig:
    fee_rate: float = FEE_RATE
    slippage: float = BASE_SLIPPAGE
    include_funding: bool = True
    validation_exit: bool = True
    mfe_floor: bool = True
    max_hold_hours: int = MAX_HOLD_HOURS
    side_filter: int = 0


@dataclass(frozen=True, slots=True)
class RunResult:
    metrics: dict[str, Any]
    campaigns: pd.DataFrame
    equity: pd.DataFrame
    shadow_events: pd.DataFrame


def load_fatha_module() -> Any:
    spec = importlib.util.spec_from_file_location("binance_pic_data", DATA_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load data module: {DATA_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_assets() -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    module = load_fatha_module()
    loaded = module.load_assets()
    frames = {asset: loaded[asset].hourly.copy() for asset in ASSETS}
    quality = {asset: loaded[asset].quality for asset in ASSETS}
    return frames, quality


def build_features(hourly: pd.DataFrame) -> pd.DataFrame:
    frame = hourly.copy()
    log_close = np.log(frame["close"])
    hourly_return = log_close.diff()
    prior_rms = (
        hourly_return.rolling(PAST_RMS_HOURS, min_periods=PAST_RMS_HOURS)
        .apply(lambda values: float(np.sqrt(np.mean(np.square(values)))), raw=True)
        .shift(IMPULSE_HOURS)
    )
    frame["past_rms"] = prior_rms
    frame["impulse"] = log_close - log_close.shift(IMPULSE_HOURS)
    frame["scaled_impulse"] = frame["impulse"].abs() / (
        frame["past_rms"] * math.sqrt(IMPULSE_HOURS)
    )
    frame["signal_side"] = np.sign(frame["impulse"]).astype("Int8")
    frame["is_signal_clock"] = frame.index.hour == IMPULSE_HOURS
    frame["signal"] = (
        frame["is_signal_clock"]
        & frame["scaled_impulse"].ge(IMPULSE_THRESHOLD)
        & frame["past_rms"].gt(EPSILON)
    )
    return frame


def adverse_fill(raw_price: float, order_side: int, slippage: float) -> float:
    return raw_price * (1.0 + order_side * slippage)


def initial_stop(entry_fill: float, side: int, r_log: float) -> float:
    return entry_fill * math.exp(-side * r_log)


def planned_quantity(
    equity: float,
    entry_fill: float,
    stop_price: float,
    side: int,
    fee_rate: float,
    slippage: float,
) -> tuple[float, float]:
    stop_fill = adverse_fill(stop_price, -side, slippage)
    price_loss = max(0.0, side * (entry_fill - stop_fill))
    cost_per_unit = fee_rate * (entry_fill + stop_fill)
    loss_per_unit = price_loss + cost_per_unit
    if loss_per_unit <= EPSILON:
        return 0.0, 0.0
    risk_quantity = RISK_BUDGET * equity / loss_per_unit
    leverage_quantity = MAX_LEVERAGE * equity / entry_fill
    quantity = min(risk_quantity, leverage_quantity)
    planned_loss = quantity * loss_per_unit
    return max(0.0, quantity), planned_loss


def marked_equity(balance: float, position: Position | None, mark: float) -> float:
    if position is None:
        return balance
    return balance + position.quantity * position.side * (mark - position.entry_fill)


def _safe_sharpe(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    volatility = float(returns.std(ddof=0))
    if volatility <= EPSILON:
        return 0.0
    return float(returns.mean() / volatility * math.sqrt(365.0 * 24.0))


def summarize_run(
    equity: pd.DataFrame,
    campaigns: pd.DataFrame,
    shadow_events: pd.DataFrame,
    max_effective_leverage: float,
    risk_violations: int,
    config: RunConfig,
) -> dict[str, Any]:
    if equity.empty:
        return {}
    values = equity["equity"].astype(float)
    returns = values.pct_change().fillna(values.iloc[0] - 1.0)
    drawdown = values / values.cummax() - 1.0
    closed = campaigns.loc[campaigns["closed"]].copy() if not campaigns.empty else campaigns
    if closed.empty:
        wins = 0.0
        profit_factor = 0.0
        avg_hold = 0.0
        median_hold = 0.0
        avg_r = 0.0
        worst_r = 0.0
    else:
        wins = float(closed["net_pnl"].gt(0.0).mean())
        gains = float(closed.loc[closed["net_pnl"].gt(0.0), "net_pnl"].sum())
        losses = float(-closed.loc[closed["net_pnl"].lt(0.0), "net_pnl"].sum())
        profit_factor = gains / losses if losses > EPSILON else math.inf
        avg_hold = float(closed["hold_hours"].mean())
        median_hold = float(closed["hold_hours"].median())
        avg_r = float(closed["pnl_r"].mean())
        worst_r = float(closed["pnl_r"].min())
    return {
        "total_return_pct": float((values.iloc[-1] / values.iloc[0] - 1.0) * 100.0),
        "sharpe": _safe_sharpe(returns),
        "max_drawdown_pct": float(drawdown.min() * 100.0),
        "campaigns": int(len(closed)),
        "win_rate_pct": wins * 100.0,
        "profit_factor": profit_factor,
        "avg_hold_hours": avg_hold,
        "median_hold_hours": median_hold,
        "avg_pnl_r": avg_r,
        "worst_pnl_r": worst_r,
        "shadow_add_events": int(len(shadow_events)),
        "max_effective_leverage": max_effective_leverage,
        "risk_violations": risk_violations,
        "fee_rate": config.fee_rate,
        "slippage": config.slippage,
        "include_funding": config.include_funding,
        "validation_exit": config.validation_exit,
        "mfe_floor": config.mfe_floor,
        "max_hold_hours": config.max_hold_hours,
        "side_filter": config.side_filter,
    }


def run_backtest(
    hourly: pd.DataFrame,
    config: RunConfig,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> RunResult:
    frame = build_features(hourly)
    if start is not None:
        start = pd.Timestamp(start)
        start = start.tz_localize("UTC") if start.tzinfo is None else start.tz_convert("UTC")
    if end is not None:
        end = pd.Timestamp(end)
        end = end.tz_localize("UTC") if end.tzinfo is None else end.tz_convert("UTC")

    balance = 1.0
    position: Position | None = None
    pending_signal: dict[str, Any] | None = None
    campaigns: list[dict[str, Any]] = []
    equity_rows: list[dict[str, Any]] = []
    shadow_rows: list[dict[str, Any]] = []
    max_effective_leverage = 0.0
    risk_violations = 0
    active_campaign_id = 0

    def close_position(
        ts: pd.Timestamp,
        raw_price: float,
        reason: str,
        closed: bool = True,
    ) -> None:
        nonlocal balance, position
        if position is None:
            return
        current = position
        fill = adverse_fill(raw_price, -current.side, config.slippage)
        exit_fee = current.quantity * fill * config.fee_rate
        price_pnl = current.quantity * current.side * (fill - current.entry_fill)
        balance += price_pnl - exit_fee
        net_pnl = balance - current.entry_equity
        planned_risk = RISK_BUDGET * current.entry_equity
        campaigns.append(
            {
                "campaign_id": active_campaign_id,
                "signal_ts": current.signal_ts,
                "entry_ts": current.entry_ts,
                "exit_ts": ts,
                "side": current.side,
                "raw_entry": current.raw_entry,
                "entry_fill": current.entry_fill,
                "exit_fill": fill,
                "quantity": current.quantity,
                "entry_equity": current.entry_equity,
                "exit_equity": balance,
                "initial_stop": current.initial_stop,
                "final_stop": current.stop,
                "r_log": current.r_log,
                "r_price": current.r_price,
                "hold_hours": current.hours_held,
                "max_mfe_r": current.max_mfe_price / current.r_price,
                "max_mae_r": current.max_mae_price / current.r_price,
                "entry_fee": current.entry_fee,
                "exit_fee": exit_fee,
                "funding_pnl": current.funding_pnl,
                "price_pnl": price_pnl,
                "net_pnl": net_pnl,
                "pnl_r": net_pnl / planned_risk if planned_risk > EPSILON else math.nan,
                "exit_reason": reason,
                "max_effective_leverage": current.max_effective_leverage,
                "closed": closed,
            }
        )
        position = None

    for location, (visible_ts, row) in enumerate(frame.iterrows()):
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
            scheduled_reason = None
            if config.validation_exit and position.hours_held >= VALIDATION_HOURS:
                if not position.reached_one_r:
                    scheduled_reason = "validation_failed_24h"
            if position.hours_held >= config.max_hold_hours:
                scheduled_reason = f"timeout_{config.max_hold_hours}h"
            if scheduled_reason is not None:
                close_position(execution_ts, raw_open, scheduled_reason)

        if pending_signal is not None and position is None:
            side = int(pending_signal["side"])
            entry_fill = adverse_fill(raw_open, side, config.slippage)
            r_log = float(pending_signal["r_log"])
            stop_price = initial_stop(entry_fill, side, r_log)
            quantity, planned_loss = planned_quantity(
                balance,
                entry_fill,
                stop_price,
                side,
                config.fee_rate,
                config.slippage,
            )
            if quantity > EPSILON:
                entry_equity = balance
                entry_fee = quantity * entry_fill * config.fee_rate
                balance -= entry_fee
                r_price = abs(entry_fill - stop_price)
                position = Position(
                    side=side,
                    signal_ts=pending_signal["signal_ts"],
                    entry_ts=execution_ts,
                    raw_entry=raw_open,
                    entry_fill=entry_fill,
                    quantity=quantity,
                    entry_equity=entry_equity,
                    entry_fee=entry_fee,
                    r_log=r_log,
                    r_price=r_price,
                    initial_stop=stop_price,
                    stop=stop_price,
                )
                active_campaign_id += 1
                if planned_loss > RISK_BUDGET * entry_equity * (1.0 + 1e-9):
                    risk_violations += 1
            pending_signal = None

        if position is not None:
            funding_rate = float(row["funding_rate"]) if config.include_funding else 0.0
            funding_pnl = (
                -position.side * position.quantity * raw_open * funding_rate
            )
            balance += funding_pnl
            position.funding_pnl += funding_pnl

            gap_hit = (position.side > 0 and raw_open <= position.stop) or (
                position.side < 0 and raw_open >= position.stop
            )
            if gap_hit:
                close_position(execution_ts, raw_open, "stop_gap")
            else:
                stop_hit = (position.side > 0 and low <= position.stop) or (
                    position.side < 0 and high >= position.stop
                )
                if stop_hit:
                    close_position(visible_ts, position.stop, "stop_intrabar")

        if position is not None:
            favorable = (
                high - position.entry_fill
                if position.side > 0
                else position.entry_fill - low
            )
            adverse = (
                position.entry_fill - low
                if position.side > 0
                else high - position.entry_fill
            )
            position.max_mfe_price = max(position.max_mfe_price, favorable, 0.0)
            position.max_mae_price = max(position.max_mae_price, adverse, 0.0)
            mfe_r = position.max_mfe_price / position.r_price
            if mfe_r >= 1.0:
                position.reached_one_r = True
            for threshold in SHADOW_THRESHOLDS:
                key = str(threshold)
                if mfe_r >= threshold and not position.shadow_reached[key]:
                    position.shadow_reached[key] = True
                    shadow_rows.append(
                        {
                            "campaign_id": active_campaign_id,
                            "ts": visible_ts,
                            "side": position.side,
                            "threshold_r": threshold,
                            "hours_held": position.hours_held + 1,
                            "mark": close,
                            "mfe_r": mfe_r,
                        }
                    )
            if config.mfe_floor and mfe_r >= 2.0:
                candidate = position.entry_fill + (
                    position.side * 0.5 * position.max_mfe_price
                )
                if position.side > 0:
                    position.stop = max(position.stop, candidate)
                else:
                    position.stop = min(position.stop, candidate)
            position.hours_held += 1

            current_equity = marked_equity(balance, position, close)
            effective = (
                position.quantity * close / max(current_equity, EPSILON)
            )
            position.max_effective_leverage = max(
                position.max_effective_leverage, effective
            )
            max_effective_leverage = max(max_effective_leverage, effective)

        if position is None and bool(row["signal"]):
            signal_side = int(row["signal_side"])
            if config.side_filter == 0 or signal_side == config.side_filter:
                pending_signal = {
                    "signal_ts": visible_ts,
                    "side": signal_side,
                    "r_log": float(row["past_rms"] * math.sqrt(24.0)),
                    "scaled_impulse": float(row["scaled_impulse"]),
                }

        equity_rows.append(
            {
                "ts": visible_ts,
                "equity": marked_equity(balance, position, close),
                "balance": balance,
                "position_side": 0 if position is None else position.side,
                "quantity": 0.0 if position is None else position.quantity,
                "mark": close,
                "stop": math.nan if position is None else position.stop,
            }
        )

    if position is not None:
        last_ts = frame.index[-1]
        last_close = float(frame.iloc[-1]["close"])
        close_position(last_ts, last_close, "data_end", closed=False)
        if equity_rows:
            equity_rows[-1]["equity"] = balance
            equity_rows[-1]["balance"] = balance
            equity_rows[-1]["position_side"] = 0
            equity_rows[-1]["quantity"] = 0.0
            equity_rows[-1]["stop"] = math.nan

    campaign_frame = pd.DataFrame(campaigns)
    equity_frame = pd.DataFrame(equity_rows)
    shadow_frame = pd.DataFrame(shadow_rows)
    metrics = summarize_run(
        equity_frame,
        campaign_frame,
        shadow_frame,
        max_effective_leverage,
        risk_violations,
        config,
    )
    return RunResult(metrics, campaign_frame, equity_frame, shadow_frame)


def recent_slice_starts(end: pd.Timestamp) -> dict[str, pd.Timestamp]:
    return {
        "1d": end - pd.Timedelta(days=1),
        "7d": end - pd.Timedelta(days=7),
        "1m": end - pd.DateOffset(months=1),
        "3m": end - pd.DateOffset(months=3),
        "6m": end - pd.DateOffset(months=6),
        "1y": end - pd.DateOffset(years=1),
    }


def rolling_windows(
    hourly: pd.DataFrame,
    config: RunConfig,
    evaluation_days: int = 120,
    step_days: int = 30,
) -> pd.DataFrame:
    earliest = hourly.index.min() + pd.Timedelta(hours=PAST_RMS_HOURS + IMPULSE_HOURS)
    latest = hourly.index.max()
    cursor = earliest.ceil("1D")
    rows: list[dict[str, Any]] = []
    while cursor + pd.Timedelta(days=evaluation_days) <= latest:
        window_end = cursor + pd.Timedelta(days=evaluation_days)
        result = run_backtest(hourly, config, cursor, window_end)
        rows.append(
            {
                "start": cursor,
                "end": window_end,
                **result.metrics,
            }
        )
        cursor += pd.Timedelta(days=step_days)
    return pd.DataFrame(rows)


def frame_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    return json.loads(frame.to_json(orient="records", date_format="iso"))


def candidate_decision(
    metrics: pd.DataFrame,
    slices: pd.DataFrame,
    rolling: pd.DataFrame,
) -> dict[str, Any]:
    base = metrics.loc[
        metrics["asset"].eq("ETH")
        & metrics["arm"].eq("all")
        & metrics["cost_model"].eq("base")
    ].iloc[0]
    stress = metrics.loc[
        metrics["asset"].eq("ETH")
        & metrics["arm"].eq("all")
        & metrics["cost_model"].eq("stress_8bps")
    ].iloc[0]
    six_month = slices.loc[
        slices["asset"].eq("ETH") & slices["slice"].eq("6m")
    ].iloc[0]
    eth_rolling = rolling.loc[rolling["asset"].eq("ETH")]
    positive_ratio = (
        float(eth_rolling["total_return_pct"].gt(0.0).mean())
        if not eth_rolling.empty
        else 0.0
    )
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
    }
    return {
        "all_minimum_gates_pass": bool(all(gates.values())),
        "rolling_positive_ratio": positive_ratio,
        "gates": gates,
        "status_if_not_pass": "explore / not promoted / not live-ready",
        "selection_boundary": (
            "historical onset evidence was revealed before V0 freeze; even a pass "
            "cannot by itself authorize promotion"
        ),
    }


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    assets, data_quality = load_assets()

    metric_rows: list[dict[str, Any]] = []
    all_campaigns: list[pd.DataFrame] = []
    all_equity: list[pd.DataFrame] = []
    all_shadow: list[pd.DataFrame] = []
    slice_rows: list[dict[str, Any]] = []
    rolling_rows: list[pd.DataFrame] = []
    ablation_rows: list[dict[str, Any]] = []

    cost_models = {
        "gross": RunConfig(fee_rate=0.0, slippage=0.0, include_funding=False),
        "base": RunConfig(),
        "stress_8bps": RunConfig(slippage=STRESS_SLIPPAGE),
    }
    arms = {"all": 0, "long": 1, "short": -1}

    for asset in ASSETS:
        hourly = assets[asset]
        for cost_name, base_config in cost_models.items():
            for arm, side_filter in arms.items():
                config = RunConfig(
                    fee_rate=base_config.fee_rate,
                    slippage=base_config.slippage,
                    include_funding=base_config.include_funding,
                    side_filter=side_filter,
                )
                result = run_backtest(hourly, config)
                metric_rows.append(
                    {
                        "asset": asset,
                        "cost_model": cost_name,
                        "arm": arm,
                        **result.metrics,
                    }
                )
                if cost_name == "base" and arm == "all":
                    for frame, target in (
                        (result.campaigns, all_campaigns),
                        (result.equity, all_equity),
                        (result.shadow_events, all_shadow),
                    ):
                        if not frame.empty:
                            copy = frame.copy()
                            copy["asset"] = asset
                            target.append(copy)

        end = hourly.index.max()
        for name, start in recent_slice_starts(end).items():
            result = run_backtest(hourly, RunConfig(), start, end)
            slice_rows.append(
                {
                    "asset": asset,
                    "slice": name,
                    "start": start,
                    "end": end,
                    **result.metrics,
                }
            )

        rolling = rolling_windows(hourly, RunConfig())
        if not rolling.empty:
            rolling["asset"] = asset
            rolling_rows.append(rolling)

    eth = assets["ETH"]
    ablations = {
        "full": RunConfig(),
        "no_validation_exit": RunConfig(validation_exit=False),
        "no_mfe_floor": RunConfig(mfe_floor=False),
        "timeout_72h": RunConfig(max_hold_hours=72),
    }
    for name, config in ablations.items():
        result = run_backtest(eth, config)
        ablation_rows.append({"variant": name, **result.metrics})

    metrics = pd.DataFrame(metric_rows)
    campaigns = pd.concat(all_campaigns, ignore_index=True) if all_campaigns else pd.DataFrame()
    equity = pd.concat(all_equity, ignore_index=True) if all_equity else pd.DataFrame()
    shadow = pd.concat(all_shadow, ignore_index=True) if all_shadow else pd.DataFrame()
    slices = pd.DataFrame(slice_rows)
    rolling = pd.concat(rolling_rows, ignore_index=True) if rolling_rows else pd.DataFrame()
    ablation = pd.DataFrame(ablation_rows)
    decision = candidate_decision(metrics, slices, rolling)

    outputs = {
        "metrics": metrics,
        "campaigns": campaigns,
        "equity": equity,
        "shadow_add_events": shadow,
        "recent_slices": slices,
        "rolling_120d": rolling,
        "ablation": ablation,
    }
    for name, frame in outputs.items():
        suffix = "parquet" if name == "equity" else "csv"
        path = ARTIFACT_DIR / f"binance_1h_pic_v0_{name}_{RUN_DATE}.{suffix}"
        if suffix == "parquet":
            frame.to_parquet(path, index=False)
        else:
            frame.to_csv(path, index=False)

    payload = {
        "family": "Binance-1H-Price-Impulse-Campaign",
        "candidate_id": "BIN-1H-PIC-V0",
        "status": "explore / not promoted / not live-ready",
        "run_date": RUN_DATE,
        "contract": {
            "assets": ASSETS,
            "candidate_asset": "ETH",
            "past_rms_hours": PAST_RMS_HOURS,
            "impulse_hours": IMPULSE_HOURS,
            "impulse_threshold": IMPULSE_THRESHOLD,
            "risk_budget": RISK_BUDGET,
            "max_leverage": MAX_LEVERAGE,
            "validation_hours": VALIDATION_HOURS,
            "max_hold_hours": MAX_HOLD_HOURS,
            "fee_rate": FEE_RATE,
            "base_slippage": BASE_SLIPPAGE,
            "stress_slippage": STRESS_SLIPPAGE,
            "shadow_thresholds_r": SHADOW_THRESHOLDS,
        },
        "data_quality": data_quality,
        "candidate_decision": decision,
        "summaries": {
            name: frame_records(frame)
            for name, frame in outputs.items()
            if name != "equity"
        },
    }
    with (ARTIFACT_DIR / f"binance_1h_pic_v0_research_{RUN_DATE}.json").open(
        "w", encoding="utf-8"
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)

    print("FROZEN V0 METRICS")
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
                "win_rate_pct",
                "profit_factor",
                "avg_hold_hours",
                "max_effective_leverage",
                "risk_violations",
            ],
        ].to_string(index=False)
    )
    print("\nETH RECENT SLICES")
    print(
        slices.loc[
            slices["asset"].eq("ETH"),
            ["slice", "total_return_pct", "sharpe", "max_drawdown_pct", "campaigns"],
        ].to_string(index=False)
    )
    print("\nETH ABLATION")
    print(
        ablation[
            ["variant", "total_return_pct", "sharpe", "max_drawdown_pct", "campaigns", "avg_hold_hours"]
        ].to_string(index=False)
    )
    print("\nDECISION")
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
