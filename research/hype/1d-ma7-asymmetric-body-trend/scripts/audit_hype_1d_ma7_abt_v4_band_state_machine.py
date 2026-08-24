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
TIMING_PATH = (
    FAMILY_DIR
    / "scripts/audit_hype_1d_ma7_abt_v4_short_entry_timing.py"
)
TIMING_SHA256 = (
    "d221c0d51db2bfd206bf3b0709d7fb51762a3029ba7b39df937d609fefe54926"
)
CONTRACT = (
    "specs/hype-1d-ma7-abt-v4-band-state-machine-contract-2026-08-07.md"
)
HOLDOUT_START = pd.Timestamp("2026-05-01T00:00:00Z")
V4_CONTROL = "V4_CONTROL"
BAND_STATE_MACHINE = "BAND_STATE_MACHINE"
VARIANTS = (V4_CONTROL, BAND_STATE_MACHINE)
BAND_ATR = 0.75


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit V4 ATR-band trend state machine."
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


class BandTargetSignal:
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
        target_config = replace(
            config,
            entry_mode="regime",
            confirm_days=1,
            entry_buffer_atr=BAND_ATR,
        )
        passed = self.engine.close_entry_signal(
            target_config,
            book,
            features,
            index,
        )
        if passed:
            atr = float(features.atr7[index])
            prior = index - config.slope_lookback
            slope = float(
                config.side
                * (features.ma7[index] - features.ma7[prior])
                / atr
            )
            self.events.append(
                {
                    "event": "band_target_signal",
                    "signal_index": index,
                    "side": "long" if config.side > 0 else "short",
                    "close": float(book.close[index]),
                    "ma7": float(features.ma7[index]),
                    "atr7": atr,
                    "upper_band": float(features.ma7[index] + BAND_ATR * atr),
                    "lower_band": float(features.ma7[index] - BAND_ATR * atr),
                    "slope_atr": slope,
                    "slope_lookback": int(config.slope_lookback),
                }
            )
        return passed


class ProtectionOnlyExit:
    def __call__(self, *_args: Any, **_kwargs: Any) -> None:
        return None


def build_band_backtest(engine: Any) -> Any:
    source = textwrap.dedent(inspect.getsource(engine.backtest))
    source = source.replace(
        "def backtest(",
        "def band_state_machine_backtest(",
        1,
    )
    marker = """\
        decision_index = index - 1 - signal_lag
        if index < terminal_index and side != 0 and decision_index >= 0:
"""
    if source.count(marker) != 1:
        raise RuntimeError("pinned engine decision marker drift")
    reversal = """\
        decision_index = index - 1 - signal_lag
        band_reversed_at_open = False
        if (
            index < terminal_index
            and side != 0
            and decision_index >= 0
        ):
            band_signal_index = max(0, decision_index)
            target_config = None
            if (
                side < 0
                and long_config is not None
                and close_entry_signal(
                    long_config,
                    book,
                    features,
                    band_signal_index,
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
                    band_signal_index,
                )
            ):
                target_config = short_config
            if target_config is not None:
                old_side = side
                close(
                    ts,
                    current_open,
                    "band_target_reversal",
                    index,
                )
                enter(
                    target_config,
                    ts,
                    current_open,
                    index,
                    band_signal_index,
                )
                cooldown_left = 0
                exited_at_open = True
                band_reversed_at_open = True
                action = (
                    "reverse_short_to_long_band_target"
                    if old_side < 0
                    else "reverse_long_to_short_band_target"
                )
        if (
            index < terminal_index
            and side != 0
            and decision_index >= 0
            and not band_reversed_at_open
        ):
"""
    source = source.replace(marker, reversal, 1)
    namespace = dict(engine.__dict__)
    try:
        compiled = compile(source, str(engine.__file__), "exec")
    except SyntaxError as exc:
        lines = source.splitlines()
        left = max(0, (exc.lineno or 1) - 8)
        right = min(len(lines), (exc.lineno or 1) + 7)
        context = "\n".join(
            f"{index + 1}: {lines[index]}"
            for index in range(left, right)
        )
        raise RuntimeError(
            f"band state source failed to compile:\n{context}"
        ) from exc
    exec(compiled, namespace)
    function = namespace["band_state_machine_backtest"]
    function.__globals__["close_entry_signal"] = BandTargetSignal(engine)
    function.__globals__["signal_exit"] = ProtectionOnlyExit()
    return function


def annotate_state_trades(formation: Any, result: Any) -> pd.DataFrame:
    frame = formation.annotate_trades(result, "T0_original")
    if frame.empty:
        return frame
    frame["entry_source"] = "band_flat_entry"
    frame["band_target_reversal"] = False
    frame["cooldown_reentry"] = False
    for index in range(1, len(frame)):
        previous = frame.iloc[index - 1]
        current = frame.iloc[index]
        previous_exit = pd.Timestamp(previous["exit_ts"])
        current_entry = pd.Timestamp(current["entry_ts"])
        if (
            previous["exit_reason"] == "band_target_reversal"
            and previous["side"] != current["side"]
            and previous_exit == current_entry
        ):
            frame.loc[index, "entry_source"] = "band_target_reversal"
            frame.loc[index, "band_target_reversal"] = True
        elif (
            previous["exit_reason"] == "protective_stop"
            and previous["side"] == current["side"]
            and current_entry > previous_exit
        ):
            frame.loc[index, "entry_source"] = "cooldown_reentry"
            frame.loc[index, "cooldown_reentry"] = True
    return frame


