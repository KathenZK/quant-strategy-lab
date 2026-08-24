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
HYBRID_CORE = "HYBRID_CORE"
HYBRID_V2_RISK = "HYBRID_V2_RISK"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit persistent MA7 state with frozen V2 slope gates."
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


def transition_counts(result: Any) -> dict[str, int]:
    trades = sorted(
        result.trades,
        key=lambda row: pd.Timestamp(row["entry_ts"]),
    )
    direct_flips = 0
    flat_exits = 0
    for index, trade in enumerate(trades):
        if trade["exit_reason"] == "terminal_flatten":
            continue
        next_trade = trades[index + 1] if index + 1 < len(trades) else None
        is_flip = (
            next_trade is not None
            and pd.Timestamp(next_trade["entry_ts"])
            == pd.Timestamp(trade["exit_ts"])
            and next_trade["side"] != trade["side"]
        )
        if is_flip:
            direct_flips += 1
        else:
            flat_exits += 1
    return {
        "direct_flip_count": direct_flips,
        "flat_exit_count": flat_exits,
        "protective_exit_count": sum(
            row["exit_reason"] == "protective_stop" for row in trades
        ),
    }


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
        **transition_counts(result),
        "exposure_pct": exposure_pct(result),
    }


def entry_quality(
    result: Any,
    variant: str,
    book: Any,
) -> list[dict[str, Any]]:
    index = pd.DatetimeIndex(book.ts)
    rows: list[dict[str, Any]] = []
    for trade_number, trade in enumerate(result.trades, 1):
        entry_day = pd.Timestamp(trade["entry_ts"]).floor("1D")
        entry_index = int(index.searchsorted(entry_day))
        if entry_index >= book.count:
            continue
        side = 1 if trade["side"] == "long" else -1
        row = {
            "variant": variant,
            "trade_number": trade_number,
            "entry_ts": trade["entry_ts"],
            "side": trade["side"],
            "trade_net_return": trade["net_return"],
            "exit_reason": trade["exit_reason"],
        }
        for horizon in (3, 7, 14):
            end = min(book.count - 1, entry_index + horizon)
            row[f"forward_{horizon}d_directional_return"] = side * (
                float(book.close[end]) / float(book.open[entry_index]) - 1.0
            )
        rows.append(row)
    return rows


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
        "hype_state_slope_formation",
    )
    engine = formation.load_pinned(
        formation.ENGINE_PATH,
        formation.ENGINE_SHA256,
        "hype_state_slope_engine",
    )
    base = formation.load_pinned(
        formation.BASE_PATH,
        formation.BASE_SHA256,
        "hype_state_slope_base",
    )
    selected = formation.read_pinned_json(
        formation.SUMMARY_PATH,
        formation.SUMMARY_SHA256,
    )["historically_profitable_all_checks"][0]
    v2_long = engine.Config(**selected["long_config"])
    v2_short = engine.Config(**selected["short_config"])
    core_long = replace(
        v2_long,
        entry_mode="regime",
        entry_buffer_atr=0.25,
        hard_stop_atr=0.0,
        trail_atr=0.0,
        max_hold_days=0,
        cooldown_days=0,
    )
    core_short = replace(
        v2_short,
        entry_mode="regime",
        entry_buffer_atr=0.75,
        hard_stop_atr=0.0,
        trail_atr=0.0,
        max_hold_days=0,
        cooldown_days=0,
    )
    risk_long = replace(
        v2_long,
        entry_mode="regime",
        entry_buffer_atr=0.25,
    )
    risk_short = replace(
        v2_short,
        entry_mode="regime",
        entry_buffer_atr=0.75,
    )
    if args.self_test:
        assert core_long.entry_mode == core_short.entry_mode == "regime"
        assert core_long.entry_buffer_atr == 0.25
        assert core_short.entry_buffer_atr == 0.75
        assert core_long.slope_min_atr == core_short.slope_min_atr == 0.02
        assert not core_long.trail_atr and not core_short.hard_stop_atr
        assert risk_long.trail_atr == 1.5
        assert risk_short.hard_stop_atr == 1.5
        assert risk_short.slope_exit_lookback == 1
        print("self-test passed: hybrid core and V2 risk configs")
        return

    v2_backtest = formation.build_reversal_backtest(engine)
    configs = {
        HYBRID_CORE: (core_long, core_short),
        HYBRID_V2_RISK: (risk_long, risk_short),
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
        retain: bool = True,
    ) -> Any:
        if variant == V2_CONTROL:
            return v2_backtest(
                target_book,
                target_features,
                long_config=v2_long,
                short_config=v2_short,
                start_index=start,
                terminal_index=end,
                slippage=slippage,
                signal_lag=signal_lag,
                include_funding=include_funding,
                retain=retain,
            )
        long_config, short_config = configs[variant]
        return engine.backtest(
            target_book,
            target_features,
            long_config=long_config,
            short_config=short_config,
            start_index=start,
            terminal_index=end,
            slippage=slippage,
            signal_lag=signal_lag,
            include_funding=include_funding,
            retain=retain,
        )

    variants = (V2_CONTROL, HYBRID_CORE, HYBRID_V2_RISK)
    rows: list[dict[str, Any]] = []
    recent_rows: list[dict[str, Any]] = []
    rolling_rows: list[dict[str, Any]] = []
    full_results: dict[str, Any] = {}
    for variant in variants:
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
                    **transition_counts(result),
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
    for variant in variants:
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
                    **transition_counts(result),
                    "exposure_pct": exposure_pct(result),
                }
            )

    latest_book, latest_features = build(0, latest=True)
    latest_rows = []
    for variant in variants:
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

    entry_quality_rows = []
    for variant, result in full_results.items():
        entry_quality_rows.extend(entry_quality(result, variant, book))
    entry_quality_frame = pd.DataFrame(entry_quality_rows)
    side_summary = {}
    for variant, result in full_results.items():
        frame = pd.DataFrame(result.trades)
        side_summary[variant] = {}
        for side, selected_side in frame.groupby("side"):
            quality = entry_quality_frame.loc[
                entry_quality_frame["variant"].eq(variant)
                & entry_quality_frame["side"].eq(side)
            ]
            side_summary[variant][str(side)] = {
                "trades": int(len(selected_side)),
                "wins": int((selected_side["net_pnl"] > 0.0).sum()),
                "net_pnl_sum": float(selected_side["net_pnl"].sum()),
                "median_trade_return": float(
                    selected_side["net_return"].median()
                ),
                "median_forward_14d_directional_return": float(
                    quality["forward_14d_directional_return"].median()
                ),
            }

    phase_frame = pd.DataFrame(phase_rows)
    rolling_frame = pd.DataFrame(rolling_rows)
    phase_summary = {
        variant: summarize(
            phase_frame.loc[phase_frame["variant"].eq(variant)]
        )
        for variant in variants
    }
    rolling_summary = {
        variant: summarize(
            rolling_frame.loc[rolling_frame["variant"].eq(variant)]
        )
        for variant in variants
    }
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "HYPE-1D-MA7-Asymmetric-Body-Trend",
        "status": "diagnostic only; V2 unchanged; no new version registered",
        "contract": (
            "specs/hype-1d-ma7-abt-state-slope-hybrid-contract-2026-08-07.md"
        ),
        "configs": {
            HYBRID_CORE: {
                "long": asdict(core_long),
                "short": asdict(core_short),
            },
            HYBRID_V2_RISK: {
                "long": asdict(risk_long),
                "short": asdict(risk_short),
            },
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
        "phase_summary": phase_summary,
        "rolling_90d_summary": rolling_summary,
        "side_and_entry_quality": side_summary,
        "evidence_role": (
            "post-reveal zero-tuning hybrid diagnostic; not OOS or promotion"
        ),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"hype_1d_ma7_state_slope_hybrid_{args.run_date}"
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
    entry_quality_frame.to_csv(
        ARTIFACT_DIR / f"{stem}_entry_quality.csv",
        index=False,
    )
    for variant in (HYBRID_CORE, HYBRID_V2_RISK):
        pd.DataFrame(full_results[variant].trades).to_csv(
            ARTIFACT_DIR / f"{stem}_{variant.lower()}_trades.csv",
            index=False,
        )
        pd.DataFrame(full_results[variant].path).to_csv(
            ARTIFACT_DIR / f"{stem}_{variant.lower()}_path.csv",
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
                "exposure_pct",
                "direct_flip_count",
                "flat_exit_count",
                "protective_exit_count",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
