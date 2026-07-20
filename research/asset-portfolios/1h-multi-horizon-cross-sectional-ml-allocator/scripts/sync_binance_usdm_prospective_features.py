from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / (
    "research/asset-portfolios/1h-multi-horizon-cross-sectional-ml-allocator"
)
SCRIPT_DIR = FAMILY_DIR / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import sync_binance_usdm_freeze_gap as base  # noqa: E402


OOS_START = pd.Timestamp("2026-07-19T00:00:00Z")
OOS_END = pd.Timestamp("2026-10-19T00:00:00Z")
OUTCOME_DATA_END = pd.Timestamp("2026-10-20T22:00:00Z")
WARMUP_START = pd.Timestamp("2026-07-01T00:00:00Z")
ROLLING_FETCH = pd.Timedelta(days=45)
OUTPUT_DIR = FAMILY_DIR / "artifacts/prospective_oos/data"
MANIFEST_PATH = OUTPUT_DIR / "latest_data_manifest.json"
SOURCE_PARTITION = "source=binance_fapi_prospective_oos"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync feature inputs only for the frozen prospective OOS runner."
    )
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--attempts", type=int, default=7)
    parser.add_argument("--symbols", nargs="*")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def closed_end() -> pd.Timestamp:
    return min(pd.Timestamp.now("UTC").floor("h"), OUTCOME_DATA_END)


def fetch_symbol(
    symbol: str,
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
    timeout: float,
    attempts: int,
) -> dict[str, Any]:
    common = {
        "symbol": symbol,
        "startTime": int(start.timestamp() * 1000),
        "endTime": int(end.timestamp() * 1000) - 1,
        "limit": 1500,
    }
    kline = base.request_json(
        "/fapi/v1/klines",
        {**common, "interval": "1h"},
        timeout=timeout,
        attempts=attempts,
    )
    mark = base.request_json(
        "/fapi/v1/markPriceKlines",
        {**common, "interval": "1h"},
        timeout=timeout,
        attempts=attempts,
    )
    if not isinstance(kline, list) or not isinstance(mark, list):
        raise RuntimeError(f"unexpected kline payload for {symbol}")
    if len(kline) >= 1500 or len(mark) >= 1500:
        raise RuntimeError(f"rolling fetch unexpectedly reached API limit for {symbol}")
    return {"symbol": symbol, "kline_1h": kline, "mark_1h": mark}