def state_attribution(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {
            "band_target_reversals": 0,
            "protective_exits": 0,
            "cooldown_reentries": 0,
            "rapid_target_round_trips": 0,
        }
    reversals = frame.loc[frame["band_target_reversal"]]
    return {
        "band_target_reversals": int(frame["band_target_reversal"].sum()),
        "protective_exits": int(
            frame["exit_reason"].eq("protective_stop").sum()
        ),
        "cooldown_reentries": int(frame["cooldown_reentry"].sum()),
        "rapid_target_round_trips": int((reversals["bars_held"] <= 3).sum()),
    }


def result_row(
    v4: Any,
    formation: Any,
    result: Any,
    variant: str,
    *,
    window: str,
    scenario: str,
) -> dict[str, Any]:
    row = v4.result_row(
        formation,
        result,
        variant,
        window=window,
        scenario=scenario,
    )
    if variant == BAND_STATE_MACHINE:
        row.update(state_attribution(annotate_state_trades(formation, result)))
    else:
        row.update(
            {
                "band_target_reversals": 0,
                "protective_exits": int(
                    pd.DataFrame(result.trades)
                    .get("exit_reason", pd.Series(dtype=str))
                    .eq("protective_stop")
                    .sum()
                ),
                "cooldown_reentries": 0,
                "rapid_target_round_trips": 0,
            }
        )
    return row


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
        "hype_v4_band_shared",
    )
    v4 = shared.load_pinned(
        shared.V4_FORMATION_PATH,
        shared.V4_FORMATION_SHA256,
        "hype_v4_band_formation",
    )
    formation = v4.load_pinned(
        v4.FORMATION_PATH,
        v4.FORMATION_SHA256,
        "hype_v4_band_reversal",
    )
    engine = formation.load_pinned(
        formation.ENGINE_PATH,
        formation.ENGINE_SHA256,
        "hype_v4_band_engine",
    )
    base = formation.load_pinned(
        formation.BASE_PATH,
        formation.BASE_SHA256,
        "hype_v4_band_base",
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
        long_config.cooldown_days != 2
        or short_config.cooldown_days != 5
        or long_config.slope_lookback != 1
        or short_config.slope_lookback != 2
    ):
        raise RuntimeError("registered V4 state identity drift")
    functions = {
        V4_CONTROL: v4.build_filtered_backtest(formation, engine, v4.MA_ONLY),
        BAND_STATE_MACHINE: build_band_backtest(engine),
    }
    band_signal = functions[BAND_STATE_MACHINE].__globals__[
        "close_entry_signal"
    ]
    signals = {BAND_STATE_MACHINE: band_signal}
    if args.self_test:
        assert all(callable(functions[variant]) for variant in VARIANTS)
        assert isinstance(band_signal, BandTargetSignal)
        assert isinstance(
            functions[BAND_STATE_MACHINE].__globals__["signal_exit"],
            ProtectionOnlyExit,
        )
        print("self-test passed: V4 ATR-band state machine compiled")
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
                result_row(
                    v4,
                    formation,
                    result,
                    variant,
                    window=window,
                    scenario="base_4bps",
                )
            )
            if window == "full":
                full_results[variant] = result
                full_trades[variant] = (
                    v4.annotate(formation, result)
                    if variant == V4_CONTROL
                    else annotate_state_trades(formation, result)
                )
                if variant == BAND_STATE_MACHINE:
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
                result_row(
                    v4,
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
            result_row(
                v4,
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
    candidate = full_trades[BAND_STATE_MACHINE]
    if (
        candidate["exit_reason"]
        .isin(("ma7_hysteresis_exit", "ma7_slope_exit", "max_hold"))
        .any()
    ):
        raise RuntimeError("candidate retained a disabled daily exit")
    if candidate.empty or not (candidate["entry_price"] > 0.0).all():
        raise RuntimeError("candidate trade path invalid")

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
            row = {
                "variant": variant,
                "phase_hours": phase,
                **result.metrics,
            }
            if variant == BAND_STATE_MACHINE:
                row.update(
                    state_attribution(
                        annotate_state_trades(formation, result)
                    )
                )
            else:
                row.update(
                    {
                        "band_target_reversals": 0,
                        "protective_exits": int(
                            pd.DataFrame(result.trades)
                            .get("exit_reason", pd.Series(dtype=str))
                            .eq("protective_stop")
                            .sum()
                        ),
                        "cooldown_reentries": 0,
                        "rapid_target_round_trips": 0,
                    }
                )
            phase_rows.append(row)

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
            result_row(
                v4,
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
        full_trades[BAND_STATE_MACHINE],
    )
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_version": "HYPE-1D-MA7-Asymmetric-Body-Trend-V4",
        "status": "post-reveal diagnostic only; registered V4 unchanged",
        "contract": CONTRACT,
        "band_atr": BAND_ATR,
        "entry_events": full_events,
        "trade_deltas": deltas,
        "candidate_attribution": state_attribution(candidate),
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
    stem = f"hype_1d_v4_band_state_machine_{args.run_date}"
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
                "band_target_reversals",
                "protective_exits",
                "cooldown_reentries",
                "exposure_pct",
            ],
        ].to_string(index=False)
    )
    print(json.dumps(clean(full_events), ensure_ascii=False, indent=2))
    print(json.dumps(clean(deltas), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
