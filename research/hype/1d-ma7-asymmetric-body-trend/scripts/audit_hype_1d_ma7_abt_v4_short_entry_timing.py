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
V4_FORMATION_PATH = (
    FAMILY_DIR
    / "scripts/audit_hype_1d_ma7_abt_v3_forced_reversal_confirmation.py"
)
V4_FORMATION_SHA256 = (
    "8dda2472da22f89761d3231da7d12e9a3bb9b4c67444c0436be4fd6d70d64543"
)
CONTRACT = (
    "specs/hype-1d-ma7-abt-v4-short-entry-timing-contract-2026-08-07.md"
)
HOLDOUT_START = pd.Timestamp("2026-05-01T00:00:00Z")
V4_EQUITY_MULTIPLE = 5.112301180229631
V4_CONTROL = "V4_CONTROL"
SHORT_ENTRY_SLOPE_1D = "SHORT_ENTRY_SLOPE_1D"
PERSISTENT_CROSS_2D = "PERSISTENT_CROSS_2D"
VARIANTS = (V4_CONTROL, SHORT_ENTRY_SLOPE_1D, PERSISTENT_CROSS_2D)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit V4 one-day slope and persistent short-cross entry."
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


class ShortEntrySignal:
    def __init__(self, engine: Any, mode: str) -> None:
        self.engine = engine
        self.mode = mode
        self.events: list[dict[str, Any]] = []
        self.armed = False
        self.armed_at: int | None = None

    def reset(self) -> None:
        self.events = []
        self.armed = False
        self.armed_at = None

    @staticmethod
    def _finite(*values: float) -> bool:
        return all(np.isfinite(value) for value in values)

    def _slopes(
        self,
        features: Any,
        index: int,
    ) -> tuple[float, float]:
        atr = float(features.atr7[index])
        if index < 2 or not self._finite(atr) or atr <= 0.0:
            return math.nan, math.nan
        slope_1d = float(
            (features.ma7[index - 1] - features.ma7[index]) / atr
        )
        slope_2d = float(
            (features.ma7[index - 2] - features.ma7[index]) / atr
        )
        return slope_1d, slope_2d

    def _price_state(
        self,
        config: Any,
        book: Any,
        features: Any,
        index: int,
    ) -> tuple[bool, bool, float, float]:
        if index < 1:
            return False, False, math.nan, math.nan
        close = float(book.close[index])
        ma = float(features.ma7[index])
        atr = float(features.atr7[index])
        prior_close = float(book.close[index - 1])
        prior_ma = float(features.ma7[index - 1])
        prior_atr = float(features.atr7[index - 1])
        if (
            not self._finite(close, ma, atr, prior_close, prior_ma, prior_atr)
            or atr <= 0.0
            or prior_atr <= 0.0
        ):
            return False, False, close, ma
        buffer_pass = bool(
            config.side * (close - ma) > config.entry_buffer_atr * atr
        )
        reclaim = bool(
            config.side * (prior_close - prior_ma)
            <= config.pullback_touch_atr * prior_atr
        )
        return buffer_pass, buffer_pass and reclaim, close, ma

    def __call__(
        self,
        config: Any,
        book: Any,
        features: Any,
        index: int,
    ) -> bool:
        if config.side > 0:
            if self.mode == PERSISTENT_CROSS_2D and index >= 0:
                close = float(book.close[index])
                ma = float(features.ma7[index])
                if self.armed and self._finite(close, ma) and close >= ma:
                    self.events.append(
                        {
                            "event": "invalidate_above_ma7",
                            "signal_index": index,
                            "armed_at_index": self.armed_at,
                            "close": close,
                            "ma7": ma,
                        }
                    )
                    self.armed = False
                    self.armed_at = None
            return self.engine.close_entry_signal(
                config,
                book,
                features,
                index,
            )

        if config.entry_mode != "reclaim":
            raise RuntimeError("frozen short entry mode is no longer reclaim")
        buffer_pass, fresh_cross, close, ma = self._price_state(
            config,
            book,
            features,
            index,
        )
        slope_1d, slope_2d = self._slopes(features, index)

        if self.mode == SHORT_ENTRY_SLOPE_1D:
            entry_config = replace(config, slope_lookback=1)
            passed = self.engine.close_entry_signal(
                entry_config,
                book,
                features,
                index,
            )
            if passed:
                self.events.append(
                    {
                        "event": "short_entry_signal",
                        "signal_index": index,
                        "fresh_cross": fresh_cross,
                        "close": close,
                        "ma7": ma,
                        "slope_1d_atr": slope_1d,
                        "slope_2d_atr": slope_2d,
                        "v4_2d_would_pass": bool(
                            np.isfinite(slope_2d)
                            and slope_2d >= config.slope_min_atr
                        ),
                    }
                )
            return passed

        if self.mode != PERSISTENT_CROSS_2D:
            return self.engine.close_entry_signal(
                config,
                book,
                features,
                index,
            )

        if self.armed and self._finite(close, ma) and close >= ma:
            self.events.append(
                {
                    "event": "invalidate_above_ma7",
                    "signal_index": index,
                    "armed_at_index": self.armed_at,
                    "close": close,
                    "ma7": ma,
                }
            )
            self.armed = False
            self.armed_at = None
        if fresh_cross:
            self.armed = True
            self.armed_at = index
            self.events.append(
                {
                    "event": "arm_fresh_cross",
                    "signal_index": index,
                    "close": close,
                    "ma7": ma,
                    "slope_1d_atr": slope_1d,
                    "slope_2d_atr": slope_2d,
                }
            )
        trend_pass = bool(
            np.isfinite(slope_2d) and slope_2d >= config.slope_min_atr
        )
        passed = self.armed and buffer_pass and trend_pass
        if passed:
            self.events.append(
                {
                    "event": "confirm_short_entry",
                    "signal_index": index,
                    "armed_at_index": self.armed_at,
                    "wait_days": index - int(self.armed_at),
                    "fresh_on_confirmation": fresh_cross,
                    "close": close,
                    "ma7": ma,
                    "slope_1d_atr": slope_1d,
                    "slope_2d_atr": slope_2d,
                }
            )
            self.armed = False
            self.armed_at = None
        return passed


