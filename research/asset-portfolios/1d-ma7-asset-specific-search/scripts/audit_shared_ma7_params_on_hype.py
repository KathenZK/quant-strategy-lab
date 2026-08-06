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
FAMILY_DIR = (
    ROOT / "research/asset-portfolios/1d-ma7-asset-specific-search"
)
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
SUMMARY_PATH = ARTIFACT_DIR / (
    "binance_btc_eth_1d_ma7_asset_specific_search_summary_2026-08-05.json"
)
SUMMARY_SHA256 = (
    "ecaf0d65ddc7ed114acd078656e7da948a6ed5399c1b6292d716fb91199031be"
)
ENGINE_PATH = (
    ROOT
    / "research/hype/1d-ma7-asymmetric-body-trend/scripts/"
    "search_hype_1d_ma7_separated_trend.py"
)
ENGINE_SHA256 = (
    "c376f8bd1bae814b0ba53687380ee1060cf3cc3095ae815ebb0311ed1aef59e1"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Zero-tuning transfer of BTC/ETH shared MA7 params to HYPE."
    )
    parser.add_argument(
        "--run-date",
        default=datetime.now(UTC).date().isoformat(),
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
    digest = hashlib.sha256(SUMMARY_PATH.read_bytes()).hexdigest()
    if digest != SUMMARY_SHA256:
        raise RuntimeError(
            f"shared summary drift: expected {SUMMARY_SHA256}, got {digest}"
        )
    payload = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    selected = payload["selections"]["BTC_ETH_shared"]
    return (
        engine.Config(**selected["long_config"]),
        engine.Config(**selected["short_config"]),
    )


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


def main() -> None:
    args = parse_args()
    engine = load_module(
        ENGINE_PATH,
        ENGINE_SHA256,
        "shared_ma7_hype_transfer_engine",
    )
    long_config, short_config = load_shared_configs(engine)
    if args.self_test:
        assert long_config.entry_mode == "reclaim"
        assert long_config.slope_lookback == 5
        assert short_config.entry_mode == "pullback_reclaim"
        assert short_config.max_hold_days == 10
        print("self-test: PASS")
        return

    base = engine.load_base()
    books = base.load_books()
    parent = base.load_parent()
    market_engine = parent.load_engine()
    hourly, hourly_quality = market_engine.audit_and_load_market(ROOT, "1h")
    funding, funding_quality = market_engine.load_and_audit_funding(ROOT)
    features_by_phase = {
        phase: engine.build_features(book, hourly, funding)
        for phase, book in books.items()
    }
    book = books[0]
    features = features_by_phase[0]

    variants = {
        "combined": (long_config, short_config),
        "long_only": (long_config, None),
        "short_only": (None, short_config),
    }
    metrics_rows: list[dict[str, Any]] = []
    results: dict[str, Any] = {}
    retained: dict[str, Any] = {}
    for label, (long_leg, short_leg) in variants.items():
        base_result = engine.backtest(
            book,
            features,
            long_config=long_leg,
            short_config=short_leg,
            start_index=0,
            terminal_index=book.count,
            retain=True,
        )
        stress_result = engine.backtest(
            book,
            features,
            long_config=long_leg,
            short_config=short_leg,
            start_index=0,
            terminal_index=book.count,
            slippage=engine.STRESS_SLIPPAGE,
        )
        delayed_result = engine.backtest(
            book,
            features,
            long_config=long_leg,
            short_config=short_leg,
            start_index=0,
            terminal_index=book.count,
            signal_lag=1,
        )
        results[label] = {
            "base": base_result.metrics,
            "stress_8bps": stress_result.metrics,
            "one_day_extra_delay": delayed_result.metrics,
        }
        retained[label] = base_result
        for stress, result in (
            ("base", base_result),
            ("stress_8bps", stress_result),
            ("one_day_extra_delay", delayed_result),
        ):
            metrics_rows.append(
                {
                    "variant": label,
                    "stress": stress,
                    **result.metrics,
                }
            )

    benchmark = engine.buy_and_hold(book, features)
    phase: list[dict[str, Any]] = []
    for variant, (long_leg, short_leg) in variants.items():
        phase.extend(
            {
                "variant": variant,
                **row,
            }
            for row in engine.phase_rows(
                long_leg,
                short_leg,
                books,
                features_by_phase,
            )
        )
    rolling: list[dict[str, Any]] = []
    for variant, (long_leg, short_leg) in variants.items():
        rolling.extend(
            {
                "variant": variant,
                **row,
            }
            for row in engine.rolling_rows(
                long_leg,
                short_leg,
                book,
                features,
            )
        )
    recent: list[dict[str, Any]] = []
    for variant, result in retained.items():
        recent.extend(
            {
                "variant": variant,
                **row,
            }
            for row in engine.recent_slices(result)
        )

    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "Binance-1D-MA7-Asset-Specific-Search",
        "observation": "BTC_ETH_shared_params_zero_tuning_on_HYPE",
        "status": "explore / not promoted / not live-ready",
        "selection_role": (
            "shared params selected only on BTC/ETH development; "
            "HYPE not used in this selection"
        ),
        "shared_summary": {
            "path": str(SUMMARY_PATH.relative_to(ROOT)),
            "sha256": SUMMARY_SHA256,
        },
        "engine": {
            "path": str(ENGINE_PATH.relative_to(ROOT)),
            "sha256": ENGINE_SHA256,
        },
        "long_config": asdict(long_config),
        "short_config": asdict(short_config),
        "data_quality": {
            "hourly": hourly_quality,
            "funding": funding_quality,
            "daily": book.quality,
        },
        "results": results,
        "buy_and_hold": benchmark,
        "phase": phase,
        "rolling_90d": rolling,
        "recent": recent,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = "binance_ma7_shared_params_on_hype"
    (ARTIFACT_DIR / f"{stem}_summary_{args.run_date}.json").write_text(
        json.dumps(
            clean_json(payload),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    pd.DataFrame(metrics_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_metrics_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(phase).to_csv(
        ARTIFACT_DIR / f"{stem}_phase_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(rolling).to_csv(
        ARTIFACT_DIR / f"{stem}_rolling_90d_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(recent).to_csv(
        ARTIFACT_DIR / f"{stem}_recent_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(retained["combined"].trades).to_csv(
        ARTIFACT_DIR / f"{stem}_trades_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(retained["combined"].path).to_csv(
        ARTIFACT_DIR / f"{stem}_path_{args.run_date}.csv",
        index=False,
    )
    print(json.dumps(clean_json(payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
