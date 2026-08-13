"""Extend the HYPEUSDT 1h + funding lake for V1 prospective observation.

Fetches Binance USD-M fapi klines and funding events from the current lake
end to the latest fully closed hour, writes them into the standard lake
layout (raw + normalized partitions, normalized funding parquet) with the
exact schemas already in use, then re-runs the shared-kernel zero-blocker
audits (multi-horizon-ema-forecast v1 engine) to prove the extended lake
is clean. Idempotent: re-running only appends missing bars.

Evidence JSON goes to the family artifacts directory.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
ENGINE_PATH = ROOT / "research/_shared-kernels/multi-horizon-ema-forecast/v1/engine.py"
ENGINE_SHA256 = "63d754088ac55b958b5a5536d4ae8f5049d6b6c9c48a0fca7dc89c770d6e31c4"

SYMBOL = "HYPEUSDT"
KLINE_URL = "https://fapi.binance.com/fapi/v1/klines"
FUNDING_URL = "https://fapi.binance.com/fapi/v1/fundingRate"
KLINE_SOURCE = "binance_futures_kline_api"
FUNDING_SOURCE = "binance_futures_funding_rate_api"

OHLCV_RAW = ROOT / "data/raw/ohlcv/exchange=binance/market_type=perp/timeframe=1h"
OHLCV_NORM = ROOT / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=1h"
FUNDING_NORM = (
    ROOT
    / "data/normalized/funding/exchange=binance/market_type=perp"
    / "symbol=hype_usdt_usdt/funding.parquet"
)
PARTITION_NAME = "symbol=hype_usdt_usdt.parquet"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    return parser.parse_args()


def load_engine() -> Any:
    digest = hashlib.sha256(ENGINE_PATH.read_bytes()).hexdigest()
    if digest != ENGINE_SHA256:
        raise RuntimeError(f"shared kernel SHA mismatch: {digest}")
    spec = importlib.util.spec_from_file_location("sync_market_audit", ENGINE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import shared kernel: {ENGINE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def http_get_json(url: str, params: dict[str, Any]) -> Any:
    query = "&".join(f"{k}={v}" for k, v in params.items())
    full = f"{url}?{query}"
    last: Exception | None = None
    for attempt in range(4):
        if attempt:
            time.sleep(3.0 * attempt)
        try:
            completed = subprocess.run(
                [
                    "curl", "--fail", "--location", "--silent", "--show-error",
                    "--max-time", "30", full,
                ],
                check=True,
                capture_output=True,
            )
            return json.loads(completed.stdout)
        except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            last = exc
    raise RuntimeError(f"fetch failed: {full}: {last}")


def fetch_klines(start_ms: int, end_ms: int) -> list[list[Any]]:
    rows: list[list[Any]] = []
    cursor = start_ms
    while cursor < end_ms:
        batch = http_get_json(
            KLINE_URL,
            {
                "symbol": SYMBOL,
                "interval": "1h",
                "startTime": cursor,
                "endTime": end_ms,
                "limit": 1500,
            },
        )
        if not batch:
            break
        rows.extend(batch)
        next_cursor = int(batch[-1][0]) + 3_600_000
        if next_cursor <= cursor:
            raise RuntimeError("kline pagination did not advance")
        cursor = next_cursor
        if len(batch) < 1500:
            break
    return rows


def klines_to_raw(rows: list[list[Any]], now_ms: int) -> pd.DataFrame:
    frame = pd.DataFrame(
        rows,
        columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trade_count",
            "taker_buy_volume", "taker_buy_quote_volume", "ignore",
        ],
    )
    frame = frame.loc[frame["close_time"].astype("int64") < now_ms].copy()
    for column in (
        "open", "high", "low", "close", "volume", "quote_volume",
        "taker_buy_volume", "taker_buy_quote_volume",
    ):
        frame[column] = pd.to_numeric(frame[column], errors="raise").astype("float64")
    frame["trade_count"] = frame["trade_count"].astype("int64")
    frame["open_time"] = pd.to_datetime(frame["open_time"], unit="ms", utc=True)
    frame["close_time"] = pd.to_datetime(frame["close_time"], unit="ms", utc=True)
    frame["ignore"] = frame["ignore"].astype(str)
    frame["source"] = KLINE_SOURCE
    frame["is_closed"] = True
    return frame[
        [
            "open_time", "open", "high", "low", "close", "volume", "close_time",
            "quote_volume", "trade_count", "taker_buy_volume",
            "taker_buy_quote_volume", "ignore", "source", "is_closed",
        ]
    ]


def raw_to_normalized(raw: pd.DataFrame) -> pd.DataFrame:
    if (raw["volume"] <= 0.0).any():
        raise RuntimeError("zero-volume hour encountered; vwap undefined (blocker)")
    return pd.DataFrame(
        {
            "ts": raw["open_time"],
            "exchange": "binance",
            "symbol": "HYPE/USDT:USDT",
            "market_type": "perp",
            "timeframe": "1h",
            "base_asset": "HYPE",
            "quote_asset": "USDT",
            "open": raw["open"],
            "high": raw["high"],
            "low": raw["low"],
            "close": raw["close"],
            "volume": raw["volume"],
            "quote_volume": raw["quote_volume"],
            "trade_count": raw["trade_count"],
            "vwap": raw["quote_volume"] / raw["volume"],
            "is_closed": raw["is_closed"],
            "source": raw["source"],
        }
    )


def merge_partition(path: Path, new_rows: pd.DataFrame, key: str) -> int:
    if path.exists():
        existing = pd.read_parquet(path)
        combined = pd.concat([existing, new_rows], ignore_index=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        combined = new_rows.copy()
    before = len(combined)
    combined[key] = pd.to_datetime(combined[key], utc=True)
    combined = (
        combined.drop_duplicates(key, keep="first").sort_values(key).reset_index(drop=True)
    )
    added = len(combined) - (before - len(new_rows))
    combined.to_parquet(path, index=False)
    return added


def main() -> None:
    args = parse_args()
    engine = load_engine()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    normalized_before, _ = engine.audit_and_load_market(ROOT, "1h")
    last_ts = pd.Timestamp(normalized_before["ts"].iloc[-1])
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    start_ms = int(last_ts.value // 10**6) + 3_600_000

    kline_rows = fetch_klines(start_ms, now_ms)
    raw_new = klines_to_raw(kline_rows, now_ms)
    if raw_new.empty:
        print("no new closed bars; lake already current")
        return

    ohlcv_added = 0
    for day, day_rows in raw_new.groupby(raw_new["open_time"].dt.date):
        date_dir = f"date={day.isoformat()}"
        merge_partition(OHLCV_RAW / date_dir / PARTITION_NAME, day_rows, "open_time")
        ohlcv_added += merge_partition(
            OHLCV_NORM / date_dir / PARTITION_NAME,
            raw_to_normalized(day_rows),
            "ts",
        )

    funding_existing = pd.read_parquet(FUNDING_NORM)
    funding_last_ms = int(
        pd.to_datetime(funding_existing["ts"], utc=True).max().value // 10**6
    )
    funding_rows = http_get_json(
        FUNDING_URL,
        {"symbol": SYMBOL, "startTime": funding_last_ms + 1, "limit": 1000},
    )
    funding_new = pd.DataFrame(
        {
            "ts": pd.to_datetime(
                [int(r["fundingTime"]) for r in funding_rows], unit="ms", utc=True
            ),
            "funding_rate": [float(r["fundingRate"]) for r in funding_rows],
            "mark_price": [
                float(r["markPrice"]) if r.get("markPrice") not in (None, "") else float("nan")
                for r in funding_rows
            ],
            "source": FUNDING_SOURCE,
        }
    )
    funding_added = merge_partition(FUNDING_NORM, funding_new, "ts") if len(funding_new) else 0

    normalized_after, market_quality = engine.audit_and_load_market(ROOT, "1h")
    _, funding_quality = engine.load_and_audit_funding(ROOT)

    evidence = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "purpose": "extend HYPE 1h + funding lake for V1 prospective observation",
        "kline_endpoint": KLINE_URL,
        "funding_endpoint": FUNDING_URL,
        "previous_last_ts": last_ts.isoformat(),
        "new_last_ts": pd.Timestamp(normalized_after["ts"].iloc[-1]).isoformat(),
        "ohlcv_bars_added": int(ohlcv_added),
        "funding_events_added": int(funding_added),
        "market_quality_after": market_quality,
        "funding_quality_after": funding_quality,
    }
    out = ARTIFACT_DIR / f"hype_1h_prospective_sync_{args.run_date}.json"
    out.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"added {ohlcv_added} hourly bars ({last_ts} -> {evidence['new_last_ts']}), "
        f"{funding_added} funding events; audits clean"
    )
    print("evidence ->", out)


if __name__ == "__main__":
    main()
