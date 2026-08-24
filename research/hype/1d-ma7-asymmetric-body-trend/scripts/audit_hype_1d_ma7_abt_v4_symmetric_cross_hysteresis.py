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
PARENT_PATH = FAMILY_DIR / "scripts/audit_hype_1d_ma7_abt_v4_band_state_machine.py"
PARENT_SHA256 = "5d6e0553e57f8747e0c60b30652ef8609192781020bc6fb4f68f51d53ff7c0ae"
CONTRACT = "specs/hype-1d-ma7-abt-v4-symmetric-cross-hysteresis-contract-2026-08-07.md"
HOLDOUT_START = pd.Timestamp("2026-05-01T00:00:00Z")
V4_CONTROL = "V4_CONTROL"
SYMMETRIC_CROSS_D075 = "SYMMETRIC_CROSS_D075"
VARIANTS = (V4_CONTROL, SYMMETRIC_CROSS_D075)
HYSTERESIS_ATR = 0.75


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit symmetric fresh MA7 cross entries and held hysteresis."
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


class SymmetricCrossSignal:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def reset(self) -> None:
        self.events = []

    @staticmethod
    def _finite(*values: float) -> bool:
        return all(np.isfinite(value) for value in values)

    def __call__(
        self,
        config: Any,
        book: Any,
        features: Any,
        index: int,
    ) -> bool:
        if index < 1:
            return False
        prior_close = float(book.close[index - 1])
        close = float(book.close[index])
        prior_ma = float(features.ma7[index - 1])
        ma = float(features.ma7[index])
        if not self._finite(prior_close, close, prior_ma, ma):
            return False
        if config.side > 0:
            passed = prior_close <= prior_ma and close > ma
        else:
            passed = prior_close >= prior_ma and close < ma
        if passed:
            self.events.append(
                {
                    "event": "flat_fresh_ma7_cross",
                    "signal_index": index,
                    "side": "long" if config.side > 0 else "short",
                    "prior_close": prior_close,
                    "prior_ma7": prior_ma,
                    "close": close,
                    "ma7": ma,
                }
            )
        return bool(passed)

    def held_boundary(
        self,
        config: Any,
        book: Any,
        features: Any,
        index: int,
    ) -> bool:
        if index < 0:
            return False
        close = float(book.close[index])
        ma = float(features.ma7[index])
        atr = float(features.atr7[index])
        if not self._finite(close, ma, atr) or atr <= 0.0:
            return False
        boundary = ma + config.side * HYSTERESIS_ATR * atr
        passed = close > boundary if config.side > 0 else close < boundary
        if passed:
            self.events.append(
                {
                    "event": "held_hysteresis_boundary_reversal",
                    "signal_index": index,
                    "side": "long" if config.side > 0 else "short",
                    "close": close,
                    "ma7": ma,
                    "atr7": atr,
                    "boundary": boundary,
                    "distance_atr": config.side * (close - ma) / atr,
                }
            )
        return bool(passed)


class MaxHoldOnlyExit:
    def __call__(
        self,
        config: Any,
        _book: Any,
        _features: Any,
        _index: int,
        bars_held: int,
    ) -> str:
        if config.max_hold_days > 0 and bars_held >= config.max_hold_days:
            return "max_hold"
        return ""


