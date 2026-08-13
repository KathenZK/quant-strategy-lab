from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import importlib.util
import io
import json
from pathlib import Path
import sys
from typing import Any
import zipfile

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-ma7-quantile-utility-meta-label"
ARTIFACT_DIR = FAMILY_DIR / "artifacts/p0_price_data_2026-08-10"
FEATURE_DIR = ROOT / "data/features/binance_1d_ma7_quml_p0"
RAW_ROOT = ROOT / (
    "data/raw/quml_price_funding/exchange=binance/market_type=perp/"
    "source=binance_vision_monthly"
)
CUTOFF = pd.Timestamp("2025-05-31T00:00:00Z")
MIN_MONTH: pd.Period | None = None
MAX_MONTH = pd.Period("2025-05", freq="M")
DEFAULT_SYMBOLS = ("BCHUSDT", "ETCUSDT", "XLMUSDT")
SYMBOL_META = {
    "BCHUSDT": ("BCH", "BCH-USDT-PERP", "bchusdt"),
    "ETCUSDT": ("ETC", "ETC-USDT-PERP", "etcusdt"),
    "XLMUSDT": ("XLM", "XLM-USDT-PERP", "xlmusdt"),
    "ATOMUSDT": ("ATOM", "ATOM-USDT-PERP", "atomusdt"),
    "VETUSDT": ("VET", "VET-USDT-PERP", "vetusdt"),
    "NEARUSDT": ("NEAR", "NEAR-USDT-PERP", "nearusdt"),
    "AAVEUSDT": ("AAVE", "AAVE-USDT-PERP", "aaveusdt"),
    "FILUSDT": ("FIL", "FIL-USDT-PERP", "filusdt"),
}
DATASET_SPECS = {
    "kline": ("klines", "1h", "binance_vision_monthly_klines"),
    "mark": ("markPriceKlines", "1h", "binance_vision_monthly_mark_klines"),
    "funding": ("fundingRate", None, "binance_vision_monthly_funding_rate"),
}
KLINE_COLUMNS = (
    "open_time_ms",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time_ms",
    "quote_volume",
    "trade_count",
    "taker_buy_volume",
    "taker_buy_quote_volume",
    "ignore",
)
MARK_COLUMNS = (
    "open_time_ms",
    "open",
    "high",
    "low",
    "close",
    "ignore_volume",
    "close_time_ms",
    "ignore_quote_volume",
    "observation_count",
    "ignore_taker_base",
    "ignore_taker_quote",
    "ignore",
)


def load_module(name: str, relative_path: str) -> Any:
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


base = load_module(
    "quml_p0_price_base_vision",
    (
        "research/asset-portfolios/1d-ma7-rsi6-direction-aligned-pooled-ml/"
        "scripts/sync_binance_pooled_p0_data.py"
    ),
)
vision = load_module(
    "quml_p0_vision_transport",
    (
        "research/asset-portfolios/1d-ma7-taker-flow-meta-label/"
        "scripts/sync_binance_vision_tfml_5m.py"
    ),
)


@dataclass(frozen=True)
class Archive:
    asset: str
    symbol: str
    dataset: str
    month: str
    key: str
    etag: str
    size: int
    last_modified: str

    @property
    def url(self) -> str:
        return f"{vision.DOWNLOAD_ROOT}/{self.key}"

    @property
    def raw_path(self) -> Path:
        partition = "date" if self.dataset.endswith("_daily_repair") else "month"
        return (
            RAW_ROOT
            / f"dataset={self.dataset}"
            / f"{partition}={self.month}"
            / f"symbol={self.symbol.lower()}.zip"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Use official Binance Vision monthly archives when FAPI history is "
            "temporarily unavailable. No HYPE source is permitted."
        )
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=list(DEFAULT_SYMBOLS),
        choices=sorted(SYMBOL_META),
    )
    parser.add_argument("--max-workers", type=int, default=8)
    return parser.parse_args()


