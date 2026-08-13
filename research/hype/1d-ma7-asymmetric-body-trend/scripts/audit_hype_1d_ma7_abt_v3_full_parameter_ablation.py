from __future__ import annotations

import argparse
from dataclasses import asdict, replace
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import sys
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
PARENT_PATH = (
    FAMILY_DIR
    / "scripts/audit_hype_1d_ma7_abt_v2_full_parameter_ablation.py"
)
PARENT_SHA256 = (
    "ac50cdaf034ebdf90f1e022acd4fa43c5994b8e537d5b032bbe4ceca2e38aad9"
)
V3_EQUITY_MULTIPLE = 4.508464159893385
HOLDOUT_START = pd.Timestamp("2026-05-01T00:00:00Z")
BASELINE = "baseline_v3"
KEY_SLOPE_VARIANTS = (
    BASELINE,
    "long_entry_slope_direction_only",
    "long_entry_slope_removed",
    "short_entry_slope_direction_only",
    "short_entry_slope_removed",
    "both_entry_slopes_removed",
    "short_slope_exit_removed",
    "all_slopes_removed",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Full active-parameter ablation for HYPE MA7 V3."
    )
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def load_parent() -> Any:
    actual = hashlib.sha256(PARENT_PATH.read_bytes()).hexdigest()
    if actual != PARENT_SHA256:
        raise RuntimeError(
            f"V2 ablation parent drift: expected {PARENT_SHA256}, got {actual}"
        )
    spec = importlib.util.spec_from_file_location(
        "hype_v3_full_ablation_parent",
        PARENT_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {PARENT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_oat_variants(
    parent: Any,
    long_config: Any,
    short_config: Any,
) -> list[Any]:
    variants = parent.build_oat_variants(long_config, short_config)
    output = []
    for variant in variants:
        if variant.name == "baseline_v2":
            output.append(
                replace(
                    variant,
                    name=BASELINE,
                    change="none; registered V3",
                )
            )
        elif variant.name == "short_exit_hysteresis_buffer_removed":
            output.append(
                replace(
                    variant,
                    change="short exit_buffer_atr 0.75 -> 0",
                )
            )
        else:
            output.append(variant)
    output.append(
        parent.Variant(
            name="short_exit_hysteresis_v2_025",
            group="exit",
            change="short exit_buffer_atr 0.75 -> 0.25; revert to V2",
            long_config=long_config,
            short_config=replace(short_config, exit_buffer_atr=0.25),
            reversal_enabled=True,
        )
    )
    return output


def classify_slope(
    parent: Any,
    oat: pd.DataFrame,
    phase_summary: dict[str, dict[str, Any]],
    rolling_summary: dict[str, dict[str, Any]],
    *,
    removed_name: str,
    direction_name: str | None,
) -> dict[str, Any]:
    alias = oat.copy()
    alias.loc[alias["variant"].eq(BASELINE), "variant"] = "baseline_v2"
    phase_alias = dict(phase_summary)
    phase_alias["baseline_v2"] = phase_summary[BASELINE]
    rolling_alias = dict(rolling_summary)
    rolling_alias["baseline_v2"] = rolling_summary[BASELINE]
    return parent.classify_slope(
        alias,
        phase_alias,
        rolling_alias,
        removed_name=removed_name,
        direction_name=direction_name,
    )


def main() -> None:
    args = parse_args()
    parent = load_parent()
    formation = parent.load_formation()
    engine = formation.load_pinned(
        formation.ENGINE_PATH,
        formation.ENGINE_SHA256,
        "hype_v3_ablation_engine",
    )
    base = formation.load_pinned(
        formation.BASE_PATH,
        formation.BASE_SHA256,
        "hype_v3_ablation_base",
    )
    selected = formation.read_pinned_json(
        formation.SUMMARY_PATH,
        formation.SUMMARY_SHA256,
    )["historically_profitable_all_checks"][0]
    long_config = engine.Config(**selected["long_config"])
    v2_short_config = engine.Config(**selected["short_config"])
    short_config = replace(v2_short_config, exit_buffer_atr=0.75)
    variants = build_oat_variants(parent, long_config, short_config)
    slope_grid = parent.build_slope_grid(long_config, short_config)
    if len(variants) != 28 or len({row.name for row in variants}) != 28:
        raise RuntimeError("V3 OAT variant registry drift")
    if len(slope_grid) != 32 or len({row.name for row in slope_grid}) != 32:
        raise RuntimeError("V3 slope grid registry drift")

    if args.self_test:
        by_name = {row.name: row for row in variants}
        assert by_name[BASELINE].short_config.exit_buffer_atr == 0.75
        assert (
            by_name["short_exit_hysteresis_v2_025"]
            .short_config.exit_buffer_atr
            == 0.25
        )
        assert (
            by_name["short_exit_hysteresis_buffer_removed"]
            .short_config.exit_buffer_atr
            == 0.0
        )
        assert (
            by_name["long_entry_slope_removed"].long_config.slope_min_atr
            < -1e8
        )
        assert not by_name["forced_reversal_removed"].reversal_enabled
        print("self-test passed: 28 V3 OAT and 32 slope-grid variants")
        return

    reversal_backtest = formation.build_reversal_backtest(engine)
    market_parent = base.load_parent()
    market_engine = market_parent.load_engine()
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
            market_parent,
            source_hourly,
            hourly_quality,
            source_funding,
            funding_quality,
            phase_hours=phase,
        )
        return book, engine.build_features(book, source_hourly, source_funding)

    books: dict[int, Any] = {}
    features: dict[int, Any] = {}
    for phase in (0, 12):
        books[phase], features[phase] = build(phase)
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

    book = books[0]
    split = int(pd.DatetimeIndex(book.ts).searchsorted(HOLDOUT_START))
    windows = {
        "prefit": (0, split),
        "last_90d_flat": (split, book.count),
        "full": (0, book.count),
    }
    oat_rows: list[dict[str, Any]] = []
    recent_rows: list[dict[str, Any]] = []
    rolling_rows: list[dict[str, Any]] = []
    full_results: dict[str, Any] = {}
    for variant in variants:
        for window, (start, end) in windows.items():
            result = parent.run_variant(
                engine,
                reversal_backtest,
                variant,
                book,
                features[0],
                start=start,
                end=end,
                slippage=engine.BASE_SLIPPAGE,
                retain=window == "full",
            )
            oat_rows.append(
                parent.result_row(
                    formation,
                    result,
                    variant,
                    window=window,
                    scenario="base_4bps",
                )
            )
            if window == "full":
                full_results[variant.name] = result
                recent_rows.extend(
                    {"variant": variant.name, **row}
                    for row in engine.recent_slices(result)
                )
        for scenario, slippage, lag in (
            ("stress_8bps", engine.STRESS_SLIPPAGE, 0),
            ("one_day_extra_delay", engine.BASE_SLIPPAGE, 1),
        ):
            result = parent.run_variant(
                engine,
                reversal_backtest,
                variant,
                book,
                features[0],
                start=0,
                end=book.count,
                slippage=slippage,
                signal_lag=lag,
            )
            oat_rows.append(
                parent.result_row(
                    formation,
                    result,
                    variant,
                    window="full",
                    scenario=scenario,
                )
            )
        phase12 = parent.run_variant(
            engine,
            reversal_backtest,
            variant,
            books[12],
            features[12],
            start=0,
            end=books[12].count,
            slippage=engine.BASE_SLIPPAGE,
        )
        oat_rows.append(
            parent.result_row(
                formation,
                phase12,
                variant,
                window="full",
                scenario="phase_12h",
            )
        )
        rolling_rows.extend(
            parent.rolling_rows(
                engine,
                reversal_backtest,
                variant,
                book,
                features[0],
            )
        )

    baseline = full_results[BASELINE]
    if not math.isclose(
        baseline.metrics["equity_multiple"],
        V3_EQUITY_MULTIPLE,
        rel_tol=1e-10,
        abs_tol=1e-10,
    ):
        raise RuntimeError("V3 ablation baseline anchor drift")

    by_name = {variant.name: variant for variant in variants}
    phase_rows: list[dict[str, Any]] = []
    for name in KEY_SLOPE_VARIANTS:
        variant = by_name[name]
        for phase in range(24):
            if phase in phase_errors:
                continue
            result = parent.run_variant(
                engine,
                reversal_backtest,
                variant,
                phase_books[phase],
                phase_features[phase],
                start=0,
                end=phase_books[phase].count,
                slippage=engine.BASE_SLIPPAGE,
            )
            phase_rows.append(
                {
                    "variant": name,
                    "phase_hours": phase,
                    **result.metrics,
                    **parent.attribution(formation, result, variant),
                }
            )

    grid_rows: list[dict[str, Any]] = []
    for variant in slope_grid:
        match = re.fullmatch(
            r"grid_L-(.+)_S-(.+)_SX-(on|off)",
            variant.name,
        )
        if match is None:
            raise RuntimeError(f"cannot parse slope-grid identity: {variant.name}")
        identity = {
            "long_slope_mode": match.group(1),
            "short_slope_mode": match.group(2),
            "short_slope_exit": match.group(3),
        }
        for window, (start, end) in windows.items():
            result = parent.run_variant(
                engine,
                reversal_backtest,
                variant,
                book,
                features[0],
                start=start,
                end=end,
                slippage=engine.BASE_SLIPPAGE,
            )
            grid_rows.append(
                {
                    **identity,
                    **parent.result_row(
                        formation,
                        result,
                        variant,
                        window=window,
                        scenario="base_4bps",
                    ),
                }
            )
        for scenario, target_book, target_features, slippage in (
            (
                "stress_8bps",
                book,
                features[0],
                engine.STRESS_SLIPPAGE,
            ),
            (
                "phase_12h",
                books[12],
                features[12],
                engine.BASE_SLIPPAGE,
            ),
        ):
            result = parent.run_variant(
                engine,
                reversal_backtest,
                variant,
                target_book,
                target_features,
                start=0,
                end=target_book.count,
                slippage=slippage,
            )
            grid_rows.append(
                {
                    **identity,
                    **parent.result_row(
                        formation,
                        result,
                        variant,
                        window="full",
                        scenario=scenario,
                    ),
                }
            )

    latest_book, latest_features = build(0, latest=True)
    latest_rows: list[dict[str, Any]] = []
    for name in KEY_SLOPE_VARIANTS:
        variant = by_name[name]
        result = parent.run_variant(
            engine,
            reversal_backtest,
            variant,
            latest_book,
            latest_features,
            start=0,
            end=latest_book.count,
            slippage=engine.BASE_SLIPPAGE,
        )
        latest_rows.append(
            parent.result_row(
                formation,
                result,
                variant,
                window="latest_extension",
                scenario="base_4bps",
            )
        )

    oat_frame = pd.DataFrame(oat_rows)
    phase_frame = pd.DataFrame(phase_rows)
    rolling_frame = pd.DataFrame(rolling_rows)
    grid_frame = pd.DataFrame(grid_rows)
    phase_summary = parent.summaries(phase_frame, key="variant")
    rolling_summary = parent.summaries(rolling_frame, key="variant")
    judgments = {
        "long_entry_slope": classify_slope(
            parent,
            oat_frame,
            phase_summary,
            rolling_summary,
            removed_name="long_entry_slope_removed",
            direction_name="long_entry_slope_direction_only",
        ),
        "short_entry_slope": classify_slope(
            parent,
            oat_frame,
            phase_summary,
            rolling_summary,
            removed_name="short_entry_slope_removed",
            direction_name="short_entry_slope_direction_only",
        ),
        "short_slope_exit": classify_slope(
            parent,
            oat_frame,
            phase_summary,
            rolling_summary,
            removed_name="short_slope_exit_removed",
            direction_name=None,
        ),
        "all_slopes_removed": classify_slope(
            parent,
            oat_frame,
            phase_summary,
            rolling_summary,
            removed_name="all_slopes_removed",
            direction_name=None,
        ),
    }
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "HYPE-1D-MA7-Asymmetric-Body-Trend",
        "version": "HYPE-1D-MA7-Asymmetric-Body-Trend-V3",
        "status": "registered V3 unchanged; ablation diagnostic only",
        "contract": (
            "specs/hype-1d-ma7-abt-v3-full-parameter-ablation-contract-"
            "2026-08-07.md"
        ),
        "pins": {
            "parent_path": str(PARENT_PATH.relative_to(ROOT)),
            "parent_sha256": PARENT_SHA256,
            "formation_sha256": parent.FORMATION_SHA256,
            "engine_sha256": formation.ENGINE_SHA256,
            "base_sha256": formation.BASE_SHA256,
        },
        "baseline_configs": {
            "long": asdict(long_config),
            "short": asdict(short_config),
        },
        "inactive_parameter_notes": [
            "confirm_days=1 has no removable multi-day confirmation layer",
            "long entry_buffer/hard_stop/slope_exit are already zero",
            "pullback_lookback and breakout_lookback are inactive under reclaim",
        ],
        "data_quality": {
            "hourly": hourly_quality,
            "funding": funding_quality,
        },
        "counts": {
            "oat_variants": len(variants),
            "slope_grid_variants": len(slope_grid),
            "phase_variants": len(KEY_SLOPE_VARIANTS),
            "phase_offsets": 24,
            "phase_offsets_valid": len(phase_books),
        },
        "phase_errors": phase_errors,
        "slope_judgments": judgments,
        "phase_summary": phase_summary,
        "rolling_90d_summary": rolling_summary,
        "evidence_role": (
            "post-reveal V3 mechanism ablation; not clean OOS or selection"
        ),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"hype_1d_v3_full_parameter_ablation_{args.run_date}"
    (ARTIFACT_DIR / f"{stem}_summary.json").write_text(
        json.dumps(
            parent.clean(payload),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    oat_frame.to_csv(ARTIFACT_DIR / f"{stem}_oat.csv", index=False)
    grid_frame.to_csv(ARTIFACT_DIR / f"{stem}_slope_grid.csv", index=False)
    phase_frame.to_csv(ARTIFACT_DIR / f"{stem}_phase24.csv", index=False)
    pd.DataFrame(recent_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_recent.csv",
        index=False,
    )
    rolling_frame.to_csv(
        ARTIFACT_DIR / f"{stem}_rolling_90d.csv",
        index=False,
    )
    pd.DataFrame(latest_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_latest.csv",
        index=False,
    )
    print(json.dumps(parent.clean(judgments), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
