from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, date, datetime
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
FAMILY_DIR = ROOT / "research/mu/1d-ma7-separated-trend-transfer"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
HYPE_HELPER_PATH = (
    ROOT
    / "research/hype/1d-ma7-asymmetric-body-trend/scripts/"
    "audit_hype_1d_v1_ema7_substitution.py"
)
HYPE_HELPER_SHA256 = (
    "3a2837dd1d315f477270c555fac74b35efed4ff102facfe65171e54cb77d5dc5"
)
MU_AUDIT_PATH = ROOT / "research/mu/scripts/refresh_and_audit_mu_binance_15m.py"
MU_AUDIT_SHA256 = (
    "84c78a2c1bfc3ab7ce551d02385ebfa0887e581d8c65853874cd6bf3e98e82b0"
)
SOX_HELPER_PATH = (
    ROOT
    / "research/sox/1d-ma7-separated-trend-transfer/scripts/"
    "research_sox_1d_ma7_v1_transfer.py"
)
SOX_HELPER_SHA256 = (
    "84f08d9d83235e76e7009c46717157e784bacdf0b04945165bcccc11a42a72fb"
)
BINANCE_NORMALIZED_ROOT = (
    ROOT / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m"
)
BINANCE_RAW_ROOT = (
    ROOT / "data/raw/ohlcv/exchange=binance/market_type=perp/timeframe=15m"
)
BINANCE_NORMALIZED_FUNDING_ROOT = (
    ROOT / "data/normalized/funding_rates/exchange=binance/market_type=perp"
)
BINANCE_RAW_FUNDING_ROOT = (
    ROOT / "data/raw/funding_rates/exchange=binance/market_type=perp"
)
NASDAQ_RAW_ROOT = (
    ROOT
    / "data/raw/ohlcv/exchange=nasdaq/market_type=equity/"
    "timeframe=1d/source=yahoo_finance"
)
SYMBOL_FILE_BINANCE = "symbol=mu_usdt_usdt.parquet"
SYMBOL_FILE_NASDAQ = "symbol=mu.parquet"
RECENT_DAYS = {
    "1d": 1,
    "7d": 7,
    "1m": 30,
    "3m": 90,
    "6m": 182,
    "1y": 365,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Zero-tuning HYPE daily MA7 V1 transfer to Binance MUUSDT "
            "and Nasdaq MU."
        )
    )
    parser.add_argument(
        "--run-date",
        default=datetime.now(UTC).date().isoformat(),
    )
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def load_module(path: Path, expected_hash: str, name: str) -> Any:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected_hash:
        raise RuntimeError(
            f"{path.name} drift: expected {expected_hash}, got {digest}"
        )
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_parquets(root: Path, filename: str) -> pd.DataFrame:
    files = sorted(root.rglob(filename))
    if not files:
        raise FileNotFoundError(f"no {filename} under {root}")
    return pd.concat(
        [pd.read_parquet(path) for path in files],
        ignore_index=True,
    )


def load_binance_data(
    mu_audit: Any,
) -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame, dict[str, Any]]:
    normalized = load_parquets(
        BINANCE_NORMALIZED_ROOT,
        SYMBOL_FILE_BINANCE,
    )
    raw = load_parquets(BINANCE_RAW_ROOT, SYMBOL_FILE_BINANCE)
    normalized["ts"] = pd.to_datetime(normalized["ts"], utc=True)
    raw["open_time"] = pd.to_datetime(raw["open_time"], utc=True)
    normalized = normalized.sort_values("ts").reset_index(drop=True)
    raw = raw.sort_values("open_time").reset_index(drop=True)
    quality = mu_audit.audit_ohlcv(raw, normalized)
    identity = {
        "exchange": sorted(normalized["exchange"].astype(str).unique()),
        "symbol": sorted(normalized["symbol"].astype(str).unique()),
        "market_type": sorted(
            normalized["market_type"].astype(str).unique()
        ),
        "timeframe": sorted(normalized["timeframe"].astype(str).unique()),
        "source": sorted(normalized["source"].astype(str).unique()),
    }
    expected_identity = {
        "exchange": ["binance"],
        "symbol": ["MU/USDT:USDT"],
        "market_type": ["perp"],
        "timeframe": ["15m"],
        "source": ["binance_futures_kline_api"],
    }
    if identity != expected_identity:
        raise RuntimeError(f"Binance MU identity mismatch: {identity}")
    quality["identity"] = identity
    quality["contract_type"] = "TRADIFI_PERPETUAL"
    quality["underlying_type"] = "EQUITY"

    normalized_funding = load_parquets(
        BINANCE_NORMALIZED_FUNDING_ROOT,
        SYMBOL_FILE_BINANCE,
    )
    raw_funding = load_parquets(
        BINANCE_RAW_FUNDING_ROOT,
        SYMBOL_FILE_BINANCE,
    )
    normalized_funding["ts"] = pd.to_datetime(
        normalized_funding["ts"],
        utc=True,
    )
    raw_funding["funding_time"] = pd.to_datetime(
        raw_funding["funding_time"],
        utc=True,
    )
    normalized_funding = normalized_funding.sort_values("ts").reset_index(
        drop=True
    )
    raw_funding = raw_funding.sort_values("funding_time").reset_index(
        drop=True
    )
    funding_quality = mu_audit.audit_funding(
        raw_funding,
        normalized_funding,
    )
    return normalized, quality, normalized_funding, funding_quality


