from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-ma7-asset-specific-search"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
LOCAL_AUDIT_PATH = FAMILY_DIR / "scripts/audit_shared_ma7_params_on_hype.py"
FETCHER_PATH = (
    ROOT
    / "research/hype/1d-ma7-asymmetric-body-trend/scripts/"
    "audit_hype_1d_ma7_abt_v7_1_top15_binance_perp_transfer.py"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run BTC/ETH shared MA7 params on a fresh Binance HYPE window."
    )
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--history-days", type=int, default=520)
    parser.add_argument("--symbol", default="HYPEUSDT")
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument(
        "--output-stem",
        default="binance_ma7_shared_params_on_hype_fresh_aligned",
    )
    return parser.parse_args()


def date_to_ms(value: str) -> int:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    return int(timestamp.timestamp() * 1000)


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: clean_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json(item) for item in value]
    if isinstance(value, np.generic):
        return clean_json(value.item())
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def candle_frame(candles: list[Any]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ts": pd.Timestamp(row.ts, unit="ms", tz="UTC"),
                "open": row.open,
                "high": row.high,
                "low": row.low,
                "close": row.close,
                "volume": row.volume,
                "quote_volume": row.quote_volume,
                "trade_count": row.trade_count,
            }
            for row in candles
        ]
    )


def funding_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ts": pd.Timestamp(row["funding_time"], unit="ms", tz="UTC"),
                "funding_rate": row["funding_rate"],
            }
            for row in rows
        ]
    )


def build_book(symbol: str, daily: list[Any], hourly: list[Any], fetcher: Any) -> Any:
    if not daily:
        raise RuntimeError("daily data is empty")
    hourly_by_ts = {row.ts for row in hourly}
    complete_daily = [
        row
        for row in daily
        if sum(
            row.ts + hour * fetcher.MS_PER_HOUR in hourly_by_ts
            for hour in range(24)
        )
        == 24
    ]
    if not complete_daily:
        raise RuntimeError("no daily bar has a complete 24-hour path")
    daily = complete_daily
    terminal_ts_ms = daily[-1].ts + fetcher.MS_PER_DAY
    terminal_hours = [row for row in hourly if row.ts == terminal_ts_ms]
    if not terminal_hours:
        raise RuntimeError(f"missing terminal hourly open at {fetcher.iso(terminal_ts_ms)}")
    terminal_open = terminal_hours[0].open
    return SimpleNamespace(
        symbol=symbol,
        count=len(daily),
        ts=pd.DatetimeIndex([pd.Timestamp(row.ts, unit="ms", tz="UTC") for row in daily]),
        terminal_ts=pd.Timestamp(terminal_ts_ms, unit="ms", tz="UTC"),
        open=np.asarray([row.open for row in daily], dtype=float),
        high=np.asarray([row.high for row in daily], dtype=float),
        low=np.asarray([row.low for row in daily], dtype=float),
        close=np.asarray([row.close for row in daily], dtype=float),
        short_entry_open=np.asarray([row.open for row in daily], dtype=float),
        quality={
            "source": "binance_fapi_public_api",
            "daily": fetcher.quality(daily, fetcher.MS_PER_DAY),
            "hourly": fetcher.quality(hourly, fetcher.MS_PER_HOUR),
            "terminal_open_ts": fetcher.iso(terminal_ts_ms),
            "terminal_open": terminal_open,
        },
    )


