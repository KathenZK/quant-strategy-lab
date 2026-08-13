from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/4h-ma7-close-reversal"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
SOURCE_ADAPTER = (
    ROOT
    / "research/hype/4h-ma7-asymmetric-body-trend/scripts"
    / "research_hype_4h_ma7_v1_transfer.py"
)
SOURCE_ADAPTER_SHA256 = (
    "4d39631cdb40b4d318c2f757110984fe5db41fa18d8578d35be8c3e04607e4e5"
)
PARENT_LOADER_SHA256 = (
    "e5b4c9732cdf0a789ebe97a2a4d8e1d799f5496d2a7a2f8068f3773c376ef232"
)

FAMILY = "HYPE-4H-MA7-Close-Reversal"
ALIAS = "HYPE-4H-MA7-CR"
BAR_HOURS = 4
MA_WINDOW = 7
PHASES = (0, 1, 2, 3)
FEE = 0.001
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
RECENT_WINDOWS = {
    "1d": 1,
    "7d": 7,
    "1m": 30,
    "3m": 90,
    "6m": 182,
    "1y": 365,
}


@dataclass(frozen=True, slots=True)
class FundingEvent:
    ts: pd.Timestamp
    rate: float
    price: float


@dataclass(slots=True)
class MarketBundle:
    bars: pd.DataFrame
    terminal_ts: pd.Timestamp
    terminal_open: float
    hourly_open: np.ndarray
    hourly_high: np.ndarray
    hourly_low: np.ndarray
    hourly_close: np.ndarray
    funding_events: list[list[FundingEvent]]
    sma7: np.ndarray
    quality: dict[str, Any]

    @property
    def count(self) -> int:
        return len(self.bars)


@dataclass(slots=True)
class Result:
    metrics: dict[str, Any]
    trades: list[dict[str, Any]]
    path: list[dict[str, Any]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backtest HYPE 4h close-confirmed SMA7 reversal."
    )
    parser.add_argument(
        "--run-date",
        default=datetime.now(UTC).date().isoformat(),
    )
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def load_module(path: Path, expected_hash: str, name: str) -> Any:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected_hash:
        raise RuntimeError(
            f"{path.name} drift: expected {expected_hash}, got {digest}"
        )
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_bundle(
    adapter: Any,
    hourly: pd.DataFrame,
    hourly_quality: dict[str, Any],
    funding: pd.DataFrame,
    funding_quality: dict[str, Any],
    *,
    phase_hours: int,
) -> MarketBundle:
    bars, aggregate_quality = adapter.aggregate_4h(
        hourly,
        phase_hours=phase_hours,
    )
    hourly_frame = hourly.copy()
    hourly_frame["ts"] = pd.to_datetime(hourly_frame["ts"], utc=True)
    hourly_frame = hourly_frame.set_index("ts").sort_index()
    funding_frame = funding.copy()
    funding_frame["ts"] = pd.to_datetime(funding_frame["ts"], utc=True)
    funding_frame = funding_frame.sort_values("ts")
    terminal_ts = pd.Timestamp(aggregate_quality["terminal_open_ts"])
    terminal_open = float(hourly_frame.loc[terminal_ts, "open"])
    hourly_open: list[np.ndarray] = []
    hourly_high: list[np.ndarray] = []
    hourly_low: list[np.ndarray] = []
    hourly_close: list[np.ndarray] = []
    funding_events: list[list[FundingEvent]] = []
    for bar_start in pd.DatetimeIndex(bars["ts"]):
        bar_end = bar_start + pd.Timedelta(hours=BAR_HOURS)
        rows = hourly_frame.loc[
            (hourly_frame.index >= bar_start)
            & (hourly_frame.index < bar_end)
        ]
        if len(rows) != BAR_HOURS:
            raise RuntimeError(
                f"phase {phase_hours}: expected four 1h bars at {bar_start}"
            )
        hourly_open.append(rows["open"].to_numpy("float64"))
        hourly_high.append(rows["high"].to_numpy("float64"))
        hourly_low.append(rows["low"].to_numpy("float64"))
        hourly_close.append(rows["close"].to_numpy("float64"))
        selected_funding = funding_frame.loc[
            funding_frame["ts"].ge(bar_start)
            & funding_frame["ts"].lt(bar_end)
        ]
        events: list[FundingEvent] = []
        for row in selected_funding.itertuples(index=False):
            event_ts = pd.Timestamp(row.ts)
            event_hour = event_ts.floor("h")
            if event_hour not in rows.index:
                raise RuntimeError(
                    f"funding event {event_ts} has no matching 1h candle"
                )
            events.append(
                FundingEvent(
                    ts=event_ts,
                    rate=float(row.funding_rate),
                    price=float(rows.loc[event_hour, "open"]),
                )
            )
        funding_events.append(events)
    close = bars["close"].astype(float)
    sma7 = close.rolling(
        MA_WINDOW,
        min_periods=MA_WINDOW,
    ).mean()
    quality = {
        "exchange": "Binance",
        "market": "USD-M perpetual",
        "symbol": "HYPEUSDT",
        "source_timeframe": "1h",
        "strategy_timeframe": "4h",
        "phase_hours": phase_hours,
        "hourly": hourly_quality,
        "funding": funding_quality,
        "bars": aggregate_quality,
        "terminal_open": terminal_open,
    }
    return MarketBundle(
        bars=bars,
        terminal_ts=terminal_ts,
        terminal_open=terminal_open,
        hourly_open=np.asarray(hourly_open, dtype=float),
        hourly_high=np.asarray(hourly_high, dtype=float),
        hourly_low=np.asarray(hourly_low, dtype=float),
        hourly_close=np.asarray(hourly_close, dtype=float),
        funding_events=funding_events,
        sma7=sma7.to_numpy("float64"),
        quality=quality,
    )