def aggregate_hourly(
    bars_15m: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    frame = bars_15m.copy()
    frame["hour"] = frame["ts"].dt.floor("1h")
    rows: list[dict[str, Any]] = []
    incomplete = 0
    for hour, part in frame.groupby("hour", sort=True):
        part = part.sort_values("ts")
        expected = pd.date_range(hour, periods=4, freq="15min")
        if len(part) != 4 or not pd.DatetimeIndex(part["ts"]).equals(
            expected
        ):
            incomplete += 1
            continue
        volume = float(part["volume"].sum())
        quote_volume = float(part["quote_volume"].sum())
        rows.append(
            {
                "ts": pd.Timestamp(hour),
                "open": float(part.iloc[0]["open"]),
                "high": float(part["high"].max()),
                "low": float(part["low"].min()),
                "close": float(part.iloc[-1]["close"]),
                "volume": volume,
                "quote_volume": quote_volume,
                "trade_count": int(part["trade_count"].sum()),
                "vwap": (
                    quote_volume / volume
                    if volume > 0.0
                    else float(part.iloc[-1]["close"])
                ),
                "is_closed": bool(part["is_closed"].all()),
                "source": "binance_futures_kline_api",
            }
        )
    hourly = pd.DataFrame(rows)
    expected_hours = pd.date_range(
        hourly["ts"].iloc[0],
        hourly["ts"].iloc[-1],
        freq="1h",
    )
    missing = expected_hours.difference(pd.DatetimeIndex(hourly["ts"]))
    invalid = int(
        (
            (hourly[["open", "high", "low", "close"]] <= 0.0).any(axis=1)
            | hourly["high"].lt(
                hourly[["open", "close", "low"]].max(axis=1)
            )
            | hourly["low"].gt(
                hourly[["open", "close", "high"]].min(axis=1)
            )
        ).sum()
    )
    blockers = (
        len(missing)
        + int(hourly["ts"].duplicated().sum())
        + int(hourly.isna().any(axis=1).sum())
        + invalid
        + int((~hourly["is_closed"]).sum())
    )
    if blockers:
        raise RuntimeError(f"MU hourly aggregation blockers={blockers}")
    quality = {
        "source_timeframe": "15m",
        "output_timeframe": "1h",
        "rows": len(hourly),
        "first_ts": hourly["ts"].iloc[0].isoformat(),
        "last_ts": hourly["ts"].iloc[-1].isoformat(),
        "incomplete_edge_hours_dropped": incomplete,
        "missing_hours": len(missing),
        "invalid_ohlc_rows": invalid,
        "blocker_count": blockers,
    }
    return hourly, quality


def load_nasdaq_data(
    sox: Any,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    frame = load_parquets(NASDAQ_RAW_ROOT, SYMBOL_FILE_NASDAQ)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = frame.sort_values("ts").reset_index(drop=True)
    core = ["ts", "open", "high", "low", "close", "volume", "adj_close"]
    nulls = {column: int(frame[column].isna().sum()) for column in core}
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
            | frame["volume"].lt(0.0)
        ).sum()
    )
    identity = {
        "exchange": sorted(frame["exchange"].astype(str).unique()),
        "symbol": sorted(frame["symbol"].astype(str).unique()),
        "market_type": sorted(frame["market_type"].astype(str).unique()),
        "timeframe": sorted(frame["timeframe"].astype(str).unique()),
        "source": sorted(frame["source"].astype(str).unique()),
        "quality_status": sorted(
            frame["quality_status"].astype(str).unique()
        ),
    }
    expected_identity = {
        "exchange": ["nasdaq"],
        "symbol": ["MU"],
        "market_type": ["equity"],
        "timeframe": ["1d"],
        "source": ["yahoo_finance"],
        "quality_status": ["raw_unaccepted"],
    }
    if identity != expected_identity:
        raise RuntimeError(f"Nasdaq MU identity mismatch: {identity}")
    local = pd.DatetimeIndex(frame["ts"]).tz_convert("America/New_York")
    frame["session_date"] = pd.to_datetime(local.date)
    observed = set(frame["session_date"].dt.date)
    expected = sox.expected_sessions(min(observed), max(observed))
    missing_sessions = sorted(expected.difference(observed))
    unexpected_sessions = sorted(observed.difference(expected))
    adj_diff = (
        frame["adj_close"].sub(frame["close"]).abs().div(frame["close"].abs())
    )
    blocking_issues = [
        "quality_status=raw_unaccepted",
        "missing explicit is_closed",
        "missing quote_volume/trade_count/vwap",
        "provider adjustment policy not accepted",
    ]
    mechanical_blockers = (
        sum(nulls.values())
        + duplicate_ts
        + invalid_ohlc
        + len(missing_sessions)
        + len(unexpected_sessions)
    )
    if mechanical_blockers:
        raise RuntimeError(
            "Nasdaq MU mechanical blockers: "
            f"nulls={nulls}, duplicate={duplicate_ts}, invalid={invalid_ohlc}, "
            f"missing_sessions={missing_sessions}, "
            f"unexpected_sessions={unexpected_sessions}"
        )
    quality = {
        "exchange": "nasdaq",
        "market_type": "equity",
        "symbol": "MU",
        "source": "yahoo_finance",
        "source_dataset_id": sorted(
            frame["source_dataset_id"].astype(str).unique()
        ),
        "quality_status": "raw_unaccepted",
        "accepted_for_strategy_evidence": False,
        "identity": identity,
        "rows": len(frame),
        "first_session": min(observed).isoformat(),
        "last_session": max(observed).isoformat(),
        "nulls": nulls,
        "duplicate_ts": duplicate_ts,
        "invalid_ohlc_rows": invalid_ohlc,
        "missing_expected_sessions": [
            item.isoformat() for item in missing_sessions
        ],
        "unexpected_sessions": [
            item.isoformat() for item in unexpected_sessions
        ],
        "adjclose_close_mismatch_rows": int(
            (~np.isclose(
                frame["adj_close"].to_numpy("float64"),
                frame["close"].to_numpy("float64"),
                rtol=1e-12,
                atol=1e-12,
            )).sum()
        ),
        "adjclose_max_relative_diff_bps": float(adj_diff.max() * 10_000.0),
        "mechanical_blocker_count": mechanical_blockers,
        "acceptance_blockers": blocking_issues,
        "calendar": "US equity regular-session calendar",
        "exchange_timezone": "America/New_York",
    }
    return frame, quality


