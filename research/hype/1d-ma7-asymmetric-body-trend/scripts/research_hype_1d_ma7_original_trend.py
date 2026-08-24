from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
ENGINE_PATH = FAMILY_DIR / "scripts/hype_1d_ma7_original_trend_engine.py"
ENGINE_SHA256 = "4e2bcfda0dd693968687f3cff1ca845df892e88d0eb5c82029333e828274f403"
BASE_PATH = FAMILY_DIR / "scripts/research_hype_1d_ma7_asymmetric_body_trend.py"
BASE_SHA256 = "05d76943a671d1463f8950f1f6e317d8653831fd0f72ea825a039caa1fb2a386"
SEARCH_PATH = FAMILY_DIR / "scripts/search_hype_1d_ma7_separated_trend.py"
SEARCH_SHA256 = "c376f8bd1bae814b0ba53687380ee1060cf3cc3095ae815ebb0311ed1aef59e1"
CONTRACT_PATH = (
    FAMILY_DIR / "specs/hype-1d-ma7-original-trend-state-machine-contract-2026-08-09.md"
)

FAMILY = "HYPE-1D-MA7-Asymmetric-Body-Trend"
BRANCH = "original-trend-state-machine"
HOURLY_CUTOFF = pd.Timestamp("2026-08-06T07:00:00Z")
FUNDING_CUTOFF = pd.Timestamp("2026-08-06T08:00:00Z")
FEE = 0.001
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
PROTECTION_ATR = 1.5
RECENT_WINDOWS = {"1d": 1, "7d": 7, "1m": 30, "3m": 90, "6m": 182, "1y": 365}


@dataclass(slots=True)
class MarketData:
    book: Any
    features: Any
    daily: pd.DataFrame
    hourly: pd.DataFrame
    funding: pd.DataFrame
    audit: dict[str, Any]


