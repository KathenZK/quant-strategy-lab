from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import random
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/btc/1d-qingze-critical-point-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
BASELINE_PATH = (
    FAMILY_DIR / "scripts/research_btc_1d_qingze_critical_point.py"
)
BASELINE_SHA256 = (
    "9f61e8cf79d281255ee216c74014454a5a9d23a6e02ac2574e199b3d4030e182"
)

TRAIN_START = pd.Timestamp("2024-07-31T00:00:00Z")
TRAIN_END_EXCLUSIVE = pd.Timestamp("2026-01-02T00:00:00Z")
VALIDATION_START = TRAIN_END_EXCLUSIVE
VALIDATION_END_EXCLUSIVE = pd.Timestamp("2026-07-30T00:00:00Z")
FOLDS = (
    (
        "fold_1",
        pd.Timestamp("2024-07-31T00:00:00Z"),
        pd.Timestamp("2025-02-01T00:00:00Z"),
    ),
    (
        "fold_2",
        pd.Timestamp("2025-02-01T00:00:00Z"),
        pd.Timestamp("2025-08-01T00:00:00Z"),
    ),
    (
        "fold_3",
        pd.Timestamp("2025-08-01T00:00:00Z"),
        pd.Timestamp("2026-01-02T00:00:00Z"),
    ),
)
DEFAULT_SEED = 20260807
DEFAULT_SAMPLES = 20_000


@dataclass(frozen=True, slots=True)
class SearchConfig:
    ma_days: int
    confirm_days: int
    deviation_min: float
    breakout_days: int
    impulse_min: float
    volume_lookback: int
    volume_multiplier: float
    narrow_days: int
    narrow_range_max: float
    b_impulse_max: float
    signal_mode: str
    atr_days: int
    stop_atr: float
    pyramiding: bool

    @property
    def key(self) -> str:
        return json.dumps(
            asdict(self), sort_keys=True, separators=(",", ":")
        )


BASELINE_CONFIG = SearchConfig(
    ma_days=60,
    confirm_days=3,
    deviation_min=0.015,
    breakout_days=20,
    impulse_min=0.02,
    volume_lookback=5,
    volume_multiplier=1.5,
    narrow_days=5,
    narrow_range_max=0.015,
    b_impulse_max=0.02,
    signal_mode="AB",
    atr_days=14,
    stop_atr=3.0,
    pyramiding=True,
)

MA_DAYS = (40, 55, 60)
CONFIRM_DAYS = (1, 2, 3)
DEVIATIONS = (0.0, 0.005, 0.01, 0.015, 0.02)
BREAKOUT_DAYS = (10, 15, 20, 30)
IMPULSE_MINS = (0.01, 0.015, 0.02, 0.03)
VOLUME_LOOKBACKS = (3, 5, 10)
VOLUME_MULTIPLIERS = (1.0, 1.25, 1.5, 1.75)
NARROW_DAYS = (3, 5, 7)
NARROW_RANGES = (0.015, 0.02, 0.025, 0.03)
B_IMPULSE_MAXES = (0.015, 0.02, 0.03)
SIGNAL_MODES = ("A", "B", "AB")
ATR_DAYS = (10, 14, 20)
STOP_ATRS = (2.0, 3.0, 4.0, 5.0)
PYRAMIDING = (False, True)