def install_signal(
    function: Any,
    engine: Any,
    mode: str,
) -> ShortEntrySignal:
    signal = ShortEntrySignal(engine, mode)
    function.__globals__["close_entry_signal"] = signal
    return signal


def run(
    functions: dict[str, Any],
    signals: dict[str, ShortEntrySignal],
    variant: str,
    book: Any,
    features: Any,
    long_config: Any,
    short_config: Any,
    *,
    start: int,
    end: int,
    slippage: float,
    signal_lag: int = 0,
    include_funding: bool = True,
    retain: bool = False,
) -> tuple[Any, list[dict[str, Any]]]:
    if variant in signals:
        signals[variant].reset()
    result = functions[variant](
        book,
        features,
        long_config=long_config,
        short_config=short_config,
        start_index=start,
        terminal_index=end,
        slippage=slippage,
        signal_lag=signal_lag,
        include_funding=include_funding,
        retain=retain,
    )
    events = list(signals[variant].events) if variant in signals else []
    return result, events


def attach_timestamps(
    events: list[dict[str, Any]],
    book: Any,
) -> list[dict[str, Any]]:
    timestamps = pd.DatetimeIndex(book.ts)
    output = []
    for event in events:
        row = dict(event)
        index = int(row["signal_index"])
        row["signal_ts"] = pd.Timestamp(timestamps[index]).isoformat()
        armed_at = row.get("armed_at_index")
        if armed_at is not None:
            row["armed_at_ts"] = pd.Timestamp(
                timestamps[int(armed_at)]
            ).isoformat()
        output.append(row)
    return output


