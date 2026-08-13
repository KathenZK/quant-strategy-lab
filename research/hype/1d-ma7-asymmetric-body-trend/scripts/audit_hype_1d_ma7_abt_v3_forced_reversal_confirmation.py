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
MA_ONLY = "MA_ONLY"
MA_AND_SLOPE = "MA_AND_SLOPE"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit V3 trailing reversal MA7 confirmation fixes."
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


def capture_v3_source(formation: Any, engine: Any) -> str:
    captured: dict[str, str] = {}
    original_compile = builtins.compile

    def capture(source: Any, *args: Any, **kwargs: Any) -> Any:
        if (
            isinstance(source, str)
            and "def trailing_stop_short_reversal_backtest(" in source
        ):
            captured["source"] = source
        return original_compile(source, *args, **kwargs)

    builtins.compile = capture
    try:
        formation.build_reversal_backtest(engine)
    finally:
        builtins.compile = original_compile
    if "source" not in captured:
        raise RuntimeError("failed to capture V3 compiled backtest source")
    return captured["source"]


def eligibility_lines(
    mode: str,
    *,
    price: str,
    signal_index: str,
    indent: str,
) -> str:
    lines = [
        f"{indent}reversal_ma7 = features.ma7[{signal_index}]",
        f"{indent}reversal_allowed = (",
        f"{indent}    np.isfinite(reversal_ma7)",
        f"{indent}    and {price} < reversal_ma7",
        f"{indent})",
    ]
    if mode == MA_AND_SLOPE:
        lines.extend(
            [
                f"{indent}reversal_atr7 = features.atr7[{signal_index}]",
                f"{indent}reversal_slope_prior = (",
                f"{indent}    {signal_index} - short_config.slope_lookback",
                f"{indent})",
                f"{indent}if (",
                f"{indent}    reversal_allowed",
                f"{indent}    and reversal_slope_prior >= 0",
                f"{indent}    and np.isfinite(reversal_atr7)",
                f"{indent}    and reversal_atr7 > 0.0",
                f"{indent}):",
                f"{indent}    reversal_down_slope = (",
                f"{indent}        features.ma7[reversal_slope_prior]",
                f"{indent}        - features.ma7[{signal_index}]",
                f"{indent}    ) / reversal_atr7",
                f"{indent}    reversal_allowed = bool(",
                f"{indent}        np.isfinite(reversal_down_slope)",
                f"{indent}        and reversal_down_slope",
                f"{indent}        >= short_config.slope_min_atr",
                f"{indent}    )",
                f"{indent}else:",
                f"{indent}    reversal_allowed = False",
            ]
        )
    return "\n".join(lines) + "\n"


