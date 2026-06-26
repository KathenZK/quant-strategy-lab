from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from strategy_lab.data import DataLakeLayout, DatasetKind, DuckDBWarehouse, MarketType
from strategy_lab.settings import load_settings


SYMBOL = "HYPE/USDT:USDT"
ROUND_TRIP_COST = 0.00085
HOURS_PER_YEAR = 365 * 24
M15_PER_YEAR = 365 * 24 * 4


@dataclass(frozen=True, slots=True)
class TrendConfig:
    entry_window: int
    ema_fast: int
    ema_slow: int
    four_h_fast: int
    four_h_slow: int
    atr_window: int
    target_atr_pct: float
    max_allocation: float
    stop_atr: float
    trail_atr: float
    long_enabled: bool = True
    short_enabled: bool = False
    exit_on_ema_cross: bool = True


def main() -> None:
    m15, local_1h, local_4h = _load_data()
    h1 = _resample_ohlcv(m15, "1h")
    h4 = _resample_ohlcv(m15, "4h")
    h1_features = _build_h1_features(h1)
    h4_filter = _build_h4_filter(h4)

    candidates = _search_hourly(h1, h1_features, h4_filter)
    validated = _validate_on_15m(m15, h1, h1_features, h4_filter, candidates[:50])
    result = {
        "symbol": SYMBOL,
        "data": {
            "m15": _coverage(m15),
            "local_1h": _coverage(local_1h),
            "local_4h": _coverage(local_4h),
            "research_1h_from_15m": _coverage(h1),
            "research_4h_from_15m": _coverage(h4),
        },
        "best": validated[0] if validated else None,
        "top_hourly_candidates": candidates[:20],
        "top_15m_validated": validated[:20],
    }
    out = Path("reports/hype_multi_timeframe_trend_search.json")
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


def _load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    layout = DataLakeLayout.from_settings(load_settings(None))
    warehouse = DuckDBWarehouse(layout)

    def load(timeframe: str) -> pd.DataFrame:
        frame = warehouse.load_dataset(
            layer="normalized",
            kind=DatasetKind.OHLCV,
            exchange="binance",
            market_type=MarketType.PERP,
            symbol=SYMBOL,
            timeframe=timeframe,
            columns=["ts", "open", "high", "low", "close", "volume", "timeframe"],
        )
        if frame.empty:
            return frame
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
        return frame.drop_duplicates("ts").sort_values("ts").set_index("ts")

    return load("15m"), load("1h"), load("4h")


def _coverage(frame: pd.DataFrame) -> dict[str, object]:
    if frame.empty:
        return {"rows": 0}
    return {
        "rows": int(len(frame)),
        "start": frame.index.min().isoformat(),
        "end": frame.index.max().isoformat(),
    }


def _resample_ohlcv(frame: pd.DataFrame, rule: str) -> pd.DataFrame:
    columns = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    out = frame[list(columns)].resample(rule, label="left", closed="left").agg(columns)
    return out.dropna(subset=["open", "high", "low", "close"])


def _atr_pct(frame: pd.DataFrame, window: int) -> pd.Series:
    previous_close = frame["close"].shift(1)
    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.rolling(window, min_periods=window).mean() / frame["close"]


def _build_h1_features(frame: pd.DataFrame) -> dict[str, dict[int, pd.Series]]:
    windows = sorted({12, 24, 36, 48, 72, 96, 120, 168, 192})
    ema_windows = sorted({12, 24, 36, 48, 72, 96, 120, 168, 192})
    atr_windows = sorted({24, 48, 72, 96, 168})
    return {
        "prior_high": {
            n: frame["high"].shift(1).rolling(n, min_periods=n).max() for n in windows
        },
        "prior_low": {
            n: frame["low"].shift(1).rolling(n, min_periods=n).min() for n in windows
        },
        "ema": {
            n: frame["close"].ewm(span=n, adjust=False, min_periods=n).mean()
            for n in ema_windows
        },
        "atr_pct": {n: _atr_pct(frame, n) for n in atr_windows},
    }


def _build_h4_filter(frame: pd.DataFrame) -> dict[tuple[int, int], pd.Series]:
    windows = sorted({6, 12, 18, 24, 36, 48, 72})
    emas = {
        n: frame["close"].ewm(span=n, adjust=False, min_periods=n).mean()
        for n in windows
    }
    filters: dict[tuple[int, int], pd.Series] = {}
    for fast, slow in ((6, 24), (12, 36), (18, 48), (24, 72)):
        filters[(fast, slow)] = (emas[fast] / emas[slow] - 1.0).shift(1)
    return filters


