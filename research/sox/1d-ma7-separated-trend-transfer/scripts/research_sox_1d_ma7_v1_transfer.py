from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Any

from dateutil.relativedelta import MO, TH
import numpy as np
import pandas as pd
from pandas.tseries.holiday import (
    AbstractHolidayCalendar,
    GoodFriday,
    Holiday,
    nearest_workday,
)
from pandas.tseries.offsets import DateOffset


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/sox/1d-ma7-separated-trend-transfer"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
ENGINE_PATH = (
    ROOT
    / "research/hype/1d-ma7-asymmetric-body-trend/scripts"
    / "search_hype_1d_ma7_separated_trend.py"
)
ENGINE_SHA256 = (
    "c376f8bd1bae814b0ba53687380ee1060cf3cc3095ae815ebb0311ed1aef59e1"
)
YAHOO_URL = (
    "https://query2.finance.yahoo.com/v8/finance/chart/%5ESOX"
    "?period1=768058200&period2=1790000000"
    "&interval=1d&events=div%2Csplits"
)
HYPE_OVERLAP_START = date(2025, 5, 31)
HYPE_OVERLAP_END = date(2026, 7, 30)
ILLUSTRATIVE_FRICTION = 0.001


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
    quality: dict[str, Any]

    @property
    def count(self) -> int:
        return len(self.open)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Zero-tuning Yahoo ^SOX price-index transfer of "
            "HYPE-1D-MA7-Asymmetric-Body-Trend-V1."
        )
    )
    parser.add_argument(
        "--run-date",
        default=datetime.now(UTC).date().isoformat(),
    )
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def load_engine() -> Any:
    digest = hashlib.sha256(ENGINE_PATH.read_bytes()).hexdigest()
    if digest != ENGINE_SHA256:
        raise RuntimeError(
            f"source engine drift: expected {ENGINE_SHA256}, got {digest}"
        )
    spec = importlib.util.spec_from_file_location(
        "hype_ma7_v1_sox_transfer_engine",
        ENGINE_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {ENGINE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.FEE = 0.0
    module.BASE_SLIPPAGE = 0.0
    return module


def frozen_configs(engine: Any) -> tuple[Any, Any]:
    long_config = engine.Config(
        side=1,
        entry_mode="reclaim",
        slope_lookback=1,
        slope_min_atr=0.02,
        confirm_days=1,
        entry_buffer_atr=0.0,
        pullback_lookback=5,
        pullback_touch_atr=0.0,
        breakout_lookback=2,
        exit_confirm_days=1,
        exit_buffer_atr=0.75,
        slope_exit_lookback=0,
        hard_stop_atr=0.0,
        trail_atr=1.5,
        max_hold_days=90,
        cooldown_days=2,
    )
    short_config = engine.Config(
        side=-1,
        entry_mode="reclaim",
        slope_lookback=2,
        slope_min_atr=0.02,
        confirm_days=1,
        entry_buffer_atr=0.1,
        pullback_lookback=10,
        pullback_touch_atr=0.0,
        breakout_lookback=5,
        exit_confirm_days=1,
        exit_buffer_atr=0.25,
        slope_exit_lookback=1,
        hard_stop_atr=1.5,
        trail_atr=4.0,
        max_hold_days=20,
        cooldown_days=5,
    )
    return long_config, short_config


def _sunday_to_monday(timestamp: pd.Timestamp) -> pd.Timestamp:
    return timestamp + pd.Timedelta(days=1) if timestamp.weekday() == 6 else timestamp


class USExchangeHolidayCalendar(AbstractHolidayCalendar):
    rules = [
        Holiday(
            "New Years Day",
            month=1,
            day=1,
            observance=_sunday_to_monday,
        ),
        Holiday(
            "Martin Luther King Jr. Day",
            month=1,
            day=1,
            offset=DateOffset(weekday=MO(3)),
            start_date="1998-01-01",
        ),
        Holiday(
            "Washingtons Birthday",
            month=2,
            day=1,
            offset=DateOffset(weekday=MO(3)),
        ),
        GoodFriday,
        Holiday(
            "Memorial Day",
            month=5,
            day=31,
            offset=DateOffset(weekday=MO(-1)),
        ),
        Holiday(
            "Juneteenth",
            month=6,
            day=19,
            observance=nearest_workday,
            start_date="2022-01-01",
        ),
        Holiday(
            "Independence Day",
            month=7,
            day=4,
            observance=nearest_workday,
        ),
        Holiday(
            "Labor Day",
            month=9,
            day=1,
            offset=DateOffset(weekday=MO(1)),
        ),
        Holiday(
            "Thanksgiving",
            month=11,
            day=1,
            offset=DateOffset(weekday=TH(4)),
        ),
        Holiday(
            "Christmas",
            month=12,
            day=25,
            observance=nearest_workday,
        ),
    ]


SPECIAL_CLOSURES = {
    date(2001, 9, 11),
    date(2001, 9, 12),
    date(2001, 9, 13),
    date(2001, 9, 14),
    date(2004, 6, 11),
    date(2007, 1, 2),
    date(2012, 10, 29),
    date(2012, 10, 30),
    date(2018, 12, 5),
    date(2025, 1, 9),
}


def expected_sessions(first: date, last: date) -> set[date]:
    weekdays = pd.bdate_range(first, last)
    holidays = USExchangeHolidayCalendar().holidays(
        start=pd.Timestamp(first),
        end=pd.Timestamp(last),
    )
    return (
        set(weekdays.date)
        .difference(set(holidays.date))
        .difference(SPECIAL_CLOSURES)
    )


def fetch_yahoo(raw_path: Path, *, refresh: bool) -> bytes:
    if raw_path.exists() and not refresh:
        return raw_path.read_bytes()
    completed = subprocess.run(
        [
            "curl",
            "--fail",
            "--location",
            "--retry",
            "3",
            "--retry-delay",
            "2",
            "--silent",
            "--show-error",
            "--user-agent",
            "Mozilla/5.0",
            YAHOO_URL,
        ],
        check=True,
        capture_output=True,
    )
    content = completed.stdout
    if not content:
        raise RuntimeError("Yahoo returned an empty response")
    raw_path.write_bytes(content)
    return content


def parse_and_audit_yahoo(
    content: bytes,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    payload = json.loads(content)
    chart = payload.get("chart", {})
    if chart.get("error") is not None:
        raise RuntimeError(f"Yahoo chart error: {chart['error']}")
    results = chart.get("result") or []
    if len(results) != 1:
        raise RuntimeError(f"expected one Yahoo result, got {len(results)}")
    result = results[0]
    meta = result["meta"]
    timestamps = result.get("timestamp") or []
    quote = result["indicators"]["quote"][0]
    adjclose = result["indicators"]["adjclose"][0]["adjclose"]
    arrays = {
        "open": quote["open"],
        "high": quote["high"],
        "low": quote["low"],
        "close": quote["close"],
        "volume": quote["volume"],
        "adjclose": adjclose,
    }
    lengths = {"timestamp": len(timestamps), **{
        key: len(values) for key, values in arrays.items()
    }}
    if len(set(lengths.values())) != 1:
        raise RuntimeError(f"Yahoo array length mismatch: {lengths}")
    timezone = str(meta["exchangeTimezoneName"])
    ts_utc = pd.to_datetime(timestamps, unit="s", utc=True)
    session_dates = ts_utc.tz_convert(timezone).date
    frame = pd.DataFrame(
        {
            "session_date": pd.to_datetime(session_dates),
            "ts": ts_utc,
            **arrays,
        }
    )
    numeric = ["open", "high", "low", "close", "volume", "adjclose"]
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    nulls = {
        column: int(frame[column].isna().sum())
        for column in ["session_date", "ts", *numeric]
    }
    duplicate_dates = int(frame["session_date"].duplicated().sum())
    duplicate_ts = int(frame["ts"].duplicated().sum())
    invalid_ohlc = int(
        (
            (frame[["open", "high", "low", "close"]] <= 0.0).any(axis=1)
            | frame["high"].lt(
                frame[["open", "close", "low"]].max(axis=1)
            )
            | frame["low"].gt(
                frame[["open", "close", "high"]].min(axis=1)
            )
        ).sum()
    )
    adjclose_mismatch = int(
        (
            ~np.isclose(
                frame["close"].to_numpy("float64"),
                frame["adjclose"].to_numpy("float64"),
                rtol=1e-12,
                atol=1e-12,
                equal_nan=True,
            )
        ).sum()
    )
    adjclose_relative_diff = (
        frame["adjclose"].sub(frame["close"]).abs().div(frame["close"].abs())
    )
    observed = set(frame["session_date"].dt.date)
    expected = expected_sessions(min(observed), max(observed))
    missing_sessions = sorted(expected.difference(observed))
    unexpected_sessions = sorted(observed.difference(expected))
    blockers = (
        sum(nulls.values())
        + duplicate_dates
        + duplicate_ts
        + invalid_ohlc
        + len(missing_sessions)
        + len(unexpected_sessions)
    )
    quality = {
        "source": "Yahoo Finance chart API",
        "url": YAHOO_URL,
        "raw_sha256": hashlib.sha256(content).hexdigest(),
        "symbol": meta.get("symbol"),
        "long_name": meta.get("longName"),
        "exchange_name": meta.get("exchangeName"),
        "full_exchange_name": meta.get("fullExchangeName"),
        "instrument_type": meta.get("instrumentType"),
        "currency": meta.get("currency"),
        "exchange_timezone": timezone,
        "rows": int(len(frame)),
        "first_session": frame["session_date"].iloc[0].date().isoformat(),
        "last_session": frame["session_date"].iloc[-1].date().isoformat(),
        "nulls": nulls,
        "duplicate_dates": duplicate_dates,
        "duplicate_timestamps": duplicate_ts,
        "invalid_ohlc_rows": invalid_ohlc,
        "missing_expected_sessions": [
            item.isoformat() for item in missing_sessions
        ],
        "unexpected_sessions": [
            item.isoformat() for item in unexpected_sessions
        ],
        "zero_volume_rows": int(frame["volume"].eq(0.0).sum()),
        "adjclose_close_mismatch": adjclose_mismatch,
        "adjclose_max_relative_diff_bps": float(
            adjclose_relative_diff.max() * 10_000.0
        ),
        "calendar": (
            "US equity regular sessions with standard holidays and retained "
            "special full-day closures"
        ),
        "blocker_count": int(blockers),
    }
    if blockers:
        raise RuntimeError(f"Yahoo ^SOX data-quality blockers: {quality}")
    return frame, quality


def build_book_and_features(
    engine: Any,
    frame: pd.DataFrame,
    quality: dict[str, Any],
) -> tuple[Book, Any]:
    if len(frame) < 30:
        raise RuntimeError("insufficient ^SOX daily history")
    bars = frame.iloc[:-1].reset_index(drop=True)
    terminal = frame.iloc[-1]
    high = bars["high"].to_numpy("float64")
    low = bars["low"].to_numpy("float64")
    close = bars["close"].to_numpy("float64")
    previous_close = np.r_[np.nan, close[:-1]]
    true_range = np.nanmax(
        np.vstack(
            [
                high - low,
                np.abs(high - previous_close),
                np.abs(low - previous_close),
            ]
        ),
        axis=0,
    )
    ma7 = pd.Series(close).rolling(7).mean().to_numpy("float64")
    atr7 = pd.Series(true_range).rolling(7).mean().to_numpy("float64")
    hourly_open = bars["open"].to_numpy("float64").reshape(-1, 1)
    hourly_high = high.reshape(-1, 1)
    hourly_low = low.reshape(-1, 1)
    features = engine.Features(
        ma7=ma7,
        atr7=atr7,
        prior_high={},
        prior_low={},
        hourly_open=hourly_open,
        hourly_high=hourly_high,
        hourly_low=hourly_low,
        funding_events=[[] for _ in range(len(bars))],
    )
    book_quality = {
        **quality,
        "terminal_open": float(terminal["open"]),
        "terminal_session": terminal["session_date"].date().isoformat(),
        "backtest_daily_rows": int(len(bars)),
        "intraday_path_resolution": (
            "daily OHLC only; active stop gaps fill at session open and "
            "within-session touches fill at stop"
        ),
    }
    book = Book(
        ts=pd.DatetimeIndex(bars["ts"]),
        terminal_ts=pd.Timestamp(terminal["ts"]),
        open=bars["open"].to_numpy("float64"),
        short_entry_open=bars["open"].to_numpy("float64"),
        post_short_entry_high=high,
        post_short_entry_low=low,
        high=high,
        low=low,
        close=close,
        quality=book_quality,
    )
    return book, features


def normalize_result(result: Any) -> Any:
    close_equity = pd.Series(
        [1.0, *[
            float(row["close_equity"]) for row in result.path
        ]],
        dtype=float,
    )
    returns = (
        close_equity.pct_change()
        .replace([np.inf, -np.inf], np.nan)
        .dropna()
    )
    result.metrics["sharpe"] = (
        float(np.sqrt(252.0) * returns.mean() / returns.std(ddof=1))
        if len(returns) >= 30 and returns.std(ddof=1) > 0.0
        else math.nan
    )
    days = float(result.metrics["days"])
    equity = float(result.metrics["equity_multiple"])
    result.metrics["annualized_factor"] = (
        equity ** (365.25 / days) if equity > 0.0 else 0.0
    )
    positions = [int(row["position"]) for row in result.path[:-1]]
    result.metrics["exposure_pct"] = (
        100.0 * sum(position != 0 for position in positions) / len(positions)
        if positions
        else 0.0
    )
    return result


def run_variant(
    engine: Any,
    book: Book,
    features: Any,
    long_config: Any | None,
    short_config: Any | None,
    *,
    start: int,
    end: int,
    friction: float = 0.0,
    signal_lag: int = 0,
) -> Any:
    result = engine.backtest(
        book,
        features,
        long_config=long_config,
        short_config=short_config,
        start_index=start,
        terminal_index=end,
        slippage=friction,
        signal_lag=signal_lag,
        include_funding=False,
        retain=True,
    )
    return normalize_result(result)


def window_book_features(
    book: Book,
    features: Any,
    start: int,
    end: int,
) -> tuple[Book, Any]:
    terminal_ts = (
        book.terminal_ts if end == book.count else pd.Timestamp(book.ts[end])
    )
    terminal_open = (
        float(book.quality["terminal_open"])
        if end == book.count
        else float(book.open[end])
    )
    window_book = Book(
        ts=book.ts[start:end],
        terminal_ts=terminal_ts,
        open=book.open[start:end],
        short_entry_open=book.short_entry_open[start:end],
        post_short_entry_high=book.post_short_entry_high[start:end],
        post_short_entry_low=book.post_short_entry_low[start:end],
        high=book.high[start:end],
        low=book.low[start:end],
        close=book.close[start:end],
        quality={**book.quality, "terminal_open": terminal_open},
    )
    feature_type = type(features)
    window_features = feature_type(
        ma7=features.ma7[start:end],
        atr7=features.atr7[start:end],
        prior_high={},
        prior_low={},
        hourly_open=features.hourly_open[start:end],
        hourly_high=features.hourly_high[start:end],
        hourly_low=features.hourly_low[start:end],
        funding_events=features.funding_events[start:end],
    )
    return window_book, window_features


def buy_and_hold(
    engine: Any,
    book: Book,
    features: Any,
    start: int,
    end: int,
) -> dict[str, Any]:
    window_book, window_features = window_book_features(
        book,
        features,
        start,
        end,
    )
    return engine.buy_and_hold(
        window_book,
        window_features,
        slippage=0.0,
    )


def audit_window(
    engine: Any,
    book: Book,
    features: Any,
    long_config: Any,
    short_config: Any,
    *,
    start: int,
    end: int,
) -> dict[str, Any]:
    variants = {
        "combined": (long_config, short_config, 0.0, 0),
        "combined_10bps_per_fill": (
            long_config,
            short_config,
            ILLUSTRATIVE_FRICTION,
            0,
        ),
        "combined_one_session_delay": (
            long_config,
            short_config,
            0.0,
            1,
        ),
        "long_only": (long_config, None, 0.0, 0),
        "short_only": (None, short_config, 0.0, 0),
    }
    results = {
        label: run_variant(
            engine,
            book,
            features,
            long_leg,
            short_leg,
            start=start,
            end=end,
            friction=friction,
            signal_lag=lag,
        )
        for label, (long_leg, short_leg, friction, lag) in variants.items()
    }
    benchmark = buy_and_hold(engine, book, features, start, end)
    return {
        **{
            label: result.metrics for label, result in results.items()
        },
        "buy_and_hold": benchmark,
        "excess_return_pct": (
            results["combined"].metrics["net_return_pct"]
            - benchmark["net_return_pct"]
        ),
        "_results": results,
    }


def calendar_year_rows(
    engine: Any,
    book: Book,
    features: Any,
    long_config: Any,
    short_config: Any,
) -> list[dict[str, Any]]:
    dates = pd.DatetimeIndex(book.ts).tz_convert(
        book.quality["exchange_timezone"]
    )
    rows: list[dict[str, Any]] = []
    for year in range(dates[0].year, dates[-1].year + 1):
        indices = np.flatnonzero(dates.year == year)
        if len(indices) < 20:
            continue
        start = int(indices[0])
        end = min(int(indices[-1]) + 1, book.count)
        result = run_variant(
            engine,
            book,
            features,
            long_config,
            short_config,
            start=start,
            end=end,
        )
        rows.append({"year": year, **result.metrics})
    return rows


def rolling_three_year_rows(
    engine: Any,
    book: Book,
    features: Any,
    long_config: Any,
    short_config: Any,
) -> list[dict[str, Any]]:
    local = pd.DatetimeIndex(book.ts).tz_convert(
        book.quality["exchange_timezone"]
    )
    local_dates = np.asarray(local.date)
    first_year = local[0].year
    last_year = local[-1].year
    rows: list[dict[str, Any]] = []
    for year in range(first_year, last_year - 2):
        start_date = date(year, 1, 1)
        end_date = date(year + 3, 1, 1)
        start = int(np.searchsorted(local_dates, start_date, side="left"))
        end = int(np.searchsorted(local_dates, end_date, side="left"))
        if end - start < 500 or end > book.count:
            continue
        result = run_variant(
            engine,
            book,
            features,
            long_config,
            short_config,
            start=start,
            end=end,
        )
        rows.append(
            {
                "window_start_year": year,
                "window_end_year_exclusive": year + 3,
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
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def main() -> None:
    args = parse_args()
    engine = load_engine()
    long_config, short_config = frozen_configs(engine)
    if args.self_test:
        assert long_config.side == 1
        assert short_config.side == -1
        sessions = expected_sessions(date(2025, 1, 1), date(2025, 1, 10))
        assert date(2025, 1, 1) not in sessions
        assert date(2025, 1, 9) not in sessions
        assert date(2025, 1, 10) in sessions
        print("self-test: PASS")
        return

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = ARTIFACT_DIR / f"sox_yahoo_chart_1d_raw_{args.run_date}.json"
    content = fetch_yahoo(raw_path, refresh=args.refresh)
    frame, quality = parse_and_audit_yahoo(content)
    normalized_path = (
        ARTIFACT_DIR / f"sox_yahoo_1d_normalized_{args.run_date}.csv"
    )
    frame.to_csv(normalized_path, index=False)
    book, features = build_book_and_features(
        engine,
        frame,
        quality,
    )
    local_dates = np.asarray(
        pd.DatetimeIndex(book.ts)
        .tz_convert(quality["exchange_timezone"])
        .date
    )
    overlap_start = int(
        np.searchsorted(local_dates, HYPE_OVERLAP_START, side="left")
    )
    overlap_end = int(
        np.searchsorted(local_dates, HYPE_OVERLAP_END, side="left")
    )
    if overlap_start >= overlap_end:
        raise RuntimeError("HYPE calendar-overlap window unavailable")
    windows = {
        "full_available": (0, book.count),
        "hype_calendar_overlap": (overlap_start, overlap_end),
    }
    payload: dict[str, Any] = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "SOX-1D-MA7-Separated-Trend-Transfer",
        "source_version": (
            "HYPE-1D-MA7-Asymmetric-Body-Trend-V1"
        ),
        "status": "explore / not promoted / not live-ready",
        "selection": "zero SOX tuning; exact V1 parameter transfer",
        "source_engine": {
            "path": str(ENGINE_PATH.relative_to(ROOT)),
            "sha256": ENGINE_SHA256,
        },
        "data_quality": {
            **quality,
            "raw_artifact": str(raw_path.relative_to(ROOT)),
            "normalized_artifact": str(normalized_path.relative_to(ROOT)),
        },
        "instrument_limitations": {
            "tradability": (
                "^SOX is a price index, not a directly tradable instrument"
            ),
            "cost_model": (
                "unspecified; primary results use zero fees/slippage/borrow/"
                "financing and are price-path diagnostics only"
            ),
            "illustrative_friction": (
                "10 bps per fill sensitivity; not claimed as an executable "
                "SOX cost model"
            ),
            "dividends": (
                "raw OHLC is used consistently; Yahoo adjusted close differs "
                f"by at most {quality['adjclose_max_relative_diff_bps']:.2f} "
                "bps and is not an ETF total-return series"
            ),
            "intraday_resolution": (
                "daily OHLC; no historical intraday ordering within a "
                "session"
            ),
        },
        "long_config": asdict(long_config),
        "short_config": asdict(short_config),
        "windows": {},
    }
    metric_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    path_rows: list[dict[str, Any]] = []
    recent_rows: list[dict[str, Any]] = []
    for label, (start, end) in windows.items():
        audit = audit_window(
            engine,
            book,
            features,
            long_config,
            short_config,
            start=start,
            end=end,
        )
        results = audit.pop("_results")
        payload["windows"][label] = audit
        for variant, metrics in audit.items():
            if isinstance(metrics, dict):
                metric_rows.append(
                    {
                        "window": label,
                        "variant": variant,
                        **metrics,
                    }
                )
        if label == "full_available":
            for variant in ("combined", "long_only", "short_only"):
                result = results[variant]
                trade_rows.extend(
                    {
                        "variant": variant,
                        **trade,
                    }
                    for trade in result.trades
                )
                recent_rows.extend(
                    {
                        "variant": variant,
                        **row,
                    }
                    for row in engine.recent_slices(result)
                )
            path_rows.extend(results["combined"].path)

    annual = calendar_year_rows(
        engine,
        book,
        features,
        long_config,
        short_config,
    )
    rolling = rolling_three_year_rows(
        engine,
        book,
        features,
        long_config,
        short_config,
    )
    payload["stability"] = {
        "calendar_years": {
            "count": len(annual),
            "positive": sum(
                row["net_return_pct"] > 0.0 for row in annual
            ),
            "negative": sum(
                row["net_return_pct"] < 0.0 for row in annual
            ),
        },
        "rolling_3y": {
            "count": len(rolling),
            "positive": sum(
                row["net_return_pct"] > 0.0 for row in rolling
            ),
            "negative": sum(
                row["net_return_pct"] < 0.0 for row in rolling
            ),
            "min_return_pct": min(
                row["net_return_pct"] for row in rolling
            ),
            "median_return_pct": float(
                np.median([row["net_return_pct"] for row in rolling])
            ),
        },
    }
    stem = "sox_1d_ma7_v1_transfer"
    clean_payload = clean_json(payload)
    (ARTIFACT_DIR / f"{stem}_summary_{args.run_date}.json").write_text(
        json.dumps(
            clean_payload,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    pd.DataFrame(metric_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_metrics_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(trade_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_trades_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(path_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_path_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(recent_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_recent_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(annual).to_csv(
        ARTIFACT_DIR / f"{stem}_calendar_years_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(rolling).to_csv(
        ARTIFACT_DIR / f"{stem}_rolling_3y_{args.run_date}.csv",
        index=False,
    )
    print(
        json.dumps(
            {
                "quality": {
                    "rows": quality["rows"],
                    "first": quality["first_session"],
                    "last": quality["last_session"],
                    "blockers": quality["blocker_count"],
                },
                "windows": {
                    label: {
                        variant: {
                            "return_pct": metrics["net_return_pct"],
                            "mdd_pct": metrics.get(
                                "max_drawdown_pct"
                            ),
                            "trades": metrics.get("closed_trades"),
                        }
                        for variant, metrics in window.items()
                        if isinstance(metrics, dict)
                    }
                    for label, window in clean_payload["windows"].items()
                },
                "stability": clean_payload["stability"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
