from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent))
import hype_15m_signal_1h_confirm_bidirectional_search as dual15
import hype_new_trend_mechanism_search as base

from strategy_lab.data import DataLakeLayout, DatasetKind, DuckDBWarehouse, MarketType
from strategy_lab.data.normalize import normalize_dataset
from strategy_lab.data.store import write_dataframe
from strategy_lab.settings import load_settings


SYMBOL = "HYPE/USDT:USDT"
BINANCE_SYMBOL = "HYPEUSDT"
EXCHANGE = "binance"
EXECUTION_TIMEFRAME = "5m"
SIGNAL_TIMEFRAME = "15m"
INTERVAL_MS = 5 * 60 * 1000


def main() -> None:
    layout = DataLakeLayout.from_settings(load_settings(None))
    warehouse = DuckDBWarehouse(layout)
    before = _coverage(warehouse, DatasetKind.OHLCV, timeframe=EXECUTION_TIMEFRAME)
    refresh = _refresh_5m_data(layout, warehouse)
    m5, m15, funding = _load_data(warehouse)
    m5 = m5[m5.index <= m15.index.max()].copy()
    funding = funding.reindex(m5.index).fillna(0.0)
    h1 = base._resample_ohlcv(m15, "1h")
    features = dual15._build_features(m15, h1)
    config = _v2i_config()
    long_entry_15, long_exit_15, short_entry_15, short_exit_15, atr_15 = dual15._signals(features, config)
    signal_frame = _build_5m_signals(m5, m15, long_entry_15, long_exit_15, short_entry_15, short_exit_15, atr_15)
    start_ts = m15.index[1600]
    start = int(m5.index.searchsorted(start_ts))
    full = _run_5m(m5, funding, signal_frame, config, start, len(m5) - 1)
    periods = _periods(m5, funding, signal_frame, config, warm_start=start)
    result = {
        "symbol": SYMBOL,
        "strategy": "V2I 15m bidirectional signal with 5m execution",
        "data_before_refresh": before,
        "data_after_refresh": {
            "m5": _frame_coverage(m5),
            "m15": _frame_coverage(m15),
            "h1_from_15m": _frame_coverage(h1),
            "funding": _series_coverage(funding),
        },
        "refresh": refresh,
        "config": {
            **dual15.asdict(config),
            "execution_timeframe": EXECUTION_TIMEFRAME,
            "signal_timeframe": SIGNAL_TIMEFRAME,
            "hold_bars_converted_to_5m": {
                "max_hold_bars": config.max_hold_bars * 3,
                "short_max_hold_bars": config.short_max_hold_bars * 3,
                "cooldown_bars": config.cooldown_bars * 3,
            },
        },
        "full": full,
        "periods": periods,
        "v2i_15m_execution_reference": {
            "return": 2.2282,
            "max_drawdown": -0.2002,
            "sharpe": 2.93,
            "entries": 145,
        },
    }
    out = Path("archive/reports/legacy/hype_v2i_5m_execution_backtest.json")
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


def _v2i_config() -> dual15.Signal15mDualConfig:
    return dual15.Signal15mDualConfig(
        ema_fast=96,
        ema_slow=384,
        atr_window=192,
        keltner_multiplier=2.0,
        adx_window=28,
        adx_min=22.0,
        short_adx_boost=4.0,
        adx_exit=22.0,
        volume_window=96,
        min_volume_surge=0.5,
        short_volume_boost=0.5,
        confirm_1h="ema",
        short_confirm_1h="bear_adx_di",
        target_atr_pct=0.012,
        short_target_atr_pct=0.002,
        max_allocation=3.0,
        short_max_allocation=1.0,
        stop_atr=6.0,
        short_stop_atr=2.0,
        take_atr=6.0,
        short_take_atr=4.0,
        trail_atr=10.0,
        short_trail_atr=6.0,
        max_hold_bars=288,
        short_max_hold_bars=48,
        cooldown_bars=8,
    )


def _coverage(
    warehouse: DuckDBWarehouse,
    kind: DatasetKind,
    *,
    timeframe: str | None = None,
) -> dict[str, object]:
    columns = ["ts", "open", "high", "low", "close", "volume"] if kind == DatasetKind.OHLCV else ["ts", "funding_rate"]
    frame = warehouse.load_dataset(
        layer="normalized",
        kind=kind,
        exchange=EXCHANGE,
        market_type=MarketType.PERP,
        symbol=SYMBOL,
        timeframe=timeframe,
        columns=columns,
    )
    if frame.empty:
        return {"rows": 0}
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    return {"rows": int(len(frame)), "start": frame["ts"].min().isoformat(), "end": frame["ts"].max().isoformat()}