def _search_hourly(
    h1: pd.DataFrame,
    h1_features: dict[str, dict[int, pd.Series]],
    h4_filter: dict[tuple[int, int], pd.Series],
) -> list[dict[str, object]]:
    all_configs = [
        TrendConfig(
            entry_window=entry_window,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            four_h_fast=four_h_fast,
            four_h_slow=four_h_slow,
            atr_window=atr_window,
            target_atr_pct=target_atr_pct,
            max_allocation=max_allocation,
            stop_atr=stop_atr,
            trail_atr=trail_atr,
            long_enabled=long_enabled,
            short_enabled=short_enabled,
        )
        for entry_window in (24, 48, 72, 96, 120, 168, 192)
        for ema_fast, ema_slow in ((12, 48), (24, 96), (36, 120), (48, 168))
        for four_h_fast, four_h_slow in ((6, 24), (12, 36), (18, 48), (24, 72))
        for atr_window in (24, 48, 72, 96, 168)
        for target_atr_pct in (0.004, 0.006, 0.008, 0.012)
        for max_allocation in (1.0, 1.5, 2.0)
        for stop_atr in (3.0, 4.0, 6.0, 8.0)
        for trail_atr in (3.0, 4.0, 6.0, 8.0, 10.0)
        for long_enabled, short_enabled in ((True, False), (True, True))
    ]
    rng = random.Random(20260526)
    configs = rng.sample(all_configs, min(8000, len(all_configs)))
    rows: list[dict[str, object]] = []
    for config in configs:
        splits = _run_hourly_splits(h1, h1_features, h4_filter, config)
        full = splits["full"]
        train = splits["train"]
        val = splits["val"]
        test = splits["test"]
        if (
            full["entries"] >= 15
            and full["return"] > 0.0
            and full["max_drawdown"] > -0.45
            and train["return"] > -0.05
            and val["return"] > -0.05
            and test["return"] > -0.05
            and min(train["entries"], val["entries"], test["entries"]) >= 2
        ):
            score = min(_calmar(train), _calmar(val), _calmar(test)) + 0.25 * _calmar(full)
            rows.append(
                {
                    "config": asdict(config),
                    "score": score,
                    "train": train,
                    "val": val,
                    "test": test,
                    "full": full,
                }
            )
    return sorted(rows, key=lambda row: (row["score"], row["full"]["return"]), reverse=True)


def _run_hourly_splits(
    h1: pd.DataFrame,
    h1_features: dict[str, dict[int, pd.Series]],
    h4_filter: dict[tuple[int, int], pd.Series],
    config: TrendConfig,
) -> dict[str, dict[str, float | int | str]]:
    n = len(h1)
    start = max(config.entry_window, config.ema_slow, config.atr_window, 300)
    train_end = int(n * 0.55)
    val_end = int(n * 0.78)
    return {
        "train": _run_hourly(h1, h1_features, h4_filter, config, start, train_end),
        "val": _run_hourly(h1, h1_features, h4_filter, config, train_end, val_end),
        "test": _run_hourly(h1, h1_features, h4_filter, config, val_end, n - 1),
        "full": _run_hourly(h1, h1_features, h4_filter, config, start, n - 1),
    }