def atomic_parquet(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    frame.to_parquet(temporary, index=False, compression="zstd")
    os.replace(temporary, path)


def other_normalized_keys(
    root: Path, *, target: Path, start: pd.Timestamp, end: pd.Timestamp
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in root.glob("**/*.parquet"):
        if path == target:
            continue
        try:
            frame = pd.read_parquet(path, columns=["ts", "symbol"])
        except Exception:
            continue
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
        frame = frame.loc[frame["ts"].ge(start) & frame["ts"].lt(end)]
        if not frame.empty:
            frames.append(frame)
    if not frames:
        return pd.DataFrame(columns=["ts", "symbol"])
    return pd.concat(frames, ignore_index=True).drop_duplicates(["ts", "symbol"])


def persist_normalized(name: str, frame: pd.DataFrame) -> list[dict[str, Any]]:
    root = Path(base.DATASETS[name]["normalized_root"])
    records: list[dict[str, Any]] = []
    frame = frame.copy()
    frame["month"] = frame["ts"].dt.strftime("%Y-%m")
    for month, part in frame.groupby("month", sort=True):
        part = part.drop(columns="month")
        target = root / SOURCE_PARTITION / f"month={month}" / "part.parquet"
        if target.exists():
            previous = pd.read_parquet(target)
            previous["ts"] = pd.to_datetime(previous["ts"], utc=True)
            part = pd.concat([previous, part], ignore_index=True)
        part = part.sort_values(["ts", "symbol"]).drop_duplicates(
            ["ts", "symbol"], keep="last"
        )
        month_start = pd.Timestamp(f"{month}-01", tz="UTC")
        month_end = month_start + pd.offsets.MonthBegin(1)
        overlaps = other_normalized_keys(
            root, target=target, start=month_start, end=month_end
        )
        excluded = 0
        if not overlaps.empty:
            marked = part.merge(
                overlaps.assign(_other=True), on=["ts", "symbol"], how="left"
            )
            excluded = int(marked["_other"].fillna(False).sum())
            part = marked.loc[marked["_other"].isna()].drop(columns="_other")
        atomic_parquet(part, target)
        records.append(
            {
                "path": str(target.relative_to(ROOT)),
                "sha256": sha256(target),
                "rows": len(part),
                "other_source_keys_excluded": excluded,
                "duplicate_keys": int(part.duplicated(["ts", "symbol"]).sum()),
                "first_ts": part["ts"].min().isoformat() if len(part) else None,
                "last_ts": part["ts"].max().isoformat() if len(part) else None,
            }
        )
    return records


def persist_raw(name: str, frame: pd.DataFrame) -> list[dict[str, Any]]:
    root = Path(base.DATASETS[name]["raw_root"])
    value = frame.copy()
    time_column = "fundingTime" if name == "funding" else "open_time"
    value["_ts"] = pd.to_datetime(value[time_column], unit="ms", utc=True)
    value["_month"] = value["_ts"].dt.strftime("%Y-%m")
    keys = ["api_symbol", time_column]
    records: list[dict[str, Any]] = []
    for month, part in value.groupby("_month", sort=True):
        part = part.drop(columns=["_ts", "_month"])
        target = root / SOURCE_PARTITION / f"month={month}" / "part.parquet"
        if target.exists():
            part = pd.concat([pd.read_parquet(target), part], ignore_index=True)
        part = part.sort_values(keys).drop_duplicates(keys, keep="last")
        atomic_parquet(part, target)
        records.append(
            {
                "path": str(target.relative_to(ROOT)),
                "sha256": sha256(target),
                "rows": len(part),
                "duplicate_keys": int(part.duplicated(keys).sum()),
            }
        )
    return records


def main() -> None:
    args = parse_args()
    end = closed_end()
    if end <= WARMUP_START:
        raise RuntimeError("no closed feature bars are available")
    start = max(WARMUP_START, end - ROLLING_FETCH)
    exchange_info = base.request_json(
        "/fapi/v1/exchangeInfo", None, timeout=args.timeout, attempts=args.attempts
    )
    symbols = base.current_symbols(exchange_info)
    if args.symbols:
        requested = {value.upper() for value in args.symbols}
        unknown = sorted(requested - set(symbols))
        if unknown:
            raise RuntimeError(f"unknown current symbols: {unknown}")
        symbols = [value for value in symbols if value in requested]
    results: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                fetch_symbol,
                symbol,
                start=start,
                end=end,
                timeout=args.timeout,
                attempts=args.attempts,
            ): symbol
            for symbol in symbols
        }
        for index, future in enumerate(as_completed(futures), start=1):
            symbol = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:  # noqa: BLE001
                failures.append({"symbol": symbol, "error": repr(exc)})
            if index % 50 == 0 or index == len(futures):
                print(
                    f"prospective_features {index}/{len(futures)} "
                    f"failures={len(failures)}",
                    flush=True,
                )
    if failures:
        raise RuntimeError(f"prospective feature fetch failures: {failures[:10]}")
    funding_rows = base.fetch_funding_bulk(
        end=end, timeout=args.timeout, attempts=args.attempts
    )
    funding_rows = [
        row for row in funding_rows
        if int(row["fundingTime"]) >= int(start.timestamp() * 1000)
    ]
    raw_kline, kline = base.parse_kline(results, mark_price=False)
    raw_mark, mark = base.parse_kline(results, mark_price=True)
    raw_funding, funding = base.parse_funding(funding_rows)
    kline["source"] = "binance_fapi_kline_prospective_oos"
    mark["source"] = "binance_fapi_mark_price_kline_prospective_oos"
    funding["source"] = "binance_fapi_funding_prospective_oos"
    expected_last = end - pd.Timedelta(hours=1)
    kline_last = kline.groupby("symbol")["ts"].max()
    mark_last = mark.groupby("symbol")["ts"].max()
    stale_kline = sorted(kline_last.index[kline_last.ne(expected_last)].tolist())
    stale_mark = sorted(mark_last.index[mark_last.ne(expected_last)].tolist())
    missing_kline = sorted(set(symbols) - set(raw_kline["api_symbol"]))
    missing_mark = sorted(set(symbols) - set(raw_mark["api_symbol"]))
    blockers: list[str] = []
    if stale_kline or stale_mark or missing_kline or missing_mark:
        blockers.append("current_symbol_closed_bar_coverage_incomplete")
    datasets = {}
    for name, raw, normalized in (
        ("kline_1h", raw_kline, kline),
        ("mark_1h", raw_mark, mark),
        ("funding", raw_funding, funding),
    ):
        datasets[name] = {
            "raw": persist_raw(name, raw),
            "normalized": persist_normalized(name, normalized),
        }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    exchange_path = OUTPUT_DIR / "latest_exchange_info.json"
    exchange_path.write_text(
        json.dumps(exchange_info, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    manifest = {
        "family": "Binance-1H-Multi-Horizon-Cross-Sectional-ML-Allocator",
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "status": "PASS" if not blockers else "BLOCKED",
        "role": "prospective OOS feature-input sync; no labels or outcomes",
        "fetch_start": start.isoformat(),
        "closed_end_exclusive": end.isoformat(),
        "oos_start": OOS_START.isoformat(),
        "oos_end_exclusive": OOS_END.isoformat(),
        "outcome_data_end_exclusive": OUTCOME_DATA_END.isoformat(),
        "symbols_requested": len(symbols),
        "symbols_succeeded": len(results),
        "stale_kline_symbols": stale_kline,
        "stale_mark_symbols": stale_mark,
        "missing_kline_symbols": missing_kline,
        "missing_mark_symbols": missing_mark,
        "exchange_info_path": str(exchange_path.relative_to(ROOT)),
        "exchange_info_sha256": sha256(exchange_path),
        "datasets": datasets,
        "prospective_oos_outcomes_read": False,
        "blockers": blockers,
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    if blockers:
        raise RuntimeError(f"prospective feature sync blocked: {blockers}")


if __name__ == "__main__":
    main()