@dataclass(slots=True)
class Cache:
    ts: pd.DatetimeIndex
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray
    funding: np.ndarray
    sma: dict[int, np.ndarray]
    atr: dict[int, np.ndarray]
    prior_high: dict[int, np.ndarray]
    prior_low: dict[int, np.ndarray]
    prior_volume: dict[int, np.ndarray]
    prior_all_narrow: dict[tuple[int, float], np.ndarray]
    return_1d: np.ndarray


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "One-round development search and locked holdout validation for "
            "BTC 1D Qingze critical-point trend."
        )
    )
    parser.add_argument(
        "--run-date", default=datetime.now(UTC).date().isoformat()
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--samples", type=int, default=DEFAULT_SAMPLES)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def load_baseline() -> Any:
    digest = hashlib.sha256(BASELINE_PATH.read_bytes()).hexdigest()
    if digest != BASELINE_SHA256:
        raise RuntimeError(
            f"baseline engine drift: expected {BASELINE_SHA256}, got {digest}"
        )
    spec = importlib.util.spec_from_file_location(
        "btc_qingze_baseline_for_search", BASELINE_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {BASELINE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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


def rolling_prior(
    values: pd.Series, window: int, kind: str
) -> np.ndarray:
    shifted = values.shift(1).rolling(window)
    if kind == "max":
        output = shifted.max()
    elif kind == "min":
        output = shifted.min()
    elif kind == "mean":
        output = shifted.mean()
    else:
        raise ValueError(kind)
    return output.to_numpy("float64")


def build_cache(daily: pd.DataFrame) -> Cache:
    previous_close = daily["close"].shift(1)
    true_range = pd.concat(
        [
            daily["high"] - daily["low"],
            (daily["high"] - previous_close).abs(),
            (daily["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    daily_range = (daily["high"] - daily["low"]) / daily["close"]
    prior_all_narrow: dict[tuple[int, float], np.ndarray] = {}
    for days in NARROW_DAYS:
        for threshold in NARROW_RANGES:
            prior_all_narrow[(days, threshold)] = (
                daily_range.lt(threshold)
                .shift(1)
                .rolling(days)
                .sum()
                .eq(days)
                .to_numpy(bool)
            )
    extreme_windows = sorted(set(BREAKOUT_DAYS + NARROW_DAYS))
    return Cache(
        ts=pd.DatetimeIndex(daily["ts"]),
        open=daily["open"].to_numpy("float64"),
        high=daily["high"].to_numpy("float64"),
        low=daily["low"].to_numpy("float64"),
        close=daily["close"].to_numpy("float64"),
        volume=daily["volume"].to_numpy("float64"),
        funding=daily["funding_rate_sum"].to_numpy("float64"),
        sma={
            days: daily["close"].rolling(days).mean().to_numpy("float64")
            for days in MA_DAYS
        },
        atr={
            days: true_range.rolling(days).mean().to_numpy("float64")
            for days in ATR_DAYS
        },
        prior_high={
            days: rolling_prior(daily["high"], days, "max")
            for days in extreme_windows
        },
        prior_low={
            days: rolling_prior(daily["low"], days, "min")
            for days in extreme_windows
        },
        prior_volume={
            days: rolling_prior(daily["volume"], days, "mean")
            for days in VOLUME_LOOKBACKS
        },
        prior_all_narrow=prior_all_narrow,
        return_1d=daily["close"].pct_change().to_numpy("float64"),
    )


def trend_for(
    cache: Cache,
    config: SearchConfig,
    memo: dict[tuple[int, int, float], np.ndarray],
) -> np.ndarray:
    key = (config.ma_days, config.confirm_days, config.deviation_min)
    if key in memo:
        return memo[key]
    close = cache.close
    sma = cache.sma[config.ma_days]
    above = close > sma
    below = close < sma
    above_confirmed = (
        pd.Series(above)
        .rolling(config.confirm_days)
        .sum()
        .eq(config.confirm_days)
        .to_numpy(bool)
    )
    below_confirmed = (
        pd.Series(below)
        .rolling(config.confirm_days)
        .sum()
        .eq(config.confirm_days)
        .to_numpy(bool)
    )
    deviation = close / sma - 1.0
    slope = np.r_[np.nan, np.diff(sma)]
    trend = np.zeros(len(close), dtype=np.int8)
    trend[
        above_confirmed
        & (deviation >= config.deviation_min)
        & (slope > 0)
    ] = 1
    trend[
        below_confirmed
        & (deviation <= -config.deviation_min)
        & (slope < 0)
    ] = -1
    memo[key] = trend
    return trend


def signals_for(
    cache: Cache,
    config: SearchConfig,
    trend_memo: dict[tuple[int, int, float], np.ndarray],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    trend = trend_for(cache, config, trend_memo)
    volume_ok = cache.volume >= (
        config.volume_multiplier
        * cache.prior_volume[config.volume_lookback]
    )
    a_long = (
        (trend == 1)
        & (cache.close > cache.prior_high[config.breakout_days])
        & (cache.return_1d > config.impulse_min)
        & volume_ok
    )
    a_short = (
        (trend == -1)
        & (cache.close < cache.prior_low[config.breakout_days])
        & (cache.return_1d < -config.impulse_min)
        & volume_ok
    )
    narrow = cache.prior_all_narrow[
        (config.narrow_days, config.narrow_range_max)
    ]
    b_long = (
        (trend == 1)
        & narrow
        & (cache.close > cache.prior_high[config.narrow_days])
        & (cache.return_1d > 0)
        & (cache.return_1d <= config.b_impulse_max)
        & volume_ok
    )
    b_short = (
        (trend == -1)
        & narrow
        & (cache.close < cache.prior_low[config.narrow_days])
        & (cache.return_1d < 0)
        & (cache.return_1d >= -config.b_impulse_max)
        & volume_ok
    )
    signal = np.zeros(len(cache.close), dtype=np.int8)
    signal_type = np.zeros(len(cache.close), dtype=np.int8)
    if config.signal_mode in ("A", "AB"):
        signal[a_long] = 1
        signal[a_short] = -1
        signal_type[a_long | a_short] = 1
    if config.signal_mode in ("B", "AB"):
        empty = signal == 0
        signal[empty & b_long] = 1
        signal[empty & b_short] = -1
        signal_type[empty & (b_long | b_short)] = 2
    return trend, signal, signal_type


def drawdown(values: list[float]) -> float:
    peak = -math.inf
    worst = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            worst = min(worst, value / peak - 1.0)
    return worst


def segment_indices(
    cache: Cache, start: pd.Timestamp, end_exclusive: pd.Timestamp
) -> tuple[int, int]:
    left = int(cache.ts.searchsorted(start, side="left"))
    right = int(cache.ts.searchsorted(end_exclusive, side="left"))
    if left >= right:
        raise RuntimeError(f"empty segment {start} to {end_exclusive}")
    return left, right


def run_segment(
    cache: Cache,
    config: SearchConfig,
    trend: np.ndarray,
    signal: np.ndarray,
    signal_type: np.ndarray,
    start: int,
    end: int,
    *,
    detail: bool = False,
) -> dict[str, Any]:
    fee_rate = 0.001
    slippage = 0.0004
    weights = (0.20, 0.12, 0.08)
    add_levels = (1.0, 2.0)
    atr = cache.atr[config.atr_days]

    equity = 1.0
    qty = 0.0
    side = 0
    stop = math.nan
    entry_atr = math.nan
    initial_fill = math.nan
    tranches = 0
    pending_entry = int(signal[start - 1]) if start > 0 else 0
    pending_signal_type = int(signal_type[start - 1]) if start > 0 else 0
    pending_exit = False
    pending_add = False
    campaign: dict[str, Any] | None = None
    trades: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    equity_values: list[float] = []
    path_rows: list[dict[str, Any]] = []
    trade_returns: list[float] = []
    trade_id = 0
    fees_paid = 0.0
    funding_paid = 0.0
    turnover = 0.0
    exposure_days = 0
    max_exposure = 0.0

    def order_fill(price: float, order_side: int) -> float:
        return price * (1.0 + order_side * slippage)

    for i in range(start, end):
        ts = cache.ts[i]
        open_price = cache.open[i]
        close = cache.close[i]
        action_parts: list[str] = []
        if i > start:
            equity += qty * (open_price - cache.close[i - 1])

        def close_position(raw_price: float, mark: float, reason: str) -> None:
            nonlocal equity, qty, side, campaign, tranches, stop
            nonlocal fees_paid, turnover
            effective = order_fill(raw_price, -side)
            equity += qty * (effective - mark)
            notional = abs(qty) * effective
            fee = notional * fee_rate
            equity -= fee
            fees_paid += fee
            turnover += notional
            if detail:
                events.append(
                    {
                        "trade_id": trade_id,
                        "ts": ts,
                        "event": "exit",
                        "side": "long" if side > 0 else "short",
                        "raw_price": raw_price,
                        "fill_price": effective,
                        "notional": notional,
                        "fee": fee,
                        "reason": reason,
                    }
                )
            if campaign is None:
                raise RuntimeError("position without campaign")
            net_return = equity / float(campaign["entry_equity"]) - 1.0
            trade_returns.append(net_return)
            if detail:
                trades.append(
                    {
                        **campaign,
                        "exit_ts": ts,
                        "exit_price": effective,
                        "exit_reason": reason,
                        "tranches": tranches,
                        "net_return_pct": net_return * 100.0,
                        "exit_equity": equity,
                    }
                )
            qty = 0.0
            side = 0
            campaign = None
            tranches = 0
            stop = math.nan

        if pending_exit and side != 0:
            close_position(open_price, open_price, "opposite_trend_next_open")
            action_parts.append("exit_opposite_trend")
        pending_exit = False

        if (
            pending_entry != 0
            and side == 0
            and np.isfinite(atr[i - 1] if i > 0 else math.nan)
        ):
            trade_id += 1
            side = pending_entry
            entry_atr = float(atr[i - 1])
            entry_equity = equity
            effective = order_fill(open_price, side)
            notional = equity * weights[0]
            added_qty = side * notional / effective
            fee = notional * fee_rate
            equity -= fee
            equity += added_qty * (open_price - effective)
            qty += added_qty
            fees_paid += fee
            turnover += notional
            initial_fill = effective
            tranches = 1
            stop = initial_fill - side * config.stop_atr * entry_atr
            campaign = {
                "trade_id": trade_id,
                "side": "long" if side > 0 else "short",
                "signal_type": "A" if pending_signal_type == 1 else "B",
                "signal_ts": cache.ts[i - 1],
                "entry_ts": ts,
                "entry_price": initial_fill,
                "entry_equity": entry_equity,
                "entry_atr": entry_atr,
            }
            if detail:
                events.append(
                    {
                        "trade_id": trade_id,
                        "ts": ts,
                        "event": "entry",
                        "side": campaign["side"],
                        "raw_price": open_price,
                        "fill_price": effective,
                        "notional": notional,
                        "fee": fee,
                    }
                )
            action_parts.append(f"entry_{campaign['signal_type']}")
        pending_entry = 0
        pending_signal_type = 0

        if (
            pending_add
            and side != 0
            and config.pyramiding
            and tranches < len(weights)
        ):
            effective = order_fill(open_price, side)
            notional = equity * weights[tranches]
            added_qty = side * notional / effective
            fee = notional * fee_rate
            equity -= fee
            equity += added_qty * (open_price - effective)
            qty += added_qty
            fees_paid += fee
            turnover += notional
            if detail:
                events.append(
                    {
                        "trade_id": trade_id,
                        "ts": ts,
                        "event": f"add_{tranches}",
                        "side": "long" if side > 0 else "short",
                        "raw_price": open_price,
                        "fill_price": effective,
                        "notional": notional,
                        "fee": fee,
                    }
                )
            tranches += 1
            action_parts.append("add")
        pending_add = False

        stopped = False
        if side > 0 and cache.low[i] <= stop:
            close_position(min(open_price, stop), open_price, "stop_or_trail")
            action_parts.append("stop")
            stopped = True
        elif side < 0 and cache.high[i] >= stop:
            close_position(max(open_price, stop), open_price, "stop_or_trail")
            action_parts.append("stop")
            stopped = True

        if not stopped and side != 0:
            equity += qty * (close - open_price)
            funding_cashflow = (
                -side * abs(qty) * close * cache.funding[i]
            )
            equity += funding_cashflow
            funding_paid -= funding_cashflow

        exposure = abs(qty) * close / equity if side and equity > 0 else 0.0
        max_exposure = max(max_exposure, exposure)
        exposure_days += int(side != 0)
        equity_values.append(equity)
        if detail:
            path_rows.append(
                {
                    "ts": ts,
                    "open": open_price,
                    "high": cache.high[i],
                    "low": cache.low[i],
                    "close": close,
                    "volume": cache.volume[i],
                    "sma": cache.sma[config.ma_days][i],
                    "atr": atr[i],
                    "trend": int(trend[i]),
                    "position_side": side,
                    "exposure": exposure,
                    "stop": stop if side else math.nan,
                    "equity": equity,
                    "action": (
                        ";".join(action_parts) if action_parts else "hold"
                    ),
                }
            )

        if side != 0:
            if int(trend[i]) == -side:
                pending_exit = True
            if config.pyramiding and tranches < len(weights):
                threshold = (
                    initial_fill
                    + side * add_levels[tranches - 1] * entry_atr
                )
                if (side > 0 and close >= threshold) or (
                    side < 0 and close <= threshold
                ):
                    pending_add = True
            if np.isfinite(atr[i]):
                candidate = close - side * config.stop_atr * atr[i]
                stop = (
                    max(stop, candidate) if side > 0 else min(stop, candidate)
                )
        else:
            if signal[i] and np.isfinite(atr[i]):
                pending_entry = int(signal[i])
                pending_signal_type = int(signal_type[i])

    if side != 0:
        ts = cache.ts[end - 1] + pd.Timedelta(days=1)
        close_position(
            cache.close[end - 1],
            cache.close[end - 1],
            "period_end_mark",
        )
        equity_values[-1] = equity
        if detail:
            path_rows[-1]["equity"] = equity
            path_rows[-1]["position_side"] = 0
            path_rows[-1]["exposure"] = 0.0
            path_rows[-1]["action"] += ";period_end_mark"

    returns = pd.Series(equity_values, dtype=float).pct_change().dropna()
    negative = returns.loc[returns < 0]
    gains = sum(value for value in trade_returns if value > 0)
    losses = abs(sum(value for value in trade_returns if value < 0))
    metrics = {
        "start_ts": cache.ts[start],
        "end_ts": cache.ts[end - 1],
        "bars": end - start,
        "net_return_pct": (equity - 1.0) * 100.0,
        "max_drawdown_pct": drawdown(equity_values) * 100.0,
        "sharpe": (
            float(returns.mean() / returns.std() * math.sqrt(365.25))
            if returns.std() > 0
            else math.nan
        ),
        "sortino": (
            float(returns.mean() / negative.std() * math.sqrt(365.25))
            if negative.std() > 0
            else math.nan
        ),
        "closed_trades": len(trade_returns),
        "win_rate_pct": (
            sum(value > 0 for value in trade_returns)
            / len(trade_returns)
            * 100.0
            if trade_returns
            else math.nan
        ),
        "profit_factor": gains / losses if losses else math.nan,
        "avg_trade_pct": (
            float(np.mean(trade_returns) * 100.0)
            if trade_returns
            else math.nan
        ),
        "max_exposure_pct": max_exposure * 100.0,
        "time_in_market_pct": exposure_days / (end - start) * 100.0,
        "fees_paid_equity": fees_paid,
        "funding_paid_equity": funding_paid,
        "turnover_equity": turnover,
    }
    result: dict[str, Any] = {"metrics": metrics}
    if detail:
        result["path"] = pd.DataFrame(path_rows)
        result["trades"] = pd.DataFrame(trades)
        result["events"] = pd.DataFrame(events)
    return result


def random_config(rng: random.Random) -> SearchConfig:
    return SearchConfig(
        ma_days=rng.choice(MA_DAYS),
        confirm_days=rng.choice(CONFIRM_DAYS),
        deviation_min=rng.choice(DEVIATIONS),
        breakout_days=rng.choice(BREAKOUT_DAYS),
        impulse_min=rng.choice(IMPULSE_MINS),
        volume_lookback=rng.choice(VOLUME_LOOKBACKS),
        volume_multiplier=rng.choice(VOLUME_MULTIPLIERS),
        narrow_days=rng.choice(NARROW_DAYS),
        narrow_range_max=rng.choice(NARROW_RANGES),
        b_impulse_max=rng.choice(B_IMPULSE_MAXES),
        signal_mode=rng.choice(SIGNAL_MODES),
        atr_days=rng.choice(ATR_DAYS),
        stop_atr=rng.choice(STOP_ATRS),
        pyramiding=rng.choice(PYRAMIDING),
    )


def unique_configs(samples: int, seed: int) -> list[SearchConfig]:
    rng = random.Random(seed)
    configs = [BASELINE_CONFIG]
    seen = {BASELINE_CONFIG.key}
    while len(configs) < samples:
        config = random_config(rng)
        if config.key not in seen:
            configs.append(config)
            seen.add(config.key)
    return configs


def selection_score(
    full: dict[str, Any], fold_metrics: list[dict[str, Any]]
) -> tuple[float, bool, int, int]:
    returns = [float(item["net_return_pct"]) for item in fold_metrics]
    active_folds = sum(int(item["closed_trades"]) > 0 for item in fold_metrics)
    profitable_folds = sum(value > 0 for value in returns)
    eligible = bool(
        int(full["closed_trades"]) >= 6
        and float(full["max_drawdown_pct"]) >= -20.0
        and active_folds >= 2
    )
    score = (
        min(returns)
        + float(np.median(returns))
        + 0.25 * float(full["net_return_pct"])
        - 0.50 * abs(float(full["max_drawdown_pct"]))
    )
    return score if eligible else -math.inf, eligible, active_folds, profitable_folds


def evaluate_config(
    cache: Cache,
    config: SearchConfig,
    trend_memo: dict[tuple[int, int, float], np.ndarray],
) -> dict[str, Any]:
    trend, signal, signal_type = signals_for(cache, config, trend_memo)
    train_start, train_end = segment_indices(
        cache, TRAIN_START, TRAIN_END_EXCLUSIVE
    )
    full = run_segment(
        cache,
        config,
        trend,
        signal,
        signal_type,
        train_start,
        train_end,
    )["metrics"]
    folds = []
    for name, start_ts, end_ts in FOLDS:
        start, end = segment_indices(cache, start_ts, end_ts)
        metrics = run_segment(
            cache,
            config,
            trend,
            signal,
            signal_type,
            start,
            end,
        )["metrics"]
        folds.append({"name": name, **metrics})
    score, eligible, active_folds, profitable_folds = selection_score(
        full, folds
    )
    return {
        "config_json": config.key,
        **asdict(config),
        "eligible": eligible,
        "score": score,
        "active_folds": active_folds,
        "profitable_folds": profitable_folds,
        **{f"train_{key}": value for key, value in full.items()},
        **{
            f"{fold['name']}_{key}": value
            for fold in folds
            for key, value in fold.items()
            if key != "name"
        },
    }


def evaluate_holdout(
    cache: Cache,
    config: SearchConfig,
    trend_memo: dict[tuple[int, int, float], np.ndarray],
    *,
    detail: bool = False,
) -> dict[str, Any]:
    trend, signal, signal_type = signals_for(cache, config, trend_memo)
    start, end = segment_indices(
        cache, VALIDATION_START, VALIDATION_END_EXCLUSIVE
    )
    return run_segment(
        cache,
        config,
        trend,
        signal,
        signal_type,
        start,
        end,
        detail=detail,
    )


def benchmark_return(
    cache: Cache, start_ts: pd.Timestamp, end_exclusive: pd.Timestamp
) -> float:
    start, end = segment_indices(cache, start_ts, end_exclusive)
    underlying = cache.close[end - 1] / cache.open[start] - 1.0
    return (
        0.40 * underlying - 2 * 0.40 * (0.001 + 0.0004)
    ) * 100.0


def self_test() -> None:
    rng = random.Random(DEFAULT_SEED)
    first = random_config(rng)
    assert first == random_config(random.Random(DEFAULT_SEED))
    assert BASELINE_CONFIG.key == json.dumps(
        asdict(BASELINE_CONFIG), sort_keys=True, separators=(",", ":")
    )
    score, eligible, active, profitable = selection_score(
        {
            "closed_trades": 8,
            "max_drawdown_pct": -10.0,
            "net_return_pct": 12.0,
        },
        [
            {"closed_trades": 2, "net_return_pct": 2.0},
            {"closed_trades": 3, "net_return_pct": 3.0},
            {"closed_trades": 3, "net_return_pct": 4.0},
        ],
    )
    assert eligible and active == 3 and profitable == 3 and np.isfinite(score)
    print("self-test: PASS")


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return
    baseline = load_baseline()
    hourly, funding, quality = baseline.load_and_audit()
    daily = baseline.aggregate_daily(hourly, funding)
    oi_dates = sorted(baseline.OI_ROOT.glob("date=*"))
    quality["open_interest"] = {
        "available_daily_partitions": len(oi_dates),
        "first_partition": oi_dates[0].name if oi_dates else None,
        "last_partition": oi_dates[-1].name if oi_dates else None,
        "usable_for_20d_filter": False,
        "treatment": (
            "not searched or used; insufficient coverage, and volume is not "
            "treated as an open-interest proxy"
        ),
    }
    cache = build_cache(daily)
    if cache.ts[0] != TRAIN_START:
        raise RuntimeError(f"unexpected first day: {cache.ts[0]}")
    if cache.ts[-1] != pd.Timestamp("2026-07-29T00:00:00Z"):
        raise RuntimeError(f"unexpected last day: {cache.ts[-1]}")

    configs = unique_configs(args.samples, args.seed)
    trend_memo: dict[tuple[int, int, float], np.ndarray] = {}
    rows = []
    for index, config in enumerate(configs, start=1):
        rows.append(evaluate_config(cache, config, trend_memo))
        if index % 2_000 == 0:
            print(f"evaluated {index}/{len(configs)}", flush=True)
    candidates = pd.DataFrame(rows)
    eligible = candidates.loc[candidates["eligible"]].copy()
    if eligible.empty:
        raise RuntimeError("no eligible development candidates")
    eligible = eligible.sort_values(
        ["score", "train_net_return_pct", "train_max_drawdown_pct"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    eligible["development_rank"] = np.arange(1, len(eligible) + 1)
    selected_row = eligible.iloc[0]
    selected = SearchConfig(
        **json.loads(str(selected_row["config_json"]))
    )

    validation_rows = []
    for row in eligible.head(20).itertuples(index=False):
        config = SearchConfig(**json.loads(row.config_json))
        metrics = evaluate_holdout(
            cache, config, trend_memo, detail=False
        )["metrics"]
        validation_rows.append(
            {
                "development_rank": int(row.development_rank),
                "config_json": row.config_json,
                "development_score": float(row.score),
                "development_net_return_pct": float(
                    row.train_net_return_pct
                ),
                "development_max_drawdown_pct": float(
                    row.train_max_drawdown_pct
                ),
                **{f"validation_{key}": value for key, value in metrics.items()},
            }
        )
    validation = pd.DataFrame(validation_rows)

    selected_validation = evaluate_holdout(
        cache, selected, trend_memo, detail=True
    )
    selected_trend, selected_signal, selected_signal_type = signals_for(
        cache, selected, trend_memo
    )
    development_start, development_end = segment_indices(
        cache, TRAIN_START, TRAIN_END_EXCLUSIVE
    )
    selected_development = run_segment(
        cache,
        selected,
        selected_trend,
        selected_signal,
        selected_signal_type,
        development_start,
        development_end,
        detail=True,
    )
    selected_train_row = selected_row.to_dict()
    baseline_train_row = candidates.loc[
        candidates["config_json"].eq(BASELINE_CONFIG.key)
    ].iloc[0].to_dict()
    baseline_validation = evaluate_holdout(
        cache, BASELINE_CONFIG, trend_memo, detail=False
    )["metrics"]
    train_benchmark = benchmark_return(
        cache, TRAIN_START, TRAIN_END_EXCLUSIVE
    )
    validation_benchmark = benchmark_return(
        cache, VALIDATION_START, VALIDATION_END_EXCLUSIVE
    )

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = "btc_1d_qingze_parameter_search"
    candidates_path = ARTIFACT_DIR / f"{stem}_candidates_{args.run_date}.csv"
    frontier_path = ARTIFACT_DIR / f"{stem}_frontier_{args.run_date}.csv"
    validation_path = (
        ARTIFACT_DIR / f"{stem}_validation_{args.run_date}.csv"
    )
    summary_path = ARTIFACT_DIR / f"{stem}_summary_{args.run_date}.json"
    path_path = (
        ARTIFACT_DIR / f"{stem}_selected_validation_path_{args.run_date}.csv"
    )
    trades_path = (
        ARTIFACT_DIR
        / f"{stem}_selected_validation_trades_{args.run_date}.csv"
    )
    events_path = (
        ARTIFACT_DIR
        / f"{stem}_selected_validation_events_{args.run_date}.csv"
    )
    recent_path = (
        ARTIFACT_DIR
        / f"{stem}_selected_validation_recent_{args.run_date}.csv"
    )
    chart_path = (
        ARTIFACT_DIR
        / f"{stem}_selected_validation_trade_path_{args.run_date}.html"
    )
    development_trades_path = (
        ARTIFACT_DIR
        / f"{stem}_selected_development_trades_{args.run_date}.csv"
    )

    candidates.to_csv(candidates_path, index=False)
    eligible.head(100).to_csv(frontier_path, index=False)
    validation.to_csv(validation_path, index=False)
    selected_validation["path"].to_csv(path_path, index=False)
    selected_validation["trades"].to_csv(trades_path, index=False)
    selected_validation["events"].to_csv(events_path, index=False)
    validation_recent = baseline.recent_slices(
        selected_validation["path"]
    )
    validation_recent = validation_recent.loc[
        validation_recent["window"].ne("1y")
    ].reset_index(drop=True)
    validation_recent.to_csv(recent_path, index=False)
    selected_development["trades"].to_csv(
        development_trades_path, index=False
    )
    chart_metrics = {
        **selected_validation["metrics"],
        "variant": "development_rank_1_locked_validation",
    }
    chart_path.write_text(
        baseline.render_chart(
            selected_validation["path"],
            selected_validation["trades"],
            chart_metrics,
        ),
        encoding="utf-8",
    )

    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "BTC-1D-Qingze-Critical-Point-Trend",
        "status": "explore / diagnostic-only / not promoted / not live-ready",
        "protocol": {
            "seed": args.seed,
            "sample_count": len(configs),
            "development_start": TRAIN_START,
            "development_end_inclusive": TRAIN_END_EXCLUSIVE
            - pd.Timedelta(days=1),
            "validation_start": VALIDATION_START,
            "validation_end_inclusive": VALIDATION_END_EXCLUSIVE
            - pd.Timedelta(days=1),
            "folds": [
                {
                    "name": name,
                    "start": start,
                    "end_inclusive": end - pd.Timedelta(days=1),
                }
                for name, start, end in FOLDS
            ],
            "eligibility": (
                "development closed_trades >= 6, MDD >= -20%, active in at "
                "least two development folds"
            ),
            "score": (
                "min(fold returns) + median(fold returns) + "
                "0.25*development return - 0.50*abs(development MDD)"
            ),
            "selection": (
                "rank 1 frozen before holdout; top-20 holdout is diagnostic "
                "only and cannot replace the primary"
            ),
            "search_space": {
                "ma_days": MA_DAYS,
                "confirm_days": CONFIRM_DAYS,
                "deviation_min": DEVIATIONS,
                "breakout_days": BREAKOUT_DAYS,
                "impulse_min": IMPULSE_MINS,
                "volume_lookback": VOLUME_LOOKBACKS,
                "volume_multiplier": VOLUME_MULTIPLIERS,
                "narrow_days": NARROW_DAYS,
                "narrow_range_max": NARROW_RANGES,
                "b_impulse_max": B_IMPULSE_MAXES,
                "signal_mode": SIGNAL_MODES,
                "atr_days": ATR_DAYS,
                "stop_atr": STOP_ATRS,
                "pyramiding": PYRAMIDING,
            },
        },
        "source_engine": {
            "path": str(BASELINE_PATH.relative_to(ROOT)),
            "sha256": BASELINE_SHA256,
        },
        "data_quality": quality,
        "selected": {
            "config": asdict(selected),
            "development": clean_json(selected_train_row),
            "validation": clean_json(selected_validation["metrics"]),
        },
        "baseline": {
            "config": asdict(BASELINE_CONFIG),
            "development": clean_json(baseline_train_row),
            "validation": clean_json(baseline_validation),
        },
        "benchmarks": {
            "development_40pct_buy_hold_return_pct": train_benchmark,
            "validation_40pct_buy_hold_return_pct": validation_benchmark,
        },
        "frontier_validation": clean_json(validation.to_dict("records")),
        "artifacts": {
            "candidates": str(candidates_path.relative_to(ROOT)),
            "frontier": str(frontier_path.relative_to(ROOT)),
            "validation": str(validation_path.relative_to(ROOT)),
            "selected_validation_path": str(path_path.relative_to(ROOT)),
            "selected_validation_trades": str(trades_path.relative_to(ROOT)),
            "selected_validation_events": str(events_path.relative_to(ROOT)),
            "selected_validation_recent": str(recent_path.relative_to(ROOT)),
            "selected_development_trades": str(
                development_trades_path.relative_to(ROOT)
            ),
            "selected_validation_trade_path_html": str(
                chart_path.relative_to(ROOT)
            ),
        },
    }
    summary_path.write_text(
        json.dumps(
            clean_json(payload),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    print("selected config")
    print(json.dumps(asdict(selected), ensure_ascii=False, indent=2))
    print("selected development")
    print(
        json.dumps(
            clean_json(selected_train_row), ensure_ascii=False, indent=2
        )
    )
    print("selected validation")
    print(
        json.dumps(
            clean_json(selected_validation["metrics"]),
            ensure_ascii=False,
            indent=2,
        )
    )
    print("baseline validation")
    print(
        json.dumps(
            clean_json(baseline_validation), ensure_ascii=False, indent=2
        )
    )
    print(f"Wrote {summary_path}")


if __name__ == "__main__":
    main()
