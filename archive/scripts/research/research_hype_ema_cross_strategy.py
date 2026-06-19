from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
import requests


SYMBOL = "HYPEUSDT"
INTERVAL = "15m"
PANDAS_INTERVAL = "15min"
INTERVAL_MS = 15 * 60 * 1000
SINCE = datetime(2025, 5, 1, tzinfo=timezone.utc)
SLIPPAGE = 0.0005
TRADE_COST = 0.00085
PERIODS_PER_YEAR = 365 * 24 * 4


@dataclass(frozen=True, slots=True)
class EntrySpec:
    name: str
    filters: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExitSpec:
    name: str
    kind: str
    bad_bars: int = 1
    trail_atr: str | None = None
    trail_mult: float | None = None


@dataclass(frozen=True, slots=True)
class StrategySpec:
    name: str
    entry: EntrySpec
    exit: ExitSpec


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Research HYPE EMA96/384 cross-trigger trend strategies."
    )
    parser.add_argument("--refresh", action="store_true", help="Refresh Binance data cache.")
    parser.add_argument(
        "--cache",
        type=Path,
        default=Path("data/cache/hypeusdt_15m_fapi.csv"),
        help="CSV cache path for Binance fapi klines.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/hype_ema_cross_research.json"),
        help="JSON report output path.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=30,
        help="Number of ranked variants to keep in report.",
    )
    return parser.parse_args()


