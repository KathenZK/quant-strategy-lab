from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import UTC, datetime
import hashlib
import importlib.util
import inspect
import json
import math
from pathlib import Path
import sys
import textwrap
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
HOLDOUT_START = pd.Timestamp("2026-05-01T00:00:00Z")
V3_EQUITY_MULTIPLE = 4.508464159893385
V3_CONTROL = "V3_CONTROL"
TRAIL_FLAT = "TRAIL_FLAT_CONTROL"
DAILY_CROSS = "DAILY_CROSS_REVERSAL"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit V3 daily close cross below MA7 short reversal."
    )
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def load_formation() -> Any:
    spec = importlib.util.spec_from_file_location(
        "hype_v3_daily_cross_formation",
        FORMATION_PATH,
    )
    actual = hashlib.sha256(FORMATION_PATH.read_bytes()).hexdigest()
    if actual != FORMATION_SHA256:
        raise RuntimeError(
            f"formation drift: expected {FORMATION_SHA256}, got {actual}"
        )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {FORMATION_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_daily_cross_backtest(engine: Any) -> Any:
    source = textwrap.dedent(inspect.getsource(engine.backtest))
    source = source.replace(
        "def backtest(",
        "def daily_ma7_close_cross_reversal_backtest(",
        1,
    )
    old = """\
        entered_after_open = False
        exited_at_open = False
        decision_index = index - 1 - signal_lag
        if index < terminal_index and side != 0 and decision_index >= 0:
"""
    new = """\
        entered_after_open = False
        exited_at_open = False
        reversed_at_open = False
        decision_index = index - 1 - signal_lag
        if (
            index < terminal_index
            and side > 0
            and short_config is not None
            and decision_index >= 1
        ):
            current_ma = features.ma7[decision_index]
            prior_ma = features.ma7[decision_index - 1]
            current_close = book.close[decision_index]
            prior_close = book.close[decision_index - 1]
            if (
                np.isfinite(current_ma)
                and np.isfinite(prior_ma)
                and np.isfinite(current_close)
                and np.isfinite(prior_close)
                and prior_close >= prior_ma
                and current_close < current_ma
            ):
                close(
                    ts,
                    current_open,
                    "ma7_close_cross_reversal",
                    index,
                )
                enter(
                    short_config,
                    ts,
                    current_open,
                    index,
                    decision_index,
                )
                cooldown_left = 0
                reversed_at_open = True
                action = "reverse_long_ma7_close_cross_to_short"
        if (
            index < terminal_index
            and side != 0
            and decision_index >= 0
            and not reversed_at_open
        ):
"""
    if source.count(old) != 1:
        raise RuntimeError("pinned engine loop no longer matches cross insertion")
    source = source.replace(old, new, 1)
    namespace = dict(engine.__dict__)
    exec(compile(source, str(engine.__file__), "exec"), namespace)
    return namespace["daily_ma7_close_cross_reversal_backtest"]


def annotate_trades(
    formation: Any,
    result: Any,
    variant: str,
) -> pd.DataFrame:
    if variant == V3_CONTROL:
        return formation.annotate_trades(
            result,
            "T1_trailing_stop_short_reversal",
        )
    frame = pd.DataFrame(result.trades)
    if frame.empty:
        return frame
    frame["entry_source"] = "original_entry"
    if variant == DAILY_CROSS:
        for index in range(1, len(frame)):
            previous = frame.iloc[index - 1]
            current = frame.iloc[index]
            if (
                previous["side"] == "long"
                and previous["exit_reason"] == "ma7_close_cross_reversal"
                and current["side"] == "short"
                and pd.Timestamp(previous["exit_ts"])
                == pd.Timestamp(current["entry_ts"])
            ):
                frame.loc[index, "entry_source"] = (
                    "forced_daily_ma7_close_cross_reversal"
                )
    return frame


def attribution(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {
            "trailing_reversal_trades": 0,
            "trailing_reversal_net_pnl": 0.0,
            "close_cross_reversal_trades": 0,
            "close_cross_reversal_net_pnl": 0.0,
        }
    trailing = frame.loc[
        frame["entry_source"].eq("forced_trailing_stop_reversal")
    ]
    close_cross = frame.loc[
        frame["entry_source"].eq(
            "forced_daily_ma7_close_cross_reversal"
        )
    ]
    return {
        "trailing_reversal_trades": int(len(trailing)),
        "trailing_reversal_net_pnl": float(trailing["net_pnl"].sum()),
        "close_cross_reversal_trades": int(len(close_cross)),
        "close_cross_reversal_net_pnl": float(close_cross["net_pnl"].sum()),
    }


def exposure_pct(result: Any) -> float:
    positions = [
        int(row["position"])
        for row in result.path
        if row["action"] != "terminal"
    ]
    return (
        100.0 * sum(position != 0 for position in positions) / len(positions)
        if positions
        else math.nan
    )


def run(
    engine: Any,
    v3_backtest: Any,
    cross_backtest: Any,
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
) -> Any:
    function = {
        V3_CONTROL: v3_backtest,
        TRAIL_FLAT: engine.backtest,
        DAILY_CROSS: cross_backtest,
    }[variant]
    return function(
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


def result_row(
    formation: Any,
    result: Any,
    variant: str,
    *,
    window: str,
    scenario: str,
) -> dict[str, Any]:
    trades = annotate_trades(formation, result, variant)
    return {
        "variant": variant,
        "window": window,
        "scenario": scenario,
        **result.metrics,
        **attribution(trades),
        "exposure_pct": exposure_pct(result),
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


def cross_evidence(
    frame: pd.DataFrame,
    book: Any,
    features: Any,
    short_config: Any,
) -> list[dict[str, Any]]:
    timestamps = pd.DatetimeIndex(book.ts)
    output = []
    selected_indexes = frame.index[
        frame["entry_source"].eq(
            "forced_daily_ma7_close_cross_reversal"
        )
    ]
    for frame_index in selected_indexes:
        row = frame.loc[frame_index]
        previous = frame.iloc[frame.index.get_loc(frame_index) - 1]
        entry_ts = pd.Timestamp(row["entry_ts"])
        entry_index = int(timestamps.searchsorted(entry_ts.floor("1D")))
        signal_index = entry_index - 1
        prior = signal_index - 1
        atr = float(features.atr7[signal_index])
        slope_prior = signal_index - short_config.slope_lookback
        down_slope_atr = float(
            (
                features.ma7[slope_prior]
                - features.ma7[signal_index]
            )
            / atr
        )
        gap_atr = float(
            (features.ma7[signal_index] - book.close[signal_index]) / atr
        )
        evidence = {
            "short_entry_ts": entry_ts.isoformat(),
            "short_exit_ts": str(row["exit_ts"]),
            "short_net_return_pct": float(row["net_return"]) * 100.0,
            "preceding_long_entry_ts": str(previous["entry_ts"]),
            "preceding_long_bars_held": int(previous["bars_held"]),
            "preceding_long_net_return_pct": (
                float(previous["net_return"]) * 100.0
            ),
            "prior_day": timestamps[prior].isoformat(),
            "prior_close": float(book.close[prior]),
            "prior_ma7": float(features.ma7[prior]),
            "signal_day": timestamps[signal_index].isoformat(),
            "signal_close": float(book.close[signal_index]),
            "signal_ma7": float(features.ma7[signal_index]),
            "signal_atr7": atr,
            "below_ma_gap_atr": gap_atr,
            "down_slope_atr": down_slope_atr,
        }
        evidence["condition_valid"] = bool(
            evidence["prior_close"] >= evidence["prior_ma7"]
            and evidence["signal_close"] < evidence["signal_ma7"]
        )
        evidence["natural_short_buffer_pass"] = bool(
            gap_atr > short_config.entry_buffer_atr
        )
        evidence["natural_short_slope_pass"] = bool(
            down_slope_atr >= short_config.slope_min_atr
        )
        evidence["natural_short_would_pass"] = bool(
            evidence["condition_valid"]
            and evidence["natural_short_buffer_pass"]
            and evidence["natural_short_slope_pass"]
        )
        output.append(evidence)
    return output


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
        "hype_v3_daily_cross_engine",
    )
    base = formation.load_pinned(
        formation.BASE_PATH,
        formation.BASE_SHA256,
        "hype_v3_daily_cross_base",
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
    cross_backtest = build_daily_cross_backtest(engine)
    v3_backtest = formation.build_reversal_backtest(engine)
    if args.self_test:
        source = inspect.getsource(engine.backtest)
        assert "reversed_at_open" not in source
        assert cross_backtest.__name__ == (
            "daily_ma7_close_cross_reversal_backtest"
        )
        assert short_config.exit_buffer_atr == 0.75
        print("self-test passed: close-cross reversal compiled")
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
    variants = (V3_CONTROL, TRAIL_FLAT, DAILY_CROSS)
    rows: list[dict[str, Any]] = []
    recent_rows: list[dict[str, Any]] = []
    rolling_rows: list[dict[str, Any]] = []
    full_results: dict[str, Any] = {}
    full_trades: dict[str, pd.DataFrame] = {}
    for variant in variants:
        for window, (start, end) in windows.items():
            result = run(
                engine,
                v3_backtest,
                cross_backtest,
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
                result_row(
                    formation,
                    result,
                    variant,
                    window=window,
                    scenario="base_4bps",
                )
            )
            if window == "full":
                full_results[variant] = result
                full_trades[variant] = annotate_trades(
                    formation,
                    result,
                    variant,
                )
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
                engine,
                v3_backtest,
                cross_backtest,
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
                result_row(
                    formation,
                    result,
                    variant,
                    window="full",
                    scenario=scenario,
                )
            )
        phase12 = run(
            engine,
            v3_backtest,
            cross_backtest,
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
            result_row(
                formation,
                phase12,
                variant,
                window="full",
                scenario="phase_12h",
            )
        )
        start = 0
        while start + 90 <= book.count:
            result = run(
                engine,
                v3_backtest,
                cross_backtest,
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
        full_results[V3_CONTROL].metrics["equity_multiple"],
        V3_EQUITY_MULTIPLE,
        rel_tol=1e-10,
        abs_tol=1e-10,
    ):
        raise RuntimeError("V3 control anchor drift")

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
    phase_rows = []
    for variant in variants:
        for phase in range(24):
            if phase in phase_errors:
                continue
            result = run(
                engine,
                v3_backtest,
                cross_backtest,
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
                    **attribution(
                        annotate_trades(formation, result, variant)
                    ),
                }
            )

    latest_book, latest_features = build(0, latest=True)
    latest_rows = []
    for variant in variants:
        result = run(
            engine,
            v3_backtest,
            cross_backtest,
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
            result_row(
                formation,
                result,
                variant,
                window="latest_extension",
                scenario="base_4bps",
            )
        )

    candidate_evidence = cross_evidence(
        full_trades[DAILY_CROSS],
        book,
        features[0],
        short_config,
    )
    if not all(row["condition_valid"] for row in candidate_evidence):
        raise RuntimeError("candidate contains invalid close-cross reversal")
    candidate_entries = full_trades[DAILY_CROSS]["entry_ts"].astype(str)
    r_s02_removed = not candidate_entries.str.startswith(
        "2025-06-13T02:00:00"
    ).any()
    if not r_s02_removed:
        raise RuntimeError("R-S02 trailing reversal remains in candidate")

    metrics_frame = pd.DataFrame(rows)
    phase_frame = pd.DataFrame(phase_rows)
    rolling_frame = pd.DataFrame(rolling_rows)
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "HYPE-1D-MA7-Asymmetric-Body-Trend",
        "source_version": "HYPE-1D-MA7-Asymmetric-Body-Trend-V3",
        "status": "diagnostic only; V3 unchanged",
        "contract": (
            "specs/hype-1d-ma7-abt-v3-daily-ma7-cross-reversal-contract-"
            "2026-08-07.md"
        ),
        "mechanism": {
            "long_trailing_stop": "exit to flat; never reverse",
            "reversal": (
                "while long: prior close >= prior SMA7 and current close "
                "< current SMA7; close and short at next daily open"
            ),
            "minimum_hold": "no extra parameter",
        },
        "behavior_checks": {
            "r_s02_removed": r_s02_removed,
            "candidate_close_cross_reversals": candidate_evidence,
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
            for variant in variants
        },
        "rolling_90d_summary": {
            variant: summarize(
                rolling_frame.loc[rolling_frame["variant"].eq(variant)]
            )
            for variant in variants
        },
        "evidence_role": "post-reveal mechanism diagnostic; not clean OOS",
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"hype_1d_v3_daily_ma7_cross_reversal_{args.run_date}"
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
    for variant in variants:
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
                "trailing_reversal_trades",
                "close_cross_reversal_trades",
            ],
        ].to_string(index=False)
    )
    print(json.dumps(clean(candidate_evidence), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
