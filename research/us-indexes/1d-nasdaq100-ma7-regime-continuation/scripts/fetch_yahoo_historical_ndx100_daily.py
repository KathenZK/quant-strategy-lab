from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import exchange_calendars as xcals
import pandas as pd


FAMILY_DIR = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CONFIG_PATH = (
    FAMILY_DIR
    / "configs/ndx100-1d-ma7-regime-continuation-yahoo-historical-y1.json"
)
INTERVAL_PATH = ARTIFACT_DIR / "ndx100_1d_ma7_rc_p0_membership_intervals.csv"
Y0_SCRIPT = FAMILY_DIR / "scripts/fetch_yahoo_current_ndx100_daily.py"
Y0_CACHE_DIR = ARTIFACT_DIR / "yahoo-current-cache" / "chart"
Y1_CACHE_DIR = ARTIFACT_DIR / "yahoo-historical-cache" / "chart"
UNIVERSE_PATH = ARTIFACT_DIR / "ndx100_1d_ma7_rc_y1_historical_ticker_universe.csv"
PRICE_PATH = ARTIFACT_DIR / "ndx100_1d_ma7_rc_y1_yahoo_ticker_prices.parquet"
AUDIT_PATH = ARTIFACT_DIR / "ndx100_1d_ma7_rc_y1_yahoo_fetch_audit.json"
MANIFEST_PATH = ARTIFACT_DIR / "ndx100_1d_ma7_rc_y1_yahoo_fetch_manifest.json"

STUDY_ID = "NDX100-1D-MA7-RC-Y1"


def load_y0_module() -> Any:
    spec = importlib.util.spec_from_file_location("ndx100_y0_fetch", Y0_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Yahoo fetch kernel")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


YAHOO = load_y0_module()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch Yahoo daily bars for every historical Nasdaq-100 ticker."
    )
    parser.add_argument("--force", action="store_true", help="Replace Y1 raw caches.")
    parser.add_argument("--limit", type=int, help="Smoke-test only: first N tickers.")
    parser.add_argument("--sleep-seconds", type=float, default=0.45)
    return parser.parse_args()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_config() -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if config.get("study_id") != STUDY_ID:
        raise RuntimeError("unexpected Y1 config identity")
    if config["research_contract"].get("parameter_search") is not False:
        raise RuntimeError("parameter search must remain disabled")
    return config


def historical_universe() -> pd.DataFrame:
    intervals = pd.read_csv(INTERVAL_PATH, dtype={"ticker": str, "entity_key": str})
    summary = (
        intervals.groupby("ticker", as_index=False)
        .agg(
            first_membership_session=("start_session", "min"),
            last_membership_session=("end_session_inclusive", "max"),
            entity_count=("entity_key", "nunique"),
            interval_count=("entity_key", "size"),
        )
        .sort_values("ticker")
        .reset_index(drop=True)
    )
    lineages = intervals.groupby("ticker")["entity_key"].agg(
        lambda values: "|".join(sorted(set(values.astype(str))))
    )
    summary["entity_keys"] = summary["ticker"].map(lineages)
    summary["universe_role"] = "historical_point_in_time_ticker_union"
    return summary


def cache_name(ticker: str, start: str, end: str) -> str:
    return f"{ticker}_{start}_{end}_1d.json"


def request_with_cache_reuse(
    ticker: str,
    *,
    start: str,
    end: str,
    force: bool,
    sleep_seconds: float,
) -> tuple[dict[str, Any], str]:
    name = cache_name(ticker, start, end)
    y1_path = Y1_CACHE_DIR / name
    y0_path = Y0_CACHE_DIR / name
    if not force and y1_path.exists():
        return json.loads(y1_path.read_text(encoding="utf-8")), "y1_cache"
    if not force and y0_path.exists():
        return json.loads(y0_path.read_text(encoding="utf-8")), "y0_cache"
    original_cache = YAHOO.CACHE_DIR
    YAHOO.CACHE_DIR = Y1_CACHE_DIR
    try:
        payload, from_cache = YAHOO.yahoo_request(
            ticker,
            start=start,
            end_inclusive=end,
            force=force,
            sleep_seconds=sleep_seconds,
        )
    finally:
        YAHOO.CACHE_DIR = original_cache
    return payload, "y1_cache" if from_cache else "downloaded"


