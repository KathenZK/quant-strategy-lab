from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
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
NO_SLOPE_GATE = -1_000_000_000.0
NO_NATURAL_ENTRY = 1_000_000_000.0
KEY_SLOPE_VARIANTS = (
    "baseline_v2",
    "long_entry_slope_direction_only",
    "long_entry_slope_removed",
    "short_entry_slope_direction_only",
    "short_entry_slope_removed",
    "both_entry_slopes_removed",
    "short_slope_exit_removed",
    "all_slopes_removed",
)


@dataclass(frozen=True, slots=True)
class Variant:
    name: str
    group: str
    change: str
    long_config: Any
    short_config: Any
    reversal_enabled: bool = True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Full active-parameter and slope ablation for HYPE MA7 V2."
    )
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def load_formation() -> Any:
    actual = hashlib.sha256(FORMATION_PATH.read_bytes()).hexdigest()
    if actual != FORMATION_SHA256:
        raise RuntimeError(
            f"formation script drift: expected {FORMATION_SHA256}, got {actual}"
        )
    spec = importlib.util.spec_from_file_location(
        "hype_v2_full_ablation_formation",
        FORMATION_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {FORMATION_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_oat_variants(long_config: Any, short_config: Any) -> list[Variant]:
    def variant(
        name: str,
        group: str,
        change: str,
        *,
        long: Any = long_config,
        short: Any = short_config,
        reversal: bool = True,
    ) -> Variant:
        return Variant(name, group, change, long, short, reversal)

    return [
        variant("baseline_v2", "baseline", "none"),
        variant(
            "long_entry_slope_direction_only",
            "slope",
            "long slope_min_atr 0.02 -> 0",
            long=replace(long_config, slope_min_atr=0.0),
        ),
        variant(
            "long_entry_slope_removed",
            "slope",
            "bypass long entry slope gate",
            long=replace(long_config, slope_min_atr=NO_SLOPE_GATE),
        ),
        variant(
            "short_entry_slope_direction_only",
            "slope",
            "short slope_min_atr 0.02 -> 0",
            short=replace(short_config, slope_min_atr=0.0),
        ),
        variant(
            "short_entry_slope_removed",
            "slope",
            "bypass short natural-entry slope gate",
            short=replace(short_config, slope_min_atr=NO_SLOPE_GATE),
        ),
        variant(
            "both_entry_slopes_removed",
            "slope",
            "bypass both natural-entry slope gates",
            long=replace(long_config, slope_min_atr=NO_SLOPE_GATE),
            short=replace(short_config, slope_min_atr=NO_SLOPE_GATE),
        ),
        variant(
            "short_slope_exit_removed",
            "slope",
            "short slope_exit_lookback 1 -> 0",
            short=replace(short_config, slope_exit_lookback=0),
        ),
        variant(
            "all_slopes_removed",
            "slope",
            "bypass both entry slopes and remove short slope exit",
            long=replace(long_config, slope_min_atr=NO_SLOPE_GATE),
            short=replace(
                short_config,
                slope_min_atr=NO_SLOPE_GATE,
                slope_exit_lookback=0,
            ),
        ),
        variant(
            "long_reclaim_removed_regime",
            "entry_event",
            "long entry_mode reclaim -> regime",
            long=replace(long_config, entry_mode="regime"),
        ),
        variant(
            "short_reclaim_removed_regime",
            "entry_event",
            "short entry_mode reclaim -> regime",
            short=replace(short_config, entry_mode="regime"),
        ),
        variant(
            "both_reclaims_removed_regime",
            "entry_event",
            "both entry_mode reclaim -> regime",
            long=replace(long_config, entry_mode="regime"),
            short=replace(short_config, entry_mode="regime"),
        ),
        variant(
            "short_entry_buffer_removed",
            "entry_event",
            "short entry_buffer_atr 0.10 -> 0",
            short=replace(short_config, entry_buffer_atr=0.0),
        ),
        variant(
            "natural_long_entry_removed",
            "component",
            "disable natural long entries",
            long=replace(long_config, slope_min_atr=NO_NATURAL_ENTRY),
        ),
        variant(
            "natural_short_entry_removed",
            "component",
            "disable natural short entries; keep forced reversals",
            short=replace(short_config, slope_min_atr=NO_NATURAL_ENTRY),
        ),
        variant(
            "long_exit_hysteresis_buffer_removed",
            "exit",
            "long exit_buffer_atr 0.75 -> 0",
            long=replace(long_config, exit_buffer_atr=0.0),
        ),
        variant(
            "short_exit_hysteresis_buffer_removed",
            "exit",
            "short exit_buffer_atr 0.25 -> 0",
            short=replace(short_config, exit_buffer_atr=0.0),
        ),
        variant(
            "forced_reversal_removed",
            "state_transition",
            "disable V2 long trailing-stop to short reversal",
            reversal=False,
        ),
        variant(
            "long_trailing_stop_removed",
            "protection",
            "long trail_atr 1.5 -> 0; no forced reversal trigger",
            long=replace(long_config, trail_atr=0.0),
        ),
        variant(
            "short_hard_stop_removed",
            "protection",
            "short hard_stop_atr 1.5 -> 0",
            short=replace(short_config, hard_stop_atr=0.0),
        ),
        variant(
            "short_trailing_stop_removed",
            "protection",
            "short trail_atr 4.0 -> 0",
            short=replace(short_config, trail_atr=0.0),
        ),
        variant(
            "short_all_protective_stops_removed",
            "protection",
            "short hard_stop_atr/trail_atr -> 0",
            short=replace(short_config, hard_stop_atr=0.0, trail_atr=0.0),
        ),
        variant(
            "long_max_hold_removed",
            "max_hold",
            "long max_hold_days 90 -> 0",
            long=replace(long_config, max_hold_days=0),
        ),
        variant(
            "short_max_hold_removed",
            "max_hold",
            "short max_hold_days 20 -> 0",
            short=replace(short_config, max_hold_days=0),
        ),
        variant(
            "both_max_hold_removed",
            "max_hold",
            "both max_hold_days -> 0",
            long=replace(long_config, max_hold_days=0),
            short=replace(short_config, max_hold_days=0),
        ),
        variant(
            "long_cooldown_removed",
            "cooldown",
            "long cooldown_days 2 -> 0",
            long=replace(long_config, cooldown_days=0),
        ),
        variant(
            "short_cooldown_removed",
            "cooldown",
            "short cooldown_days 5 -> 0",
            short=replace(short_config, cooldown_days=0),
        ),
        variant(
            "both_cooldowns_removed",
            "cooldown",
            "both cooldown_days -> 0",
            long=replace(long_config, cooldown_days=0),
            short=replace(short_config, cooldown_days=0),
        ),
    ]


def slope_mode_value(mode: str) -> float:
    return {
        "removed": NO_SLOPE_GATE,
        "direction_only": 0.0,
        "base_0p02": 0.02,
        "strict_0p04": 0.04,
    }[mode]


def build_slope_grid(long_config: Any, short_config: Any) -> list[Variant]:
    rows: list[Variant] = []
    modes = ("removed", "direction_only", "base_0p02", "strict_0p04")
    for long_mode in modes:
        for short_mode in modes:
            for short_exit in ("on", "off"):
                rows.append(
                    Variant(
                        name=(
                            f"grid_L-{long_mode}_S-{short_mode}"
                            f"_SX-{short_exit}"
                        ),
                        group="slope_grid",
                        change="pre-registered slope factorial",
                        long_config=replace(
                            long_config,
                            slope_min_atr=slope_mode_value(long_mode),
                        ),
                        short_config=replace(
                            short_config,
                            slope_min_atr=slope_mode_value(short_mode),
                            slope_exit_lookback=(
                                short_config.slope_exit_lookback
                                if short_exit == "on"
                                else 0
                            ),
                        ),
                    )
                )
    return rows


def run_variant(
    engine: Any,
    reversal_backtest: Any,
    variant: Variant,
    book: Any,
    features: Any,
    *,
    start: int,
    end: int,
    slippage: float,
    signal_lag: int = 0,
    retain: bool = False,
) -> Any:
    function = reversal_backtest if variant.reversal_enabled else engine.backtest
    return function(
        book,
        features,
        long_config=variant.long_config,
        short_config=variant.short_config,
        start_index=start,
        terminal_index=end,
        slippage=slippage,
        signal_lag=signal_lag,
        retain=retain,
    )


def attribution(formation: Any, result: Any, variant: Variant) -> dict[str, Any]:
    label = (
        "T1_trailing_stop_short_reversal"
        if variant.reversal_enabled
        else "T0_baseline"
    )
    return formation.attribution(formation.annotate_trades(result, label))


def result_row(
    formation: Any,
    result: Any,
    variant: Variant,
    *,
    window: str,
    scenario: str,
) -> dict[str, Any]:
    return {
        "variant": variant.name,
        "group": variant.group,
        "change": variant.change,
        "window": window,
        "scenario": scenario,
        **result.metrics,
        **attribution(formation, result, variant),
    }


def rolling_rows(
    engine: Any,
    reversal_backtest: Any,
    variant: Variant,
    book: Any,
    features: Any,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    while start + 90 <= book.count:
        result = run_variant(
            engine,
            reversal_backtest,
            variant,
            book,
            features,
            start=start,
            end=start + 90,
            slippage=engine.BASE_SLIPPAGE,
        )
        rows.append(
            {
                "variant": variant.name,
                "window_index": len(rows),
                **result.metrics,
            }
        )
        start += 30
    return rows


def summaries(
    frame: pd.DataFrame,
    *,
    key: str,
) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for name, selected in frame.groupby(key):
        output[str(name)] = {
            "count": int(len(selected)),
            "positive": int((selected["net_return_pct"] > 0.0).sum()),
            "median_return_pct": float(selected["net_return_pct"].median()),
            "min_return_pct": float(selected["net_return_pct"].min()),
            "worst_mdd_pct": float(selected["max_drawdown_pct"].min()),
            "median_sharpe": float(selected["sharpe"].median()),
            "bankrupt": int(selected["bankrupt_intraday"].sum()),
        }
    return output


def classify_slope(
    oat: pd.DataFrame,
    phase_summary: dict[str, dict[str, Any]],
    rolling_summary: dict[str, dict[str, Any]],
    *,
    removed_name: str,
    direction_name: str | None,
) -> dict[str, Any]:
    def metric(name: str, scenario: str, window: str = "full") -> pd.Series:
        return oat.loc[
            oat["variant"].eq(name)
            & oat["scenario"].eq(scenario)
            & oat["window"].eq(window)
        ].iloc[0]

    baseline = {
        "full": metric("baseline_v2", "base_4bps"),
        "stress": metric("baseline_v2", "stress_8bps"),
        "prefit": metric("baseline_v2", "base_4bps", "prefit"),
        "last90": metric("baseline_v2", "base_4bps", "last_90d_flat"),
    }
    removed = {
        "full": metric(removed_name, "base_4bps"),
        "stress": metric(removed_name, "stress_8bps"),
        "prefit": metric(removed_name, "base_4bps", "prefit"),
        "last90": metric(removed_name, "base_4bps", "last_90d_flat"),
    }
    phase_base = phase_summary["baseline_v2"]
    phase_removed = phase_summary[removed_name]
    rolling_base = rolling_summary["baseline_v2"]
    rolling_removed = rolling_summary[removed_name]

    robust_regressions = {
        "prefit": (
            removed["prefit"]["net_return_pct"]
            < baseline["prefit"]["net_return_pct"]
        ),
        "last90": (
            removed["last90"]["net_return_pct"]
            < baseline["last90"]["net_return_pct"]
        ),
        "rolling": (
            rolling_removed["positive"] < rolling_base["positive"]
            or rolling_removed["median_return_pct"]
            < rolling_base["median_return_pct"]
        ),
        "phase": (
            phase_removed["positive"] < phase_base["positive"]
            or phase_removed["median_return_pct"]
            < phase_base["median_return_pct"]
        ),
    }
    full_down = (
        removed["full"]["net_return_pct"]
        < baseline["full"]["net_return_pct"]
    )
    stress_down = (
        removed["stress"]["net_return_pct"]
        < baseline["stress"]["net_return_pct"]
    )
    mdd_ok = (
        removed["full"]["max_drawdown_pct"]
        >= baseline["full"]["max_drawdown_pct"] - 5.0
    )
    regressions = sum(robust_regressions.values())
    if full_down and stress_down and regressions >= 2:
        verdict = "必要"
    elif not full_down and not stress_down and mdd_ok and regressions <= 1:
        verdict = "不必要"
    else:
        verdict = "证据混合"

    direction_metrics = None
    if direction_name is not None:
        direction_full = metric(direction_name, "base_4bps")
        direction_stress = metric(direction_name, "stress_8bps")
        direction_metrics = {
            "name": direction_name,
            "full_return_delta_pp": float(
                direction_full["net_return_pct"]
                - baseline["full"]["net_return_pct"]
            ),
            "stress_return_delta_pp": float(
                direction_stress["net_return_pct"]
                - baseline["stress"]["net_return_pct"]
            ),
            "mdd_delta_pp": float(
                direction_full["max_drawdown_pct"]
                - baseline["full"]["max_drawdown_pct"]
            ),
        }
        if (
            verdict == "必要"
            and direction_metrics["full_return_delta_pp"] >= 0.0
            and direction_metrics["stress_return_delta_pp"] >= 0.0
            and direction_metrics["mdd_delta_pp"] >= -5.0
        ):
            verdict = "只需方向、不需0.02阈值"

    return {
        "verdict": verdict,
        "removed_variant": removed_name,
        "full_return_delta_pp": float(
            removed["full"]["net_return_pct"]
            - baseline["full"]["net_return_pct"]
        ),
        "stress_return_delta_pp": float(
            removed["stress"]["net_return_pct"]
            - baseline["stress"]["net_return_pct"]
        ),
        "mdd_delta_pp": float(
            removed["full"]["max_drawdown_pct"]
            - baseline["full"]["max_drawdown_pct"]
        ),
        "robust_regressions": robust_regressions,
        "direction_only": direction_metrics,
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
    formation = load_formation()
    engine = formation.load_pinned(
        formation.ENGINE_PATH,
        formation.ENGINE_SHA256,
        "hype_v2_ablation_engine",
    )
    base = formation.load_pinned(
        formation.BASE_PATH,
        formation.BASE_SHA256,
        "hype_v2_ablation_base",
    )
    selected = formation.read_pinned_json(
        formation.SUMMARY_PATH,
        formation.SUMMARY_SHA256,
    )["historically_profitable_all_checks"][0]
    long_config = engine.Config(**selected["long_config"])
    short_config = engine.Config(**selected["short_config"])
    variants = build_oat_variants(long_config, short_config)
    slope_grid = build_slope_grid(long_config, short_config)
    if len(variants) != 27 or len({row.name for row in variants}) != 27:
        raise RuntimeError("OAT variant registry drift")
    if len(slope_grid) != 32 or len({row.name for row in slope_grid}) != 32:
        raise RuntimeError("slope grid registry drift")

    if args.self_test:
        by_name = {row.name: row for row in variants}
        if by_name["long_entry_slope_removed"].long_config.slope_min_atr >= -1e8:
            raise AssertionError("long slope removal not configured")
        if by_name["forced_reversal_removed"].reversal_enabled:
            raise AssertionError("forced reversal removal not configured")
        if by_name["short_all_protective_stops_removed"].short_config.hard_stop_atr:
            raise AssertionError("short hard stop removal not configured")
        if by_name["short_all_protective_stops_removed"].short_config.trail_atr:
            raise AssertionError("short trailing stop removal not configured")
        print("self-test passed: 27 OAT variants and 32 slope-grid variants")
        return

    reversal_backtest = formation.build_reversal_backtest(engine)
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
    rolling: list[dict[str, Any]] = []
    full_results: dict[str, Any] = {}
    for variant in variants:
        for window, (start, end) in windows.items():
            result = run_variant(
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
                result_row(
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
                    {
                        "variant": variant.name,
                        **row,
                    }
                    for row in engine.recent_slices(result)
                )
        for scenario, slippage, lag in (
            ("stress_8bps", engine.STRESS_SLIPPAGE, 0),
            ("one_day_extra_delay", engine.BASE_SLIPPAGE, 1),
        ):
            result = run_variant(
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
                result_row(
                    formation,
                    result,
                    variant,
                    window="full",
                    scenario=scenario,
                )
            )
        phase12 = run_variant(
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
            result_row(
                formation,
                phase12,
                variant,
                window="full",
                scenario="phase_12h",
            )
        )
        rolling.extend(
            rolling_rows(
                engine,
                reversal_backtest,
                variant,
                book,
                features[0],
            )
        )

    baseline = full_results["baseline_v2"]
    if not math.isclose(
        baseline.metrics["equity_multiple"],
        V2_EQUITY_MULTIPLE,
        rel_tol=1e-10,
        abs_tol=1e-10,
    ):
        raise RuntimeError("V2 ablation baseline anchor drift")

    by_name = {variant.name: variant for variant in variants}
    phase_rows: list[dict[str, Any]] = []
    for name in KEY_SLOPE_VARIANTS:
        variant = by_name[name]
        for phase in range(24):
            if phase in phase_errors:
                continue
            result = run_variant(
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
                    **attribution(formation, result, variant),
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
            result = run_variant(
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
                    **result_row(
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
            result = run_variant(
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
                    **result_row(
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
        result = run_variant(
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
            result_row(
                formation,
                result,
                variant,
                window="latest_extension",
                scenario="base_4bps",
            )
        )

    oat_frame = pd.DataFrame(oat_rows)
    phase_frame = pd.DataFrame(phase_rows)
    rolling_frame = pd.DataFrame(rolling)
    grid_frame = pd.DataFrame(grid_rows)
    phase_summary = summaries(phase_frame, key="variant")
    rolling_summary = summaries(rolling_frame, key="variant")
    judgments = {
        "long_entry_slope": classify_slope(
            oat_frame,
            phase_summary,
            rolling_summary,
            removed_name="long_entry_slope_removed",
            direction_name="long_entry_slope_direction_only",
        ),
        "short_entry_slope": classify_slope(
            oat_frame,
            phase_summary,
            rolling_summary,
            removed_name="short_entry_slope_removed",
            direction_name="short_entry_slope_direction_only",
        ),
        "short_slope_exit": classify_slope(
            oat_frame,
            phase_summary,
            rolling_summary,
            removed_name="short_slope_exit_removed",
            direction_name=None,
        ),
        "all_slopes_removed": classify_slope(
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
        "version": "HYPE-1D-MA7-Asymmetric-Body-Trend-V2",
        "status": "registered V2 unchanged; ablation diagnostic only",
        "contract": (
            "specs/hype-1d-ma7-abt-v2-full-parameter-ablation-contract-"
            "2026-08-06.md"
        ),
        "pins": {
            "formation_path": str(FORMATION_PATH.relative_to(ROOT)),
            "formation_sha256": FORMATION_SHA256,
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
            "post-reveal mechanism ablation; not clean OOS and not version selection"
        ),
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"hype_1d_v2_full_parameter_ablation_{args.run_date}"
    (ARTIFACT_DIR / f"{stem}_summary.json").write_text(
        json.dumps(clean(payload), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    oat_frame.to_csv(ARTIFACT_DIR / f"{stem}_oat.csv", index=False)
    grid_frame.to_csv(ARTIFACT_DIR / f"{stem}_slope_grid.csv", index=False)
    phase_frame.to_csv(ARTIFACT_DIR / f"{stem}_phase24.csv", index=False)
    pd.DataFrame(recent_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_recent.csv", index=False
    )
    rolling_frame.to_csv(
        ARTIFACT_DIR / f"{stem}_rolling_90d.csv", index=False
    )
    pd.DataFrame(latest_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_latest.csv", index=False
    )
    print(json.dumps(clean(judgments), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
