from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
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
FAMILY_DIR = (
    ROOT / "research/asset-portfolios/1d-ma7-separated-trend-transfer"
)
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
ENGINE_PATH = (
    ROOT
    / "research/hype/1d-ma7-asymmetric-body-trend/scripts"
    / "search_hype_1d_ma7_separated_trend.py"
)
ENGINE_SHA256 = (
    "c376f8bd1bae814b0ba53687380ee1060cf3cc3095ae815ebb0311ed1aef59e1"
)
COMMON_START = pd.Timestamp("2025-05-31T00:00:00Z")
ASSETS = {
    "BTCUSDT": "btc_usdt_usdt",
    "ETHUSDT": "eth_usdt_usdt",
}
NORMALIZED_ROOT = (
    ROOT
    / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=1h"
)
RAW_ROOT = (
    ROOT
    / "data/raw/ohlcv/exchange=binance/market_type=perp/timeframe=1h"
)
FUNDING_ROOT = (
    ROOT / "data/normalized/funding/exchange=binance/market_type=perp"
)


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
    funding_quality: dict[str, Any]

    @property
    def count(self) -> int:
        return len(self.open)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Zero-tuning BTC/ETH transfer of the frozen HYPE 1D MA7 "
            "separated-trend observation."
        )
    )
    parser.add_argument(
        "--run-date",
        default=datetime.now(UTC).date().isoformat(),
    )
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def load_engine() -> Any:
    digest = hashlib.sha256(ENGINE_PATH.read_bytes()).hexdigest()
    if digest != ENGINE_SHA256:
        raise RuntimeError(
            f"source engine drift: expected {ENGINE_SHA256}, got {digest}"
        )
    spec = importlib.util.spec_from_file_location(
        "hype_ma7_separated_transfer_engine",
        ENGINE_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {ENGINE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
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


def _partition_paths(root: Path, slug: str) -> list[Path]:
    paths = sorted(root.glob(f"date=*/symbol={slug}.parquet"))
    if not paths:
        raise FileNotFoundError(f"no partitions for {slug} under {root}")
    return paths


def _load_partitions(paths: list[Path]) -> pd.DataFrame:
    return pd.concat(
        [pd.read_parquet(path) for path in paths],
        ignore_index=True,
    )


def load_and_audit(
    symbol: str,
    slug: str,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    normalized_paths = _partition_paths(NORMALIZED_ROOT, slug)
    raw_paths = _partition_paths(RAW_ROOT, slug)
    normalized = _load_partitions(normalized_paths)
    raw = _load_partitions(raw_paths)
    normalized["ts"] = pd.to_datetime(normalized["ts"], utc=True)
    raw["open_time"] = pd.to_datetime(raw["open_time"], utc=True)
    normalized = normalized.sort_values("ts").reset_index(drop=True)
    raw = raw.sort_values("open_time").reset_index(drop=True)
    funding_path = FUNDING_ROOT / f"symbol={slug}/funding.parquet"
    funding = pd.read_parquet(funding_path)
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
    funding["funding_rate"] = pd.to_numeric(
        funding["funding_rate"],
        errors="coerce",
    )
    funding = funding.sort_values("ts").reset_index(drop=True)
    accepted_start = funding["ts"].iloc[0].ceil("D")
    normalized = normalized.loc[
        normalized["ts"].ge(accepted_start)
    ].reset_index(drop=True)
    raw = raw.loc[raw["open_time"].ge(accepted_start)].reset_index(drop=True)
    required = [
        "ts",
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
    missing_columns = sorted(set(required).difference(normalized.columns))
    expected = pd.date_range(
        normalized["ts"].iloc[0],
        normalized["ts"].iloc[-1],
        freq="1h",
    )
    missing_timestamps = expected.difference(
        pd.DatetimeIndex(normalized["ts"])
    )
    critical_nulls = {
        column: int(normalized[column].isna().sum())
        for column in required
        if column in normalized
    }
    invalid_ohlc = int(
        (
            (normalized[["open", "high", "low", "close"]] <= 0.0).any(axis=1)
            | normalized["high"].lt(
                normalized[["open", "close", "low"]].max(axis=1)
            )
            | normalized["low"].gt(
                normalized[["open", "close", "high"]].min(axis=1)
            )
        ).sum()
    )
    compare = normalized[
        [
            "ts",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "quote_volume",
            "trade_count",
        ]
    ].merge(
        raw[
            [
                "open_time",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "quote_volume",
                "trade_count",
            ]
        ],
        left_on="ts",
        right_on="open_time",
        how="outer",
        suffixes=("_normalized", "_raw"),
        indicator=True,
    )
    both = compare.loc[compare["_merge"].eq("both")]
    mismatch: dict[str, int] = {}
    for column in (
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
    ):
        left = pd.to_numeric(
            both[f"{column}_normalized"],
            errors="coerce",
        ).to_numpy("float64")
        right = pd.to_numeric(
            both[f"{column}_raw"],
            errors="coerce",
        ).to_numpy("float64")
        mismatch[column] = int(
            (
                ~np.isclose(
                    left,
                    right,
                    rtol=0.0,
                    atol=0.0 if column == "trade_count" else 1e-12,
                )
            ).sum()
        )
    expected_vwap = normalized["quote_volume"].div(
        normalized["volume"].replace(0.0, np.nan)
    )
    vwap_formula_mismatch = int(
        (
            ~np.isclose(
                normalized["vwap"].to_numpy("float64"),
                expected_vwap.to_numpy("float64"),
                rtol=1e-12,
                atol=1e-12,
                equal_nan=True,
            )
        ).sum()
    )
    market_blockers = (
        len(missing_columns)
        + len(missing_timestamps)
        + int(normalized["ts"].duplicated().sum())
        + int(raw["open_time"].duplicated().sum())
        + sum(critical_nulls.values())
        + invalid_ohlc
        + int((~normalized["is_closed"].astype(bool)).sum())
        + int(compare["_merge"].ne("both").sum())
        + sum(mismatch.values())
        + vwap_formula_mismatch
    )

    funding_gaps = funding["ts"].diff().dropna()
    funding_quality = {
        "rows": int(len(funding)),
        "first_ts": funding["ts"].iloc[0].isoformat(),
        "last_ts": funding["ts"].iloc[-1].isoformat(),
        "duplicate_ts": int(funding["ts"].duplicated().sum()),
        "critical_null_rows": int(
            funding[["ts", "funding_rate"]].isna().any(axis=1).sum()
        ),
        "max_gap_hours": float(
            funding_gaps.max().total_seconds() / 3600.0
        ),
    }
    funding_quality["blocker_count"] = int(
        funding_quality["duplicate_ts"]
        + funding_quality["critical_null_rows"]
        + (funding_quality["max_gap_hours"] > 8.01)
    )
    quality = {
        "symbol": symbol,
        "exchange": "Binance",
        "market": "USD-M perpetual",
        "timeframe": "1h -> UTC 1d",
        "rows": int(len(normalized)),
        "accepted_start_reason": (
            "first full UTC day after normalized funding coverage begins"
        ),
        "first_ts": normalized["ts"].iloc[0].isoformat(),
        "last_ts": normalized["ts"].iloc[-1].isoformat(),
        "expected_rows": int(len(expected)),
        "missing_bars": int(len(missing_timestamps)),
        "duplicate_normalized": int(normalized["ts"].duplicated().sum()),
        "duplicate_raw": int(raw["open_time"].duplicated().sum()),
        "critical_nulls": critical_nulls,
        "invalid_ohlc_rows": invalid_ohlc,
        "non_closed_rows": int(
            (~normalized["is_closed"].astype(bool)).sum()
        ),
        "raw_normalized_unmatched_rows": int(
            compare["_merge"].ne("both").sum()
        ),
        "raw_normalized_mismatch": mismatch,
        "vwap_formula": "quote_volume / volume",
        "vwap_formula_mismatch": vwap_formula_mismatch,
        "source_values": sorted(
            normalized["source"].dropna().astype(str).unique().tolist()
        ),
        "blocker_count": int(
            market_blockers + funding_quality["blocker_count"]
        ),
        "funding": funding_quality,
    }
    if quality["blocker_count"]:
        raise RuntimeError(f"{symbol} data-quality blockers: {quality}")
    return normalized, funding[["ts", "funding_rate"]].copy(), quality


def aggregate_daily(
    hourly: pd.DataFrame,
    *,
    phase_hours: int,
) -> pd.DataFrame:
    frame = hourly[
        ["ts", "open", "high", "low", "close"]
    ].copy()
    frame["shifted_ts"] = frame["ts"] - pd.Timedelta(hours=phase_hours)
    frame["day"] = frame["shifted_ts"].dt.floor("D")
    rows: list[dict[str, Any]] = []
    for day, group in frame.groupby("day", sort=True):
        group = group.sort_values("ts")
        if len(group) != 24:
            continue
        expected = pd.date_range(
            pd.Timestamp(day) + pd.Timedelta(hours=phase_hours),
            periods=24,
            freq="1h",
        )
        if not pd.DatetimeIndex(group["ts"]).equals(expected):
            continue
        rows.append(
            {
                "ts": expected[0],
                "open": float(group["open"].iloc[0]),
                "high": float(group["high"].max()),
                "low": float(group["low"].min()),
                "close": float(group["close"].iloc[-1]),
            }
        )
    daily = pd.DataFrame(rows)
    if daily.empty:
        raise RuntimeError(f"phase {phase_hours}: no complete daily bars")
    daily["ts"] = pd.to_datetime(daily["ts"], utc=True)
    return daily


def build_book(
    symbol: str,
    hourly: pd.DataFrame,
    quality: dict[str, Any],
    *,
    phase_hours: int,
) -> Book:
    daily = aggregate_daily(hourly, phase_hours=phase_hours)
    hourly_indexed = hourly.set_index("ts").sort_index()
    terminal_ts = pd.Timestamp(daily["ts"].iloc[-1]) + pd.Timedelta(days=1)
    if terminal_ts not in hourly_indexed.index:
        raise RuntimeError(
            f"{symbol} phase {phase_hours}: terminal open missing at {terminal_ts}"
        )
    short_entry_open: list[float] = []
    post_high: list[float] = []
    post_low: list[float] = []
    for day_start in pd.DatetimeIndex(daily["ts"]):
        entry_ts = day_start + pd.Timedelta(hours=1)
        day_end = day_start + pd.Timedelta(days=1)
        part = hourly_indexed.loc[
            (hourly_indexed.index >= entry_ts)
            & (hourly_indexed.index < day_end)
        ]
        if len(part) != 23:
            raise RuntimeError(
                f"{symbol} phase {phase_hours}: expected 23 post-entry bars "
                f"at {day_start}, got {len(part)}"
            )
        short_entry_open.append(float(part.loc[entry_ts, "open"]))
        post_high.append(float(part["high"].max()))
        post_low.append(float(part["low"].min()))
    book_quality = {
        **quality,
        "phase_hours": phase_hours,
        "daily_rows": int(len(daily)),
        "daily_first_ts": daily["ts"].iloc[0].isoformat(),
        "daily_last_ts": daily["ts"].iloc[-1].isoformat(),
        "terminal_open_ts": terminal_ts.isoformat(),
        "terminal_open": float(hourly_indexed.loc[terminal_ts, "open"]),
    }
    return Book(
        ts=pd.DatetimeIndex(daily["ts"]),
        terminal_ts=terminal_ts,
        open=daily["open"].to_numpy("float64"),
        short_entry_open=np.asarray(short_entry_open, dtype=float),
        post_short_entry_high=np.asarray(post_high, dtype=float),
        post_short_entry_low=np.asarray(post_low, dtype=float),
        high=daily["high"].to_numpy("float64"),
        low=daily["low"].to_numpy("float64"),
        close=daily["close"].to_numpy("float64"),
        quality=book_quality,
        funding_quality=quality["funding"],
    )


def run_variant(
    engine: Any,
    book: Book,
    features: Any,
    long_config: Any | None,
    short_config: Any | None,
    *,
    start: int,
    end: int,
    retain: bool = False,
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
        retain=retain,
        **kwargs,
    )


def window_audit(
    engine: Any,
    book: Book,
    features: Any,
    long_config: Any,
    short_config: Any,
    *,
    start: int,
    end: int,
    retain: bool,
) -> dict[str, Any]:
    base = run_variant(
        engine,
        book,
        features,
        long_config,
        short_config,
        start=start,
        end=end,
        retain=retain,
    )
    stress = run_variant(
        engine,
        book,
        features,
        long_config,
        short_config,
        start=start,
        end=end,
        slippage=engine.STRESS_SLIPPAGE,
    )
    delayed = run_variant(
        engine,
        book,
        features,
        long_config,
        short_config,
        start=start,
        end=end,
        signal_lag=1,
    )
    long_only = run_variant(
        engine,
        book,
        features,
        long_config,
        None,
        start=start,
        end=end,
        retain=retain,
    )
    short_only = run_variant(
        engine,
        book,
        features,
        None,
        short_config,
        start=start,
        end=end,
        retain=retain,
    )
    long_stress = run_variant(
        engine,
        book,
        features,
        long_config,
        None,
        start=start,
        end=end,
        slippage=engine.STRESS_SLIPPAGE,
    )
    long_delayed = run_variant(
        engine,
        book,
        features,
        long_config,
        None,
        start=start,
        end=end,
        signal_lag=1,
    )
    short_stress = run_variant(
        engine,
        book,
        features,
        None,
        short_config,
        start=start,
        end=end,
        slippage=engine.STRESS_SLIPPAGE,
    )
    short_delayed = run_variant(
        engine,
        book,
        features,
        None,
        short_config,
        start=start,
        end=end,
        signal_lag=1,
    )
    benchmark = engine.buy_and_hold(
        _window_book(book, start, end),
        _window_features(features, start, end),
    )
    return {
        "base": base.metrics,
        "stress_8bps": stress.metrics,
        "one_day_extra_delay": delayed.metrics,
        "long_only": long_only.metrics,
        "long_only_stress_8bps": long_stress.metrics,
        "long_only_one_day_extra_delay": long_delayed.metrics,
        "short_only": short_only.metrics,
        "short_only_stress_8bps": short_stress.metrics,
        "short_only_one_day_extra_delay": short_delayed.metrics,
        "buy_and_hold": benchmark,
        "excess_return_pct": (
            base.metrics["net_return_pct"] - benchmark["net_return_pct"]
        ),
        "recent_slices": {
            "combined": engine.recent_slices(base) if retain else [],
            "long_only": (
                engine.recent_slices(long_only) if retain else []
            ),
            "short_only": (
                engine.recent_slices(short_only) if retain else []
            ),
        },
        "_result": base,
    }


def _window_book(book: Book, start: int, end: int) -> Book:
    terminal_ts = (
        book.terminal_ts if end == book.count else pd.Timestamp(book.ts[end])
    )
    terminal_open = (
        float(book.quality["terminal_open"])
        if end == book.count
        else float(book.open[end])
    )
    return Book(
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
        funding_quality=book.funding_quality,
    )


def _window_features(features: Any, start: int, end: int) -> Any:
    feature_type = type(features)
    return feature_type(
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


def rolling_rows(
    engine: Any,
    symbol: str,
    book: Book,
    features: Any,
    long_config: Any,
    short_config: Any,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    while start + 180 <= book.count:
        end = start + 180
        window_index = start // 60
        for variant, long_leg, short_leg in (
            ("combined", long_config, short_config),
            ("long_only", long_config, None),
            ("short_only", None, short_config),
        ):
            result = run_variant(
                engine,
                book,
                features,
                long_leg,
                short_leg,
                start=start,
                end=end,
            )
            rows.append(
                {
                    "symbol": symbol,
                    "variant": variant,
                    "window_index": window_index,
                    **result.metrics,
                }
            )
        start += 60
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
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def main() -> None:
    args = parse_args()
    engine = load_engine()
    if args.self_test:
        long_config, short_config = frozen_configs(engine)
        assert long_config.side == 1
        assert short_config.side == -1
        assert short_config.entry_mode == "reclaim"
        print("self-test: PASS")
        return

    long_config, short_config = frozen_configs(engine)
    payload: dict[str, Any] = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "Binance-1D-MA7-Separated-Trend-Transfer",
        "status": "explore / not promoted / not live-ready",
        "selection": (
            "zero target-asset tuning; exact transfer of HYPE post-reveal "
            "observation 041"
        ),
        "source_engine": {
            "path": str(ENGINE_PATH.relative_to(ROOT)),
            "sha256": ENGINE_SHA256,
        },
        "long_config": asdict(long_config),
        "short_config": asdict(short_config),
        "costs": {
            "fee_per_fill": engine.FEE,
            "base_slippage_per_fill": engine.BASE_SLIPPAGE,
            "stress_slippage_per_fill": engine.STRESS_SLIPPAGE,
            "funding": (
                "actual Binance event timestamps/rates; event-hour open "
                "notional approximation; charged only while held"
            ),
        },
        "assets": {},
    }
    metric_rows: list[dict[str, Any]] = []
    recent_rows: list[dict[str, Any]] = []
    phase_rows: list[dict[str, Any]] = []
    rolling: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    path_rows: list[dict[str, Any]] = []

    for symbol, slug in ASSETS.items():
        hourly, funding, quality = load_and_audit(symbol, slug)
        books = {
            phase: build_book(
                symbol,
                hourly,
                quality,
                phase_hours=phase,
            )
            for phase in (0, 12)
        }
        features = {
            phase: engine.build_features(book, hourly, funding)
            for phase, book in books.items()
        }
        book = books[0]
        common_start = int(book.ts.searchsorted(COMMON_START, side="left"))
        if (
            common_start >= book.count
            or pd.Timestamp(book.ts[common_start]) != COMMON_START
        ):
            raise RuntimeError(f"{symbol}: common start unavailable")
        windows = {
            "full_available": (0, book.count),
            "hype_common_425d": (common_start, book.count),
        }
        asset_payload: dict[str, Any] = {
            "data_quality": quality,
            "windows": {},
            "phase_audit": [],
        }
        for label, (start, end) in windows.items():
            audit = window_audit(
                engine,
                book,
                features[0],
                long_config,
                short_config,
                start=start,
                end=end,
                retain=True,
            )
            result = audit.pop("_result")
            asset_payload["windows"][label] = audit
            for variant in (
                "base",
                "stress_8bps",
                "one_day_extra_delay",
                "long_only",
                "long_only_stress_8bps",
                "long_only_one_day_extra_delay",
                "short_only",
                "short_only_stress_8bps",
                "short_only_one_day_extra_delay",
            ):
                metric_rows.append(
                    {
                        "symbol": symbol,
                        "window": label,
                        "variant": variant,
                        **audit[variant],
                    }
                )
            metric_rows.append(
                {
                    "symbol": symbol,
                    "window": label,
                    "variant": "buy_and_hold",
                    **audit["buy_and_hold"],
                }
            )
            if label == "full_available":
                recent_rows.extend(
                    {
                        "symbol": symbol,
                        "variant": variant,
                        **row,
                    }
                    for variant, rows in audit["recent_slices"].items()
                    for row in rows
                )
                trade_rows.extend(
                    {"symbol": symbol, **row} for row in result.trades
                )
                path_rows.extend(
                    {"symbol": symbol, **row} for row in result.path
                )

        common_phase_start = max(
            phase_book.ts[0] for phase_book in books.values()
        )
        common_phase_end = min(
            phase_book.terminal_ts for phase_book in books.values()
        )
        for phase, phase_book in books.items():
            start = int(
                phase_book.ts.searchsorted(common_phase_start, side="left")
            )
            timestamps = pd.DatetimeIndex(
                [*phase_book.ts, phase_book.terminal_ts]
            )
            end = int(
                timestamps.searchsorted(common_phase_end, side="right") - 1
            )
            for variant, long_leg, short_leg in (
                ("combined", long_config, short_config),
                ("long_only", long_config, None),
                ("short_only", None, short_config),
            ):
                result = run_variant(
                    engine,
                    phase_book,
                    features[phase],
                    long_leg,
                    short_leg,
                    start=start,
                    end=end,
                )
                row = {
                    "symbol": symbol,
                    "variant": variant,
                    "phase_hours": phase,
                    "common_start": common_phase_start.isoformat(),
                    "common_end": common_phase_end.isoformat(),
                    **result.metrics,
                }
                phase_rows.append(row)
                asset_payload["phase_audit"].append(row)
        rolling.extend(
            rolling_rows(
                engine,
                symbol,
                book,
                features[0],
                long_config,
                short_config,
            )
        )
        payload["assets"][symbol] = asset_payload

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = "binance_1d_ma7_separated_trend_transfer"
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
    pd.DataFrame(recent_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_recent_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(phase_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_phase_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(rolling).to_csv(
        ARTIFACT_DIR / f"{stem}_rolling_180d_{args.run_date}.csv",
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
    print(
        json.dumps(
            {
                "summary": str(
                    (
                        ARTIFACT_DIR
                        / f"{stem}_summary_{args.run_date}.json"
                    ).relative_to(ROOT)
                ),
                "assets": {
                    symbol: {
                        label: {
                            "return_pct": window["base"][
                                "net_return_pct"
                            ],
                            "mdd_pct": window["base"][
                                "max_drawdown_pct"
                            ],
                            "trades": window["base"]["closed_trades"],
                            "buy_hold_pct": window["buy_and_hold"][
                                "net_return_pct"
                            ],
                        }
                        for label, window in asset["windows"].items()
                    }
                    for symbol, asset in clean_payload["assets"].items()
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