def main() -> int:
    args = parse_args()
    config = load_config()
    universe = historical_universe()
    expected = config["universe"]["ticker_union_expected"]
    if len(universe) != expected:
        raise RuntimeError(f"historical ticker count changed: {len(universe)} != {expected}")
    if args.limit is not None:
        if args.limit <= 0:
            raise SystemExit("--limit must be positive")
        universe = universe.head(args.limit).copy()
    UNIVERSE_PATH.parent.mkdir(parents=True, exist_ok=True)
    universe.to_csv(UNIVERSE_PATH, index=False)

    start = config["data"]["fetch_start_inclusive"]
    end = config["data"]["study_end_inclusive"]
    tickers = sorted(set(universe["ticker"]) | {"QQQ"})
    frames: list[pd.DataFrame] = []
    per_ticker: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for number, ticker in enumerate(tickers, start=1):
        try:
            payload, cache_source = request_with_cache_reuse(
                ticker,
                start=start,
                end=end,
                force=args.force,
                sleep_seconds=args.sleep_seconds,
            )
            frame, diagnostic = YAHOO.parse_chart(ticker, payload)
            diagnostic["cache_source"] = cache_source
            per_ticker.append(diagnostic)
            if not frame.empty:
                frames.append(frame)
        except Exception as error:
            failures.append({"ticker": ticker, "error": str(error)})
        if number % 25 == 0:
            print(
                json.dumps(
                    {
                        "progress": f"{number}/{len(tickers)}",
                        "failures": len(failures),
                        "usable": len(frames),
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
    if not frames:
        raise RuntimeError("Yahoo returned no historical price frames")
    prices = pd.concat(frames, ignore_index=True).sort_values(
        ["ticker", "session_date"]
    )
    duplicate = prices.duplicated(["ticker", "session_date"], keep=False)
    invalid = (
        prices[["open", "high", "low", "close", "volume"]].isna().any(axis=1)
        | prices[["open", "high", "low", "close"]].le(0).any(axis=1)
        | prices["volume"].lt(0)
        | prices["high"].lt(prices[["open", "close", "low"]].max(axis=1))
        | prices["low"].gt(prices[["open", "close", "high"]].min(axis=1))
    )
    calendar = xcals.get_calendar("XNAS")
    sessions = pd.DatetimeIndex(
        calendar.sessions_in_range(pd.Timestamp(start), pd.Timestamp(end))
    ).tz_localize(None)
    out_of_session = ~prices["session_date"].isin(sessions)
    prices.to_parquet(PRICE_PATH, index=False)

    requested_universe = set(universe["ticker"].astype(str))
    usable = set(prices["ticker"].astype(str))
    no_usable = sorted(requested_universe - usable)
    cache_counts = pd.Series(
        [item["cache_source"] for item in per_ticker], dtype=str
    ).value_counts().to_dict()
    audit = {
        "study_id": STUDY_ID,
        "generated_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "status": "FETCH_COMPLETE_WITH_LIMITATIONS" if failures or no_usable else "FETCH_COMPLETE",
        "historical_ticker_count": int(len(universe)),
        "requested_ticker_count_including_qqq": len(tickers),
        "usable_ticker_count_including_qqq": int(prices["ticker"].nunique()),
        "rows": int(len(prices)),
        "first_session": prices["session_date"].min(),
        "last_session": prices["session_date"].max(),
        "cache_source_counts": cache_counts,
        "request_failures": failures,
        "historical_tickers_without_usable_data": no_usable,
        "duplicate_ticker_session_rows": int(duplicate.sum()),
        "invalid_ohlcv_rows": int(invalid.sum()),
        "out_of_xnas_session_rows": int(out_of_session.sum()),
        "per_ticker": per_ticker,
        "next_stage": "point-in-time membership coverage and entity-lineage audit",
    }
    write_json(AUDIT_PATH, audit)
    manifest = {
        "study_id": STUDY_ID,
        "generated_at_utc": audit["generated_at_utc"],
        "files": {
            str(CONFIG_PATH.relative_to(FAMILY_DIR)): sha256_file(CONFIG_PATH),
            str(UNIVERSE_PATH.relative_to(FAMILY_DIR)): sha256_file(UNIVERSE_PATH),
            str(PRICE_PATH.relative_to(FAMILY_DIR)): sha256_file(PRICE_PATH),
            str(AUDIT_PATH.relative_to(FAMILY_DIR)): sha256_file(AUDIT_PATH),
        },
        "y1_cache_file_count": len(list(Y1_CACHE_DIR.glob("*.json"))),
        "reused_y0_cache_file_count": int(cache_counts.get("y0_cache", 0)),
    }
    write_json(MANIFEST_PATH, manifest)
    print(json.dumps({key: value for key, value in audit.items() if key != "per_ticker"}, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