@dataclass(slots=True)
class BacktestResult:
    metrics: dict[str, Any]
    trades: list[dict[str, Any]]
    path: list[dict[str, Any]]
    actions: list[dict[str, Any]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"Research {FAMILY} {BRANCH}.")
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--bootstrap-samples", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20260809)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_pinned(path: Path, expected: str, name: str) -> Any:
    actual = sha256(path)
    if actual != expected:
        raise RuntimeError(f"{path.name} drift: expected {expected}, got {actual}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def modules() -> tuple[Any, Any, Any]:
    engine = load_pinned(ENGINE_PATH, ENGINE_SHA256, "hype_ma7_original_engine")
    base = load_pinned(BASE_PATH, BASE_SHA256, "hype_ma7_original_base")
    search = load_pinned(SEARCH_PATH, SEARCH_SHA256, "hype_ma7_original_search")
    return engine, base, search


def canonical_hash(frame: pd.DataFrame, columns: list[str]) -> str:
    selected = frame.loc[:, columns].copy()
    for column in selected.columns:
        if pd.api.types.is_datetime64_any_dtype(selected[column]):
            selected[column] = pd.to_datetime(selected[column], utc=True).map(
                lambda value: value.isoformat()
            )
    payload = selected.to_csv(index=False, float_format="%.12g").encode()
    return hashlib.sha256(payload).hexdigest()


def load_market(phase_hour: int = 0) -> MarketData:
    engine, base, search = modules()
    parent = base.load_parent()
    market_engine = parent.load_engine()
    hourly, hourly_quality = market_engine.audit_and_load_market(ROOT, "1h")
    funding, funding_quality = market_engine.load_and_audit_funding(ROOT)
    hourly = hourly.copy()
    funding = funding.copy()
    hourly["ts"] = pd.to_datetime(hourly["ts"], utc=True)
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
    hourly = hourly.loc[hourly["ts"].le(HOURLY_CUTOFF)].sort_values("ts")
    funding = funding.loc[funding["ts"].le(FUNDING_CUTOFF)].sort_values("ts")
    if hourly.empty or funding.empty:
        raise RuntimeError("frozen market inputs are empty")
    if hourly["ts"].duplicated().any() or funding["ts"].duplicated().any():
        raise RuntimeError("frozen market inputs contain duplicate timestamps")
    if not hourly["ts"].diff().dropna().eq(pd.Timedelta(hours=1)).all():
        raise RuntimeError("frozen HYPE hourly data are not continuous")

    phase_hourly = hourly
    terminal_fallback = False
    try:
        book = base.build_book(
            parent,
            phase_hourly,
            hourly_quality,
            funding,
            funding_quality,
            phase_hours=phase_hour,
        )
    except RuntimeError as exc:
        if "expected one terminal open" not in str(exc):
            raise
        shifted_start = (phase_hourly["ts"] - pd.Timedelta(hours=phase_hour)).dt.floor(
            "D"
        ) + pd.Timedelta(hours=phase_hour)
        counts = shifted_start.value_counts()
        available_opens = set(phase_hourly["ts"])
        candidates = sorted(
            start
            for start, count in counts.items()
            if count == 24 and start + pd.Timedelta(days=1) in available_opens
        )
        if not candidates:
            raise RuntimeError(
                f"phase {phase_hour}: no complete executable session"
            ) from exc
        fallback_terminal = candidates[-1] + pd.Timedelta(days=1)
        phase_hourly = phase_hourly.loc[phase_hourly["ts"].le(fallback_terminal)].copy()
        book = base.build_book(
            parent,
            phase_hourly,
            hourly_quality,
            funding,
            funding_quality,
            phase_hours=phase_hour,
        )
        terminal_fallback = True
    features = search.build_features(book, phase_hourly, funding)
    daily = pd.DataFrame(
        {
            "open": book.open,
            "high": book.high,
            "low": book.low,
            "close": book.close,
        },
        index=pd.DatetimeIndex(book.ts),
    )
    daily = engine.add_daily_indicators(
        daily,
        ma_period=7,
        atr_period=7,
        rsi_period=6,
        slope_lookback=1,
        expected_phase_hour=phase_hour,
    )
    audit = {
        "phase_hour": phase_hour,
        "hourly_start": hourly["ts"].iloc[0].isoformat(),
        "hourly_end": hourly["ts"].iloc[-1].isoformat(),
        "hourly_rows": int(len(hourly)),
        "funding_start": funding["ts"].iloc[0].isoformat(),
        "funding_end": funding["ts"].iloc[-1].isoformat(),
        "funding_rows": int(len(funding)),
        "daily_start": pd.Timestamp(book.ts[0]).isoformat(),
        "daily_end": pd.Timestamp(book.ts[-1]).isoformat(),
        "daily_rows": int(book.count),
        "terminal_open": pd.Timestamp(book.terminal_ts).isoformat(),
        "terminal_fallback": terminal_fallback,
        "phase_input_hourly_end": phase_hourly["ts"].iloc[-1].isoformat(),
        "phase_input_hourly_rows": int(len(phase_hourly)),
        "hourly_sha256": canonical_hash(
            hourly,
            ["ts", "open", "high", "low", "close", "volume"],
        ),
        "phase_input_hourly_sha256": canonical_hash(
            phase_hourly,
            ["ts", "open", "high", "low", "close", "volume"],
        ),
        "funding_sha256": canonical_hash(funding, ["ts", "funding_rate"]),
        "trusted_hourly_audit": hourly_quality,
        "trusted_funding_audit": funding_quality,
    }
    return MarketData(book, features, daily, phase_hourly, funding, audit)


def frozen_configs(engine: Any, *, phase_hour: int = 0) -> dict[str, Any]:
    common = {
        "prior_side_days": 1,
        "session_open_hour": phase_hour,
        "tolerance_atr": 0.75,
        "slope_min_atr": 0.0,
        "entry_requires_slope": False,
        "band_requires_slope": True,
        "slope_loss_action": engine.SlopeLossAction.FLAT,
        "arm_cross_while_held": True,
        "arm_expiry_days": None,
        "flat_cross_waits_for_confirmation": False,
        "short_rsi_exit_threshold": 30.0,
        "short_rsi_exit_days": 3,
        "short_rsi_exit_requires_profit": True,
        "overbought_threshold": 70.0,
        "overbought_days": 3,
        "overbought_requires_short_slope": True,
        "strict_previous_side": True,
    }
    return {
        "A_CORE": engine.StrategyConfig(
            **common,
            short_rsi_exit_enabled=False,
            overbought_mode=engine.OverboughtMode.DISABLED,
        ),
        "B_SHORT_RSI_EXIT": engine.StrategyConfig(
            **common,
            short_rsi_exit_enabled=True,
            overbought_mode=engine.OverboughtMode.DISABLED,
        ),
        "C_OVERBOUGHT_REVERSAL": engine.StrategyConfig(
            **common,
            short_rsi_exit_enabled=False,
            overbought_mode=engine.OverboughtMode.EARLY_REVERSAL,
        ),
        "D_BOTH_RSI": engine.StrategyConfig(
            **common,
            short_rsi_exit_enabled=True,
            overbought_mode=engine.OverboughtMode.EARLY_REVERSAL,
        ),
    }


def _target_quantity(
    equity: float,
    old_qty: float,
    target_side: int,
    price: float,
    cost_rate: float,
) -> tuple[float, float, float, float]:
    post_equity = equity
    target_qty = old_qty
    turnover = 0.0
    for _ in range(30):
        target_qty = target_side * post_equity / price
        turnover = abs(target_qty - old_qty) * price
        updated = equity - turnover * cost_rate
        if math.isclose(updated, post_equity, rel_tol=0.0, abs_tol=1e-14):
            post_equity = updated
            break
        post_equity = updated
    return target_qty, post_equity, turnover, equity - post_equity


def _annualized(equity: float, days: float) -> float:
    if equity <= 0.0:
        return 0.0
    return equity ** (365.25 / days) if days >= 30.0 else math.nan


def _observation(
    engine: Any, data: MarketData, index: int, *, prime: bool = False
) -> Any:
    row = data.daily.iloc[index]
    slope = float(row["slope_atr"])
    if prime and not np.isfinite(slope):
        slope = 0.0
    return engine.CloseObservation(
        ts=pd.Timestamp(data.daily.index[index]),
        close=float(row["close"]),
        ma7=float(row["ma7"]),
        atr7=float(row["atr7"]),
        slope_atr=slope,
        rsi6=float(row["rsi6"]),
    )


def _first_valid_index(data: MarketData) -> int:
    columns = ["ma7", "atr7", "rsi6", "slope_atr"]
    valid = np.isfinite(data.daily[columns].to_numpy()).all(axis=1)
    indices = np.flatnonzero(valid)
    if not len(indices):
        raise RuntimeError("no complete indicator row")
    return int(indices[0])


def backtest(
    engine: Any,
    data: MarketData,
    config: Any,
    *,
    label: str,
    start_index: int = 0,
    terminal_index: int | None = None,
    slippage: float = BASE_SLIPPAGE,
    extra_delay_days: int = 0,
    hard_stop_atr: float = 0.0,
    retain: bool = False,
) -> BacktestResult:
    book = data.book
    terminal_index = book.count if terminal_index is None else terminal_index
    if not (0 <= start_index < terminal_index <= book.count):
        raise ValueError("invalid backtest window")
    if extra_delay_days not in {0, 1}:
        raise ValueError("extra_delay_days must be 0 or 1")
    if hard_stop_atr < 0.0:
        raise ValueError("hard_stop_atr must be non-negative")

    machine = engine.OriginalTrendMachine(config)
    first_valid = _first_valid_index(data)
    active_start = max(start_index, first_valid)
    history_days = max(
        config.prior_side_days,
        config.short_rsi_exit_days,
        config.overbought_days,
    )
    prime_rows: list[Any] = []
    for index in range(max(0, active_start - history_days), active_start):
        row = data.daily.iloc[index]
        if np.isfinite(row[["ma7", "atr7", "rsi6"]].to_numpy()).all():
            prime_rows.append(_observation(engine, data, index, prime=True))
    if prime_rows:
        consecutive: list[Any] = [prime_rows[-1]]
        for value in reversed(prime_rows[:-1]):
            if value.ts + pd.Timedelta(days=1) != consecutive[0].ts:
                break
            consecutive.insert(0, value)
        machine.prime_history(consecutive)

    cost_rate = FEE + slippage
    equity = 1.0
    qty = 0.0
    side = engine.Side.FLAT
    mark_price = float(book.open[start_index])
    peak = 1.0
    max_drawdown = 0.0
    max_effective_leverage = 0.0
    turnover_total = 0.0
    cost_total = 0.0
    funding_total = 0.0
    exposure_hours = 0
    bankrupt = False
    pending_due_index: int | None = None
    stop_count = 0
    equity_points: list[float] = [1.0]
    trades: list[dict[str, Any]] = []
    path: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    current_trade: dict[str, Any] | None = None

    def observe_equity(value: float) -> None:
        nonlocal peak, max_drawdown, bankrupt
        peak = max(peak, value)
        if peak > 0.0:
            max_drawdown = min(max_drawdown, value / peak - 1.0)
        if value <= 0.0:
            bankrupt = True

    def mark_to(price: float) -> None:
        nonlocal equity, mark_price
        equity += qty * (price - mark_price)
        mark_price = price
        observe_equity(equity)

    def trade_to(target: Any, price: float) -> tuple[float, float]:
        nonlocal equity, qty, side, turnover_total, cost_total
        qty, equity, turnover, cost = _target_quantity(
            equity, qty, int(target), price, cost_rate
        )
        side = target
        turnover_total += turnover
        cost_total += cost
        observe_equity(equity)
        return turnover, cost

    def open_trade(
        target: Any,
        ts: pd.Timestamp,
        price: float,
        signal_ts: pd.Timestamp,
        reason: str,
        entry_atr: float,
    ) -> None:
        nonlocal current_trade
        if current_trade is not None or side != engine.Side.FLAT:
            raise RuntimeError("entry requires a flat ledger")
        entry_equity = equity
        _, entry_cost = trade_to(target, price)
        current_trade = {
            "trade_id": f"{label}-{len(trades) + 1:03d}",
            "entry_ts": ts.isoformat(),
            "entry_signal_ts": signal_ts.isoformat(),
            "side": "long" if target == engine.Side.LONG else "short",
            "entry_price": price,
            "entry_quantity": qty,
            "entry_equity": entry_equity,
            "entry_cost": entry_cost,
            "entry_reason": reason,
            "entry_atr": entry_atr,
            "highest": price,
            "lowest": price,
            "funding_payment": 0.0,
        }

    def update_trade_range(high: float, low: float) -> None:
        if current_trade is None:
            return
        current_trade["highest"] = max(float(current_trade["highest"]), high)
        current_trade["lowest"] = min(float(current_trade["lowest"]), low)

    def close_trade(ts: pd.Timestamp, price: float, reason: str) -> None:
        nonlocal current_trade
        if current_trade is None or side == engine.Side.FLAT:
            raise RuntimeError("exit requires an open trade")
        old_side = side
        exit_equity_before = equity
        _, exit_cost = trade_to(engine.Side.FLAT, price)
        entry_price = float(current_trade["entry_price"])
        direction = 1.0 if old_side == engine.Side.LONG else -1.0
        gross_return = direction * (price - entry_price) / entry_price
        favorable_price = (
            float(current_trade["highest"])
            if old_side == engine.Side.LONG
            else float(current_trade["lowest"])
        )
        adverse_price = (
            float(current_trade["lowest"])
            if old_side == engine.Side.LONG
            else float(current_trade["highest"])
        )
        mfe_return = direction * (favorable_price - entry_price) / entry_price
        mae_return = direction * (adverse_price - entry_price) / entry_price
        trade = {
            **current_trade,
            "exit_ts": ts.isoformat(),
            "exit_price": price,
            "exit_reason": reason,
            "exit_cost": exit_cost,
            "exit_equity_before": exit_equity_before,
            "exit_equity": equity,
            "net_pnl": equity - float(current_trade["entry_equity"]),
            "net_return": equity / float(current_trade["entry_equity"]) - 1.0,
            "gross_return": gross_return,
            "mfe_return": mfe_return,
            "mae_return": mae_return,
            "giveback_return": max(0.0, mfe_return - gross_return),
        }
        trades.append(trade)
        current_trade = None

    def execute_decision(
        decision: Any, index: int, ts: pd.Timestamp, price: float
    ) -> None:
        nonlocal pending_due_index
        if side != decision.from_side or machine.state.side != decision.from_side:
            raise RuntimeError("machine/ledger side drift before decision fill")
        if decision.from_side != engine.Side.FLAT:
            close_trade(ts, price, decision.reason)
        machine.on_next_open(
            ts,
            price,
            extra_delay_days=extra_delay_days,
        )
        if decision.target_side != engine.Side.FLAT:
            signal_index = data.daily.index.get_loc(decision.signal_ts)
            entry_atr = float(data.daily.iloc[signal_index]["atr7"])
            open_trade(
                decision.target_side,
                ts,
                price,
                decision.signal_ts,
                decision.reason,
                entry_atr,
            )
        pending_due_index = None
        actions.append(
            {
                "ts": ts.isoformat(),
                "signal_ts": decision.signal_ts.isoformat(),
                "from_side": int(decision.from_side),
                "target_side": int(decision.target_side),
                "reason": decision.reason,
                "fills": decision.fills,
                "price": price,
            }
        )

    def intraday_stop(index: int, hour: int) -> bool:
        nonlocal stop_count, mark_price, max_effective_leverage
        if hard_stop_atr <= 0.0 or current_trade is None or side == engine.Side.FLAT:
            return False
        old_side = side
        entry = float(current_trade["entry_price"])
        entry_atr = float(current_trade["entry_atr"])
        stop = entry - int(old_side) * hard_stop_atr * entry_atr
        hour_open = float(data.features.hourly_open[index][hour])
        hour_high = float(data.features.hourly_high[index][hour])
        hour_low = float(data.features.hourly_low[index][hour])
        hit = hour_low <= stop if old_side == engine.Side.LONG else hour_high >= stop
        if not hit:
            return False
        gap = hour_open <= stop if old_side == engine.Side.LONG else hour_open >= stop
        fill = hour_open if gap else stop
        if not math.isclose(mark_price, hour_open):
            mark_to(hour_open)
        # OHLC cannot reveal whether the favorable extreme occurred before the
        # stop.  Record only the observable open-to-fill segment and never use
        # post-exit hourly extremes in MFE/MAE or drawdown.
        update_trade_range(max(hour_open, fill), min(hour_open, fill))
        if not math.isclose(mark_price, fill):
            mark_to(fill)
        if equity > 0.0:
            max_effective_leverage = max(
                max_effective_leverage,
                abs(qty) * fill / equity,
            )
        close_trade(
            pd.Timestamp(data.daily.index[index]) + pd.Timedelta(hours=hour),
            fill,
            "emergency_hard_stop",
        )
        mark_price = fill
        machine.force_flat()
        stop_count += 1
        actions.append(
            {
                "ts": (
                    pd.Timestamp(data.daily.index[index]) + pd.Timedelta(hours=hour)
                ).isoformat(),
                "signal_ts": None,
                "from_side": int(old_side),
                "target_side": 0,
                "reason": "emergency_hard_stop",
                "fills": 1,
                "price": fill,
            }
        )
        return True

    for index in range(start_index, terminal_index):
        ts = pd.Timestamp(data.daily.index[index])
        current_open = float(book.open[index])
        if index > start_index:
            mark_to(current_open)
        else:
            mark_price = current_open

        if pending_due_index is not None and index == pending_due_index:
            decision = machine.state.pending
            if decision is None:
                raise RuntimeError("missing pending decision at due open")
            execute_decision(decision, index, ts, current_open)

        day_events = {
            event.ts.floor("h"): event for event in data.features.funding_events[index]
        }
        for hour in range(24):
            hour_ts = ts + pd.Timedelta(hours=hour)
            hour_open = float(data.features.hourly_open[index][hour])
            if not math.isclose(mark_price, hour_open):
                mark_to(hour_open)
            if side != engine.Side.FLAT:
                exposure_hours += 1
                event = day_events.get(hour_ts)
                if event is not None:
                    payment = qty * event.price * event.rate
                    equity -= payment
                    funding_total += payment
                    if current_trade is not None:
                        current_trade["funding_payment"] += payment
                    observe_equity(equity)
                if intraday_stop(index, hour):
                    continue
                high = float(data.features.hourly_high[index][hour])
                low = float(data.features.hourly_low[index][hour])
                update_trade_range(high, low)
                favorable = high if side == engine.Side.LONG else low
                adverse = low if side == engine.Side.LONG else high
                favorable_equity = equity + qty * (favorable - hour_open)
                adverse_equity = equity + qty * (adverse - hour_open)
                observe_equity(favorable_equity)
                observe_equity(adverse_equity)
                if adverse_equity > 0.0:
                    max_effective_leverage = max(
                        max_effective_leverage,
                        abs(qty) * adverse / adverse_equity,
                    )
        mark_to(float(book.close[index]))
        update_trade_range(float(book.high[index]), float(book.low[index]))
        if bankrupt:
            break

        decision = None
        row = data.daily.iloc[index]
        complete = np.isfinite(
            row[["ma7", "atr7", "rsi6", "slope_atr"]].to_numpy()
        ).all()
        if index >= active_start:
            if machine.state.pending is None:
                if complete:
                    decision = machine.on_close(_observation(engine, data, index))
                    if decision is not None:
                        pending_due_index = index + 1 + extra_delay_days
            else:
                if not complete:
                    raise RuntimeError("pending execution crossed an incomplete row")
                if pending_due_index is None or index >= pending_due_index:
                    raise RuntimeError("pending execution schedule drift")
                machine.observe_pending_close(_observation(engine, data, index))

        equity_points.append(equity)

        if retain:
            path.append(
                {
                    "ts": ts.isoformat(),
                    "open": float(book.open[index]),
                    "high": float(book.high[index]),
                    "low": float(book.low[index]),
                    "close": float(book.close[index]),
                    "ma7": float(row["ma7"]) if np.isfinite(row["ma7"]) else None,
                    "atr7": float(row["atr7"]) if np.isfinite(row["atr7"]) else None,
                    "rsi6": float(row["rsi6"]) if np.isfinite(row["rsi6"]) else None,
                    "slope_atr": (
                        float(row["slope_atr"])
                        if np.isfinite(row["slope_atr"])
                        else None
                    ),
                    "upper_band": (
                        float(row["ma7"] + config.tolerance_atr * row["atr7"])
                        if complete
                        else None
                    ),
                    "lower_band": (
                        float(row["ma7"] - config.tolerance_atr * row["atr7"])
                        if complete
                        else None
                    ),
                    "equity": equity,
                    "side": int(side),
                    "armed_side": int(machine.state.armed_side),
                    "pending_reason": decision.reason if decision is not None else "",
                    "terminal": False,
                }
            )

    terminal_ts = (
        pd.Timestamp(book.terminal_ts)
        if terminal_index == book.count
        else pd.Timestamp(book.ts[terminal_index])
    )
    terminal_open = (
        float(book.quality["terminal_open"])
        if terminal_index == book.count
        else float(book.open[terminal_index])
    )
    if not bankrupt:
        mark_to(terminal_open)
        if side != engine.Side.FLAT:
            old_side = side
            close_trade(terminal_ts, terminal_open, "terminal_flatten")
            actions.append(
                {
                    "ts": terminal_ts.isoformat(),
                    "signal_ts": None,
                    "from_side": int(old_side),
                    "target_side": 0,
                    "reason": "terminal_flatten",
                    "fills": 1,
                    "price": terminal_open,
                }
            )
        machine.state.pending = None
        machine.force_flat()
        equity_points.append(equity)
        if retain:
            path.append(
                {
                    "ts": terminal_ts.isoformat(),
                    "open": terminal_open,
                    "high": terminal_open,
                    "low": terminal_open,
                    "close": terminal_open,
                    "ma7": None,
                    "atr7": None,
                    "rsi6": None,
                    "slope_atr": None,
                    "upper_band": None,
                    "lower_band": None,
                    "equity": equity,
                    "side": 0,
                    "armed_side": 0,
                    "pending_reason": "",
                    "terminal": True,
                }
            )
    days = (terminal_ts - pd.Timestamp(book.ts[start_index])).total_seconds() / 86_400.0
    trade_returns = np.asarray([trade["net_return"] for trade in trades], dtype=float)
    wins = trade_returns[trade_returns > 0.0]
    losses = trade_returns[trade_returns < 0.0]
    daily_returns = (
        pd.Series(equity_points, dtype=float).pct_change().dropna().to_numpy()
    )
    sharpe = (
        float(np.mean(daily_returns) / np.std(daily_returns, ddof=1) * np.sqrt(365.25))
        if len(daily_returns) > 1 and np.std(daily_returns, ddof=1) > 0.0
        else math.nan
    )
    short_trades = [trade for trade in trades if trade["side"] == "short"]
    long_trades = [trade for trade in trades if trade["side"] == "long"]
    metrics = {
        "label": label,
        "start_ts": pd.Timestamp(book.ts[start_index]).isoformat(),
        "end_ts": terminal_ts.isoformat(),
        "equity_multiple": equity,
        "net_return_pct": (equity - 1.0) * 100.0,
        "annualized_factor": _annualized(equity, days),
        "max_drawdown_pct": max_drawdown * 100.0,
        "sharpe": sharpe,
        "profit_factor": (
            float(wins.sum() / abs(losses.sum())) if len(losses) else math.inf
        ),
        "closed_trades": len(trades),
        "long_trades": len(long_trades),
        "short_trades": len(short_trades),
        "win_rate": float((trade_returns > 0.0).mean()) if len(trades) else math.nan,
        "long_net_pnl": float(sum(trade["net_pnl"] for trade in long_trades)),
        "short_net_pnl": float(sum(trade["net_pnl"] for trade in short_trades)),
        "short_median_giveback_pct": (
            float(
                np.median([trade["giveback_return"] for trade in short_trades]) * 100.0
            )
            if short_trades
            else math.nan
        ),
        "short_mean_giveback_pct": (
            float(np.mean([trade["giveback_return"] for trade in short_trades]) * 100.0)
            if short_trades
            else math.nan
        ),
        "exposure_pct": exposure_hours
        / max(1, (terminal_index - start_index) * 24)
        * 100.0,
        "turnover": turnover_total,
        "cost": cost_total,
        "funding_payment": funding_total,
        "max_effective_leverage": max_effective_leverage,
        "hard_stop_count": stop_count,
        "bankrupt": bankrupt,
        "slippage_bps": slippage * 10_000.0,
        "extra_delay_days": extra_delay_days,
        "hard_stop_atr": hard_stop_atr,
    }
    return BacktestResult(
        metrics, trades if retain else [], path, actions if retain else []
    )


def rolling_rows(
    engine: Any,
    data: MarketData,
    configs: dict[str, Any],
    *,
    window_days: int = 90,
    step_days: int = 30,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, config in configs.items():
        for start in range(
            _first_valid_index(data), data.book.count - window_days + 1, step_days
        ):
            end = start + window_days
            result = backtest(
                engine,
                data,
                config,
                label=label,
                start_index=start,
                terminal_index=end,
            )
            rows.append(
                {
                    "label": label,
                    "start_ts": pd.Timestamp(data.book.ts[start]).isoformat(),
                    "end_ts": pd.Timestamp(data.book.ts[end]).isoformat(),
                    **result.metrics,
                }
            )
    return rows


def cpcv_rows(
    engine: Any,
    data: MarketData,
    configs: dict[str, Any],
    *,
    blocks: int = 6,
    purge_days: int = 10,
) -> list[dict[str, Any]]:
    valid_start = _first_valid_index(data)
    block_indices = [
        array
        for array in np.array_split(np.arange(valid_start, data.book.count), blocks)
    ]
    rows: list[dict[str, Any]] = []
    for label, config in configs.items():
        for combo_id, selected in enumerate(
            itertools.combinations(range(blocks), 2), start=1
        ):
            equity = 1.0
            trades = 0
            positive = 0
            usable = 0
            for block_id in selected:
                values = block_indices[block_id]
                start = int(values[0]) + purge_days
                end = int(values[-1]) + 1 - purge_days
                if end - start < 20:
                    continue
                result = backtest(
                    engine,
                    data,
                    config,
                    label=label,
                    start_index=start,
                    terminal_index=end,
                )
                usable += 1
                equity *= result.metrics["equity_multiple"]
                trades += int(result.metrics["closed_trades"])
                positive += result.metrics["equity_multiple"] > 1.0
            rows.append(
                {
                    "label": label,
                    "combo_id": combo_id,
                    "test_blocks": "+".join(map(str, selected)),
                    "usable_blocks": usable,
                    "equity_multiple": equity,
                    "net_return_pct": (equity - 1.0) * 100.0,
                    "closed_trades": trades,
                    "positive_blocks": positive,
                    "insufficient_evidence": trades < 5,
                }
            )
    return rows


def mc3_rows(
    results: dict[str, BacktestResult],
    *,
    samples: int,
    seed: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, result in results.items():
        trades = result.trades
        long_returns = np.asarray(
            [trade["net_return"] for trade in trades if trade["side"] == "long"],
            dtype=float,
        )
        short_returns = np.asarray(
            [trade["net_return"] for trade in trades if trade["side"] == "short"],
            dtype=float,
        )
        if not len(trades):
            rows.append({"label": label, "insufficient_evidence": True, "samples": 0})
            continue
        # Common random numbers make path-identical arms exactly comparable.
        rng = np.random.default_rng(seed)
        ending = np.empty(samples, dtype=float)
        drawdown = np.empty(samples, dtype=float)
        for sample in range(samples):
            parts = []
            if len(long_returns):
                parts.extend(rng.choice(long_returns, len(long_returns), replace=True))
            if len(short_returns):
                parts.extend(
                    rng.choice(short_returns, len(short_returns), replace=True)
                )
            sampled = np.asarray(parts, dtype=float)
            rng.shuffle(sampled)
            curve = np.cumprod(1.0 + sampled)
            peaks = np.maximum.accumulate(np.r_[1.0, curve])
            full = np.r_[1.0, curve]
            ending[sample] = full[-1]
            drawdown[sample] = np.min(full / peaks - 1.0)
        for quantile in (0.05, 0.10, 0.50, 0.90, 0.95):
            rows.append(
                {
                    "label": label,
                    "quantile": quantile,
                    "equity_multiple": float(np.quantile(ending, quantile)),
                    "max_drawdown_pct": float(np.quantile(drawdown, quantile) * 100.0),
                    "loss_probability": float(np.mean(ending < 1.0)),
                    "samples": samples,
                    "trades_per_sample": len(trades),
                    "insufficient_evidence": len(trades) < 20,
                }
            )
    return rows


def sensitivity_configs(engine: Any, base: Any) -> dict[str, Any]:
    return {
        "CORE_NCROSS_2": replace(base, prior_side_days=2),
        "CORE_NCROSS_3": replace(base, prior_side_days=3),
        "CORE_ATR_050": replace(base, tolerance_atr=0.50),
        "CORE_ATR_100": replace(base, tolerance_atr=1.00),
        "CORE_SLOPE_002": replace(base, slope_min_atr=0.02),
        "CORE_SLOPE_005": replace(base, slope_min_atr=0.05),
        "CORE_NO_ARM": replace(base, arm_cross_while_held=False),
        "CORE_NO_SLOPE_EXIT": replace(
            base, slope_loss_action=engine.SlopeLossAction.HOLD
        ),
        "CORE_NO_SLOPE": replace(
            base,
            band_requires_slope=False,
            slope_loss_action=engine.SlopeLossAction.HOLD,
        ),
        "CORE_ZERO_TOLERANCE": replace(base, tolerance_atr=0.0),
    }


def rsi_sensitivity_configs(engine: Any, configs: dict[str, Any]) -> dict[str, Any]:
    base = configs["D_BOTH_RSI"]
    return {
        "RSI_DAYS_2": replace(base, short_rsi_exit_days=2, overbought_days=2),
        "RSI_DAYS_4": replace(base, short_rsi_exit_days=4, overbought_days=4),
        "RSI_EXIT_25": replace(base, short_rsi_exit_threshold=25.0),
        "RSI_EXIT_35": replace(base, short_rsi_exit_threshold=35.0),
        "RSI_OB_65": replace(base, overbought_threshold=65.0),
        "RSI_OB_75": replace(base, overbought_threshold=75.0),
    }


def phase_rows(engine: Any, configs: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for phase in range(24):
        try:
            data = load_market(phase)
        except RuntimeError as exc:
            rows.append({"phase_hour": phase, "available": False, "error": str(exc)})
            continue
        for label, primary in configs.items():
            config = replace(primary, session_open_hour=phase)
            result = backtest(engine, data, config, label=label)
            rows.append(
                {
                    "phase_hour": phase,
                    "available": True,
                    **result.metrics,
                }
            )
    return rows


def recent_rows(result: BacktestResult) -> list[dict[str, Any]]:
    frame = pd.DataFrame(result.path)
    if frame.empty:
        return []
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    end = frame["ts"].max()
    rows = []
    for label, days in RECENT_WINDOWS.items():
        selected = frame.loc[frame["ts"].ge(end - pd.Timedelta(days=days))]
        if len(selected) < 2:
            rows.append({"window": label, "available": False})
            continue
        equity = selected["equity"].to_numpy(dtype=float)
        peaks = np.maximum.accumulate(equity)
        rows.append(
            {
                "window": label,
                "available": True,
                "start_ts": selected["ts"].iloc[0].isoformat(),
                "end_ts": selected["ts"].iloc[-1].isoformat(),
                "net_return_pct": (equity[-1] / equity[0] - 1.0) * 100.0,
                "max_drawdown_pct": float(np.min(equity / peaks - 1.0) * 100.0),
            }
        )
    return rows


def write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    frame = pd.DataFrame(list(rows))
    frame.to_csv(path, index=False)


def json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value).__name__)


def self_test() -> None:
    engine, _, _ = modules()
    configs = frozen_configs(engine)
    if tuple(configs) != (
        "A_CORE",
        "B_SHORT_RSI_EXIT",
        "C_OVERBOUGHT_REVERSAL",
        "D_BOTH_RSI",
    ):
        raise RuntimeError("frozen arm order drift")
    if configs["A_CORE"].slope_min_atr != 0.0:
        raise RuntimeError("core slope must remain a strict sign test")
    if configs["D_BOTH_RSI"].short_rsi_exit_threshold != 30.0:
        raise RuntimeError("short RSI threshold drift")
    if configs["D_BOTH_RSI"].overbought_threshold != 70.0:
        raise RuntimeError("overbought threshold drift")
    print(json.dumps({"self_test": "PASS", "engine_sha256": ENGINE_SHA256}))


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return
    if not CONTRACT_PATH.exists():
        raise RuntimeError("frozen contract is missing")
    engine, _, search = modules()
    data = load_market(0)
    configs = frozen_configs(engine)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    prefix = ARTIFACT_DIR / f"hype_1d_ma7_original_trend_{args.run_date}"

    primary: dict[str, BacktestResult] = {}
    stress_rows: list[dict[str, Any]] = []
    protection_rows: list[dict[str, Any]] = []
    all_trades: list[dict[str, Any]] = []
    all_paths: list[dict[str, Any]] = []
    all_actions: list[dict[str, Any]] = []
    for label, config in configs.items():
        result = backtest(engine, data, config, label=label, retain=True)
        primary[label] = result
        all_trades.extend({"label": label, **row} for row in result.trades)
        all_paths.extend({"label": label, **row} for row in result.path)
        all_actions.extend({"label": label, **row} for row in result.actions)
        for scenario, kwargs in (
            ("stress_8bps", {"slippage": STRESS_SLIPPAGE}),
            ("extra_delay_1d", {"extra_delay_days": 1}),
        ):
            stressed = backtest(engine, data, config, label=label, **kwargs)
            stress_rows.append({"scenario": scenario, **stressed.metrics})
        protected = backtest(
            engine,
            data,
            config,
            label=label,
            hard_stop_atr=PROTECTION_ATR,
        )
        protection_rows.append(protected.metrics)

    rolling = rolling_rows(engine, data, configs)
    cpcv = cpcv_rows(engine, data, configs)
    mc3 = mc3_rows(primary, samples=args.bootstrap_samples, seed=args.seed)
    core_sensitivity = []
    for label, config in sensitivity_configs(engine, configs["A_CORE"]).items():
        core_sensitivity.append(backtest(engine, data, config, label=label).metrics)
    rsi_sensitivity = []
    for label, config in rsi_sensitivity_configs(engine, configs).items():
        rsi_sensitivity.append(backtest(engine, data, config, label=label).metrics)
    phases = phase_rows(engine, configs)

    base_features = data.features
    buy_hold = search.buy_and_hold(data.book, base_features)
    recent = []
    for label, result in primary.items():
        recent.extend({"label": label, **row} for row in recent_rows(result))

    summary = {
        "family": FAMILY,
        "branch": BRANCH,
        "status": "explore / not promoted / not live-ready",
        "run_date": args.run_date,
        "contract": str(CONTRACT_PATH.relative_to(ROOT)),
        "contract_sha256": sha256(CONTRACT_PATH),
        "engine_sha256": ENGINE_SHA256,
        "research_script_sha256": sha256(Path(__file__)),
        "data": data.audit,
        "configs": {label: asdict(config) for label, config in configs.items()},
        "primary": {label: result.metrics for label, result in primary.items()},
        "buy_and_hold": buy_hold,
        "evidence_role": (
            "all performance is researcher-exposed development diagnostics; "
            "not clean OOS and not promotion evidence"
        ),
        "prospective": {
            "status": "not_started",
            "rule": "first complete UTC day after contract freeze; flat-start",
        },
    }
    Path(f"{prefix}_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )
    write_csv(
        Path(f"{prefix}_metrics.csv"), [result.metrics for result in primary.values()]
    )
    write_csv(Path(f"{prefix}_stress.csv"), stress_rows)
    write_csv(Path(f"{prefix}_protection.csv"), protection_rows)
    write_csv(Path(f"{prefix}_rolling_90d.csv"), rolling)
    write_csv(Path(f"{prefix}_cpcv.csv"), cpcv)
    write_csv(Path(f"{prefix}_mc3.csv"), mc3)
    write_csv(Path(f"{prefix}_core_sensitivity.csv"), core_sensitivity)
    write_csv(Path(f"{prefix}_rsi_sensitivity.csv"), rsi_sensitivity)
    write_csv(Path(f"{prefix}_phase24.csv"), phases)
    write_csv(Path(f"{prefix}_recent.csv"), recent)
    write_csv(Path(f"{prefix}_trades.csv"), all_trades)
    write_csv(Path(f"{prefix}_path.csv"), all_paths)
    write_csv(Path(f"{prefix}_actions.csv"), all_actions)
    print(
        json.dumps(
            {
                "summary": str(Path(f"{prefix}_summary.json").relative_to(ROOT)),
                "primary": summary["primary"],
                "buy_and_hold": buy_hold,
                "artifacts": 13,
            },
            ensure_ascii=False,
            default=json_default,
        )
    )


if __name__ == "__main__":
    main()
