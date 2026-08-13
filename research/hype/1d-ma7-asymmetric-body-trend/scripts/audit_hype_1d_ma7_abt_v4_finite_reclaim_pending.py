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
CONTRACT = (
    "specs/hype-1d-ma7-abt-v4-finite-reclaim-pending-contract-2026-08-07.md"
)
HOLDOUT_START = pd.Timestamp("2026-05-01T00:00:00Z")
V4_CONTROL = "V4_CONTROL"
SHORT_PENDING_1D = "SHORT_PENDING_1D"
SHORT_PENDING_2D = "SHORT_PENDING_2D"
LONG_PENDING_1D = "LONG_PENDING_1D"
LONG_PENDING_2D = "LONG_PENDING_2D"
BOTH_PENDING_1D = "BOTH_PENDING_1D"
BOTH_PENDING_2D = "BOTH_PENDING_2D"
LONG1_SHORT2 = "LONG1_SHORT2"
LONG2_SHORT1 = "LONG2_SHORT1"
VARIANT_WAITS = {
    V4_CONTROL: (0, 0),
    SHORT_PENDING_1D: (0, 1),
    SHORT_PENDING_2D: (0, 2),
    LONG_PENDING_1D: (1, 0),
    LONG_PENDING_2D: (2, 0),
    BOTH_PENDING_1D: (1, 1),
    BOTH_PENDING_2D: (2, 2),
    LONG1_SHORT2: (1, 2),
    LONG2_SHORT1: (2, 1),
}
VARIANTS = tuple(VARIANT_WAITS)
TARGET_SHORT_ENTRY = pd.Timestamp("2025-06-19T00:00:00Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit V4 finite reclaim pending local repairs."
    )
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def load_pinned(path: Path, expected: str, name: str) -> Any:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise RuntimeError(f"{path.name} drift: expected {expected}, got {actual}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FinitePendingSignal:
    def __init__(self, engine: Any, long_wait: int, short_wait: int) -> None:
        self.engine = engine
        self.waits = {1: long_wait, -1: short_wait}
        self.events: list[dict[str, Any]] = []
        self.armed_at: dict[int, int | None] = {1: None, -1: None}

    def reset(self) -> None:
        self.events = []
        self.armed_at = {1: None, -1: None}

    @staticmethod
    def _finite(*values: float) -> bool:
        return all(np.isfinite(value) for value in values)

    @staticmethod
    def _side_name(side: int) -> str:
        return "long" if side > 0 else "short"

    def _snapshot(
        self,
        config: Any,
        book: Any,
        features: Any,
        index: int,
    ) -> dict[str, Any]:
        side = int(config.side)
        close = float(book.close[index])
        ma = float(features.ma7[index])
        atr = float(features.atr7[index])
        prior_close = float(book.close[index - 1])
        prior_ma = float(features.ma7[index - 1])
        prior_atr = float(features.atr7[index - 1])
        prior_slope_index = index - config.slope_lookback
        slope = math.nan
        if (
            prior_slope_index >= 0
            and self._finite(
                features.ma7[index],
                features.ma7[prior_slope_index],
                atr,
            )
            and atr > 0.0
        ):
            slope = float(
                side
                * (
                    features.ma7[index]
                    - features.ma7[prior_slope_index]
                )
                / atr
            )
        valid = (
            self._finite(close, ma, atr, prior_close, prior_ma, prior_atr)
            and atr > 0.0
            and prior_atr > 0.0
        )
        buffer_pass = bool(
            valid
            and self.engine._confirmed_side(
                config,
                book,
                features,
                index,
            )
        )
        prior_touch = bool(
            valid
            and side * (prior_close - prior_ma)
            <= config.pullback_touch_atr * prior_atr
        )
        trend_pass = bool(
            valid
            and self.engine._trend_ok(
                config,
                book,
                features,
                index,
            )
        )
        return {
            "close": close,
            "ma7": ma,
            "atr7": atr,
            "slope_atr": slope,
            "buffer_pass": buffer_pass,
            "prior_touch": prior_touch,
            "fresh_reclaim": buffer_pass and prior_touch,
            "trend_pass": trend_pass,
            "valid": valid,
        }

    def _event(
        self,
        name: str,
        side: int,
        index: int,
        snapshot: dict[str, Any],
        **extra: Any,
    ) -> None:
        self.events.append(
            {
                "event": name,
                "signal_index": index,
                "side": self._side_name(side),
                **snapshot,
                **extra,
            }
        )

    def __call__(
        self,
        config: Any,
        book: Any,
        features: Any,
        index: int,
    ) -> bool:
        side = int(config.side)
        wait = self.waits[side]
        if wait == 0:
            return self.engine.close_entry_signal(
                config,
                book,
                features,
                index,
            )
        if config.entry_mode != "reclaim":
            raise RuntimeError("finite pending requires frozen reclaim entry mode")
        if index < 1:
            return False
        snapshot = self._snapshot(config, book, features, index)
        armed_at = self.armed_at[side]
        if armed_at is not None and index - armed_at > wait:
            self._event(
                "expire_pending",
                side,
                index,
                snapshot,
                armed_at_index=armed_at,
                wait_days=index - armed_at,
                max_wait_days=wait,
            )
            self.armed_at[side] = None
            armed_at = None
        if (
            armed_at is not None
            and snapshot["valid"]
            and side * (snapshot["close"] - snapshot["ma7"]) <= 0.0
        ):
            self._event(
                "invalidate_across_ma7",
                side,
                index,
                snapshot,
                armed_at_index=armed_at,
                wait_days=index - armed_at,
                max_wait_days=wait,
            )
            self.armed_at[side] = None
            armed_at = None
        if snapshot["fresh_reclaim"]:
            self.armed_at[side] = index
            armed_at = index
            self._event(
                "arm_fresh_reclaim",
                side,
                index,
                snapshot,
                armed_at_index=index,
                wait_days=0,
                max_wait_days=wait,
            )
        passed = bool(
            armed_at is not None
            and index - armed_at <= wait
            and snapshot["buffer_pass"]
            and snapshot["trend_pass"]
        )
        if passed:
            self._event(
                "confirm_pending_entry",
                side,
                index,
                snapshot,
                armed_at_index=armed_at,
                wait_days=index - armed_at,
                max_wait_days=wait,
                delayed=index > armed_at,
            )
            self.armed_at[side] = None
        return passed


def install_signal(
    function: Any,
    engine: Any,
    long_wait: int,
    short_wait: int,
) -> FinitePendingSignal:
    signal = FinitePendingSignal(engine, long_wait, short_wait)
    function.__globals__["close_entry_signal"] = signal
    return signal


def event_counts(events: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "pending_arms": sum(
            event["event"] == "arm_fresh_reclaim" for event in events
        ),
        "pending_confirms": sum(
            event["event"] == "confirm_pending_entry" for event in events
        ),
        "delayed_confirms": sum(
            event["event"] == "confirm_pending_entry"
            and bool(event.get("delayed"))
            for event in events
        ),
        "pending_expires": sum(
            event["event"] == "expire_pending" for event in events
        ),
        "pending_invalidates": sum(
            event["event"] == "invalidate_across_ma7" for event in events
        ),
    }


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
    shared = load_pinned(
        TIMING_PATH,
        TIMING_SHA256,
        "hype_v4_finite_pending_shared",
    )
    v4 = shared.load_pinned(
        shared.V4_FORMATION_PATH,
        shared.V4_FORMATION_SHA256,
        "hype_v4_finite_pending_v4",
    )
    formation = v4.load_pinned(
        v4.FORMATION_PATH,
        v4.FORMATION_SHA256,
        "hype_v4_finite_pending_formation",
    )
    engine = formation.load_pinned(
        formation.ENGINE_PATH,
        formation.ENGINE_SHA256,
        "hype_v4_finite_pending_engine",
    )
    base = formation.load_pinned(
        formation.BASE_PATH,
        formation.BASE_SHA256,
        "hype_v4_finite_pending_base",
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
    if long_config.entry_mode != "reclaim" or short_config.entry_mode != "reclaim":
        raise RuntimeError("registered V4 reclaim identity drift")
    functions = {
        variant: v4.build_filtered_backtest(formation, engine, v4.MA_ONLY)
        for variant in VARIANTS
    }
    signals = {
        variant: install_signal(
            functions[variant],
            engine,
            *VARIANT_WAITS[variant],
        )
        for variant in VARIANTS
        if variant != V4_CONTROL
    }
    if args.self_test:
        assert len(functions) == 9
        assert all(callable(functions[variant]) for variant in VARIANTS)
        assert VARIANT_WAITS[SHORT_PENDING_1D] == (0, 1)
        assert VARIANT_WAITS[LONG2_SHORT1] == (2, 1)
        print("self-test passed: V4 finite reclaim pending variants compiled")
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
    full_events: dict[str, list[dict[str, Any]]] = {}
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
            row = v4.result_row(
                formation,
                result,
                variant,
                window=window,
                scenario="base_4bps",
            )
            row.update(event_counts(events))
            rows.append(row)
            if window == "full":
                full_results[variant] = result
                full_trades[variant] = v4.annotate(formation, result)
                full_events[variant] = shared.attach_timestamps(events, book)
                recent_rows.extend(
                    {"variant": variant, **item}
                    for item in engine.recent_slices(result)
                )
        for scenario, slippage, lag, include_funding in (
            ("stress_8bps", engine.STRESS_SLIPPAGE, 0, True),
            ("one_day_extra_delay", engine.BASE_SLIPPAGE, 1, True),
            ("zero_funding", engine.BASE_SLIPPAGE, 0, False),
        ):
            result, events = shared.run(
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
            row = v4.result_row(
                formation,
                result,
                variant,
                window="full",
                scenario=scenario,
            )
            row.update(event_counts(events))
            rows.append(row)
        result, events = shared.run(
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
        row = v4.result_row(
            formation,
            result,
            variant,
            window="full",
            scenario="phase_12h",
        )
        row.update(event_counts(events))
        rows.append(row)
        start = 0
        while start + 90 <= book.count:
            result, events = shared.run(
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
                    **event_counts(events),
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
    short_one = full_trades[SHORT_PENDING_1D].copy()
    short_one["entry_ts_utc"] = pd.to_datetime(short_one["entry_ts"], utc=True)
    target = short_one.loc[
        short_one["side"].eq("short")
        & short_one["entry_ts_utc"].eq(TARGET_SHORT_ENTRY)
    ]
    if len(target) != 1:
        raise RuntimeError("one-day pending did not repair target June short")

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
            result, events = shared.run(
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
                    **event_counts(events),
                }
            )

    latest_book, latest_features = build(0, latest=True)
    latest_rows: list[dict[str, Any]] = []
    for variant in VARIANTS:
        result, events = shared.run(
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
        row = v4.result_row(
            formation,
            result,
            variant,
            window="latest_extension",
            scenario="base_4bps",
        )
        row.update(event_counts(events))
        latest_rows.append(row)

    metrics_frame = pd.DataFrame(rows)
    rolling_frame = pd.DataFrame(rolling_rows)
    phase_frame = pd.DataFrame(phase_rows)
    base_rows = metrics_frame.loc[
        metrics_frame["window"].eq("full")
        & metrics_frame["scenario"].eq("base_4bps")
    ].set_index("variant")
    delay_rows = metrics_frame.loc[
        metrics_frame["window"].eq("full")
        & metrics_frame["scenario"].eq("one_day_extra_delay")
    ].set_index("variant")
    phase12_rows = metrics_frame.loc[
        metrics_frame["window"].eq("full")
        & metrics_frame["scenario"].eq("phase_12h")
    ].set_index("variant")
    phase_summaries = {
        variant: shared.summarize(
            phase_frame.loc[phase_frame["variant"].eq(variant)]
        )
        for variant in VARIANTS
    }
    rolling_summaries = {
        variant: shared.summarize(
            rolling_frame.loc[rolling_frame["variant"].eq(variant)]
        )
        for variant in VARIANTS
    }
    trade_deltas = {
        variant: shared.trade_deltas(
            full_trades[V4_CONTROL],
            full_trades[variant],
        )
        for variant in VARIANTS
        if variant != V4_CONTROL
    }
    qualifications = {}
    for variant in VARIANTS:
        if variant == V4_CONTROL:
            continue
        phase_summary = phase_summaries[variant]
        qualifications[variant] = {
            "mdd_within_5pp": bool(
                base_rows.loc[variant, "max_drawdown_pct"]
                >= base_rows.loc[V4_CONTROL, "max_drawdown_pct"] - 5.0
            ),
            "delay_positive": bool(
                delay_rows.loc[variant, "net_return_pct"] > 0.0
            ),
            "phase12_positive": bool(
                phase12_rows.loc[variant, "net_return_pct"] > 0.0
            ),
            "phase_median_positive": bool(
                phase_summary["median_return_pct"] > 0.0
            ),
            "phase_positive_at_least_18": bool(
                phase_summary["positive"] >= 18
            ),
            "target_short_fixed": bool(
                (
                    pd.to_datetime(
                        full_trades[variant]["entry_ts"],
                        utc=True,
                    ).eq(TARGET_SHORT_ENTRY)
                    & full_trades[variant]["side"].eq("short")
                ).any()
            ),
        }
        checks = qualifications[variant]
        checks["robustness_floor_pass"] = all(
            checks[key]
            for key in (
                "mdd_within_5pp",
                "delay_positive",
                "phase12_positive",
                "phase_median_positive",
                "phase_positive_at_least_18",
            )
        )
    eligible = [
        variant
        for variant in VARIANTS
        if variant != V4_CONTROL
        and qualifications[variant]["robustness_floor_pass"]
        and VARIANT_WAITS[variant][1] > 0
        and qualifications[variant]["target_short_fixed"]
    ]
    eligible.sort(
        key=lambda variant: (
            sum(VARIANT_WAITS[variant]),
            len(trade_deltas[variant]),
            -float(base_rows.loc[variant, "net_return_pct"]),
        )
    )
    best_variant = eligible[0] if eligible else None
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_version": "HYPE-1D-MA7-Asymmetric-Body-Trend-V4",
        "status": "post-reveal local repair diagnostic; registered V4 unchanged",
        "contract": CONTRACT,
        "variant_waits": {
            variant: {
                "long_pending_days": waits[0],
                "short_pending_days": waits[1],
            }
            for variant, waits in VARIANT_WAITS.items()
        },
        "entry_events": full_events,
        "trade_deltas": trade_deltas,
        "qualifications": qualifications,
        "eligible_variants": eligible,
        "best_variant_by_frozen_rules": best_variant,
        "phase_errors": phase_errors,
        "phase_summary": phase_summaries,
        "rolling_90d_summary": rolling_summaries,
        "data_quality": {
            "hourly": hourly_quality,
            "funding": funding_quality,
        },
        "evidence_role": "post-reveal mechanism diagnostic; not clean OOS",
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"hype_1d_v4_finite_reclaim_pending_{args.run_date}"
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
        base_rows[
            [
                "net_return_pct",
                "max_drawdown_pct",
                "sharpe",
                "closed_trades",
                "profit_factor",
                "delayed_confirms",
                "exposure_pct",
            ]
        ].to_string()
    )
    print(
        json.dumps(
            clean(
                {
                    "qualifications": qualifications,
                    "eligible": eligible,
                    "best": best_variant,
                }
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
