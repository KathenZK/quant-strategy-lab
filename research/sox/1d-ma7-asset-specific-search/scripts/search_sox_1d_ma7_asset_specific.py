from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, date, datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import random
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/sox/1d-ma7-asset-specific-search"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
SOX_HELPER_PATH = (
    ROOT
    / "research/sox/1d-ma7-separated-trend-transfer/scripts/"
    "research_sox_1d_ma7_v1_transfer.py"
)
SOX_HELPER_SHA256 = (
    "84f08d9d83235e76e7009c46717157e784bacdf0b04945165bcccc11a42a72fb"
)
RAW_PATH = (
    ROOT
    / "research/sox/1d-ma7-separated-trend-transfer/artifacts/"
    "sox_yahoo_chart_1d_raw_2026-08-05.json"
)
RAW_SHA256 = (
    "402440c9129f65f828074089386d52c06d0c76ada67528af7a1ac96a0d5a5e4e"
)
SHARED_SUMMARY_PATH = (
    ROOT
    / "research/asset-portfolios/1d-ma7-asset-specific-search/artifacts/"
    "binance_btc_eth_1d_ma7_asset_specific_search_summary_2026-08-05.json"
)
SHARED_SUMMARY_SHA256 = (
    "ecaf0d65ddc7ed114acd078656e7da948a6ed5399c1b6292d716fb91199031be"
)
DEVELOPMENT_START = date(2010, 1, 4)
HOLDOUT_START = date(2021, 1, 4)
DEFAULT_SEED = 20260805
DEFAULT_SAMPLES = 8_000
DEFAULT_SHORTLIST = 120
DEFAULT_PAIR_POOL = 20
ILLUSTRATIVE_FRICTION = 0.001


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Test shared MA7 params on ^SOX and, if negative, search "
            "SOX-specific daily MA7 parameters."
        )
    )
    parser.add_argument(
        "--run-date",
        default=datetime.now(UTC).date().isoformat(),
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--samples-per-side",
        type=int,
        default=DEFAULT_SAMPLES,
    )
    parser.add_argument(
        "--shortlist",
        type=int,
        default=DEFAULT_SHORTLIST,
    )
    parser.add_argument(
        "--pair-pool",
        type=int,
        default=DEFAULT_PAIR_POOL,
    )
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


def augment_search_features(engine: Any, book: Any, features: Any) -> Any:
    windows = (2, 3, 5, 7, 10, 14)
    return engine.Features(
        ma7=features.ma7,
        atr7=features.atr7,
        prior_high={
            window: pd.Series(book.high)
            .shift(1)
            .rolling(window, min_periods=window)
            .max()
            .to_numpy("float64")
            for window in windows
        },
        prior_low={
            window: pd.Series(book.low)
            .shift(1)
            .rolling(window, min_periods=window)
            .min()
            .to_numpy("float64")
            for window in windows
        },
        hourly_open=features.hourly_open,
        hourly_high=features.hourly_high,
        hourly_low=features.hourly_low,
        funding_events=features.funding_events,
    )


def window_indices(book: Any) -> dict[str, tuple[int, int]]:
    local_dates = np.asarray(
        pd.DatetimeIndex(book.ts)
        .tz_convert(book.quality["exchange_timezone"])
        .date
    )
    development_start = int(
        np.searchsorted(local_dates, DEVELOPMENT_START, side="left")
    )
    holdout_start = int(
        np.searchsorted(local_dates, HOLDOUT_START, side="left")
    )
    if not (500 < development_start < holdout_start - 2_000):
        raise RuntimeError("invalid SOX development boundaries")
    if holdout_start >= book.count - 500:
        raise RuntimeError("insufficient exposed holdout")
    return {
        "backward_pre_2010": (0, development_start),
        "development_2010_2020": (development_start, holdout_start),
        "researcher_exposed_holdout_2021_plus": (
            holdout_start,
            book.count,
        ),
        "full_available": (0, book.count),
    }


def audit_selection(
    sox: Any,
    engine: Any,
    label: str,
    long_config: Any | None,
    short_config: Any | None,
    book: Any,
    features: Any,
    windows: dict[str, tuple[int, int]],
) -> tuple[dict[str, Any], Any]:
    output: dict[str, Any] = {
        "label": label,
        "long_config": (
            None if long_config is None else asdict(long_config)
        ),
        "short_config": (
            None if short_config is None else asdict(short_config)
        ),
        "windows": {},
    }
    full_result = None
    for window, (start, end) in windows.items():
        base = sox.run_variant(
            engine,
            book,
            features,
            long_config,
            short_config,
            start=start,
            end=end,
        )
        friction = sox.run_variant(
            engine,
            book,
            features,
            long_config,
            short_config,
            start=start,
            end=end,
            friction=ILLUSTRATIVE_FRICTION,
        )
        delayed = sox.run_variant(
            engine,
            book,
            features,
            long_config,
            short_config,
            start=start,
            end=end,
            signal_lag=1,
        )
        output["windows"][window] = {
            "base": base.metrics,
            "illustrative_10bps_per_fill": friction.metrics,
            "one_session_extra_delay": delayed.metrics,
            "buy_and_hold": sox.buy_and_hold(
                engine,
                book,
                features,
                start,
                end,
            ),
        }
        if window == "full_available":
            full_result = base
    if full_result is None:
        raise RuntimeError("full result missing")
    return output, full_result