def main() -> None:
    args = parse_args()
    local_audit = load_module(LOCAL_AUDIT_PATH, "shared_ma7_local_audit")
    engine = local_audit.load_module(
        local_audit.ENGINE_PATH,
        local_audit.ENGINE_SHA256,
        "shared_ma7_engine",
    )
    long_config, short_config = local_audit.load_shared_configs(engine)
    fetcher = load_module(FETCHER_PATH, "hype_v7_1_transfer_fetcher")

    dataset = fetcher.fetch_symbol_dataset(
        args.symbol,
        "perp_usdt",
        args.history_days,
        fetcher.utc_ms_now(),
    )
    daily = dataset["daily"]
    if args.start_date is not None:
        start_ms = date_to_ms(args.start_date)
        daily = [row for row in daily if row.ts >= start_ms]
    if args.end_date is not None:
        end_ms = date_to_ms(args.end_date)
        daily = [row for row in daily if row.ts <= end_ms]
    hourly = dataset["hourly"]
    funding = dataset["funding"]
    book = build_book(args.symbol, daily, hourly, fetcher)
    features = engine.build_features(book, candle_frame(hourly), funding_frame(funding))

    variants = {
        "combined": (long_config, short_config),
        "long_only": (long_config, None),
        "short_only": (None, short_config),
    }
    results: dict[str, Any] = {}
    retained: dict[str, Any] = {}
    metrics_rows: list[dict[str, Any]] = []
    for label, (long_leg, short_leg) in variants.items():
        base = engine.backtest(
            book,
            features,
            long_config=long_leg,
            short_config=short_leg,
            start_index=0,
            terminal_index=book.count,
            retain=True,
        )
        stress = engine.backtest(
            book,
            features,
            long_config=long_leg,
            short_config=short_leg,
            start_index=0,
            terminal_index=book.count,
            slippage=engine.STRESS_SLIPPAGE,
        )
        delay = engine.backtest(
            book,
            features,
            long_config=long_leg,
            short_config=short_leg,
            start_index=0,
            terminal_index=book.count,
            signal_lag=1,
        )
        results[label] = {
            "base": base.metrics,
            "stress_8bps": stress.metrics,
            "one_day_extra_delay": delay.metrics,
        }
        retained[label] = base
        for stress_label, result in (
            ("base", base),
            ("stress_8bps", stress),
            ("one_day_extra_delay", delay),
        ):
            metrics_rows.append(
                {
                    "variant": label,
                    "stress": stress_label,
                    **result.metrics,
                }
            )

    recent: list[dict[str, Any]] = []
    for variant, result in retained.items():
        recent.extend(
            {"variant": variant, **row}
            for row in engine.recent_slices(result)
        )

    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "Binance-1D-MA7-Asset-Specific-Search",
        "observation": "BTC_ETH_shared_params_zero_tuning_on_HYPE_fresh_aligned_window",
        "status": "explore / diagnostic-only / not promoted / not live-ready",
        "selection_role": (
            "shared params selected only on BTC/ETH development; "
            "HYPE not used in selection"
        ),
        "symbol": args.symbol,
        "data_source": {
            "source": "binance_fapi_public_api",
            "history_days_requested": args.history_days,
            "requested_start_date": args.start_date,
            "requested_end_date": args.end_date,
            "raw_daily_bars_retained": len(daily),
            "complete_daily_bars_used": book.count,
            "available_daily_bars": dataset["available_daily_bars"],
            "short_history": dataset["short_history"],
            "fetcher": {
                "path": str(FETCHER_PATH.relative_to(ROOT)),
                "sha256": hashlib.sha256(FETCHER_PATH.read_bytes()).hexdigest(),
            },
        },
        "shared_summary": {
            "path": str(local_audit.SUMMARY_PATH.relative_to(ROOT)),
            "sha256": local_audit.SUMMARY_SHA256,
        },
        "engine": {
            "path": str(local_audit.ENGINE_PATH.relative_to(ROOT)),
            "sha256": local_audit.ENGINE_SHA256,
        },
        "long_config": asdict(long_config),
        "short_config": asdict(short_config),
        "data_quality": {
            "daily": book.quality["daily"],
            "hourly": book.quality["hourly"],
            "funding_events": len(funding),
            "terminal_open_ts": book.quality["terminal_open_ts"],
            "terminal_open": book.quality["terminal_open"],
        },
        "results": results,
        "buy_and_hold": engine.buy_and_hold(book, features),
        "recent": recent,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{args.output_stem}_{args.run_date}"
    (ARTIFACT_DIR / f"{stem}.json").write_text(
        json.dumps(clean_json(payload), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    pd.DataFrame(metrics_rows).to_csv(ARTIFACT_DIR / f"{stem}_metrics.csv", index=False)
    pd.DataFrame(recent).to_csv(ARTIFACT_DIR / f"{stem}_recent.csv", index=False)
    pd.DataFrame(retained["combined"].trades).to_csv(
        ARTIFACT_DIR / f"{stem}_trades.csv",
        index=False,
    )
    pd.DataFrame(retained["combined"].path).to_csv(
        ARTIFACT_DIR / f"{stem}_path.csv",
        index=False,
    )
    print(json.dumps(clean_json(payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
