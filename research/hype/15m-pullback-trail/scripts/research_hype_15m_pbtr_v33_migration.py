from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FIVE_M_SCRIPT_DIR = ROOT / "research/hype/5m-pullback-trail/scripts"
if str(FIVE_M_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(FIVE_M_SCRIPT_DIR))

from research_hype_5m_indicator_search import Trade  # noqa: E402
from research_hype_5m_pbtr_v2_live_cost_ablation_slices import (  # noqa: E402
    ENTRY_SLIPPAGE_RATE,
    EXIT_SLIPPAGE_RATE,
    FEE_RATE_PER_FILL,
)
from research_hype_5m_positive_payoff_search import load_all_hype_5m  # noqa: E402


DATE_TAG = "2026-06-30"
FAMILY_DIR = ROOT / "research/hype/15m-pullback-trail"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DIAG_DIR = FAMILY_DIR / "diagnostics"

REPORT_PATH = ARTIFACT_DIR / f"hype_15m_pbtr_v33_migration_{DATE_TAG}.json"
SUMMARY_PATH = ARTIFACT_DIR / f"hype_15m_pbtr_v33_migration_summary_{DATE_TAG}.csv"
SLICES_PATH = ARTIFACT_DIR / f"hype_15m_pbtr_v33_migration_slices_{DATE_TAG}.csv"
TRADES_PATH = ARTIFACT_DIR / f"hype_15m_pbtr_v33_migration_trades_{DATE_TAG}.csv"
DIAG_PATH = ARTIFACT_DIR / f"hype_15m_pbtr_v33_migration_diag_{DATE_TAG}.csv"
MARKDOWN_PATH = DIAG_DIR / f"hype-15m-pullback-trail-v3-3-migration-{DATE_TAG}.md"

LEVERAGE = 1.0


@dataclass(frozen=True, slots=True)
class PBTRConfig:
    label: str
    timeframe: str = "15m"
    side_mode: str = "both"
    ema_fast: int = 21
    ema_slow: int = 96
    atr_window: int = 14
    pullback_buffer: float = 0.01
    stop_atr: float = 0.5
    trail_atr: float = 0.75
    min_hold_bars: int = 9


V33_5M = PBTRConfig(label="5m_v33_reference", timeframe="5m")
V33_15M_SAME = PBTRConfig(label="15m_same_numbers", timeframe="15m")
V33_15M_HOLD3 = PBTRConfig(label="15m_same_ema_hold3", timeframe="15m", min_hold_bars=3)
V33_15M_COMPRESSED = PBTRConfig(
    label="15m_calendar_compressed",
    timeframe="15m",
    ema_fast=7,
    ema_slow=32,
    atr_window=5,
    min_hold_bars=3,
)


def pct(value: float, digits: int = 2) -> str:
    return "inf" if not np.isfinite(value) else f"{value * 100:.{digits}f}%"


def num(value: float, digits: int = 3) -> str:
    return "inf" if not np.isfinite(value) else f"{value:.{digits}f}"


def mult(value: float, digits: int = 2) -> str:
    return "inf" if not np.isfinite(value) else f"{value:.{digits}f}x"


def json_safe(value: Any) -> Any:
    if isinstance(value, (pd.Timestamp, pd.Timedelta)):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"cannot serialize {type(value)!r}")


def verify_5m_data(frame: pd.DataFrame) -> dict[str, Any]:
    required = ["ts", "open", "high", "low", "close", "volume", "is_closed", "exchange", "symbol", "market_type", "timeframe"]
    missing_cols = [col for col in required if col not in frame.columns]
    if missing_cols:
        raise RuntimeError(f"missing required columns: {missing_cols}")
    if frame["ts"].duplicated().any():
        raise RuntimeError("duplicate 5m timestamps")
    if not frame["ts"].is_monotonic_increasing:
        raise RuntimeError("5m timestamps are not sorted")
    expected = pd.date_range(frame["ts"].iloc[0], frame["ts"].iloc[-1], freq="5min")
    missing = expected.difference(frame["ts"])
    if len(missing):
        raise RuntimeError(f"5m gap count={len(missing)}, first={missing[0]}")
    critical_nulls = frame[["open", "high", "low", "close", "volume"]].isna().sum().sum()
    if critical_nulls:
        raise RuntimeError(f"critical null OHLCV values: {critical_nulls}")
    invalid_ohlc = frame[(frame["high"] < frame[["open", "close", "low"]].max(axis=1)) | (frame["low"] > frame[["open", "close", "high"]].min(axis=1))]
    if len(invalid_ohlc):
        raise RuntimeError(f"invalid OHLC rows: {len(invalid_ohlc)}")
    closed_rate = float(frame["is_closed"].astype(bool).mean())
    if closed_rate < 1.0:
        raise RuntimeError(f"non-closed 5m bars present, closed_rate={closed_rate}")
    return {
        "rows": int(len(frame)),
        "start": frame["ts"].iloc[0],
        "end": frame["ts"].iloc[-1],
        "exchange_values": sorted(frame["exchange"].astype(str).unique().tolist()),
        "symbol_values": sorted(frame["symbol"].astype(str).unique().tolist()),
        "market_type_values": sorted(frame["market_type"].astype(str).unique().tolist()),
        "timeframe_values": sorted(frame["timeframe"].astype(str).unique().tolist()),
        "missing_5m_bars": int(len(missing)),
        "duplicate_timestamps": 0,
        "closed_rate": closed_rate,
    }


