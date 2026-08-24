from __future__ import annotations

import argparse
from dataclasses import asdict
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
ENGINE_PATH = FAMILY_DIR / "scripts/search_hype_1d_ma7_separated_trend.py"
ENGINE_SHA256 = "c376f8bd1bae814b0ba53687380ee1060cf3cc3095ae815ebb0311ed1aef59e1"
BASE_PATH = FAMILY_DIR / "scripts/research_hype_1d_ma7_asymmetric_body_trend.py"
BASE_SHA256 = "05d76943a671d1463f8950f1f6e317d8653831fd0f72ea825a039caa1fb2a386"
SUMMARY_PATH = ARTIFACT_DIR / "hype_1d_ma7_separated_summary_2026-08-04.json"
SUMMARY_SHA256 = "ba6245f5ca1811cac9566abc78b09fdf24e846fd70a0f9265aaa8dd9360c97ae"

HISTORICAL_HOUR_CUTOFF = pd.Timestamp("2026-07-30T04:00:00Z")
HOLDOUT_START = pd.Timestamp("2026-05-01T00:00:00Z")
PHASES = (0, 12)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit HYPE V1 long trailing-stop to short reversal."
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


def read_pinned_json(path: Path, expected: str) -> dict[str, Any]:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise RuntimeError(f"{path.name} drift: expected {expected}, got {actual}")
    return json.loads(path.read_text(encoding="utf-8"))


