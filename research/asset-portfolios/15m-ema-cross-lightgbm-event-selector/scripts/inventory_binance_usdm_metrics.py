"""Inventory Binance Vision USDM daily metrics archives for pool symbols.

Sizing pass for the A-family supplement
(specs/bin-15m-emax-af-feature-supplement-contract-2026-07-29.md): lists the
S3 keys for every trading-pool symbol, counts files and bytes with entry date
<= 2025-12-31, and writes a CSV manifest for the sync script.
"""

from __future__ import annotations

import csv
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from xml.etree import ElementTree

import pandas as pd

import emax_common as ec

S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"
MAX_DATE = "2025-12-31"
OUT_CSV = ec.ARTIFACT_DIR / "af_supplement" / "metrics_inventory.csv"


def list_symbol(symbol: str) -> list[tuple[str, str, int]]:
    rows: list[tuple[str, str, int]] = []
    marker = ""
    pattern = re.compile(rf"{symbol}-metrics-(\d{{4}}-\d{{2}}-\d{{2}})\.zip$")
    while True:
        url = (
            f"{S3}?prefix=data/futures/um/daily/metrics/{symbol}/&max-keys=1000"
            + (f"&marker={marker}" if marker else "")
        )
        for attempt in range(4):
            try:
                body = urllib.request.urlopen(url, timeout=60).read()
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(2.0 * (attempt + 1))
        tree = ElementTree.fromstring(body)
        last_key = None
        for item in tree.iter(f"{NS}Contents"):
            key = item.find(f"{NS}Key").text
            last_key = key
            size = int(item.find(f"{NS}Size").text)
            match = pattern.search(key)
            if match and match.group(1) <= MAX_DATE:
                rows.append((symbol, match.group(1), size))
        if tree.find(f"{NS}IsTruncated").text != "true" or last_key is None:
            break
        marker = last_key
    return rows


def main() -> None:
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    events = pd.read_parquet(
        ec.ARTIFACT_DIR / "events_dev.parquet", columns=["sym_key", "in_trading_pool"]
    )
    sym_keys = sorted(events.loc[events["in_trading_pool"], "sym_key"].unique())
    symbols = [key + "USDT" for key in sym_keys]
    print(f"listing metrics archives for {len(symbols)} symbols...", flush=True)

    all_rows: list[tuple[str, str, int]] = []
    empty: list[str] = []
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = {pool.submit(list_symbol, sym): sym for sym in symbols}
        for done, future in enumerate(as_completed(futures), start=1):
            rows = future.result()
            if rows:
                all_rows.extend(rows)
            else:
                empty.append(futures[future])
            if done % 100 == 0 or done == len(futures):
                print(f"listed {done}/{len(symbols)} ({time.monotonic() - started:.0f}s)", flush=True)

    with OUT_CSV.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["symbol", "date", "size_bytes"])
        writer.writerows(sorted(all_rows))

    total_bytes = sum(size for _, _, size in all_rows)
    dates = [d for _, d, _ in all_rows]
    print(f"files: {len(all_rows)}, total: {total_bytes / 1e9:.2f} GB")
    print(f"date range: {min(dates)} .. {max(dates)}")
    print(f"symbols with no metrics: {len(empty)} -> {empty[:20]}")
    print(f"manifest -> {OUT_CSV}")


if __name__ == "__main__":
    main()
