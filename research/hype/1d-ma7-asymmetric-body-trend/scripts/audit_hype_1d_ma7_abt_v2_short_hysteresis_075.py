from __future__ import annotations

import argparse
from dataclasses import asdict, replace
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
FORMATION_PATH = (
    FAMILY_DIR / "scripts/audit_hype_v1_trailing_stop_short_reversal.py"
)
FORMATION_SHA256 = (
    "35185bbdba87732a806ef3d5e0ff9fc9da9e314e8369695646e7b3f07cbb1166"
)
V2_EQUITY_MULTIPLE = 4.225904698992523
HOLDOUT_START = pd.Timestamp("2026-05-01T00:00:00Z")
V2_CONTROL = "V2_CONTROL"
SHORT_EXIT_075 = "SHORT_EXIT_075"
NO_HARD = "SHORT_EXIT_075_NO_HARD"
NO_TRAIL = "SHORT_EXIT_075_NO_TRAIL"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit V2 short hysteresis buffer 0.25 -> 0.75."
    )
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def load_pinned(path: Path, expected: str, name: str) -> Any:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise RuntimeError(
            f"{path.name} drift: expected {expected}, got {actual}"
        )
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def exposure_pct(result: Any) -> float:
    positions = [
        int(row["position"])
        for row in result.path
        if row["action"] != "terminal"
    ]
    return (
        100.0 * sum(value != 0 for value in positions) / len(positions)
        if positions
        else math.nan
    )


def short_exit_counts(result: Any) -> dict[str, int]:
    short = [row for row in result.trades if row["side"] == "short"]
    return {
        "short_protective_exit_count": sum(
            row["exit_reason"] == "protective_stop" for row in short
        ),
        "short_hysteresis_exit_count": sum(
            row["exit_reason"] == "ma7_hysteresis_exit" for row in short
        ),
        "short_slope_exit_count": sum(
            row["exit_reason"] == "ma7_slope_exit" for row in short
        ),
        "short_max_hold_exit_count": sum(
            row["exit_reason"] == "max_hold" for row in short
        ),
    }


def result_row(
    result: Any,
    variant: str,
    *,
    window: str,
    scenario: str,
) -> dict[str, Any]:
    return {
        "variant": variant,
        "window": window,
        "scenario": scenario,
        **result.metrics,
        **short_exit_counts(result),
        "exposure_pct": exposure_pct(result),
    }


def trade_signature(result: Any) -> list[tuple[Any, ...]]:
    return [
        (
            row["entry_ts"],
            row["exit_ts"],
            row["side"],
            row["exit_reason"],
            round(float(row["entry_price"]), 12),
            round(float(row["exit_price"]), 12),
        )
        for row in result.trades
    ]