def list_archives(symbol: str, dataset: str) -> list[Archive]:
    if "HYPE" in symbol.upper():
        raise RuntimeError("HYPE source request is forbidden")
    path_kind, interval, _ = DATASET_SPECS[dataset]
    if interval is None:
        prefix = f"data/futures/um/monthly/{path_kind}/{symbol}/"
        marker = f"{symbol}-fundingRate-"
    else:
        prefix = f"data/futures/um/monthly/{path_kind}/{symbol}/{interval}/"
        marker = f"{symbol}-{interval}-"
    archives: list[Archive] = []
    for item in vision.s3_objects(prefix):
        key = str(item["key"])
        filename = Path(key).name
        if not filename.startswith(marker) or not filename.endswith(".zip"):
            continue
        month_text = filename[len(marker) : -4]
        try:
            month = pd.Period(month_text, freq="M")
        except ValueError:
            continue
        if month > MAX_MONTH or (MIN_MONTH is not None and month < MIN_MONTH):
            continue
        archives.append(
            Archive(
                asset=SYMBOL_META[symbol][0],
                symbol=symbol,
                dataset=dataset,
                month=str(month),
                key=key,
                etag=str(item["etag"]),
                size=int(item["size"]),
                last_modified=str(item["last_modified"]),
            )
        )
    archives.sort(key=lambda row: row.month)
    if not archives:
        raise RuntimeError(f"No {dataset} monthly archives for {symbol}")
    months = pd.PeriodIndex([row.month for row in archives], freq="M")
    expected_start = MIN_MONTH if MIN_MONTH is not None else months.min()
    expected = pd.period_range(expected_start, MAX_MONTH, freq="M")
    if months.duplicated().any() or not months.equals(expected):
        missing = expected.difference(months)
        raise RuntimeError(
            f"{symbol} {dataset} listing incomplete: "
            f"first={months.min()} last={months.max()} "
            f"missing={list(map(str, missing[:10]))}"
        )
    return archives


def download_all(archives: list[Archive], workers: int) -> dict[str, int]:
    counts = {"cached": 0, "downloaded": 0}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(vision.download_archive, archive): archive
            for archive in archives
        }
        for index, future in enumerate(as_completed(futures), start=1):
            counts[future.result()] += 1
            if index % 50 == 0 or index == len(archives):
                print(f"DOWNLOAD_PROGRESS {index}/{len(archives)}", flush=True)
    return counts


def list_daily_repairs(
    symbol: str,
    dataset: str,
    dates: list[str],
) -> list[Archive]:
    path_kind, interval, _ = DATASET_SPECS[dataset]
    if interval is None:
        raise RuntimeError(f"Daily repair is unsupported for {dataset}")
    archives: list[Archive] = []
    for date in dates:
        filename = f"{symbol}-{interval}-{date}.zip"
        key = (
            f"data/futures/um/daily/{path_kind}/{symbol}/{interval}/{filename}"
        )
        matches = [row for row in vision.s3_objects(key) if row["key"] == key]
        if len(matches) != 1:
            raise RuntimeError(
                f"{symbol} {dataset} missing daily repair archive for {date}"
            )
        item = matches[0]
        archives.append(
            Archive(
                asset=SYMBOL_META[symbol][0],
                symbol=symbol,
                dataset=f"{dataset}_daily_repair",
                month=date,
                key=key,
                etag=str(item["etag"]),
                size=int(item["size"]),
                last_modified=str(item["last_modified"]),
            )
        )
    return archives


def read_csv(archive: Archive) -> pd.DataFrame:
    payload = archive.raw_path.read_bytes()
    if len(payload) != archive.size or vision.md5_bytes(payload) != archive.etag:
        raise RuntimeError(f"{archive.raw_path} failed size/ETag recheck")
    with zipfile.ZipFile(io.BytesIO(payload)) as bundle:
        if bundle.testzip() is not None:
            raise RuntimeError(f"{archive.raw_path} failed ZIP CRC")
        members = [name for name in bundle.namelist() if name.endswith(".csv")]
        if len(members) != 1:
            raise RuntimeError(f"{archive.raw_path} has {len(members)} CSV members")
        frame = pd.read_csv(bundle.open(members[0]), header=None, low_memory=False)
    first = str(frame.iloc[0, 0]).strip()
    if not first.lstrip("-").isdigit():
        frame = frame.iloc[1:].reset_index(drop=True)
    return frame


def epoch_ms(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="raise").astype("int64")
    unit = "us" if int(numeric.abs().median()) >= 100_000_000_000_000 else "ms"
    timestamps = pd.to_datetime(numeric, unit=unit, utc=True)
    milliseconds = (
        pd.DatetimeIndex(timestamps)
        .to_numpy(dtype="datetime64[ns]")
        .astype("int64")
        // 1_000_000
    )
    return pd.Series(milliseconds, index=values.index)


