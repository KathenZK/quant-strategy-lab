from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterator

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
LEVERAGE = 3.0
V2_1X_EQUITY_MULTIPLE = 4.225904698992523
HOLDOUT_START = pd.Timestamp("2026-05-01T00:00:00Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Entry-target 3x leverage audit for HYPE-1D-MA7-ABT-V2."
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
        "hype_v2_3x_formation",
        FORMATION_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {FORMATION_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def leveraged_target_quantity(
    equity: float,
    old_qty: float,
    target_side: int,
    price: float,
    cost_rate: float,
) -> tuple[float, float, float]:
    post_equity = equity
    target_qty = old_qty
    turnover = 0.0
    for _ in range(50):
        target_qty = target_side * LEVERAGE * post_equity / price
        turnover = abs(target_qty - old_qty) * price
        updated = equity - turnover * cost_rate
        if math.isclose(
            updated,
            post_equity,
            rel_tol=0.0,
            abs_tol=1e-14,
        ):
            post_equity = updated
            break
        post_equity = updated
    return target_qty, post_equity, turnover


@contextmanager
def leverage_patch(engine: Any, backtest: Any) -> Iterator[None]:
    original_engine = engine._target_quantity
    original_backtest = backtest.__globals__["_target_quantity"]
    engine._target_quantity = leveraged_target_quantity
    backtest.__globals__["_target_quantity"] = leveraged_target_quantity
    try:
        yield
    finally:
        engine._target_quantity = original_engine
        backtest.__globals__["_target_quantity"] = original_backtest


def run(
    backtest: Any,
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
    result = backtest(
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
    result.metrics["bankruptcy_ts"] = (
        result.path[-1]["ts"]
        if result.metrics["bankrupt_intraday"] and result.path
        else None
    )
    return result


def rolling_rows(
    backtest: Any,
    book: Any,
    features: Any,
    long_config: Any,
    short_config: Any,
    slippage: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    while start + 90 <= book.count:
        end = start + 90
        result = run(
            backtest,
            book,
            features,
            long_config,
            short_config,
            start=start,
            end=end,
            slippage=slippage,
        )
        rows.append({"window_index": len(rows), **result.metrics})
        start += 30
    return rows


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
    if args.self_test:
        qty, post, turnover = leveraged_target_quantity(
            1.0, 0.0, 1, 100.0, 0.0014
        )
        if not (2.999 < qty * 100.0 / post < 3.001):
            raise AssertionError("entry leverage target drift")
        exit_qty, exit_post, exit_turnover = leveraged_target_quantity(
            post, qty, 0, 90.0, 0.0014
        )
        if exit_qty != 0.0 or exit_post >= post or exit_turnover <= 0.0:
            raise AssertionError("leveraged exit accounting drift")
        print(
            "self-test passed: post-cost entry target is 3x and exits charge cost"
        )
        return

    formation = load_formation()
    engine = formation.load_pinned(
        formation.ENGINE_PATH,
        formation.ENGINE_SHA256,
        "hype_v2_3x_engine",
    )
    base = formation.load_pinned(
        formation.BASE_PATH,
        formation.BASE_SHA256,
        "hype_v2_3x_base",
    )
    summary = formation.read_pinned_json(
        formation.SUMMARY_PATH,
        formation.SUMMARY_SHA256,
    )
    selected = summary["historically_profitable_all_checks"][0]
    long_config = engine.Config(**selected["long_config"])
    short_config = engine.Config(**selected["short_config"])
    backtest = formation.build_reversal_backtest(engine)

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

    books: dict[int, Any] = {}
    features: dict[int, Any] = {}
    for phase in formation.PHASES:
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
    book = books[0]
    prefit_end = int(pd.DatetimeIndex(book.ts).searchsorted(HOLDOUT_START))

    baseline = run(
        backtest,
        book,
        features[0],
        long_config,
        short_config,
        start=0,
        end=book.count,
        slippage=engine.BASE_SLIPPAGE,
        retain=True,
    )
    if not math.isclose(
        baseline.metrics["equity_multiple"],
        V2_1X_EQUITY_MULTIPLE,
        rel_tol=1e-10,
        abs_tol=1e-10,
    ):
        raise RuntimeError("V2 1x anchor drift")

    windows = {
        "prefit": (0, prefit_end),
        "last_90d_flat": (prefit_end, book.count),
        "full": (0, book.count),
    }
    metrics_rows: list[dict[str, Any]] = [
        {
            "leverage": "1x_registered",
            "window": "full",
            "scenario": "base_4bps",
            **baseline.metrics,
            **formation.attribution(
                formation.annotate_trades(
                    baseline,
                    "T1_trailing_stop_short_reversal",
                )
            ),
        }
    ]
    retained_3x: Any = None
    results_3x: dict[str, Any] = {"windows": {}}

    with leverage_patch(engine, backtest):
        for window, (start, end) in windows.items():
            result = run(
                backtest,
                book,
                features[0],
                long_config,
                short_config,
                start=start,
                end=end,
                slippage=engine.BASE_SLIPPAGE,
                retain=window == "full",
            )
            trades = formation.annotate_trades(
                result,
                "T1_trailing_stop_short_reversal",
            )
            stats = formation.attribution(trades)
            results_3x["windows"][window] = {
                "metrics": result.metrics,
                "reversal_attribution": stats,
            }
            metrics_rows.append(
                {
                    "leverage": "3x_entry_target",
                    "window": window,
                    "scenario": "base_4bps",
                    **result.metrics,
                    **stats,
                }
            )
            if window == "full":
                retained_3x = result

        for scenario, kwargs in {
            "stress_8bps": {"slippage": engine.STRESS_SLIPPAGE},
            "one_day_extra_delay": {
                "slippage": engine.BASE_SLIPPAGE,
                "signal_lag": 1,
            },
            "zero_funding_control": {
                "slippage": engine.BASE_SLIPPAGE,
                "include_funding": False,
            },
        }.items():
            result = run(
                backtest,
                book,
                features[0],
                long_config,
                short_config,
                start=0,
                end=book.count,
                **kwargs,
            )
            stats = formation.attribution(
                formation.annotate_trades(
                    result,
                    "T1_trailing_stop_short_reversal",
                )
            )
            results_3x[scenario] = {
                "metrics": result.metrics,
                "reversal_attribution": stats,
            }
            metrics_rows.append(
                {
                    "leverage": "3x_entry_target",
                    "window": "full",
                    "scenario": scenario,
                    **result.metrics,
                    **stats,
                }
            )

        phase_rows: list[dict[str, Any]] = []
        for phase in formation.PHASES:
            result = run(
                backtest,
                books[phase],
                features[phase],
                long_config,
                short_config,
                start=0,
                end=books[phase].count,
                slippage=engine.BASE_SLIPPAGE,
            )
            phase_rows.append(
                {
                    "phase_hours": phase,
                    **result.metrics,
                    **formation.attribution(
                        formation.annotate_trades(
                            result,
                            "T1_trailing_stop_short_reversal",
                        )
                    ),
                }
            )

        rolling = rolling_rows(
            backtest,
            book,
            features[0],
            long_config,
            short_config,
            engine.BASE_SLIPPAGE,
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
        latest_result = run(
            backtest,
            latest_book,
            latest_features,
            long_config,
            short_config,
            start=0,
            end=latest_book.count,
            slippage=engine.BASE_SLIPPAGE,
            retain=True,
        )

    if retained_3x is None:
        raise RuntimeError("missing retained 3x result")
    if retained_3x.metrics["max_intraday_leverage"] < 2.9:
        raise RuntimeError("3x integration patch was not applied")

    annotated_trades = formation.annotate_trades(
        retained_3x,
        "T1_trailing_stop_short_reversal",
    )
    recent = engine.recent_slices(retained_3x)
    rolling_returns = [row["net_return_pct"] for row in rolling]
    results_3x["phase_audit"] = phase_rows
    results_3x["rolling_90d"] = {
        "count": len(rolling),
        "positive": int(sum(value > 0.0 for value in rolling_returns)),
        "median_return_pct": float(np.median(rolling_returns)),
        "min_return_pct": float(min(rolling_returns)),
        "max_drawdown_worst_pct": float(
            min(row["max_drawdown_pct"] for row in rolling)
        ),
        "bankrupt_windows": int(
            sum(bool(row["bankrupt_intraday"]) for row in rolling)
        ),
    }
    results_3x["latest_extension"] = {
        "metrics": latest_result.metrics,
        "reversal_attribution": formation.attribution(
            formation.annotate_trades(
                latest_result,
                "T1_trailing_stop_short_reversal",
            )
        ),
    }

    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "HYPE-1D-MA7-Asymmetric-Body-Trend",
        "source_version": "HYPE-1D-MA7-Asymmetric-Body-Trend-V2",
        "source_status": "registered / not promoted / not live-ready",
        "diagnostic_status": (
            "3x official observation only; registered V2 remains 1x"
        ),
        "contract": (
            "specs/hype-1d-ma7-abt-v2-3x-leverage-contract-2026-08-06.md"
        ),
        "pins": {
            "formation_path": str(FORMATION_PATH.relative_to(ROOT)),
            "formation_sha256": FORMATION_SHA256,
            "engine_sha256": formation.ENGINE_SHA256,
            "base_sha256": formation.BASE_SHA256,
        },
        "leverage_contract": (
            "target 3x post-cost equity at every natural or reversal entry; "
            "fixed quantity until exit/reversal; no daily rebalancing"
        ),
        "risk_scope": (
            "1h adverse equity<=0 is bankruptcy; Binance maintenance-margin "
            "tiers, early liquidation trigger and liquidation fee are not modeled"
        ),
        "data_quality": {
            "hourly": hourly_quality,
            "funding": funding_quality,
        },
        "baseline_v2_1x": {
            "metrics": baseline.metrics,
            "reversal_attribution": formation.attribution(
                formation.annotate_trades(
                    baseline,
                    "T1_trailing_stop_short_reversal",
                )
            ),
        },
        "leverage_v2_3x": results_3x,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"hype_1d_v2_3x_leverage_{args.run_date}"
    (ARTIFACT_DIR / f"{stem}_summary.json").write_text(
        json.dumps(clean(payload), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    pd.DataFrame(metrics_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_metrics.csv", index=False
    )
    pd.DataFrame(phase_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_phase.csv", index=False
    )
    pd.DataFrame(recent).to_csv(
        ARTIFACT_DIR / f"{stem}_recent.csv", index=False
    )
    pd.DataFrame(rolling).to_csv(
        ARTIFACT_DIR / f"{stem}_rolling_90d.csv", index=False
    )
    annotated_trades.to_csv(
        ARTIFACT_DIR / f"{stem}_trades.csv", index=False
    )
    pd.DataFrame(retained_3x.path).to_csv(
        ARTIFACT_DIR / f"{stem}_path.csv", index=False
    )

    full = results_3x["windows"]["full"]["metrics"]
    print(
        json.dumps(
            clean(
                {
                    "v2_1x": baseline.metrics,
                    "v2_3x": full,
                    "phase_12h": phase_rows[-1],
                    "rolling_90d": results_3x["rolling_90d"],
                }
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
