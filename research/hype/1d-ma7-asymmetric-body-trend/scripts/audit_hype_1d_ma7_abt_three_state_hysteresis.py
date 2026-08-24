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
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
FORMATION_PATH = (
    FAMILY_DIR / "scripts/audit_hype_v1_trailing_stop_short_reversal.py"
)
FORMATION_SHA256 = (
    "35185bbdba87732a806ef3d5e0ff9fc9da9e314e8369695646e7b3f07cbb1166"
)
V2_EQUITY_MULTIPLE = 4.225904698992523
HOLDOUT_START = pd.Timestamp("2026-05-01T00:00:00Z")
VARIANT_V2 = "V2_CONTROL"
VARIANT_BINARY = "BINARY_D075"
VARIANT_TRI = "TRI_D075_N025_K3"


@dataclass(frozen=True, slots=True)
class StateConfig:
    name: str
    outer_atr: float
    neutral_atr: float
    neutral_days: int

    @property
    def has_neutral_exit(self) -> bool:
        return self.neutral_days > 0


BINARY_CONFIG = StateConfig(VARIANT_BINARY, 0.75, 0.0, 0)
TRI_CONFIG = StateConfig(VARIANT_TRI, 0.75, 0.25, 3)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit binary and three-state MA7 hysteresis mechanisms."
    )
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def load_pinned(path: Path, expected: str, name: str) -> Any:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise RuntimeError(
            f"{path.name} drift: expected {expected}, got {actual}"
        )
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def neutral_streak(
    close: np.ndarray,
    ma7: np.ndarray,
    atr7: np.ndarray,
    width_atr: float,
) -> np.ndarray:
    streak = np.zeros(len(close), dtype="int64")
    if width_atr <= 0.0:
        return streak
    running = 0
    for index in range(len(close)):
        valid = np.isfinite(ma7[index]) and np.isfinite(atr7[index])
        inside = (
            valid
            and abs(float(close[index]) - float(ma7[index]))
            <= width_atr * float(atr7[index])
        )
        running = running + 1 if inside else 0
        streak[index] = running
    return streak


def target_state(
    current_side: int,
    close: float,
    ma7: float,
    atr7: float,
    streak: int,
    config: StateConfig,
) -> tuple[int, str]:
    if not all(math.isfinite(value) for value in (close, ma7, atr7)):
        return current_side, "indicator_warmup"
    upper = ma7 + config.outer_atr * atr7
    lower = ma7 - config.outer_atr * atr7
    if current_side > 0:
        if close <= lower:
            return -1, "lower_boundary_flip"
        if config.has_neutral_exit and streak >= config.neutral_days:
            return 0, "neutral_timeout_exit"
        return 1, "hold_long"
    if current_side < 0:
        if close >= upper:
            return 1, "upper_boundary_flip"
        if config.has_neutral_exit and streak >= config.neutral_days:
            return 0, "neutral_timeout_exit"
        return -1, "hold_short"
    if close >= upper:
        return 1, "upper_boundary_entry"
    if close <= lower:
        return -1, "lower_boundary_entry"
    return 0, "hold_flat"