def build_filtered_backtest(
    formation: Any,
    engine: Any,
    mode: str,
) -> Any:
    if mode not in (MA_ONLY, MA_AND_SLOPE):
        raise ValueError(f"unsupported reversal filter mode: {mode}")
    source = capture_v3_source(formation, engine)
    source = source.replace(
        "def trailing_stop_short_reversal_backtest(",
        f"def v3_{mode.lower()}_backtest(",
        1,
    )

    pending_start = source.index(
        "        if pending_short_reversal and index < terminal_index:"
    )
    pending_end = source.index(
        "        if (\n            index < terminal_index",
        pending_start,
    )
    pending = (
        "        if pending_short_reversal and index < terminal_index:\n"
        "            if short_config is None:\n"
        '                raise RuntimeError("pending reversal has no short config")\n'
        "            pending_signal_index = max(0, decision_index)\n"
        + eligibility_lines(
            mode,
            price="current_open",
            signal_index="pending_signal_index",
            indent="            ",
        )
        + "            if reversal_allowed:\n"
        "                enter(\n"
        "                    short_config,\n"
        "                    ts,\n"
        "                    current_open,\n"
        "                    index,\n"
        "                    pending_signal_index,\n"
        "                )\n"
        "                entered_pending_reversal = True\n"
        '                action = "enter_pending_filtered_reversal_short"\n'
        "            else:\n"
        "                cooldown_left = (\n"
        "                    long_config.cooldown_days\n"
        "                    if long_config is not None\n"
        "                    else 0\n"
        "                )\n"
        '                action = "pending_reversal_filter_rejected"\n'
        "            pending_short_reversal = False\n"
    )
    source = source[:pending_start] + pending + source[pending_end:]

    signal_marker = "                        signal_index = max(0, decision_index)\n"
    signal_at = source.index(signal_marker)
    body_start = source.index(
        "                        enter(\n",
        signal_at,
    )
    outer_else = "\n                else:\n                    cooldown_left = config.cooldown_days"
    body_end = source.index(outer_else, body_start)
    body = source[body_start:body_end]
    guarded = (
        eligibility_lines(
            mode,
            price="reversal_price",
            signal_index="signal_index",
            indent="                        ",
        )
        + "                        if reversal_allowed:\n"
        + textwrap.indent(body, "    ")
        + "\n                        else:\n"
        "                            cooldown_left = config.cooldown_days\n"
        "                            mark_price = fill\n"
        '                            action = "protective_stop_reversal_filter_rejected"\n'
        "                            favorable_equity = max(\n"
        "                                long_favorable_equity,\n"
        "                                equity,\n"
        "                            )\n"
        "                            adverse_equity = min(\n"
        "                                long_adverse_equity,\n"
        "                                equity,\n"
        "                            )\n"
        "                            close_equity = equity\n"
    )
    source = source[:body_start] + guarded + source[body_end:]
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
            f"filtered V3 source failed to compile:\n{context}"
        ) from exc
    exec(compiled, namespace)
    return namespace[f"v3_{mode.lower()}_backtest"]


def annotate(formation: Any, result: Any) -> pd.DataFrame:
    return formation.annotate_trades(
        result,
        "T1_trailing_stop_short_reversal",
    )