def build_symmetric_backtest(engine: Any) -> tuple[Any, SymmetricCrossSignal]:
    source = textwrap.dedent(inspect.getsource(engine.backtest))
    source = source.replace(
        "def backtest(",
        "def symmetric_cross_hysteresis_backtest(",
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
        hysteresis_reversed_at_open = False
        if (
            index < terminal_index
            and side != 0
            and decision_index >= 0
        ):
            target_config = None
            if (
                side < 0
                and long_config is not None
                and held_hysteresis_signal(
                    long_config,
                    book,
                    features,
                    decision_index,
                )
            ):
                target_config = long_config
            elif (
                side > 0
                and short_config is not None
                and held_hysteresis_signal(
                    short_config,
                    book,
                    features,
                    decision_index,
                )
            ):
                target_config = short_config
            if target_config is not None:
                old_side = side
                close(
                    ts,
                    current_open,
                    "symmetric_hysteresis_reversal",
                    index,
                )
                enter(
                    target_config,
                    ts,
                    current_open,
                    index,
                    decision_index,
                )
                cooldown_left = 0
                exited_at_open = True
                hysteresis_reversed_at_open = True
                action = (
                    "reverse_short_to_long_symmetric_hysteresis"
                    if old_side < 0
                    else "reverse_long_to_short_symmetric_hysteresis"
                )
        if (
            index < terminal_index
            and side != 0
            and decision_index >= 0
            and not hysteresis_reversed_at_open
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
            f"{index + 1}: {lines[index]}" for index in range(left, right)
        )
        raise RuntimeError(
            f"symmetric state source failed to compile:\n{context}"
        ) from exc
    exec(compiled, namespace)
    function = namespace["symmetric_cross_hysteresis_backtest"]
    signal = SymmetricCrossSignal()
    function.__globals__["close_entry_signal"] = signal
    function.__globals__["held_hysteresis_signal"] = signal.held_boundary
    function.__globals__["signal_exit"] = MaxHoldOnlyExit()
    return function, signal


def annotate_trades(formation: Any, result: Any) -> pd.DataFrame:
    frame = formation.annotate_trades(result, "T0_original")
    if frame.empty:
        return frame
    frame["entry_source"] = "flat_fresh_ma7_cross"
    frame["hysteresis_reversal"] = False
    for index in range(1, len(frame)):
        previous = frame.iloc[index - 1]
        current = frame.iloc[index]
        if (
            previous["exit_reason"] == "symmetric_hysteresis_reversal"
            and previous["side"] != current["side"]
            and pd.Timestamp(previous["exit_ts"]) == pd.Timestamp(current["entry_ts"])
        ):
            frame.loc[index, "entry_source"] = "held_hysteresis_reversal"
            frame.loc[index, "hysteresis_reversal"] = True
    return frame


def attribution(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {
            "fresh_cross_entries": 0,
            "hysteresis_reversals": 0,
            "protective_exits": 0,
            "max_hold_exits": 0,
            "rapid_reversal_round_trips": 0,
        }
    reversals = frame.loc[frame["hysteresis_reversal"]]
    return {
        "fresh_cross_entries": int(
            frame["entry_source"].eq("flat_fresh_ma7_cross").sum()
        ),
        "hysteresis_reversals": int(frame["hysteresis_reversal"].sum()),
        "protective_exits": int(frame["exit_reason"].eq("protective_stop").sum()),
        "max_hold_exits": int(frame["exit_reason"].eq("max_hold").sum()),
        "rapid_reversal_round_trips": int((reversals["bars_held"] <= 3).sum()),
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
    if variant == SYMMETRIC_CROSS_D075:
        row.update(attribution(annotate_trades(formation, result)))
    else:
        trades = pd.DataFrame(result.trades)
        exit_reason = trades.get("exit_reason", pd.Series(dtype=str))
        row.update(
            {
                "fresh_cross_entries": 0,
                "hysteresis_reversals": 0,
                "protective_exits": int(exit_reason.eq("protective_stop").sum()),
                "max_hold_exits": int(exit_reason.eq("max_hold").sum()),
                "rapid_reversal_round_trips": 0,
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
    parent = load_pinned(
        PARENT_PATH,
        PARENT_SHA256,
        "hype_v4_symmetric_cross_parent",
    )
    shared = parent.load_pinned(
        parent.TIMING_PATH,
        parent.TIMING_SHA256,
        "hype_v4_symmetric_cross_shared",
    )
    v4 = shared.load_pinned(
        shared.V4_FORMATION_PATH,
        shared.V4_FORMATION_SHA256,
        "hype_v4_symmetric_cross_v4",
    )
    formation = v4.load_pinned(
        v4.FORMATION_PATH,
        v4.FORMATION_SHA256,
        "hype_v4_symmetric_cross_formation",
    )
    engine = formation.load_pinned(
        formation.ENGINE_PATH,
        formation.ENGINE_SHA256,
        "hype_v4_symmetric_cross_engine",
    )
    base = formation.load_pinned(
        formation.BASE_PATH,
        formation.BASE_SHA256,
        "hype_v4_symmetric_cross_base",
    )
    selected = formation.read_pinned_json(
        formation.SUMMARY_PATH,
        formation.SUMMARY_SHA256,
    )["historically_profitable_all_checks"][0]
    long_config = replace(
        engine.Config(**selected["long_config"]),
        exit_buffer_atr=HYSTERESIS_ATR,
    )
    short_config = replace(
        engine.Config(**selected["short_config"]),
        exit_buffer_atr=HYSTERESIS_ATR,
    )
    candidate_function, candidate_signal = build_symmetric_backtest(engine)
    functions = {
        V4_CONTROL: v4.build_filtered_backtest(formation, engine, v4.MA_ONLY),
        SYMMETRIC_CROSS_D075: candidate_function,
    }
    signals = {SYMMETRIC_CROSS_D075: candidate_signal}
    if (
        long_config.cooldown_days != 2
        or short_config.cooldown_days != 5
        or long_config.trail_atr != 1.5
        or short_config.hard_stop_atr != 1.5
        or short_config.trail_atr != 4.0
        or long_config.max_hold_days != 90
        or short_config.max_hold_days != 20
    ):
        raise RuntimeError("registered V4 risk identity drift")
    if args.self_test:
        assert all(callable(functions[variant]) for variant in VARIANTS)
        assert isinstance(candidate_signal, SymmetricCrossSignal)
        assert isinstance(
            candidate_function.__globals__["signal_exit"],
            MaxHoldOnlyExit,
        )
        print("self-test passed: symmetric cross hysteresis compiled")
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
                    else annotate_trades(formation, result)
                )
                if variant == SYMMETRIC_CROSS_D075:
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
                    **(
                        attribution(annotate_trades(formation, result))
                        if variant == SYMMETRIC_CROSS_D075
                        else {}
                    ),
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
    candidate = full_trades[SYMMETRIC_CROSS_D075]
    allowed_exits = {
        "symmetric_hysteresis_reversal",
        "protective_stop",
        "max_hold",
        "terminal_flatten",
    }
    unexpected = sorted(set(candidate["exit_reason"]) - allowed_exits)
    if unexpected:
        raise RuntimeError(f"candidate retained unexpected exits: {unexpected}")
    if candidate.empty or not (candidate["entry_price"] > 0.0).all():
        raise RuntimeError("candidate trade path invalid")
    if candidate.duplicated(["side", "entry_ts"]).any():
        raise RuntimeError("candidate trade identities are not unique")
    if not (
        pd.to_datetime(candidate["entry_ts"], utc=True)
        <= pd.to_datetime(candidate["exit_ts"], utc=True)
    ).all():
        raise RuntimeError("candidate trade timestamp order invalid")
    if len(full_events) != len(candidate):
        raise RuntimeError(
            f"entry event/trade mismatch: {len(full_events)} != {len(candidate)}"
        )
    for event in full_events:
        if event["event"] == "flat_fresh_ma7_cross":
            if event["side"] == "long":
                valid = (
                    event["prior_close"] <= event["prior_ma7"]
                    and event["close"] > event["ma7"]
                )
            else:
                valid = (
                    event["prior_close"] >= event["prior_ma7"]
                    and event["close"] < event["ma7"]
                )
        elif event["event"] == "held_hysteresis_boundary_reversal":
            valid = float(event["distance_atr"]) > HYSTERESIS_ATR
        else:
            raise RuntimeError(f"unexpected candidate event: {event['event']}")
        if not valid:
            raise RuntimeError(f"invalid candidate event: {event}")

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
            if variant == SYMMETRIC_CROSS_D075:
                row.update(attribution(annotate_trades(formation, result)))
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
        full_trades[SYMMETRIC_CROSS_D075],
    )
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_version": "HYPE-1D-MA7-Asymmetric-Body-Trend-V4",
        "status": "post-reveal diagnostic only; registered V4 unchanged",
        "contract": CONTRACT,
        "candidate": {
            "name": SYMMETRIC_CROSS_D075,
            "flat_entry": "fresh close cross of SMA7; no slope or ATR buffer",
            "held_reversal": "opposite SMA7 boundary at 0.75 ATR7",
            "hysteresis_atr": HYSTERESIS_ATR,
            "risk_layer": "V4 hard/trailing/max-hold/cooldown values retained",
        },
        "events": full_events,
        "trade_deltas": deltas,
        "candidate_attribution": attribution(candidate),
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
    stem = f"hype_1d_v4_symmetric_cross_hysteresis_{args.run_date}"
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
    pd.DataFrame(deltas).to_csv(
        ARTIFACT_DIR / f"{stem}_trade_deltas.csv",
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
    base_rows = metrics_frame.loc[
        metrics_frame["window"].eq("full") & metrics_frame["scenario"].eq("base_4bps"),
        [
            "variant",
            "net_return_pct",
            "max_drawdown_pct",
            "sharpe",
            "closed_trades",
            "profit_factor",
            "fresh_cross_entries",
            "hysteresis_reversals",
            "protective_exits",
            "max_hold_exits",
            "exposure_pct",
        ],
    ]
    print(base_rows.to_string(index=False))
    print(json.dumps(clean(deltas), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
