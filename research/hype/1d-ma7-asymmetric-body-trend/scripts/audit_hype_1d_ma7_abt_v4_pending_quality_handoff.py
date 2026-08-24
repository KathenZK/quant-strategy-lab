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
PENDING_PATH = (
    FAMILY_DIR
    / "scripts/audit_hype_1d_ma7_abt_v4_finite_reclaim_pending.py"
)
PENDING_SHA256 = (
    "54bb70abb0fa65e7a560d9e597ac44a0ff19877d9688652a979bf7090e72b822"
)
CONTRACT = (
    "specs/hype-1d-ma7-abt-v4-pending-quality-handoff-contract-2026-08-07.md"
)
HOLDOUT_START = pd.Timestamp("2026-05-01T00:00:00Z")
V4_CONTROL = "V4_CONTROL"
SP1_CONTROL = "SP1_CONTROL"
SP1_CAP_075 = "SP1_CAP_075"
SP1_HANDOFF = "SP1_HANDOFF"
SP1_CAP_075_HANDOFF = "SP1_CAP_075_HANDOFF"
VARIANTS = (
    V4_CONTROL,
    SP1_CONTROL,
    SP1_CAP_075,
    SP1_HANDOFF,
    SP1_CAP_075_HANDOFF,
)
CAP_ATR = 0.75
TARGET_SHORT_ENTRY = pd.Timestamp("2025-06-19T00:00:00Z")
TARGET_LONG_ENTRY = pd.Timestamp("2025-06-28T00:00:00Z")
SP1_EQUITY_MULTIPLE = 2.1073128215120005


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit V4 pending anti-chase and delayed handoff."
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


class QualityPendingSignal:
    def __init__(
        self,
        parent: Any,
        engine: Any,
        *,
        cap_atr: float | None,
    ) -> None:
        self.base = parent.FinitePendingSignal(engine, 0, 1)
        self.cap_atr = cap_atr
        self.events = self.base.events
        self.delayed_confirmations: set[tuple[int, int]] = set()

    def reset(self) -> None:
        self.base.reset()
        self.events = self.base.events
        self.delayed_confirmations = set()

    def __call__(
        self,
        config: Any,
        book: Any,
        features: Any,
        index: int,
    ) -> bool:
        passed = self.base(config, book, features, index)
        self.events = self.base.events
        if not passed:
            return False
        if not self.events:
            return True
        event = self.events[-1]
        delayed = bool(
            event["event"] == "confirm_pending_entry"
            and event.get("delayed")
        )
        if not delayed:
            return True
        side = int(config.side)
        distance_atr = float(
            side
            * (event["close"] - event["ma7"])
            / event["atr7"]
        )
        if self.cap_atr is not None and distance_atr > self.cap_atr:
            confirmation = self.events.pop()
            self.events.append(
                {
                    **confirmation,
                    "event": "reject_overextended_pending",
                    "distance_atr": distance_atr,
                    "cap_atr": self.cap_atr,
                }
            )
            return False
        self.events[-1]["distance_atr"] = distance_atr
        self.delayed_confirmations.add((side, index))
        return True

    def entry_was_delayed(self, side: int, signal_index: int) -> bool:
        return (int(side), int(signal_index)) in self.delayed_confirmations

    def record_handoff(
        self,
        old_side: int,
        new_side: int,
        signal_index: int,
        exit_reason: str,
    ) -> None:
        self.events.append(
            {
                "event": "delayed_position_opposite_handoff",
                "signal_index": signal_index,
                "side": "long" if new_side > 0 else "short",
                "old_side": "long" if old_side > 0 else "short",
                "new_side": "long" if new_side > 0 else "short",
                "exit_reason": exit_reason,
            }
        )


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
        raise RuntimeError("failed to capture compiled V4 source")
    return captured["source"]