def _trend_arrays(
    h1: pd.DataFrame,
    h1_features: dict[str, dict[int, pd.Series]],
    h4_filter: dict[tuple[int, int], pd.Series],
    config: TrendConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    close = h1["close"]
    long_breakout = close.gt(h1_features["prior_high"][config.entry_window])
    short_breakout = close.lt(h1_features["prior_low"][config.entry_window])
    h1_ema_spread = (
        h1_features["ema"][config.ema_fast] / h1_features["ema"][config.ema_slow] - 1.0
    )
    h4_spread = h4_filter[(config.four_h_fast, config.four_h_slow)].reindex(
        h1.index,
        method="ffill",
    )
    long_signal = (
        long_breakout
        & h1_ema_spread.gt(0.0)
        & h4_spread.gt(0.0)
        & config.long_enabled
    )
    short_signal = (
        short_breakout
        & h1_ema_spread.lt(0.0)
        & h4_spread.lt(0.0)
        & config.short_enabled
    )
    exit_long = h1_ema_spread.lt(0.0) if config.exit_on_ema_cross else pd.Series(False, index=h1.index)
    exit_short = h1_ema_spread.gt(0.0) if config.exit_on_ema_cross else pd.Series(False, index=h1.index)
    signal = np.where(long_signal, 1, np.where(short_signal, -1, 0))
    exit_signal = np.where(exit_long, 1, np.where(exit_short, -1, 0))
    atr = h1_features["atr_pct"][config.atr_window].to_numpy()
    return signal.astype("int64"), exit_signal.astype("int64"), atr


def _run_hourly(
    h1: pd.DataFrame,
    h1_features: dict[str, dict[int, pd.Series]],
    h4_filter: dict[tuple[int, int], pd.Series],
    config: TrendConfig,
    start: int,
    end: int,
) -> dict[str, float | int | str]:
    signal, exit_signal, atr = _trend_arrays(h1, h1_features, h4_filter, config)
    return _simulate(
        index=h1.index,
        close=h1["close"].to_numpy(),
        high=h1["high"].to_numpy(),
        low=h1["low"].to_numpy(),
        signal=signal,
        exit_signal=exit_signal,
        atr=atr,
        config=config,
        start=start,
        end=end,
        annualization=HOURS_PER_YEAR,
    )


def _validate_on_15m(
    m15: pd.DataFrame,
    h1: pd.DataFrame,
    h1_features: dict[str, dict[int, pd.Series]],
    h4_filter: dict[tuple[int, int], pd.Series],
    candidates: list[dict[str, object]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    n = len(m15)
    train_end = int(n * 0.55)
    val_end = int(n * 0.78)
    for candidate in candidates:
        config = TrendConfig(**candidate["config"])
        h1_signal, h1_exit, h1_atr = _trend_arrays(h1, h1_features, h4_filter, config)
        signal = pd.Series(h1_signal, index=h1.index).shift(1).reindex(m15.index, method="ffill").fillna(0).to_numpy(dtype="int64")
        exit_signal = pd.Series(h1_exit, index=h1.index).shift(1).reindex(m15.index, method="ffill").fillna(0).to_numpy(dtype="int64")
        atr = pd.Series(h1_atr, index=h1.index).shift(1).reindex(m15.index, method="ffill").to_numpy()
        start = max(int(np.nanargmax(~np.isnan(atr))), 1200)
        splits = {
            "train": _simulate_m15(m15, signal, exit_signal, atr, config, start, train_end),
            "val": _simulate_m15(m15, signal, exit_signal, atr, config, train_end, val_end),
            "test": _simulate_m15(m15, signal, exit_signal, atr, config, val_end, n - 1),
            "full": _simulate_m15(m15, signal, exit_signal, atr, config, start, n - 1),
        }
        full = splits["full"]
        train = splits["train"]
        val = splits["val"]
        test = splits["test"]
        if (
            full["entries"] >= 10
            and full["return"] > 0.0
            and full["max_drawdown"] > -0.45
            and min(train["entries"], val["entries"], test["entries"]) >= 1
            and train["return"] > -0.1
            and val["return"] > -0.1
            and test["return"] > -0.1
        ):
            score = min(_calmar(train), _calmar(val), _calmar(test)) + 0.25 * _calmar(full)
            rows.append({"config": asdict(config), "score": score, **splits})
    return sorted(rows, key=lambda row: (row["score"], row["full"]["return"]), reverse=True)


def _simulate_m15(
    m15: pd.DataFrame,
    signal: np.ndarray,
    exit_signal: np.ndarray,
    atr: np.ndarray,
    config: TrendConfig,
    start: int,
    end: int,
) -> dict[str, float | int | str]:
    return _simulate(
        index=m15.index,
        close=m15["close"].to_numpy(),
        high=m15["high"].to_numpy(),
        low=m15["low"].to_numpy(),
        signal=signal,
        exit_signal=exit_signal,
        atr=atr,
        config=config,
        start=start,
        end=end,
        annualization=M15_PER_YEAR,
    )


def _simulate(
    *,
    index: pd.DatetimeIndex,
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    signal: np.ndarray,
    exit_signal: np.ndarray,
    atr: np.ndarray,
    config: TrendConfig,
    start: int,
    end: int,
    annualization: int,
) -> dict[str, float | int | str]:
    equity = 1.0
    position = 0
    allocation = 0.0
    entry_price = 0.0
    trail_ref = 0.0
    previous_price = close[start]
    entries = exits = stops = trails = ema_exits = 0
    equity_values: list[float] = []
    returns: list[float] = []
    weights: list[float] = []
    for i in range(start, end + 1):
        period_return = 0.0
        if position != 0:
            if position > 0:
                trail_ref = max(trail_ref, high[i])
                stop_price = entry_price * (1.0 - config.stop_atr * atr[i])
                trail_price = trail_ref * (1.0 - config.trail_atr * atr[i])
                exit_price = max(stop_price, trail_price)
                stop_hit = low[i] <= exit_price
                pnl = allocation * ((exit_price if stop_hit else close[i]) / previous_price - 1.0)
                should_ema_exit = exit_signal[i] == 1
            else:
                trail_ref = min(trail_ref, low[i])
                stop_price = entry_price * (1.0 + config.stop_atr * atr[i])
                trail_price = trail_ref * (1.0 + config.trail_atr * atr[i])
                exit_price = min(stop_price, trail_price)
                stop_hit = high[i] >= exit_price
                pnl = -allocation * ((exit_price if stop_hit else close[i]) / previous_price - 1.0)
                should_ema_exit = exit_signal[i] == -1
            equity *= 1.0 + pnl
            period_return += pnl
            if stop_hit or should_ema_exit:
                equity *= 1.0 - ROUND_TRIP_COST * allocation
                period_return -= ROUND_TRIP_COST * allocation
                exits += 1
                stops += int(stop_hit)
                trails += int(stop_hit)
                ema_exits += int(should_ema_exit and not stop_hit)
                position = 0
                allocation = 0.0
            previous_price = close[i]

        if position == 0 and signal[i] != 0 and not np.isnan(atr[i]) and atr[i] > 0.0:
            position = int(signal[i])
            allocation = min(config.max_allocation, config.target_atr_pct / float(atr[i]))
            entry_price = close[i]
            trail_ref = high[i] if position > 0 else low[i]
            previous_price = close[i]
            entries += 1
            equity *= 1.0 - ROUND_TRIP_COST * allocation
            period_return -= ROUND_TRIP_COST * allocation

        equity_values.append(equity)
        returns.append(period_return)
        weights.append(position * allocation)

    return _metrics(
        index=index[start : end + 1],
        close=close[start : end + 1],
        equity=np.array(equity_values),
        returns=np.array(returns),
        weights=np.array(weights),
        entries=entries,
        exits=exits,
        stops=stops,
        trails=trails,
        ema_exits=ema_exits,
        annualization=annualization,
    )


def _metrics(
    *,
    index: pd.DatetimeIndex,
    close: np.ndarray,
    equity: np.ndarray,
    returns: np.ndarray,
    weights: np.ndarray,
    entries: int,
    exits: int,
    stops: int,
    trails: int,
    ema_exits: int,
    annualization: int,
) -> dict[str, float | int | str]:
    drawdown = equity / np.maximum.accumulate(equity) - 1.0
    volatility = returns.std()
    buy_hold = close / close[0] - 1.0
    buy_hold_drawdown = close / np.maximum.accumulate(close) - 1.0
    return {
        "start": index.min().isoformat(),
        "end": index.max().isoformat(),
        "bars": int(len(index)),
        "return": float(equity[-1] - 1.0),
        "max_drawdown": float(drawdown.min()),
        "sharpe": float(0.0 if volatility == 0.0 else returns.mean() / volatility * np.sqrt(annualization)),
        "entries": int(entries),
        "exits": int(exits),
        "stops": int(stops),
        "trail_or_stop_exits": int(trails),
        "ema_exits": int(ema_exits),
        "avg_abs_weight": float(np.mean(np.abs(weights))),
        "max_abs_weight": float(np.max(np.abs(weights))),
        "buy_hold_return": float(buy_hold[-1]),
        "buy_hold_max_drawdown": float(buy_hold_drawdown.min()),
    }


def _calmar(metrics: dict[str, float | int | str]) -> float:
    max_drawdown = float(metrics["max_drawdown"])
    if max_drawdown >= 0.0:
        return 0.0
    return float(metrics["return"]) / abs(max_drawdown)


if __name__ == "__main__":
    main()
