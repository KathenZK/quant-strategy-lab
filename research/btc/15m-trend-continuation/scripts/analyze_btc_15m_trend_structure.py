from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/btc/15m-trend-continuation"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
AUDIT_PATH = ARTIFACT_DIR / "btc_binance_15m_long_data_quality_latest.json"
SUMMARY_PATH = ARTIFACT_DIR / "btc_15m_trend_structure_summary_2026-07-20.json"
OHLCV_ROOT = (
    ROOT / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m"
)
SYMBOL_FILE = "symbol=btc_usdt_usdt.parquet"
BAR = pd.Timedelta(minutes=15)
ROUND_TRIP_COST = 2.0 * (0.001 + 0.0004)
HORIZONS = (4, 16, 32, 96, 192)


@dataclass(frozen=True, slots=True)
class EventDefinition:
    name: str
    long: pd.Series
    short: pd.Series
    formula: str


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def payload_sha256(payload: dict[str, Any]) -> str:
    body = {key: value for key, value in payload.items() if key != "payload_sha256"}
    return sha256_bytes(canonical_json_bytes(body))


def finite(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): finite(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        if math.isfinite(number):
            return number
        return "inf" if number > 0 else "-inf"
    return value


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    complete = finite(payload)
    complete["payload_sha256"] = payload_sha256(complete)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(complete, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def date_paths(start: pd.Timestamp, end: pd.Timestamp) -> list[Path]:
    dates = pd.date_range(
        start.normalize(),
        (end - pd.Timedelta(nanoseconds=1)).normalize(),
        freq="1D",
    )
    paths = [OHLCV_ROOT / f"date={date:%Y-%m-%d}" / SYMBOL_FILE for date in dates]
    missing = [path for path in paths if not path.exists()]
    if missing:
        sample = ", ".join(str(path.relative_to(ROOT)) for path in missing[:3])
        raise FileNotFoundError(f"missing BTC 15m partitions: {sample}")
    return paths


def load_market() -> tuple[pd.DataFrame, dict[str, Any]]:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    if audit.get("total_blocker_count") != 0:
        raise RuntimeError("long-history data audit has blockers")
    start = pd.Timestamp(audit["research_start"])
    end = pd.Timestamp(audit["closed_bar_cutoff_exclusive"])
    columns = [
        "ts",
        "exchange",
        "symbol",
        "market_type",
        "timeframe",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "vwap",
        "is_closed",
        "source",
    ]
    pieces = [pd.read_parquet(path, columns=columns) for path in date_paths(start, end)]
    frame = pd.concat(pieces, ignore_index=True)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = (
        frame.loc[(frame["ts"] >= start) & (frame["ts"] < end)]
        .sort_values("ts")
        .reset_index(drop=True)
    )
    expected = pd.date_range(start, end - BAR, freq=BAR)
    checks = {
        "rows": len(frame) == len(expected),
        "continuity": pd.DatetimeIndex(frame["ts"]).equals(expected),
        "duplicates": not frame["ts"].duplicated().any(),
        "closed": bool(frame["is_closed"].all()),
        "identity": bool(
            frame["exchange"].eq("binance").all()
            and frame["symbol"].eq("BTC/USDT:USDT").all()
            and frame["market_type"].eq("perp").all()
            and frame["timeframe"].eq("15m").all()
        ),
        "critical_nulls": not frame[
            [
                "open",
                "high",
                "low",
                "close",
                "volume",
                "quote_volume",
                "trade_count",
                "vwap",
            ]
        ]
        .isna()
        .any()
        .any(),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise RuntimeError(f"trend-structure market checks failed: {failed}")
    metadata = {
        "audit_path": str(AUDIT_PATH.relative_to(ROOT)),
        "audit_sha256": sha256_bytes(AUDIT_PATH.read_bytes()),
        "start": start.isoformat(),
        "end_exclusive": end.isoformat(),
        "rows": len(frame),
        "checks": checks,
    }
    return frame.set_index("ts"), metadata


def ema(series: pd.Series, window: int) -> pd.Series:
    return series.ewm(
        alpha=2.0 / (window + 1.0),
        adjust=False,
        min_periods=window,
    ).mean()


def wilder_atr(frame: pd.DataFrame, window: int) -> pd.Series:
    previous = frame["close"].shift(1)
    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous).abs(),
            (frame["low"] - previous).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(
        alpha=1.0 / window,
        adjust=False,
        min_periods=window,
    ).mean()


def event_definitions(frame: pd.DataFrame) -> list[EventDefinition]:
    close = frame["close"]
    definitions: list[EventDefinition] = []
    for window in (48, 96, 192, 384, 768):
        upper = frame["high"].rolling(window, min_periods=window).max().shift(1)
        lower = frame["low"].rolling(window, min_periods=window).min().shift(1)
        definitions.append(
            EventDefinition(
                name=f"donchian_{window}",
                long=close.gt(upper),
                short=close.lt(lower),
                formula=(
                    f"close > prior {window}-bar high / close < prior "
                    f"{window}-bar low"
                ),
            )
        )

    fast = ema(close, 96)
    slow = ema(close, 384)
    long_regime = fast.gt(slow) & slow.gt(slow.shift(16))
    short_regime = fast.lt(slow) & slow.lt(slow.shift(16))
    for window in (96, 192, 384):
        upper = frame["high"].rolling(window, min_periods=window).max().shift(1)
        lower = frame["low"].rolling(window, min_periods=window).min().shift(1)
        definitions.append(
            EventDefinition(
                name=f"donchian_{window}_ema96_384",
                long=close.gt(upper) & long_regime,
                short=close.lt(lower) & short_regime,
                formula=(
                    f"Donchian {window} breakout aligned with EMA96/384 and "
                    "16-bar slow-EMA slope"
                ),
            )
        )

    atr = wilder_atr(frame, 96)
    atr_pct = atr / close
    rolling = 90 * 24 * 4
    minimum = 60 * 24 * 4
    compression_threshold = (
        atr_pct.rolling(rolling, min_periods=minimum).quantile(0.20).shift(1)
    )
    compressed_recently = (
        atr_pct.lt(compression_threshold)
        .rolling(32, min_periods=1)
        .max()
        .shift(1)
        .fillna(0.0)
        .gt(0.0)
    )
    upper_96 = frame["high"].rolling(96, min_periods=96).max().shift(1)
    lower_96 = frame["low"].rolling(96, min_periods=96).min().shift(1)
    definitions.append(
        EventDefinition(
            name="compression32_donchian96_ema96_384",
            long=compressed_recently & close.gt(upper_96) & long_regime,
            short=compressed_recently & close.lt(lower_96) & short_regime,
            formula=(
                "ATR96/close below its trailing 90d q20 within prior 32 bars, "
                "then Donchian96 breakout aligned with EMA96/384"
            ),
        )
    )

    previous_below_fast = close.shift(1).le(fast.shift(1))
    previous_above_fast = close.shift(1).ge(fast.shift(1))
    definitions.append(
        EventDefinition(
            name="ema96_reclaim_ema384_regime",
            long=previous_below_fast & close.gt(fast) & long_regime,
            short=previous_above_fast & close.lt(fast) & short_regime,
            formula=(
                "close reclaims EMA96 after prior close on opposite side, "
                "aligned with EMA96/384 and slow slope"
            ),
        )
    )
    return definitions


def non_overlapping_locations(
    locations: np.ndarray,
    horizon: int,
) -> np.ndarray:
    selected: list[int] = []
    next_allowed = -1
    for location in locations:
        if int(location) >= next_allowed:
            selected.append(int(location))
            next_allowed = int(location) + horizon
    return np.asarray(selected, dtype=int)


def profit_factor(values: np.ndarray) -> float:
    gains = float(values[values > 0.0].sum())
    losses = abs(float(values[values < 0.0].sum()))
    if losses == 0.0:
        return float("inf") if gains > 0.0 else 0.0
    return gains / losses


def event_rows(
    frame: pd.DataFrame,
    definition: EventDefinition,
) -> list[dict[str, Any]]:
    open_ = frame["open"].to_numpy(float)
    close = frame["close"].to_numpy(float)
    timestamps = frame.index
    direction = np.zeros(len(frame), dtype=int)
    direction[definition.long.fillna(False).to_numpy(bool)] = 1
    direction[definition.short.fillna(False).to_numpy(bool)] = -1
    rows: list[dict[str, Any]] = []

    for horizon in HORIZONS:
        valid = np.flatnonzero(direction != 0)
        valid = valid[(valid + horizon < len(frame)) & (valid + 1 < len(frame))]
        locations = non_overlapping_locations(valid, horizon)
        if locations.size == 0:
            continue
        side = direction[locations]
        entry = open_[locations + 1]
        exit_ = close[locations + horizon]
        raw = side * (exit_ / entry - 1.0)
        net_proxy = raw - ROUND_TRIP_COST
        for location, direction_value, raw_value, net_value in zip(
            locations,
            side,
            raw,
            net_proxy,
            strict=True,
        ):
            rows.append(
                {
                    "event": definition.name,
                    "formula": definition.formula,
                    "signal_ts": timestamps[location],
                    "entry_ts": timestamps[location + 1],
                    "year": timestamps[location].year,
                    "direction": "long" if direction_value == 1 else "short",
                    "horizon_bars": horizon,
                    "raw_return": raw_value,
                    "net_proxy_return": net_value,
                }
            )
    return rows


def aggregate_events(events: pd.DataFrame) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    group_columns = ["event", "horizon_bars"]
    for (event, horizon), group in events.groupby(group_columns, sort=True):
        raw = group["raw_return"].to_numpy(float)
        net = group["net_proxy_return"].to_numpy(float)
        yearly = (
            group.groupby("year")["net_proxy_return"]
            .mean()
            .mul(10_000.0)
            .to_dict()
        )
        summaries.append(
            {
                "event": event,
                "horizon_bars": int(horizon),
                "trades": len(group),
                "raw_mean_bps": float(raw.mean() * 10_000.0),
                "raw_median_bps": float(np.median(raw) * 10_000.0),
                "raw_win_rate": float((raw > 0.0).mean()),
                "raw_profit_factor": float(profit_factor(raw)),
                "net_proxy_mean_bps": float(net.mean() * 10_000.0),
                "net_proxy_win_rate": float((net > 0.0).mean()),
                "net_proxy_profit_factor": float(profit_factor(net)),
                "positive_year_mean_count": int(
                    sum(float(value) > 0.0 for value in yearly.values())
                ),
                "year_count": len(yearly),
                "yearly_net_proxy_mean_bps": yearly,
            }
        )
    return summaries


def market_profile(frame: pd.DataFrame) -> dict[str, Any]:
    close = frame["close"]
    returns = close.pct_change().dropna()
    atr_pct = wilder_atr(frame, 96) / close
    yearly = pd.DataFrame(
        {
            "return": returns,
            "atr_pct": atr_pct,
        }
    )
    yearly_rows: dict[str, Any] = {}
    for year, group in yearly.groupby(yearly.index.year):
        close_year = close.loc[close.index.year == year]
        yearly_rows[str(year)] = {
            "bars": len(group),
            "close_return_pct": float(
                (close_year.iloc[-1] / close_year.iloc[0] - 1.0) * 100.0
            ),
            "bar_return_std_bps": float(group["return"].std(ddof=0) * 10_000.0),
            "atr96_pct_median": float(group["atr_pct"].median() * 100.0),
        }
    return {
        "round_trip_cost_bps": ROUND_TRIP_COST * 10_000.0,
        "bar_return_mean_bps": float(returns.mean() * 10_000.0),
        "bar_return_std_bps": float(returns.std(ddof=0) * 10_000.0),
        "atr96_pct_median": float(atr_pct.median() * 100.0),
        "yearly": yearly_rows,
    }


def main() -> None:
    frame, data_metadata = load_market()
    definitions = event_definitions(frame)
    rows: list[dict[str, Any]] = []
    for definition in definitions:
        rows.extend(event_rows(frame, definition))
    events = pd.DataFrame(rows)
    if events.empty:
        raise RuntimeError("trend structure event study produced no events")

    script_path = Path(__file__).resolve()
    provenance = {
        "formula_version": "btc-15m-trend-structure-v1",
        "source_columns": ["ts", "open", "high", "low", "close", "volume"],
        "source_dataset": data_metadata,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "null_policy": "rolling indicators remain null until min_periods; null signals false",
        "fill_policy": "none",
        "code_path": str(script_path.relative_to(ROOT)),
        "code_sha256": sha256_bytes(script_path.read_bytes()),
        "funding_policy": (
            "excluded from fixed-horizon event study; outputs are structural diagnostics "
            "and cannot serve as strategy evidence"
        ),
        "cost_proxy": (
            "28 bps round-trip fee plus adverse slippage hurdle; strategy backtests "
            "must use fill-level costs and event funding"
        ),
    }
    summary = {
        "family": "BTC-15M-Trend-Continuation",
        "status": "explore / untrusted event diagnostic",
        "provenance": provenance,
        "market_profile": market_profile(frame),
        "event_definitions": [
            {"name": definition.name, "formula": definition.formula}
            for definition in definitions
        ],
        "event_summary": aggregate_events(events),
    }
    atomic_write_json(SUMMARY_PATH, summary)
    print(json.dumps(finite(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
