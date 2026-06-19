from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


BASE_URL = "https://api.polygon.io/v2/aggs/ticker"
DEFAULT_SYMBOL = "MU"
DEFAULT_MULTIPLIER = 15
DEFAULT_TIMESPAN = "minute"
DEFAULT_DAYS = 365


def pct(value: float) -> float:
    return round(value * 100.0, 4)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch US equity aggregate bars from Polygon into the local data lake."
    )
    parser.add_argument("--symbol", default=DEFAULT_SYMBOL, help="US equity ticker.")
    parser.add_argument(
        "--multiplier",
        type=int,
        default=DEFAULT_MULTIPLIER,
        help="Polygon aggregate multiplier, e.g. 15 for 15-minute bars.",
    )
    parser.add_argument(
        "--timespan",
        default=DEFAULT_TIMESPAN,
        choices=["minute", "hour", "day", "week", "month", "quarter", "year"],
        help="Polygon aggregate timespan.",
    )
    parser.add_argument(
        "--from-date",
        dest="from_date",
        help="Start date in YYYY-MM-DD. Defaults to --days before --to-date.",
    )
    parser.add_argument(
        "--to-date",
        dest="to_date",
        help="End date in YYYY-MM-DD. Defaults to today in UTC.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_DAYS,
        help="Lookback days when --from-date is omitted.",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("POLYGON_API_KEY"),
        help="Polygon API key. Prefer POLYGON_API_KEY env var.",
    )
    parser.add_argument(
        "--adjusted",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use split-adjusted aggregate bars.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=12.1,
        help="Delay between paginated calls, useful for 5 calls/minute plans.",
    )
    return parser.parse_args()


def default_dates(days: int) -> tuple[str, str]:
    to_day = datetime.now(UTC).date()
    from_day = to_day - timedelta(days=days)
    return from_day.isoformat(), to_day.isoformat()


def with_api_key(url: str, api_key: str) -> str:
    parsed = urllib.parse.urlparse(url)
    query = dict(urllib.parse.parse_qsl(parsed.query))
    query["apiKey"] = api_key
    return urllib.parse.urlunparse(
        parsed._replace(query=urllib.parse.urlencode(query))
    )


def fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "quant-strategy-lab/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Polygon HTTP {exc.code}: {body}") from exc
    payload = json.loads(body)
    if payload.get("status") in {"ERROR", "NOT_AUTHORIZED"}:
        raise RuntimeError(f"Polygon error: {payload}")
    return payload


def fetch_polygon_bars(
    *,
    symbol: str,
    multiplier: int,
    timespan: str,
    from_date: str,
    to_date: str,
    adjusted: bool,
    api_key: str,
    sleep_seconds: float,
) -> pd.DataFrame:
    query = urllib.parse.urlencode(
        {
            "adjusted": str(adjusted).lower(),
            "sort": "asc",
            "limit": 50000,
            "apiKey": api_key,
        }
    )
    url = (
        f"{BASE_URL}/{urllib.parse.quote(symbol.upper())}/range/"
        f"{multiplier}/{timespan}/{from_date}/{to_date}?{query}"
    )
    records: list[dict[str, Any]] = []
    page = 0
    while url:
        page += 1
        payload = fetch_json(url)
        records.extend(payload.get("results", []))
        next_url = payload.get("next_url")
        if not next_url:
            break
        url = with_api_key(next_url, api_key)
        time.sleep(sleep_seconds)

    if not records:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume", "vwap", "transactions"])

    frame = pd.DataFrame.from_records(records)
    frame = frame.rename(
        columns={
            "t": "ts",
            "o": "open",
            "h": "high",
            "l": "low",
            "c": "close",
            "v": "volume",
            "vw": "vwap",
            "n": "transactions",
        }
    )
    frame["ts"] = pd.to_datetime(frame["ts"], unit="ms", utc=True)
    keep_columns = ["ts", "open", "high", "low", "close", "volume", "vwap", "transactions"]
    for column in keep_columns:
        if column not in frame.columns:
            frame[column] = np.nan
    frame = frame[keep_columns].drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    return frame


def summarize(frame: pd.DataFrame, *, symbol: str, source_url: str) -> dict[str, Any]:
    if frame.empty:
        return {
            "symbol": symbol.upper(),
            "source": "polygon",
            "source_url": source_url,
            "rows": 0,
        }
    returns = frame.close.pct_change().dropna()
    drawdown = frame.close / frame.close.cummax() - 1.0
    local = pd.DatetimeIndex(frame.ts).tz_convert("America/New_York")
    minutes = local.hour * 60 + local.minute
    sessions = {
        "premarket_rows": int(((minutes >= 4 * 60) & (minutes < 9 * 60 + 30)).sum()),
        "regular_rows": int(((minutes >= 9 * 60 + 30) & (minutes < 16 * 60)).sum()),
        "afterhours_rows": int(((minutes >= 16 * 60) & (minutes < 20 * 60)).sum()),
        "overnight_rows": int(((minutes >= 20 * 60) | (minutes < 4 * 60)).sum()),
    }
    return {
        "symbol": symbol.upper(),
        "source": "polygon",
        "source_url": source_url,
        "rows": int(len(frame)),
        "start": str(pd.Timestamp(frame.ts.iloc[0])),
        "end": str(pd.Timestamp(frame.ts.iloc[-1])),
        "close_start": round(float(frame.close.iloc[0]), 6),
        "close_end": round(float(frame.close.iloc[-1]), 6),
        "period_return_pct": pct(float(frame.close.iloc[-1] / frame.close.iloc[0] - 1.0)),
        "max_drawdown_pct": pct(float(drawdown.min())),
        "mean_15m_return_bps": round(float(returns.mean() * 10000.0), 4),
        "vol_15m_return_bps": round(float(returns.std(ddof=0) * 10000.0), 4),
        **sessions,
    }


def main() -> None:
    args = parse_args()
    if not args.api_key:
        raise SystemExit("missing Polygon API key: set POLYGON_API_KEY or pass --api-key")

    from_date, to_date = default_dates(args.days)
    if args.from_date:
        date.fromisoformat(args.from_date)
        from_date = args.from_date
    if args.to_date:
        date.fromisoformat(args.to_date)
        to_date = args.to_date

    symbol = args.symbol.upper()
    timeframe = f"{args.multiplier}{args.timespan[0]}"
    output_dir = (
        Path("data/external/us_equities/polygon")
        / f"symbol={symbol.lower()}"
        / f"timeframe={timeframe}"
    )
    output_stem = f"{symbol.lower()}_{timeframe}_{from_date}_{to_date}_adjusted"
    csv_path = output_dir / f"{output_stem}.csv"
    parquet_path = output_dir / f"{output_stem}.parquet"
    summary_path = Path("reports") / f"{symbol.lower()}_us_equity_polygon_{timeframe}_{from_date}_{to_date}_summary.json"

    frame = fetch_polygon_bars(
        symbol=symbol,
        multiplier=args.multiplier,
        timespan=args.timespan,
        from_date=from_date,
        to_date=to_date,
        adjusted=args.adjusted,
        api_key=args.api_key,
        sleep_seconds=args.sleep_seconds,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(csv_path, index=False)
    frame.to_parquet(parquet_path, index=False)

    source_url = (
        f"{BASE_URL}/{symbol}/range/{args.multiplier}/{args.timespan}/"
        f"{from_date}/{to_date}"
    )
    summary = summarize(frame, symbol=symbol, source_url=source_url)
    summary["csv_path"] = str(csv_path)
    summary["parquet_path"] = str(parquet_path)
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