def load_kline_like(
    symbol: str,
    archives: list[Archive],
    *,
    mark: bool,
) -> pd.DataFrame:
    columns = MARK_COLUMNS if mark else KLINE_COLUMNS
    parts: list[pd.DataFrame] = []
    for archive in archives:
        frame = read_csv(archive)
        if frame.shape[1] != len(columns):
            raise RuntimeError(
                f"{archive.raw_path} has {frame.shape[1]} columns, expected {len(columns)}"
            )
        frame.columns = columns
        frame["open_time_ms"] = epoch_ms(frame["open_time_ms"])
        frame["close_time_ms"] = epoch_ms(frame["close_time_ms"])
        parts.append(frame)
    output = pd.concat(parts, ignore_index=True)
    output = (
        output.sort_values("open_time_ms")
        .drop_duplicates("open_time_ms", keep="last")
        .reset_index(drop=True)
    )
    cutoff_ms = int(CUTOFF.timestamp() * 1000)
    output = output.loc[output["open_time_ms"].lt(cutoff_ms)].copy()
    output["open"] = pd.to_numeric(output["open"], errors="raise")
    output["high"] = pd.to_numeric(output["high"], errors="raise")
    output["low"] = pd.to_numeric(output["low"], errors="raise")
    output["close"] = pd.to_numeric(output["close"], errors="raise")
    if mark:
        output["observation_count"] = pd.to_numeric(
            output["observation_count"], errors="raise"
        ).astype("int64")
        output["ts"] = pd.to_datetime(output["open_time_ms"], unit="ms", utc=True)
        output["close_ts"] = pd.to_datetime(
            output["close_time_ms"], unit="ms", utc=True
        )
        output["exchange"] = "binance"
        output["market_type"] = "perp"
        output["symbol"] = SYMBOL_META[symbol][1]
        output["timeframe"] = "1h"
        output["source"] = base.MARK_SOURCE
        output["is_closed"] = output["close_time_ms"].lt(cutoff_ms)
        return output.loc[output["is_closed"]].reset_index(drop=True)
    for column in (
        "volume",
        "quote_volume",
        "trade_count",
        "taker_buy_volume",
        "taker_buy_quote_volume",
    ):
        output[column] = pd.to_numeric(output[column], errors="raise")
    output["trade_count"] = output["trade_count"].astype("int64")
    output["open_time"] = pd.to_datetime(
        output["open_time_ms"], unit="ms", utc=True
    )
    output["close_time"] = pd.to_datetime(
        output["close_time_ms"], unit="ms", utc=True
    )
    output["exchange"] = "binance"
    output["symbol"] = SYMBOL_META[symbol][1]
    output["market_type"] = "perp"
    output["timeframe"] = "1h"
    output["is_closed"] = output["close_time_ms"].lt(cutoff_ms)
    output["source"] = base.KLINE_SOURCE
    return output.loc[output["is_closed"]].reset_index(drop=True)


def load_funding(symbol: str, archives: list[Archive]) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for archive in archives:
        frame = read_csv(archive)
        if frame.shape[1] != 3:
            raise RuntimeError(
                f"{archive.raw_path} has {frame.shape[1]} funding columns"
            )
        frame.columns = ("calc_time", "funding_interval_hours", "last_funding_rate")
        frame["funding_time_ms"] = epoch_ms(frame["calc_time"])
        parts.append(frame)
    output = pd.concat(parts, ignore_index=True)
    cutoff_ms = int(CUTOFF.timestamp() * 1000)
    output = (
        output.loc[output["funding_time_ms"].lt(cutoff_ms)]
        .sort_values("funding_time_ms")
        .drop_duplicates("funding_time_ms", keep="last")
        .reset_index(drop=True)
    )
    output["ts"] = pd.to_datetime(
        output["funding_time_ms"], unit="ms", utc=True
    )
    output["funding_rate"] = pd.to_numeric(
        output["last_funding_rate"], errors="raise"
    )
    output["endpoint_mark_price"] = float("nan")
    output["exchange"] = "binance"
    output["symbol"] = SYMBOL_META[symbol][1]
    output["market_type"] = "perp"
    output["base_asset"] = SYMBOL_META[symbol][0]
    output["quote_asset"] = "USDT"
    output["source"] = base.FUNDING_SOURCE
    return output


def missing_hour_dates(frame: pd.DataFrame, timestamp_column: str) -> list[str]:
    timestamps = pd.DatetimeIndex(frame[timestamp_column])
    expected = pd.date_range(timestamps.min(), timestamps.max(), freq="1h")
    missing = expected.difference(timestamps)
    return sorted({str(ts.date()) for ts in missing})