def _frame_coverage(frame: pd.DataFrame) -> dict[str, object]:
    return {"rows": int(len(frame)), "start": frame.index.min().isoformat(), "end": frame.index.max().isoformat()}


def _series_coverage(series: pd.Series) -> dict[str, object]:
    non_zero = series[series.ne(0.0)]
    return {
        "rows": int(len(series)),
        "non_zero_rows": int(len(non_zero)),
        "start": series.index.min().isoformat(),
        "end": series.index.max().isoformat(),
    }


def _load_data(warehouse: DuckDBWarehouse) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    def load_ohlcv(timeframe: str) -> pd.DataFrame:
        frame = warehouse.load_dataset(
            layer="normalized",
            kind=DatasetKind.OHLCV,
            exchange=EXCHANGE,
            market_type=MarketType.PERP,
            symbol=SYMBOL,
            timeframe=timeframe,
            columns=["ts", "open", "high", "low", "close", "volume"],
        )
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
        return frame.drop_duplicates("ts").sort_values("ts").set_index("ts")

    m5 = load_ohlcv(EXECUTION_TIMEFRAME)
    m15 = load_ohlcv(SIGNAL_TIMEFRAME)
    funding_frame = warehouse.load_dataset(
        layer="normalized",
        kind=DatasetKind.FUNDING_RATES,
        exchange=EXCHANGE,
        market_type=MarketType.PERP,
        symbol=SYMBOL,
        columns=["ts", "funding_rate"],
    )
    if funding_frame.empty:
        funding = pd.Series(0.0, index=m5.index)
    else:
        funding_frame["ts"] = pd.to_datetime(funding_frame["ts"], utc=True)
        funding = funding_frame.groupby("ts")["funding_rate"].last().reindex(m5.index).fillna(0.0)
    return m5, m15, funding


def _refresh_5m_data(layout: DataLakeLayout, warehouse: DuckDBWarehouse) -> dict[str, object]:
    existing = warehouse.load_dataset(
        layer="normalized",
        kind=DatasetKind.OHLCV,
        exchange=EXCHANGE,
        market_type=MarketType.PERP,
        symbol=SYMBOL,
        timeframe=EXECUTION_TIMEFRAME,
    )
    if existing.empty:
        since = pd.Timestamp("2025-05-30T00:00:00Z")
    else:
        existing["ts"] = pd.to_datetime(existing["ts"], utc=True)
        since = existing["ts"].max() + pd.Timedelta(minutes=5)
    until = pd.Timestamp.now("UTC").floor("5min") - pd.Timedelta(minutes=5)
    if since > until:
        return {"requested_since": since.isoformat(), "requested_until": until.isoformat(), "rows_fetched": 0, "paths_written": []}
    fetched = _fetch_klines(since, until)
    paths = _write_merged_partitions(layout, warehouse, fetched)
    return {
        "requested_since": since.isoformat(),
        "requested_until": until.isoformat(),
        "rows_fetched": int(len(fetched)),
        "paths_written": [str(path) for path in paths],
    }


