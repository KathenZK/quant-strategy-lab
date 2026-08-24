from __future__ import annotations

import argparse
from dataclasses import replace
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
TIMING_PATH = (
    FAMILY_DIR
    / "scripts/audit_hype_1d_ma7_abt_v4_short_entry_timing.py"
)
TIMING_SHA256 = (
    "d221c0d51db2bfd206bf3b0709d7fb51762a3029ba7b39df937d609fefe54926"
)
CONTRACT = "specs/hype-1d-ma7-abt-v4-flat-regime-entry-contract-2026-08-07.md"
HOLDOUT_START = pd.Timestamp("2026-05-01T00:00:00Z")
V4_CONTROL = "V4_CONTROL"
FLAT_REGIME_ENTRY = "FLAT_REGIME_ENTRY"
VARIANTS = (V4_CONTROL, FLAT_REGIME_ENTRY)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit symmetric flat-state MA7 regime entries for V4."
    )
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


class FlatRegimeSignal:
    def __init__(self, engine: Any) -> None:
        self.engine = engine
        self.events: list[dict[str, Any]] = []

    def reset(self) -> None:
        self.events = []

    def __call__(
        self,
        config: Any,
        book: Any,
        features: Any,
        index: int,
    ) -> bool:
        regime_config = replace(
            config,
            entry_mode="regime",
            entry_buffer_atr=0.0,
        )
        passed = self.engine.close_entry_signal(
            regime_config,
            book,
            features,
            index,
        )
        if passed:
            atr = float(features.atr7[index])
            prior = index - config.slope_lookback
            slope = (
                float(
                    config.side
                    * (features.ma7[index] - features.ma7[prior])
                    / atr
                )
                if prior >= 0 and np.isfinite(atr) and atr > 0.0
                else math.nan
            )
            self.events.append(
                {
                    "event": "flat_regime_entry_signal",
                    "signal_index": index,
                    "side": "long" if config.side > 0 else "short",
                    "close": float(book.close[index]),
                    "ma7": float(features.ma7[index]),
                    "slope_atr": slope,
                    "slope_lookback": int(config.slope_lookback),
                    "original_reclaim_would_pass": bool(
                        self.engine.close_entry_signal(
                            config,
                            book,
                            features,
                            index,
                        )
                    ),
                }
            )
        return passed


def clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(item) for item in value]
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def main() -> None:
    args = parse_args()
    loader = importlib.util.spec_from_file_location(
        "hype_v4_regime_timing",
        TIMING_PATH,
    )
    if loader is None or loader.loader is None:
        raise RuntimeError(f"cannot import {TIMING_PATH}")
    actual = hashlib.sha256(TIMING_PATH.read_bytes()).hexdigest()
    if actual != TIMING_SHA256:
        raise RuntimeError(
            f"{TIMING_PATH.name} drift: expected {TIMING_SHA256}, got {actual}"
        )
    shared = importlib.util.module_from_spec(loader)
    sys.modules[loader.name] = shared
    loader.loader.exec_module(shared)
    v4 = shared.load_pinned(
        shared.V4_FORMATION_PATH,
        shared.V4_FORMATION_SHA256,
        "hype_v4_regime_formation",
    )
    formation = v4.load_pinned(
        v4.FORMATION_PATH,
        v4.FORMATION_SHA256,
        "hype_v4_regime_reversal",
    )
    engine = formation.load_pinned(
        formation.ENGINE_PATH,
        formation.ENGINE_SHA256,
        "hype_v4_regime_engine",
    )
    base = formation.load_pinned(
        formation.BASE_PATH,
        formation.BASE_SHA256,
        "hype_v4_regime_base",
    )
    selected = formation.read_pinned_json(
        formation.SUMMARY_PATH,
        formation.SUMMARY_SHA256,
    )["historically_profitable_all_checks"][0]
    long_config = engine.Config(**selected["long_config"])
    short_config = replace(
        engine.Config(**selected["short_config"]),
        exit_buffer_atr=0.75,
    )
    functions = {
        variant: v4.build_filtered_backtest(formation, engine, v4.MA_ONLY)
        for variant in VARIANTS
    }
    signal = FlatRegimeSignal(engine)
    functions[FLAT_REGIME_ENTRY].__globals__["close_entry_signal"] = signal
    signals = {FLAT_REGIME_ENTRY: signal}
    if args.self_test:
        assert all(callable(functions[variant]) for variant in VARIANTS)
        assert callable(signal)
        print("self-test passed: V4 flat-regime entry variant compiled")
        return

    parent = base.load_parent()
    market_engine = parent.load_engine()
    hourly, hourly_quality = market_engine.audit_and_load_market(ROOT, "1h")
    funding, funding_quality = market_engine.load_and_audit_funding(ROOT)
    hourly["ts"] = pd.to_datetime(hourly["ts"], utc=True)
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
    historical_hourly = hourly.loc[
        hourly["ts"] <= formation.HISTORICAL_HOUR_CUTOFF
    ].copy()
    historical_funding = funding.loc[
        funding["ts"] <= formation.HISTORICAL_HOUR_CUTOFF
    ].copy()

    def build(phase: int, *, latest: bool = False) -> tuple[Any, Any]:
        source_hourly = hourly if latest else historical_hourly
        source_funding = funding if latest else historical_funding
        book = base.build_book(
            parent,
            source_hourly,
            hourly_quality,
            source_funding,
            funding_quality,
            phase_hours=phase,
        )
        return book, engine.build_features(book, source_hourly, source_funding)

    books = {}
    features = {}
    for phase in (0, 12):
        books[phase], features[phase] = build(phase)
    book = books[0]
    split = int(pd.DatetimeIndex(book.ts).searchsorted(HOLDOUT_START))
    windows = {
        "prefit": (0, split),
        "last_90d_flat": (split, book.count),
        "full": (0, book.count),
    }
    rows: list[dict[str, Any]] = []
    recent_rows: list[dict[str, Any]] = []
    rolling_rows: list[dict[str, Any]] = []
    full_results: dict[str, Any] = {}
    full_trades: dict[str, pd.DataFrame] = {}
    full_events: list[dict[str, Any]] = []
    for variant in VARIANTS:
        for window, (start, end) in windows.items():
            result, events = shared.run(
                functions,
                signals,
                variant,
                book,
                features[0],
                long_config,
                short_config,
                start=start,
                end=end,
                slippage=engine.BASE_SLIPPAGE,
                retain=window == "full",
            )
            rows.append(
                v4.result_row(
                    formation,
                    result,
                    variant,
                    window=window,
                    scenario="base_4bps",
                )
            )
            if window == "full":
                full_results[variant] = result
                full_trades[variant] = v4.annotate(formation, result)
                if variant == FLAT_REGIME_ENTRY:
                    full_events = shared.attach_timestamps(events, book)
                recent_rows.extend(
                    {"variant": variant, **item}
                    for item in engine.recent_slices(result)
                )
        for scenario, slippage, lag, include_funding in (
            ("stress_8bps", engine.STRESS_SLIPPAGE, 0, True),
            ("one_day_extra_delay", engine.BASE_SLIPPAGE, 1, True),
            ("zero_funding", engine.BASE_SLIPPAGE, 0, False),
        ):
            result, _ = shared.run(
                functions,
                signals,
                variant,
                book,
                features[0],
                long_config,
                short_config,
                start=0,
                end=book.count,
                slippage=slippage,
                signal_lag=lag,
                include_funding=include_funding,
            )
            rows.append(
                v4.result_row(
                    formation,
                    result,
                    variant,
                    window="full",
                    scenario=scenario,
                )
            )
        phase12, _ = shared.run(
            functions,
            signals,
            variant,
            books[12],
            features[12],
            long_config,
            short_config,
            start=0,
            end=books[12].count,
            slippage=engine.BASE_SLIPPAGE,
        )
        rows.append(
            v4.result_row(
                formation,
                phase12,
                variant,
                window="full",
                scenario="phase_12h",
            )
        )
        start = 0
        while start + 90 <= book.count:
            result, _ = shared.run(
                functions,
                signals,
                variant,
                book,
                features[0],
                long_config,
                short_config,
                start=start,
                end=start + 90,
                slippage=engine.BASE_SLIPPAGE,
            )
            rolling_rows.append(
                {
                    "variant": variant,
                    "window_index": sum(
                        row["variant"] == variant for row in rolling_rows
                    ),
                    **result.metrics,
                }
            )
            start += 30

    if not math.isclose(
        full_results[V4_CONTROL].metrics["equity_multiple"],
        shared.V4_EQUITY_MULTIPLE,
        rel_tol=1e-10,
        abs_tol=1e-10,
    ):
        raise RuntimeError("registered V4 control anchor drift")
    regime_entries = full_trades[FLAT_REGIME_ENTRY].copy()
    regime_entries["entry_ts_utc"] = pd.to_datetime(
        regime_entries["entry_ts"],
        utc=True,
    )
    june_long = regime_entries.loc[
        regime_entries["side"].eq("long")
        & regime_entries["entry_ts_utc"].eq(
            pd.Timestamp("2025-06-16T00:00:00Z")
        )
    ]
    june_reversal = regime_entries.loc[
        regime_entries["side"].eq("short")
        & regime_entries["entry_ts_utc"].eq(
            pd.Timestamp("2025-06-19T21:00:00Z")
        )
    ]
    if len(june_long) != 1 or len(june_reversal) != 1:
        raise RuntimeError("clarified 2025-06 symmetric regime path drift")

    phase_books = {}
    phase_features = {}
    phase_errors = {}
    for phase in range(24):
        try:
            phase_books[phase], phase_features[phase] = build(
                phase,
                latest=True,
            )
        except RuntimeError as exc:
            phase_errors[phase] = str(exc)
    phase_rows: list[dict[str, Any]] = []
    for variant in VARIANTS:
        for phase in range(24):
            if phase in phase_errors:
                continue
            result, _ = shared.run(
                functions,
                signals,
                variant,
                phase_books[phase],
                phase_features[phase],
                long_config,
                short_config,
                start=0,
                end=phase_books[phase].count,
                slippage=engine.BASE_SLIPPAGE,
            )
            phase_rows.append(
                {
                    "variant": variant,
                    "phase_hours": phase,
                    **result.metrics,
                    **v4.attribution(v4.annotate(formation, result)),
                }
            )

    latest_book, latest_features = build(0, latest=True)
    latest_rows: list[dict[str, Any]] = []
    for variant in VARIANTS:
        result, _ = shared.run(
            functions,
            signals,
            variant,
            latest_book,
            latest_features,
            long_config,
            short_config,
            start=0,
            end=latest_book.count,
            slippage=engine.BASE_SLIPPAGE,
        )
        latest_rows.append(
            v4.result_row(
                formation,
                result,
                variant,
                window="latest_extension",
                scenario="base_4bps",
            )
        )

    metrics_frame = pd.DataFrame(rows)
    rolling_frame = pd.DataFrame(rolling_rows)
    phase_frame = pd.DataFrame(phase_rows)
    deltas = shared.trade_deltas(
        full_trades[V4_CONTROL],
        full_trades[FLAT_REGIME_ENTRY],
    )
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_version": "HYPE-1D-MA7-Asymmetric-Body-Trend-V4",
        "status": "post-reveal diagnostic only; registered V4 unchanged",
        "contract": CONTRACT,
        "variant": (
            "flat + current close on MA7 side + frozen directional slope; "
            "no prior-day reclaim"
        ),
        "entry_events": full_events,
        "trade_deltas": deltas,
        "phase_errors": phase_errors,
        "phase_summary": {
            variant: shared.summarize(
                phase_frame.loc[phase_frame["variant"].eq(variant)]
            )
            for variant in VARIANTS
        },
        "rolling_90d_summary": {
            variant: shared.summarize(
                rolling_frame.loc[rolling_frame["variant"].eq(variant)]
            )
            for variant in VARIANTS
        },
        "data_quality": {
            "hourly": hourly_quality,
            "funding": funding_quality,
        },
        "evidence_role": "post-reveal mechanism diagnostic; not clean OOS",
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"hype_1d_v4_flat_regime_entry_{args.run_date}"
    (ARTIFACT_DIR / f"{stem}_summary.json").write_text(
        json.dumps(clean(payload), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    metrics_frame.to_csv(ARTIFACT_DIR / f"{stem}_metrics.csv", index=False)
    pd.DataFrame(recent_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_recent.csv",
        index=False,
    )
    rolling_frame.to_csv(
        ARTIFACT_DIR / f"{stem}_rolling_90d.csv",
        index=False,
    )
    phase_frame.to_csv(
        ARTIFACT_DIR / f"{stem}_phase24.csv",
        index=False,
    )
    pd.DataFrame(latest_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_latest.csv",
        index=False,
    )
    for variant in VARIANTS:
        full_trades[variant].to_csv(
            ARTIFACT_DIR / f"{stem}_{variant.lower()}_trades.csv",
            index=False,
        )
        pd.DataFrame(full_results[variant].path).to_csv(
            ARTIFACT_DIR / f"{stem}_{variant.lower()}_path.csv",
            index=False,
        )
    print(
        metrics_frame.loc[
            metrics_frame["window"].eq("full")
            & metrics_frame["scenario"].eq("base_4bps"),
            [
                "variant",
                "net_return_pct",
                "max_drawdown_pct",
                "sharpe",
                "closed_trades",
                "profit_factor",
                "exposure_pct",
            ],
        ].to_string(index=False)
    )
    print(json.dumps(clean(full_events), ensure_ascii=False, indent=2))
    print(json.dumps(clean(deltas), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
