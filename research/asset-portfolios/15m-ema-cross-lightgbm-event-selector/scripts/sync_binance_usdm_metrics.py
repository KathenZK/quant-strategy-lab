"""Sync Binance Vision USDM daily metrics (OI / long-short ratios) to the lake.

Scoped explore-grade ingestion for the A-family supplement
(specs/bin-15m-emax-af-feature-supplement-contract-2026-07-29.md): downloads
the manifest produced by inventory_binance_usdm_metrics.py, parses the 5m
metrics rows, and writes per symbol-month parquet under
data/normalized/derivatives_metrics/. Raw values are preserved; quality
counters land in a sync report next to the manifest.
"""

from __future__ import annotations

import csv
import io
import json
import time
import urllib.request
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

import emax_common as ec

S3_DL = "https://data.binance.vision"
MANIFEST = ec.ARTIFACT_DIR / "af_supplement" / "metrics_inventory.csv"
LAKE_ROOT = (
    ec.ROOT
    / "data/normalized/derivatives_metrics/exchange=binance/market_type=perp"
    / "timeframe=5m/source=binance_vision_daily"
)
STATE_DIR = ec.ARTIFACT_DIR / "af_supplement" / "metrics_sync_state"
REPORT = ec.ARTIFACT_DIR / "af_supplement" / "metrics_sync_report.json"

NUM_COLS = [
    "sum_open_interest",
    "sum_open_interest_value",
    "count_toptrader_long_short_ratio",
    "sum_toptrader_long_short_ratio",
    "count_long_short_ratio",
    "sum_taker_long_short_vol_ratio",
]


def _to_float(value: str | None) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def fetch_day(symbol: str, date: str) -> list[tuple] | None:
    """Return compact (create_time, *NUM_COLS) tuples to keep memory bounded."""
    url = f"{S3_DL}/data/futures/um/daily/metrics/{symbol}/{symbol}-metrics-{date}.zip"
    for attempt in range(4):
        try:
            payload = urllib.request.urlopen(url, timeout=60).read()
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                with archive.open(archive.namelist()[0]) as fh:
                    reader = csv.reader(io.TextIOWrapper(fh, encoding="utf-8"))
                    header = next(reader, None)
                    if header is None:
                        return []
                    pos = {name: idx for idx, name in enumerate(header)}
                    time_idx = pos.get("create_time")
                    col_idx = [pos.get(col) for col in NUM_COLS]
                    if time_idx is None:
                        return []
                    return [
                        (
                            row[time_idx],
                            *(
                                _to_float(row[idx]) if idx is not None and idx < len(row) else float("nan")
                                for idx in col_idx
                            ),
                        )
                        for row in reader
                    ]
        except Exception:
            if attempt == 3:
                return None
            time.sleep(1.5 * (attempt + 1))
    return None


def process_symbol(symbol: str, dates: list[str]) -> dict:
    marker = STATE_DIR / f"{symbol}.done"
    if marker.exists():
        return {"symbol": symbol, "skipped": True}
    rows: list[tuple] = []
    failed: list[str] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fetch_day, symbol, date): date for date in dates}
        for future in as_completed(futures):
            result = future.result()
            if result is None:
                failed.append(futures[future])
            else:
                rows.extend(result)
    if not rows:
        marker.write_text(json.dumps({"files": 0, "failed": failed}))
        return {"symbol": symbol, "rows": 0, "failed": len(failed)}

    frame = pd.DataFrame(rows, columns=["create_time", *NUM_COLS])
    frame["ts"] = pd.to_datetime(frame["create_time"], utc=True, format="mixed")
    frame["symbol"] = symbol
    frame = (
        frame[["ts", "symbol", *NUM_COLS]]
        .sort_values("ts")
        .drop_duplicates(subset=["ts"], keep="last")
    )
    null_counts = {col: int(frame[col].isna().sum()) for col in NUM_COLS}

    for month, chunk in frame.groupby(frame["ts"].dt.strftime("%Y-%m")):
        out_dir = LAKE_ROOT / f"month={month}"
        out_dir.mkdir(parents=True, exist_ok=True)
        chunk.to_parquet(out_dir / f"{symbol}.parquet", index=False, compression="zstd")

    marker.write_text(json.dumps({"files": len(dates) - len(failed), "failed": failed}))
    return {
        "symbol": symbol,
        "rows": len(frame),
        "failed": len(failed),
        "nulls": null_counts,
    }


def main() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    by_symbol: dict[str, list[str]] = defaultdict(list)
    with MANIFEST.open() as fh:
        for record in csv.DictReader(fh):
            by_symbol[record["symbol"]].append(record["date"])

    totals = {"symbols": 0, "rows": 0, "failed_files": 0, "skipped": 0}
    null_totals: dict[str, int] = defaultdict(int)
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {
            pool.submit(process_symbol, sym, dates): sym for sym, dates in by_symbol.items()
        }
        for done, future in enumerate(as_completed(futures), start=1):
            result = future.result()
            if result.get("skipped"):
                totals["skipped"] += 1
            else:
                totals["symbols"] += 1
                totals["rows"] += result.get("rows", 0)
                totals["failed_files"] += result.get("failed", 0)
                for col, count in (result.get("nulls") or {}).items():
                    null_totals[col] += count
            if done % 25 == 0 or done == len(futures):
                print(
                    f"sync {done}/{len(futures)} symbols "
                    f"({totals['rows']} rows, {totals['failed_files']} failed files, "
                    f"{time.monotonic() - started:.0f}s)",
                    flush=True,
                )

    report = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "manifest": str(MANIFEST.relative_to(ec.ROOT)),
        "lake_root": str(LAKE_ROOT.relative_to(ec.ROOT)),
        "grade": "explore / untrusted until full lake audit",
        **totals,
        "null_totals": dict(null_totals),
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print("SYNC COMPLETE")


if __name__ == "__main__":
    main()
