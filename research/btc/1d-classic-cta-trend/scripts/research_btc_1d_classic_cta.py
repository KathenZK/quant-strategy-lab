"""BTC-1D-Classic-CTA-Trend literature baseline.

Frozen before the run in
specs/btc-1d-ccta-literature-baseline-2026-08-17.md.
No BTC-specific search of EMA pairs, scalars, vol target, or buffer.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/btc/1d-classic-cta-trend"
ENGINE_PATH = (
    ROOT / "research/_shared-kernels/multi-horizon-ema-forecast/v1/engine.py"
)
ENGINE_SHA256 = "63d754088ac55b958b5a5536d4ae8f5049d6b6c9c48a0fca7dc89c770d6e31c4"
FAMILY_NAME = "BTC-1D-Classic-CTA-Trend"
FAMILY_ALIAS = "BTC-1D-CCTA"
TIMEFRAME = "1d"
SYMBOL = "BTCUSDT"
DISPLAY_SYMBOL = "BTC/USDT:USDT"
SYMBOL_SLUG = "btc_usdt_usdt"

NORMALIZED_1D = (
    ROOT
    / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=1d"
)
RAW_1D = (
    ROOT
    / "data/raw/ohlcv/exchange=binance/market_type=perp/timeframe=1d"
    / "source=binance_futures_kline_api_direct"
)
FUNDING_ROOT = (
    ROOT / "data/normalized/funding_rates/exchange=binance/market_type=perp"
)

EMA_PAIRS = ((8, 32), (16, 64), (32, 128), (64, 256))
EMA_WEIGHTS = (0.25, 0.25, 0.25, 0.25)
EWMAC_SCALARS = {
    (8, 32): 5.3,
    (16, 64): 3.75,
    (32, 128): 2.65,
    (64, 256): 1.87,
}
DAILY_VOL_SPAN = 35
STANDARD_FORECAST_CAP = 20.0
TARGET_VOL = 0.20
WEIGHT_CAP = 2.0
BUFFER_FRACTION = 0.10
ANNUALIZER = 365


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=f"Run {FAMILY_NAME} literature baseline."
    )
    parser.add_argument(
        "--run-date",
        default=datetime.now(UTC).date().isoformat(),
        help="Date embedded in report and artifact filenames.",
    )
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def load_engine() -> object:
    digest = hashlib.sha256(ENGINE_PATH.read_bytes()).hexdigest()
    if digest != ENGINE_SHA256:
        raise RuntimeError(
            f"shared kernel SHA mismatch: expected {ENGINE_SHA256}, got {digest}"
        )
    spec = importlib.util.spec_from_file_location(
        "multi_horizon_ema_forecast_v1_btc_1d_cta",
        ENGINE_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import shared kernel: {ENGINE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    original_periods_per_year = module.periods_per_year

    def periods_per_year(timeframe: str) -> int:
        if timeframe == TIMEFRAME:
            return ANNUALIZER
        return original_periods_per_year(timeframe)

    module.periods_per_year = periods_per_year
    return module


def _read_parquet_glob(pattern: str) -> pd.DataFrame:
    con = duckdb.connect()
    con.execute("SET TimeZone='UTC'")
    frame = con.execute(
        f"SELECT * FROM read_parquet('{pattern}', union_by_name=true)"
    ).fetch_df()
    con.close()
    return frame


def load_and_audit_daily() -> tuple[pd.DataFrame, dict[str, Any]]:
    normalized = _read_parquet_glob(
        str(NORMALIZED_1D / f"date=*/symbol={SYMBOL_SLUG}.parquet")
    )
    raw = _read_parquet_glob(
        str(RAW_1D / f"date=*/symbol={SYMBOL_SLUG}.parquet")
    )
    if normalized.empty or raw.empty:
        raise FileNotFoundError("BTC native 1d partitions missing")

    normalized["ts"] = pd.to_datetime(normalized["ts"], utc=True)
    raw["open_time"] = pd.to_datetime(raw["open_time"], utc=True)
    normalized = (
        normalized.sort_values("ts").drop_duplicates("ts", keep="last").reset_index(drop=True)
    )
    raw = (
        raw.sort_values("open_time")
        .drop_duplicates("open_time", keep="last")
        .reset_index(drop=True)
    )

    required = [
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
    missing_columns = sorted(set(required).difference(normalized.columns))
    expected = pd.date_range(
        normalized["ts"].iloc[0], normalized["ts"].iloc[-1], freq="1D", tz="UTC"
    )
    missing = expected.difference(pd.DatetimeIndex(normalized["ts"]))
    critical_nulls = {
        column: int(normalized[column].isna().sum()) for column in required if column in normalized
    }
    invalid_ohlc = int(
        (
            (normalized[["open", "high", "low", "close"]] <= 0.0).any(axis=1)
            | normalized["high"].lt(normalized[["open", "close", "low"]].max(axis=1))
            | normalized["low"].gt(normalized[["open", "close", "high"]].min(axis=1))
        ).sum()
    )
    compare = normalized[
        ["ts", "open", "high", "low", "close", "volume", "quote_volume", "trade_count"]
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
        left = pd.to_numeric(both[f"{column}_normalized"], errors="coerce").to_numpy("float64")
        right = pd.to_numeric(both[f"{column}_raw"], errors="coerce").to_numpy("float64")
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
    source_values = sorted(str(value) for value in normalized["source"].dropna().unique())
    unknown_source = int(
        not source_values or any(value in {"", "unknown", "nan"} for value in source_values)
    )
    closed_violations = int((~normalized["is_closed"].astype(bool)).sum())
    timeframe_mismatch = int((normalized["timeframe"].astype(str) != TIMEFRAME).sum())
    symbol_mismatch = int((normalized["symbol"].astype(str) != DISPLAY_SYMBOL).sum())
    blocker_count = (
        len(missing_columns)
        + len(missing)
        + int(normalized["ts"].duplicated().sum())
        + int(raw["open_time"].duplicated().sum())
        + sum(critical_nulls.values())
        + invalid_ohlc
        + closed_violations
        + unknown_source
        + timeframe_mismatch
        + symbol_mismatch
        + int(compare["_merge"].ne("both").sum())
        + sum(mismatch.values())
    )
    quality = {
        "exchange": "binance",
        "market_type": "perp",
        "symbol": DISPLAY_SYMBOL,
        "timeframe": TIMEFRAME,
        "source_values": source_values,
        "rows": int(len(normalized)),
        "first_ts": normalized["ts"].iloc[0].isoformat(),
        "last_ts": normalized["ts"].iloc[-1].isoformat(),
        "expected_rows": int(len(expected)),
        "missing_bars": int(len(missing)),
        "duplicate_normalized": int(normalized["ts"].duplicated().sum()),
        "duplicate_raw": int(raw["open_time"].duplicated().sum()),
        "critical_nulls": critical_nulls,
        "invalid_ohlc_rows": invalid_ohlc,
        "non_closed_rows": closed_violations,
        "timeframe_mismatch_rows": timeframe_mismatch,
        "symbol_mismatch_rows": symbol_mismatch,
        "raw_normalized_unmatched_rows": int(compare["_merge"].ne("both").sum()),
        "raw_normalized_mismatch": mismatch,
        "missing_columns": missing_columns,
        "blocker_count": int(blocker_count),
    }
    if blocker_count:
        raise RuntimeError(f"BTC 1d data-quality blockers: {quality}")
    keep = [
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
    return normalized[keep].copy(), quality


def load_and_audit_funding() -> tuple[pd.DataFrame, dict[str, Any]]:
    funding = _read_parquet_glob(
        str(FUNDING_ROOT / f"date=*/symbol={SYMBOL_SLUG}.parquet")
    )
    if funding.empty:
        raise FileNotFoundError(f"no BTC funding_rates partitions under {FUNDING_ROOT}")
    required = {"ts", "funding_rate"}
    missing_columns = sorted(required.difference(funding.columns))
    if missing_columns:
        raise RuntimeError(f"funding data missing columns: {missing_columns}")
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
    funding["funding_rate"] = pd.to_numeric(funding["funding_rate"], errors="coerce")
    funding = (
        funding.sort_values("ts").drop_duplicates("ts", keep="last").reset_index(drop=True)
    )
    duplicate = int(funding["ts"].duplicated().sum())
    nulls = int(funding[["ts", "funding_rate"]].isna().any(axis=1).sum())
    gaps = funding["ts"].diff().dropna()
    max_gap_hours = float(gaps.max().total_seconds() / 3600.0) if len(gaps) else None
    source_values = (
        sorted(str(value) for value in funding["source"].dropna().unique())
        if "source" in funding.columns
        else []
    )
    blocker_count = (
        duplicate
        + nulls
        + int(max_gap_hours is not None and max_gap_hours > 8.01)
        + int(not source_values or any(value in {"", "unknown", "nan"} for value in source_values))
    )
    quality = {
        "rows": int(len(funding)),
        "first_ts": funding["ts"].iloc[0].isoformat(),
        "last_ts": funding["ts"].iloc[-1].isoformat(),
        "duplicate_ts": duplicate,
        "critical_null_rows": nulls,
        "max_gap_hours": max_gap_hours,
        "source_values": source_values,
        "blocker_count": int(blocker_count),
    }
    if blocker_count:
        raise RuntimeError(f"BTC funding data-quality blockers: {quality}")
    return funding[["ts", "funding_rate"]].copy(), quality


def as_utc(value: object) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


def align_to_funding_coverage(
    daily: pd.DataFrame,
    funding: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    first_complete = as_utc(funding["ts"].iloc[0]).ceil("D")
    last_event = as_utc(funding["ts"].iloc[-1])
    last_complete = last_event.floor("D")
    aligned = daily.loc[
        daily["ts"].ge(first_complete) & daily["ts"].le(last_complete)
    ].reset_index(drop=True)
    if aligned.empty:
        raise RuntimeError("no daily bars remain after funding-coverage alignment")
    info = {
        "first_complete_utc_day": first_complete.isoformat(),
        "last_complete_utc_day": last_complete.isoformat(),
        "aligned_rows": int(len(aligned)),
        "dropped_leading_or_trailing": int(len(daily) - len(aligned)),
        "reason": (
            "keep UTC days whose open-to-open holding interval can be charged "
            "from the 8h funding_rates event tape"
        ),
    }
    return aligned, info


def build_classic_cta_features(daily: pd.DataFrame, engine: object) -> pd.DataFrame:
    frame = daily.copy().sort_values("ts").reset_index(drop=True)
    close = pd.to_numeric(frame["close"], errors="coerce")
    price_vol = (
        close.diff()
        .ewm(span=DAILY_VOL_SPAN, adjust=False, min_periods=DAILY_VOL_SPAN)
        .std(bias=False)
    )
    return_vol = (
        close.pct_change()
        .ewm(span=DAILY_VOL_SPAN, adjust=False, min_periods=DAILY_VOL_SPAN)
        .std(bias=False)
    )
    sigma_ann = return_vol * math.sqrt(ANNUALIZER)
    vol_scale = (TARGET_VOL / sigma_ann.replace(0.0, np.nan)).clip(upper=WEIGHT_CAP * 5.0)
    frame["price_volatility"] = price_vol
    frame["return_volatility"] = return_vol
    frame["sigma_ann"] = sigma_ann
    frame["vol_scale"] = vol_scale
    frame["position_buffer"] = BUFFER_FRACTION * vol_scale

    forecast_columns: list[str] = []
    position_columns: list[str] = []
    for fast, slow in EMA_PAIRS:
        fast_ema = engine.ema(close, fast)
        slow_ema = engine.ema(close, slow)
        raw = (fast_ema - slow_ema) / price_vol.replace(0.0, np.nan)
        standard = (raw * EWMAC_SCALARS[(fast, slow)]).clip(
            -STANDARD_FORECAST_CAP,
            STANDARD_FORECAST_CAP,
        )
        stem = f"{fast}_{slow}"
        frame[f"ema_fast_{stem}"] = fast_ema
        frame[f"ema_slow_{stem}"] = slow_ema
        frame[f"raw_forecast_{stem}"] = raw
        frame[f"forecast_{stem}"] = standard
        frame[f"position_{stem}"] = (standard / 10.0 * vol_scale).clip(-WEIGHT_CAP, WEIGHT_CAP)
        forecast_columns.append(f"forecast_{stem}")
        position_columns.append(f"position_{stem}")

    combined = (
        frame[forecast_columns]
        .mul(np.asarray(EMA_WEIGHTS), axis=1)
        .sum(axis=1, min_count=len(forecast_columns))
        .clip(-STANDARD_FORECAST_CAP, STANDARD_FORECAST_CAP)
    )
    frame["forecast"] = combined
    frame["desired_position"] = (combined / 10.0 * vol_scale).clip(-WEIGHT_CAP, WEIGHT_CAP)
    frame["desired_long_only"] = frame["desired_position"].clip(lower=0.0)
    frame["desired_short_only"] = frame["desired_position"].clip(upper=0.0)
    frame["desired_forecast_mapped_1x"] = (combined / STANDARD_FORECAST_CAP).clip(-1.0, 1.0)
    return frame


def apply_variable_buffer(
    desired: pd.Series,
    buffers: pd.Series,
    max_abs_position: float,
) -> pd.Series:
    output = np.zeros(len(desired), dtype="float64")
    current = 0.0
    targets = desired.to_numpy("float64")
    widths = buffers.to_numpy("float64")
    for index, (value, width) in enumerate(zip(targets, widths, strict=True)):
        if not np.isfinite(value):
            target = 0.0
            threshold = 0.0
        else:
            target = float(np.clip(value, -max_abs_position, max_abs_position))
            threshold = float(width) if np.isfinite(width) else 0.0
        if abs(target - current) + 1e-15 >= threshold:
            current = target
        output[index] = current
    return pd.Series(output, index=desired.index, name="position")


def yearly_table(path: pd.DataFrame) -> list[dict[str, Any]]:
    frame = path.copy()
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame["year"] = frame["ts"].dt.year
    rows: list[dict[str, Any]] = []
    for year, group in frame.groupby("year", sort=True):
        if len(group) < 2:
            continue
        equity = group["equity_net"].astype("float64") / float(group["equity_net"].iloc[0])
        drawdown = equity / equity.cummax() - 1.0
        rows.append(
            {
                "year": int(year),
                "bars": int(len(group)),
                "return_pct": float((equity.iloc[-1] - 1.0) * 100.0),
                "max_drawdown_pct": float(drawdown.min() * 100.0),
                "average_abs_position": float(group["position"].abs().mean()),
                "turnover": float(group["turnover"].sum()),
            }
        )
    return rows


def run_named(
    engine: object,
    features: pd.DataFrame,
    funding: pd.DataFrame,
    desired: pd.Series,
    *,
    name: str,
    start_index: int,
    config: object,
    buffer_series: pd.Series | None = None,
) -> object:
    if buffer_series is not None:
        desired = apply_variable_buffer(desired, buffer_series, config.max_abs_position)
    return engine.backtest_target(
        features,
        funding,
        desired,
        name=name,
        timeframe=TIMEFRAME,
        buffer=0.0,
        config=config,
        start_index=start_index,
    )


def run_suite(engine: object) -> tuple[dict[str, Any], dict[str, pd.DataFrame]]:
    daily, daily_quality = load_and_audit_daily()
    funding, funding_quality = load_and_audit_funding()
    daily, funding_align = align_to_funding_coverage(daily, funding)
    features = build_classic_cta_features(daily, engine)
    valid = features[
        [
            "forecast",
            "desired_position",
            "vol_scale",
            "forecast_8_32",
            "forecast_16_64",
            "forecast_32_128",
            "forecast_64_256",
        ]
    ].notna().all(axis=1)
    valid_indices = np.flatnonzero(valid.to_numpy())
    if not len(valid_indices):
        raise RuntimeError("classic CTA produced no complete daily forecast")
    first_signal_index = int(valid_indices[0])
    start_index = first_signal_index + 1
    if start_index >= len(features):
        raise RuntimeError("no daily bar remains after the first complete forecast")

    config = engine.ForecastConfig(
        ema_pairs=EMA_PAIRS,
        weights=EMA_WEIGHTS,
        max_abs_position=WEIGHT_CAP,
    )
    buffer_series = features["position_buffer"]
    results = [
        run_named(
            engine,
            features,
            funding,
            features["desired_position"],
            name="cta_vol_target_buffer_0.00",
            start_index=start_index,
            config=config,
        ),
        run_named(
            engine,
            features,
            funding,
            features["desired_position"],
            name="cta_vol_target_buffer_0.10",
            start_index=start_index,
            config=config,
            buffer_series=buffer_series,
        ),
        run_named(
            engine,
            features,
            funding,
            features["desired_long_only"],
            name="cta_long_only_buffer_0.10",
            start_index=start_index,
            config=config,
            buffer_series=buffer_series,
        ),
        run_named(
            engine,
            features,
            funding,
            features["desired_short_only"],
            name="cta_short_only_buffer_0.10",
            start_index=start_index,
            config=config,
            buffer_series=buffer_series,
        ),
        run_named(
            engine,
            features,
            funding,
            features["desired_forecast_mapped_1x"],
            name="alpha_only_forecast_mapped_1x",
            start_index=start_index,
            config=engine.ForecastConfig(
                ema_pairs=EMA_PAIRS,
                weights=EMA_WEIGHTS,
                max_abs_position=1.0,
            ),
        ),
    ]
    for fast, slow in EMA_PAIRS:
        results.append(
            run_named(
                engine,
                features,
                funding,
                features[f"position_{fast}_{slow}"],
                name=f"sleeve_{fast}_{slow}",
                start_index=start_index,
                config=config,
            )
        )
    results.append(
        run_named(
            engine,
            features,
            funding,
            pd.Series(1.0, index=features.index),
            name="perpetual_buy_hold_1x",
            start_index=start_index,
            config=engine.ForecastConfig(
                ema_pairs=EMA_PAIRS,
                weights=EMA_WEIGHTS,
                max_abs_position=1.0,
            ),
        )
    )

    payload = {
        "family_name": FAMILY_NAME,
        "family_alias": FAMILY_ALIAS,
        "strategy_family_mechanism": (
            "classic three-layer CTA: unified EWMAC alpha, volatility scaling, "
            "BTC perpetual execution"
        ),
        "market": "Binance USD-M Futures",
        "symbol": SYMBOL,
        "display_symbol": DISPLAY_SYMBOL,
        "timeframe": TIMEFRAME,
        "status": "explore / not promoted / not live-ready",
        "daily_quality": daily_quality,
        "funding_quality": funding_quality,
        "funding_alignment": funding_align,
        "config": {
            "ema_pairs": [list(pair) for pair in EMA_PAIRS],
            "weights": list(EMA_WEIGHTS),
            "ewmac_scalars": {
                f"{fast}_{slow}": scalar for (fast, slow), scalar in EWMAC_SCALARS.items()
            },
            "daily_volatility_span": DAILY_VOL_SPAN,
            "standard_forecast_cap": STANDARD_FORECAST_CAP,
            "target_vol": TARGET_VOL,
            "weight_cap": WEIGHT_CAP,
            "buffer_fraction": BUFFER_FRACTION,
            "annualizer": ANNUALIZER,
            "fee_per_turnover": config.fee_per_turnover,
            "slippage_per_turnover": config.slippage_per_turnover,
            "execution": (
                "closed UTC daily forecast at t; volatility-scaled target executed "
                "at t+1 daily open"
            ),
            "funding_ordering": (
                "funding in (previous open, current open] is charged to the "
                "previously held position before rebalance"
            ),
            "end_of_sample": (
                "open position is marked at the final open and is not forcibly liquidated"
            ),
            "parameter_source": "Carver EWMAC literature; not tuned on BTC",
        },
        "forecast_start_ts": pd.Timestamp(features["ts"].iloc[first_signal_index]).isoformat(),
        "backtest_start_ts": pd.Timestamp(features["ts"].iloc[start_index]).isoformat(),
        "results": [
            {
                "name": result.name,
                "buffer": result.buffer,
                "metrics": result.metrics,
                "slices": result.slices,
                "yearly": yearly_table(result.path),
            }
            for result in results
        ],
    }
    paths = {result.name: result.path for result in results}
    paths["forecasts"] = features.loc[
        start_index:,
        [
            "ts",
            "open",
            "high",
            "low",
            "close",
            "price_volatility",
            "return_volatility",
            "sigma_ann",
            "vol_scale",
            "forecast_8_32",
            "forecast_16_64",
            "forecast_32_128",
            "forecast_64_256",
            "forecast",
            "desired_position",
            "desired_forecast_mapped_1x",
        ],
    ].reset_index(drop=True)
    return payload, paths


def number(value: object, digits: int = 2) -> str:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if not math.isfinite(parsed):
        return "n/a"
    return f"{parsed:.{digits}f}"


def pct(value: object, digits: int = 2) -> str:
    parsed = number(value, digits)
    return "n/a" if parsed == "n/a" else f"{parsed}%"


def render_report(payload: dict[str, Any], *, artifact_stem: str, run_date: str) -> str:
    results = {str(item["name"]): item for item in payload["results"]}
    primary = results["cta_vol_target_buffer_0.10"]["metrics"]
    exact = results["cta_vol_target_buffer_0.00"]["metrics"]
    long_only = results["cta_long_only_buffer_0.10"]["metrics"]
    short_only = results["cta_short_only_buffer_0.10"]["metrics"]
    mapped = results["alpha_only_forecast_mapped_1x"]["metrics"]
    buy_hold = results["perpetual_buy_hold_1x"]["metrics"]
    daily_quality = payload["daily_quality"]
    funding_quality = payload["funding_quality"]
    order = [
        "cta_vol_target_buffer_0.10",
        "cta_vol_target_buffer_0.00",
        "cta_long_only_buffer_0.10",
        "cta_short_only_buffer_0.10",
        "alpha_only_forecast_mapped_1x",
        "sleeve_8_32",
        "sleeve_16_64",
        "sleeve_32_128",
        "sleeve_64_256",
        "perpetual_buy_hold_1x",
    ]
    headline_rows = []
    for name in order:
        metrics = results[name]["metrics"]
        headline_rows.append(
            "| `{name}` | {gross} | {net} | {mdd} | {sharpe} | {cagr} | {avg_pos} | {turnover} | {cost} | {funding} |".format(
                name=name,
                gross=pct(metrics["gross_return_pct"]),
                net=pct(metrics["net_return_pct"]),
                mdd=pct(metrics["max_drawdown_net_pct"]),
                sharpe=number(metrics["sharpe_net"], 3),
                cagr=pct(metrics["cagr_net_pct"]),
                avg_pos=number(metrics["average_abs_position"], 3),
                turnover=number(metrics["annualized_turnover"], 1),
                cost=pct(metrics["trading_cost_pct_initial_equity"]),
                funding=pct(metrics["funding_paid_pct_initial_equity"]),
            )
        )
    slice_rows = []
    for item in results["cta_vol_target_buffer_0.10"]["slices"]:
        slice_rows.append(
            "| `{window}` | {ret} | {mdd} | {sharpe} | {turnover} | {avg_pos} |".format(
                window=item["window"],
                ret=pct(item["return_pct"]),
                mdd=pct(item["max_drawdown_pct"]),
                sharpe=number(item["sharpe"], 3),
                turnover=number(item["turnover"], 1),
                avg_pos=number(item["average_abs_position"], 3),
            )
        )
    year_rows = []
    for item in results["cta_vol_target_buffer_0.10"]["yearly"]:
        year_rows.append(
            "| {year} | {ret} | {mdd} | {avg_pos} | {turnover} |".format(
                year=item["year"],
                ret=pct(item["return_pct"]),
                mdd=pct(item["max_drawdown_pct"]),
                avg_pos=number(item["average_abs_position"], 3),
                turnover=number(item["turnover"], 1),
            )
        )
    excess_net = float(primary["net_return_pct"]) - float(buy_hold["net_return_pct"])
    if float(primary["net_return_pct"]) > 0.0:
        absolute = (
            f"主口径 `0.10` 波动率缓冲净收益 `{pct(primary['net_return_pct'])}`，"
            f"Sharpe `{number(primary['sharpe_net'], 3)}`，最大回撤 `{pct(primary['max_drawdown_net_pct'])}`。"
        )
    else:
        absolute = (
            f"主口径 `0.10` 波动率缓冲净收益 `{pct(primary['net_return_pct'])}`，"
            "绝对收益未成立。"
        )
    if excess_net > 0.0:
        excess = (
            f"同期 1x 永续买入持有净收益 `{pct(buy_hold['net_return_pct'])}`，"
            f"策略超额 `{pct(excess_net)}`。"
        )
    else:
        excess = (
            f"同期 1x 永续买入持有净收益 `{pct(buy_hold['net_return_pct'])}`、"
            f"Sharpe `{number(buy_hold['sharpe_net'], 3)}`、回撤 `{pct(buy_hold['max_drawdown_net_pct'])}`；"
            f"策略相对买入持有超额 `{pct(excess_net)}`，没有通过门禁 0。"
        )
    return "\n".join(
        [
            f"# {FAMILY_NAME} 经典 CTA 日线回测（{run_date}）",
            "",
            f"- Family：`{FAMILY_NAME}`（`{FAMILY_ALIAS}`）",
            "- 状态：`explore / not promoted / not live-ready`",
            f"- 市场：Binance USD-M Futures `{SYMBOL}` perpetual，UTC `1d`",
            (
                f"- 日线数据：`{daily_quality['first_ts']}` → `{daily_quality['last_ts']}`；"
                f"资金费对齐后回测从 `{payload['backtest_start_ts']}` 开始"
            ),
            "- 成本：每单位换手手续费 `0.001` + adverse slippage `0.0004`；纳入实际 funding",
            "- 切片仅作事后审计，不用于参数选择",
            "- 参数来源：Carver EWMAC 文献；未对 BTC 调参",
            "",
            "## 结论",
            "",
            absolute,
            excess,
            (
                f"多头-only `{pct(long_only['net_return_pct'])}` / "
                f"空头-only `{pct(short_only['net_return_pct'])}`；"
                f"去掉波动目标、把 forecast 映射到 `±1x` 时净收益 `{pct(mapped['net_return_pct'])}`。"
                f"精确跟踪净收益 `{pct(exact['net_return_pct'])}`。"
            ),
            "",
            (
                "这是单资产、文献参数、次日开盘成交的诊断，不是跨市场 leave-one-out 优化，"
                "也不构成版本登记或 runner 输入。相关但不同源的关闭研究线见 "
                "[`XA-1D-EWMAC-UT`](../../../asset-portfolios/1d-ewmac-universal-trend/README.md)。"
            ),
            "",
            "## 三层定义",
            "",
            "- Alpha：EMA `8/32`、`16/64`、`32/128`、`64/256` 等权；scalar `5.3/3.75/2.65/1.87`；forecast 裁剪 `±20`。",
            "- Risk：`w = (F/10) × (20% / σ_ann)`，`σ` 为 `span=35` 的 EWMA 收益波动，仓位上限 `2x`。",
            "- Execution：当日收盘决策、次日开盘成交；主口径 buffer 为 `0.10 × (20%/σ_ann)`。",
            "- 完整冻结点见 [文献基线契约](../specs/btc-1d-ccta-literature-baseline-2026-08-17.md)。",
            "",
            "## 全区间结果",
            "",
            "| 运行 | 毛收益 | 净收益 | 最大回撤 | Sharpe | CAGR | 平均绝对仓位 | 年换手 | 成本/初始权益 | 资金费/初始权益 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            *headline_rows,
            "",
            "## 最近区间（主口径 0.10 缓冲）",
            "",
            "| 窗口 | 收益 | 最大回撤 | Sharpe | 换手 | 平均绝对仓位 |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
            *slice_rows,
            "",
            "## 分年（主口径 0.10 缓冲）",
            "",
            "| 年 | 收益 | 最大回撤 | 平均绝对仓位 | 换手 |",
            "| --- | ---: | ---: | ---: | ---: |",
            *year_rows,
            "",
            "## 数据质量与执行",
            "",
            (
                f"- Native `1d` normalized rows：`{daily_quality['rows']}`，expected "
                f"`{daily_quality['expected_rows']}`，missing `{daily_quality['missing_bars']}`，"
                f"blocker `{daily_quality['blocker_count']}`。"
            ),
            (
                f"- Raw/normalized unmatched：`{daily_quality['raw_normalized_unmatched_rows']}`；"
                f"字段 mismatch：`{sum(daily_quality['raw_normalized_mismatch'].values())}`。"
            ),
            (
                f"- Funding events：`{funding_quality['rows']}`，"
                f"`{funding_quality['first_ts']}` → `{funding_quality['last_ts']}`，"
                f"最大间隔 `{number(funding_quality['max_gap_hours'], 2)}h`，"
                f"blocker `{funding_quality['blocker_count']}`。"
            ),
            (
                f"- 资金费对齐：丢弃首尾无法收费的日 K `{payload['funding_alignment']['dropped_leading_or_trailing']}` 根，"
                f"保留 `{payload['funding_alignment']['aligned_rows']}` 根。"
            ),
            "- 连续目标仓位未模拟最小名义、数量步长或拒单；即使收益为正也不是 live-ready。",
            "",
            "## 证据",
            "",
            f"- Summary：[../artifacts/{artifact_stem}-summary.json](../artifacts/{artifact_stem}-summary.json)",
            f"- Forecast path：[../artifacts/{artifact_stem}-forecasts.csv](../artifacts/{artifact_stem}-forecasts.csv)",
            f"- Equity / turnover paths：[../artifacts/{artifact_stem}-paths.csv](../artifacts/{artifact_stem}-paths.csv)",
            f"- 脚本：[../scripts/{Path(__file__).name}](../scripts/{Path(__file__).name})",
            (
                f"- 共享执行内核：[../../../_shared-kernels/multi-horizon-ema-forecast/v1/engine.py]"
                f"(../../../_shared-kernels/multi-horizon-ema-forecast/v1/engine.py)，"
                f"SHA256 `{ENGINE_SHA256}`"
            ),
            "",
            "## 状态",
            "",
            "`explore / not promoted / not live-ready`。本轮只回答这组文献 CTA 规则在 BTC 日线上的可交易性，不登记版本。",
            "",
        ]
    )


def self_test(engine: object) -> None:
    rng = np.random.default_rng(7)
    n = 900
    trend = np.cumsum(np.full(n, 0.004) + rng.normal(0, 0.012, n))
    ts = pd.date_range("2020-01-01", periods=n, freq="1D", tz="UTC")
    close = 10000.0 * np.exp(trend)
    daily = pd.DataFrame(
        {
            "ts": ts,
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": 1.0,
            "quote_volume": close,
            "trade_count": 1,
            "vwap": close,
            "is_closed": True,
            "source": "self-test",
        }
    )
    funding = pd.DataFrame(
        {
            "ts": pd.date_range(ts[0], ts[-1] + pd.Timedelta(hours=16), freq="8h", tz="UTC"),
        }
    )
    funding["funding_rate"] = 0.0
    features = build_classic_cta_features(daily, engine)
    start_index = int(features["desired_position"].first_valid_index()) + 1
    config = engine.ForecastConfig(
        ema_pairs=EMA_PAIRS,
        weights=EMA_WEIGHTS,
        max_abs_position=WEIGHT_CAP,
    )
    result = run_named(
        engine,
        features,
        funding,
        features["desired_position"],
        name="self_test_uptrend",
        start_index=start_index,
        config=config,
        buffer_series=features["position_buffer"],
    )
    if result.path["position"].iloc[-1] <= 0:
        raise AssertionError("uptrend must end long")
    if result.metrics["net_return_pct"] <= 0:
        raise AssertionError("uptrend must be profitable after costs")


def main() -> None:
    args = parse_args()
    engine = load_engine()
    if args.self_test:
        self_test(engine)
        print("self-test passed")
        return
    artifact_stem = f"btc-1d-ccta-classic-cta-{args.run_date}"
    payload, paths = run_suite(engine)
    payload["run_date"] = args.run_date
    payload["kernel"] = {
        "path": str(ENGINE_PATH.relative_to(ROOT)),
        "sha256": ENGINE_SHA256,
    }
    payload["artifacts"] = {
        "summary": f"artifacts/{artifact_stem}-summary.json",
        "forecasts": f"artifacts/{artifact_stem}-forecasts.csv",
        "paths": f"artifacts/{artifact_stem}-paths.csv",
    }
    engine.write_suite_outputs(
        family_dir=FAMILY_DIR,
        artifact_stem=artifact_stem,
        payload=payload,
        paths=paths,
    )
    report_path = (
        FAMILY_DIR / "diagnostics" / f"btc-1d-ccta-classic-cta-backtest-{args.run_date}.md"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        render_report(payload, artifact_stem=artifact_stem, run_date=args.run_date),
        encoding="utf-8",
    )
    headline = {
        result["name"]: {
            "net_return_pct": result["metrics"]["net_return_pct"],
            "sharpe_net": result["metrics"]["sharpe_net"],
            "max_drawdown_net_pct": result["metrics"]["max_drawdown_net_pct"],
            "cagr_net_pct": result["metrics"]["cagr_net_pct"],
        }
        for result in payload["results"]
        if result["name"]
        in {
            "cta_vol_target_buffer_0.10",
            "cta_vol_target_buffer_0.00",
            "cta_long_only_buffer_0.10",
            "cta_short_only_buffer_0.10",
            "perpetual_buy_hold_1x",
        }
    }
    print(json.dumps(headline, ensure_ascii=False, indent=2))
    print(f"report -> {report_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