def _binance_get(path: str, params: dict[str, object]) -> object:
    url = f"https://fapi.binance.com{path}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "strategy-lab/1.0"})
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _fetch_klines(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    rows: list[list[object]] = []
    cursor = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    while cursor <= end_ms:
        data = _binance_get(
            "/fapi/v1/klines",
            {"symbol": BINANCE_SYMBOL, "interval": EXECUTION_TIMEFRAME, "startTime": cursor, "endTime": end_ms, "limit": 1500},
        )
        if not data:
            break
        rows.extend(data)
        next_cursor = int(data[-1][0]) + INTERVAL_MS
        if next_cursor <= cursor:
            break
        cursor = next_cursor
        time.sleep(0.05)
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(
        rows,
        columns=[
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_volume",
            "trade_count",
            "taker_buy_base",
            "taker_buy_quote",
            "ignore",
        ],
    )
    volume = pd.to_numeric(frame["volume"], errors="coerce")
    quote_volume = pd.to_numeric(frame["quote_volume"], errors="coerce")
    return pd.DataFrame(
        {
            "ts": pd.to_datetime(frame["open_time"], unit="ms", utc=True),
            "exchange": EXCHANGE,
            "symbol": SYMBOL,
            "market_type": MarketType.PERP.value,
            "open": frame["open"],
            "high": frame["high"],
            "low": frame["low"],
            "close": frame["close"],
            "volume": frame["volume"],
            "quote_volume": frame["quote_volume"],
            "trade_count": frame["trade_count"],
            "vwap": quote_volume / volume.replace(0.0, pd.NA),
            "is_closed": True,
            "source": "binance_futures_api",
            "timeframe": EXECUTION_TIMEFRAME,
        }
    )


def _write_merged_partitions(
    layout: DataLakeLayout,
    warehouse: DuckDBWarehouse,
    fetched: pd.DataFrame,
) -> list[Path]:
    if fetched.empty:
        return []
    fetched = normalize_dataset(DatasetKind.OHLCV, fetched)
    existing = warehouse.load_dataset(
        layer="normalized",
        kind=DatasetKind.OHLCV,
        exchange=EXCHANGE,
        market_type=MarketType.PERP,
        symbol=SYMBOL,
        timeframe=EXECUTION_TIMEFRAME,
    )
    if not existing.empty:
        existing["ts"] = pd.to_datetime(existing["ts"], utc=True)
    paths = []
    for partition_date, group in fetched.groupby(fetched["ts"].dt.date, sort=True):
        if existing.empty:
            merged = group.copy()
        else:
            existing_day = existing[pd.to_datetime(existing["ts"], utc=True).dt.date == partition_date]
            merged = pd.concat([existing_day, group], ignore_index=True, sort=False)
        merged = normalize_dataset(DatasetKind.OHLCV, merged).drop_duplicates(
            ["ts", "exchange", "symbol", "market_type", "timeframe"],
            keep="last",
        )
        paths.append(
            write_dataframe(
                merged.reset_index(drop=True),
                layout=layout,
                layer="normalized",
                kind=DatasetKind.OHLCV,
                exchange=EXCHANGE,
                market_type=MarketType.PERP,
                symbol=SYMBOL,
                partition_date=partition_date,
                timeframe=EXECUTION_TIMEFRAME,
            )
        )
    return paths


def _build_5m_signals(
    m5: pd.DataFrame,
    m15: pd.DataFrame,
    long_entry_15: np.ndarray,
    long_exit_15: np.ndarray,
    short_entry_15: np.ndarray,
    short_exit_15: np.ndarray,
    atr_15: np.ndarray,
) -> pd.DataFrame:
    signal_15 = pd.DataFrame(
        {
            "long_entry": long_entry_15,
            "long_exit": long_exit_15,
            "short_entry": short_entry_15,
            "short_exit": short_exit_15,
            "atr": atr_15,
        },
        index=m15.index,
    )
    signal_5 = pd.DataFrame(False, index=m5.index, columns=["long_entry", "long_exit", "short_entry", "short_exit"])
    shared_index = signal_5.index.intersection(signal_15.index)
    signal_5.loc[shared_index, ["long_entry", "long_exit", "short_entry", "short_exit"]] = signal_15.loc[
        shared_index,
        ["long_entry", "long_exit", "short_entry", "short_exit"],
    ].astype(bool)
    signal_5["atr"] = signal_15["atr"].reindex(m5.index, method="ffill")
    return signal_5


def _run_5m(
    m5: pd.DataFrame,
    funding: pd.Series,
    signal: pd.DataFrame,
    config: dual15.Signal15mDualConfig,
    start: int,
    end: int,
) -> dict[str, float | int | str]:
    close = m5["close"].to_numpy(dtype="float64")
    high = m5["high"].to_numpy(dtype="float64")
    low = m5["low"].to_numpy(dtype="float64")
    funding_values = funding.reindex(m5.index).fillna(0.0).to_numpy(dtype="float64")
    long_entry = signal["long_entry"].to_numpy(dtype=bool)
    long_exit = signal["long_exit"].to_numpy(dtype=bool)
    short_entry = signal["short_entry"].to_numpy(dtype=bool)
    short_exit = signal["short_exit"].to_numpy(dtype=bool)
    atr = signal["atr"].to_numpy(dtype="float64")

    max_hold_bars = config.max_hold_bars * 3
    short_max_hold_bars = config.short_max_hold_bars * 3
    cooldown_bars = config.cooldown_bars * 3

    equity = 1.0
    position = 0
    allocation = 0.0
    entry_price = 0.0
    previous_price = close[start]
    high_water = close[start]
    low_water = close[start]
    hold_bars = 0
    cooldown = 0
    entries = exits = long_entries = short_entries = stops = takes = trails = timeouts = indicator_exits = 0
    equity_values: list[float] = []
    returns: list[float] = []
    weights: list[float] = []

    for i in range(start, end + 1):
        period_return = 0.0
        if position != 0:
            hold_bars += 1
            high_water = max(high_water, high[i])
            low_water = min(low_water, low[i])
            if position > 0:
                stop_price = entry_price * (1.0 - config.stop_atr * atr[i])
                take_price = entry_price * (1.0 + config.take_atr * atr[i])
                trail_price = high_water * (1.0 - config.trail_atr * atr[i])
                stop_hit = low[i] <= stop_price
                take_hit = high[i] >= take_price
                trail_hit = low[i] <= trail_price and close[i] > entry_price
                indicator_exit = bool(long_exit[i])
                timed_out = hold_bars >= max_hold_bars
                exit_price = stop_price if stop_hit else trail_price if trail_hit else take_price if take_hit else close[i]
                pnl = allocation * (exit_price / previous_price - 1.0) - allocation * funding_values[i]
            else:
                stop_price = entry_price * (1.0 + config.short_stop_atr * atr[i])
                take_price = entry_price * (1.0 - config.short_take_atr * atr[i])
                trail_price = low_water * (1.0 + config.short_trail_atr * atr[i])
                stop_hit = high[i] >= stop_price
                take_hit = low[i] <= take_price
                trail_hit = high[i] >= trail_price and close[i] < entry_price
                indicator_exit = bool(short_exit[i])
                timed_out = hold_bars >= short_max_hold_bars
                exit_price = stop_price if stop_hit else trail_price if trail_hit else take_price if take_hit else close[i]
                pnl = allocation * (previous_price / exit_price - 1.0) + allocation * funding_values[i]
            equity *= 1.0 + pnl
            period_return += pnl
            if stop_hit or trail_hit or take_hit or indicator_exit or timed_out:
                equity *= 1.0 - base.ROUND_TRIP_COST * allocation
                period_return -= base.ROUND_TRIP_COST * allocation
                exits += 1
                stops += int(stop_hit)
                trails += int(trail_hit and not stop_hit)
                takes += int(take_hit and not stop_hit and not trail_hit)
                indicator_exits += int(indicator_exit and not stop_hit and not trail_hit and not take_hit)
                timeouts += int(timed_out and not stop_hit and not trail_hit and not take_hit and not indicator_exit)
                position = 0
                allocation = 0.0
                cooldown = cooldown_bars
            previous_price = close[i]

        if position == 0:
            if cooldown > 0:
                cooldown -= 1
            elif np.isfinite(atr[i]) and atr[i] > 0.0:
                if long_entry[i] and not short_entry[i]:
                    position = 1
                    allocation = min(config.max_allocation, config.target_atr_pct / float(atr[i]))
                    long_entries += 1
                elif short_entry[i] and not long_entry[i]:
                    position = -1
                    allocation = min(config.short_max_allocation, config.short_target_atr_pct / float(atr[i]))
                    short_entries += 1
                if position != 0:
                    entry_price = close[i]
                    previous_price = close[i]
                    high_water = high[i]
                    low_water = low[i]
                    hold_bars = 0
                    entries += 1
                    equity *= 1.0 - base.ROUND_TRIP_COST * allocation
                    period_return -= base.ROUND_TRIP_COST * allocation

        equity_values.append(equity)
        returns.append(period_return)
        weights.append(position * allocation)

    return _metrics(
        index=m5.index[start : end + 1],
        close=close[start : end + 1],
        equity=np.array(equity_values),
        returns=np.array(returns),
        weights=np.array(weights),
        entries=entries,
        exits=exits,
        long_entries=long_entries,
        short_entries=short_entries,
        stops=stops,
        takes=takes,
        trails=trails,
        timeouts=timeouts,
        indicator_exits=indicator_exits,
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
    long_entries: int,
    short_entries: int,
    stops: int,
    takes: int,
    trails: int,
    timeouts: int,
    indicator_exits: int,
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
        "sharpe": float(0.0 if volatility == 0.0 else returns.mean() / volatility * np.sqrt(365 * 24 * 12)),
        "entries": int(entries),
        "exits": int(exits),
        "long_entries": int(long_entries),
        "short_entries": int(short_entries),
        "stops": int(stops),
        "takes": int(takes),
        "trails": int(trails),
        "timeouts": int(timeouts),
        "indicator_exits": int(indicator_exits),
        "avg_abs_weight": float(np.mean(np.abs(weights))),
        "max_abs_weight": float(np.max(np.abs(weights))),
        "buy_hold_return": float(buy_hold[-1]),
        "buy_hold_max_drawdown": float(buy_hold_drawdown.min()),
    }


def _periods(
    m5: pd.DataFrame,
    funding: pd.Series,
    signal_frame: pd.DataFrame,
    config: dual15.Signal15mDualConfig,
    *,
    warm_start: int,
) -> dict[str, dict[str, float | int | str]]:
    out = {}
    end = len(m5) - 1
    for name, days in (("1w", 7), ("1m", 30), ("3m", 90), ("6m", 180), ("1y", 365)):
        start_ts = m5.index[-1] - pd.Timedelta(days=days)
        start = max(warm_start, int(m5.index.searchsorted(start_ts)))
        out[name] = _run_5m(m5, funding, signal_frame, config, start, end)
    return out


if __name__ == "__main__":
    main()
