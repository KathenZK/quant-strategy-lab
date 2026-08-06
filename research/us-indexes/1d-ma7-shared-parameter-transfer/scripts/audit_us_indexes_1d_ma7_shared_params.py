from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, date, datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Any
from urllib.parse import quote

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/us-indexes/1d-ma7-shared-parameter-transfer"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
SOX_HELPER_PATH = (
    ROOT
    / "research/sox/1d-ma7-separated-trend-transfer/scripts/"
    "research_sox_1d_ma7_v1_transfer.py"
)
SOX_HELPER_SHA256 = (
    "84f08d9d83235e76e7009c46717157e784bacdf0b04945165bcccc11a42a72fb"
)
SHARED_SUMMARY_PATH = (
    ROOT
    / "research/asset-portfolios/1d-ma7-asset-specific-search/artifacts/"
    "binance_btc_eth_1d_ma7_asset_specific_search_summary_2026-08-05.json"
)
SHARED_SUMMARY_SHA256 = (
    "ecaf0d65ddc7ed114acd078656e7da948a6ed5399c1b6292d716fb91199031be"
)
PERIOD1 = 768058200
PERIOD2 = 1790000000
ILLUSTRATIVE_FRICTION = 0.001
ASSETS = {
    "sp500": {
        "symbol": "^GSPC",
        "name": "S&P 500 price index",
    },
    "nasdaq_composite": {
        "symbol": "^IXIC",
        "name": "Nasdaq Composite price index",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Zero-tuning transfer of frozen BTC/ETH shared daily MA7 "
            "parameters to S&P 500 and Nasdaq Composite."
        )
    )
    parser.add_argument(
        "--run-date",
        default=datetime.now(UTC).date().isoformat(),
    )
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def load_module(path: Path, expected_hash: str, name: str) -> Any:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected_hash:
        raise RuntimeError(
            f"{path.name} drift: expected {expected_hash}, got {digest}"
        )
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_shared_configs(engine: Any) -> tuple[Any, Any]:
    digest = hashlib.sha256(SHARED_SUMMARY_PATH.read_bytes()).hexdigest()
    if digest != SHARED_SUMMARY_SHA256:
        raise RuntimeError(
            f"shared summary drift: expected {SHARED_SUMMARY_SHA256}, got {digest}"
        )
    payload = json.loads(
        SHARED_SUMMARY_PATH.read_text(encoding="utf-8")
    )
    selected = payload["selections"]["BTC_ETH_shared"]
    return (
        engine.Config(**selected["long_config"]),
        engine.Config(**selected["short_config"]),
    )


def yahoo_url(symbol: str) -> str:
    encoded = quote(symbol, safe="")
    return (
        f"https://query2.finance.yahoo.com/v8/finance/chart/{encoded}"
        f"?period1={PERIOD1}&period2={PERIOD2}"
        "&interval=1d&events=div%2Csplits"
    )


def fetch_yahoo(
    symbol: str,
    raw_path: Path,
    *,
    refresh: bool,
) -> tuple[bytes, str]:
    url = yahoo_url(symbol)
    if raw_path.exists() and not refresh:
        return raw_path.read_bytes(), url
    completed = subprocess.run(
        [
            "curl",
            "--fail",
            "--location",
            "--retry",
            "3",
            "--retry-delay",
            "2",
            "--silent",
            "--show-error",
            "--user-agent",
            "Mozilla/5.0",
            url,
        ],
        check=True,
        capture_output=True,
    )
    content = completed.stdout
    if not content:
        raise RuntimeError(f"Yahoo returned empty response for {symbol}")
    raw_path.write_bytes(content)
    return content, url