def slice_book_features(
    sox: Any,
    book: Any,
    features: Any,
    start: int,
    end: int,
) -> tuple[Any, Any]:
    terminal_ts = (
        book.terminal_ts if end == book.count else pd.Timestamp(book.ts[end])
    )
    terminal_open = (
        float(book.quality["terminal_open"])
        if end == book.count
        else float(book.open[end])
    )
    sliced_book = sox.Book(
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
    sliced_features = feature_type(
        ma7=features.ma7[start:end],
        atr7=features.atr7[start:end],
        prior_high={
            key: values[start:end]
            for key, values in features.prior_high.items()
        },
        prior_low={
            key: values[start:end]
            for key, values in features.prior_low.items()
        },
        hourly_open=features.hourly_open[start:end],
        hourly_high=features.hourly_high[start:end],
        hourly_low=features.hourly_low[start:end],
        funding_events=features.funding_events[start:end],
    )
    return sliced_book, sliced_features


def run_binance(
    engine: Any,
    book: Any,
    features: Any,
    long_config: Any | None,
    short_config: Any | None,
    *,
    start: int,
    end: int,
    slippage: float | None = None,
    signal_lag: int = 0,
) -> Any:
    kwargs: dict[str, Any] = {}
    if slippage is not None:
        kwargs["slippage"] = slippage
    return engine.backtest(
        book,
        features,
        long_config=long_config,
        short_config=short_config,
        start_index=start,
        terminal_index=end,
        signal_lag=signal_lag,
        retain=True,
        **kwargs,
    )


def audit_binance_window(
    engine: Any,
    sox: Any,
    book: Any,
    features: Any,
    long_config: Any,
    short_config: Any,
    *,
    start: int,
    end: int,
) -> dict[str, Any]:
    variants = {
        "combined": (long_config, short_config, None, 0),
        "combined_8bps": (
            long_config,
            short_config,
            engine.STRESS_SLIPPAGE,
            0,
        ),
        "combined_one_day_delay": (
            long_config,
            short_config,
            None,
            1,
        ),
        "long_only": (long_config, None, None, 0),
        "short_only": (None, short_config, None, 0),
    }
    output: dict[str, Any] = {"_results": {}}
    for label, (long_leg, short_leg, slippage, lag) in variants.items():
        result = run_binance(
            engine,
            book,
            features,
            long_leg,
            short_leg,
            start=start,
            end=end,
            slippage=slippage,
            signal_lag=lag,
        )
        output[label] = result.metrics
        output["_results"][label] = result
    window_book, window_features = slice_book_features(
        sox,
        book,
        features,
        start,
        end,
    )
    output["buy_and_hold"] = engine.buy_and_hold(
        window_book,
        window_features,
    )
    output["excess_return_pct"] = (
        output["combined"]["net_return_pct"]
        - output["buy_and_hold"]["net_return_pct"]
    )
    return output


def rolling_90d(
    market: str,
    run_fn: Any,
    book: Any,
    features: Any,
    long_config: Any,
    short_config: Any,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    timestamps = pd.DatetimeIndex([*book.ts, book.terminal_ts])
    start_time = timestamps[0]
    final_time = timestamps[-1]
    window_index = 0
    while start_time + pd.Timedelta(days=90) <= final_time:
        start = int(timestamps.searchsorted(start_time, side="left"))
        end = int(
            timestamps.searchsorted(
                start_time + pd.Timedelta(days=90),
                side="left",
            )
        )
        if end > start:
            for variant, long_leg, short_leg in (
                ("combined", long_config, short_config),
                ("long_only", long_config, None),
                ("short_only", None, short_config),
            ):
                result = run_fn(
                    book,
                    features,
                    long_leg,
                    short_leg,
                    start,
                    end,
                )
                rows.append(
                    {
                        "market": market,
                        "variant": variant,
                        "window_index": window_index,
                        **result.metrics,
                    }
                )
        start_time += pd.Timedelta(days=30)
        window_index += 1
    return rows


def recent_rows(
    engine: Any,
    market: str,
    variant: str,
    result: Any,
) -> list[dict[str, Any]]:
    span = (
        pd.Timestamp(result.metrics["end_ts"])
        - pd.Timestamp(result.metrics["start_ts"])
    ).total_seconds() / 86_400.0
    return [
        {
            "market": market,
            "variant": variant,
            **row,
        }
        for row in engine.recent_slices(result)
        if span >= RECENT_DAYS[row["window"]]
    ]


def phase_audit_binance(
    engine: Any,
    books: dict[int, Any],
    features: dict[int, Any],
    long_config: Any,
    short_config: Any,
) -> list[dict[str, Any]]:
    common_start = max(book.ts[0] for book in books.values())
    common_end = min(book.terminal_ts for book in books.values())
    rows: list[dict[str, Any]] = []
    for variant, long_leg, short_leg in (
        ("combined", long_config, short_config),
        ("long_only", long_config, None),
        ("short_only", None, short_config),
    ):
        for phase, book in sorted(books.items()):
            timestamps = pd.DatetimeIndex([*book.ts, book.terminal_ts])
            start = int(book.ts.searchsorted(common_start, side="left"))
            end = int(timestamps.searchsorted(common_end, side="right") - 1)
            result = run_binance(
                engine,
                book,
                features[phase],
                long_leg,
                short_leg,
                start=start,
                end=end,
            )
            rows.append(
                {
                    "variant": variant,
                    "phase_hours": phase,
                    "common_start": common_start.isoformat(),
                    "common_end": common_end.isoformat(),
                    **result.metrics,
                }
            )
    return rows


def alignment_rows(
    binance_book: Any,
    nasdaq_book: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    binance = pd.DataFrame(
        {
            "session_date": pd.to_datetime(binance_book.ts.date),
            "binance_close": binance_book.close,
        }
    )
    nasdaq = pd.DataFrame(
        {
            "session_date": pd.to_datetime(
                pd.DatetimeIndex(nasdaq_book.ts)
                .tz_convert("America/New_York")
                .date
            ),
            "nasdaq_close": nasdaq_book.close,
        }
    )
    aligned = binance.merge(nasdaq, on="session_date", how="inner")
    aligned["binance_return"] = aligned["binance_close"].pct_change()
    aligned["nasdaq_return"] = aligned["nasdaq_close"].pct_change()
    returns = aligned.dropna()
    summary = {
        "rows": len(aligned),
        "first_session": aligned["session_date"].iloc[0].date().isoformat(),
        "last_session": aligned["session_date"].iloc[-1].date().isoformat(),
        "daily_return_corr": float(
            returns[["binance_return", "nasdaq_return"]].corr().iloc[0, 1]
        ),
        "binance_period_return_pct": float(
            (aligned["binance_close"].iloc[-1]
             / aligned["binance_close"].iloc[0] - 1.0) * 100.0
        ),
        "nasdaq_period_return_pct": float(
            (aligned["nasdaq_close"].iloc[-1]
             / aligned["nasdaq_close"].iloc[0] - 1.0) * 100.0
        ),
        "timestamp_caveat": (
            "Binance close is 23:45 UTC daily close; Nasdaq close is "
            "regular-session provider close. Same calendar date is compared."
        ),
    }
    rows = [
        {
            **row,
            "session_date": pd.Timestamp(row["session_date"])
            .date()
            .isoformat(),
        }
        for row in aligned.to_dict(orient="records")
    ]
    return rows, summary


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: clean_json(item)
            for key, item in value.items()
            if key != "_results"
        }
    if isinstance(value, (list, tuple)):
        return [clean_json(item) for item in value]
    if isinstance(value, np.generic):
        return clean_json(value.item())
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def main() -> None:
    args = parse_args()
    hype_helper = load_module(
        HYPE_HELPER_PATH,
        HYPE_HELPER_SHA256,
        "mu_1d_ma7_hype_helper",
    )
    mu_audit = load_module(
        MU_AUDIT_PATH,
        MU_AUDIT_SHA256,
        "mu_1d_ma7_data_audit",
    )
    sox = load_module(
        SOX_HELPER_PATH,
        SOX_HELPER_SHA256,
        "mu_1d_ma7_sox_helper",
    )
    engine_binance = hype_helper.load_module(
        hype_helper.ENGINE_PATH,
        hype_helper.ENGINE_SHA256,
        "mu_1d_ma7_binance_engine",
    )
    base = hype_helper.load_module(
        hype_helper.BASE_PATH,
        hype_helper.BASE_SHA256,
        "mu_1d_ma7_base",
    )
    engine_nasdaq = sox.load_engine()
    binance_long, binance_short = hype_helper.frozen_configs(engine_binance)
    nasdaq_long, nasdaq_short = sox.frozen_configs(engine_nasdaq)
    if args.self_test:
        sample = pd.DataFrame(
            {
                "ts": pd.date_range(
                    "2026-01-01T00:00:00Z",
                    periods=8,
                    freq="15min",
                ),
                "open": np.arange(1.0, 9.0),
                "high": np.arange(1.5, 9.5),
                "low": np.arange(0.5, 8.5),
                "close": np.arange(1.25, 9.25),
                "volume": np.ones(8),
                "quote_volume": np.arange(1.25, 9.25),
                "trade_count": np.ones(8, dtype=int),
                "is_closed": np.ones(8, dtype=bool),
            }
        )
        hourly, quality = aggregate_hourly(sample)
        assert len(hourly) == 2 and quality["blocker_count"] == 0
        assert binance_long.side == 1 and nasdaq_short.side == -1
        print("self-test: PASS")
        return

    bars_15m, binance_quality, funding, funding_quality = (
        load_binance_data(mu_audit)
    )
    hourly, hourly_quality = aggregate_hourly(bars_15m)
    parent = base.load_parent()
    books_binance = {
        phase: base.build_book(
            parent,
            hourly,
            {
                **hourly_quality,
                "source_dataset_quality": binance_quality,
            },
            funding,
            funding_quality,
            phase_hours=phase,
        )
        for phase in (0, 12)
    }
    for book in books_binance.values():
        book.quality.update(
            {
                "exchange": "Binance",
                "market": "USD-M TRADIFI_PERPETUAL",
                "symbol": "MUUSDT",
                "source_symbol": "MU/USDT:USDT",
            }
        )
    features_binance = {
        phase: engine_binance.build_features(book, hourly, funding)
        for phase, book in books_binance.items()
    }
    book_binance = books_binance[0]

    nasdaq_frame, nasdaq_quality = load_nasdaq_data(sox)
    book_nasdaq, features_nasdaq = sox.build_book_and_features(
        engine_nasdaq,
        nasdaq_frame,
        nasdaq_quality,
    )

    common_start = max(
        book_binance.ts[0].date(),
        pd.DatetimeIndex(book_nasdaq.ts)
        .tz_convert("America/New_York")[0]
        .date(),
    )
    common_end = min(
        book_binance.terminal_ts.date(),
        date.fromisoformat(book_nasdaq.quality["terminal_session"]),
    )
    binance_common_start = int(
        book_binance.ts.searchsorted(
            pd.Timestamp(common_start, tz="UTC"),
            side="left",
        )
    )
    binance_common_end = int(
        pd.DatetimeIndex([*book_binance.ts, book_binance.terminal_ts])
        .searchsorted(pd.Timestamp(common_end, tz="UTC"), side="left")
    )
    nasdaq_dates = np.asarray(
        pd.DatetimeIndex(book_nasdaq.ts)
        .tz_convert("America/New_York")
        .date
    )
    nasdaq_common_start = int(
        np.searchsorted(nasdaq_dates, common_start, side="left")
    )
    nasdaq_common_end = int(
        np.searchsorted(nasdaq_dates, common_end, side="left")
    )
    if common_end == date.fromisoformat(
        book_nasdaq.quality["terminal_session"]
    ):
        nasdaq_common_end = book_nasdaq.count

    binance_windows = {
        "full_available": (0, book_binance.count),
        "common_calendar_overlap": (
            binance_common_start,
            binance_common_end,
        ),
    }
    nasdaq_windows = {
        "full_available": (0, book_nasdaq.count),
        "common_calendar_overlap": (
            nasdaq_common_start,
            nasdaq_common_end,
        ),
    }
    payload: dict[str, Any] = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "MU-1D-MA7-Separated-Trend-Transfer",
        "source_version": "HYPE-1D-MA7-Asymmetric-Body-Trend-V1",
        "status": "explore / untrusted equity arm / not promoted / not live-ready",
        "common_calendar_overlap": {
            "start": common_start.isoformat(),
            "end_exclusive_terminal": common_end.isoformat(),
        },
        "contracts": {
            "binance": {
                "market": "Binance USD-M MUUSDT TRADIFI_PERPETUAL",
                "daily_boundary": "UTC 00:00",
                "cost": "fee 0.001/fill + adverse slippage 4 bps/fill",
                "funding": "actual event-time Binance funding",
                "long_config": asdict(binance_long),
                "short_config": asdict(binance_short),
            },
            "nasdaq": {
                "market": "Nasdaq MU equity; Yahoo Finance raw source",
                "daily_boundary": "US regular-session provider daily bar",
                "cost": (
                    "primary zero cost because commission/slippage/borrow/"
                    "financing are unspecified; illustrative 10 bps/fill"
                ),
                "funding": "none; stock borrow/dividend/financing unspecified",
                "long_config": asdict(nasdaq_long),
                "short_config": asdict(nasdaq_short),
            },
        },
        "data_quality": {
            "binance": {
                "ohlcv_15m": binance_quality,
                "hourly": hourly_quality,
                "funding": funding_quality,
                "daily": book_binance.quality,
            },
            "nasdaq": nasdaq_quality,
        },
        "markets": {"binance": {"windows": {}}, "nasdaq": {"windows": {}}},
    }
    metric_rows: list[dict[str, Any]] = []
    recent: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    paths: dict[str, list[dict[str, Any]]] = {}

    for window, (start, end) in binance_windows.items():
        audit = audit_binance_window(
            engine_binance,
            sox,
            book_binance,
            features_binance[0],
            binance_long,
            binance_short,
            start=start,
            end=end,
        )
        payload["markets"]["binance"]["windows"][window] = audit
        for variant, metrics in audit.items():
            if variant != "_results" and isinstance(metrics, dict):
                metric_rows.append(
                    {
                        "market": "binance",
                        "window": window,
                        "variant": variant,
                        **metrics,
                    }
                )
        if window == "full_available":
            for variant in ("combined", "long_only", "short_only"):
                result = audit["_results"][variant]
                recent.extend(
                    recent_rows(engine_binance, "binance", variant, result)
                )
                trades.extend(
                    {
                        "market": "binance",
                        "variant": variant,
                        **trade,
                    }
                    for trade in result.trades
                )
            paths["binance"] = audit["_results"]["combined"].path

    for window, (start, end) in nasdaq_windows.items():
        audit = sox.audit_window(
            engine_nasdaq,
            book_nasdaq,
            features_nasdaq,
            nasdaq_long,
            nasdaq_short,
            start=start,
            end=end,
        )
        payload["markets"]["nasdaq"]["windows"][window] = audit
        for variant, metrics in audit.items():
            if variant != "_results" and isinstance(metrics, dict):
                metric_rows.append(
                    {
                        "market": "nasdaq",
                        "window": window,
                        "variant": variant,
                        **metrics,
                    }
                )
        if window == "full_available":
            for variant in ("combined", "long_only", "short_only"):
                result = audit["_results"][variant]
                recent.extend(
                    recent_rows(engine_nasdaq, "nasdaq", variant, result)
                )
                trades.extend(
                    {
                        "market": "nasdaq",
                        "variant": variant,
                        **trade,
                    }
                    for trade in result.trades
                )
            paths["nasdaq"] = audit["_results"]["combined"].path

    phase_rows = phase_audit_binance(
        engine_binance,
        books_binance,
        features_binance,
        binance_long,
        binance_short,
    )
    payload["markets"]["binance"]["phase_audit"] = phase_rows

    def binance_rolling_run(
        book: Any,
        features: Any,
        long_leg: Any,
        short_leg: Any,
        start: int,
        end: int,
    ) -> Any:
        return run_binance(
            engine_binance,
            book,
            features,
            long_leg,
            short_leg,
            start=start,
            end=end,
        )

    def nasdaq_rolling_run(
        book: Any,
        features: Any,
        long_leg: Any,
        short_leg: Any,
        start: int,
        end: int,
    ) -> Any:
        return sox.run_variant(
            engine_nasdaq,
            book,
            features,
            long_leg,
            short_leg,
            start=start,
            end=end,
        )

    rolling_rows = [
        *rolling_90d(
            "binance",
            binance_rolling_run,
            book_binance,
            features_binance[0],
            binance_long,
            binance_short,
        ),
        *rolling_90d(
            "nasdaq",
            nasdaq_rolling_run,
            book_nasdaq,
            features_nasdaq,
            nasdaq_long,
            nasdaq_short,
        ),
    ]
    payload["rolling_90d"] = {
        market: {
            variant: {
                "count": len(selected),
                "positive": sum(
                    row["net_return_pct"] > 0.0 for row in selected
                ),
                "median_return_pct": float(
                    np.median([
                        row["net_return_pct"] for row in selected
                    ])
                ),
                "min_return_pct": min(
                    row["net_return_pct"] for row in selected
                ),
            }
            for variant in ("combined", "long_only", "short_only")
            for selected in [[
                row
                for row in rolling_rows
                if row["market"] == market
                and row["variant"] == variant
            ]]
            if selected
        }
        for market in ("binance", "nasdaq")
    }
    aligned_rows, alignment_summary = alignment_rows(
        book_binance,
        book_nasdaq,
    )
    payload["daily_alignment"] = alignment_summary

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = "mu_1d_ma7_dual_market_transfer"
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
    pd.DataFrame(recent).to_csv(
        ARTIFACT_DIR / f"{stem}_recent_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(phase_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_phase_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(rolling_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_rolling_90d_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(trades).to_csv(
        ARTIFACT_DIR / f"{stem}_trades_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(aligned_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_daily_alignment_{args.run_date}.csv",
        index=False,
    )
    for market, path in paths.items():
        pd.DataFrame(path).to_csv(
            ARTIFACT_DIR / f"{stem}_{market}_path_{args.run_date}.csv",
            index=False,
        )
    print(
        json.dumps(
            {
                "markets": clean_payload["markets"],
                "daily_alignment": clean_payload["daily_alignment"],
                "rolling_90d": clean_payload["rolling_90d"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