def build_reversal_backtest(engine: Any) -> Any:
    """Compile a pinned-engine variant with intraday short reversal handling."""

    source = textwrap.dedent(inspect.getsource(engine.backtest))
    source = source.replace(
        "def backtest(",
        "def trailing_stop_short_reversal_backtest(",
        1,
    )
    old = """\
                equity += qty * (fill - position_mark)
                close(stop_fill_ts, fill, "protective_stop", index)
                cooldown_left = config.cooldown_days
                mark_price = fill
                action = "protective_stop"
                favorable_equity = max(favorable_equity, equity)
                adverse_equity = min(adverse_equity, equity)
                close_equity = equity
"""
    new = """\
                equity += qty * (fill - position_mark)
                close(stop_fill_ts, fill, "protective_stop", index)
                if position_side > 0 and short_config is not None:
                    long_favorable_equity = max(favorable_equity, equity)
                    long_adverse_equity = min(adverse_equity, equity)
                    if gap_hit:
                        reversal_hour = 0
                    elif hour_gap_hit:
                        reversal_hour = int(hit_hour)
                    else:
                        reversal_hour = int(hit_hour) + 1
                    if reversal_hour >= 24:
                        raise RuntimeError(
                            "long trailing stop in final hour has no same-day "
                            "next 1h open; contract requires explicit handling"
                        )
                    reversal_ts = ts + pd.Timedelta(hours=reversal_hour)
                    reversal_price = float(
                        features.hourly_open[index, reversal_hour]
                    )
                    signal_index = max(0, decision_index)
                    enter(
                        short_config,
                        reversal_ts,
                        reversal_price,
                        index,
                        signal_index,
                    )
                    cooldown_left = 0
                    mark_price = reversal_price
                    action = "reverse_long_trailing_stop_to_short"

                    short_stop_price = float(stop_price)
                    short_hit_hour = None
                    short_fill = math.nan
                    short_fill_ts = None
                    for hour in range(reversal_hour, 24):
                        hour_open = float(features.hourly_open[index, hour])
                        hour_high = float(features.hourly_high[index, hour])
                        if hour_open >= short_stop_price:
                            short_hit_hour = hour
                            short_fill = hour_open
                            short_fill_ts = ts + pd.Timedelta(hours=hour)
                            break
                        if hour_high >= short_stop_price:
                            short_hit_hour = hour
                            short_fill = short_stop_price
                            short_fill_ts = ts + pd.Timedelta(hours=hour + 1)
                            break

                    if short_hit_hour is not None:
                        if short_fill_ts is None:
                            raise RuntimeError("missing short stop timestamp")
                        settle_funding(
                            index,
                            reversal_ts,
                            short_fill_ts,
                        )
                        short_open_equity = equity
                        completed_high = features.hourly_high[
                            index, reversal_hour:short_hit_hour
                        ]
                        completed_low = features.hourly_low[
                            index, reversal_hour:short_hit_hour
                        ]
                        if len(completed_high):
                            short_favorable_equity = (
                                short_open_equity
                                + qty
                                * (
                                    min(
                                        reversal_price,
                                        short_fill,
                                        float(completed_low.min()),
                                    )
                                    - reversal_price
                                )
                            )
                            short_adverse_equity = (
                                short_open_equity
                                + qty
                                * (
                                    max(
                                        reversal_price,
                                        short_fill,
                                        float(completed_high.max()),
                                    )
                                    - reversal_price
                                )
                            )
                        else:
                            short_favorable_equity = short_open_equity
                            short_adverse_equity = short_open_equity
                        equity += qty * (short_fill - reversal_price)
                        close(
                            short_fill_ts,
                            short_fill,
                            "protective_stop",
                            index,
                        )
                        cooldown_left = short_config.cooldown_days
                        mark_price = short_fill
                        action = (
                            "reverse_long_trailing_stop_to_short_stop"
                        )
                        favorable_equity = max(
                            long_favorable_equity,
                            short_favorable_equity,
                            equity,
                        )
                        adverse_equity = min(
                            long_adverse_equity,
                            short_adverse_equity,
                            equity,
                        )
                        close_equity = equity
                    else:
                        settle_funding(
                            index,
                            reversal_ts,
                            ts + pd.Timedelta(days=1),
                        )
                        remaining_high = features.hourly_high[
                            index, reversal_hour:
                        ]
                        remaining_low = features.hourly_low[
                            index, reversal_hour:
                        ]
                        short_favorable_equity = equity + qty * (
                            float(remaining_low.min()) - reversal_price
                        )
                        short_adverse_equity = equity + qty * (
                            float(remaining_high.max()) - reversal_price
                        )
                        close_equity = equity + qty * (
                            float(book.close[index]) - reversal_price
                        )
                        favorable_equity = max(
                            long_favorable_equity,
                            short_favorable_equity,
                            close_equity,
                        )
                        adverse_equity = min(
                            long_adverse_equity,
                            short_adverse_equity,
                            close_equity,
                        )
                        if short_adverse_equity <= 0.0:
                            bankrupt = True
                            equity = 0.0
                            qty = 0.0
                            side = 0
                            close_equity = 0.0
                            max_drawdown = -1.0
                            action = "intraday_bankruptcy"
                        else:
                            bars_held += 1
                            highest_close = max(
                                highest_close,
                                float(book.close[index]),
                            )
                            lowest_close = min(
                                lowest_close,
                                float(book.close[index]),
                            )
                            atr = features.atr7[index]
                            if (
                                short_config.trail_atr > 0.0
                                and np.isfinite(atr)
                            ):
                                candidate = (
                                    lowest_close
                                    + short_config.trail_atr * atr
                                )
                                stop_price = min(stop_price, candidate)
                else:
                    cooldown_left = config.cooldown_days
                    mark_price = fill
                    action = "protective_stop"
                    favorable_equity = max(favorable_equity, equity)
                    adverse_equity = min(adverse_equity, equity)
                    close_equity = equity
"""
    if source.count(old) != 1:
        raise RuntimeError("pinned backtest source no longer matches replacement block")
    source = source.replace(old, new, 1)
    source = source.replace(
        "    bankrupt = False\n\n    def trade_to",
        "    bankrupt = False\n"
        "    pending_short_reversal = False\n\n"
        "    def trade_to",
        1,
    )
    loop_old = """\
        entered_after_open = False
        exited_at_open = False
        decision_index = index - 1 - signal_lag
        if index < terminal_index and side != 0 and decision_index >= 0:
"""
    loop_new = """\
        entered_after_open = False
        exited_at_open = False
        entered_pending_reversal = False
        decision_index = index - 1 - signal_lag
        if pending_short_reversal and index < terminal_index:
            if short_config is None:
                raise RuntimeError("pending reversal has no short config")
            enter(
                short_config,
                ts,
                current_open,
                index,
                max(0, decision_index),
            )
            pending_short_reversal = False
            entered_pending_reversal = True
            action = "enter_pending_trailing_stop_reversal_short"
        if (
            index < terminal_index
            and side != 0
            and decision_index >= 0
            and not entered_pending_reversal
        ):
"""
    if source.count(loop_old) != 1:
        raise RuntimeError("pinned loop source no longer matches pending-entry block")
    source = source.replace(loop_old, loop_new, 1)

    final_hour_old = """\
                    if reversal_hour >= 24:
                        raise RuntimeError(
                            "long trailing stop in final hour has no same-day "
                            "next 1h open; contract requires explicit handling"
                        )
"""
    final_hour_new = """\
                    if reversal_hour >= 24:
                        pending_short_reversal = True
                        cooldown_left = 0
                        mark_price = fill
                        action = "protective_stop_pending_short_reversal"
                        favorable_equity = max(
                            long_favorable_equity,
                            equity,
                        )
                        adverse_equity = min(
                            long_adverse_equity,
                            equity,
                        )
                        close_equity = equity
"""
    if source.count(final_hour_old) != 1:
        raise RuntimeError("compiled reversal source lacks final-hour block")
    source = source.replace(final_hour_old, final_hour_new, 1)
    guarded_start = source.index(
        "                    reversal_ts = ts + pd.Timedelta(hours=reversal_hour)"
    )
    guarded_end = source.index(
        "                else:\n"
        "                    cooldown_left = config.cooldown_days",
        guarded_start,
    )
    guarded_body = source[guarded_start:guarded_end]
    source = (
        source[:guarded_start]
        + "                    if reversal_hour < 24:\n"
        + textwrap.indent(guarded_body, "    ")
        + source[guarded_end:]
    )
    namespace = dict(engine.__dict__)
    exec(compile(source, str(ENGINE_PATH), "exec"), namespace)
    return namespace["trailing_stop_short_reversal_backtest"]