def classify_short_stops(
    candidate: Any,
    no_hard: Any,
    no_trail: Any,
) -> dict[str, Any]:
    candidate_count = short_exit_counts(candidate)[
        "short_protective_exit_count"
    ]
    no_hard_count = short_exit_counts(no_hard)[
        "short_protective_exit_count"
    ]
    no_trail_count = short_exit_counts(no_trail)[
        "short_protective_exit_count"
    ]
    if candidate_count == 0:
        verdict = "no_short_protective_stop_triggered"
        hard_count = trailing_count = 0
    elif (
        trade_signature(candidate) == trade_signature(no_trail)
        and no_hard_count < candidate_count
    ):
        verdict = "protective_stops_attributed_to_hard_stop"
        hard_count = candidate_count
        trailing_count = 0
    elif (
        trade_signature(candidate) == trade_signature(no_hard)
        and no_trail_count < candidate_count
    ):
        verdict = "protective_stops_attributed_to_trailing_stop"
        hard_count = 0
        trailing_count = candidate_count
    else:
        verdict = "interactive_or_not_uniquely_attributable"
        hard_count = trailing_count = None
    return {
        "candidate_short_protective_exit_count": candidate_count,
        "no_hard_short_protective_exit_count": no_hard_count,
        "no_trail_short_protective_exit_count": no_trail_count,
        "hard_stop_trigger_count": hard_count,
        "trailing_stop_trigger_count": trailing_count,
        "verdict": verdict,
    }


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
    formation = load_pinned(
        FORMATION_PATH,
        FORMATION_SHA256,
        "hype_short075_formation",
    )
    engine = formation.load_pinned(
        formation.ENGINE_PATH,
        formation.ENGINE_SHA256,
        "hype_short075_engine",
    )
    base = formation.load_pinned(
        formation.BASE_PATH,
        formation.BASE_SHA256,
        "hype_short075_base",
    )
    selected = formation.read_pinned_json(
        formation.SUMMARY_PATH,
        formation.SUMMARY_SHA256,
    )["historically_profitable_all_checks"][0]
    long_config = engine.Config(**selected["long_config"])
    v2_short = engine.Config(**selected["short_config"])
    short075 = replace(v2_short, exit_buffer_atr=0.75)
    short075_no_hard = replace(short075, hard_stop_atr=0.0)
    short075_no_trail = replace(short075, trail_atr=0.0)
    if args.self_test:
        assert v2_short.exit_buffer_atr == 0.25
        assert short075.exit_buffer_atr == 0.75
        assert short075.hard_stop_atr == 1.5
        assert short075.trail_atr == 4.0
        assert not short075_no_hard.hard_stop_atr
        assert not short075_no_trail.trail_atr
        print("self-test passed: short hysteresis and stop attribution configs")
        return

    backtest = formation.build_reversal_backtest(engine)
    short_configs = {
        V2_CONTROL: v2_short,
        SHORT_EXIT_075: short075,
        NO_HARD: short075_no_hard,
        NO_TRAIL: short075_no_trail,
    }
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

    def run(
        variant: str,
        target_book: Any,
        target_features: Any,
        *,
        start: int,
        end: int,
        slippage: float,
        signal_lag: int = 0,
        include_funding: bool = True,
    ) -> Any:
        return backtest(
            target_book,
            target_features,
            long_config=long_config,
            short_config=short_configs[variant],
            start_index=start,
            terminal_index=end,
            slippage=slippage,
            signal_lag=signal_lag,
            include_funding=include_funding,
            retain=True,
        )

    main_variants = (V2_CONTROL, SHORT_EXIT_075)
    rows: list[dict[str, Any]] = []
    recent_rows: list[dict[str, Any]] = []
    rolling_rows: list[dict[str, Any]] = []
    full_results: dict[str, Any] = {}
    for variant in main_variants:
        for window, (start, end) in windows.items():
            result = run(
                variant,
                book,
                features[0],
                start=start,
                end=end,
                slippage=engine.BASE_SLIPPAGE,
            )
            rows.append(
                result_row(
                    result,
                    variant,
                    window=window,
                    scenario="base_4bps",
                )
            )
            if window == "full":
                full_results[variant] = result
                recent_rows.extend(
                    {"variant": variant, **item}
                    for item in engine.recent_slices(result)
                )
        for scenario, slippage, lag, include_funding in (
            ("stress_8bps", engine.STRESS_SLIPPAGE, 0, True),
            ("one_day_extra_delay", engine.BASE_SLIPPAGE, 1, True),
            ("zero_funding", engine.BASE_SLIPPAGE, 0, False),
        ):
            result = run(
                variant,
                book,
                features[0],
                start=0,
                end=book.count,
                slippage=slippage,
                signal_lag=lag,
                include_funding=include_funding,
            )
            rows.append(
                result_row(
                    result,
                    variant,
                    window="full",
                    scenario=scenario,
                )
            )
        phase12 = run(
            variant,
            books[12],
            features[12],
            start=0,
            end=books[12].count,
            slippage=engine.BASE_SLIPPAGE,
        )
        rows.append(
            result_row(
                phase12,
                variant,
                window="full",
                scenario="phase_12h",
            )
        )
        start = 0
        window_number = 0
        while start + 90 <= book.count:
            result = run(
                variant,
                book,
                features[0],
                start=start,
                end=start + 90,
                slippage=engine.BASE_SLIPPAGE,
            )
            rolling_rows.append(
                {
                    "variant": variant,
                    "window_index": window_number,
                    **result.metrics,
                    **short_exit_counts(result),
                    "exposure_pct": exposure_pct(result),
                }
            )
            start += 30
            window_number += 1

    if not math.isclose(
        full_results[V2_CONTROL].metrics["equity_multiple"],
        V2_EQUITY_MULTIPLE,
        rel_tol=1e-10,
        abs_tol=1e-10,
    ):
        raise RuntimeError("V2 control anchor drift")

    attribution_results = {
        NO_HARD: run(
            NO_HARD,
            book,
            features[0],
            start=0,
            end=book.count,
            slippage=engine.BASE_SLIPPAGE,
        ),
        NO_TRAIL: run(
            NO_TRAIL,
            book,
            features[0],
            start=0,
            end=book.count,
            slippage=engine.BASE_SLIPPAGE,
        ),
    }
    stop_attribution = classify_short_stops(
        full_results[SHORT_EXIT_075],
        attribution_results[NO_HARD],
        attribution_results[NO_TRAIL],
    )

    phase_books: dict[int, Any] = {}
    phase_features: dict[int, Any] = {}
    phase_errors: dict[int, str] = {}
    for phase in range(24):
        try:
            phase_books[phase], phase_features[phase] = build(
                phase,
                latest=True,
            )
        except RuntimeError as exc:
            phase_errors[phase] = str(exc)
    phase_rows: list[dict[str, Any]] = []
    for variant in main_variants:
        for phase in range(24):
            if phase in phase_errors:
                continue
            result = run(
                variant,
                phase_books[phase],
                phase_features[phase],
                start=0,
                end=phase_books[phase].count,
                slippage=engine.BASE_SLIPPAGE,
            )
            phase_rows.append(
                {
                    "variant": variant,
                    "phase_hours": phase,
                    **result.metrics,
                    **short_exit_counts(result),
                    "exposure_pct": exposure_pct(result),
                }
            )

    latest_book, latest_features = build(0, latest=True)
    latest_rows = []
    for variant in main_variants:
        result = run(
            variant,
            latest_book,
            latest_features,
            start=0,
            end=latest_book.count,
            slippage=engine.BASE_SLIPPAGE,
        )
        latest_rows.append(
            result_row(
                result,
                variant,
                window="latest_extension",
                scenario="base_4bps",
            )
        )

    phase_frame = pd.DataFrame(phase_rows)
    rolling_frame = pd.DataFrame(rolling_rows)
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "HYPE-1D-MA7-Asymmetric-Body-Trend",
        "status": "diagnostic only; V2 unchanged",
        "contract": (
            "specs/hype-1d-ma7-abt-v2-short-hysteresis-075-contract-"
            "2026-08-07.md"
        ),
        "configs": {
            "v2_short": asdict(v2_short),
            "short_exit_075": asdict(short075),
        },
        "baseline_short_stop_counts": short_exit_counts(
            full_results[V2_CONTROL]
        ),
        "candidate_short_stop_attribution": stop_attribution,
        "attribution_control_metrics": {
            variant: result.metrics
            for variant, result in attribution_results.items()
        },
        "pins": {
            "formation_sha256": FORMATION_SHA256,
            "engine_sha256": formation.ENGINE_SHA256,
            "base_sha256": formation.BASE_SHA256,
        },
        "data_quality": {
            "hourly": hourly_quality,
            "funding": funding_quality,
        },
        "phase_errors": phase_errors,
        "phase_summary": {
            variant: summarize(
                phase_frame.loc[phase_frame["variant"].eq(variant)]
            )
            for variant in main_variants
        },
        "rolling_90d_summary": {
            variant: summarize(
                rolling_frame.loc[rolling_frame["variant"].eq(variant)]
            )
            for variant in main_variants
        },
        "evidence_role": "post-reveal OAT diagnostic; not OOS or promotion",
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"hype_1d_v2_short_hysteresis_075_{args.run_date}"
    (ARTIFACT_DIR / f"{stem}_summary.json").write_text(
        json.dumps(clean(payload), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    pd.DataFrame(rows).to_csv(
        ARTIFACT_DIR / f"{stem}_metrics.csv",
        index=False,
    )
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
    for variant, result in {
        **full_results,
        **attribution_results,
    }.items():
        pd.DataFrame(result.trades).to_csv(
            ARTIFACT_DIR / f"{stem}_{variant.lower()}_trades.csv",
            index=False,
        )
    table = pd.DataFrame(rows)
    table = table.loc[
        table["window"].eq("full")
        & table["scenario"].eq("base_4bps")
    ]
    print(
        table[
            [
                "variant",
                "net_return_pct",
                "max_drawdown_pct",
                "sharpe",
                "closed_trades",
                "short_hysteresis_exit_count",
                "short_slope_exit_count",
                "short_protective_exit_count",
            ]
        ].to_string(index=False)
    )
    print(json.dumps(clean(stop_attribution), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
