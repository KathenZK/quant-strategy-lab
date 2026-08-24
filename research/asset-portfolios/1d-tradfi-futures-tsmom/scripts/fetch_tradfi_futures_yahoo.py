#!/usr/bin/env python3
"""Fetch the frozen 24-market Yahoo continuous-futures surface."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import time
from typing import Any
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-tradfi-futures-tsmom"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
SOURCE = "yahoo_chart_futures_snapshot"
START_DATE = "2020-01-01"
OHLC_TOLERANCE = 0.005
MAX_ABS_DAILY_RETURN = 0.50

UNIVERSE: dict[str, dict[str, str]] = {
    "ES=F": {"class": "equity_index", "exchange": "cme", "name": "S&P 500"},
    "NQ=F": {"class": "equity_index", "exchange": "cme", "name": "Nasdaq 100"},
    "YM=F": {"class": "equity_index", "exchange": "cbot", "name": "Dow Jones"},
    "RTY=F": {"class": "equity_index", "exchange": "cme", "name": "Russell 2000"},
    "NKD=F": {"class": "equity_index", "exchange": "cme", "name": "Nikkei USD"},
    "ZT=F": {"class": "bond", "exchange": "cbot", "name": "US Treasury 2Y"},
    "ZF=F": {"class": "bond", "exchange": "cbot", "name": "US Treasury 5Y"},
    "ZN=F": {"class": "bond", "exchange": "cbot", "name": "US Treasury 10Y"},
    "ZB=F": {"class": "bond", "exchange": "cbot", "name": "US Treasury Bond"},
    "UB=F": {"class": "bond", "exchange": "cbot", "name": "Ultra Treasury Bond"},
    "6A=F": {"class": "fx", "exchange": "cme", "name": "Australian Dollar"},
    "6B=F": {"class": "fx", "exchange": "cme", "name": "British Pound"},
    "6C=F": {"class": "fx", "exchange": "cme", "name": "Canadian Dollar"},
    "6E=F": {"class": "fx", "exchange": "cme", "name": "Euro FX"},
    "6J=F": {"class": "fx", "exchange": "cme", "name": "Japanese Yen"},
    "6S=F": {"class": "fx", "exchange": "cme", "name": "Swiss Franc"},
    "GC=F": {"class": "commodity", "exchange": "comex", "name": "Gold"},
    "SI=F": {"class": "commodity", "exchange": "comex", "name": "Silver"},
    "BZ=F": {"class": "commodity", "exchange": "nymex", "name": "Brent Crude"},
    "NG=F": {"class": "commodity", "exchange": "nymex", "name": "Natural Gas"},
    "HG=F": {"class": "commodity", "exchange": "comex", "name": "Copper"},
    "ZC=F": {"class": "commodity", "exchange": "cbot", "name": "Corn"},
    "ZW=F": {"class": "commodity", "exchange": "cbot", "name": "Wheat"},
    "ZS=F": {"class": "commodity", "exchange": "cbot", "name": "Soybeans"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def unix(value: str) -> int:
    return int(pd.Timestamp(value, tz="UTC").timestamp())


def url_for(symbol: str, run_date: str) -> str:
    period2 = (pd.Timestamp(run_date) + timedelta(days=1)).strftime("%Y-%m-%d")
    query = urlencode(
        {
            "period1": unix(START_DATE),
            "period2": unix(period2),
            "interval": "1d",
            "events": "history",
        }
    )
    return f"https://query2.finance.yahoo.com/v8/finance/chart/{quote(symbol, safe='')}?{query}"


def fetch(symbol: str, run_date: str) -> tuple[str, bytes, str]:
    url = url_for(symbol, run_date)
    error: Exception | None = None
    for attempt in range(5):
        try:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(request, timeout=60) as response:
                content = response.read()
            payload = json.loads(content)
            if payload.get("chart", {}).get("result"):
                return symbol, content, url
        except Exception as exc:  # pragma: no cover - network retry
            error = exc
        time.sleep(0.75 * (attempt + 1))
    raise RuntimeError(f"Yahoo fetch failed for {symbol}: {error}")


def parse(symbol: str, content: bytes, url: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    result = json.loads(content)["chart"]["result"][0]
    meta = result["meta"]
    if meta.get("symbol") != symbol:
        raise RuntimeError(f"symbol mismatch: {symbol} != {meta.get('symbol')}")
    quote_data = result["indicators"]["quote"][0]
    frame = pd.DataFrame(quote_data)
    frame["provider_ts"] = pd.to_datetime(result["timestamp"], unit="s", utc=True)
    provider_rows = len(frame)
    price_columns = ["open", "high", "low", "close"]
    null_mask = frame[price_columns].isna().any(axis=1)
    frame = frame.loc[~null_mask].copy()
    timezone = meta.get("exchangeTimezoneName", "America/New_York")
    frame["session_date"] = frame["provider_ts"].dt.tz_convert(timezone).dt.strftime(
        "%Y-%m-%d"
    )
    frame["ts"] = pd.to_datetime(frame["session_date"], utc=True)
    frame = frame.sort_values("ts").reset_index(drop=True)
    nonpositive = frame[price_columns].le(0).any(axis=1)
    upper_breach = (
        frame[["open", "close", "low"]].max(axis=1) - frame["high"]
    ).clip(lower=0) / frame["close"].abs()
    lower_breach = (
        frame["low"] - frame[["open", "close", "high"]].min(axis=1)
    ).clip(lower=0) / frame["close"].abs()
    relative_breach = pd.concat([upper_breach, lower_breach], axis=1).max(axis=1)
    duplicates = int(frame["ts"].duplicated().sum())
    daily_return = frame["close"].pct_change(fill_method=None)
    blockers = (
        int(nonpositive.sum())
        + int(relative_breach.gt(OHLC_TOLERANCE).sum())
        + duplicates
        + int(daily_return.abs().max() > MAX_ABS_DAILY_RETURN)
    )
    if blockers:
        raise RuntimeError(
            f"data blocker {symbol}: nonpositive={int(nonpositive.sum())}, "
            f"breach_gt_0.5pct={int(relative_breach.gt(OHLC_TOLERANCE).sum())}, "
            f"duplicates={duplicates}, max_abs_return={daily_return.abs().max():.6f}"
        )
    identity = UNIVERSE[symbol]
    frame["open_interest"] = pd.NA
    frame["exchange"] = identity["exchange"]
    frame["symbol"] = symbol
    frame["asset_class"] = identity["class"]
    frame["market_type"] = "futures"
    frame["timeframe"] = "1d"
    frame["source"] = SOURCE
    frame["source_dataset_id"] = (
        f"yahoo-chart-api:{symbol}:{START_DATE}:{frame['session_date'].iloc[-1]}"
    )
    frame["roll_adjustment"] = "provider_method_unverified; raw quote.close"
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
        "asset_class",
        "market_type",
        "timeframe",
        "source",
        "source_dataset_id",
        "roll_adjustment",
        "quality_status",
    ]
    audit = {
        "symbol": symbol,
        "name": identity["name"],
        "asset_class": identity["class"],
        "exchange": identity["exchange"],
        "url": url,
        "response_sha256": sha256(content).hexdigest(),
        "provider_rows": provider_rows,
        "rows": len(frame),
        "first_session": frame["session_date"].iloc[0],
        "last_session": frame["session_date"].iloc[-1],
        "null_price_rows_dropped": int(null_mask.sum()),
        "duplicate_ts": duplicates,
        "minor_ohlc_breach_rows": int(relative_breach.gt(0).sum()),
        "max_relative_ohlc_breach": float(relative_breach.max()),
        "nonpositive_price_rows": int(nonpositive.sum()),
        "max_abs_daily_return": float(daily_return.abs().max()),
        "mechanical_blockers": blockers,
        "adjusted_close_used": False,
    }
    return frame[keep], audit


def safe_symbol(symbol: str) -> str:
    return symbol.lower().replace("=", "_")


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


def write_market(frame: pd.DataFrame, *, force: bool) -> tuple[int, int]:
    written = 0
    verified = 0
    for row in frame.itertuples(index=False):
        path = (
            ROOT
            / "data/raw/ohlcv"
            / f"exchange={row.exchange}"
            / "market_type=futures/timeframe=1d"
            / f"source={SOURCE}/date={row.session_date}"
            / f"symbol={safe_symbol(row.symbol)}.parquet"
        )
        if path.exists() and not force:
            actual = pd.read_parquet(path, columns=["session_date", "symbol"])
            if len(actual) != 1 or actual.iloc[0]["symbol"] != row.symbol:
                raise RuntimeError(f"existing partition mismatch: {path}")
            verified += 1
            continue
        atomic_parquet(pd.DataFrame([row._asdict()]), path)
        written += 1
    return written, verified


def main() -> None:
    args = parse_args()
    fetched: dict[str, tuple[bytes, str]] = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(fetch, symbol, args.run_date) for symbol in UNIVERSE]
        for future in as_completed(futures):
            symbol, content, url = future.result()
            fetched[symbol] = (content, url)
    audits = []
    written = 0
    verified = 0
    for symbol in UNIVERSE:
        frame, audit = parse(symbol, *fetched[symbol])
        market_written, market_verified = write_market(frame, force=args.force)
        written += market_written
        verified += market_verified
        audit["partitions_written"] = market_written
        audit["partitions_verified"] = market_verified
        audits.append(audit)
    payload = {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "run_date": args.run_date,
        "source": SOURCE,
        "quality_status": "raw_unaccepted",
        "accepted_for_strategy_evidence": False,
        "universe_frozen_before_results": True,
        "markets": len(UNIVERSE),
        "classes": sorted({item["class"] for item in UNIVERSE.values()}),
        "partitions_written": written,
        "partitions_verified": verified,
        "market_audits": audits,
        "acceptance_blockers": [
            "provider continuous-contract roll mapping and adjustment method are unavailable",
            "quote close is not verified against official exchange settlement",
            "explicit roll transaction costs and contract multipliers are unavailable",
            "the usable clean common surface starts in 2020 and is short for trend research",
        ],
    }
    output = ARTIFACT_DIR / f"tf-1d-fut-tsmom-p0-{args.run_date}-data-audit.json"
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "artifact": str(output.relative_to(ROOT)),
                "markets": len(UNIVERSE),
                "partitions_written": written,
                "partitions_verified": verified,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
