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
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/sox/1d-ma7-separated-trend-transfer"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
TRANSFER_PATH = FAMILY_DIR / "scripts/research_sox_1d_ma7_v1_transfer.py"
TRANSFER_SHA256 = (
    "84f08d9d83235e76e7009c46717157e784bacdf0b04945165bcccc11a42a72fb"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Zero-tuning SMA5 substitution for the SOX transfer of "
            "HYPE-1D-MA7-Asymmetric-Body-Trend-V1 rules."
        )
    )
    parser.add_argument(
        "--run-date",
        default=datetime.now(UTC).date().isoformat(),
    )
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def load_transfer() -> Any:
    digest = hashlib.sha256(TRANSFER_PATH.read_bytes()).hexdigest()
    if digest != TRANSFER_SHA256:
        raise RuntimeError(
            f"SOX transfer drift: expected {TRANSFER_SHA256}, got {digest}"
        )
    spec = importlib.util.spec_from_file_location(
        "sox_sma5_source_transfer",
        TRANSFER_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {TRANSFER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def replace_sma(
    engine: Any,
    features: Any,
    close: np.ndarray,
    window: int,
) -> Any:
    ma = (
        pd.Series(close, dtype=float)
        .rolling(window, min_periods=window)
        .mean()
        .to_numpy("float64")
    )
    return engine.Features(
        ma7=ma,
        atr7=features.atr7,
        prior_high=features.prior_high,
        prior_low=features.prior_low,
        hourly_open=features.hourly_open,
        hourly_high=features.hourly_high,
        hourly_low=features.hourly_low,
        funding_events=features.funding_events,
    )


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
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def main() -> None:
    args = parse_args()
    transfer = load_transfer()
    engine = transfer.load_engine()
    long_config, short_config = transfer.frozen_configs(engine)
    if args.self_test:
        values = np.arange(1.0, 7.0)
        template = engine.Features(
            ma7=np.full(6, np.nan),
            atr7=np.ones(6),
            prior_high={},
            prior_low={},
            hourly_open=np.ones((6, 1)),
            hourly_high=np.ones((6, 1)),
            hourly_low=np.ones((6, 1)),
            funding_events=[[] for _ in range(6)],
        )
        features = replace_sma(engine, template, values, 5)
        assert np.isnan(features.ma7[:4]).all()
        assert np.allclose(features.ma7[4:], [3.0, 4.0])
        print("self-test: PASS")
        return

    raw_path = (
        ARTIFACT_DIR / f"sox_yahoo_chart_1d_raw_{args.run_date}.json"
    )
    content = transfer.fetch_yahoo(raw_path, refresh=False)
    frame, quality = transfer.parse_and_audit_yahoo(content)
    book, features_sma7 = transfer.build_book_and_features(
        engine,
        frame,
        quality,
    )
    features_sma5 = replace_sma(
        engine,
        features_sma7,
        book.close,
        5,
    )
    local_dates = np.asarray(
        pd.DatetimeIndex(book.ts)
        .tz_convert(quality["exchange_timezone"])
        .date
    )
    overlap_start = int(
        np.searchsorted(
            local_dates,
            transfer.HYPE_OVERLAP_START,
            side="left",
        )
    )
    overlap_end = int(
        np.searchsorted(
            local_dates,
            transfer.HYPE_OVERLAP_END,
            side="left",
        )
    )
    windows = {
        "full_available": (0, book.count),
        "hype_calendar_overlap": (overlap_start, overlap_end),
    }
    payload: dict[str, Any] = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "SOX-1D-MA7-Separated-Trend-Transfer",
        "source_version": (
            "HYPE-1D-MA7-Asymmetric-Body-Trend-V1"
        ),
        "status": "explore / not promoted / not live-ready",
        "substitution": (
            "SMA7 -> SMA5; ATR7 and all V1 state-machine parameters "
            "unchanged"
        ),
        "source_transfer": {
            "path": str(TRANSFER_PATH.relative_to(ROOT)),
            "sha256": TRANSFER_SHA256,
        },
        "data_quality": quality,
        "long_config": asdict(long_config),
        "short_config": asdict(short_config),
        "indicators": {},
    }
    metric_rows: list[dict[str, Any]] = []
    recent_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    path_rows: list[dict[str, Any]] = []
    annual_rows: list[dict[str, Any]] = []
    rolling_rows: list[dict[str, Any]] = []
    for indicator, features in (
        ("SMA7_baseline", features_sma7),
        ("SMA5_substitution", features_sma5),
    ):
        indicator_payload: dict[str, Any] = {"windows": {}}
        for window, (start, end) in windows.items():
            audit = transfer.audit_window(
                engine,
                book,
                features,
                long_config,
                short_config,
                start=start,
                end=end,
            )
            results = audit["_results"]
            indicator_payload["windows"][window] = audit
            for variant, metrics in audit.items():
                if isinstance(metrics, dict) and variant != "_results":
                    metric_rows.append(
                        {
                            "indicator": indicator,
                            "window": window,
                            "variant": variant,
                            **metrics,
                        }
                    )
            if window == "full_available":
                for variant in ("combined", "long_only", "short_only"):
                    result = results[variant]
                    recent_rows.extend(
                        {
                            "indicator": indicator,
                            "variant": variant,
                            **row,
                        }
                        for row in engine.recent_slices(result)
                    )
                    if indicator == "SMA5_substitution":
                        trade_rows.extend(
                            {"variant": variant, **trade}
                            for trade in result.trades
                        )
                if indicator == "SMA5_substitution":
                    path_rows.extend(results["combined"].path)
        annual = transfer.calendar_year_rows(
            engine,
            book,
            features,
            long_config,
            short_config,
        )
        rolling = transfer.rolling_three_year_rows(
            engine,
            book,
            features,
            long_config,
            short_config,
        )
        annual_rows.extend(
            {"indicator": indicator, **row} for row in annual
        )
        rolling_rows.extend(
            {"indicator": indicator, **row} for row in rolling
        )
        indicator_payload["stability"] = {
            "calendar_years": {
                "count": len(annual),
                "positive": sum(
                    row["net_return_pct"] > 0.0 for row in annual
                ),
                "median_return_pct": float(
                    np.median([
                        row["net_return_pct"] for row in annual
                    ])
                ),
            },
            "rolling_3y": {
                "count": len(rolling),
                "positive": sum(
                    row["net_return_pct"] > 0.0 for row in rolling
                ),
                "min_return_pct": min(
                    row["net_return_pct"] for row in rolling
                ),
                "median_return_pct": float(
                    np.median([
                        row["net_return_pct"] for row in rolling
                    ])
                ),
            },
        }
        payload["indicators"][indicator] = indicator_payload

    stem = "sox_1d_sma5_substitution"
    clean_payload = clean_json(payload)
    (ARTIFACT_DIR / f"{stem}_summary_{args.run_date}.json").write_text(
        json.dumps(
            clean_payload,
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
    pd.DataFrame(path_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_path_{args.run_date}.csv",
        index=False,
    )
    print(
        json.dumps(
            {
                indicator: {
                    "full": data["windows"]["full_available"],
                    "overlap": data["windows"][
                        "hype_calendar_overlap"
                    ],
                    "stability": data["stability"],
                }
                for indicator, data in clean_payload[
                    "indicators"
                ].items()
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