def main() -> None:
    args = parse_args()
    symbols = list(dict.fromkeys(args.symbols))
    if any("HYPE" in symbol.upper() for symbol in symbols):
        raise RuntimeError("HYPE source request is forbidden")
    base.SYMBOLS = {symbol: SYMBOL_META[symbol] for symbol in symbols}
    base.FEATURE_DIR = FEATURE_DIR
    base.ARTIFACT_DIR = ARTIFACT_DIR
    base.SEALED_START = CUTOFF
    base.SEALED_END_EXCLUSIVE = CUTOFF
    base.KLINE_SOURCE = DATASET_SPECS["kline"][2]
    base.MARK_SOURCE = DATASET_SPECS["mark"][2]
    base.FUNDING_SOURCE = DATASET_SPECS["funding"][2]

    by_key: dict[tuple[str, str], list[Archive]] = {}
    all_archives: list[Archive] = []
    for symbol in symbols:
        for dataset in DATASET_SPECS:
            rows = list_archives(symbol, dataset)
            by_key[(symbol, dataset)] = rows
            all_archives.extend(rows)
    download_counts = download_all(all_archives, args.max_workers)

    cache: dict[tuple[str, str], pd.DataFrame] = {}
    for symbol in symbols:
        for dataset, is_mark, timestamp_column in (
            ("kline", False, "open_time"),
            ("mark", True, "ts"),
        ):
            frame = load_kline_like(
                symbol, by_key[(symbol, dataset)], mark=is_mark
            )
            missing_dates = missing_hour_dates(frame, timestamp_column)
            if missing_dates:
                repairs = list_daily_repairs(symbol, dataset, missing_dates)
                repair_counts = download_all(repairs, args.max_workers)
                for key, value in repair_counts.items():
                    download_counts[key] += value
                by_key[(symbol, dataset)].extend(repairs)
                all_archives.extend(repairs)
                frame = load_kline_like(
                    symbol, by_key[(symbol, dataset)], mark=is_mark
                )
                remaining = missing_hour_dates(frame, timestamp_column)
                if remaining:
                    raise RuntimeError(
                        f"{symbol} {dataset} still misses hourly dates: {remaining}"
                    )
            cache[(symbol, dataset)] = frame
        cache[(symbol, "funding")] = load_funding(
            symbol, by_key[(symbol, "funding")]
        )

    base.fetch_hourly = lambda symbol, **_: cache[(symbol, "kline")].copy()
    base.fetch_mark = lambda symbol, **_: cache[(symbol, "mark")].copy()
    base.fetch_funding = lambda symbol, **_: cache[(symbol, "funding")].copy()

    generated_at = datetime.now(UTC).isoformat()
    cutoff_ms = int(CUTOFF.timestamp() * 1000)
    layout = base.DataLakeLayout.from_settings(base.load_settings(None))
    layout.ensure_directories()
    results: dict[str, Any] = {}
    for symbol in symbols:
        first_ms = int(cache[(symbol, "kline")]["open_time_ms"].min())
        contract = {
            "symbol": symbol,
            "status": "archive_identity",
            "contract_type": "PERPETUAL",
            "quote_asset": "USDT",
            "margin_asset": "USDT",
            "onboard_date_ms": first_ms,
            "onboard_date": pd.to_datetime(first_ms, unit="ms", utc=True).isoformat(),
            "identity_source": "Binance Vision USD-M futures archive namespace",
        }
        results[symbol] = base.process_symbol(
            symbol,
            contract=contract,
            cutoff_ms=cutoff_ms,
            generated_at=generated_at,
            timeout=0.0,
            no_write=False,
            layout=layout,
        )

    manifest = {
        "generated_at_utc": generated_at,
        "family": "BIN-1D-MA7-QUML",
        "purpose": "P0 official-archive fallback after explicit FAPI IP ban",
        "cutoff_exclusive": CUTOFF.isoformat(),
        "symbols": symbols,
        "source": "https://data.binance.vision/data/futures/um/monthly/",
        "download_counts": download_counts,
        "archive_count": len(all_archives),
        "archive_bytes": int(sum(row.size for row in all_archives)),
        "archives": [
            {
                **asdict(row),
                "raw_path": str(row.raw_path.relative_to(ROOT)),
                "sha256": vision.sha256_path(row.raw_path),
            }
            for row in all_archives
        ],
        "results": results,
        "hype_requests": 0,
        "hype_rows": 0,
        "hype_features": 0,
        "blocker_count": int(
            sum(
                row["hourly_quality"]["blocker_count"]
                + int(not row["daily_quality"]["audit"]["trusted"])
                + row["funding_quality"]["blocker_count"]
                + row["mark_quality"]["blocker_count"]
                for row in results.values()
            )
        ),
    }
    if manifest["blocker_count"]:
        raise RuntimeError(f"Vision fallback blockers remain: {manifest['blocker_count']}")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_DIR / "p0_vision_fallback_manifest.json"
    base.atomic_write_path(
        path,
        lambda temporary: temporary.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        ),
    )
    print(
        json.dumps(
            {
                "artifact": str(path.relative_to(ROOT)),
                "symbols": symbols,
                "archive_count": len(all_archives),
                "blocker_count": manifest["blocker_count"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