def hysteresis_backtest(
    engine: Any,
    book: Any,
    features: Any,
    config: StateConfig,
    *,
    start_index: int,
    terminal_index: int,
    slippage: float,
    signal_lag: int = 0,
    include_funding: bool = True,
    retain: bool = False,
) -> Any:
    if not (0 <= start_index < terminal_index <= book.count):
        raise ValueError("invalid window")
    timestamps = pd.DatetimeIndex([*book.ts, book.terminal_ts])
    opens = np.r_[book.open, float(book.quality["terminal_open"])]
    streaks = neutral_streak(
        np.asarray(book.close, dtype=float),
        np.asarray(features.ma7, dtype=float),
        np.asarray(features.atr7, dtype=float),
        config.neutral_atr,
    )
    cost_rate = engine.FEE + slippage
    equity = 1.0
    qty = 0.0
    side = 0
    mark_price = float(opens[start_index])
    peak = 1.0
    max_drawdown = 0.0
    total_turnover = 0.0
    total_cost = 0.0
    total_funding = 0.0
    max_intraday_leverage = 0.0
    exposed_days = 0
    flip_count = 0
    neutral_exit_count = 0
    entry_ts: pd.Timestamp | None = None
    entry_index: int | None = None
    entry_price = math.nan
    entry_equity = math.nan
    entry_side = 0
    entry_reason = ""
    trades: list[dict[str, Any]] = []
    path: list[dict[str, Any]] = []
    equity_points: list[float] = [1.0]
    bankrupt = False

    def trade_to(target: int, price: float) -> None:
        nonlocal qty, equity, side, total_turnover, total_cost
        old_equity = equity
        qty, equity, turnover = engine._target_quantity(
            equity,
            qty,
            target,
            price,
            cost_rate,
        )
        total_turnover += turnover
        total_cost += old_equity - equity
        side = target

    def close_position(
        ts: pd.Timestamp,
        price: float,
        reason: str,
        index: int,
    ) -> None:
        nonlocal entry_ts, entry_index, entry_price, entry_equity
        nonlocal entry_side, entry_reason
        if entry_ts is None or entry_index is None:
            raise RuntimeError("cannot close absent position")
        old_side = entry_side
        old_entry_equity = entry_equity
        trade_to(0, price)
        trades.append(
            {
                "entry_ts": entry_ts.isoformat(),
                "exit_ts": ts.isoformat(),
                "side": "long" if old_side > 0 else "short",
                "entry_price": entry_price,
                "exit_price": price,
                "bars_held": index - entry_index,
                "entry_reason": entry_reason,
                "exit_reason": reason,
                "net_return": equity / old_entry_equity - 1.0,
                "net_pnl": equity - old_entry_equity,
            }
        )
        entry_ts = None
        entry_index = None
        entry_price = entry_equity = math.nan
        entry_side = 0
        entry_reason = ""

    def enter_position(
        target: int,
        ts: pd.Timestamp,
        price: float,
        index: int,
        reason: str,
    ) -> None:
        nonlocal entry_ts, entry_index, entry_price, entry_equity
        nonlocal entry_side, entry_reason
        before = equity
        trade_to(target, price)
        entry_ts = ts
        entry_index = index
        entry_price = price
        entry_equity = before
        entry_side = target
        entry_reason = reason

    for index in range(start_index, terminal_index + 1):
        ts = pd.Timestamp(timestamps[index])
        current_open = float(opens[index])
        if index > start_index and qty != 0.0:
            equity += qty * (current_open - mark_price)
        mark_price = current_open
        if equity <= 0.0:
            bankrupt = True
            equity = 0.0
            qty = 0.0
            side = 0
            max_drawdown = -1.0
            break

        pre_action_equity = equity
        action = "hold"
        decision_reason = "no_decision"
        decision_index = index - 1 - signal_lag
        if index < terminal_index and decision_index >= 0:
            target, decision_reason = target_state(
                side,
                float(book.close[decision_index]),
                float(features.ma7[decision_index]),
                float(features.atr7[decision_index]),
                int(streaks[decision_index]),
                config,
            )
            if target != side:
                old_side = side
                is_flip = old_side != 0 and target != 0
                if old_side != 0:
                    close_position(ts, current_open, decision_reason, index)
                if target != 0:
                    enter_position(
                        target,
                        ts,
                        current_open,
                        index,
                        decision_reason,
                    )
                if is_flip:
                    flip_count += 1
                    action = (
                        "flip_long_to_short"
                        if target < 0
                        else "flip_short_to_long"
                    )
                elif target == 0:
                    neutral_exit_count += 1
                    action = "neutral_exit"
                else:
                    action = "enter_long" if target > 0 else "enter_short"

        if index >= terminal_index:
            if qty != 0.0:
                close_position(ts, current_open, "terminal_flatten", index)
                action = "terminal_flatten"
            post_action_equity = equity
            peak = max(peak, pre_action_equity, post_action_equity)
            max_drawdown = min(
                max_drawdown,
                post_action_equity / peak - 1.0,
            )
            equity_points.append(post_action_equity)
            if retain:
                path.append(
                    {
                        "ts": ts.isoformat(),
                        "pre_action_equity": pre_action_equity,
                        "post_action_equity": post_action_equity,
                        "close_equity": post_action_equity,
                        "favorable_equity": post_action_equity,
                        "adverse_equity": post_action_equity,
                        "position": side,
                        "action": action,
                        "decision_reason": decision_reason,
                    }
                )
            continue

        post_action_equity = equity
        peak = max(peak, pre_action_equity, post_action_equity)
        max_drawdown = min(
            max_drawdown,
            post_action_equity / peak - 1.0,
        )
        if side != 0:
            exposed_days += 1
            if post_action_equity > 0.0:
                max_intraday_leverage = max(
                    max_intraday_leverage,
                    abs(qty) * current_open / post_action_equity,
                )
            if include_funding:
                for event in features.funding_events[index]:
                    payment = qty * event.price * event.rate
                    equity -= payment
                    total_funding += payment
            favorable_price = (
                float(book.high[index])
                if side > 0
                else float(book.low[index])
            )
            adverse_price = (
                float(book.low[index])
                if side > 0
                else float(book.high[index])
            )
            favorable_equity = equity + qty * (
                favorable_price - current_open
            )
            adverse_equity = equity + qty * (adverse_price - current_open)
            close_equity = equity + qty * (
                float(book.close[index]) - current_open
            )
            if adverse_equity <= 0.0:
                bankrupt = True
                equity = 0.0
                qty = 0.0
                side = 0
                close_equity = 0.0
                max_drawdown = -1.0
                action = "intraday_bankruptcy"
            peak = max(peak, favorable_equity, close_equity)
            max_drawdown = min(
                max_drawdown,
                adverse_equity / peak - 1.0,
                close_equity / peak - 1.0,
            )
        else:
            favorable_equity = adverse_equity = close_equity = equity

        if retain:
            path.append(
                {
                    "ts": ts.isoformat(),
                    "pre_action_equity": pre_action_equity,
                    "post_action_equity": post_action_equity,
                    "close_equity": close_equity,
                    "favorable_equity": favorable_equity,
                    "adverse_equity": adverse_equity,
                    "position": side,
                    "action": action,
                    "decision_reason": decision_reason,
                }
            )
        equity_points.append(float(close_equity))
        if bankrupt:
            break

    days = max(
        1.0,
        (timestamps[terminal_index] - timestamps[start_index]).total_seconds()
        / 86_400.0,
    )
    trade_pnl = np.asarray(
        [float(row["net_pnl"]) for row in trades],
        dtype=float,
    )
    gross_profit = float(trade_pnl[trade_pnl > 0.0].sum())
    gross_loss = float(-trade_pnl[trade_pnl < 0.0].sum())
    equity_series = pd.Series(equity_points, dtype=float)
    returns = (
        equity_series.pct_change()
        .replace([np.inf, -np.inf], np.nan)
        .dropna()
    )
    sharpe = (
        float(np.sqrt(365.25) * returns.mean() / returns.std(ddof=1))
        if len(returns) >= 30 and returns.std(ddof=1) > 0.0
        else math.nan
    )
    metrics = {
        "start_ts": pd.Timestamp(timestamps[start_index]).isoformat(),
        "end_ts": pd.Timestamp(timestamps[terminal_index]).isoformat(),
        "days": days,
        "equity_multiple": equity,
        "net_return_pct": (equity - 1.0) * 100.0,
        "max_drawdown_pct": max_drawdown * 100.0,
        "sharpe": sharpe,
        "closed_trades": len(trades),
        "long_trades": sum(row["side"] == "long" for row in trades),
        "short_trades": sum(row["side"] == "short" for row in trades),
        "win_rate": (
            float((trade_pnl > 0.0).mean()) if len(trade_pnl) else math.nan
        ),
        "profit_factor": (
            gross_profit / gross_loss
            if gross_loss > 0.0
            else (math.inf if gross_profit > 0.0 else math.nan)
        ),
        "turnover_multiple": total_turnover,
        "cost_pct_initial": total_cost * 100.0,
        "funding_pct_initial": total_funding * 100.0,
        "max_intraday_leverage": max_intraday_leverage,
        "bankrupt_intraday": bankrupt,
        "flip_count": flip_count,
        "neutral_exit_count": neutral_exit_count,
        "exposure_pct": exposed_days / days * 100.0,
    }
    return engine.Result(metrics=metrics, trades=trades, path=path)