def fetch_klines(*, cache_path: Path, refresh: bool) -> pd.DataFrame:
    if cache_path.exists() and not refresh:
        frame = pd.read_csv(cache_path)
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
        return frame

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    start = int(SINCE.timestamp() * 1000)
    end = int(pd.Timestamp.now(tz="UTC").floor(PANDAS_INTERVAL).timestamp() * 1000)
    rows: list[list[object]] = []
    session = requests.Session()

    while start < end:
        response = session.get(
            "https://fapi.binance.com/fapi/v1/klines",
            params={
                "symbol": SYMBOL,
                "interval": INTERVAL,
                "startTime": start,
                "endTime": end,
                "limit": 1500,
            },
            timeout=30,
        )
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break
        rows.extend(batch)
        next_start = int(batch[-1][0]) + INTERVAL_MS
        if next_start <= start:
            break
        start = next_start
        time.sleep(0.05)

    frame = pd.DataFrame(
        rows,
        columns=[
            "ts",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_volume",
            "trade_count",
            "taker_base",
            "taker_quote",
            "ignore",
        ],
    )
    frame = (
        frame[["ts", "open", "high", "low", "close", "volume"]]
        .drop_duplicates("ts")
        .sort_values("ts")
        .reset_index(drop=True)
    )
    frame["ts"] = pd.to_datetime(frame["ts"], unit="ms", utc=True)
    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = frame[column].astype("float64")
    frame.to_csv(cache_path, index=False)
    return frame


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    previous_close = close.shift(1)
    return pd.concat(
        [high - low, (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)


def adx_di(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    window: int,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    tr = true_range(high, low, close)
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
        index=high.index,
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=high.index,
    )
    atr = tr.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    plus_di = (
        100
        * plus_dm.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
        / atr.replace(0.0, np.nan)
    )
    minus_di = (
        100
        * minus_dm.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
        / atr.replace(0.0, np.nan)
    )
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    adx = dx.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    return adx, plus_di, minus_di


def rsi(close: pd.Series, window: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return 100 - 100 / (1 + rs)


def trend_efficiency(close: pd.Series, window: int) -> pd.Series:
    direct = close.pct_change(window).abs()
    path = close.pct_change().abs().rolling(window, min_periods=window).sum()
    return direct / path.replace(0.0, np.nan)


def add_htf_features(frame: pd.DataFrame, rule: str, prefix: str) -> pd.DataFrame:
    ohlcv = (
        frame.set_index("ts")[["open", "high", "low", "close", "volume"]]
        .resample(rule, label="left", closed="left")
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        .dropna()
    )
    htf = pd.DataFrame(index=ohlcv.index)
    htf[f"{prefix}_ema24"] = ohlcv.close.ewm(
        span=24, adjust=False, min_periods=24
    ).mean()
    htf[f"{prefix}_ema96"] = ohlcv.close.ewm(
        span=96, adjust=False, min_periods=96
    ).mean()
    htf[f"{prefix}_ema_spread"] = (
        htf[f"{prefix}_ema24"] / htf[f"{prefix}_ema96"].replace(0.0, np.nan) - 1
    )
    htf[f"{prefix}_ret12"] = ohlcv.close.pct_change(12)
    htf[f"{prefix}_rsi14"] = rsi(ohlcv.close, 14)
    htf[f"{prefix}_adx21"], htf[f"{prefix}_pdi21"], htf[f"{prefix}_mdi21"] = adx_di(
        ohlcv.high,
        ohlcv.low,
        ohlcv.close,
        21,
    )
    aligned = htf.shift(1).reindex(pd.DatetimeIndex(frame.ts), method="ffill")
    return aligned.reset_index(drop=True)


def build_features(raw: pd.DataFrame) -> pd.DataFrame:
    frame = raw.copy()
    close = frame.close
    high = frame.high
    low = frame.low
    volume = frame.volume

    frame["ema96"] = close.ewm(span=96, adjust=False, min_periods=96).mean()
    frame["ema384"] = close.ewm(span=384, adjust=False, min_periods=384).mean()
    frame["ema_spread"] = frame.ema96 / frame.ema384.replace(0.0, np.nan) - 1
    frame["ema96_slope16"] = frame.ema96.pct_change(16)
    frame["ema96_slope48"] = frame.ema96.pct_change(48)
    frame["ema384_slope96"] = frame.ema384.pct_change(96)

    for window in (4, 16, 48, 96):
        frame[f"ret{window}"] = close.pct_change(window)
    for window in (96, 192):
        frame[f"vol_surge{window}"] = (
            volume / volume.rolling(window, min_periods=window).mean().replace(0.0, np.nan)
            - 1
        )
    tr = true_range(high, low, close)
    for window in (96, 336, 672):
        frame[f"atr_pct{window}"] = (
            tr.rolling(window, min_periods=window).mean() / close.replace(0.0, np.nan)
        )
    frame["atr_ratio96_672"] = frame.atr_pct96 / frame.atr_pct672.replace(0.0, np.nan)

    for window in (14, 28):
        (
            frame[f"adx{window}"],
            frame[f"pdi{window}"],
            frame[f"mdi{window}"],
        ) = adx_di(high, low, close, window)

    frame["rsi14"] = rsi(close, 14)
    frame["eff48"] = trend_efficiency(close, 48)
    frame["eff96"] = trend_efficiency(close, 96)

    for window in (96, 192):
        rolling_high = high.rolling(window, min_periods=window).max()
        rolling_low = low.rolling(window, min_periods=window).min()
        frame[f"donchian_pos{window}"] = (
            (close - rolling_low) / (rolling_high - rolling_low).replace(0.0, np.nan)
        )

    frame = pd.concat(
        [
            frame,
            add_htf_features(frame, "1h", "h1"),
            add_htf_features(frame, "4h", "h4"),
        ],
        axis=1,
    )
    return frame.reset_index(drop=True)


def build_filter_masks(frame: pd.DataFrame) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    masks: dict[str, tuple[np.ndarray, np.ndarray]] = {}

    def add(name: str, long_cond: pd.Series, short_cond: pd.Series) -> None:
        masks[name] = (
            long_cond.fillna(False).to_numpy(dtype=bool),
            short_cond.fillna(False).to_numpy(dtype=bool),
        )

    always = pd.Series(True, index=frame.index)
    add("none", always, always)
    add("ret16_same_0", frame.ret16 > 0, frame.ret16 < 0)
    add("ret16_same_0p5", frame.ret16 > 0.005, frame.ret16 < -0.005)
    add("ret48_same_1", frame.ret48 > 0.01, frame.ret48 < -0.01)
    add("ema96_slope16", frame.ema96_slope16 > 0, frame.ema96_slope16 < 0)
    add("ema96_slope48", frame.ema96_slope48 > 0, frame.ema96_slope48 < 0)
    add("ema384_slope96", frame.ema384_slope96 > 0, frame.ema384_slope96 < 0)
    add("di14_same", frame.pdi14 > frame.mdi14, frame.mdi14 > frame.pdi14)
    add("di28_same", frame.pdi28 > frame.mdi28, frame.mdi28 > frame.pdi28)
    add("adx14_20", frame.adx14 >= 20, frame.adx14 >= 20)
    add("adx28_24", frame.adx28 >= 24, frame.adx28 >= 24)
    add("vol96_0", frame.vol_surge96 >= 0, frame.vol_surge96 >= 0)
    add("vol192_25", frame.vol_surge192 >= 0.25, frame.vol_surge192 >= 0.25)
    add("eff48_25", frame.eff48 >= 0.25, frame.eff48 >= 0.25)
    add("eff96_30", frame.eff96 >= 0.30, frame.eff96 >= 0.30)
    add("donchian96_edge", frame.donchian_pos96 >= 0.65, frame.donchian_pos96 <= 0.35)
    add("donchian192_edge", frame.donchian_pos192 >= 0.65, frame.donchian_pos192 <= 0.35)
    add("atr_expand", frame.atr_ratio96_672 >= 1.0, frame.atr_ratio96_672 >= 1.0)
    add("atr_not_hot", frame.atr_ratio96_672 <= 1.6, frame.atr_ratio96_672 <= 1.6)
    add("rsi14_dir", frame.rsi14 >= 52, frame.rsi14 <= 48)
    add("h1_ema", frame.h1_ema_spread > 0, frame.h1_ema_spread < 0)
    add("h1_ret12", frame.h1_ret12 > 0, frame.h1_ret12 < 0)
    add("h1_di", frame.h1_pdi21 > frame.h1_mdi21, frame.h1_mdi21 > frame.h1_pdi21)
    add("h4_ema", frame.h4_ema_spread > 0, frame.h4_ema_spread < 0)
    add("h4_ret12", frame.h4_ret12 > 0, frame.h4_ret12 < 0)
    return masks


def build_entry_specs() -> list[EntrySpec]:
    momentum = [
        "none",
        "ret16_same_0",
        "ret16_same_0p5",
        "ret48_same_1",
        "ema96_slope16",
        "ema96_slope48",
        "ema384_slope96",
    ]
    strength = ["none", "di14_same", "di28_same", "adx14_20", "adx28_24"]
    participation = ["none", "vol96_0", "vol192_25", "eff48_25", "eff96_30"]
    structure = ["none", "donchian96_edge", "donchian192_edge", "rsi14_dir"]
    volatility = ["none", "atr_expand", "atr_not_hot"]
    htf = ["none", "h1_ema", "h1_ret12", "h1_di", "h4_ema", "h4_ret12"]

    specs: list[EntrySpec] = []
    seen: set[tuple[str, ...]] = set()
    for combo in product(momentum, strength, participation, structure, volatility, htf):
        filters = tuple(filter(lambda item: item != "none", combo))
        if filters in seen:
            continue
        seen.add(filters)
        name = "cross_only" if not filters else "cross+" + "+".join(filters)
        specs.append(EntrySpec(name=name, filters=filters))
    return specs


def build_exit_specs() -> list[ExitSpec]:
    return [
        ExitSpec("opposite_cross", "opposite_cross"),
        ExitSpec("ema96_break_2", "ema96_break", bad_bars=2),
        ExitSpec("ema96_break_4", "ema96_break", bad_bars=4),
        ExitSpec("ema384_break_2", "ema384_break", bad_bars=2),
        ExitSpec("slope48_break_4", "slope48_break", bad_bars=4),
        ExitSpec("di28_break_3", "di28_break", bad_bars=3),
        ExitSpec("h1_ema_break_2", "h1_ema_break", bad_bars=2),
        ExitSpec(
            "chandelier_atr336_4",
            "chandelier",
            trail_atr="atr_pct336",
            trail_mult=4.0,
        ),
        ExitSpec(
            "chandelier_atr336_6",
            "chandelier",
            trail_atr="atr_pct336",
            trail_mult=6.0,
        ),
        ExitSpec(
            "ema96_or_chandelier6",
            "ema96_or_chandelier",
            bad_bars=2,
            trail_atr="atr_pct336",
            trail_mult=6.0,
        ),
    ]


def build_entries(
    frame: pd.DataFrame,
    entry: EntrySpec,
    masks: dict[str, tuple[np.ndarray, np.ndarray]],
) -> np.ndarray:
    spread = frame.ema_spread.to_numpy("float64")
    previous = np.r_[np.nan, spread[:-1]]
    long_cross = (spread > 0.0) & (previous <= 0.0)
    short_cross = (spread < 0.0) & (previous >= 0.0)

    long_ok = np.ones(len(frame), dtype=bool)
    short_ok = np.ones(len(frame), dtype=bool)
    for filter_name in entry.filters:
        filter_long, filter_short = masks[filter_name]
        long_ok &= filter_long
        short_ok &= filter_short

    signal = np.zeros(len(frame), dtype=np.int8)
    signal[long_cross & long_ok] = 1
    signal[short_cross & short_ok] = -1
    return signal


def trend_bad_mask(frame: pd.DataFrame, exit_spec: ExitSpec, direction: int) -> np.ndarray:
    if exit_spec.kind == "opposite_cross":
        return np.zeros(len(frame), dtype=bool)
    if exit_spec.kind in {"ema96_break", "ema96_or_chandelier"}:
        bad = frame.close < frame.ema96 if direction > 0 else frame.close > frame.ema96
        return bad.fillna(False).to_numpy(bool)
    if exit_spec.kind == "ema384_break":
        bad = frame.close < frame.ema384 if direction > 0 else frame.close > frame.ema384
        return bad.fillna(False).to_numpy(bool)
    if exit_spec.kind == "slope48_break":
        bad = frame.ema96_slope48 < 0 if direction > 0 else frame.ema96_slope48 > 0
        return bad.fillna(False).to_numpy(bool)
    if exit_spec.kind == "di28_break":
        bad = frame.pdi28 < frame.mdi28 if direction > 0 else frame.mdi28 < frame.pdi28
        return bad.fillna(False).to_numpy(bool)
    if exit_spec.kind == "h1_ema_break":
        bad = frame.h1_ema_spread < 0 if direction > 0 else frame.h1_ema_spread > 0
        return bad.fillna(False).to_numpy(bool)
    if exit_spec.kind == "chandelier":
        return np.zeros(len(frame), dtype=bool)
    raise ValueError(f"unsupported exit kind: {exit_spec.kind}")


def backtest(
    frame: pd.DataFrame,
    spec: StrategySpec,
    entry_signal: np.ndarray,
    *,
    start_ts: pd.Timestamp | None = None,
) -> dict[str, object]:
    if start_ts is None:
        start_i = 0
    else:
        ts_series = pd.to_datetime(frame.ts, utc=True)
        candidates = np.flatnonzero(ts_series >= start_ts)
        start_i = int(candidates[0]) if len(candidates) else len(frame)
    if start_i >= len(frame):
        raise ValueError("start_ts is outside the frame")

    ts = pd.to_datetime(frame.ts, utc=True).to_numpy()
    open_ = frame.open.to_numpy("float64")
    close = frame.close.to_numpy("float64")
    spread = frame.ema_spread.to_numpy("float64")
    previous_spread = np.r_[np.nan, spread[:-1]]
    long_bad = trend_bad_mask(frame, spec.exit, 1)
    short_bad = trend_bad_mask(frame, spec.exit, -1)
    trail_atr = (
        frame[spec.exit.trail_atr].to_numpy("float64")
        if spec.exit.trail_atr is not None
        else None
    )

    pos = 0
    entry_price = 0.0
    entry_ts: pd.Timestamp | None = None
    equity = 1.0
    last_mark = open_[start_i]
    pending_exit = False
    pending_entry = 0
    bad_count = 0
    peak = np.nan
    trough = np.nan
    curve: list[float] = []
    trades: list[dict[str, object]] = []

    def close_position(i: int, price: float, reason: str) -> None:
        nonlocal pos, entry_price, entry_ts, equity, last_mark, bad_count, peak, trough
        equity *= 1 + pos * (price / last_mark - 1)
        equity *= 1 - TRADE_COST
        trades.append(
            {
                "entry_ts": str(entry_ts),
                "exit_ts": str(pd.Timestamp(ts[i])),
                "direction": int(pos),
                "pnl_pct": float(pos * (price / entry_price - 1)),
                "exit_reason": reason,
            }
        )
        pos = 0
        entry_price = 0.0
        entry_ts = None
        last_mark = price
        bad_count = 0
        peak = np.nan
        trough = np.nan

    for i in range(start_i, len(frame)):
        if i > start_i:
            if pos:
                equity *= 1 + pos * (open_[i] / last_mark - 1)
            last_mark = open_[i]

        if pending_exit and pos:
            exit_px = open_[i] * (1 - SLIPPAGE if pos > 0 else 1 + SLIPPAGE)
            close_position(i, exit_px, "trend_break")
            pending_exit = False

        if pending_entry and not pos:
            pos = pending_entry
            entry_price = open_[i] * (1 + SLIPPAGE if pos > 0 else 1 - SLIPPAGE)
            entry_ts = pd.Timestamp(ts[i])
            equity *= 1 - TRADE_COST
            last_mark = entry_price
            peak = entry_price
            trough = entry_price
            pending_entry = 0

        if pos:
            if pos > 0:
                peak = max(peak, close[i])
            else:
                trough = min(trough, close[i])
            equity *= 1 + pos * (close[i] / last_mark - 1)
            last_mark = close[i]

        signal = int(entry_signal[i])
        opposite_cross = (pos > 0 and spread[i] < 0 <= previous_spread[i]) or (
            pos < 0 and spread[i] > 0 >= previous_spread[i]
        )
        if opposite_cross:
            pending_exit = True
            if signal == -pos:
                pending_entry = signal
        elif signal and not pos:
            pending_entry = signal

        if pos:
            bad = False
            if spec.exit.kind != "opposite_cross":
                bad = bool(long_bad[i] if pos > 0 else short_bad[i])
            if spec.exit.kind in {"chandelier", "ema96_or_chandelier"} and trail_atr is not None:
                atr_value = trail_atr[i]
                if np.isfinite(atr_value):
                    if pos > 0:
                        bad |= close[i] < peak * (1 - spec.exit.trail_mult * atr_value)
                    else:
                        bad |= close[i] > trough * (1 + spec.exit.trail_mult * atr_value)
            bad_count = bad_count + 1 if bad else 0
            if bad_count >= spec.exit.bad_bars:
                pending_exit = True

        curve.append(float(equity))

    if pos:
        trades.append(
            {
                "entry_ts": str(entry_ts),
                "exit_ts": str(pd.Timestamp(ts[-1])),
                "direction": int(pos),
                "pnl_pct": float(pos * (close[-1] / entry_price - 1)),
                "exit_reason": "open_at_end",
            }
        )

    equity_curve = pd.Series(curve, index=pd.DatetimeIndex(ts[start_i : start_i + len(curve)]))
    returns = equity_curve.pct_change().fillna(0.0)
    drawdown = equity_curve / equity_curve.cummax() - 1.0
    std = returns.std(ddof=0)
    closed = [trade for trade in trades if trade["exit_reason"] != "open_at_end"]
    wins = [trade for trade in closed if float(trade["pnl_pct"]) > 0.0]
    long_trades = [trade for trade in closed if int(trade["direction"]) > 0]
    short_trades = [trade for trade in closed if int(trade["direction"]) < 0]
    return_pct = float(equity_curve.iloc[-1] - 1.0)
    max_dd = float(drawdown.min())
    sharpe = 0.0 if std == 0.0 else float(returns.mean() / std * np.sqrt(PERIODS_PER_YEAR))
    return {
        "name": spec.name,
        "entry": spec.entry.name,
        "exit": spec.exit.name,
        "return": return_pct,
        "max_dd": max_dd,
        "sharpe": sharpe,
        "trades": len(closed),
        "win_rate": float(len(wins) / len(closed)) if closed else 0.0,
        "long_trades": len(long_trades),
        "short_trades": len(short_trades),
        "avg_trade_pct": float(np.mean([trade["pnl_pct"] for trade in closed])) if closed else 0.0,
        "open_at_end": sum(trade["exit_reason"] == "open_at_end" for trade in trades),
        "fitness": float(return_pct * 1.5 + sharpe * 0.45 + max_dd * 1.2),
    }


def pct(value: object) -> str:
    return f"{float(value) * 100:+.2f}%"


def rounded_result(result: dict[str, object]) -> dict[str, object]:
    numeric_keys = {"return", "max_dd", "sharpe", "win_rate", "avg_trade_pct", "fitness"}
    output: dict[str, object] = {}
    for key, value in result.items():
        output[key] = round(float(value), 6) if key in numeric_keys else value
    return output


def main() -> None:
    args = parse_args()
    raw = fetch_klines(cache_path=args.cache, refresh=args.refresh)
    frame = build_features(raw)
    masks = build_filter_masks(frame)
    entries = build_entry_specs()
    exits = build_exit_specs()

    results: list[dict[str, object]] = []
    specs_by_name: dict[str, StrategySpec] = {}
    entries_by_name: dict[str, np.ndarray] = {}
    started = time.time()

    for entry_idx, entry in enumerate(entries, start=1):
        entry_signal = build_entries(frame, entry, masks)
        signal_count = int(np.count_nonzero(entry_signal))
        if signal_count < 4:
            continue
        entries_by_name[entry.name] = entry_signal
        for exit_spec in exits:
            spec = StrategySpec(
                name=f"{entry.name} | exit:{exit_spec.name}",
                entry=entry,
                exit=exit_spec,
            )
            result = backtest(frame, spec, entry_signal)
            if int(result["trades"]) >= 4:
                results.append(result)
                specs_by_name[spec.name] = spec
        if entry_idx % 250 == 0:
            elapsed = time.time() - started
            print(
                f"processed_entries={entry_idx}/{len(entries)} "
                f"kept_results={len(results)} elapsed_sec={elapsed:.1f}",
                flush=True,
            )

    if not results:
        raise RuntimeError("no strategy variants produced enough trades")

    by_fitness = sorted(results, key=lambda item: item["fitness"], reverse=True)
    by_return_dd = sorted(
        [item for item in results if item["max_dd"] >= -0.35],
        key=lambda item: (item["return"], item["sharpe"]),
        reverse=True,
    )
    by_sharpe = sorted(results, key=lambda item: item["sharpe"], reverse=True)
    chosen = by_fitness[0]
    chosen_spec = specs_by_name[str(chosen["name"])]
    chosen_signal = entries_by_name[chosen_spec.entry.name]
    end_ts = pd.to_datetime(frame.ts, utc=True).max()
    windows = {
        "1W": pd.Timedelta(days=7),
        "1M": pd.Timedelta(days=30),
        "3M": pd.Timedelta(days=90),
        "6M": pd.Timedelta(days=182),
        "1Y": pd.Timedelta(days=365),
    }
    window_results = {
        label: rounded_result(
            backtest(frame, chosen_spec, chosen_signal, start_ts=end_ts - delta)
        )
        for label, delta in windows.items()
    }
    best_per_exit: dict[str, dict[str, object]] = {}
    for exit_spec in exits:
        subset = [item for item in results if item["exit"] == exit_spec.name]
        if subset:
            best_per_exit[exit_spec.name] = rounded_result(
                sorted(subset, key=lambda item: item["fitness"], reverse=True)[0]
            )

    report = {
        "metadata": {
            "symbol": SYMBOL,
            "timeframe": INTERVAL,
            "start": str(pd.to_datetime(frame.ts, utc=True).min()),
            "end": str(end_ts),
            "bars": len(frame),
            "entry_specs": len(entries),
            "exit_specs": len(exits),
            "result_count": len(results),
            "slippage": SLIPPAGE,
            "trade_cost": TRADE_COST,
            "elapsed_sec": round(time.time() - started, 2),
            "note": "EMA96/EMA384 cross is the only trigger; filters and exits are searched.",
        },
        "chosen": rounded_result(chosen),
        "chosen_windows": window_results,
        "top_by_fitness": [rounded_result(item) for item in by_fitness[: args.top]],
        "top_by_return_dd35": [rounded_result(item) for item in by_return_dd[: args.top]],
        "top_by_sharpe": [rounded_result(item) for item in by_sharpe[: args.top]],
        "best_per_exit": best_per_exit,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")

    print(json.dumps(report["metadata"], ensure_ascii=False, indent=2))
    print(json.dumps({"chosen": report["chosen"], "windows": window_results}, ensure_ascii=False, indent=2))
    print(f"wrote={args.output}")


if __name__ == "__main__":
    main()