def close_targets(bundle: MarketBundle) -> np.ndarray:
    close = bundle.bars["close"].to_numpy("float64")
    targets = np.zeros(bundle.count, dtype=np.int8)
    valid = np.isfinite(bundle.sma7)
    targets[valid & (close > bundle.sma7)] = 1
    targets[valid & (close < bundle.sma7)] = -1
    return targets


def target_quantity(
    equity: float,
    old_qty: float,
    target_side: int,
    price: float,
    cost_rate: float,
) -> tuple[float, float, float]:
    post_equity = equity
    target_qty = old_qty
    turnover = 0.0
    for _ in range(20):
        target_qty = target_side * post_equity / price
        turnover = abs(target_qty - old_qty) * price
        updated = equity - turnover * cost_rate
        if math.isclose(updated, post_equity, rel_tol=0.0, abs_tol=1e-14):
            post_equity = updated
            break
        post_equity = updated
    return target_qty, post_equity, turnover


def route_target(signal: int, route: str, current_side: int) -> int:
    if route == "buy_and_hold":
        return 1
    if signal == 0:
        return current_side
    if route == "combined":
        return signal
    if route == "long_only":
        return 1 if signal > 0 else 0
    if route == "short_only":
        return -1 if signal < 0 else 0
    raise ValueError(route)