def trade_deltas(
    control: pd.DataFrame,
    candidate: pd.DataFrame,
) -> list[dict[str, Any]]:
    def keyed(frame: pd.DataFrame) -> dict[tuple[str, str], pd.Series]:
        return {
            (str(row["side"]), str(row["entry_ts"])): row
            for _, row in frame.iterrows()
        }

    left = keyed(control)
    right = keyed(candidate)
    rows: list[dict[str, Any]] = []
    for key in sorted(set(left) | set(right), key=lambda item: item[1]):
        before = left.get(key)
        after = right.get(key)
        if before is None:
            change = "added"
        elif after is None:
            change = "removed"
        elif (
            str(before["exit_ts"]) == str(after["exit_ts"])
            and math.isclose(
                float(before["net_return"]),
                float(after["net_return"]),
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
        ):
            continue
        else:
            change = "modified"
        rows.append(
            {
                "change": change,
                "side": key[0],
                "entry_ts": key[1],
                "control_exit_ts": (
                    str(before["exit_ts"]) if before is not None else None
                ),
                "candidate_exit_ts": (
                    str(after["exit_ts"]) if after is not None else None
                ),
                "control_return_pct": (
                    float(before["net_return"]) * 100.0
                    if before is not None
                    else None
                ),
                "candidate_return_pct": (
                    float(after["net_return"]) * 100.0
                    if after is not None
                    else None
                ),
                "control_exit_reason": (
                    str(before["exit_reason"]) if before is not None else None
                ),
                "candidate_exit_reason": (
                    str(after["exit_reason"]) if after is not None else None
                ),
            }
        )
    return rows


def summarize(frame: pd.DataFrame) -> dict[str, Any]:
    return {
        "count": int(len(frame)),
        "positive": int((frame["net_return_pct"] > 0.0).sum()),
        "median_return_pct": float(frame["net_return_pct"].median()),
        "min_return_pct": float(frame["net_return_pct"].min()),
        "worst_mdd_pct": float(frame["max_drawdown_pct"].min()),
        "bankrupt": int(frame["bankrupt_intraday"].sum()),
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
    v4 = load_pinned(
        V4_FORMATION_PATH,
        V4_FORMATION_SHA256,
        "hype_v4_short_timing_formation",
    )
    formation = v4.load_pinned(
        v4.FORMATION_PATH,
        v4.FORMATION_SHA256,
        "hype_v4_short_timing_reversal",
    )
    engine = formation.load_pinned(
        formation.ENGINE_PATH,
        formation.ENGINE_SHA256,
        "hype_v4_short_timing_engine",
    )
    base = formation.load_pinned(
        formation.BASE_PATH,
        formation.BASE_SHA256,
        "hype_v4_short_timing_base",
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
    if (
        short_config.slope_lookback != 2
        or short_config.entry_mode != "reclaim"
        or short_config.confirm_days != 1
        or not math.isclose(short_config.entry_buffer_atr, 0.10)
        or not math.isclose(short_config.pullback_touch_atr, 0.0)
    ):
        raise RuntimeError("registered V4 short entry identity drift")

    functions = {
        variant: v4.build_filtered_backtest(formation, engine, v4.MA_ONLY)
        for variant in VARIANTS
    }
    signals = {
        variant: install_signal(functions[variant], engine, variant)
        for variant in (SHORT_ENTRY_SLOPE_1D, PERSISTENT_CROSS_2D)
    }
    if args.self_test:
        assert all(callable(functions[variant]) for variant in VARIANTS)
        assert signals[SHORT_ENTRY_SLOPE_1D].mode == SHORT_ENTRY_SLOPE_1D
        assert signals[PERSISTENT_CROSS_2D].mode == PERSISTENT_CROSS_2D
        print("self-test passed: V4 short-entry timing variants compiled")
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
            result, events = run(
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
                full_events[variant] = attach_timestamps(events, book)
                recent_rows.extend(
                    {"variant": variant, **item}
                    for item in engine.recent_slices(result)
                )
        for scenario, slippage, lag, include_funding in (
            ("stress_8bps", engine.STRESS_SLIPPAGE, 0, True),
            ("one_day_extra_delay", engine.BASE_SLIPPAGE, 1, True),
            ("zero_funding", engine.BASE_SLIPPAGE, 0, False),
        ):
            result, _ = run(
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
        phase12, _ = run(
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
            result, _ = run(
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
        V4_EQUITY_MULTIPLE,
        rel_tol=1e-10,
        abs_tol=1e-10,
    ):
        raise RuntimeError("registered V4 control anchor drift")

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
            result, _ = run(
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
        result, _ = run(
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
    deltas = {
        variant: trade_deltas(full_trades[V4_CONTROL], full_trades[variant])
        for variant in (SHORT_ENTRY_SLOPE_1D, PERSISTENT_CROSS_2D)
    }
    one_day_june = [
        event
        for event in full_events[SHORT_ENTRY_SLOPE_1D]
        if event["signal_ts"].startswith("2025-06-17")
    ]
    persistent_june = [
        event
        for event in full_events[PERSISTENT_CROSS_2D]
        if event["event"] == "confirm_short_entry"
        and event["signal_ts"].startswith("2025-06-18")
        and event["armed_at_ts"].startswith("2025-06-17")
    ]
    if len(one_day_june) != 1 or len(persistent_june) != 1:
        raise RuntimeError("2025-06 short-entry timing evidence drift")
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_version": "HYPE-1D-MA7-Asymmetric-Body-Trend-V4",
        "status": "post-reveal diagnostic only; registered V4 unchanged",
        "contract": CONTRACT,
        "variants": {
            V4_CONTROL: "registered V4",
            SHORT_ENTRY_SLOPE_1D: (
                "natural short entry uses 1d slope; short exits remain 2d"
            ),
            PERSISTENT_CROSS_2D: (
                "fresh short cross remains armed below MA7 until 2d slope passes"
            ),
        },
        "entry_events": full_events,
        "trade_deltas": deltas,
        "phase_errors": phase_errors,
        "phase_summary": {
            variant: summarize(
                phase_frame.loc[phase_frame["variant"].eq(variant)]
            )
            for variant in VARIANTS
        },
        "rolling_90d_summary": {
            variant: summarize(
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
    stem = f"hype_1d_v4_short_entry_timing_{args.run_date}"
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
