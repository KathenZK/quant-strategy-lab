from __future__ import annotations

import argparse
import builtins
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
FLAT_PATH = (
    FAMILY_DIR
    / "scripts/audit_hype_1d_ma7_abt_v4_flat_regime_entry.py"
)
FLAT_SHA256 = (
    "21db8d5121b6462b6fe6b37e9aef9fb3d521352a6632ed5e61f960d904f01f38"
)
CONTRACT = "specs/hype-1d-ma7-abt-v4-target-side-regime-contract-2026-08-07.md"
HOLDOUT_START = pd.Timestamp("2026-05-01T00:00:00Z")
V4_CONTROL = "V4_CONTROL"
TARGET_SIDE_REGIME = "TARGET_SIDE_REGIME"
VARIANTS = (V4_CONTROL, TARGET_SIDE_REGIME)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit next-open target-side MA7 regime reversals for V4."
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


def capture_v4_source(v4: Any, formation: Any, engine: Any) -> str:
    captured: dict[str, str] = {}
    original_compile = builtins.compile

    def capture(source: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(source, str) and "def v3_ma_only_backtest(" in source:
            captured["source"] = source
        return original_compile(source, *args, **kwargs)

    builtins.compile = capture
    try:
        v4.build_filtered_backtest(formation, engine, v4.MA_ONLY)
    finally:
        builtins.compile = original_compile
    if "source" not in captured:
        raise RuntimeError("failed to capture registered V4 backtest source")
    return captured["source"]


def build_target_backtest(v4: Any, formation: Any, engine: Any) -> Any:
    source = capture_v4_source(v4, formation, engine)
    source = source.replace(
        "def v3_ma_only_backtest(",
        "def v4_target_side_regime_backtest(",
        1,
    )
    exit_marker = """\
        if (
            index < terminal_index
            and side != 0
            and decision_index >= 0
            and not entered_pending_reversal
        ):
"""
    if source.count(exit_marker) != 1:
        raise RuntimeError("registered V4 open-exit marker drift")
    reversal = """\
        regime_reversed_at_open = False
        if (
            index < terminal_index
            and side != 0
            and decision_index >= 0
            and not entered_pending_reversal
        ):
            regime_signal_index = max(0, decision_index)
            target_config = None
            if (
                side < 0
                and long_config is not None
                and close_entry_signal(
                    long_config,
                    book,
                    features,
                    regime_signal_index,
                )
            ):
                target_config = long_config
            elif (
                side > 0
                and short_config is not None
                and close_entry_signal(
                    short_config,
                    book,
                    features,
                    regime_signal_index,
                )
            ):
                target_config = short_config
            if target_config is not None:
                old_side = side
                close(
                    ts,
                    current_open,
                    "ma7_target_side_reversal",
                    index,
                )
                enter(
                    target_config,
                    ts,
                    current_open,
                    index,
                    regime_signal_index,
                )
                cooldown_left = 0
                exited_at_open = True
                regime_reversed_at_open = True
                action = (
                    "reverse_short_to_long_target_regime"
                    if old_side < 0
                    else "reverse_long_to_short_target_regime"
                )
"""
    guarded_exit = exit_marker.replace(
        "            and not entered_pending_reversal\n",
        (
            "            and not entered_pending_reversal\n"
            "            and not regime_reversed_at_open\n"
        ),
    )
    source = source.replace(
        exit_marker,
        reversal + guarded_exit,
        1,
    )
    namespace = dict(engine.__dict__)
    try:
        compiled = compile(source, str(formation.ENGINE_PATH), "exec")
    except SyntaxError as exc:
        lines = source.splitlines()
        left = max(0, (exc.lineno or 1) - 8)
        right = min(len(lines), (exc.lineno or 1) + 7)
        context = "\n".join(
            f"{index + 1}: {lines[index]}"
            for index in range(left, right)
        )
        raise RuntimeError(
            f"target-side V4 source failed to compile:\n{context}"
        ) from exc
    exec(compiled, namespace)
    return namespace["v4_target_side_regime_backtest"]


def annotate_target_reversals(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    output["target_side_reversal"] = False
    for index in range(1, len(output)):
        previous = output.iloc[index - 1]
        current = output.iloc[index]
        if (
            previous["exit_reason"] == "ma7_target_side_reversal"
            and previous["side"] != current["side"]
            and pd.Timestamp(previous["exit_ts"])
            == pd.Timestamp(current["entry_ts"])
        ):
            output.loc[index, "target_side_reversal"] = True
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
    flat = load_pinned(
        FLAT_PATH,
        FLAT_SHA256,
        "hype_v4_target_flat",
    )
    shared = load_pinned(
        flat.TIMING_PATH,
        flat.TIMING_SHA256,
        "hype_v4_target_timing",
    )
    v4 = shared.load_pinned(
        shared.V4_FORMATION_PATH,
        shared.V4_FORMATION_SHA256,
        "hype_v4_target_formation",
    )
    formation = v4.load_pinned(
        v4.FORMATION_PATH,
        v4.FORMATION_SHA256,
        "hype_v4_target_reversal",
    )
    engine = formation.load_pinned(
        formation.ENGINE_PATH,
        formation.ENGINE_SHA256,
        "hype_v4_target_engine",
    )
    base = formation.load_pinned(
        formation.BASE_PATH,
        formation.BASE_SHA256,
        "hype_v4_target_base",
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
        V4_CONTROL: v4.build_filtered_backtest(formation, engine, v4.MA_ONLY),
        TARGET_SIDE_REGIME: build_target_backtest(v4, formation, engine),
    }
    signal = flat.FlatRegimeSignal(engine)
    functions[TARGET_SIDE_REGIME].__globals__["close_entry_signal"] = signal
    signals = {TARGET_SIDE_REGIME: signal}
    if args.self_test:
        assert all(callable(functions[variant]) for variant in VARIANTS)
        assert functions[TARGET_SIDE_REGIME].__name__ == (
            "v4_target_side_regime_backtest"
        )
        print("self-test passed: V4 target-side regime variant compiled")
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
            frame = annotate_target_reversals(v4.annotate(formation, result))
            row = v4.result_row(
                formation,
                result,
                variant,
                window=window,
                scenario="base_4bps",
            )
            row["target_side_reversals"] = int(
                frame["target_side_reversal"].sum()
            )
            rows.append(row)
            if window == "full":
                full_results[variant] = result
                full_trades[variant] = frame
                if variant == TARGET_SIDE_REGIME:
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
            frame = annotate_target_reversals(v4.annotate(formation, result))
            row = v4.result_row(
                formation,
                result,
                variant,
                window="full",
                scenario=scenario,
            )
            row["target_side_reversals"] = int(
                frame["target_side_reversal"].sum()
            )
            rows.append(row)
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
        phase12_frame = annotate_target_reversals(
            v4.annotate(formation, phase12)
        )
        row = v4.result_row(
            formation,
            phase12,
            variant,
            window="full",
            scenario="phase_12h",
        )
        row["target_side_reversals"] = int(
            phase12_frame["target_side_reversal"].sum()
        )
        rows.append(row)
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
    target_frame = full_trades[TARGET_SIDE_REGIME]
    june_short = target_frame.loc[
        target_frame["side"].eq("short")
        & pd.to_datetime(target_frame["entry_ts"], utc=True).eq(
            pd.Timestamp("2025-06-19T00:00:00Z")
        )
        & target_frame["target_side_reversal"]
    ]
    if len(june_short) != 1:
        raise RuntimeError("2025-06 target-side short reversal missing")

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
            frame = annotate_target_reversals(v4.annotate(formation, result))
            phase_rows.append(
                {
                    "variant": variant,
                    "phase_hours": phase,
                    **result.metrics,
                    **v4.attribution(frame),
                    "target_side_reversals": int(
                        frame["target_side_reversal"].sum()
                    ),
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
        frame = annotate_target_reversals(v4.annotate(formation, result))
        row = v4.result_row(
            formation,
            result,
            variant,
            window="latest_extension",
            scenario="base_4bps",
        )
        row["target_side_reversals"] = int(
            frame["target_side_reversal"].sum()
        )
        latest_rows.append(row)

    metrics_frame = pd.DataFrame(rows)
    rolling_frame = pd.DataFrame(rolling_rows)
    phase_frame = pd.DataFrame(phase_rows)
    deltas = shared.trade_deltas(
        full_trades[V4_CONTROL],
        full_trades[TARGET_SIDE_REGIME],
    )
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_version": "HYPE-1D-MA7-Asymmetric-Body-Trend-V4",
        "status": "post-reveal diagnostic only; registered V4 unchanged",
        "contract": CONTRACT,
        "variant": (
            "current MA7 side plus frozen slope defines target; opposite "
            "position reverses at next open"
        ),
        "entry_events": full_events,
        "trade_deltas": deltas,
        "target_side_reversals": int(
            full_trades[TARGET_SIDE_REGIME]["target_side_reversal"].sum()
        ),
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
    stem = f"hype_1d_v4_target_side_regime_{args.run_date}"
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
                "target_side_reversals",
                "exposure_pct",
            ],
        ].to_string(index=False)
    )
    print(json.dumps(clean(full_events), ensure_ascii=False, indent=2))
    print(json.dumps(clean(deltas), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