def build_handoff_backtest(v4: Any, formation: Any, engine: Any) -> Any:
    source = capture_v4_source(v4, formation, engine)
    source = source.replace(
        "def v3_ma_only_backtest(",
        "def v4_delayed_handoff_backtest(",
        1,
    )
    state_marker = "    cooldown_left = 0\n    bars_held = 0\n"
    if source.count(state_marker) != 1:
        raise RuntimeError("V4 cooldown state marker drift")
    source = source.replace(
        state_marker,
        (
            "    cooldown_left = 0\n"
            "    active_entry_was_delayed_pending = False\n"
            "    bars_held = 0\n"
        ),
        1,
    )
    enter_nonlocal = (
        "        nonlocal entry_ts, entry_price, entry_equity, entry_side\n"
        "        nonlocal bars_held, stop_price, highest_close, lowest_close, mark_price\n"
    )
    if source.count(enter_nonlocal) != 1:
        raise RuntimeError("V4 enter nonlocal marker drift")
    source = source.replace(
        enter_nonlocal,
        (
            enter_nonlocal
            + "        nonlocal active_entry_was_delayed_pending\n"
        ),
        1,
    )
    enter_end = "        mark_price = price\n\n    def settle_funding("
    if source.count(enter_end) != 1:
        raise RuntimeError("V4 enter end marker drift")
    source = source.replace(
        enter_end,
        (
            "        mark_price = price\n"
            "        active_entry_was_delayed_pending = (\n"
            "            finite_pending_entry_was_delayed(\n"
            "                config.side,\n"
            "                signal_index,\n"
            "            )\n"
            "        )\n\n"
            "    def settle_funding("
        ),
        1,
    )
    exit_block = """\
            if reason:
                close(ts, current_open, reason, index)
                cooldown_left = config.cooldown_days
                exited_at_open = True
                action = reason
"""
    if source.count(exit_block) != 1:
        raise RuntimeError("V4 daily exit block drift")
    handoff_block = """\
            if reason:
                exiting_side = side
                was_delayed_pending = active_entry_was_delayed_pending
                close(ts, current_open, reason, index)
                cooldown_left = config.cooldown_days
                exited_at_open = True
                action = reason
                opposite_config = (
                    short_config if exiting_side > 0 else long_config
                )
                if (
                    was_delayed_pending
                    and opposite_config is not None
                    and v4_close_entry_signal(
                        opposite_config,
                        book,
                        features,
                        decision_index,
                    )
                ):
                    enter(
                        opposite_config,
                        ts,
                        current_open,
                        index,
                        decision_index,
                    )
                    cooldown_left = 0
                    record_finite_pending_handoff(
                        exiting_side,
                        opposite_config.side,
                        decision_index,
                        reason,
                    )
                    action = (
                        "handoff_short_to_long_v4_reclaim"
                        if exiting_side < 0
                        else "handoff_long_to_short_v4_reclaim"
                    )
"""
    source = source.replace(exit_block, handoff_block, 1)
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
            f"delayed handoff source failed to compile:\n{context}"
        ) from exc
    exec(compiled, namespace)
    return namespace["v4_delayed_handoff_backtest"]


def install_signal(
    function: Any,
    signal: QualityPendingSignal,
    engine: Any,
    *,
    handoff: bool,
) -> None:
    function.__globals__["close_entry_signal"] = signal
    function.__globals__["finite_pending_entry_was_delayed"] = (
        signal.entry_was_delayed
    )
    function.__globals__["record_finite_pending_handoff"] = signal.record_handoff
    function.__globals__["v4_close_entry_signal"] = engine.close_entry_signal
    if handoff and function.__name__ != "v4_delayed_handoff_backtest":
        raise RuntimeError("handoff signal installed on non-handoff backtest")


def event_counts(parent: Any, events: list[dict[str, Any]]) -> dict[str, int]:
    counts = parent.event_counts(events)
    counts.update(
        {
            "overextended_rejects": sum(
                event["event"] == "reject_overextended_pending"
                for event in events
            ),
            "opposite_handoffs": sum(
                event["event"] == "delayed_position_opposite_handoff"
                for event in events
            ),
        }
    )
    return counts