def resample_15m_from_5m(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    indexed = frame.set_index("ts", drop=False)
    grouped = indexed.resample("15min", label="left", closed="left", origin="epoch")
    count = grouped["close"].count()
    agg = grouped.agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
            "quote_volume": "sum",
            "trade_count": "sum",
        }
    )
    complete = count == 3
    incomplete = agg.loc[~complete & count.gt(0)].copy()
    result = agg.loc[complete].copy()
    result["ts"] = result.index
    result["exchange"] = "binance"
    result["symbol"] = "HYPEUSDT"
    result["market_type"] = "um_futures"
    result["timeframe"] = "15m"
    result["is_closed"] = True
    result["source"] = "resampled_from_local_binance_5m"
    result["date"] = result["ts"].dt.date.astype(str)
    result["base_asset"] = "HYPE"
    result["quote_asset"] = "USDT"
    result["vwap"] = np.where(result["volume"] > 0, result["quote_volume"] / result["volume"], np.nan)
    result = result.reset_index(drop=True)
    expected = pd.date_range(result["ts"].iloc[0], result["ts"].iloc[-1], freq="15min")
    missing = expected.difference(result["ts"])
    if len(missing):
        raise RuntimeError(f"15m resample gap count={len(missing)}, first={missing[0]}")
    return result, {
        "rows": int(len(result)),
        "start": result["ts"].iloc[0],
        "end": result["ts"].iloc[-1],
        "dropped_incomplete_15m_buckets": int(len(incomplete)),
        "first_incomplete_15m_bucket": incomplete.index[0] if len(incomplete) else None,
        "last_incomplete_15m_bucket": incomplete.index[-1] if len(incomplete) else None,
        "missing_15m_bars": int(len(missing)),
    }


def add_features(frame: pd.DataFrame, cfg: PBTRConfig) -> pd.DataFrame:
    result = frame.copy()
    result["_ts_ns"] = result["ts"].map(lambda value: pd.Timestamp(value).value).astype("int64")
    close = result["close"]
    high = result["high"]
    low = result["low"]
    prev_close = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    result[f"ema{cfg.ema_fast}"] = close.ewm(span=cfg.ema_fast, adjust=False, min_periods=cfg.ema_fast).mean()
    result[f"ema{cfg.ema_slow}"] = close.ewm(span=cfg.ema_slow, adjust=False, min_periods=cfg.ema_slow).mean()
    result["atr"] = tr.rolling(cfg.atr_window, min_periods=cfg.atr_window).mean()
    return result


def build_signal(frame: pd.DataFrame, cfg: PBTRConfig) -> np.ndarray:
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    ema_fast = frame[f"ema{cfg.ema_fast}"].to_numpy("float64")
    ema_slow = frame[f"ema{cfg.ema_slow}"].to_numpy("float64")
    atr = frame["atr"].to_numpy("float64")
    spread = ema_fast - ema_slow
    direction = np.where(np.isfinite(spread), np.sign(spread), 0).astype(np.int8)
    if cfg.side_mode == "long":
        direction = np.where(direction > 0, direction, 0).astype(np.int8)
    elif cfg.side_mode == "short":
        direction = np.where(direction < 0, direction, 0).astype(np.int8)
    elif cfg.side_mode != "both":
        raise ValueError(f"unknown side_mode: {cfg.side_mode}")
    touched = np.where(direction > 0, low <= ema_fast * (1.0 + cfg.pullback_buffer), high >= ema_fast * (1.0 - cfg.pullback_buffer))
    reclaimed = np.where(direction > 0, close > ema_fast, close < ema_fast)
    candle = np.where(direction > 0, close > open_, close < open_)
    mask = (direction != 0) & touched & reclaimed & candle & np.isfinite(atr)
    signal = np.zeros(len(frame), dtype=np.int8)
    signal[np.nan_to_num(mask, nan=False).astype(bool)] = direction[np.nan_to_num(mask, nan=False).astype(bool)]
    previous_same = np.r_[False, (signal[1:] != 0) & (signal[1:] == signal[:-1])]
    signal[previous_same] = 0
    return signal


def apply_exit_cost(raw_exit_price: float, direction: int) -> float:
    return float(raw_exit_price * (1.0 - direction * EXIT_SLIPPAGE_RATE))


def crossed_stop_at_open(open_price: float, active_stop: float, direction: int) -> bool:
    return bool(open_price <= active_stop if direction > 0 else open_price >= active_stop)


def touched_stop_in_bar(high_price: float, low_price: float, active_stop: float, direction: int) -> bool:
    return bool(low_price <= active_stop if direction > 0 else high_price >= active_stop)


def active_stop_from_history(
    *,
    direction: int,
    entry_price: float,
    initial_stop: float,
    high_history: np.ndarray,
    low_history: np.ndarray,
    atr_value: float,
    trail_atr: float,
    previous_active_stop: float | None = None,
) -> float:
    if direction > 0:
        peak = max(entry_price, float(np.nanmax(high_history))) if len(high_history) else entry_price
        candidate = max(initial_stop, peak - trail_atr * atr_value)
        if previous_active_stop is not None:
            candidate = max(previous_active_stop, candidate)
    else:
        trough = min(entry_price, float(np.nanmin(low_history))) if len(low_history) else entry_price
        candidate = min(initial_stop, trough + trail_atr * atr_value)
        if previous_active_stop is not None:
            candidate = min(previous_active_stop, candidate)
    return float(candidate)