def backtest(
    bundle: MarketBundle,
    *,
    route: str,
    start_index: int,
    terminal_index: int,
    fee: float = FEE,
    slippage: float = BASE_SLIPPAGE,
    signal_lag: int = 0,
    retain: bool = False,
    external_targets: np.ndarray | None = None,
) -> Result:
    if route not in {
        "combined",
        "long_only",
        "short_only",
        "buy_and_hold",
        "external",
    }:
        raise ValueError(route)
    if not (0 <= start_index < terminal_index <= bundle.count):
        raise ValueError("invalid backtest window")
    if route == "external":
        if external_targets is None or len(external_targets) != bundle.count:
            raise ValueError("external route requires one target per close")
        if not np.isin(external_targets, (-1, 0, 1)).all():
            raise ValueError("external targets must be -1, 0, or 1")
    timestamps = pd.DatetimeIndex(
        [*bundle.bars["ts"], bundle.terminal_ts]
    )
    opens = np.r_[
        bundle.bars["open"].to_numpy("float64"),
        bundle.terminal_open,
    ]
    targets = (
        np.asarray(external_targets, dtype=np.int8)
        if route == "external"
        else close_targets(bundle)
    )
    cost_rate = fee + slippage
    equity = 1.0
    qty = 0.0
    side = 0
    mark_price = float(opens[start_index])
    peak = 1.0
    max_drawdown = 0.0
    total_turnover = 0.0
    total_cost = 0.0
    total_funding = 0.0
    max_intrabar_leverage = 0.0
    flip_count = 0
    fill_count = 0
    exposed_bars = 0
    entry_ts: pd.Timestamp | None = None
    entry_price = math.nan
    entry_equity = math.nan
    entry_side = 0
    trades: list[dict[str, Any]] = []
    path: list[dict[str, Any]] = []
    equity_points: list[float] = [1.0]
    bankrupt = False

    def trade_to(target_side: int, price: float) -> None:
        nonlocal equity, qty, side, total_turnover, total_cost, fill_count
        old_equity = equity
        qty, equity, turnover = target_quantity(
            equity,
            qty,
            target_side,
            price,
            cost_rate,
        )
        total_turnover += turnover
        total_cost += old_equity - equity
        fill_count += 1
        side = target_side

    def close_trade(ts: pd.Timestamp, price: float, reason: str) -> None:
        nonlocal entry_ts, entry_price, entry_equity, entry_side
        if entry_ts is None:
            raise RuntimeError("cannot close absent trade")
        old_side = entry_side
        trade_to(0, price)
        holding_hours = (ts - entry_ts).total_seconds() / 3_600.0
        trades.append(
            {
                "entry_ts": entry_ts.isoformat(),
                "exit_ts": ts.isoformat(),
                "side": "long" if old_side > 0 else "short",
                "entry_price": entry_price,
                "exit_price": price,
                "holding_hours": holding_hours,
                "bars_held": int(max(0.0, holding_hours) // BAR_HOURS),
                "exit_reason": reason,
                "net_return": equity / entry_equity - 1.0,
                "net_pnl": equity - entry_equity,
            }
        )
        entry_ts = None
        entry_price = math.nan
        entry_equity = math.nan
        entry_side = 0

    def open_trade(ts: pd.Timestamp, price: float, target_side: int) -> None:
        nonlocal entry_ts, entry_price, entry_equity, entry_side
        before = equity
        trade_to(target_side, price)
        entry_ts = ts
        entry_price = price
        entry_equity = before
        entry_side = target_side

    for index in range(start_index, terminal_index + 1):
        ts = pd.Timestamp(timestamps[index])
        current_open = float(opens[index])
        if index > start_index and qty != 0.0:
            equity += qty * (current_open - mark_price)
        mark_price = current_open
        pre_action_equity = equity
        action = "hold"
        if index >= terminal_index:
            if side != 0:
                close_trade(ts, current_open, "terminal_flatten")
                action = "terminal_flatten"
            peak = max(peak, pre_action_equity, equity)
            max_drawdown = min(max_drawdown, equity / peak - 1.0)
            if retain:
                path.append(
                    {
                        "ts": ts.isoformat(),
                        "pre_action_equity": pre_action_equity,
                        "post_action_equity": equity,
                        "close_equity": equity,
                        "favorable_equity": equity,
                        "adverse_equity": equity,
                        "position": 0,
                        "action": action,
                    }
                )
            equity_points.append(equity)
            break

        if route == "buy_and_hold":
            desired = 1
        else:
            decision_index = index - 1 - signal_lag
            if route == "external":
                desired = (
                    int(targets[decision_index])
                    if decision_index >= 0
                    else 0
                )
            else:
                signal = (
                    int(targets[decision_index])
                    if decision_index >= 0
                    else 0
                )
                desired = route_target(signal, route, side)
        if desired != side:
            old_side = side
            if side != 0:
                close_trade(ts, current_open, "signal_flip")
            if desired != 0:
                open_trade(ts, current_open, desired)
            if old_side != 0 and desired != 0:
                flip_count += 1
                action = "reverse_to_long" if desired > 0 else "reverse_to_short"
            elif desired != 0:
                action = "enter_long" if desired > 0 else "enter_short"
            else:
                action = "exit_to_flat"

        post_action_equity = equity
        peak = max(peak, pre_action_equity, post_action_equity)
        max_drawdown = min(max_drawdown, post_action_equity / peak - 1.0)
        favorable_equity = post_action_equity
        adverse_equity = post_action_equity
        if side != 0:
            exposed_bars += 1
        events_by_hour: dict[pd.Timestamp, list[FundingEvent]] = {}
        for event in bundle.funding_events[index]:
            events_by_hour.setdefault(event.ts.floor("h"), []).append(event)
        for hour in range(BAR_HOURS):
            hour_ts = ts + pd.Timedelta(hours=hour)
            hour_open = float(bundle.hourly_open[index, hour])
            if qty != 0.0 and not math.isclose(
                hour_open,
                mark_price,
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                equity += qty * (hour_open - mark_price)
            mark_price = hour_open
            for event in events_by_hour.get(hour_ts, []):
                payment = qty * event.price * event.rate
                equity -= payment
                total_funding += payment
            if qty != 0.0 and equity > 0.0:
                max_intrabar_leverage = max(
                    max_intrabar_leverage,
                    abs(qty) * mark_price / equity,
                )
            high = float(bundle.hourly_high[index, hour])
            low = float(bundle.hourly_low[index, hour])
            high_equity = equity + qty * (high - mark_price)
            low_equity = equity + qty * (low - mark_price)
            for extreme_price, extreme_equity in (
                (high, high_equity),
                (low, low_equity),
            ):
                if qty != 0.0 and extreme_equity > 0.0:
                    max_intrabar_leverage = max(
                        max_intrabar_leverage,
                        abs(qty) * extreme_price / extreme_equity,
                    )
            local_favorable = max(high_equity, low_equity)
            local_adverse = min(high_equity, low_equity)
            favorable_equity = max(favorable_equity, local_favorable)
            adverse_equity = min(adverse_equity, local_adverse)
            peak = max(peak, local_favorable)
            max_drawdown = min(max_drawdown, local_adverse / peak - 1.0)
            if local_adverse <= 0.0:
                bankrupt = True
                equity = 0.0
                max_drawdown = -1.0
                break
            hour_close = float(bundle.hourly_close[index, hour])
            equity += qty * (hour_close - mark_price)
            mark_price = hour_close
        if bankrupt:
            break
        close_equity = equity
        peak = max(peak, close_equity)
        max_drawdown = min(max_drawdown, close_equity / peak - 1.0)
        equity_points.append(close_equity)
        if retain:
            path.append(
                {
                    "ts": (ts + pd.Timedelta(hours=BAR_HOURS)).isoformat(),
                    "pre_action_equity": pre_action_equity,
                    "post_action_equity": post_action_equity,
                    "close_equity": close_equity,
                    "favorable_equity": favorable_equity,
                    "adverse_equity": adverse_equity,
                    "position": side,
                    "action": action,
                }
            )

    days = max(
        1.0,
        (
            timestamps[terminal_index] - timestamps[start_index]
        ).total_seconds()
        / 86_400.0,
    )
    trade_pnl = np.asarray(
        [float(trade["net_pnl"]) for trade in trades],
        dtype=float,
    )
    gross_profit = (
        float(trade_pnl[trade_pnl > 0.0].sum()) if len(trade_pnl) else 0.0
    )
    gross_loss = (
        float(-trade_pnl[trade_pnl < 0.0].sum()) if len(trade_pnl) else 0.0
    )
    returns = (
        pd.Series(equity_points, dtype=float)
        .pct_change()
        .replace([np.inf, -np.inf], np.nan)
        .dropna()
    )
    sharpe = (
        float(
            np.sqrt(365.25 * 24.0 / BAR_HOURS)
            * returns.mean()
            / returns.std(ddof=1)
        )
        if len(returns) >= 30 and returns.std(ddof=1) > 0.0
        else math.nan
    )
    metrics = {
        "route": route,
        "start_ts": pd.Timestamp(timestamps[start_index]).isoformat(),
        "end_ts": pd.Timestamp(timestamps[terminal_index]).isoformat(),
        "days": days,
        "equity_multiple": equity,
        "net_return_pct": (equity - 1.0) * 100.0,
        "max_drawdown_pct": max_drawdown * 100.0,
        "sharpe": sharpe,
        "closed_trades": len(trades),
        "long_trades": sum(trade["side"] == "long" for trade in trades),
        "short_trades": sum(trade["side"] == "short" for trade in trades),
        "win_rate": (
            float((trade_pnl > 0.0).mean()) if len(trade_pnl) else math.nan
        ),
        "profit_factor": (
            gross_profit / gross_loss
            if gross_loss > 0.0
            else (math.inf if gross_profit > 0.0 else math.nan)
        ),
        "flip_count": flip_count,
        "fill_count": fill_count,
        "exposure_pct": (
            exposed_bars / max(1, terminal_index - start_index) * 100.0
        ),
        "turnover_multiple": total_turnover,
        "cost_pct_initial": total_cost * 100.0,
        "funding_pct_initial": total_funding * 100.0,
        "max_intrabar_leverage": max_intrabar_leverage,
        "bankrupt_intrabar": bankrupt,
    }
    return Result(metrics=metrics, trades=trades, path=path)


def recent_slices(result: Result) -> list[dict[str, Any]]:
    path = pd.DataFrame(result.path)
    if path.empty:
        return []
    path["ts"] = pd.to_datetime(path["ts"], utc=True)
    end = path["ts"].max()
    rows: list[dict[str, Any]] = []
    for label, days in RECENT_WINDOWS.items():
        start = end - pd.Timedelta(days=days)
        part = path.loc[path["ts"].gt(start)].copy()
        if part.empty:
            continue
        initial = float(part.iloc[0]["pre_action_equity"])
        final = float(part.iloc[-1]["close_equity"])
        peak = initial
        drawdown = 0.0
        for row in part.itertuples(index=False):
            peak = max(
                peak,
                float(row.pre_action_equity),
                float(row.post_action_equity),
                float(row.favorable_equity),
            )
            drawdown = min(
                drawdown,
                float(row.post_action_equity) / peak - 1.0,
                float(row.adverse_equity) / peak - 1.0,
                float(row.close_equity) / peak - 1.0,
            )
        rows.append(
            {
                "window": label,
                "start_ts": start.isoformat(),
                "end_ts": end.isoformat(),
                "return_pct": (final / initial - 1.0) * 100.0,
                "path_mdd_pct": drawdown * 100.0,
            }
        )
    return rows


def rolling_90d(bundle: MarketBundle) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    window_bars = 90 * 24 // BAR_HOURS
    step_bars = 30 * 24 // BAR_HOURS
    start = 0
    while start + window_bars <= bundle.count:
        end = start + window_bars
        result = backtest(
            bundle,
            route="combined",
            start_index=start,
            terminal_index=end,
        )
        rows.append({"window_index": len(rows), **result.metrics})
        start += step_bars
    return rows


def phase_audit(bundles: dict[int, MarketBundle]) -> list[dict[str, Any]]:
    common_start = max(
        pd.Timestamp(bundle.bars.iloc[0]["ts"])
        for bundle in bundles.values()
    )
    common_end = min(bundle.terminal_ts for bundle in bundles.values())
    rows: list[dict[str, Any]] = []
    for phase, bundle in sorted(bundles.items()):
        timestamps = pd.DatetimeIndex(
            [*bundle.bars["ts"], bundle.terminal_ts]
        )
        start = int(timestamps.searchsorted(common_start, side="left"))
        end = int(timestamps.searchsorted(common_end, side="right") - 1)
        result = backtest(
            bundle,
            route="combined",
            start_index=start,
            terminal_index=end,
        )
        rows.append(
            {
                "phase_hours": phase,
                "common_start": common_start.isoformat(),
                "common_end": common_end.isoformat(),
                **result.metrics,
            }
        )
    return rows


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: clean_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json(item) for item in value]
    if isinstance(value, np.generic):
        return clean_json(value.item())
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_outputs(
    *,
    run_date: str,
    bundles: dict[int, MarketBundle],
) -> None:
    bundle = bundles[0]
    audit_split = bundle.terminal_ts - pd.Timedelta(days=120)
    split_index = int(
        pd.DatetimeIndex(bundle.bars["ts"]).searchsorted(
            audit_split,
            side="left",
        )
    )
    if (
        split_index <= 0
        or split_index >= bundle.count
        or pd.Timestamp(bundle.bars.iloc[split_index]["ts"]) != audit_split
    ):
        raise RuntimeError("audit split unavailable")
    scenarios = {
        "base": {
            "fee": FEE,
            "slippage": BASE_SLIPPAGE,
            "signal_lag": 0,
        },
        "stress_8bps": {
            "fee": FEE,
            "slippage": STRESS_SLIPPAGE,
            "signal_lag": 0,
        },
        "delay_1bar": {
            "fee": FEE,
            "slippage": BASE_SLIPPAGE,
            "signal_lag": 1,
        },
        "gross_no_trade_cost": {
            "fee": 0.0,
            "slippage": 0.0,
            "signal_lag": 0,
        },
    }
    windows = {
        "early": (0, split_index),
        "last_120d": (split_index, bundle.count),
        "full": (0, bundle.count),
    }
    audits: dict[str, Any] = {}
    metric_rows: list[dict[str, Any]] = []
    full_result: Result | None = None
    for window, (start, end) in windows.items():
        audits[window] = {}
        for scenario, kwargs in scenarios.items():
            retain = window == "full" and scenario == "base"
            result = backtest(
                bundle,
                route="combined",
                start_index=start,
                terminal_index=end,
                retain=retain,
                **kwargs,
            )
            audits[window][scenario] = result.metrics
            metric_rows.append(
                {
                    "window": window,
                    "scenario": scenario,
                    **result.metrics,
                }
            )
            if retain:
                full_result = result
        benchmark = backtest(
            bundle,
            route="buy_and_hold",
            start_index=start,
            terminal_index=end,
        )
        audits[window]["buy_and_hold"] = benchmark.metrics
        metric_rows.append(
            {
                "window": window,
                "scenario": "buy_and_hold",
                **benchmark.metrics,
            }
        )
    if full_result is None:
        raise RuntimeError("retained full result missing")
    components: list[dict[str, Any]] = []
    for route in ("combined", "long_only", "short_only"):
        for window, start, end in (
            ("last_120d", split_index, bundle.count),
            ("full", 0, bundle.count),
        ):
            result = backtest(
                bundle,
                route=route,
                start_index=start,
                terminal_index=end,
            )
            components.append(
                {"window": window, "variant": route, **result.metrics}
            )
    phases = phase_audit(bundles)
    rolling = rolling_90d(bundle)
    recent = recent_slices(full_result)
    full_base = audits["full"]["base"]
    full_benchmark = audits["full"]["buy_and_hold"]
    last_base = audits["last_120d"]["base"]
    last_benchmark = audits["last_120d"]["buy_and_hold"]
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": FAMILY,
        "alias": ALIAS,
        "status": "explore / not promoted / not live-ready",
        "contract": {
            "indicator": "SMA7 on closed 4h bars",
            "signal": "close > SMA7 => +1; close < SMA7 => -1",
            "execution": "signal at 4h close; target at next 4h open",
            "always_in_after_warmup": True,
            "reversal_fill_count": 2,
            "fee_per_fill": FEE,
            "base_slippage_per_fill": BASE_SLIPPAGE,
            "stress_slippage_per_fill": STRESS_SLIPPAGE,
            "gross_scenario": "fee=0 and slippage=0; funding retained",
            "funding": "actual Binance event timestamp/rate",
            "parameter_search": False,
        },
        "source_adapter": {
            "path": str(SOURCE_ADAPTER.relative_to(ROOT)),
            "sha256": SOURCE_ADAPTER_SHA256,
            "transitive_parent_loader_sha256": PARENT_LOADER_SHA256,
        },
        "data_quality": {
            str(phase): bundle.quality
            for phase, bundle in bundles.items()
        },
        "audits": audits,
        "components": components,
        "phase_audit": phases,
        "rolling_90d": rolling,
        "recent_slices": recent,
        "decision": {
            "full_positive": full_base["equity_multiple"] > 1.0,
            "last_120d_positive": last_base["equity_multiple"] > 1.0,
            "full_excess_return_pct": (
                full_base["net_return_pct"]
                - full_benchmark["net_return_pct"]
            ),
            "last_120d_excess_return_pct": (
                last_base["net_return_pct"]
                - last_benchmark["net_return_pct"]
            ),
            "stress_positive": audits["full"]["stress_8bps"][
                "equity_multiple"
            ]
            > 1.0,
            "delay_positive": audits["full"]["delay_1bar"][
                "equity_multiple"
            ]
            > 1.0,
            "protection_blocker": "no hard stop or exchange-resident protection",
            "registration_effect": "none",
            "promotion_effect": "none",
        },
        "warning": (
            "All history is researcher-exposed. This is a zero-parameter "
            "diagnostic, not prospective OOS or promotion evidence."
        ),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = "hype_4h_ma7_close_reversal"
    summary_path = ARTIFACT_DIR / f"{stem}_summary_{run_date}.json"
    summary_path.write_text(
        json.dumps(
            clean_json(payload),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    pd.DataFrame(metric_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_metrics_{run_date}.csv",
        index=False,
    )
    pd.DataFrame(components).to_csv(
        ARTIFACT_DIR / f"{stem}_components_{run_date}.csv",
        index=False,
    )
    pd.DataFrame(phases).to_csv(
        ARTIFACT_DIR / f"{stem}_phase_{run_date}.csv",
        index=False,
    )
    pd.DataFrame(rolling).to_csv(
        ARTIFACT_DIR / f"{stem}_rolling_90d_{run_date}.csv",
        index=False,
    )
    pd.DataFrame(recent).to_csv(
        ARTIFACT_DIR / f"{stem}_recent_{run_date}.csv",
        index=False,
    )
    pd.DataFrame(full_result.trades).to_csv(
        ARTIFACT_DIR / f"{stem}_trades_{run_date}.csv",
        index=False,
    )
    pd.DataFrame(full_result.path).to_csv(
        ARTIFACT_DIR / f"{stem}_path_{run_date}.csv",
        index=False,
    )
    print(
        json.dumps(
            clean_json(
                {
                    "summary": str(summary_path.relative_to(ROOT)),
                    "full": audits["full"],
                    "last_120d": audits["last_120d"],
                    "components": components,
                    "phase_audit": phases,
                    "decision": payload["decision"],
                }
            ),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        flush=True,
    )


def self_test() -> None:
    qty, post, turnover = target_quantity(
        1.0,
        0.0,
        1,
        10.0,
        FEE + BASE_SLIPPAGE,
    )
    assert post < 1.0 and turnover > 0.0
    assert math.isclose(
        qty * 10.0 / post,
        1.0,
        rel_tol=0.0,
        abs_tol=1e-12,
    )
    assert route_target(1, "combined", -1) == 1
    assert route_target(-1, "long_only", 1) == 0
    assert route_target(-1, "short_only", 0) == -1
    assert route_target(0, "combined", 1) == 1
    print("self-test: PASS")


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return
    adapter = load_module(
        SOURCE_ADAPTER,
        SOURCE_ADAPTER_SHA256,
        "hype_4h_ma7_cr_adapter",
    )
    base = adapter.load_module(
        adapter.BASE_PATH,
        adapter.BASE_SHA256,
        "hype_4h_ma7_cr_base",
    )
    parent_digest = hashlib.sha256(base.PARENT_SCRIPT.read_bytes()).hexdigest()
    if parent_digest != PARENT_LOADER_SHA256:
        raise RuntimeError(
            "parent data loader drift: "
            f"expected {PARENT_LOADER_SHA256}, got {parent_digest}"
        )
    parent = base.load_parent()
    data_engine = parent.load_engine()
    hourly, hourly_quality = data_engine.audit_and_load_market(ROOT, "1h")
    funding, funding_quality = data_engine.load_and_audit_funding(ROOT)
    bundles = {
        phase: build_bundle(
            adapter,
            hourly,
            hourly_quality,
            funding,
            funding_quality,
            phase_hours=phase,
        )
        for phase in PHASES
    }
    write_outputs(run_date=args.run_date, bundles=bundles)


if __name__ == "__main__":
    main()
