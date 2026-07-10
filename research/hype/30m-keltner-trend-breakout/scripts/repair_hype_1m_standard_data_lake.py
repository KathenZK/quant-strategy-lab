from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import research_hype_30m_k2_fq_v2_atrvt_off_backtest as base  # noqa: E402

from strategy_lab.data import DataLakeLayout, DatasetKind, MarketType  # noqa: E402
from strategy_lab.data.normalize import normalize_dataset  # noqa: E402
from strategy_lab.data.settings import load_settings  # noqa: E402
from strategy_lab.data.store import write_dataframe  # noqa: E402


RUN_DATE = "2026-07-10"
SUMMARY_PATH = base.ARTIFACT_DIR / f"hype_1m_standard_data_lake_repair_{RUN_DATE}.json"
CONFLICT_TS = pd.Timestamp("2026-06-25 08:46:00+00:00")
EXPECTED_CONFLICT_BAR = {
    "open": 63.561,
    "high": 63.581,
    "low": 63.520,
    "close": 63.567,
    "volume": 6404.81,
    "quote_volume": 406978.32864,
    "trade_count": 1117,
}
SCHEMA = [
    "ts",
    "exchange",
    "symbol",
    "market_type",
    "timeframe",
    "base_asset",
    "quote_asset",
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
    "date",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, default=base.CACHE_PATH)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def prepare_cache(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_parquet(path)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = frame.sort_values("ts").drop_duplicates("ts", keep="last").reset_index(drop=True)
    numeric = ["open", "high", "low", "close", "volume", "quote_volume", "trade_count"]
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["vwap"] = frame["quote_volume"] / frame["volume"].replace(0.0, np.nan)
    frame["vwap"] = frame["vwap"].fillna(frame["close"])
    frame["exchange"] = "binance"
    frame["symbol"] = base.DISPLAY_SYMBOL
    frame["market_type"] = "perp"
    frame["timeframe"] = "1m"
    frame["base_asset"] = "HYPE"
    frame["quote_asset"] = "USDT"
    frame["is_closed"] = frame.get("is_closed", True).fillna(False).astype(bool)
    frame["source"] = frame.get("source", "binance_futures_kline_api").fillna("binance_futures_kline_api")
    frame["date"] = frame["ts"].dt.date.astype("string")
    return frame[SCHEMA]


def quality_gate(frame: pd.DataFrame) -> dict[str, Any]:
    ts = pd.DatetimeIndex(frame["ts"])
    expected = pd.date_range(ts.min(), ts.max(), freq="1min", tz="UTC")
    invalid_ohlc = (
        frame["high"].lt(frame[["open", "close", "low"]].max(axis=1))
        | frame["low"].gt(frame[["open", "close", "high"]].min(axis=1))
    )
    critical = ["open", "high", "low", "close", "volume", "quote_volume", "trade_count", "vwap"]
    quality = {
        "rows": int(len(frame)),
        "start": str(ts.min()),
        "end": str(ts.max()),
        "expected_rows": int(len(expected)),
        "missing_bars": int(len(expected.difference(ts))),
        "duplicate_ts": int(ts.duplicated().sum()),
        "invalid_ohlc": int(invalid_ohlc.sum()),
        "critical_null_rows": int(frame[critical].isna().any(axis=1).sum()),
        "non_closed_rows": int((~frame["is_closed"]).sum()),
        "non_positive_price_rows": int(frame[["open", "high", "low", "close"]].le(0.0).any(axis=1).sum()),
        "negative_volume_rows": int(frame[["volume", "quote_volume", "trade_count"]].lt(0.0).any(axis=1).sum()),
    }
    quality["pass"] = all(
        quality[key] == 0
        for key in [
            "missing_bars",
            "duplicate_ts",
            "invalid_ohlc",
            "critical_null_rows",
            "non_closed_rows",
            "non_positive_price_rows",
            "negative_volume_rows",
        ]
    )
    return quality


def verify_conflict_bar(frame: pd.DataFrame) -> dict[str, Any]:
    rows = frame.loc[frame["ts"].eq(CONFLICT_TS)]
    if len(rows) != 1:
        raise RuntimeError(f"expected exactly one conflict row, found {len(rows)}")
    row = rows.iloc[0]
    comparisons = {
        column: bool(np.isclose(float(row[column]), float(expected), rtol=0.0, atol=1e-12))
        for column, expected in EXPECTED_CONFLICT_BAR.items()
    }
    if not all(comparisons.values()):
        raise RuntimeError(f"cache conflict row does not match retained Binance API witness: {comparisons}")
    return {
        "ts": str(CONFLICT_TS),
        "expected": EXPECTED_CONFLICT_BAR,
        "actual": {column: float(row[column]) for column in EXPECTED_CONFLICT_BAR},
        "all_match": True,
        "evidence": "Binance FAPI /fapi/v1/klines queried after bar closure on 2026-07-10.",
    }


def write_partitions(frame: pd.DataFrame, *, dry_run: bool) -> dict[str, Any]:
    layout = DataLakeLayout.from_settings(load_settings(None))
    layout.ensure_directories()
    written: dict[str, list[str]] = {"raw": [], "normalized": []}
    for partition_date, day in frame.groupby(frame["ts"].dt.date, sort=True):
        normalized_day = normalize_dataset(DatasetKind.OHLCV, day.reset_index(drop=True))
        raw_day = normalized_day.copy()
        if dry_run:
            continue
        raw_path = write_dataframe(
            raw_day,
            layout=layout,
            layer="raw",
            kind=DatasetKind.OHLCV,
            exchange="binance",
            market_type=MarketType.PERP,
            symbol=base.DISPLAY_SYMBOL,
            timeframe="1m",
            partition_date=partition_date,
        )
        normalized_path = write_dataframe(
            normalized_day,
            layout=layout,
            layer="normalized",
            kind=DatasetKind.OHLCV,
            exchange="binance",
            market_type=MarketType.PERP,
            symbol=base.DISPLAY_SYMBOL,
            timeframe="1m",
            partition_date=partition_date,
        )
        written["raw"].append(str(raw_path))
        written["normalized"].append(str(normalized_path))
    return {
        "dry_run": dry_run,
        "partition_days": int(frame["ts"].dt.date.nunique()),
        "raw_written": len(written["raw"]),
        "normalized_written": len(written["normalized"]),
        "first_raw_path": written["raw"][0] if written["raw"] else None,
        "last_raw_path": written["raw"][-1] if written["raw"] else None,
    }


def load_layer(root: Path) -> pd.DataFrame:
    files = sorted(root.rglob("symbol=hype_usdt_usdt.parquet"))
    if not files:
        raise RuntimeError(f"no HYPE 1m partitions under {root}")
    return pd.concat([pd.read_parquet(path) for path in files], ignore_index=True)


def verify_written_lake(cache: pd.DataFrame) -> dict[str, Any]:
    relative = Path("ohlcv/exchange=binance/market_type=perp/timeframe=1m")
    raw = load_layer(base.ROOT / "data/raw" / relative)
    normalized = load_layer(base.ROOT / "data/normalized" / relative)
    for frame in [raw, normalized]:
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
        frame.sort_values("ts", inplace=True)
        frame.drop_duplicates("ts", keep="last", inplace=True)
        frame.reset_index(drop=True, inplace=True)
    common = [column for column in SCHEMA if column in raw.columns and column in normalized.columns]
    raw_cmp = raw[common].reset_index(drop=True)
    normalized_cmp = normalized[common].reset_index(drop=True)
    raw_normalized_equal = bool(raw_cmp.equals(normalized_cmp))

    value_columns = ["open", "high", "low", "close", "volume", "quote_volume", "trade_count", "vwap"]
    merged = cache[["ts", *value_columns]].merge(
        normalized[["ts", *value_columns]],
        on="ts",
        how="outer",
        suffixes=("_cache", "_lake"),
        indicator=True,
    )
    mismatch_cells = 0
    for column in value_columns:
        left = pd.to_numeric(merged[f"{column}_cache"], errors="coerce").to_numpy("float64")
        right = pd.to_numeric(merged[f"{column}_lake"], errors="coerce").to_numpy("float64")
        mismatch_cells += int((~np.isclose(left, right, rtol=0.0, atol=1e-12, equal_nan=True)).sum())
    result = {
        "raw_rows": int(len(raw)),
        "normalized_rows": int(len(normalized)),
        "raw_start": str(raw["ts"].min()),
        "raw_end": str(raw["ts"].max()),
        "normalized_start": str(normalized["ts"].min()),
        "normalized_end": str(normalized["ts"].max()),
        "raw_normalized_exact_match": raw_normalized_equal,
        "cache_lake_join": merged["_merge"].value_counts().sort_index().to_dict(),
        "cache_lake_mismatch_cells": mismatch_cells,
    }
    result["pass"] = bool(
        raw_normalized_equal
        and len(raw) == len(cache)
        and len(normalized) == len(cache)
        and result["cache_lake_join"].get("both", 0) == len(cache)
        and result["cache_lake_join"].get("left_only", 0) == 0
        and result["cache_lake_join"].get("right_only", 0) == 0
        and mismatch_cells == 0
    )
    return result


def main() -> None:
    args = parse_args()
    base.ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    cache = prepare_cache(args.cache)
    quality = quality_gate(cache)
    if not quality["pass"]:
        raise RuntimeError(f"cache quality gate failed: {quality}")
    conflict = verify_conflict_bar(cache)
    write_summary = write_partitions(cache, dry_run=args.dry_run)
    if not args.dry_run:
        cache.to_parquet(args.cache, index=False)
        lake_verification = verify_written_lake(cache)
        if not lake_verification["pass"]:
            raise RuntimeError(f"written lake verification failed: {lake_verification}")
    else:
        lake_verification = {"pass": None, "dry_run": True}
    summary = {
        "run_date": RUN_DATE,
        "source_cache": str(args.cache),
        "quality": quality,
        "conflict_bar_verification": conflict,
        "write": write_summary,
        "lake_verification": lake_verification,
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    print(f"summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