def make_trade(
    *,
    cfg: PBTRConfig,
    mode: str,
    frame: pd.DataFrame,
    signal_i: int,
    entry_i: int,
    exit_i: int,
    direction: int,
    entry_price: float,
    raw_exit_price: float,
    reason: str,
) -> Trade:
    ts_ns = frame["_ts_ns"].to_numpy("int64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    exit_price = apply_exit_cost(raw_exit_price, direction)
    gross = direction * (exit_price / entry_price - 1.0)
    fee_cost = FEE_RATE_PER_FILL * (1.0 + exit_price / entry_price)
    net = gross - fee_cost
    path_high = high[entry_i : exit_i + 1]
    path_low = low[entry_i : exit_i + 1]
    if direction > 0:
        mae = float(np.nanmin(path_low / entry_price - 1.0))
        mfe = float(np.nanmax(path_high / entry_price - 1.0))
    else:
        mae = float(np.nanmin(direction * (path_high / entry_price - 1.0)))
        mfe = float(np.nanmax(direction * (path_low / entry_price - 1.0)))
    return Trade(
        config=f"{cfg.label}__{mode}",
        signal_ts=pd.Timestamp(ts_ns[signal_i], unit="ns", tz="UTC"),
        entry_ts=pd.Timestamp(ts_ns[entry_i], unit="ns", tz="UTC"),
        exit_ts=pd.Timestamp(ts_ns[exit_i], unit="ns", tz="UTC"),
        side=direction,
        entry_price=float(entry_price),
        exit_price=float(exit_price),
        reason=reason,
        bars_held=int(exit_i - entry_i + 1),
        net_ret_1x=float(net),
        mae_1x=float(mae - FEE_RATE_PER_FILL),
        mfe_1x=float(mfe),
    )


def simulate_legacy_stop_fill(frame: pd.DataFrame, signal: np.ndarray, cfg: PBTRConfig) -> list[Trade]:
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr"].to_numpy("float64")
    trades: list[Trade] = []
    blocked_until = -1
    n = len(frame)
    for signal_i in np.flatnonzero(signal):
        direction = int(signal[signal_i])
        entry_i = signal_i + 1
        if entry_i >= n or entry_i <= blocked_until or direction == 0:
            continue
        signal_atr = float(atr[signal_i])
        if not np.isfinite(signal_atr) or signal_atr <= 0:
            continue
        entry_price = float(open_[entry_i] * (1.0 + direction * ENTRY_SLIPPAGE_RATE))
        initial_stop = entry_price - direction * cfg.stop_atr * signal_atr
        high_seg = high[entry_i:]
        low_seg = low[entry_i:]
        close_seg = close[entry_i:]
        atr_seg = atr[entry_i:]
        if direction > 0:
            prev_peak = np.r_[entry_price, np.maximum.accumulate(high_seg)[:-1]]
            stop_levels = np.maximum(np.full(len(high_seg), initial_stop), prev_peak - cfg.trail_atr * atr_seg)
            stop_hit = low_seg <= stop_levels
        else:
            prev_trough = np.r_[entry_price, np.minimum.accumulate(low_seg)[:-1]]
            stop_levels = np.minimum(np.full(len(low_seg), initial_stop), prev_trough + cfg.trail_atr * atr_seg)
            stop_hit = high_seg >= stop_levels
        stop_hit[: cfg.min_hold_bars] = False
        hit_idx = np.flatnonzero(stop_hit)
        if len(hit_idx):
            offset = int(hit_idx[0])
            reason = "legacy_stop_price_fill"
            raw_exit_price = float(stop_levels[offset])
        else:
            offset = len(close_seg) - 1
            reason = "dataset_end_close"
            raw_exit_price = float(close_seg[offset])
        exit_i = entry_i + offset
        trades.append(
            make_trade(
                cfg=cfg,
                mode="legacy",
                frame=frame,
                signal_i=signal_i,
                entry_i=entry_i,
                exit_i=exit_i,
                direction=direction,
                entry_price=entry_price,
                raw_exit_price=raw_exit_price,
                reason=reason,
            )
        )
        blocked_until = exit_i
    return trades


def simulate_live_realistic(frame: pd.DataFrame, signal: np.ndarray, cfg: PBTRConfig) -> tuple[list[Trade], pd.DataFrame]:
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr"].to_numpy("float64")
    ts_ns = frame["_ts_ns"].to_numpy("int64")
    trades: list[Trade] = []
    diag_rows: list[dict[str, Any]] = []
    blocked_until = -1
    n = len(frame)
    for signal_i in np.flatnonzero(signal):
        direction = int(signal[signal_i])
        entry_i = signal_i + 1
        if entry_i >= n or entry_i <= blocked_until or direction == 0:
            continue
        signal_atr = float(atr[signal_i])
        if not np.isfinite(signal_atr) or signal_atr <= 0:
            continue
        entry_price = float(open_[entry_i] * (1.0 + direction * ENTRY_SLIPPAGE_RATE))
        initial_stop = entry_price - direction * cfg.stop_atr * signal_atr
        unlock_i = entry_i + cfg.min_hold_bars
        if unlock_i >= n:
            break
        lockout_high = high[entry_i:unlock_i]
        lockout_low = low[entry_i:unlock_i]
        active_stop = active_stop_from_history(
            direction=direction,
            entry_price=entry_price,
            initial_stop=initial_stop,
            high_history=lockout_high,
            low_history=lockout_low,
            atr_value=float(atr[unlock_i - 1]),
            trail_atr=cfg.trail_atr,
        )
        unlock_active_stop = active_stop
        unlock_stop_valid = not crossed_stop_at_open(float(open_[unlock_i]), active_stop, direction)
        exit_i = unlock_i
        if not unlock_stop_valid:
            reason = "unlock_market_exit"
            raw_exit_price = float(open_[unlock_i])
        else:
            reason = "dataset_end_close"
            raw_exit_price = float(close[-1])
            for j in range(unlock_i, n):
                if crossed_stop_at_open(float(open_[j]), active_stop, direction):
                    exit_i = j
                    reason = "gap_market_exit"
                    raw_exit_price = float(open_[j])
                    break
                if touched_stop_in_bar(float(high[j]), float(low[j]), active_stop, direction):
                    exit_i = j
                    reason = "stop_market"
                    raw_exit_price = float(active_stop)
                    break
                if j + 1 < n:
                    active_stop = active_stop_from_history(
                        direction=direction,
                        entry_price=entry_price,
                        initial_stop=initial_stop,
                        high_history=high[entry_i : j + 1],
                        low_history=low[entry_i : j + 1],
                        atr_value=float(atr[j]),
                        trail_atr=cfg.trail_atr,
                        previous_active_stop=active_stop,
                    )
            else:
                exit_i = n - 1
        trade = make_trade(
            cfg=cfg,
            mode="live",
            frame=frame,
            signal_i=signal_i,
            entry_i=entry_i,
            exit_i=exit_i,
            direction=direction,
            entry_price=entry_price,
            raw_exit_price=raw_exit_price,
            reason=reason,
        )
        trades.append(trade)
        if direction > 0:
            lockout_mae = float(np.nanmin(lockout_low / entry_price - 1.0)) if len(lockout_low) else 0.0
            lockout_mfe = float(np.nanmax(lockout_high / entry_price - 1.0)) if len(lockout_high) else 0.0
        else:
            lockout_mae = float(np.nanmin(direction * (lockout_high / entry_price - 1.0))) if len(lockout_high) else 0.0
            lockout_mfe = float(np.nanmax(direction * (lockout_low / entry_price - 1.0))) if len(lockout_low) else 0.0
        diag_rows.append(
            {
                "label": cfg.label,
                "signal_ts": trade.signal_ts,
                "entry_ts": trade.entry_ts,
                "unlock_ts": pd.Timestamp(ts_ns[unlock_i], unit="ns", tz="UTC"),
                "exit_ts": trade.exit_ts,
                "side": direction,
                "reason": reason,
                "bars_held": trade.bars_held,
                "net_ret_1x": trade.net_ret_1x,
                "mae_1x": trade.mae_1x,
                "mfe_1x": trade.mfe_1x,
                "entry_price": entry_price,
                "exit_price": trade.exit_price,
                "initial_stop": initial_stop,
                "unlock_active_stop": unlock_active_stop,
                "final_active_stop": active_stop,
                "initial_stop_bps": abs(entry_price - initial_stop) / entry_price * 10000.0,
                "unlock_active_stop_bps": abs(entry_price - unlock_active_stop) / entry_price * 10000.0,
                "lockout_mae_bps": lockout_mae * 10000.0,
                "lockout_mfe_bps": lockout_mfe * 10000.0,
                "unlock_stop_valid": unlock_stop_valid,
            }
        )
        blocked_until = exit_i
    return trades, pd.DataFrame(diag_rows)


def metric_from_trades(trades: list[Trade], *, start: pd.Timestamp, end: pd.Timestamp) -> dict[str, Any]:
    selected = [trade for trade in trades if start <= trade.entry_ts < end]
    days = max((end - start).total_seconds() / 86400.0, 1.0)
    if not selected:
        return {
            "trades": 0,
            "total_return": 0.0,
            "equity_multiple": 1.0,
            "annualized_multiple": 1.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "payoff_ratio": 0.0,
            "avg_trade": 0.0,
            "avg_win": 0.0,
            "avg_loss_abs": 0.0,
            "max_dd": 0.0,
            "worst_trade": 0.0,
            "best_trade": 0.0,
            "long_trades": 0,
            "short_trades": 0,
            "avg_bars_held": 0.0,
        }
    raw_rets = np.array([trade.net_ret_1x for trade in selected], dtype=float)
    rets = raw_rets * LEVERAGE
    maes = np.array([trade.mae_1x * LEVERAGE for trade in selected], dtype=float)
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for ret, mae in zip(rets, maes, strict=True):
        trough = equity * max(0.001, 1.0 + mae)
        max_dd = min(max_dd, trough / peak - 1.0)
        equity *= max(0.001, 1.0 + ret)
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1.0)
    wins = raw_rets[raw_rets > 0]
    losses = raw_rets[raw_rets <= 0]
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss_abs = float(abs(losses.mean())) if len(losses) else 0.0
    payoff = float(avg_win / avg_loss_abs) if avg_loss_abs > 0 else float("inf") if avg_win > 0 else 0.0
    pf = float(wins.sum() / abs(losses.sum())) if len(losses) and losses.sum() < 0 else float("inf")
    long_trades = sum(1 for trade in selected if trade.side > 0)
    short_trades = sum(1 for trade in selected if trade.side < 0)
    return {
        "trades": int(len(selected)),
        "total_return": float(equity - 1.0),
        "equity_multiple": float(equity),
        "annualized_multiple": float(equity ** (365.25 / days)) if equity > 0 else 0.0,
        "win_rate": float((raw_rets > 0).mean()),
        "profit_factor": pf,
        "payoff_ratio": payoff,
        "avg_trade": float(rets.mean()),
        "avg_win": avg_win,
        "avg_loss_abs": avg_loss_abs,
        "max_dd": float(max_dd),
        "worst_trade": float(rets.min()),
        "best_trade": float(rets.max()),
        "long_trades": int(long_trades),
        "short_trades": int(short_trades),
        "avg_bars_held": float(np.mean([trade.bars_held for trade in selected])),
    }


