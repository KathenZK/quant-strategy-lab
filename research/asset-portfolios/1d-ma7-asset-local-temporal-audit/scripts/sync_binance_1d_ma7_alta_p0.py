from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-ma7-asset-local-temporal-audit"
ARTIFACT_DIR = FAMILY_DIR / "artifacts/p0_data_2026-08-10"
FEATURE_DIR = ROOT / "data/features/binance_1d_ma7_alta_p0"
RAW_ROOT = ROOT / (
    "data/raw/alta_price_funding/exchange=binance/market_type=perp/"
    "source=binance_vision"
)
T0 = pd.Timestamp("2025-05-31T00:00:00Z")
T1 = pd.Timestamp("2026-08-01T00:00:00Z")
ASSETS = {
    "BTC": "btcusdt",
    "ETH": "ethusdt",
    "BNB": "bnbusdt",
    "SOL": "solusdt",
    "TRX": "trxusdt",
    "XRP": "xrpusdt",
    "DOGE": "dogeusdt",
    "ADA": "adausdt",
    "LINK": "linkusdt",
    "LTC": "ltcusdt",
    "DOT": "dotusdt",
    "AVAX": "avaxusdt",
    "UNI": "uniusdt",
    "BCH": "bchusdt",
    "ETC": "etcusdt",
    "XLM": "xlmusdt",
    "ATOM": "atomusdt",
    "VET": "vetusdt",
    "NEAR": "nearusdt",
    "AAVE": "aaveusdt",
    "FIL": "filusdt",
}
ORIGINAL_ASSETS = {"BTC", "ETH", "BNB", "SOL", "TRX"}
TFML_ASSETS = {"XRP", "DOGE", "ADA", "LINK", "LTC", "DOT", "AVAX", "UNI"}
BASELINE_DIRS = {
    "original": ROOT / "data/features/binance_1d_ma7_rsi6_dapml_p0",
    "tfml": ROOT / "data/features/binance_1d_ma7_tfml_p0e",
    "quml": ROOT / "data/features/binance_1d_ma7_quml_p0",
}


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


transport = load_module(
    "binance_1d_ma7_alta_vision_transport",
    ROOT
    / (
        "research/asset-portfolios/1d-ma7-quantile-utility-meta-label/"
        "scripts/sync_binance_quml_p0_vision_fallback.py"
    ),
)
base = transport.base


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-workers", type=int, default=12)
    parser.add_argument(
        "--symbols",
        nargs="+",
        choices=sorted(f"{asset}USDT" for asset in ASSETS),
        default=[f"{asset}USDT" for asset in ASSETS],
    )
    return parser.parse_args()


def baseline_dir(asset: str) -> Path:
    if asset in ORIGINAL_ASSETS:
        return BASELINE_DIRS["original"]
    if asset in TFML_ASSETS:
        return BASELINE_DIRS["tfml"]
    return BASELINE_DIRS["quml"]


def feature_paths(directory: Path, slug: str) -> dict[str, Path]:
    return {
        "hourly": directory / f"{slug}_perp_1h.parquet",
        "daily": directory / f"{slug}_perp_1d.parquet",
        "funding": directory / f"{slug}_perp_funding_mark.parquet",
    }


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, (pd.Timestamp, datetime)):
        return pd.Timestamp(value).isoformat()
    return value