def attribution(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {
            "reversal_attempts": 0,
            "forced_reversal_trades": 0,
            "reversal_rejections": 0,
            "forced_reversal_net_pnl": 0.0,
            "forced_reversal_one_bar_or_less": 0,
        }
    attempts = int(
        (
            frame["side"].eq("long")
            & frame["exit_reason"].eq("protective_stop")
        ).sum()
    )
    forced = frame.loc[
        frame["entry_source"].eq("forced_trailing_stop_reversal")
    ]
    return {
        "reversal_attempts": attempts,
        "forced_reversal_trades": int(len(forced)),
        "reversal_rejections": attempts - int(len(forced)),
        "forced_reversal_net_pnl": float(forced["net_pnl"].sum()),
        "forced_reversal_one_bar_or_less": int(
            (forced["bars_held"] <= 1).sum()
        ),
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
    functions: dict[str, Any],
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
    return functions[variant](
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
    return {
        "variant": variant,
        "window": window,
        "scenario": scenario,
        **result.metrics,
        **attribution(annotate(formation, result)),
        "exposure_pct": exposure_pct(result),
    }


def forced_entry_evidence(
    frame: pd.DataFrame,
    book: Any,
    features: Any,
    short_config: Any,
) -> list[dict[str, Any]]:
    timestamps = pd.DatetimeIndex(book.ts)
    output = []
    for frame_index, row in frame.iterrows():
        if row["entry_source"] != "forced_trailing_stop_reversal":
            continue
        entry_ts = pd.Timestamp(row["entry_ts"])
        daily_index = int(timestamps.searchsorted(entry_ts.floor("1D")))
        signal_index = daily_index - 1
        prior_index = signal_index - short_config.slope_lookback
        atr = float(features.atr7[signal_index])
        slope = float(
            (
                features.ma7[prior_index]
                - features.ma7[signal_index]
            )
            / atr
        )
        entry_price = float(row["entry_price"])
        ma7 = float(features.ma7[signal_index])
        output.append(
            {
                "trade_id": f"R-S{frame_index + 1:02d}",
                "entry_ts": entry_ts.isoformat(),
                "entry_price": entry_price,
                "last_completed_ma7": ma7,
                "entry_below_ma7": entry_price < ma7,
                "down_slope_atr": slope,
                "slope_pass": slope >= short_config.slope_min_atr,
                "bars_held": int(row["bars_held"]),
                "exit_reason": str(row["exit_reason"]),
                "net_return_pct": float(row["net_return"]) * 100.0,
            }
        )
    return output


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
        "hype_v3_reversal_fix_formation",
    )
    engine = formation.load_pinned(
        formation.ENGINE_PATH,
        formation.ENGINE_SHA256,
        "hype_v3_reversal_fix_engine",
    )
    base = formation.load_pinned(
        formation.BASE_PATH,
        formation.BASE_SHA256,
        "hype_v3_reversal_fix_base",
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
        V3_CONTROL: formation.build_reversal_backtest(engine),
        MA_ONLY: build_filtered_backtest(formation, engine, MA_ONLY),
        MA_AND_SLOPE: build_filtered_backtest(
            formation,
            engine,
            MA_AND_SLOPE,
        ),
    }
    if args.self_test:
        assert all(callable(function) for function in functions.values())
        assert functions[MA_ONLY].__name__ == "v3_ma_only_backtest"
        assert functions[MA_AND_SLOPE].__name__ == (
            "v3_ma_and_slope_backtest"
        )
        print("self-test passed: V3 reversal confirmation variants compiled")
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
    variants = (V3_CONTROL, MA_ONLY, MA_AND_SLOPE)
    rows = []
    recent_rows = []
    rolling_rows = []
    full_results = {}
    full_trades = {}
    for variant in variants:
        for window, (start, end) in windows.items():
            result = run(
                functions,
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
                full_trades[variant] = annotate(formation, result)
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
                functions,
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
            functions,
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
                functions,
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
                functions,
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
                    **attribution(annotate(formation, result)),
                }
            )

    latest_book, latest_features = build(0, latest=True)
    latest_rows = []
    for variant in variants:
        result = run(
            functions,
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

    entry_evidence = {
        variant: forced_entry_evidence(
            full_trades[variant],
            book,
            features[0],
            short_config,
        )
        for variant in variants
    }
    for variant in (MA_ONLY, MA_AND_SLOPE):
        if not all(item["entry_below_ma7"] for item in entry_evidence[variant]):
            raise RuntimeError(f"{variant} retained above-MA7 reversal")
    if not all(
        item["slope_pass"] for item in entry_evidence[MA_AND_SLOPE]
    ):
        raise RuntimeError("MA_AND_SLOPE retained slope-failing reversal")

    metrics_frame = pd.DataFrame(rows)
    phase_frame = pd.DataFrame(phase_rows)
    rolling_frame = pd.DataFrame(rolling_rows)
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_version": "HYPE-1D-MA7-Asymmetric-Body-Trend-V3",
        "status": "diagnostic only; V3 unchanged",
        "contract": (
            "specs/hype-1d-ma7-abt-v3-forced-reversal-confirmation-"
            "contract-2026-08-07.md"
        ),
        "variants": {
            V3_CONTROL: "unconditional trailing-stop short reversal",
            MA_ONLY: "reversal open below last completed MA7",
            MA_AND_SLOPE: (
                "MA_ONLY plus V3 natural-short down-slope threshold"
            ),
        },
        "entry_evidence": entry_evidence,
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
        "data_quality": {
            "hourly": hourly_quality,
            "funding": funding_quality,
        },
        "evidence_role": "post-reveal mechanism diagnostic; not clean OOS",
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"hype_1d_v3_reversal_confirmation_{args.run_date}"
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
                "forced_reversal_trades",
                "reversal_rejections",
                "forced_reversal_one_bar_or_less",
            ],
        ].to_string(index=False)
    )
    print(json.dumps(clean(entry_evidence), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