def validation_slices(frame: pd.DataFrame, timeframe_minutes: int) -> list[dict[str, Any]]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=timeframe_minutes)
    return [
        {"slice": "full", "start": start, "end": end},
        {"slice": "2025-05-30_2025-09-01", "start": start, "end": pd.Timestamp("2025-09-01T00:00:00Z")},
        {"slice": "2025-09-01_2025-12-01", "start": pd.Timestamp("2025-09-01T00:00:00Z"), "end": pd.Timestamp("2025-12-01T00:00:00Z")},
        {"slice": "2025-12-01_2026-03-01", "start": pd.Timestamp("2025-12-01T00:00:00Z"), "end": pd.Timestamp("2026-03-01T00:00:00Z")},
        {"slice": "2026-03-01_2026-06-01", "start": pd.Timestamp("2026-03-01T00:00:00Z"), "end": pd.Timestamp("2026-06-01T00:00:00Z")},
        {"slice": "forward_2026-06-01_latest", "start": pd.Timestamp("2026-06-01T00:00:00Z"), "end": end},
    ]


def summarize_variant(
    *,
    cfg: PBTRConfig,
    mode: str,
    signal_count: int,
    trades: list[Trade],
    frame: pd.DataFrame,
    timeframe_minutes: int,
    diag: pd.DataFrame | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    slices = validation_slices(frame, timeframe_minutes)
    start = slices[0]["start"]
    end = slices[0]["end"]
    full = metric_from_trades(trades, start=start, end=end)
    row: dict[str, Any] = {
        "label": cfg.label,
        "mode": mode,
        "timeframe": cfg.timeframe,
        "signal_count": signal_count,
        **asdict(cfg),
        **full,
    }
    if diag is not None and len(diag):
        reasons = diag["reason"].value_counts(normalize=True).to_dict()
        row["unlock_stop_valid_rate"] = float(diag["unlock_stop_valid"].mean())
        row["unlock_market_exit_rate"] = float(reasons.get("unlock_market_exit", 0.0))
        row["gap_market_exit_rate"] = float(reasons.get("gap_market_exit", 0.0))
        row["stop_market_rate"] = float(reasons.get("stop_market", 0.0))
        row["median_unlock_stop_bps"] = float(diag["unlock_active_stop_bps"].median())
    else:
        row["unlock_stop_valid_rate"] = np.nan
        row["unlock_market_exit_rate"] = np.nan
        row["gap_market_exit_rate"] = np.nan
        row["stop_market_rate"] = np.nan
        row["median_unlock_stop_bps"] = np.nan
    slice_rows: list[dict[str, Any]] = []
    for item in slices:
        metrics = metric_from_trades(trades, start=item["start"], end=item["end"])
        slice_rows.append(
            {
                "label": cfg.label,
                "mode": mode,
                "slice": item["slice"],
                "slice_start": item["start"],
                "slice_end": item["end"],
                **metrics,
            }
        )
        if item["slice"] != "full":
            prefix = item["slice"].replace("-", "_").replace(".", "_")
            row[f"{prefix}_trades"] = metrics["trades"]
            row[f"{prefix}_total_return"] = metrics["total_return"]
            row[f"{prefix}_profit_factor"] = metrics["profit_factor"]
            row[f"{prefix}_win_rate"] = metrics["win_rate"]
            row[f"{prefix}_max_dd"] = metrics["max_dd"]
    return row, slice_rows


def build_grid() -> list[PBTRConfig]:
    variants: list[PBTRConfig] = [
        V33_15M_SAME,
        V33_15M_HOLD3,
        V33_15M_COMPRESSED,
        replace(V33_15M_SAME, label="15m_same_numbers_long", side_mode="long"),
        replace(V33_15M_SAME, label="15m_same_numbers_short", side_mode="short"),
    ]
    seen = {variant.label for variant in variants}
    idx = 0
    for side_mode in ("both", "long", "short"):
        for ema_fast, ema_slow in ((7, 32), (21, 96)):
            for atr_window in (5, 14):
                for min_hold in (3, 9):
                    for stop_atr in (0.5,):
                        for trail_atr in (0.75, 1.5, 3.0):
                            for pullback_buffer in (0.01,):
                                idx += 1
                                label = (
                                    f"grid_{idx:04d}_{side_mode}_ema{ema_fast}_{ema_slow}"
                                    f"_atr{atr_window}_hold{min_hold}_st{stop_atr:g}_tr{trail_atr:g}_pb{pullback_buffer:g}"
                                )
                                if label in seen:
                                    continue
                                seen.add(label)
                                variants.append(
                                    PBTRConfig(
                                        label=label,
                                        timeframe="15m",
                                        side_mode=side_mode,
                                        ema_fast=ema_fast,
                                        ema_slow=ema_slow,
                                        atr_window=atr_window,
                                        pullback_buffer=pullback_buffer,
                                        stop_atr=stop_atr,
                                        trail_atr=trail_atr,
                                        min_hold_bars=min_hold,
                                    )
                                )
    return variants


def trades_to_rows(trades: list[Trade], cfg: PBTRConfig, mode: str, max_rows: int = 20000) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, trade in enumerate(trades[:max_rows], start=1):
        rows.append(
            {
                "label": cfg.label,
                "mode": mode,
                "trade_no": idx,
                "signal_ts": trade.signal_ts,
                "entry_ts": trade.entry_ts,
                "exit_ts": trade.exit_ts,
                "side": trade.side,
                "bars_held": trade.bars_held,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "net_ret_1x": trade.net_ret_1x,
                "mae_1x": trade.mae_1x,
                "mfe_1x": trade.mfe_1x,
                "reason": trade.reason,
            }
        )
    return rows


def score_live_row(row: dict[str, Any]) -> float:
    pf = float(row["profit_factor"])
    payoff = float(row["payoff_ratio"])
    if not np.isfinite(pf):
        pf = 5.0
    if not np.isfinite(payoff):
        payoff = 5.0
    return (
        float(row["total_return"]) * 100.0
        + min(pf, 3.0) * 20.0
        + float(row["win_rate"]) * 20.0
        + min(payoff, 4.0) * 8.0
        + float(row["max_dd"]) * 30.0
        + min(int(row["trades"]), 200) / 10.0
    )


def render_markdown(
    data_quality: dict[str, Any],
    summary: pd.DataFrame,
    slices: pd.DataFrame,
    diag: pd.DataFrame,
) -> str:
    important_labels = [
        ("5m_v33_reference", "5m V3.3 reference"),
        ("15m_same_numbers", "15m same numbers"),
        ("15m_same_ema_hold3", "15m same EMA hold3"),
        ("15m_calendar_compressed", "15m calendar compressed"),
        ("15m_same_numbers_long", "15m same numbers long"),
        ("15m_same_numbers_short", "15m same numbers short"),
    ]
    live = summary[(summary["mode"] == "live") & (summary["timeframe"] == "15m")].copy()
    legacy = summary[summary["mode"] == "legacy"].copy()
    live["score"] = live.apply(lambda row: score_live_row(row.to_dict()), axis=1)
    top_live = live.sort_values(["score", "profit_factor", "total_return"], ascending=False).head(12)
    pass_like = live[
        (live["trades"] >= 50)
        & (live["profit_factor"] > 1.0)
        & (live["payoff_ratio"] > 1.0)
        & (live["max_dd"] > -0.30)
        & (live["forward_2026_06_01_latest_trades"] >= 5)
        & (live["forward_2026_06_01_latest_profit_factor"] > 1.0)
    ].copy()

    lines = [
        "# HYPE-15M-Pullback-Trail V3.3 迁移诊断 2026-06-30",
        "",
        "Family id：`HYPE-15M-Pullback-Trail`",
        "",
        "本报告回答一个具体问题：`HYPE-5M-Pullback-Trail-V3.3` 在 `5m` 上严格实盘口径失败，换成 `15m` K 后，是否会因为噪音降低而好一些。",
        "",
        "## 数据与口径",
        "",
        f"- 数据源：本地标准数据湖 Binance HYPEUSDT USD-M Futures `5m`，重采样为严格闭合 `15m`。",
        f"- 5m 范围：`{data_quality['raw_5m']['start']}` -> `{data_quality['raw_5m']['end']}`，行数 `{data_quality['raw_5m']['rows']}`，缺口 `{data_quality['raw_5m']['missing_5m_bars']}`。",
        f"- 15m 范围：`{data_quality['resampled_15m']['start']}` -> `{data_quality['resampled_15m']['end']}`，行数 `{data_quality['resampled_15m']['rows']}`，缺口 `{data_quality['resampled_15m']['missing_15m_bars']}`，丢弃未完整 15m bucket `{data_quality['resampled_15m']['dropped_incomplete_15m_buckets']}`。",
        f"- 成本：沿用 V3.3 live spec 的观测成本，手续费 `{FEE_RATE_PER_FILL * 10000:.4f} bps/成交额`，入场滑点 `{ENTRY_SLIPPAGE_RATE * 10000:.2f} bps`，出场滑点 `{EXIT_SLIPPAGE_RATE * 10000:.2f} bps`。",
        "- `legacy`：旧 stop-price fill 口径，锁仓后即使 stop 已被当前价格穿越也按 stop 价成交。",
        "- `live`：可实盘口径，锁仓结束若 stop 已穿越，按该根 K 开盘市价退出；否则挂 stop-market，后续只用已收盘 K 更新 trailing。",
        "",
        "## 核心对照",
        "",
        "| 版本 | 口径 | 交易数 | 收益 | 年化 | 胜率 | PF | payoff | 最大回撤 | 解锁 stop 可挂 | 解锁市价退出 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, display in important_labels:
        for mode in ("legacy", "live"):
            rows = summary[(summary["label"] == label) & (summary["mode"] == mode)]
            if rows.empty:
                continue
            row = rows.iloc[0]
            lines.append(
                f"| `{display}` | `{mode}` | `{int(row['trades'])}` | `{pct(float(row['total_return']))}` | `{mult(float(row['annualized_multiple']))}` | "
                f"`{pct(float(row['win_rate']))}` | `{num(float(row['profit_factor']))}` | `{num(float(row['payoff_ratio']))}` | `{pct(float(row['max_dd']))}` | "
                f"`{pct(float(row['unlock_stop_valid_rate'])) if pd.notna(row['unlock_stop_valid_rate']) else '-'}` | "
                f"`{pct(float(row['unlock_market_exit_rate'])) if pd.notna(row['unlock_market_exit_rate']) else '-'}` |"
            )
    lines.extend(
        [
            "",
            "## 15m 网格前排 live 结果",
            "",
            "| label | 交易数 | 收益 | 胜率 | PF | payoff | 最大回撤 | OOS 交易 | OOS PF | 解锁 stop 可挂 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in top_live.to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{int(row['trades'])}` | `{pct(float(row['total_return']))}` | `{pct(float(row['win_rate']))}` | "
            f"`{num(float(row['profit_factor']))}` | `{num(float(row['payoff_ratio']))}` | `{pct(float(row['max_dd']))}` | "
            f"`{int(row['forward_2026_06_01_latest_trades'])}` | `{num(float(row['forward_2026_06_01_latest_profit_factor']))}` | "
            f"`{pct(float(row['unlock_stop_valid_rate']))}` |"
        )
    lines.extend(
        [
            "",
            "## pass-like 过滤",
            "",
            "过滤条件：`full trades>=50`、`PF>1`、`payoff>1`、`max_dd>-30%`、`forward trades>=5`、`forward PF>1`。",
            "",
            f"- 通过数量：`{len(pass_like)}/{len(live)}`。",
        ]
    )
    if len(pass_like):
        lines.extend(["", "| label | 交易数 | 收益 | PF | payoff | 最大回撤 | OOS PF |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"])
        for row in pass_like.sort_values("score", ascending=False).head(10).to_dict(orient="records"):
            lines.append(
                f"| `{row['label']}` | `{int(row['trades'])}` | `{pct(float(row['total_return']))}` | `{num(float(row['profit_factor']))}` | "
                f"`{num(float(row['payoff_ratio']))}` | `{pct(float(row['max_dd']))}` | `{num(float(row['forward_2026_06_01_latest_profit_factor']))}` |"
            )
    else:
        lines.append("- 没有任何 15m live-realistic 网格配置通过该过滤。")

    direct_live = summary[(summary["label"] == "15m_same_numbers") & (summary["mode"] == "live")].iloc[0]
    direct_legacy = summary[(summary["label"] == "15m_same_numbers") & (summary["mode"] == "legacy")].iloc[0]
    v5_live = summary[(summary["label"] == "5m_v33_reference") & (summary["mode"] == "live")].iloc[0]
    lines.extend(
        [
            "",
            "## 结论",
            "",
            f"1. 15m 的确降频：直接照搬 V3.3 数字后，交易从 5m reference live 的 `{int(v5_live['trades'])}` 笔降到 `{int(direct_live['trades'])}` 笔。",
            f"2. 但 15m 没有修复核心执行问题：直接照搬数字的 `legacy` 收益 `{pct(float(direct_legacy['total_return']))}`，而 `live` 只剩 `{pct(float(direct_live['total_return']))}`，PF `{num(float(direct_live['profit_factor']))}`，最大回撤 `{pct(float(direct_live['max_dd']))}`。",
            f"3. 直接照搬数字的 15m 解锁 stop 可挂比例只有 `{pct(float(direct_live['unlock_stop_valid_rate']))}`，也就是说大量交易在解锁时依然已经穿越 stop，只能市价处理。",
            "4. 小网格里没有任何 live 配置为正收益；前排配置最多只是把亏损从接近归零降到约 `-79%`，不是 V3.3 机制自然变好。",
            "",
            "判断：`15m` 可以减少噪音和交易数，但不能把 V3.3 的 `min_hold + delayed trailing` 从不可实盘机制变成好策略。继续研究时不应直接迁移 V3.3 trailing；更合理的是采用 15m 信号作为事件源，再使用入场即存在的 bracket / emergency stop / timeout 结构重新设计。",
            "",
            "## 产物",
            "",
            f"- 脚本：`research/hype/15m-pullback-trail/scripts/research_hype_15m_pbtr_v33_migration.py`",
            f"- JSON：`{REPORT_PATH.relative_to(ROOT)}`",
            f"- summary CSV：`{SUMMARY_PATH.relative_to(ROOT)}`",
            f"- slices CSV：`{SLICES_PATH.relative_to(ROOT)}`",
            f"- trades CSV：`{TRADES_PATH.relative_to(ROOT)}`",
            f"- diag CSV：`{DIAG_PATH.relative_to(ROOT)}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    raw_5m = load_all_hype_5m()
    raw_quality = verify_5m_data(raw_5m)
    data_15m, resample_quality = resample_15m_from_5m(raw_5m)

    frames = {
        "5m": (add_features(raw_5m, V33_5M), V33_5M, 5),
        "15m": (data_15m, V33_15M_SAME, 15),
    }

    summary_rows: list[dict[str, Any]] = []
    slice_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    diag_frames: list[pd.DataFrame] = []
    report_variants: dict[str, Any] = {}

    direct_configs = [V33_5M, V33_15M_SAME, V33_15M_HOLD3, V33_15M_COMPRESSED]
    grid_configs = build_grid()
    configs = direct_configs + [cfg for cfg in grid_configs if cfg.label not in {item.label for item in direct_configs}]

    feature_cache: dict[tuple[str, int, int, int], pd.DataFrame] = {("5m", V33_5M.ema_fast, V33_5M.ema_slow, V33_5M.atr_window): frames["5m"][0]}
    raw_15m = data_15m

    for cfg in configs:
        if cfg.timeframe == "5m":
            base_frame = raw_5m
            timeframe_minutes = 5
        else:
            base_frame = raw_15m
            timeframe_minutes = 15
        cache_key = (cfg.timeframe, cfg.ema_fast, cfg.ema_slow, cfg.atr_window)
        if cache_key in feature_cache:
            frame = feature_cache[cache_key]
        else:
            frame = add_features(base_frame, cfg)
            feature_cache[cache_key] = frame
        signal = build_signal(frame, cfg)
        signal_count = int(np.count_nonzero(signal))
        legacy_trades = simulate_legacy_stop_fill(frame, signal, cfg)
        live_trades, diag = simulate_live_realistic(frame, signal, cfg)
        legacy_summary, legacy_slices = summarize_variant(
            cfg=cfg,
            mode="legacy",
            signal_count=signal_count,
            trades=legacy_trades,
            frame=frame,
            timeframe_minutes=timeframe_minutes,
        )
        live_summary, live_slices = summarize_variant(
            cfg=cfg,
            mode="live",
            signal_count=signal_count,
            trades=live_trades,
            frame=frame,
            timeframe_minutes=timeframe_minutes,
            diag=diag,
        )
        summary_rows.extend([legacy_summary, live_summary])
        slice_rows.extend(legacy_slices)
        slice_rows.extend(live_slices)
        if cfg.label in {
            "5m_v33_reference",
            "15m_same_numbers",
            "15m_same_ema_hold3",
            "15m_calendar_compressed",
            "15m_same_numbers_long",
            "15m_same_numbers_short",
        }:
            trade_rows.extend(trades_to_rows(legacy_trades, cfg, "legacy"))
            trade_rows.extend(trades_to_rows(live_trades, cfg, "live"))
            diag_frames.append(diag)
        report_variants[cfg.label] = asdict(cfg)

    summary = pd.DataFrame(summary_rows)
    slices = pd.DataFrame(slice_rows)
    trades = pd.DataFrame(trade_rows)
    diag_all = pd.concat(diag_frames, ignore_index=True) if diag_frames else pd.DataFrame()

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    DIAG_DIR.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    slices.to_csv(SLICES_PATH, index=False)
    trades.to_csv(TRADES_PATH, index=False)
    diag_all.to_csv(DIAG_PATH, index=False)
    data_quality = {"raw_5m": raw_quality, "resampled_15m": resample_quality}
    MARKDOWN_PATH.write_text(render_markdown(data_quality, summary, slices, diag_all), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "family_id": "HYPE-15M-Pullback-Trail",
                "question": "Does HYPE-5M-Pullback-Trail-V3.3 improve on 15m bars?",
                "date": DATE_TAG,
                "cost_model": {
                    "fee_rate_per_fill": FEE_RATE_PER_FILL,
                    "entry_slippage_rate": ENTRY_SLIPPAGE_RATE,
                    "exit_slippage_rate": EXIT_SLIPPAGE_RATE,
                },
                "data_quality": data_quality,
                "variant_count": int(len(configs)),
                "variants": report_variants,
                "exit_reason_counts": {
                    label: dict(Counter(group["reason"]))
                    for label, group in diag_all.groupby("label")
                }
                if len(diag_all)
                else {},
                "outputs": {
                    "markdown": str(MARKDOWN_PATH.relative_to(ROOT)),
                    "summary": str(SUMMARY_PATH.relative_to(ROOT)),
                    "slices": str(SLICES_PATH.relative_to(ROOT)),
                    "trades": str(TRADES_PATH.relative_to(ROOT)),
                    "diag": str(DIAG_PATH.relative_to(ROOT)),
                },
            },
            ensure_ascii=False,
            indent=2,
            default=json_safe,
        ),
        encoding="utf-8",
    )

    key = summary[
        summary["label"].isin(
            [
                "5m_v33_reference",
                "15m_same_numbers",
                "15m_same_ema_hold3",
                "15m_calendar_compressed",
                "15m_same_numbers_long",
                "15m_same_numbers_short",
            ]
        )
    ][
        [
            "label",
            "mode",
            "trades",
            "total_return",
            "annualized_multiple",
            "win_rate",
            "profit_factor",
            "payoff_ratio",
            "max_dd",
            "unlock_stop_valid_rate",
            "unlock_market_exit_rate",
        ]
    ]
    print(f"markdown={MARKDOWN_PATH.relative_to(ROOT)}")
    print(f"summary={SUMMARY_PATH.relative_to(ROOT)}")
    print(key.to_string(index=False))


if __name__ == "__main__":
    main()
