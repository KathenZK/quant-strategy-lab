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
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
ENGINE_PATH = FAMILY_DIR / "scripts/search_hype_1d_ma7_separated_trend.py"
ENGINE_SHA256 = (
    "c376f8bd1bae814b0ba53687380ee1060cf3cc3095ae815ebb0311ed1aef59e1"
)
BASE_PATH = (
    FAMILY_DIR / "scripts/research_hype_1d_ma7_asymmetric_body_trend.py"
)
BASE_SHA256 = (
    "05d76943a671d1463f8950f1f6e317d8653831fd0f72ea825a039caa1fb2a386"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Zero-tuning EMA7 substitution audit for "
            "HYPE-1D-MA7-Asymmetric-Body-Trend-V1."
        )
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


def frozen_configs(engine: Any) -> tuple[Any, Any]:
    long_config = engine.Config(
        side=1,
        entry_mode="reclaim",
        slope_lookback=1,
        slope_min_atr=0.02,
        confirm_days=1,
        entry_buffer_atr=0.0,
        pullback_lookback=5,
        pullback_touch_atr=0.0,
        breakout_lookback=2,
        exit_confirm_days=1,
        exit_buffer_atr=0.75,
        slope_exit_lookback=0,
        hard_stop_atr=0.0,
        trail_atr=1.5,
        max_hold_days=90,
        cooldown_days=2,
    )
    short_config = engine.Config(
        side=-1,
        entry_mode="reclaim",
        slope_lookback=2,
        slope_min_atr=0.02,
        confirm_days=1,
        entry_buffer_atr=0.1,
        pullback_lookback=10,
        pullback_touch_atr=0.0,
        breakout_lookback=5,
        exit_confirm_days=1,
        exit_buffer_atr=0.25,
        slope_exit_lookback=1,
        hard_stop_atr=1.5,
        trail_atr=4.0,
        max_hold_days=20,
        cooldown_days=5,
    )
    return long_config, short_config


def load_inputs(engine: Any, base: Any) -> tuple[
    dict[int, Any],
    pd.DataFrame,
    pd.DataFrame,
]:
    parent = base.load_parent()
    data_engine = parent.load_engine()
    hourly, hourly_quality = data_engine.audit_and_load_market(ROOT, "1h")
    funding, funding_quality = data_engine.load_and_audit_funding(ROOT)
    books = {
        phase: base.build_book(
            parent,
            hourly,
            hourly_quality,
            funding,
            funding_quality,
            phase_hours=phase,
        )
        for phase in (0, 12)
    }
    return books, hourly, funding


def ema(values: np.ndarray, span: int) -> np.ndarray:
    return (
        pd.Series(values, dtype=float)
        .ewm(span=span, adjust=False, min_periods=span)
        .mean()
        .to_numpy("float64")
    )


def replace_ma(engine: Any, features: Any, values: np.ndarray) -> Any:
    return engine.Features(
        ma7=values,
        atr7=features.atr7,
        prior_high=features.prior_high,
        prior_low=features.prior_low,
        hourly_open=features.hourly_open,
        hourly_high=features.hourly_high,
        hourly_low=features.hourly_low,
        funding_events=features.funding_events,
    )


def run(
    engine: Any,
    book: Any,
    features: Any,
    long_config: Any | None,
    short_config: Any | None,
    *,
    start: int,
    end: int,
    retain: bool = False,
    slippage: float | None = None,
    signal_lag: int = 0,
) -> Any:
    kwargs: dict[str, Any] = {}
    if slippage is not None:
        kwargs["slippage"] = slippage
    return engine.backtest(
        book,
        features,
        long_config=long_config,
        short_config=short_config,
        start_index=start,
        terminal_index=end,
        signal_lag=signal_lag,
        retain=retain,
        **kwargs,
    )


