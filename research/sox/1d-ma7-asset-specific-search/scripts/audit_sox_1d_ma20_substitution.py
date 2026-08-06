from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/sox/1d-ma7-asset-specific-search"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
SEARCH_PATH = FAMILY_DIR / "scripts/search_sox_1d_ma7_asset_specific.py"
SEARCH_SHA256 = (
    "e9ed3ba92cbd0ac7ef0347a127d8f985cedb14767d89520fdb6d6905bc78f95d"
)
SOURCE_SUMMARY_PATH = (
    ARTIFACT_DIR
    / "sox_1d_ma7_asset_specific_search_summary_2026-08-05.json"
)
SOURCE_SUMMARY_SHA256 = (
    "5e574beb5dabc0219078f7f03eed67d0e6e18ffb5f6fcc7dd4d74bcc6f844ae7"
)
SMA_WINDOW = 20


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Zero-tuning SMA7 to SMA20 substitution for the frozen "
            "SOX development-selected configurations."
        )
    )
    parser.add_argument(
        "--run-date",
        default=datetime.now(UTC).date().isoformat(),
    )
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def load_search() -> Any:
    digest = hashlib.sha256(SEARCH_PATH.read_bytes()).hexdigest()
    if digest != SEARCH_SHA256:
        raise RuntimeError(
            f"SOX search drift: expected {SEARCH_SHA256}, got {digest}"
        )
    spec = importlib.util.spec_from_file_location(
        "sox_ma20_source_search",
        SEARCH_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {SEARCH_PATH}")
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


def load_source_selections(engine: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    digest = hashlib.sha256(SOURCE_SUMMARY_PATH.read_bytes()).hexdigest()
    if digest != SOURCE_SUMMARY_SHA256:
        raise RuntimeError(
            f"source summary drift: expected {SOURCE_SUMMARY_SHA256}, got {digest}"
        )
    payload = json.loads(SOURCE_SUMMARY_PATH.read_text(encoding="utf-8"))
    audits = payload["audits"]
    selections: dict[str, Any] = {}
    for label in (
        "sox_development_combined",
        "sox_development_long_only",
        "sox_development_short_only",
    ):
        source = audits[label]
        selections[label] = (
            (
                None
                if source["long_config"] is None
                else engine.Config(**source["long_config"])
            ),
            (
                None
                if source["short_config"] is None
                else engine.Config(**source["short_config"])
            ),
        )
    return payload, selections


def main() -> None:
    args = parse_args()
    search = load_search()
    sox = search.load_module(
        search.SOX_HELPER_PATH,
        search.SOX_HELPER_SHA256,
        "sox_ma20_substitution_helper",
    )
    engine = sox.load_engine()
    engine.STRESS_SLIPPAGE = search.ILLUSTRATIVE_FRICTION
    source_payload, selections = load_source_selections(engine)
    if args.self_test:
        template = engine.Features(
            ma7=np.full(21, np.nan),
            atr7=np.ones(21),
            prior_high={},
            prior_low={},
            hourly_open=np.ones((21, 1)),
            hourly_high=np.ones((21, 1)),
            hourly_low=np.ones((21, 1)),
            funding_events=[[] for _ in range(21)],
        )
        features = replace_sma(
            engine,
            template,
            np.arange(1.0, 22.0),
            SMA_WINDOW,
        )
        assert np.isnan(features.ma7[:19]).all()
        assert np.allclose(features.ma7[19:], [10.5, 11.5])
        assert selections["sox_development_combined"][0] is not None
        print("self-test: PASS")
        return

    raw_digest = hashlib.sha256(search.RAW_PATH.read_bytes()).hexdigest()
    if raw_digest != search.RAW_SHA256:
        raise RuntimeError(
            f"SOX raw drift: expected {search.RAW_SHA256}, got {raw_digest}"
        )
    frame, quality = sox.parse_and_audit_yahoo(search.RAW_PATH.read_bytes())
    book, base_features = sox.build_book_and_features(
        engine,
        frame,
        quality,
    )
    search_features = search.augment_search_features(
        engine,
        book,
        base_features,
    )
    ma20_features = replace_sma(
        engine,
        search_features,
        book.close,
        SMA_WINDOW,
    )
    windows = search.window_indices(book)

    audits: dict[str, Any] = {}
    retained: dict[str, Any] = {}
    metric_rows: list[dict[str, Any]] = []
    calendar_rows: list[dict[str, Any]] = []
    rolling_rows: list[dict[str, Any]] = []
    recent_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    for source_label, (long_config, short_config) in selections.items():
        label = source_label.replace(
            "sox_development_",
            "sox_ma20_",
        )
        audit, full_result = search.audit_selection(
            sox,
            engine,
            label,
            long_config,
            short_config,
            book,
            ma20_features,
            windows,
        )
        audits[label] = audit
        retained[label] = full_result
        for window, stresses in audit["windows"].items():
            for stress, metrics in stresses.items():
                if stress == "buy_and_hold":
                    continue
                metric_rows.append(
                    {
                        "selection": label,
                        "window": window,
                        "stress": stress,
                        **metrics,
                    }
                )
        calendar_rows.extend(
            {
                "selection": label,
                **row,
            }
            for row in sox.calendar_year_rows(
                engine,
                book,
                ma20_features,
                long_config,
                short_config,
            )
        )
        rolling_rows.extend(
            {
                "selection": label,
                **row,
            }
            for row in sox.rolling_three_year_rows(
                engine,
                book,
                ma20_features,
                long_config,
                short_config,
            )
        )
        recent_rows.extend(
            {
                "selection": label,
                **row,
            }
            for row in engine.recent_slices(full_result)
        )
        trade_rows.extend(
            {
                "selection": label,
                **trade,
            }
            for trade in full_result.trades
        )

    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "SOX-1D-MA7-Asset-Specific-Search",
        "status": "explore / not promoted / not live-ready",
        "substitution": (
            "SMA7 -> SMA20; ATR7 and all frozen "
            "development-selected parameters unchanged"
        ),
        "selection": (
            "zero tuning; no SMA20 result used to choose parameters"
        ),
        "source": {
            "search_script_path": str(SEARCH_PATH.relative_to(ROOT)),
            "search_script_sha256": SEARCH_SHA256,
            "search_summary_path": str(
                SOURCE_SUMMARY_PATH.relative_to(ROOT)
            ),
            "search_summary_sha256": SOURCE_SUMMARY_SHA256,
            "raw_path": str(search.RAW_PATH.relative_to(ROOT)),
            "raw_sha256": search.RAW_SHA256,
        },
        "data_quality": quality,
        "source_ma7_audits": {
            label: source_payload["audits"][label]
            for label in selections
        },
        "ma20_audits": audits,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = "sox_1d_ma20_substitution"
    (ARTIFACT_DIR / f"{stem}_summary_{args.run_date}.json").write_text(
        json.dumps(
            search.clean_json(payload),
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
    pd.DataFrame(calendar_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_calendar_years_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(rolling_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_rolling_3y_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(recent_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_recent_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(trade_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_trades_{args.run_date}.csv",
        index=False,
    )
    for label, result in retained.items():
        pd.DataFrame(result.path).to_csv(
            ARTIFACT_DIR / f"{stem}_{label}_path_{args.run_date}.csv",
            index=False,
        )
    print(
        json.dumps(
            search.clean_json(audits),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