def annotate_trades(result: Any, variant: str) -> pd.DataFrame:
    frame = pd.DataFrame(result.trades)
    if frame.empty:
        return frame
    frame["entry_source"] = "original_entry"
    if variant == "T1_trailing_stop_short_reversal":
        for index in range(1, len(frame)):
            previous = frame.iloc[index - 1]
            current = frame.iloc[index]
            exit_ts = pd.Timestamp(previous["exit_ts"])
            entry_ts = pd.Timestamp(current["entry_ts"])
            if (
                previous["side"] == "long"
                and previous["exit_reason"] == "protective_stop"
                and current["side"] == "short"
                and pd.Timedelta(0) <= entry_ts - exit_ts <= pd.Timedelta(hours=1)
            ):
                frame.loc[index, "entry_source"] = "forced_trailing_stop_reversal"
    return frame


def attribution(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {
            "forced_reversal_trades": 0,
            "forced_reversal_net_pnl": 0.0,
            "forced_reversal_win_rate": math.nan,
            "forced_reversal_stopouts": 0,
        }
    forced = frame.loc[
        frame["entry_source"].eq("forced_trailing_stop_reversal")
    ]
    return {
        "forced_reversal_trades": int(len(forced)),
        "forced_reversal_net_pnl": float(forced["net_pnl"].sum()),
        "forced_reversal_win_rate": (
            float((forced["net_pnl"] > 0.0).mean()) if len(forced) else math.nan
        ),
        "forced_reversal_stopouts": int(
            forced["exit_reason"].eq("protective_stop").sum()
        ),
    }


def run(
    engine: Any,
    reversal_backtest: Any,
    book: Any,
    features: Any,
    long_config: Any,
    short_config: Any,
    *,
    variant: str,
    start: int,
    end: int,
    slippage: float,
    signal_lag: int = 0,
    retain: bool = False,
) -> Any:
    function = (
        engine.backtest
        if variant == "T0_baseline"
        else reversal_backtest
    )
    return function(
        book,
        features,
        long_config=long_config,
        short_config=short_config,
        start_index=start,
        terminal_index=end,
        slippage=slippage,
        signal_lag=signal_lag,
        retain=retain,
    )


def clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): clean(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, float):
        return None if not math.isfinite(value) else value
    return value