def top_config_rows(
    frame: pd.DataFrame,
    *,
    side: str,
    limit: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rank, row in enumerate(
        frame.sort_values("robust_score", ascending=False)
        .head(limit)
        .itertuples(index=False),
        start=1,
    ):
        values = row._asdict()
        config = values.pop("config")
        rows.append(
            {
                "side": side,
                "rank": rank,
                "config_json": json.dumps(
                    asdict(config),
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                **values,
            }
        )
    return rows


def top_pair_rows(frame: pd.DataFrame, limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rank, row in enumerate(
        frame.head(limit).itertuples(index=False),
        start=1,
    ):
        values = row._asdict()
        long_config = values.pop("long_config")
        short_config = values.pop("short_config")
        rows.append(
            {
                "rank": rank,
                "long_config_json": json.dumps(
                    asdict(long_config),
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "short_config_json": json.dumps(
                    asdict(short_config),
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                **values,
            }
        )
    return rows


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: clean_json(item) for key, item in value.items()}
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
        "sox_ma7_asset_search_helper",
    )
    engine = sox.load_engine()
    engine.STRESS_SLIPPAGE = ILLUSTRATIVE_FRICTION
    shared_long, shared_short = load_shared_configs(engine)
    if args.self_test:
        assert shared_long.slope_lookback == 5
        assert shared_short.entry_mode == "pullback_reclaim"
        assert DEVELOPMENT_START < HOLDOUT_START
        print("self-test: PASS")
        return

    raw_digest = hashlib.sha256(RAW_PATH.read_bytes()).hexdigest()
    if raw_digest != RAW_SHA256:
        raise RuntimeError(
            f"SOX raw drift: expected {RAW_SHA256}, got {raw_digest}"
        )
    frame, quality = sox.parse_and_audit_yahoo(RAW_PATH.read_bytes())
    book, base_features = sox.build_book_and_features(
        engine,
        frame,
        quality,
    )
    features = augment_search_features(engine, book, base_features)
    windows = window_indices(book)

    shared_audit, shared_result = audit_selection(
        sox,
        engine,
        "btc_eth_shared_zero_tuning",
        shared_long,
        shared_short,
        book,
        features,
        windows,
    )
    shared_positive = (
        shared_audit["windows"]["full_available"]["base"][
            "net_return_pct"
        ]
        > 0.0
    )

    selections: dict[str, tuple[Any | None, Any | None]] = {}
    long_stable = pd.DataFrame()
    short_stable = pd.DataFrame()
    pairs = pd.DataFrame()
    if not shared_positive:
        dev_start, dev_end = windows["development_2010_2020"]
        dev_book, dev_features = sox.window_book_features(
            book,
            features,
            dev_start,
            dev_end,
        )
        dev_features = augment_search_features(
            engine,
            dev_book,
            dev_features,
        )
        rng = random.Random(args.seed)
        long_configs = engine.unique_configs(
            1,
            rng,
            args.samples_per_side,
        )
        short_configs = engine.unique_configs(
            -1,
            rng,
            args.samples_per_side,
        )
        print("SOX long stage1", flush=True)
        long_stage1 = engine.stage1_search(
            long_configs,
            dev_book,
            dev_features,
            end=dev_book.count,
        )
        print("SOX short stage1", flush=True)
        short_stage1 = engine.stage1_search(
            short_configs,
            dev_book,
            dev_features,
            end=dev_book.count,
        )
        long_shortlist = list(
            long_stage1.sort_values("score", ascending=False)
            .head(args.shortlist)["config"]
        )
        short_shortlist = list(
            short_stage1.sort_values("score", ascending=False)
            .head(args.shortlist)["config"]
        )
        long_stable = engine.rank_stable(
            engine.stability_audit(
                long_shortlist,
                dev_book,
                dev_features,
                prefit_end=dev_book.count,
            ),
            args.shortlist,
        )
        short_stable = engine.rank_stable(
            engine.stability_audit(
                short_shortlist,
                dev_book,
                dev_features,
                prefit_end=dev_book.count,
            ),
            args.shortlist,
        )
        long_pool = list(
            long_stable.head(args.pair_pool)["config"]
        )
        short_pool = list(
            short_stable.head(args.pair_pool)["config"]
        )
        pairs = engine.pair_search(
            long_pool,
            short_pool,
            dev_book,
            dev_features,
            prefit_end=dev_book.count,
        )
        primary_pair = pairs.iloc[0]
        selections = {
            "sox_development_combined": (
                primary_pair["long_config"],
                primary_pair["short_config"],
            ),
            "sox_development_long_only": (
                long_stable.iloc[0]["config"],
                None,
            ),
            "sox_development_short_only": (
                None,
                short_stable.iloc[0]["config"],
            ),
        }

    audits: dict[str, Any] = {
        "btc_eth_shared_zero_tuning": shared_audit,
    }
    retained = {
        "btc_eth_shared_zero_tuning": shared_result,
    }
    for label, (long_config, short_config) in selections.items():
        audit, result = audit_selection(
            sox,
            engine,
            label,
            long_config,
            short_config,
            book,
            features,
            windows,
        )
        audits[label] = audit
        retained[label] = result

    metric_rows: list[dict[str, Any]] = []
    calendar_rows: list[dict[str, Any]] = []
    rolling_rows: list[dict[str, Any]] = []
    recent_rows: list[dict[str, Any]] = []
    for label, audit in audits.items():
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
        long_config = (
            shared_long
            if label == "btc_eth_shared_zero_tuning"
            else selections[label][0]
        )
        short_config = (
            shared_short
            if label == "btc_eth_shared_zero_tuning"
            else selections[label][1]
        )
        calendar_rows.extend(
            {
                "selection": label,
                **row,
            }
            for row in sox.calendar_year_rows(
                engine,
                book,
                features,
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
                features,
                long_config,
                short_config,
            )
        )
        recent_rows.extend(
            {
                "selection": label,
                **row,
            }
            for row in engine.recent_slices(retained[label])
        )

    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "SOX-1D-MA7-Asset-Specific-Search",
        "status": "explore / not promoted / not live-ready",
        "instrument": {
            "symbol": "^SOX",
            "identity": "PHLX Semiconductor price index",
            "tradability": "not directly tradable",
            "primary_cost_model": "zero cost diagnostic",
            "illustrative_friction_per_fill": ILLUSTRATIVE_FRICTION,
        },
        "data_quality": quality,
        "contract": {
            "indicator": "fixed SMA7 and ATR7",
            "shared_control_first": True,
            "shared_control_positive": shared_positive,
            "search_triggered": not shared_positive,
            "seed": args.seed,
            "samples_per_side": args.samples_per_side,
            "shortlist_per_side": args.shortlist,
            "pair_pool_per_side": args.pair_pool,
            "development_start": DEVELOPMENT_START.isoformat(),
            "holdout_start": HOLDOUT_START.isoformat(),
            "selection_data": "development_2010_2020 only",
            "holdout_role": (
                "researcher-exposed; excluded from current selection"
            ),
        },
        "source": {
            "sox_helper_path": str(SOX_HELPER_PATH.relative_to(ROOT)),
            "sox_helper_sha256": SOX_HELPER_SHA256,
            "raw_path": str(RAW_PATH.relative_to(ROOT)),
            "raw_sha256": RAW_SHA256,
            "shared_summary_path": str(
                SHARED_SUMMARY_PATH.relative_to(ROOT)
            ),
            "shared_summary_sha256": SHARED_SUMMARY_SHA256,
        },
        "windows": {
            label: {
                "start_index": start,
                "end_index": end,
            }
            for label, (start, end) in windows.items()
        },
        "audits": audits,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = "sox_1d_ma7_asset_specific_search"
    (ARTIFACT_DIR / f"{stem}_summary_{args.run_date}.json").write_text(
        json.dumps(
            clean_json(payload),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    if not shared_positive:
        frontier = [
            *top_config_rows(
                long_stable,
                side="long",
                limit=args.shortlist,
            ),
            *top_config_rows(
                short_stable,
                side="short",
                limit=args.shortlist,
            ),
        ]
        pd.DataFrame(frontier).to_csv(
            ARTIFACT_DIR / f"{stem}_frontier_{args.run_date}.csv",
            index=False,
        )
        pd.DataFrame(
            top_pair_rows(pairs, args.shortlist)
        ).to_csv(
            ARTIFACT_DIR / f"{stem}_pairs_{args.run_date}.csv",
            index=False,
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
    trade_rows: list[dict[str, Any]] = []
    for label, result in retained.items():
        trade_rows.extend(
            {
                "selection": label,
                **trade,
            }
            for trade in result.trades
        )
        pd.DataFrame(result.path).to_csv(
            ARTIFACT_DIR
            / f"{stem}_{label}_path_{args.run_date}.csv",
            index=False,
        )
    pd.DataFrame(trade_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_trades_{args.run_date}.csv",
        index=False,
    )
    print(json.dumps(clean_json(payload["audits"]), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
