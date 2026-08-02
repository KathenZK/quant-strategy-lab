from __future__ import annotations

import argparse
from dataclasses import asdict
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
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-ma7-ma30-pyramiding-transfer"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
MA_SCRIPT = ROOT / "research/hype/1d-pyramiding-trend/scripts/research_hype_1d_ma7_ma30.py"
MA_SCRIPT_SHA256 = "6a3517c4cc066a1678881c2a1d1fa34bf6b4a98f8fd336e71abd50ec214c6b42"
COMMON_START = pd.Timestamp("2025-05-31T00:00:00Z")
TERMINAL_TS = pd.Timestamp("2026-07-30T00:00:00Z")

ASSETS = {
    "BTCUSDT": {
        "slug": "btc_usdt_usdt",
        "frame": ROOT / "research/btc/1h-adaptive-regime/artifacts/btc_binance_1h_closed_klines_2y.parquet",
        "quality": ROOT / "research/btc/1h-adaptive-regime/artifacts/btc_binance_1h_data_quality_2y.json",
    },
    "ETHUSDT": {
        "slug": "eth_usdt_usdt",
        "frame": ROOT / "research/eth/1h-adaptive-regime/artifacts/eth_binance_1h_closed_klines_2y.parquet",
        "quality": ROOT / "research/eth/1h-adaptive-regime/artifacts/eth_binance_1h_data_quality_2y.json",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Direct-transfer HYPE MA7/MA30 pure-return observation to BTC/ETH.")
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def load_module(path: Path, name: str) -> object:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if path == MA_SCRIPT and digest != MA_SCRIPT_SHA256:
        raise RuntimeError(
            f"HYPE MA7/MA30 engine drift: expected {MA_SCRIPT_SHA256}, got {digest}"
        )
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def frozen_config(ma: object) -> object:
    return ma.Config(
        ma_type=1,
        entry_mode=2,
        direction=0,
        confirm_days=2,
        slope_days=1,
        breakout_window=7,
        entry_buffer_atr=0.0,
        exit_mode=0,
        atr_window=10,
        adx_min=0.0,
        atr_pct_cap=0.0,
        initial_leverage=0.5,
        add_mode=1,
        add_step_atr=0.25,
        add_increment=1.5,
        stop_atr=3.0,
        trail_atr=3.0,
        profit_trigger_atr=3.0,
        profit_lock_atr=0.5,
        max_hold_days=20,
        cooldown_days=2,
        allow_flip=False,
    )


def _load_raw(slug: str, dates: set[object]) -> pd.DataFrame:
    root = ROOT / "data/raw/ohlcv/exchange=binance/market_type=perp/timeframe=1h"
    frames: list[pd.DataFrame] = []
    for date_value in sorted(dates):
        path = root / f"date={date_value}" / f"symbol={slug}.parquet"
        if not path.exists():
            raise FileNotFoundError(path)
        frames.append(pd.read_parquet(path))
    raw = pd.concat(frames, ignore_index=True)
    raw["open_time"] = pd.to_datetime(raw["open_time"], utc=True)
    return raw


def load_and_audit_hourly(symbol: str, spec: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    metadata = json.loads(Path(spec["quality"]).read_text(encoding="utf-8"))
    upstream = metadata["data_quality"]
    if int(upstream["blocker_count"]) != 0:
        raise RuntimeError(f"{symbol} upstream data blockers: {upstream}")

    normalized = pd.read_parquet(spec["frame"])
    normalized["ts"] = pd.to_datetime(normalized["ts"], utc=True)
    normalized = normalized.sort_values("ts").reset_index(drop=True)
    dates = set(normalized["ts"].dt.date)
    raw = _load_raw(str(spec["slug"]), dates)
    raw = raw.loc[
        raw["open_time"].between(normalized["ts"].iloc[0], normalized["ts"].iloc[-1], inclusive="both")
    ].sort_values("open_time").reset_index(drop=True)

    expected = pd.date_range(normalized["ts"].iloc[0], normalized["ts"].iloc[-1], freq="1h")
    required = [
        "ts", "open", "high", "low", "close", "volume", "quote_volume",
        "trade_count", "vwap", "is_closed", "source",
    ]
    missing_columns = sorted(set(required).difference(normalized.columns))
    critical_nulls = {column: int(normalized[column].isna().sum()) for column in required if column in normalized}
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
            ["open_time", "open", "high", "low", "close", "volume", "quote_volume", "trade_count"]
        ],
        left_on="ts",
        right_on="open_time",
        how="outer",
        suffixes=("_normalized", "_raw"),
        indicator=True,
    )
    mismatch: dict[str, int] = {}
    both = compare.loc[compare["_merge"].eq("both")]
    for column in ("open", "high", "low", "close", "volume", "quote_volume", "trade_count"):
        left = pd.to_numeric(both[f"{column}_normalized"], errors="coerce").to_numpy("float64")
        right = pd.to_numeric(both[f"{column}_raw"], errors="coerce").to_numpy("float64")
        tolerance = 0.0 if column == "trade_count" else 1e-12
        mismatch[column] = int((~np.isclose(left, right, rtol=0.0, atol=tolerance)).sum())
    missing = expected.difference(pd.DatetimeIndex(normalized["ts"]))
    blocker_count = (
        len(missing_columns)
        + len(missing)
        + int(normalized["ts"].duplicated().sum())
        + int(raw["open_time"].duplicated().sum())
        + sum(critical_nulls.values())
        + invalid_ohlc
        + int((~normalized["is_closed"].astype(bool)).sum())
        + int(compare["_merge"].ne("both").sum())
        + sum(mismatch.values())
    )
    quality = {
        "symbol": symbol,
        "rows": int(len(normalized)),
        "first_ts": normalized["ts"].iloc[0].isoformat(),
        "last_ts": normalized["ts"].iloc[-1].isoformat(),
        "expected_rows": int(len(expected)),
        "missing_bars": int(len(missing)),
        "duplicate_normalized": int(normalized["ts"].duplicated().sum()),
        "duplicate_raw": int(raw["open_time"].duplicated().sum()),
        "critical_nulls": critical_nulls,
        "invalid_ohlc_rows": invalid_ohlc,
        "non_closed_rows": int((~normalized["is_closed"].astype(bool)).sum()),
        "raw_normalized_unmatched_rows": int(compare["_merge"].ne("both").sum()),
        "raw_normalized_mismatch": mismatch,
        "upstream_blocker_count": int(upstream["blocker_count"]),
        "blocker_count": int(blocker_count),
    }
    if blocker_count:
        raise RuntimeError(f"{symbol} data-quality blockers: {quality}")

    funding_path = (
        ROOT / "data/normalized/funding/exchange=binance/market_type=perp"
        / f"symbol={spec['slug']}/funding.parquet"
    )
    funding = pd.read_parquet(funding_path)
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
    funding["funding_rate"] = pd.to_numeric(funding["funding_rate"], errors="coerce")
    funding = funding.sort_values("ts").reset_index(drop=True)
    gaps = funding["ts"].diff().dropna()
    funding_quality = {
        "rows": int(len(funding)),
        "first_ts": funding["ts"].iloc[0].isoformat(),
        "last_ts": funding["ts"].iloc[-1].isoformat(),
        "duplicate_ts": int(funding["ts"].duplicated().sum()),
        "critical_null_rows": int(funding[["ts", "funding_rate"]].isna().any(axis=1).sum()),
        "max_gap_hours": float(gaps.max().total_seconds() / 3600.0),
    }
    funding_quality["blocker_count"] = int(
        funding_quality["duplicate_ts"]
        + funding_quality["critical_null_rows"]
        + (funding_quality["max_gap_hours"] > 8.01)
    )
    if funding_quality["blocker_count"]:
        raise RuntimeError(f"{symbol} funding blockers: {funding_quality}")
    return normalized, funding[["ts", "funding_rate"]].copy(), {
        "market": quality,
        "funding": funding_quality,
    }


def build_book(ma: object, parent: object, symbol: str, spec: dict[str, Any]) -> object:
    hourly, funding, quality = load_and_audit_hourly(symbol, spec)
    daily, daily_quality = parent.aggregate_complete_daily(hourly)
    if TERMINAL_TS not in set(hourly["ts"]):
        raise RuntimeError(f"{symbol} terminal open {TERMINAL_TS} missing")
    daily = daily.loc[pd.to_datetime(daily["ts"], utc=True) < TERMINAL_TS].copy()
    if daily.empty or pd.Timestamp(daily["ts"].iloc[-1]) != TERMINAL_TS - pd.Timedelta(days=1):
        raise RuntimeError(f"{symbol} complete daily range does not reach terminal boundary")
    open_values = daily["open"].to_numpy("float64")
    high = daily["high"].to_numpy("float64")
    low = daily["low"].to_numpy("float64")
    close = daily["close"].to_numpy("float64")
    open_index = pd.DatetimeIndex([*pd.to_datetime(daily["ts"], utc=True), TERMINAL_TS])
    quality["daily"] = daily_quality
    quality["terminal_open_ts"] = TERMINAL_TS.isoformat()
    quality["terminal_open"] = float(hourly.loc[hourly["ts"].eq(TERMINAL_TS), "open"].iloc[0])
    return ma.Book(
        ts=pd.DatetimeIndex(pd.to_datetime(daily["ts"], utc=True)),
        terminal_ts=TERMINAL_TS,
        open=open_values,
        high=high,
        low=low,
        close=close,
        ma7={0: ma._sma(close, 7), 1: ma._ema(close, 7)},
        ma30={0: ma._sma(close, 30), 1: ma._ema(close, 30)},
        atr={window: parent._atr(high, low, close, window) for window in (5, 7, 10, 14, 20, 30)},
        adx={window: parent._adx(high, low, close, window) for window in (5, 7, 10, 14, 20, 30)},
        prior_high={window: parent._prior_roll(high, window, "max") for window in (2, 3, 5, 7, 10, 14, 20)},
        prior_low={window: parent._prior_roll(low, window, "min") for window in (2, 3, 5, 7, 10, 14, 20)},
        funding_by_open=parent._funding_by_open(open_index, funding),
        quality=quality,
        funding_quality=quality["funding"],
    )


def run_window(ma: object, config: object, book: object, start: int, end: int, retain: bool) -> dict[str, Any]:
    base = ma.backtest(config, book, start_index=start, terminal_index=end, retain=retain)
    stress = ma.backtest(config, book, start_index=start, terminal_index=end, slippage=ma.STRESS_SLIPPAGE)
    delayed = ma.backtest(config, book, start_index=start, terminal_index=end, delay_days=2)
    start_price = float(book.open[start])
    terminal_price = float(book.quality["terminal_open"] if end == book.daily_count else book.open[end])
    return {
        "base": base.metrics,
        "stress_8bps": stress.metrics,
        "k_plus_2": delayed.metrics,
        "buy_and_hold_multiple": terminal_price / start_price,
        "recent_slices": ma.recent_slices(base.path) if retain else [],
        "trades": base.trades,
        "path": base.path,
    }


def _json_default(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if math.isinf(value):
        return "Infinity" if value > 0 else "-Infinity"
    raise TypeError(type(value).__name__)


def main() -> None:
    args = parse_args()
    ma = load_module(MA_SCRIPT, "hype_ma7_ma30_transfer_engine")
    if args.self_test:
        ma.self_test()
        print("self-test: PASS")
        return
    parent = ma._load_parent()
    config = frozen_config(ma)
    output: dict[str, Any] = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "Binance-1D-MA7-MA30-Pyramiding-Transfer",
        "status": "explore / not promoted / not live-ready",
        "selection": "zero target-asset tuning; frozen HYPE pure-return observation",
        "source_engine": {
            "path": str(MA_SCRIPT.relative_to(ROOT)),
            "sha256": MA_SCRIPT_SHA256,
        },
        "config": ma.serialize_config(config),
        "costs": {
            "fee_per_fill": ma.FEE,
            "base_slippage_per_fill": ma.SLIPPAGE,
            "stress_slippage_per_fill": ma.STRESS_SLIPPAGE,
        },
        "assets": {},
    }
    flat_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    path_rows: list[dict[str, Any]] = []
    for symbol, spec in ASSETS.items():
        book = build_book(ma, parent, symbol, spec)
        common_start = int(book.ts.searchsorted(COMMON_START))
        if pd.Timestamp(book.ts[common_start]) != COMMON_START:
            raise RuntimeError(f"{symbol} common start missing")
        windows = {
            "asset_two_year_daily": (0, book.daily_count),
            "hype_common_window": (common_start, book.daily_count),
        }
        asset_result: dict[str, Any] = {
            "data_quality": book.quality,
            "windows": {},
        }
        for label, (start, end) in windows.items():
            result = run_window(ma, config, book, start, end, retain=True)
            asset_result["windows"][label] = {
                key: value for key, value in result.items() if key not in {"trades", "path"}
            }
            flat_rows.append({
                "symbol": symbol,
                "window": label,
                **result["base"],
                "buy_and_hold_multiple": result["buy_and_hold_multiple"],
                "stress_8bps_annualized_factor": result["stress_8bps"]["annualized_factor"],
                "stress_8bps_max_drawdown_pct": result["stress_8bps"]["max_drawdown_pct"],
                "k_plus_2_annualized_factor": result["k_plus_2"]["annualized_factor"],
                "k_plus_2_max_drawdown_pct": result["k_plus_2"]["max_drawdown_pct"],
            })
            trade_rows.extend({"symbol": symbol, "window": label, **row} for row in result["trades"])
            path_rows.extend({"symbol": symbol, "window": label, **row} for row in result["path"])
        output["assets"][symbol] = asset_result

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"binance-1d-ma7-ma30-pyramiding-transfer"
    (ARTIFACT_DIR / f"{stem}-summary-{args.run_date}.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    pd.DataFrame(flat_rows).to_csv(ARTIFACT_DIR / f"{stem}-summary-{args.run_date}.csv", index=False)
    pd.DataFrame(trade_rows).to_csv(ARTIFACT_DIR / f"{stem}-trades-{args.run_date}.csv", index=False)
    pd.DataFrame(path_rows).to_csv(ARTIFACT_DIR / f"{stem}-path-{args.run_date}.csv", index=False)
    print(json.dumps(output, ensure_ascii=False, indent=2, default=_json_default))


if __name__ == "__main__":
    main()