def audit_indicator(
    engine: Any,
    label: str,
    book: Any,
    features: Any,
    long_config: Any,
    short_config: Any,
    *,
    prefit_end: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    windows = {
        "prefit": (0, prefit_end),
        "last_90d_flat": (prefit_end, book.count),
        "full": (0, book.count),
    }
    payload: dict[str, Any] = {"windows": {}}
    metric_rows: list[dict[str, Any]] = []
    for window, (start, end) in windows.items():
        variants = {
            "combined": (long_config, short_config),
            "long_only": (long_config, None),
            "short_only": (None, short_config),
        }
        retained: dict[str, Any] = {}
        for variant, (long_leg, short_leg) in variants.items():
            result = run(
                engine,
                book,
                features,
                long_leg,
                short_leg,
                start=start,
                end=end,
                retain=window == "full",
            )
            payload["windows"].setdefault(window, {})[variant] = (
                result.metrics
            )
            metric_rows.append(
                {
                    "indicator": label,
                    "window": window,
                    "variant": variant,
                    **result.metrics,
                }
            )
            if window == "full":
                retained[variant] = result
        if window == "full":
            payload["_retained"] = retained
    stress = run(
        engine,
        book,
        features,
        long_config,
        short_config,
        start=0,
        end=book.count,
        slippage=engine.STRESS_SLIPPAGE,
    )
    delayed = run(
        engine,
        book,
        features,
        long_config,
        short_config,
        start=0,
        end=book.count,
        signal_lag=1,
    )
    payload["stress_8bps"] = stress.metrics
    payload["one_day_extra_delay"] = delayed.metrics
    for variant, result in (
        ("stress_8bps", stress),
        ("one_day_extra_delay", delayed),
    ):
        metric_rows.append(
            {
                "indicator": label,
                "window": "full",
                "variant": variant,
                **result.metrics,
            }
        )
    return payload, metric_rows


def phase_audit(
    engine: Any,
    indicator: str,
    books: dict[int, Any],
    features: dict[int, Any],
    long_config: Any,
    short_config: Any,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for variant, long_leg, short_leg in (
        ("combined", long_config, short_config),
        ("long_only", long_config, None),
        ("short_only", None, short_config),
    ):
        rows.extend(
            {
                "indicator": indicator,
                "variant": variant,
                **row,
            }
            for row in engine.phase_rows(
                long_leg,
                short_leg,
                books,
                features,
            )
        )
    return rows


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: clean_json(item)
            for key, item in value.items()
            if key != "_retained"
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
    engine = load_module(
        ENGINE_PATH,
        ENGINE_SHA256,
        "hype_v1_ema7_engine",
    )
    base = load_module(
        BASE_PATH,
        BASE_SHA256,
        "hype_v1_ema7_base",
    )
    long_config, short_config = frozen_configs(engine)
    if args.self_test:
        values = np.arange(1.0, 9.0)
        output = ema(values, 7)
        assert np.isnan(output[:6]).all()
        assert np.isfinite(output[6:]).all()
        assert long_config.side == 1 and short_config.side == -1
        print("self-test: PASS")
        return

    books, hourly, funding = load_inputs(engine, base)
    features_sma = {
        phase: engine.build_features(book, hourly, funding)
        for phase, book in books.items()
    }
    features_ema = {
        phase: replace_ma(
            engine,
            features_sma[phase],
            ema(book.close, 7),
        )
        for phase, book in books.items()
    }
    book = books[0]
    prefit_end = int(
        book.ts.searchsorted(engine.HOLDOUT_START, side="left")
    )
    if pd.Timestamp(book.ts[prefit_end]) != engine.HOLDOUT_START:
        raise RuntimeError("HYPE holdout boundary unavailable")

    payload: dict[str, Any] = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "HYPE-1D-MA7-Asymmetric-Body-Trend",
        "source_version": (
            "HYPE-1D-MA7-Asymmetric-Body-Trend-V1"
        ),
        "status": "registered V1 unchanged; EMA7 diagnostic only",
        "substitution": (
            "SMA7 -> EMA(span=7, adjust=False, min_periods=7); "
            "all V1 rules and ATR7 unchanged"
        ),
        "source_engine": {
            "path": str(ENGINE_PATH.relative_to(ROOT)),
            "sha256": ENGINE_SHA256,
            "base_path": str(BASE_PATH.relative_to(ROOT)),
            "base_sha256": BASE_SHA256,
        },
        "long_config": asdict(long_config),
        "short_config": asdict(short_config),
        "data_quality": book.quality,
        "indicators": {},
    }
    all_metrics: list[dict[str, Any]] = []
    retained: dict[str, dict[str, Any]] = {}
    for label, features in (
        ("SMA7_V1_baseline", features_sma[0]),
        ("EMA7_substitution", features_ema[0]),
    ):
        audit, rows = audit_indicator(
            engine,
            label,
            book,
            features,
            long_config,
            short_config,
            prefit_end=prefit_end,
        )
        retained[label] = audit["_retained"]
        payload["indicators"][label] = audit
        all_metrics.extend(rows)

    phase_rows = [
        *phase_audit(
            engine,
            "SMA7_V1_baseline",
            books,
            features_sma,
            long_config,
            short_config,
        ),
        *phase_audit(
            engine,
            "EMA7_substitution",
            books,
            features_ema,
            long_config,
            short_config,
        ),
    ]
    recent_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    for indicator, variants in retained.items():
        for variant, result in variants.items():
            recent_rows.extend(
                {
                    "indicator": indicator,
                    "variant": variant,
                    **row,
                }
                for row in engine.recent_slices(result)
            )
            if indicator == "EMA7_substitution":
                trade_rows.extend(
                    {"variant": variant, **trade}
                    for trade in result.trades
                )
    rolling_rows: list[dict[str, Any]] = []
    for label, features in (
        ("SMA7_V1_baseline", features_sma[0]),
        ("EMA7_substitution", features_ema[0]),
    ):
        for variant, long_leg, short_leg in (
            ("combined", long_config, short_config),
            ("long_only", long_config, None),
            ("short_only", None, short_config),
        ):
            rolling_rows.extend(
                {
                    "indicator": label,
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
    benchmark = engine.buy_and_hold(book, features_sma[0])
    payload["buy_and_hold"] = benchmark
    payload["phase_audit"] = phase_rows
    payload["rolling_90d"] = {
        label: {
            variant: {
                "count": len(rows),
                "positive": sum(
                    row["net_return_pct"] > 0.0 for row in rows
                ),
                "median_return_pct": float(
                    np.median([
                        row["net_return_pct"] for row in rows
                    ])
                ),
            }
            for variant in ("combined", "long_only", "short_only")
            for rows in [[
                row
                for row in rolling_rows
                if row["indicator"] == label
                and row["variant"] == variant
            ]]
        }
        for label in ("SMA7_V1_baseline", "EMA7_substitution")
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = "hype_1d_v1_ema7_substitution"
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
    pd.DataFrame(all_metrics).to_csv(
        ARTIFACT_DIR / f"{stem}_metrics_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(recent_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_recent_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(phase_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_phase_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(rolling_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_rolling_90d_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(trade_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_trades_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(
        retained["EMA7_substitution"]["combined"].path
    ).to_csv(
        ARTIFACT_DIR / f"{stem}_path_{args.run_date}.csv",
        index=False,
    )
    print(
        json.dumps(
            {
                "SMA7": clean_payload["indicators"][
                    "SMA7_V1_baseline"
                ]["windows"]["full"],
                "EMA7": clean_payload["indicators"][
                    "EMA7_substitution"
                ]["windows"]["full"],
                "EMA7_stress": clean_payload["indicators"][
                    "EMA7_substitution"
                ]["stress_8bps"],
                "EMA7_delay": clean_payload["indicators"][
                    "EMA7_substitution"
                ]["one_day_extra_delay"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