def control_result(
    backtest: Any,
    long_config: Any,
    short_config: Any,
    book: Any,
    features: Any,
    engine: Any,
    *,
    start: int,
    end: int,
    slippage: float,
    signal_lag: int = 0,
    include_funding: bool = True,
    retain: bool = False,
) -> Any:
    return backtest(
        book,
        features,
        long_config=long_config,
        short_config=short_config,
        start_index=start,
        terminal_index=end,
        slippage=slippage,
        signal_lag=signal_lag,
        include_funding=include_funding,
        retain=retain,
    )


def add_aux_metrics(
    result: Any,
    variant: str,
    formation: Any,
) -> dict[str, Any]:
    if variant == VARIANT_V2:
        annotated = formation.annotate_trades(
            result,
            "T1_trailing_stop_short_reversal",
        )
        attribution = formation.attribution(annotated)
        positions = [
            int(row["position"])
            for row in result.path
            if row["action"] != "terminal"
        ]
        exposure = (
            100.0 * sum(value != 0 for value in positions) / len(positions)
            if positions
            else math.nan
        )
        return {
            "flip_count": attribution["forced_reversal_trades"],
            "neutral_exit_count": 0,
            "exposure_pct": exposure,
        }
    return {
        "flip_count": result.metrics["flip_count"],
        "neutral_exit_count": result.metrics["neutral_exit_count"],
        "exposure_pct": result.metrics["exposure_pct"],
    }


