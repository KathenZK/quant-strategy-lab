#!/usr/bin/env python3
"""Ingest a dated Yahoo Chart API GC=F snapshot for the recent extension."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import time
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/gold/1d-multi-speed-tsmom"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
RAW_ROOT = (
    ROOT
    / "data/raw/ohlcv/exchange=comex/market_type=futures/timeframe=1d"
    / "source=yahoo_chart_snapshot"
)
SOURCE = "yahoo_chart_snapshot"
SYMBOL = "GC=F"
SYMBOL_FILE = "symbol=gc_f.parquet"
START_DATE = "2020-01-01"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def timestamp(value: str) -> int:
    return int(pd.Timestamp(value, tz="UTC").timestamp())


def download(run_date: str) -> tuple[bytes, str]:
    period2 = (pd.Timestamp(run_date) + timedelta(days=1)).strftime("%Y-%m-%d")
    query = urlencode(
        {
            "period1": timestamp(START_DATE),
            "period2": timestamp(period2),
            "interval": "1d",
            "events": "history",
        }
    )
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/GC%3DF?{query}"
    error: Exception | None = None
    for attempt in range(5):
        try:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(request, timeout=60) as response:
                content = response.read()
            if content:
                return content, url
        except Exception as exc:  # pragma: no cover - network retry
            error = exc
        time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"Yahoo Chart API download failed: {error}")


def parse_payload(content: bytes, url: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    payload = json.loads(content)
    if payload.get("chart", {}).get("error"):
        raise RuntimeError(f"Yahoo Chart API error: {payload['chart']['error']}")
    result = payload["chart"]["result"][0]
    quote = result["indicators"]["quote"][0]
    frame = pd.DataFrame(quote)
    frame["provider_ts"] = pd.to_datetime(result["timestamp"], unit="s", utc=True)
    provider_rows = len(frame)
    price_columns = ["open", "high", "low", "close"]
    null_mask = frame[price_columns].isna().any(axis=1)
    null_sessions = frame.loc[null_mask, "provider_ts"].dt.strftime("%Y-%m-%d").tolist()
    frame = frame.loc[~null_mask].copy()
    frame["session_date"] = frame["provider_ts"].dt.tz_convert(
        result["meta"]["exchangeTimezoneName"]
    ).dt.strftime("%Y-%m-%d")
    frame["ts"] = pd.to_datetime(frame["session_date"], utc=True)
    frame = frame.sort_values("ts").reset_index(drop=True)
    invalid = (
        frame[price_columns].le(0).any(axis=1)
        | frame["high"].lt(frame[["open", "close", "low"]].max(axis=1))
        | frame["low"].gt(frame[["open", "close", "high"]].min(axis=1))
    )
    duplicates = int(frame["ts"].duplicated().sum())
    blockers = int(invalid.sum()) + duplicates + int(not frame["ts"].is_monotonic_increasing)
    if blockers:
        raise RuntimeError(
            f"Yahoo recent price audit failed: invalid={int(invalid.sum())}, "
            f"duplicates={duplicates}"
        )
    frame["open_interest"] = pd.NA
    frame["exchange"] = "comex"
    frame["symbol"] = SYMBOL
    frame["market_type"] = "futures"
    frame["timeframe"] = "1d"
    frame["source"] = SOURCE
    frame["source_dataset_id"] = (
        f"yahoo-chart-api:GC=F:{START_DATE}:{frame['session_date'].iloc[-1]}"
    )
    frame["continuous_contract_identity"] = "Yahoo Finance GC=F continuous futures"
    frame["roll_adjustment"] = "provider_method_unverified; raw quote.close used"
    frame["price_semantics"] = "Yahoo quote OHLC; adjclose deliberately excluded"
    frame["ts_semantics"] = "exchange-local session date normalized to 00:00 UTC"
    frame["quality_status"] = "raw_unaccepted"
    keep = [
        "ts",
        "session_date",
        "provider_ts",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "open_interest",
        "exchange",
        "symbol",
        "market_type",
        "timeframe",
        "source",
        "source_dataset_id",
        "continuous_contract_identity",
        "roll_adjustment",
        "price_semantics",
        "ts_semantics",
        "quality_status",
    ]
    frame = frame[keep]
    daily_return = frame["close"].pct_change(fill_method=None)
    audit = {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "download_url": url,
        "response_sha256": sha256(content).hexdigest(),
        "source_dataset_id": frame["source_dataset_id"].iloc[0],
        "source_api": "Yahoo Finance Chart API v8",
        "symbol": SYMBOL,
        "exchange_name_from_meta": result["meta"]["fullExchangeName"],
        "exchange_timezone": result["meta"]["exchangeTimezoneName"],
        "instrument_type": result["meta"]["instrumentType"],
        "provider_rows": provider_rows,
        "null_price_rows_dropped": int(null_mask.sum()),
        "null_price_sessions": null_sessions,
        "rows": int(len(frame)),
        "first_session": frame["session_date"].iloc[0],
        "last_session": frame["session_date"].iloc[-1],
        "duplicate_ts": duplicates,
        "invalid_ohlc_rows": int(invalid.sum()),
        "max_abs_daily_return": float(daily_return.abs().max()),
        "daily_abs_return_over_10pct_rows": int(daily_return.abs().gt(0.10).sum()),
        "mechanical_price_blockers": blockers,
        "quote_close_used": True,
        "adjusted_close_used": False,
        "quality_status": "raw_unaccepted",
        "accepted_for_strategy_evidence": False,
        "acceptance_blockers": [
            "Yahoo continuous-contract roll mapping and adjustment method are unavailable",
            "daily quote close versus official COMEX settlement is not provider-verifiable",
            "COMEX exchange-calendar continuity audit is not implemented",
            "the source is a dynamic snapshot rather than an immutable vendor release",
            "open interest, is_closed, trade_count and vwap provenance are unavailable",
        ],
    }
    return frame, audit


def atomic_parquet(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=f".{path.stem}-", suffix=".tmp", delete=False
    ) as handle:
        temporary = Path(handle.name)
    try:
        frame.to_parquet(temporary, index=False)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def write_partitions(frame: pd.DataFrame, *, force: bool) -> dict[str, Any]:
    written = 0
    verified = 0
    for row in frame.itertuples(index=False):
        path = RAW_ROOT / f"date={row.session_date}" / SYMBOL_FILE
        expected = pd.DataFrame([row._asdict()])
        if path.exists() and not force:
            actual = pd.read_parquet(path)
            if len(actual) != 1 or str(actual.iloc[0]["session_date"]) != row.session_date:
                raise RuntimeError(f"existing partition mismatch: {path}")
            verified += 1
            continue
        atomic_parquet(expected, path)
        written += 1
    return {"partitions_total": len(frame), "partitions_written": written, "verified": verified}


def main() -> None:
    args = parse_args()
    content, url = download(args.run_date)
    frame, audit = parse_payload(content, url)
    writes = write_partitions(frame, force=args.force)
    audit.update(writes)
    audit["raw_root"] = RAW_ROOT.relative_to(ROOT).as_posix()
    output = ARTIFACT_DIR / (
        f"gold-1d-ms-tsmom-recent-extension-{args.run_date}-data-audit.json"
    )
    if output.exists() and not args.force:
        existing = json.loads(output.read_text(encoding="utf-8"))
        if existing.get("response_sha256") != audit["response_sha256"]:
            raise RuntimeError(f"snapshot changed; pass --force to replace {output}")
    output.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"artifact": str(output.relative_to(ROOT)), **writes}, indent=2))


if __name__ == "__main__":
    main()
