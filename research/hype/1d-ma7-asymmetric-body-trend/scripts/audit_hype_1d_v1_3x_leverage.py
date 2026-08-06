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
HELPER_PATH = FAMILY_DIR / "scripts/audit_hype_1d_v1_ema7_substitution.py"
HELPER_SHA256 = (
    "3a2837dd1d315f477270c555fac74b35efed4ff102facfe65171e54cb77d5dc5"
)
LEVERAGE = 3.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Entry-target 3x leverage audit for "
            "HYPE-1D-MA7-Asymmetric-Body-Trend-V1."
        )
    )
    parser.add_argument(
        "--run-date",
        default=datetime.now(UTC).date().isoformat(),
    )
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def load_helper() -> Any:
    digest = hashlib.sha256(HELPER_PATH.read_bytes()).hexdigest()
    if digest != HELPER_SHA256:
        raise RuntimeError(
            f"helper drift: expected {HELPER_SHA256}, got {digest}"
        )
    spec = importlib.util.spec_from_file_location(
        "hype_v1_3x_helper",
        HELPER_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {HELPER_PATH}")
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
def leverage_patch(engine: Any) -> Iterator[None]:
    original = engine._target_quantity
    engine._target_quantity = leveraged_target_quantity
    try:
        yield
    finally:
        engine._target_quantity = original


def run(
    engine: Any,
    book: Any,
    features: Any,
    long_config: Any | None,
    short_config: Any | None,
    *,
    start: int,
    end: int,
    slippage: float | None = None,
    signal_lag: int = 0,
    include_funding: bool = True,
) -> Any:
    kwargs: dict[str, Any] = {}
    if slippage is not None:
        kwargs["slippage"] = slippage
    result = engine.backtest(
        book,
        features,
        long_config=long_config,
        short_config=short_config,
        start_index=start,
        terminal_index=end,
        signal_lag=signal_lag,
        include_funding=include_funding,
        retain=True,
        **kwargs,
    )
    result.metrics["bankruptcy_ts"] = (
        result.path[-1]["ts"]
        if result.metrics["bankrupt_intraday"] and result.path
        else None
    )
    return result


def phase_audit(
    engine: Any,
    books: dict[int, Any],
    features: dict[int, Any],
    long_config: Any,
    short_config: Any,
) -> list[dict[str, Any]]:
    common_start = max(book.ts[0] for book in books.values())
    common_end = min(book.terminal_ts for book in books.values())
    rows: list[dict[str, Any]] = []
    for variant, long_leg, short_leg in (
        ("combined", long_config, short_config),
        ("long_only", long_config, None),
        ("short_only", None, short_config),
    ):
        for phase, book in sorted(books.items()):
            timestamps = pd.DatetimeIndex([*book.ts, book.terminal_ts])
            start = int(book.ts.searchsorted(common_start, side="left"))
            end = int(timestamps.searchsorted(common_end, side="right") - 1)
            result = run(
                engine,
                book,
                features[phase],
                long_leg,
                short_leg,
                start=start,
                end=end,
            )
            rows.append(
                {
                    "variant": variant,
                    "phase_hours": phase,
                    "common_start": common_start.isoformat(),
                    "common_end": common_end.isoformat(),
                    **result.metrics,
                }
            )
    return rows


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: clean_json(item)
            for key, item in value.items()
            if key != "_retained"
        }
    if isinstance(value, (list, tuple)):
        return [clean_json(item) for item in value]
    if isinstance(value, np.generic):
        return clean_json(value.item())
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def main() -> None:
    args = parse_args()
    helper = load_helper()
    engine = helper.load_module(
        helper.ENGINE_PATH,
        helper.ENGINE_SHA256,
        "hype_v1_3x_engine",
    )
    base = helper.load_module(
        helper.BASE_PATH,
        helper.BASE_SHA256,
        "hype_v1_3x_base",
    )
    long_config, short_config = helper.frozen_configs(engine)
    if args.self_test:
        qty, post, turnover = leveraged_target_quantity(
            1.0,
            0.0,
            1,
            100.0,
            0.0014,
        )
        assert 2.9 < qty * 100.0 / post < 3.1
        assert turnover > 0.0 and post < 1.0
        exit_qty, exit_post, _ = leveraged_target_quantity(
            post,
            qty,
            0,
            100.0,
            0.0014,
        )
        assert exit_qty == 0.0 and exit_post < post
        print("self-test: PASS")
        return

    books, hourly, funding = helper.load_inputs(engine, base)
    features = {
        phase: engine.build_features(book, hourly, funding)
        for phase, book in books.items()
    }
    book = books[0]
    prefit_end = int(
        book.ts.searchsorted(engine.HOLDOUT_START, side="left")
    )
    baseline_1x = run(
        engine,
        book,
        features[0],
        long_config,
        short_config,
        start=0,
        end=book.count,
    )
    windows = {
        "prefit": (0, prefit_end),
        "last_90d_flat": (prefit_end, book.count),
        "full": (0, book.count),
    }
    metric_rows: list[dict[str, Any]] = [
        {
            "leverage": "1x",
            "window": "full",
            "variant": "combined",
            **baseline_1x.metrics,
        }
    ]
    retained: dict[str, Any] = {}
    payload_3x: dict[str, Any] = {"windows": {}}
    with leverage_patch(engine):
        for window, (start, end) in windows.items():
            for variant, long_leg, short_leg in (
                ("combined", long_config, short_config),
                ("long_only", long_config, None),
                ("short_only", None, short_config),
            ):
                result = run(
                    engine,
                    book,
                    features[0],
                    long_leg,
                    short_leg,
                    start=start,
                    end=end,
                )
                payload_3x["windows"].setdefault(window, {})[
                    variant
                ] = result.metrics
                metric_rows.append(
                    {
                        "leverage": "3x_entry_target",
                        "window": window,
                        "variant": variant,
                        **result.metrics,
                    }
                )
                if window == "full":
                    retained[variant] = result
        scenarios = {
            "stress_8bps": {
                "slippage": engine.STRESS_SLIPPAGE,
            },
            "one_day_extra_delay": {
                "signal_lag": 1,
            },
            "zero_funding_control": {
                "include_funding": False,
            },
        }
        for scenario, kwargs in scenarios.items():
            result = run(
                engine,
                book,
                features[0],
                long_config,
                short_config,
                start=0,
                end=book.count,
                **kwargs,
            )
            payload_3x[scenario] = result.metrics
            metric_rows.append(
                {
                    "leverage": "3x_entry_target",
                    "window": "full",
                    "variant": scenario,
                    **result.metrics,
                }
            )
        phase_rows = phase_audit(
            engine,
            books,
            features,
            long_config,
            short_config,
        )
        rolling_rows: list[dict[str, Any]] = []
        for variant, long_leg, short_leg in (
            ("combined", long_config, short_config),
            ("long_only", long_config, None),
            ("short_only", None, short_config),
        ):
            rolling_rows.extend(
                {
                    "variant": variant,
                    **row,
                }
                for row in engine.rolling_rows(
                    long_leg,
                    short_leg,
                    book,
                    features[0],
                )
            )
    recent_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    for variant, result in retained.items():
        recent_rows.extend(
            {
                "variant": variant,
                **row,
            }
            for row in engine.recent_slices(result)
        )
        trade_rows.extend(
            {
                "variant": variant,
                **trade,
            }
            for trade in result.trades
        )
    payload_3x["phase_audit"] = phase_rows
    payload_3x["rolling_90d"] = {
        variant: {
            "count": len(selected),
            "positive": sum(
                row["net_return_pct"] > 0.0 for row in selected
            ),
            "median_return_pct": float(
                np.median([
                    row["net_return_pct"] for row in selected
                ])
            ),
            "min_return_pct": min(
                row["net_return_pct"] for row in selected
            ),
        }
        for variant in ("combined", "long_only", "short_only")
        for selected in [[
            row for row in rolling_rows if row["variant"] == variant
        ]]
    }
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "HYPE-1D-MA7-Asymmetric-Body-Trend",
        "source_version": "HYPE-1D-MA7-Asymmetric-Body-Trend-V1",
        "status": "registered V1 unchanged; 3x diagnostic only",
        "leverage_contract": (
            "target 3x post-cost equity at each entry; fixed quantity "
            "until exit; no daily rebalancing"
        ),
        "risk_scope": (
            "intraday equity<=0 is bankruptcy; exact Binance maintenance "
            "margin tiers, liquidation trigger and liquidation fee are not "
            "modeled, so this is not a live liquidation simulation"
        ),
        "source_helper": {
            "path": str(HELPER_PATH.relative_to(ROOT)),
            "sha256": HELPER_SHA256,
        },
        "data_quality": book.quality,
        "baseline_1x": baseline_1x.metrics,
        "leverage_3x": payload_3x,
        "buy_and_hold_1x": engine.buy_and_hold(book, features[0]),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = "hype_1d_v1_3x_leverage"
    clean_payload = clean_json(payload)
    (ARTIFACT_DIR / f"{stem}_summary_{args.run_date}.json").write_text(
        json.dumps(
            clean_payload,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    pd.DataFrame(metric_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_metrics_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(recent_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_recent_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(phase_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_phase_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(rolling_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_rolling_90d_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(trade_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_trades_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(retained["combined"].path).to_csv(
        ARTIFACT_DIR / f"{stem}_path_{args.run_date}.csv",
        index=False,
    )
    print(
        json.dumps(
            {
                "baseline_1x": clean_payload["baseline_1x"],
                "leverage_3x": clean_payload["leverage_3x"],
                "buy_and_hold_1x": clean_payload["buy_and_hold_1x"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