def result_row(
    result: Any,
    variant: str,
    formation: Any,
    *,
    window: str,
    scenario: str,
) -> dict[str, Any]:
    return {
        "variant": variant,
        "window": window,
        "scenario": scenario,
        **result.metrics,
        **add_aux_metrics(result, variant, formation),
    }


def clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(item) for item in value]
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def main() -> None:
    args = parse_args()
    if args.self_test:
        assert target_state(0, 12.0, 10.0, 2.0, 0, TRI_CONFIG)[0] == 1
        assert target_state(1, 8.0, 10.0, 2.0, 3, TRI_CONFIG)[0] == -1
        assert target_state(1, 10.1, 10.0, 2.0, 3, TRI_CONFIG)[0] == 0
        assert target_state(-1, 10.1, 10.0, 2.0, 2, TRI_CONFIG)[0] == -1
        test_streak = neutral_streak(
            np.array([10.0, 10.1, 10.2, 11.0]),
            np.array([10.0] * 4),
            np.array([2.0] * 4),
            0.25,
        )
        assert test_streak.tolist() == [1, 2, 3, 0]
        print("self-test passed: state transitions and neutral streak")
        return

    formation = load_pinned(
        FORMATION_PATH,
        FORMATION_SHA256,
        "hype_three_state_formation",
    )
    engine = formation.load_pinned(
        formation.ENGINE_PATH,
        formation.ENGINE_SHA256,
        "hype_three_state_engine",
    )
    base = formation.load_pinned(
        formation.BASE_PATH,
        formation.BASE_SHA256,
        "hype_three_state_base",
    )
    selected = formation.read_pinned_json(
        formation.SUMMARY_PATH,
        formation.SUMMARY_SHA256,
    )["historically_profitable_all_checks"][0]
    long_config = engine.Config(**selected["long_config"])
    short_config = engine.Config(**selected["short_config"])
    v2_backtest = formation.build_reversal_backtest(engine)

    parent = base.load_parent()
    market_engine = parent.load_engine()
    hourly, hourly_quality = market_engine.audit_and_load_market(ROOT, "1h")
    funding, funding_quality = market_engine.load_and_audit_funding(ROOT)
    hourly["ts"] = pd.to_datetime(hourly["ts"], utc=True)
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
    historical_hourly = hourly.loc[
        hourly["ts"] <= formation.HISTORICAL_HOUR_CUTOFF
    ].copy()
    historical_funding = funding.loc[
        funding["ts"] <= formation.HISTORICAL_HOUR_CUTOFF
    ].copy()

    def build(phase: int, *, latest: bool = False) -> tuple[Any, Any]:
        source_hourly = hourly if latest else historical_hourly
        source_funding = funding if latest else historical_funding
        book = base.build_book(
            parent,
            source_hourly,
            hourly_quality,
            source_funding,
            funding_quality,
            phase_hours=phase,
        )
        return book, engine.build_features(book, source_hourly, source_funding)

    books = {}
    features = {}
    for phase in (0, 12):
        books[phase], features[phase] = build(phase)
    book = books[0]
    split = int(pd.DatetimeIndex(book.ts).searchsorted(HOLDOUT_START))
    windows = {
        "prefit": (0, split),
        "last_90d_flat": (split, book.count),
        "full": (0, book.count),
    }
    state_configs = {
        VARIANT_BINARY: BINARY_CONFIG,
        VARIANT_TRI: TRI_CONFIG,
    }

    def run(
        variant: str,
        target_book: Any,
        target_features: Any,
        *,
        start: int,
        end: int,
        slippage: float,
        signal_lag: int = 0,
        include_funding: bool = True,
        retain: bool = False,
    ) -> Any:
        if variant == VARIANT_V2:
            return control_result(
                v2_backtest,
                long_config,
                short_config,
                target_book,
                target_features,
                engine,
                start=start,
                end=end,
                slippage=slippage,
                signal_lag=signal_lag,
                include_funding=include_funding,
                retain=retain,
            )
        return hysteresis_backtest(
            engine,
            target_book,
            target_features,
            state_configs[variant],
            start_index=start,
            terminal_index=end,
            slippage=slippage,
            signal_lag=signal_lag,
            include_funding=include_funding,
            retain=retain,
        )

    variants = (VARIANT_V2, VARIANT_BINARY, VARIANT_TRI)
    rows: list[dict[str, Any]] = []
    recent_rows: list[dict[str, Any]] = []
    rolling_rows: list[dict[str, Any]] = []
    full_results: dict[str, Any] = {}
    for variant in variants:
        for window, (start, end) in windows.items():
            result = run(
                variant,
                book,
                features[0],
                start=start,
                end=end,
                slippage=engine.BASE_SLIPPAGE,
                retain=window == "full",
            )
            rows.append(
                result_row(
                    result,
                    variant,
                    formation,
                    window=window,
                    scenario="base_4bps",
                )
            )
            if window == "full":
                full_results[variant] = result
                recent_rows.extend(
                    {
                        "variant": variant,
                        **item,
                    }
                    for item in engine.recent_slices(result)
                )
        for scenario, slippage, lag, include_funding in (
            ("stress_8bps", engine.STRESS_SLIPPAGE, 0, True),
            ("one_day_extra_delay", engine.BASE_SLIPPAGE, 1, True),
            ("zero_funding", engine.BASE_SLIPPAGE, 0, False),
        ):
            result = run(
                variant,
                book,
                features[0],
                start=0,
                end=book.count,
                slippage=slippage,
                signal_lag=lag,
                include_funding=include_funding,
                retain=True,
            )
            rows.append(
                result_row(
                    result,
                    variant,
                    formation,
                    window="full",
                    scenario=scenario,
                )
            )
        phase12 = run(
            variant,
            books[12],
            features[12],
            start=0,
            end=books[12].count,
            slippage=engine.BASE_SLIPPAGE,
            retain=True,
        )
        rows.append(
            result_row(
                phase12,
                variant,
                formation,
                window="full",
                scenario="phase_12h",
            )
        )
        start = 0
        while start + 90 <= book.count:
            result = run(
                variant,
                book,
                features[0],
                start=start,
                end=start + 90,
                slippage=engine.BASE_SLIPPAGE,
                retain=True,
            )
            rolling_rows.append(
                {
                    "variant": variant,
                    "window_index": len(
                        [
                            row
                            for row in rolling_rows
                            if row["variant"] == variant
                        ]
                    ),
                    **result.metrics,
                    **add_aux_metrics(result, variant, formation),
                }
            )
            start += 30

    if not math.isclose(
        full_results[VARIANT_V2].metrics["equity_multiple"],
        V2_EQUITY_MULTIPLE,
        rel_tol=1e-10,
        abs_tol=1e-10,
    ):
        raise RuntimeError("V2 control anchor drift")

    phase_books: dict[int, Any] = {}
    phase_features: dict[int, Any] = {}
    phase_errors: dict[int, str] = {}
    for phase in range(24):
        try:
            phase_books[phase], phase_features[phase] = build(
                phase,
                latest=True,
            )
        except RuntimeError as exc:
            phase_errors[phase] = str(exc)
    phase_rows: list[dict[str, Any]] = []
    for variant in variants:
        for phase in range(24):
            if phase in phase_errors:
                continue
            result = run(
                variant,
                phase_books[phase],
                phase_features[phase],
                start=0,
                end=phase_books[phase].count,
                slippage=engine.BASE_SLIPPAGE,
                retain=True,
            )
            phase_rows.append(
                {
                    "variant": variant,
                    "phase_hours": phase,
                    **result.metrics,
                    **add_aux_metrics(result, variant, formation),
                }
            )

    latest_book, latest_features = build(0, latest=True)
    latest_rows = []
    for variant in variants:
        result = run(
            variant,
            latest_book,
            latest_features,
            start=0,
            end=latest_book.count,
            slippage=engine.BASE_SLIPPAGE,
            retain=True,
        )
        latest_rows.append(
            result_row(
                result,
                variant,
                formation,
                window="latest_extension",
                scenario="base_4bps",
            )
        )

    phase_frame = pd.DataFrame(phase_rows)
    rolling_frame = pd.DataFrame(rolling_rows)
    phase_summary = {}
    rolling_summary = {}
    for variant in variants:
        selected_phase = phase_frame.loc[phase_frame["variant"].eq(variant)]
        selected_rolling = rolling_frame.loc[
            rolling_frame["variant"].eq(variant)
        ]
        phase_summary[variant] = {
            "valid": int(len(selected_phase)),
            "positive": int((selected_phase["net_return_pct"] > 0.0).sum()),
            "median_return_pct": float(
                selected_phase["net_return_pct"].median()
            ),
            "min_return_pct": float(selected_phase["net_return_pct"].min()),
            "worst_mdd_pct": float(
                selected_phase["max_drawdown_pct"].min()
            ),
            "bankrupt": int(selected_phase["bankrupt_intraday"].sum()),
        }
        rolling_summary[variant] = {
            "count": int(len(selected_rolling)),
            "positive": int(
                (selected_rolling["net_return_pct"] > 0.0).sum()
            ),
            "median_return_pct": float(
                selected_rolling["net_return_pct"].median()
            ),
            "min_return_pct": float(
                selected_rolling["net_return_pct"].min()
            ),
            "worst_mdd_pct": float(
                selected_rolling["max_drawdown_pct"].min()
            ),
            "bankrupt": int(selected_rolling["bankrupt_intraday"].sum()),
        }

    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "HYPE-1D-MA7-Asymmetric-Body-Trend",
        "status": "diagnostic only; V2 unchanged; no V3 registration",
        "contract": (
            "specs/hype-1d-ma7-abt-three-state-hysteresis-contract-"
            "2026-08-07.md"
        ),
        "configs": {
            VARIANT_BINARY: {
                "outer_atr": 0.75,
                "neutral_exit": False,
            },
            VARIANT_TRI: {
                "outer_atr": 0.75,
                "neutral_atr": 0.25,
                "neutral_days": 3,
            },
        },
        "pins": {
            "formation_sha256": FORMATION_SHA256,
            "engine_sha256": formation.ENGINE_SHA256,
            "base_sha256": formation.BASE_SHA256,
        },
        "data_quality": {
            "hourly": hourly_quality,
            "funding": funding_quality,
        },
        "phase_errors": phase_errors,
        "phase_summary": phase_summary,
        "rolling_90d_summary": rolling_summary,
        "evidence_role": (
            "post-reveal mechanism diagnostic; not OOS or promotion evidence"
        ),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"hype_1d_ma7_three_state_hysteresis_{args.run_date}"
    (ARTIFACT_DIR / f"{stem}_summary.json").write_text(
        json.dumps(clean(payload), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    pd.DataFrame(rows).to_csv(
        ARTIFACT_DIR / f"{stem}_metrics.csv",
        index=False,
    )
    pd.DataFrame(recent_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_recent.csv",
        index=False,
    )
    rolling_frame.to_csv(
        ARTIFACT_DIR / f"{stem}_rolling_90d.csv",
        index=False,
    )
    phase_frame.to_csv(
        ARTIFACT_DIR / f"{stem}_phase24.csv",
        index=False,
    )
    pd.DataFrame(latest_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_latest.csv",
        index=False,
    )
    for variant in (VARIANT_BINARY, VARIANT_TRI):
        pd.DataFrame(full_results[variant].trades).to_csv(
            ARTIFACT_DIR / f"{stem}_{variant.lower()}_trades.csv",
            index=False,
        )
    pd.DataFrame(full_results[VARIANT_TRI].path).to_csv(
        ARTIFACT_DIR / f"{stem}_{VARIANT_TRI.lower()}_path.csv",
        index=False,
    )
    full_table = pd.DataFrame(rows)
    full_table = full_table.loc[
        full_table["window"].eq("full")
        & full_table["scenario"].eq("base_4bps")
    ]
    print(
        full_table[
            [
                "variant",
                "net_return_pct",
                "max_drawdown_pct",
                "sharpe",
                "closed_trades",
                "flip_count",
                "neutral_exit_count",
                "exposure_pct",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