def main() -> None:
    args = parse_args()
    parent = load_pinned(
        PENDING_PATH,
        PENDING_SHA256,
        "hype_v4_pending_quality_parent",
    )
    shared = parent.load_pinned(
        parent.TIMING_PATH,
        parent.TIMING_SHA256,
        "hype_v4_pending_quality_shared",
    )
    v4 = shared.load_pinned(
        shared.V4_FORMATION_PATH,
        shared.V4_FORMATION_SHA256,
        "hype_v4_pending_quality_v4",
    )
    formation = v4.load_pinned(
        v4.FORMATION_PATH,
        v4.FORMATION_SHA256,
        "hype_v4_pending_quality_formation",
    )
    engine = formation.load_pinned(
        formation.ENGINE_PATH,
        formation.ENGINE_SHA256,
        "hype_v4_pending_quality_engine",
    )
    base = formation.load_pinned(
        formation.BASE_PATH,
        formation.BASE_SHA256,
        "hype_v4_pending_quality_base",
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
        SP1_CONTROL: v4.build_filtered_backtest(formation, engine, v4.MA_ONLY),
        SP1_CAP_075: v4.build_filtered_backtest(formation, engine, v4.MA_ONLY),
        SP1_HANDOFF: build_handoff_backtest(v4, formation, engine),
        SP1_CAP_075_HANDOFF: build_handoff_backtest(v4, formation, engine),
    }
    signals = {
        SP1_CONTROL: QualityPendingSignal(parent, engine, cap_atr=None),
        SP1_CAP_075: QualityPendingSignal(parent, engine, cap_atr=CAP_ATR),
        SP1_HANDOFF: QualityPendingSignal(parent, engine, cap_atr=None),
        SP1_CAP_075_HANDOFF: QualityPendingSignal(
            parent,
            engine,
            cap_atr=CAP_ATR,
        ),
    }
    for variant, signal in signals.items():
        install_signal(
            functions[variant],
            signal,
            engine,
            handoff=variant in (SP1_HANDOFF, SP1_CAP_075_HANDOFF),
        )
    if args.self_test:
        assert len(functions) == 5
        assert functions[SP1_HANDOFF].__name__ == "v4_delayed_handoff_backtest"
        assert signals[SP1_CAP_075].cap_atr == 0.75
        print("self-test passed: pending quality and handoff compiled")
        return

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
            row.update(event_counts(parent, events))
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
            row.update(event_counts(parent, events))
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
        row.update(event_counts(parent, events))
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
                    **event_counts(parent, events),
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
    if not math.isclose(
        full_results[SP1_CONTROL].metrics["equity_multiple"],
        SP1_EQUITY_MULTIPLE,
        rel_tol=1e-10,
        abs_tol=1e-10,
    ):
        raise RuntimeError("first-round SP1 anchor drift")
    combo = full_trades[SP1_CAP_075_HANDOFF].copy()
    combo["entry_ts_utc"] = pd.to_datetime(combo["entry_ts"], utc=True)
    for side, timestamp in (
        ("short", TARGET_SHORT_ENTRY),
        ("long", TARGET_LONG_ENTRY),
    ):
        if not (
            combo["side"].eq(side)
            & combo["entry_ts_utc"].eq(timestamp)
        ).any():
            raise RuntimeError(f"combo failed target {side} handoff at {timestamp}")

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
                    **event_counts(parent, events),
                }
            )

    latest_book, latest_features = build(0, latest=True)
    latest_rows = []
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
        row.update(event_counts(parent, events))
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
        checks = {
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
        }
        checks["robustness_floor_pass"] = all(checks.values())
        qualifications[variant] = checks
    eligible = [
        variant
        for variant in VARIANTS
        if variant != V4_CONTROL
        and qualifications[variant]["robustness_floor_pass"]
    ]
    eligible.sort(
        key=lambda variant: (
            0 if variant == SP1_CAP_075_HANDOFF else 1,
            len(trade_deltas[variant]),
            -float(base_rows.loc[variant, "net_return_pct"]),
        )
    )
    best_variant = eligible[0] if eligible else None
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_version": "HYPE-1D-MA7-Asymmetric-Body-Trend-V4",
        "status": "post-reveal second-round local repair; V4 unchanged",
        "contract": CONTRACT,
        "cap_atr": CAP_ATR,
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
    stem = f"hype_1d_v4_pending_quality_handoff_{args.run_date}"
    (ARTIFACT_DIR / f"{stem}_summary.json").write_text(
        json.dumps(
            parent.clean(payload),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
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
                "overextended_rejects",
                "opposite_handoffs",
                "exposure_pct",
            ]
        ].to_string()
    )
    print(
        json.dumps(
            parent.clean(
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
