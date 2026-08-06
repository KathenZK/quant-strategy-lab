from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
PARENT_SCRIPT = (
    ROOT
    / "research/hype/1d-pyramiding-trend/scripts/"
    "research_hype_1d_pyramiding_trend.py"
)

FAMILY = "HYPE-1D-MA7-Asymmetric-Body-Trend"
ALIAS = "HYPE-1D-MA7-ABT"
FEE = 0.001
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
PRIMARY_MA_WINDOW = 7
RECENT_WINDOWS = {
    "1d": 1,
    "7d": 7,
    "1m": 30,
    "3m": 90,
    "6m": 182,
    "1y": 365,
}
EXIT_VARIANTS = (
    "literal_not_intersect",
    "directional_body_above",
    "symmetric_close_above",
)


@dataclass(slots=True)
class Book:
    ts: pd.DatetimeIndex
    terminal_ts: pd.Timestamp
    open: np.ndarray
    short_entry_open: np.ndarray
    post_short_entry_high: np.ndarray
    post_short_entry_low: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    funding_by_open: np.ndarray
    quality: dict[str, Any]
    funding_quality: dict[str, Any]

    @property
    def count(self) -> int:
        return len(self.open)


@dataclass(slots=True)
class Result:
    metrics: dict[str, Any]
    trades: list[dict[str, Any]]
    path: list[dict[str, Any]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"Research {FAMILY}.")
    parser.add_argument(
        "--run-date",
        default=datetime.now(UTC).date().isoformat(),
    )
    parser.add_argument("--bootstrap-samples", type=int, default=2_000)
    parser.add_argument("--seed", type=int, default=20260804)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def load_parent() -> Any:
    spec = importlib.util.spec_from_file_location("hype_1d_ma7_abt_parent", PARENT_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import parent data loader: {PARENT_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_book(
    parent: Any,
    hourly: pd.DataFrame,
    hourly_quality: dict[str, Any],
    funding: pd.DataFrame,
    funding_quality: dict[str, Any],
    *,
    phase_hours: int,
) -> Book:
    shifted = hourly.copy()
    shifted["ts"] = pd.to_datetime(shifted["ts"], utc=True) - pd.Timedelta(
        hours=phase_hours
    )
    daily, daily_quality = parent.aggregate_complete_daily(shifted)
    daily["ts"] = pd.to_datetime(daily["ts"], utc=True) + pd.Timedelta(
        hours=phase_hours
    )
    terminal_ts = pd.Timestamp(daily["ts"].iloc[-1]) + pd.Timedelta(days=1)
    terminal = hourly.loc[
        pd.to_datetime(hourly["ts"], utc=True).eq(terminal_ts)
    ]
    if len(terminal) != 1:
        raise RuntimeError(
            f"phase {phase_hours}: expected one terminal open at {terminal_ts}, "
            f"got {len(terminal)}"
        )
    timestamps = pd.DatetimeIndex([*daily["ts"], terminal_ts])
    hourly_indexed = hourly.copy()
    hourly_indexed["ts"] = pd.to_datetime(hourly_indexed["ts"], utc=True)
    hourly_indexed = hourly_indexed.set_index("ts").sort_index()
    short_entry_open: list[float] = []
    post_short_entry_high: list[float] = []
    post_short_entry_low: list[float] = []
    for day_start in pd.DatetimeIndex(daily["ts"]):
        entry_ts = day_start + pd.Timedelta(hours=1)
        day_end = day_start + pd.Timedelta(days=1)
        post_entry = hourly_indexed.loc[
            (hourly_indexed.index >= entry_ts)
            & (hourly_indexed.index < day_end)
        ]
        if len(post_entry) != 23 or entry_ts not in post_entry.index:
            raise RuntimeError(
                f"phase {phase_hours}: expected 23 post-entry hourly bars "
                f"from {entry_ts}, got {len(post_entry)}"
            )
        short_entry_open.append(float(post_entry.loc[entry_ts, "open"]))
        post_short_entry_high.append(float(post_entry["high"].max()))
        post_short_entry_low.append(float(post_entry["low"].min()))
    quality = {
        "exchange": "Binance",
        "market": "USD-M perpetual",
        "symbol": "HYPEUSDT",
        "source_timeframe": "1h",
        "strategy_timeframe": "1d",
        "phase_hours": phase_hours,
        "hourly": hourly_quality,
        "daily": daily_quality,
        "terminal_open_ts": terminal_ts.isoformat(),
        "terminal_open": float(terminal["open"].iloc[0]),
        "short_entry_execution": (
            "observe daily open trigger; execute at next 1h open"
        ),
    }
    return Book(
        ts=pd.DatetimeIndex(daily["ts"]),
        terminal_ts=terminal_ts,
        open=daily["open"].to_numpy("float64"),
        short_entry_open=np.asarray(short_entry_open, dtype="float64"),
        post_short_entry_high=np.asarray(post_short_entry_high, dtype="float64"),
        post_short_entry_low=np.asarray(post_short_entry_low, dtype="float64"),
        high=daily["high"].to_numpy("float64"),
        low=daily["low"].to_numpy("float64"),
        close=daily["close"].to_numpy("float64"),
        funding_by_open=parent._funding_by_open(timestamps, funding),
        quality=quality,
        funding_quality=funding_quality,
    )


def load_books() -> dict[int, Book]:
    parent = load_parent()
    engine = parent.load_engine()
    hourly, hourly_quality = engine.audit_and_load_market(ROOT, "1h")
    funding, funding_quality = engine.load_and_audit_funding(ROOT)
    return {
        phase: build_book(
            parent,
            hourly,
            hourly_quality,
            funding,
            funding_quality,
            phase_hours=phase,
        )
        for phase in (0, 12)
    }


def sma(values: np.ndarray, window: int) -> np.ndarray:
    return (
        pd.Series(values)
        .rolling(window, min_periods=window)
        .mean()
        .to_numpy("float64")
    )


def short_exit_signal(
    *,
    variant: str,
    day_open: float,
    day_close: float,
    current_ma: float,
) -> bool:
    if not np.isfinite(current_ma):
        return False
    body_low = min(day_open, day_close)
    body_high = max(day_open, day_close)
    if variant == "literal_not_intersect":
        return not (body_low <= current_ma <= body_high)
    if variant == "directional_body_above":
        return body_low > current_ma
    if variant == "symmetric_close_above":
        return day_close > current_ma
    raise ValueError(f"unknown short exit variant: {variant}")


def _target_quantity(
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


def _annualized(equity: float, days: float) -> float:
    if equity <= 0.0:
        return 0.0
    if days < 30.0:
        return math.nan
    return float(equity ** (365.25 / days))


def backtest(
    book: Book,
    *,
    variant: str,
    ma_window: int = PRIMARY_MA_WINDOW,
    direction: str = "both",
    start_index: int = 0,
    terminal_index: int | None = None,
    slippage: float = BASE_SLIPPAGE,
    signal_lag: int = 0,
    include_funding: bool = True,
    retain: bool = False,
) -> Result:
    if variant not in EXIT_VARIANTS:
        raise ValueError(f"unknown variant: {variant}")
    if direction not in {"both", "long_only", "short_only"}:
        raise ValueError(f"unknown direction: {direction}")
    terminal_index = book.count if terminal_index is None else terminal_index
    if not (0 <= start_index < terminal_index <= book.count):
        raise ValueError("invalid backtest window")
    if signal_lag not in {0, 1}:
        raise ValueError("signal_lag must be 0 or 1")

    moving_average = sma(book.close, ma_window)
    timestamps = pd.DatetimeIndex([*book.ts, book.terminal_ts])
    opens = np.r_[book.open, float(book.quality["terminal_open"])]
    cost_rate = FEE + slippage
    equity = 1.0
    qty = 0.0
    side = 0
    mark_price = float(opens[start_index])
    peak = 1.0
    max_drawdown = 0.0
    max_intraday_leverage = 0.0
    total_turnover = 0.0
    total_cost = 0.0
    total_funding = 0.0
    exposure_days = 0
    entry_ts: pd.Timestamp | None = None
    entry_price = math.nan
    entry_equity = math.nan
    entry_cost = math.nan
    entry_side = 0
    entry_index = -1
    trades: list[dict[str, Any]] = []
    path: list[dict[str, Any]] = []
    bankrupt = False

    def trade_to(target_side: int, price: float) -> float:
        nonlocal equity, qty, side, total_turnover, total_cost
        old_equity = equity
        qty, equity, turnover = _target_quantity(
            equity, qty, target_side, price, cost_rate
        )
        total_turnover += turnover
        total_cost += old_equity - equity
        side = target_side
        return turnover

    def close_trade(ts: pd.Timestamp, price: float, reason: str, index: int) -> None:
        nonlocal entry_ts, entry_price, entry_equity, entry_cost
        nonlocal entry_side, entry_index
        if entry_ts is None:
            raise RuntimeError("cannot close an absent trade")
        trade_to(0, price)
        trades.append(
            {
                "entry_ts": entry_ts.isoformat(),
                "exit_ts": ts.isoformat(),
                "side": "long" if entry_side > 0 else "short",
                "entry_price": entry_price,
                "exit_price": price,
                "bars_held": index - entry_index,
                "exit_reason": reason,
                "net_return": equity / entry_equity - 1.0,
                "entry_cost": entry_cost,
            }
        )
        entry_ts = None
        entry_price = entry_equity = entry_cost = math.nan
        entry_side = 0
        entry_index = -1

    def open_trade(
        new_side: int,
        ts: pd.Timestamp,
        price: float,
        index: int,
    ) -> None:
        nonlocal entry_ts, entry_price, entry_equity, entry_cost
        nonlocal entry_side, entry_index
        before = equity
        trade_to(new_side, price)
        entry_ts = ts
        entry_price = price
        entry_equity = before
        entry_cost = before - equity
        entry_side = new_side
        entry_index = index

    for index in range(start_index, terminal_index + 1):
        ts = pd.Timestamp(timestamps[index])
        current_open = float(opens[index])
        if index > start_index and qty != 0.0:
            equity += qty * (current_open - mark_price)
            if include_funding:
                funding_payment = qty * current_open * book.funding_by_open[index]
                equity -= funding_payment
                total_funding += funding_payment
        mark_price = current_open
        if equity <= 0.0:
            bankrupt = True
            equity = 0.0
            max_drawdown = -1.0
            break

        pre_action_equity = equity
        action = "hold"
        entered_short_after_open = False
        if index < terminal_index:
            decision_index = index - signal_lag
            if decision_index >= 1:
                prior_index = decision_index - 1
                prior_ma = moving_average[prior_index]
                prior_close = book.close[prior_index]
                exit_short = short_exit_signal(
                    variant=variant,
                    day_open=book.open[prior_index],
                    day_close=book.close[prior_index],
                    current_ma=moving_average[prior_index],
                )
                exited = False
                if side > 0 and np.isfinite(prior_ma) and prior_close < prior_ma:
                    close_trade(ts, current_open, "prior_close_below_ma7", index)
                    action = "exit_long"
                    exited = True
                elif side < 0 and exit_short:
                    close_trade(ts, current_open, f"short_exit_{variant}", index)
                    action = "exit_short"
                    exited = True

                if side == 0 and np.isfinite(prior_ma):
                    desired = 0
                    if direction != "short_only" and prior_close > prior_ma:
                        desired = 1
                    elif (
                        direction != "long_only"
                        and book.open[decision_index] < prior_ma
                    ):
                        desired = -1
                    if desired:
                        fill_price = current_open
                        fill_ts = ts
                        if desired < 0 and signal_lag == 0:
                            fill_price = float(book.short_entry_open[index])
                            fill_ts = ts + pd.Timedelta(hours=1)
                            entered_short_after_open = True
                        open_trade(desired, fill_ts, fill_price, index)
                        if desired < 0 and signal_lag == 0:
                            mark_price = fill_price
                        if exited:
                            action += "_then_long" if desired > 0 else "_then_short"
                        else:
                            action = "enter_long" if desired > 0 else "enter_short"

        post_action_equity = equity
        peak = max(peak, pre_action_equity, post_action_equity)
        max_drawdown = min(
            max_drawdown,
            post_action_equity / peak - 1.0,
        )
        if side != 0 and post_action_equity > 0.0:
            position_mark = mark_price if entered_short_after_open else current_open
            max_intraday_leverage = max(
                max_intraday_leverage,
                abs(qty) * position_mark / post_action_equity,
            )

        if index < terminal_index:
            if side != 0:
                exposure_days += 1
                if entered_short_after_open:
                    day_high = book.post_short_entry_high[index]
                    day_low = book.post_short_entry_low[index]
                    position_mark = mark_price
                else:
                    day_high = book.high[index]
                    day_low = book.low[index]
                    position_mark = current_open
                favorable = day_high if side > 0 else day_low
                adverse = day_low if side > 0 else day_high
                favorable_equity = equity + qty * (favorable - position_mark)
                adverse_equity = equity + qty * (adverse - position_mark)
                peak = max(peak, favorable_equity)
                max_drawdown = min(max_drawdown, adverse_equity / peak - 1.0)
                if adverse_equity <= 0.0:
                    bankrupt = True
                    equity = 0.0
                    qty = 0.0
                    side = 0
                    close_equity = 0.0
                    if retain:
                        path.append(
                            {
                                "ts": ts.isoformat(),
                                "pre_action_equity": pre_action_equity,
                                "post_action_equity": post_action_equity,
                                "close_equity": close_equity,
                                "favorable_equity": favorable_equity,
                                "adverse_equity": adverse_equity,
                                "position": entry_side,
                                "action": "intraday_bankruptcy",
                                "ma7": moving_average[index],
                                "open": current_open,
                                "close": float(book.close[index]),
                                "max_drawdown_conservative": -1.0,
                            }
                        )
                    break
                close_equity = equity + qty * (
                    float(book.close[index]) - position_mark
                )
            else:
                close_equity = equity
            peak = max(peak, close_equity)
            max_drawdown = min(max_drawdown, close_equity / peak - 1.0)
            if retain:
                path.append(
                    {
                        "ts": ts.isoformat(),
                        "pre_action_equity": pre_action_equity,
                        "post_action_equity": post_action_equity,
                        "close_equity": close_equity,
                        "favorable_equity": (
                            favorable_equity if side != 0 else close_equity
                        ),
                        "adverse_equity": (
                            adverse_equity if side != 0 else close_equity
                        ),
                        "position": side,
                        "action": action,
                        "ma7": moving_average[index],
                        "open": current_open,
                        "close": float(book.close[index]),
                        "max_drawdown_conservative": max_drawdown,
                    }
                )
        elif retain:
            path.append(
                {
                    "ts": ts.isoformat(),
                    "pre_action_equity": pre_action_equity,
                    "post_action_equity": equity,
                    "close_equity": equity,
                    "favorable_equity": equity,
                    "adverse_equity": equity,
                    "position": side,
                    "action": "terminal",
                    "ma7": math.nan,
                    "open": current_open,
                    "close": current_open,
                    "max_drawdown_conservative": max_drawdown,
                }
            )

    if qty != 0.0 and equity > 0.0:
        close_trade(
            pd.Timestamp(timestamps[min(terminal_index, len(timestamps) - 1)]),
            float(opens[min(terminal_index, len(opens) - 1)]),
            "terminal_flatten",
            terminal_index,
        )
        if retain and path and path[-1]["action"] == "terminal":
            path[-1]["post_action_equity"] = equity
            path[-1]["close_equity"] = equity
            path[-1]["favorable_equity"] = equity
            path[-1]["adverse_equity"] = equity
            path[-1]["position"] = 0
            path[-1]["action"] = "terminal_flatten"
    peak = max(peak, equity)
    max_drawdown = min(max_drawdown, equity / peak - 1.0)
    days = max(
        1.0,
        (
            timestamps[terminal_index] - timestamps[start_index]
        ).total_seconds()
        / 86_400.0,
    )
    returns = np.array([float(row["net_return"]) for row in trades])
    gross_profit = float(returns[returns > 0.0].sum()) if len(returns) else 0.0
    gross_loss = float(-returns[returns < 0.0].sum()) if len(returns) else 0.0
    daily_equity = pd.Series(
        [1.0, *[float(row["close_equity"]) for row in path]], dtype=float
    )
    daily_returns = (
        daily_equity.pct_change()
        .replace([np.inf, -np.inf], np.nan)
        .dropna()
    )
    sharpe = (
        float(np.sqrt(365.25) * daily_returns.mean() / daily_returns.std(ddof=1))
        if len(daily_returns) >= 3 and daily_returns.std(ddof=1) > 0.0
        else math.nan
    )
    metrics = {
        "variant": variant,
        "direction": direction,
        "ma_window": ma_window,
        "phase_hours": int(book.quality["phase_hours"]),
        "signal_lag_bars": signal_lag,
        "slippage_per_fill": slippage,
        "funding_included": include_funding,
        "start_ts": pd.Timestamp(timestamps[start_index]).isoformat(),
        "end_ts": pd.Timestamp(timestamps[terminal_index]).isoformat(),
        "days": days,
        "equity_multiple": equity,
        "net_return_pct": (equity - 1.0) * 100.0,
        "annualized_factor": _annualized(equity, days),
        "cagr_pct": (_annualized(equity, days) - 1.0) * 100.0,
        "max_drawdown_pct": max_drawdown * 100.0,
        "sharpe": sharpe,
        "closed_trades": len(trades),
        "long_trades": sum(row["side"] == "long" for row in trades),
        "short_trades": sum(row["side"] == "short" for row in trades),
        "win_rate": float((returns > 0.0).mean()) if len(returns) else math.nan,
        "profit_factor": (
            gross_profit / gross_loss
            if gross_loss > 0.0
            else (math.inf if gross_profit > 0.0 else math.nan)
        ),
        "average_trade_return_pct": (
            float(returns.mean() * 100.0) if len(returns) else math.nan
        ),
        "exposure_pct": exposure_days / days * 100.0,
        "total_turnover_multiple": total_turnover,
        "cost_pct_initial": total_cost * 100.0,
        "funding_pct_initial": total_funding * 100.0,
        "max_intraday_leverage": max_intraday_leverage,
        "bankrupt_intraday": bankrupt,
    }
    return Result(metrics=metrics, trades=trades, path=path)


def buy_and_hold(
    book: Book,
    *,
    start_index: int,
    terminal_index: int,
    slippage: float = BASE_SLIPPAGE,
) -> dict[str, Any]:
    entry = float(book.open[start_index])
    exit_price = float(
        np.r_[book.open, float(book.quality["terminal_open"])][terminal_index]
    )
    entry_equity = 1.0
    entry_cost_rate = FEE + slippage
    post_entry = entry_equity / (1.0 + entry_cost_rate)
    qty = post_entry / entry
    equity = post_entry + qty * (exit_price - entry)
    funding = 0.0
    for index in range(start_index + 1, terminal_index + 1):
        payment = qty * float(
            np.r_[book.open, float(book.quality["terminal_open"])][index]
        ) * book.funding_by_open[index]
        equity -= payment
        funding += payment
    exit_notional = qty * exit_price
    equity -= exit_notional * entry_cost_rate
    days = max(
        1.0,
        (pd.Timestamp([*book.ts, book.terminal_ts][terminal_index]) - book.ts[start_index])
        .total_seconds()
        / 86_400.0,
    )
    return {
        "start_ts": book.ts[start_index].isoformat(),
        "end_ts": pd.Timestamp([*book.ts, book.terminal_ts][terminal_index]).isoformat(),
        "equity_multiple": equity,
        "net_return_pct": (equity - 1.0) * 100.0,
        "annualized_factor": _annualized(equity, days),
        "funding_pct_initial": funding * 100.0,
    }


def _path_window_drawdown(path: pd.DataFrame, initial_equity: float) -> float:
    peak = initial_equity
    drawdown = 0.0
    for row in path.itertuples(index=False):
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
        peak = max(peak, float(row.close_equity))
    return drawdown


def window_rows(
    book: Book,
    variant: str,
    full_result: Result,
) -> list[dict[str, Any]]:
    path = pd.DataFrame(full_result.path)
    path["ts"] = pd.to_datetime(path["ts"], utc=True)
    trades = pd.DataFrame(full_result.trades)
    if not trades.empty:
        trades["exit_ts"] = pd.to_datetime(trades["exit_ts"], utc=True)
    rows: list[dict[str, Any]] = []
    end_ts = book.terminal_ts
    for label, days in RECENT_WINDOWS.items():
        start_ts = end_ts - pd.Timedelta(days=days)
        part = path.loc[
            path["ts"].ge(start_ts) & path["ts"].le(end_ts)
        ].copy()
        if part.empty:
            continue
        initial_equity = float(part.iloc[0]["pre_action_equity"])
        final_equity = float(part.iloc[-1]["close_equity"])
        closed = (
            trades.loc[
                trades["exit_ts"].ge(start_ts)
                & trades["exit_ts"].le(end_ts)
            ]
            if not trades.empty
            else trades
        )
        rows.append(
            {
                "window": label,
                "variant": variant,
                "start_ts": part.iloc[0]["ts"].isoformat(),
                "end_ts": part.iloc[-1]["ts"].isoformat(),
                "days": days,
                "return_pct": (final_equity / initial_equity - 1.0) * 100.0,
                "path_mdd_pct": _path_window_drawdown(
                    part, initial_equity
                )
                * 100.0,
                "closed_trades": int(len(closed)),
                "long_trades": (
                    int(closed["side"].eq("long").sum())
                    if not closed.empty
                    else 0
                ),
                "short_trades": (
                    int(closed["side"].eq("short").sum())
                    if not closed.empty
                    else 0
                ),
                "exposure_pct": float(
                    part.loc[part["ts"].lt(end_ts), "position"]
                    .ne(0)
                    .mean()
                    * 100.0
                ),
                "slice_semantics": "continuous_full_path",
            }
        )
    return rows


def rolling_rows(
    book: Book,
    variant: str,
    *,
    window_days: int = 90,
    step_days: int = 30,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    while start + window_days <= book.count:
        result = backtest(
            book,
            variant=variant,
            start_index=start,
            terminal_index=start + window_days,
            retain=True,
        )
        rows.append(result.metrics)
        start += step_days
    return rows


def bootstrap_trades(
    trades: list[dict[str, Any]],
    *,
    samples: int,
    seed: int,
) -> dict[str, Any]:
    values = np.array([float(row["net_return"]) for row in trades], dtype=float)
    if len(values) < 2:
        return {"samples": samples, "trade_count": len(values), "status": "insufficient"}
    rng = np.random.default_rng(seed)
    ending = np.empty(samples)
    max_drawdown = np.empty(samples)
    for sample in range(samples):
        draw = rng.choice(values, size=len(values), replace=True)
        path = np.r_[1.0, np.cumprod(1.0 + draw)]
        ending[sample] = path[-1]
        max_drawdown[sample] = np.min(path / np.maximum.accumulate(path) - 1.0)
    return {
        "samples": samples,
        "trade_count": len(values),
        "equity_multiple_p05": float(np.quantile(ending, 0.05)),
        "equity_multiple_median": float(np.quantile(ending, 0.50)),
        "equity_multiple_p95": float(np.quantile(ending, 0.95)),
        "max_drawdown_pct_p05": float(np.quantile(max_drawdown, 0.05) * 100.0),
        "max_drawdown_pct_median": float(
            np.quantile(max_drawdown, 0.50) * 100.0
        ),
        "probability_profitable": float(np.mean(ending > 1.0)),
    }


def write_outputs(
    *,
    run_date: str,
    seed: int,
    bootstrap_samples: int,
    books: dict[int, Book],
) -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    primary_book = books[0]
    baseline_results = {
        variant: backtest(
            primary_book,
            variant=variant,
            retain=True,
        )
        for variant in EXIT_VARIANTS
    }
    metrics_rows = [
        result.metrics for result in baseline_results.values()
    ]
    for variant in EXIT_VARIANTS:
        for direction in ("long_only", "short_only"):
            metrics_rows.append(
                backtest(
                    primary_book,
                    variant=variant,
                    direction=direction,
                    retain=True,
                ).metrics
            )

    primary_result = baseline_results["literal_not_intersect"]
    benchmark = buy_and_hold(
        primary_book,
        start_index=0,
        terminal_index=primary_book.count,
    )
    recent = [
        row
        for variant in EXIT_VARIANTS
        for row in window_rows(
            primary_book,
            variant,
            baseline_results[variant],
        )
    ]
    rolling = [
        row
        for variant in EXIT_VARIANTS
        for row in rolling_rows(primary_book, variant)
    ]
    parameter_rows = [
        backtest(
            primary_book,
            variant=variant,
            ma_window=window,
            retain=True,
        ).metrics
        for variant in ("literal_not_intersect", "directional_body_above")
        for window in range(5, 11)
    ]
    stress_rows = []
    for variant in EXIT_VARIANTS:
        for label, kwargs in (
            ("base", {}),
            ("slippage_8bps", {"slippage": STRESS_SLIPPAGE}),
            ("one_bar_extra_delay", {"signal_lag": 1}),
            ("funding_zero", {"include_funding": False}),
        ):
            stress_rows.append(
                {
                    "stress": label,
                    **backtest(
                        primary_book,
                        variant=variant,
                        retain=True,
                        **kwargs,
                    ).metrics,
                }
            )
    common_phase_start = max(book.ts[0] for book in books.values())
    common_phase_end = min(book.terminal_ts for book in books.values())
    phase_rows = []
    for _, book in sorted(books.items()):
        phase_start = int(book.ts.searchsorted(common_phase_start, side="left"))
        phase_timestamps = pd.DatetimeIndex([*book.ts, book.terminal_ts])
        phase_end = int(
            phase_timestamps.searchsorted(common_phase_end, side="right") - 1
        )
        for variant in EXIT_VARIANTS:
            phase_rows.append(
                {
                    "phase_common_overlap_start": common_phase_start.isoformat(),
                    "phase_common_overlap_end": common_phase_end.isoformat(),
                    **backtest(
                        book,
                        variant=variant,
                        start_index=phase_start,
                        terminal_index=phase_end,
                        retain=True,
                    ).metrics,
                }
            )
    holdout_start = max(0, primary_book.count - 90)
    chronological = []
    for variant in EXIT_VARIANTS:
        for label, start, end in (
            ("prefit", 0, holdout_start),
            ("researcher_exposed_last_90d_flat", holdout_start, primary_book.count),
            ("full", 0, primary_book.count),
        ):
            if end > start:
                chronological.append(
                    {
                        "window": label,
                        **backtest(
                            primary_book,
                            variant=variant,
                            start_index=start,
                            terminal_index=end,
                            retain=True,
                        ).metrics,
                    }
                )
    bootstrap = {
        variant: bootstrap_trades(
            result.trades,
            samples=bootstrap_samples,
            seed=seed + index,
        )
        for index, (variant, result) in enumerate(baseline_results.items())
    }

    pd.DataFrame(metrics_rows).to_csv(
        ARTIFACT_DIR / f"hype_1d_ma7_abt_metrics_{run_date}.csv",
        index=False,
    )
    pd.DataFrame(recent).to_csv(
        ARTIFACT_DIR / f"hype_1d_ma7_abt_recent_slices_{run_date}.csv",
        index=False,
    )
    pd.DataFrame(rolling).to_csv(
        ARTIFACT_DIR / f"hype_1d_ma7_abt_rolling_90d_{run_date}.csv",
        index=False,
    )
    pd.DataFrame(parameter_rows).to_csv(
        ARTIFACT_DIR / f"hype_1d_ma7_abt_ma_neighborhood_{run_date}.csv",
        index=False,
    )
    pd.DataFrame(stress_rows).to_csv(
        ARTIFACT_DIR / f"hype_1d_ma7_abt_execution_stress_{run_date}.csv",
        index=False,
    )
    pd.DataFrame(phase_rows).to_csv(
        ARTIFACT_DIR / f"hype_1d_ma7_abt_phase_audit_{run_date}.csv",
        index=False,
    )
    pd.DataFrame(chronological).to_csv(
        ARTIFACT_DIR / f"hype_1d_ma7_abt_chronological_{run_date}.csv",
        index=False,
    )
    pd.DataFrame(primary_result.trades).to_csv(
        ARTIFACT_DIR / f"hype_1d_ma7_abt_literal_trades_{run_date}.csv",
        index=False,
    )
    pd.DataFrame(primary_result.path).to_csv(
        ARTIFACT_DIR / f"hype_1d_ma7_abt_literal_path_{run_date}.csv",
        index=False,
    )

    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": FAMILY,
        "alias": ALIAS,
        "status": "explore / not promoted / not live-ready",
        "run_date": run_date,
        "contract": {
            "ma_type": "SMA",
            "ma_window": PRIMARY_MA_WINDOW,
            "position_target": "1x equity at entry; fixed quantity between fills",
            "long_entry": "prior close > prior SMA7; current open fill",
            "long_exit": "prior close < prior SMA7; current open fill",
            "short_entry": (
                "flat after exit priority and current open < prior SMA7; "
                "execute at the next 1h open after observing daily open"
            ),
            "short_exit_variants": {
                "literal_not_intersect": (
                    "after close, prior-day SMA7 is outside inclusive candle body; "
                    "next open fill"
                ),
                "directional_body_above": (
                    "after close, entire candle body is above current SMA7; "
                    "next open fill"
                ),
                "symmetric_close_above": (
                    "after close, close > current SMA7; next open fill"
                ),
            },
            "priority": (
                "exit first; when flat, long signal has priority over short; "
                "literal same-side short re-entry exits at daily open and "
                "re-enters at the next 1h open"
            ),
            "fee_per_fill": FEE,
            "slippage_per_fill": BASE_SLIPPAGE,
            "funding": (
                "actual Binance funding rates; daily-open notional "
                "approximation within each interval"
            ),
            "daily_close_signals_closed_bar_only": True,
            "short_entry_uses_observed_daily_open_event": True,
            "historical_role": "researcher-exposed diagnostic; no clean prospective OOS",
        },
        "data_quality": {
            str(phase): book.quality for phase, book in books.items()
        },
        "funding_quality": primary_book.funding_quality,
        "baseline_metrics": metrics_rows,
        "buy_and_hold": benchmark,
        "literal_excess_return_pct": (
            primary_result.metrics["net_return_pct"] - benchmark["net_return_pct"]
        ),
        "trade_bootstrap": bootstrap,
        "chronological_windows": chronological,
        "promotion_gaps": [
            "user wording for short exit is materially ambiguous",
            "no protective stop or emergency risk rule",
            "history is short and researcher-exposed",
            "no clean prospective OOS",
            "no runner parity or online reconciliation",
        ],
    }
    summary_path = ARTIFACT_DIR / f"hype_1d_ma7_abt_summary_{run_date}.json"
    summary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "summary": str(summary_path.relative_to(ROOT)),
                "baseline_metrics": metrics_rows,
                "buy_and_hold": benchmark,
                "literal_excess_return_pct": payload["literal_excess_return_pct"],
                "trade_bootstrap": bootstrap,
            },
            ensure_ascii=False,
            indent=2,
            default=_json_default,
        )
    )
    return payload


def _json_default(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    raise TypeError(type(value).__name__)


def self_test() -> None:
    assert short_exit_signal(
        variant="literal_not_intersect",
        day_open=9.0,
        day_close=8.0,
        current_ma=10.0,
    )
    assert not short_exit_signal(
        variant="directional_body_above",
        day_open=9.0,
        day_close=8.0,
        current_ma=10.0,
    )
    assert short_exit_signal(
        variant="directional_body_above",
        day_open=11.0,
        day_close=12.0,
        current_ma=10.0,
    )
    qty, post, turnover = _target_quantity(1.0, 0.0, 1, 10.0, FEE + BASE_SLIPPAGE)
    assert qty > 0.0 and post < 1.0 and turnover > 0.0
    assert math.isclose(abs(qty) * 10.0 / post, 1.0, rel_tol=0.0, abs_tol=1e-12)
    print("self-test: PASS")


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return
    books = load_books()
    write_outputs(
        run_date=args.run_date,
        seed=args.seed,
        bootstrap_samples=args.bootstrap_samples,
        books=books,
    )


if __name__ == "__main__":
    main()