def main() -> None:
    args = parse_args()
    engine = load_pinned(ENGINE_PATH, ENGINE_SHA256, "hype_v1_trailing_reverse_engine")
    base = load_pinned(BASE_PATH, BASE_SHA256, "hype_v1_trailing_reverse_base")
    summary = read_pinned_json(SUMMARY_PATH, SUMMARY_SHA256)
    selected = summary["historically_profitable_all_checks"][0]
    long_config = engine.Config(**selected["long_config"])
    short_config = engine.Config(**selected["short_config"])
    if long_config.hard_stop_atr != 0.0 or long_config.trail_atr != 1.5:
        raise RuntimeError("unexpected V1 long protection identity")
    reversal_backtest = build_reversal_backtest(engine)

    parent = base.load_parent()
    market_engine = parent.load_engine()
    hourly, hourly_quality = market_engine.audit_and_load_market(ROOT, "1h")
    funding, funding_quality = market_engine.load_and_audit_funding(ROOT)
    hourly["ts"] = pd.to_datetime(hourly["ts"], utc=True)
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
    historical_hourly = hourly.loc[
        hourly["ts"] <= HISTORICAL_HOUR_CUTOFF
    ].copy()
    historical_funding = funding.loc[
        funding["ts"] <= HISTORICAL_HOUR_CUTOFF
    ].copy()

    books: dict[int, Any] = {}
    features: dict[int, Any] = {}
    for phase in PHASES:
        books[phase] = base.build_book(
            parent,
            historical_hourly,
            hourly_quality,
            historical_funding,
            funding_quality,
            phase_hours=phase,
        )
        features[phase] = engine.build_features(
            books[phase],
            historical_hourly,
            historical_funding,
        )

    baseline = run(
        engine,
        reversal_backtest,
        books[0],
        features[0],
        long_config,
        short_config,
        variant="T0_baseline",
        start=0,
        end=books[0].count,
        slippage=engine.BASE_SLIPPAGE,
    )
    expected = selected["windows"]["full"]["base"]["equity_multiple"]
    if not math.isclose(
        baseline.metrics["equity_multiple"],
        expected,
        rel_tol=1e-10,
        abs_tol=1e-10,
    ):
        raise RuntimeError("baseline anchor drift")

    if args.self_test:
        result = run(
            engine,
            reversal_backtest,
            books[0],
            features[0],
            long_config,
            short_config,
            variant="T1_trailing_stop_short_reversal",
            start=0,
            end=books[0].count,
            slippage=engine.BASE_SLIPPAGE,
            retain=True,
        )
        trades = annotate_trades(result, "T1_trailing_stop_short_reversal")
        forced = trades.loc[
            trades["entry_source"].eq("forced_trailing_stop_reversal")
        ]
        if forced.empty:
            raise AssertionError("expected forced trailing-stop reversals")
        if not (
            pd.to_datetime(forced["entry_ts"], utc=True).dt.minute.eq(0).all()
            and pd.to_datetime(forced["entry_ts"], utc=True).dt.second.eq(0).all()
        ):
            raise AssertionError("reversal entries must be on real 1h opens")
        if (forced["bars_held"] < 0).any():
            raise AssertionError("negative holding period")
        print(
            "self-test passed: baseline anchor exact; "
            f"forced reversals={len(forced)}; entries on 1h opens"
        )
        return

    variants = ("T0_baseline", "T1_trailing_stop_short_reversal")
    split = int(pd.DatetimeIndex(books[0].ts).searchsorted(HOLDOUT_START))
    windows = {
        "prefit": (0, split),
        "researcher_exposed_last_90d_flat": (split, books[0].count),
        "full": (0, books[0].count),
    }
    metrics_rows: list[dict[str, Any]] = []
    recent_rows: list[dict[str, Any]] = []
    phase_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    primary: dict[str, Any] = {}

    for variant in variants:
        for window, (start, end) in windows.items():
            result = run(
                engine,
                reversal_backtest,
                books[0],
                features[0],
                long_config,
                short_config,
                variant=variant,
                start=start,
                end=end,
                slippage=engine.BASE_SLIPPAGE,
                retain=window == "full",
            )
            trades = annotate_trades(result, variant)
            metrics_rows.append(
                {
                    "variant": variant,
                    "window": window,
                    "execution": "base_4bps",
                    **result.metrics,
                    **attribution(trades),
                }
            )
            if window == "full":
                primary[variant] = {
                    "metrics": result.metrics,
                    "attribution": attribution(trades),
                }
                for row in engine.recent_slices(result):
                    recent_rows.append({"variant": variant, **row})
                for row in trades.to_dict("records"):
                    trade_rows.append({"variant": variant, **row})
        for execution, slippage, lag in (
            ("stress_8bps", engine.STRESS_SLIPPAGE, 0),
            ("one_day_extra_delay", engine.BASE_SLIPPAGE, 1),
        ):
            result = run(
                engine,
                reversal_backtest,
                books[0],
                features[0],
                long_config,
                short_config,
                variant=variant,
                start=0,
                end=books[0].count,
                slippage=slippage,
                signal_lag=lag,
            )
            metrics_rows.append(
                {
                    "variant": variant,
                    "window": "full",
                    "execution": execution,
                    **result.metrics,
                    **attribution(annotate_trades(result, variant)),
                }
            )
        for phase in PHASES:
            result = run(
                engine,
                reversal_backtest,
                books[phase],
                features[phase],
                long_config,
                short_config,
                variant=variant,
                start=0,
                end=books[phase].count,
                slippage=engine.BASE_SLIPPAGE,
            )
            phase_rows.append(
                {
                    "variant": variant,
                    "phase_hours": phase,
                    **result.metrics,
                }
            )

    latest_book = base.build_book(
        parent,
        hourly,
        hourly_quality,
        funding,
        funding_quality,
        phase_hours=0,
    )
    latest_features = engine.build_features(latest_book, hourly, funding)
    latest: dict[str, Any] = {}
    for variant in variants:
        result = run(
            engine,
            reversal_backtest,
            latest_book,
            latest_features,
            long_config,
            short_config,
            variant=variant,
            start=0,
            end=latest_book.count,
            slippage=engine.BASE_SLIPPAGE,
            retain=True,
        )
        latest[variant] = {
            "metrics": result.metrics,
            "attribution": attribution(annotate_trades(result, variant)),
        }

    frame = pd.DataFrame(metrics_rows)
    def select(variant: str, execution: str) -> pd.Series:
        return frame.loc[
            frame["variant"].eq(variant)
            & frame["window"].eq("full")
            & frame["execution"].eq(execution)
        ].iloc[0]

    base_row = select("T0_baseline", "base_4bps")
    reversal_row = select("T1_trailing_stop_short_reversal", "base_4bps")
    base_stress = select("T0_baseline", "stress_8bps")
    reversal_stress = select(
        "T1_trailing_stop_short_reversal", "stress_8bps"
    )
    if (
        reversal_row["net_return_pct"] > base_row["net_return_pct"]
        and reversal_stress["net_return_pct"] > base_stress["net_return_pct"]
        and reversal_row["max_drawdown_pct"]
        >= base_row["max_drawdown_pct"] - 5.0
        and reversal_row["forced_reversal_net_pnl"] > 0.0
    ):
        verdict = "改善"
    elif (
        reversal_row["net_return_pct"] <= base_row["net_return_pct"]
        or reversal_row["forced_reversal_net_pnl"] <= 0.0
    ):
        verdict = "失败"
    else:
        verdict = "混合"

    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "status": "explore / diagnostic-only / not promoted / not live-ready",
        "contract": (
            "specs/hype-1d-ma7-abt-trailing-stop-short-reversal-contract-"
            "2026-08-06.md"
        ),
        "pins": {
            "engine_sha256": ENGINE_SHA256,
            "base_sha256": BASE_SHA256,
            "v1_summary_sha256": SUMMARY_SHA256,
        },
        "configs": {
            "long": asdict(long_config),
            "short": asdict(short_config),
        },
        "data_quality": {
            "hourly": hourly_quality,
            "funding": funding_quality,
        },
        "primary": primary,
        "latest_extension": latest,
        "judgment": {
            "verdict": verdict,
            "base_return_delta_pp": float(
                reversal_row["net_return_pct"] - base_row["net_return_pct"]
            ),
            "stress_return_delta_pp": float(
                reversal_stress["net_return_pct"]
                - base_stress["net_return_pct"]
            ),
            "mdd_delta_pp": float(
                reversal_row["max_drawdown_pct"]
                - base_row["max_drawdown_pct"]
            ),
            "forced_reversal_trades": int(
                reversal_row["forced_reversal_trades"]
            ),
            "forced_reversal_net_pnl": float(
                reversal_row["forced_reversal_net_pnl"]
            ),
        },
        "btc_eth_shared_applicability": {
            "status": "not_applicable",
            "reason": (
                "shared long config has hard_stop_atr=0, trail_atr=0, "
                "max_hold_days=0; no protective/trailing-stop trigger"
            ),
        },
        "evidence_role": (
            "historical mechanism diagnostic; post-reveal; not clean OOS "
            "or promotion evidence"
        ),
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"hype_1d_v1_trailing_stop_short_reversal_{args.run_date}"
    frame.to_csv(ARTIFACT_DIR / f"{stem}_metrics.csv", index=False)
    pd.DataFrame(trade_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_trades.csv", index=False
    )
    pd.DataFrame(recent_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_recent.csv", index=False
    )
    pd.DataFrame(phase_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_phase.csv", index=False
    )
    (ARTIFACT_DIR / f"{stem}_summary.json").write_text(
        json.dumps(clean(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(clean(payload["judgment"]), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