def read_baseline(asset: str) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    slug = ASSETS[asset]
    paths = feature_paths(baseline_dir(asset), slug)
    missing = [path for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(missing)
    frames = {key: pd.read_parquet(path) for key, path in paths.items()}
    for frame in frames.values():
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frames["hourly"] = frames["hourly"].loc[
        frames["hourly"]["ts"].lt(T0)
    ].copy()
    frames["daily"] = frames["daily"].loc[frames["daily"]["ts"].lt(T0)].copy()
    frames["funding"] = frames["funding"].loc[
        frames["funding"]["ts"].lt(T0)
    ].copy()
    identity = {
        key: {
            "path": str(paths[key].relative_to(ROOT)),
            "sha256": sha256_path(paths[key]),
            "rows_before_t0": int(len(frames[key])),
            "end_before_t0": frames[key]["ts"].max(),
        }
        for key in paths
    }
    return frames, identity


def configure_transport(symbol_meta: dict[str, tuple[str, str, str]]) -> None:
    transport.CUTOFF = T1
    transport.MIN_MONTH = pd.Period("2025-05", freq="M")
    transport.MAX_MONTH = pd.Period("2026-07", freq="M")
    transport.RAW_ROOT = RAW_ROOT
    transport.SYMBOL_META = symbol_meta
    base.SYMBOLS = symbol_meta
    base.KLINE_SOURCE = "binance_vision_monthly_klines"
    base.MARK_SOURCE = "binance_vision_monthly_mark_klines"
    base.FUNDING_SOURCE = "binance_vision_monthly_funding_rate"


def ensure_hourly_repairs(
    symbol: str,
    dataset: str,
    archives: list[Any],
    *,
    mark: bool,
    workers: int,
) -> tuple[pd.DataFrame, list[Any], dict[str, int]]:
    timestamp_column = "ts" if mark else "open_time"
    frame = transport.load_kline_like(symbol, archives, mark=mark)
    missing_dates = transport.missing_hour_dates(frame, timestamp_column)
    repairs: list[Any] = []
    counts = {"cached": 0, "downloaded": 0}
    if missing_dates:
        repairs = transport.list_daily_repairs(symbol, dataset, missing_dates)
        counts = transport.download_all(repairs, workers)
        archives = [*archives, *repairs]
        frame = transport.load_kline_like(symbol, archives, mark=mark)
    remaining = transport.missing_hour_dates(frame, timestamp_column)
    if remaining:
        raise RuntimeError(f"{symbol} {dataset} missing dates after repair: {remaining}")
    return frame, repairs, counts


def combine_and_audit(
    asset: str,
    symbol: str,
    baseline: dict[str, pd.DataFrame],
    *,
    raw_hourly: pd.DataFrame,
    raw_mark: pd.DataFrame,
    raw_funding: pd.DataFrame,
    generated_at: str,
) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    post_raw_hourly = raw_hourly.loc[raw_hourly["open_time"].ge(T0)].copy()
    post_hourly = base.normalize_hourly(
        symbol, post_raw_hourly, generated_at=generated_at
    )
    post_hourly_quality = base.audit_hourly(
        symbol, post_raw_hourly, post_hourly
    )
    post_daily, post_daily_quality = base.aggregate_daily(
        symbol, post_hourly, generated_at=generated_at
    )
    mark_quality = base.audit_mark(symbol, raw_mark)
    resolved_funding, funding_quality = base.resolve_funding(
        symbol,
        raw_funding,
        raw_mark,
        generated_at=generated_at,
    )
    post_funding = resolved_funding.loc[
        resolved_funding["ts"].ge(T0) & resolved_funding["ts"].lt(T1)
    ].copy()

    combined = {
        "hourly": pd.concat(
            [baseline["hourly"], post_hourly], ignore_index=True
        ),
        "daily": pd.concat([baseline["daily"], post_daily], ignore_index=True),
        "funding": pd.concat(
            [baseline["funding"], post_funding], ignore_index=True
        ),
    }
    for key, frame in combined.items():
        frame.sort_values("ts", inplace=True)
        frame.drop_duplicates("ts", keep="last", inplace=True)
        frame.reset_index(drop=True, inplace=True)
        if frame["ts"].max() >= T1:
            raise RuntimeError(f"{asset} {key} crosses T1")

    post_ts = pd.DatetimeIndex(
        combined["hourly"].loc[combined["hourly"]["ts"].ge(T0), "ts"]
    )
    expected = pd.date_range(T0, T1 - pd.Timedelta(hours=1), freq="1h")
    missing = expected.difference(post_ts)
    extras = post_ts.difference(expected)
    if len(missing) or len(extras) or post_ts.duplicated().any():
        raise RuntimeError(
            f"{asset} post hourly grid failed: "
            f"missing={len(missing)} extras={len(extras)}"
        )
    nominal = pd.to_datetime(
        combined["funding"].get(
            "funding_nominal_ts", combined["funding"]["ts"]
        ),
        utc=True,
    )
    funding_gaps = (
        pd.Series(pd.DatetimeIndex(nominal))
        .diff()
        .dt.total_seconds()
        .div(3600.0)
    )
    invalid_funding = funding_gaps.dropna().loc[
        funding_gaps.dropna().le(0.0)
        | funding_gaps.dropna().gt(8.0)
        | funding_gaps.dropna().mod(1.0).ne(0.0)
    ]
    if len(invalid_funding):
        raise RuntimeError(f"{asset} has {len(invalid_funding)} funding gaps")
    quality = {
        "post_hourly": post_hourly_quality,
        "post_daily": post_daily_quality,
        "post_mark": mark_quality,
        "post_funding": funding_quality,
        "post_rows": {
            "hourly": int(len(post_hourly)),
            "daily": int(len(post_daily)),
            "funding": int(len(post_funding)),
        },
        "combined_rows": {
            key: int(len(frame)) for key, frame in combined.items()
        },
        "post_hourly_missing": int(len(missing)),
        "post_hourly_extras": int(len(extras)),
        "max_funding_gap_hours": float(funding_gaps.max()),
        "blocker_count": 0,
    }
    return combined, quality


def main() -> None:
    args = parse_args()
    symbols = list(dict.fromkeys(args.symbols))
    if any("HYPE" in symbol.upper() for symbol in symbols):
        raise RuntimeError("HYPE source is forbidden")
    selected_assets = [symbol.removesuffix("USDT") for symbol in symbols]
    baselines: dict[str, dict[str, pd.DataFrame]] = {}
    baseline_identity: dict[str, Any] = {}
    symbol_meta: dict[str, tuple[str, str, str]] = {}
    for asset in selected_assets:
        baseline, identity = read_baseline(asset)
        baselines[asset] = baseline
        baseline_identity[asset] = identity
        displays = baseline["hourly"]["symbol"].dropna().astype(str).unique()
        if len(displays) != 1:
            raise RuntimeError(f"{asset} baseline display identity is ambiguous")
        symbol_meta[f"{asset}USDT"] = (asset, str(displays[0]), ASSETS[asset])
    configure_transport(symbol_meta)

    by_key: dict[tuple[str, str], list[Any]] = {}
    archives: list[Any] = []
    for symbol in symbols:
        for dataset in transport.DATASET_SPECS:
            rows = transport.list_archives(symbol, dataset)
            by_key[(symbol, dataset)] = rows
            archives.extend(rows)
    download_counts = transport.download_all(archives, args.max_workers)

    raw_cache: dict[tuple[str, str], pd.DataFrame] = {}
    repair_archives: list[Any] = []
    for symbol in symbols:
        for dataset, mark in (("kline", False), ("mark", True)):
            frame, repairs, repair_counts = ensure_hourly_repairs(
                symbol,
                dataset,
                by_key[(symbol, dataset)],
                mark=mark,
                workers=args.max_workers,
            )
            raw_cache[(symbol, dataset)] = frame
            repair_archives.extend(repairs)
            for key, value in repair_counts.items():
                download_counts[key] += value
        raw_cache[(symbol, "funding")] = transport.load_funding(
            symbol, by_key[(symbol, "funding")]
        )
    archives.extend(repair_archives)

    generated_at = datetime.now(UTC).isoformat()
    FEATURE_DIR.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {}
    for asset in selected_assets:
        symbol = f"{asset}USDT"
        combined, quality = combine_and_audit(
            asset,
            symbol,
            baselines[asset],
            raw_hourly=raw_cache[(symbol, "kline")],
            raw_mark=raw_cache[(symbol, "mark")],
            raw_funding=raw_cache[(symbol, "funding")],
            generated_at=generated_at,
        )
        paths = feature_paths(FEATURE_DIR, ASSETS[asset])
        for key, frame in combined.items():
            base.write_feature(frame, paths[key])
        results[asset] = {
            "quality": quality,
            "feature_identity": {
                key: {
                    "path": str(path.relative_to(ROOT)),
                    "sha256": sha256_path(path),
                    "rows": int(len(combined[key])),
                    "start": combined[key]["ts"].min(),
                    "end": combined[key]["ts"].max(),
                }
                for key, path in paths.items()
            },
        }
        print(
            f"[{asset}] accepted post rows "
            f"{quality['post_rows']['hourly']}/"
            f"{quality['post_rows']['daily']}/"
            f"{quality['post_rows']['funding']}",
            flush=True,
        )

    manifest = {
        "schema_version": "binance-1d-ma7-alta-p0-data-v1",
        "generated_at_utc": generated_at,
        "family": "BIN-1D-MA7-ALTA",
        "contract": "specs/binance-1d-ma7-alta-p0-p1-contract-2026-08-10.md",
        "t0": T0,
        "t1_exclusive": T1,
        "symbols": symbols,
        "baseline_identity": baseline_identity,
        "download_counts": download_counts,
        "archive_count": len(archives),
        "archive_bytes": int(sum(row.size for row in archives)),
        "archives": [
            {
                "symbol": row.symbol,
                "dataset": row.dataset,
                "period": row.month,
                "key": row.key,
                "size": row.size,
                "etag": row.etag,
                "last_modified": row.last_modified,
                "raw_path": str(row.raw_path.relative_to(ROOT)),
                "sha256": transport.vision.sha256_path(row.raw_path),
            }
            for row in archives
        ],
        "results": results,
        "blocker_count": 0,
        "hype_requests": 0,
        "hype_files": 0,
        "hype_rows": 0,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    artifact = ARTIFACT_DIR / "p0_data_quality_manifest.json"
    artifact.write_text(
        json.dumps(json_ready(manifest), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "artifact": str(artifact.relative_to(ROOT)),
                "archive_count": len(archives),
                "symbols": len(symbols),
                "blocker_count": 0,
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