def parse_yahoo(
    sox: Any,
    content: bytes,
    url: str,
    expected_symbol: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    original_url = sox.YAHOO_URL
    try:
        sox.YAHOO_URL = url
        frame, quality = sox.parse_and_audit_yahoo(content)
    finally:
        sox.YAHOO_URL = original_url
    if quality["symbol"] != expected_symbol:
        raise RuntimeError(
            f"symbol mismatch: expected {expected_symbol}, "
            f"got {quality['symbol']}"
        )
    return frame, quality


def window_indices(book: Any) -> dict[str, tuple[int, int]]:
    local_dates = np.asarray(
        pd.DatetimeIndex(book.ts)
        .tz_convert(book.quality["exchange_timezone"])
        .date
    )
    split_2010 = int(
        np.searchsorted(local_dates, date(2010, 1, 4), side="left")
    )
    split_2021 = int(
        np.searchsorted(local_dates, date(2021, 1, 4), side="left")
    )
    if not (500 < split_2010 < split_2021 < book.count - 500):
        raise RuntimeError("invalid US index audit windows")
    return {
        "pre_2010": (0, split_2010),
        "2010_2020": (split_2010, split_2021),
        "2021_plus": (split_2021, book.count),
        "full_available": (0, book.count),
    }


def configs_by_variant(
    long_config: Any,
    short_config: Any,
) -> dict[str, tuple[Any | None, Any | None]]:
    return {
        "combined": (long_config, short_config),
        "long_only": (long_config, None),
        "short_only": (None, short_config),
    }


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: clean_json(item)
            for key, item in value.items()
            if key != "_results"
        }
    if isinstance(value, (list, tuple)):
        return [clean_json(item) for item in value]
    if isinstance(value, np.generic):
        return clean_json(value.item())
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def main() -> None:
    args = parse_args()
    sox = load_module(
        SOX_HELPER_PATH,
        SOX_HELPER_SHA256,
        "us_indexes_ma7_transfer_helper",
    )
    engine = sox.load_engine()
    engine.STRESS_SLIPPAGE = ILLUSTRATIVE_FRICTION
    long_config, short_config = load_shared_configs(engine)
    if args.self_test:
        assert yahoo_url("^GSPC").endswith(
            "interval=1d&events=div%2Csplits"
        )
        assert "%5EGSPC" in yahoo_url("^GSPC")
        assert long_config.slope_lookback == 5
        assert short_config.entry_mode == "pullback_reclaim"
        print("self-test: PASS")
        return

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "US-Indexes-1D-MA7-Shared-Parameter-Transfer",
        "status": "explore / not promoted / not live-ready",
        "selection": (
            "zero US-index tuning; frozen BTC/ETH shared parameters"
        ),
        "source": {
            "shared_summary_path": str(
                SHARED_SUMMARY_PATH.relative_to(ROOT)
            ),
            "shared_summary_sha256": SHARED_SUMMARY_SHA256,
            "sox_helper_path": str(SOX_HELPER_PATH.relative_to(ROOT)),
            "sox_helper_sha256": SOX_HELPER_SHA256,
        },
        "long_config": asdict(long_config),
        "short_config": asdict(short_config),
        "instrument_limitations": {
            "tradability": (
                "both series are price indexes, not directly tradable"
            ),
            "primary_cost_model": (
                "zero fee, slippage, borrow, financing and dividend"
            ),
            "stress": "10 bps adverse friction per fill",
            "intraday_resolution": (
                "daily OHLC only; no within-session high/low ordering"
            ),
        },
        "assets": {},
    }
    metric_rows: list[dict[str, Any]] = []
    recent_rows: list[dict[str, Any]] = []
    annual_rows: list[dict[str, Any]] = []
    rolling_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []

    for asset, identity in ASSETS.items():
        print(f"loading {asset}", flush=True)
        raw_path = (
            ARTIFACT_DIR
            / f"{asset}_yahoo_chart_1d_raw_{args.run_date}.json"
        )
        content, url = fetch_yahoo(
            identity["symbol"],
            raw_path,
            refresh=args.refresh,
        )
        frame, quality = parse_yahoo(
            sox,
            content,
            url,
            identity["symbol"],
        )
        normalized_path = (
            ARTIFACT_DIR
            / f"{asset}_yahoo_1d_normalized_{args.run_date}.csv"
        )
        frame.to_csv(normalized_path, index=False)
        book, features = sox.build_book_and_features(
            engine,
            frame,
            quality,
        )
        windows = window_indices(book)
        asset_payload: dict[str, Any] = {
            "identity": identity,
            "data_quality": {
                **quality,
                "raw_artifact": str(raw_path.relative_to(ROOT)),
                "normalized_artifact": str(
                    normalized_path.relative_to(ROOT)
                ),
            },
            "windows": {},
            "stability": {},
        }
        full_results: dict[str, Any] = {}
        for window, (start, end) in windows.items():
            audit = sox.audit_window(
                engine,
                book,
                features,
                long_config,
                short_config,
                start=start,
                end=end,
            )
            asset_payload["windows"][window] = audit
            for variant, metrics in audit.items():
                if isinstance(metrics, dict) and variant != "_results":
                    metric_rows.append(
                        {
                            "asset": asset,
                            "window": window,
                            "variant": variant,
                            **metrics,
                        }
                    )
            if window == "full_available":
                full_results = audit["_results"]

        for variant, (long_leg, short_leg) in configs_by_variant(
            long_config,
            short_config,
        ).items():
            annual = sox.calendar_year_rows(
                engine,
                book,
                features,
                long_leg,
                short_leg,
            )
            rolling = sox.rolling_three_year_rows(
                engine,
                book,
                features,
                long_leg,
                short_leg,
            )
            annual_rows.extend(
                {
                    "asset": asset,
                    "variant": variant,
                    **row,
                }
                for row in annual
            )
            rolling_rows.extend(
                {
                    "asset": asset,
                    "variant": variant,
                    **row,
                }
                for row in rolling
            )
            result = full_results[variant]
            recent_rows.extend(
                {
                    "asset": asset,
                    "variant": variant,
                    **row,
                }
                for row in engine.recent_slices(result)
            )
            trade_rows.extend(
                {
                    "asset": asset,
                    "variant": variant,
                    **trade,
                }
                for trade in result.trades
            )
            pd.DataFrame(result.path).to_csv(
                ARTIFACT_DIR
                / (
                    f"us_indexes_1d_ma7_shared_{asset}_{variant}"
                    f"_path_{args.run_date}.csv"
                ),
                index=False,
            )
            asset_payload["stability"][variant] = {
                "calendar_years": {
                    "count": len(annual),
                    "positive": sum(
                        row["net_return_pct"] > 0.0 for row in annual
                    ),
                    "median_return_pct": float(
                        np.median(
                            [row["net_return_pct"] for row in annual]
                        )
                    ),
                },
                "rolling_three_years": {
                    "count": len(rolling),
                    "positive": sum(
                        row["net_return_pct"] > 0.0 for row in rolling
                    ),
                    "median_return_pct": float(
                        np.median(
                            [row["net_return_pct"] for row in rolling]
                        )
                    ),
                    "worst_return_pct": float(
                        min(row["net_return_pct"] for row in rolling)
                    ),
                },
            }
        payload["assets"][asset] = asset_payload

    stem = "us_indexes_1d_ma7_shared_parameter_transfer"
    (ARTIFACT_DIR / f"{stem}_summary_{args.run_date}.json").write_text(
        json.dumps(
            clean_json(payload),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    pd.DataFrame(metric_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_metrics_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(recent_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_recent_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(annual_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_calendar_years_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(rolling_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_rolling_3y_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(trade_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_trades_{args.run_date}.csv",
        index=False,
    )
    print(json.dumps(clean_json(payload["assets"]), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
