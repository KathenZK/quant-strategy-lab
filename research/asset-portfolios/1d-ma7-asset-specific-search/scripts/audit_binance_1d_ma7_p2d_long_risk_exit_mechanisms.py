from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, replace
from datetime import UTC, datetime
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-ma7-asset-specific-search"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
BASELINE_PATH = (
    FAMILY_DIR
    / "scripts/audit_binance_1d_ma7_shared_v1_long_history.py"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Development-only P2-D long risk/exit mechanism ablation."
    )
    parser.add_argument(
        "--run-date", default=datetime.now(UTC).date().isoformat()
    )
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def frozen_arms(long_config: Any) -> dict[str, Any]:
    parent = replace(long_config, entry_mode="pullback_reclaim")
    return {
        "P0_PULLBACK": parent,
        "H2_INITIAL_STOP": replace(parent, hard_stop_atr=2.0),
        "X0_STRUCTURE_EXIT": replace(
            parent,
            exit_confirm_days=1,
            exit_buffer_atr=0.0,
        ),
        "H2_X0_COMBINED": replace(
            parent,
            hard_stop_atr=2.0,
            exit_confirm_days=1,
            exit_buffer_atr=0.0,
        ),
    }


def compact_metrics(result: Any) -> dict[str, Any]:
    return {
        key: result.metrics[key]
        for key in (
            "start_ts",
            "end_ts",
            "days",
            "equity_multiple",
            "net_return_pct",
            "max_drawdown_pct",
            "sharpe",
            "closed_trades",
            "long_trades",
            "short_trades",
            "win_rate",
            "profit_factor",
            "turnover_multiple",
            "cost_pct_initial",
            "funding_pct_initial",
            "max_intraday_leverage",
            "bankrupt_intraday",
        )
    }


def run(
    baseline: Any,
    engine: Any,
    book: Any,
    features: Any,
    long_config: Any,
    short_config: Any | None,
    *,
    start: int,
    end: int,
    slippage: float,
    signal_lag: int,
) -> Any:
    return baseline.run_window(
        engine,
        book,
        features,
        long_config,
        short_config,
        start=start,
        end=end,
        slippage=slippage,
        signal_lag=signal_lag,
        retain=False,
    )


def calendar_windows(
    book: Any,
    *,
    start: int,
    end: int,
) -> list[tuple[str, int, int]]:
    timestamps = pd.DatetimeIndex([*book.ts, book.terminal_ts])
    start_ts = pd.Timestamp(timestamps[start])
    end_ts = pd.Timestamp(timestamps[end])
    output: list[tuple[str, int, int]] = []
    for year in range(start_ts.year, end_ts.year + 1):
        left_ts = max(start_ts, pd.Timestamp(f"{year}-01-01T00:00:00Z"))
        right_ts = min(end_ts, pd.Timestamp(f"{year + 1}-01-01T00:00:00Z"))
        if right_ts <= left_ts:
            continue
        left = int(timestamps.searchsorted(left_ts, side="left"))
        right = int(timestamps.searchsorted(right_ts, side="left"))
        if right > left:
            output.append((str(year), left, right))
    return output


def rolling_windows(
    *,
    start: int,
    end: int,
    length: int = 365,
    step: int = 90,
) -> list[tuple[str, int, int]]:
    output: list[tuple[str, int, int]] = []
    left = start
    while left + length <= end:
        right = left + length
        output.append((f"{left}_{right}", left, right))
        left += step
    return output


def positive_share(rows: list[dict[str, Any]], *, scope: str) -> float:
    selected = [
        row
        for row in rows
        if row["scope"] == scope
        and row["variant"] == "combined"
        and row["stress"] == "base"
    ]
    if not selected:
        return math.nan
    return float(
        np.mean([row["equity_multiple"] > 1.0 for row in selected])
    )


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: clean_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json(item) for item in value]
    if isinstance(value, np.generic):
        return clean_json(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def main() -> None:
    args = parse_args()
    baseline = load_module(BASELINE_PATH, "binance_ma7_p2d_baseline")
    transfer = baseline.load_module(
        baseline.TRANSFER_PATH,
        baseline.TRANSFER_SHA256,
        "binance_ma7_p2d_transfer",
    )
    engine = transfer.load_engine()
    long_config, short_config = baseline.v1_configs(engine)
    arms = frozen_arms(long_config)
    if args.self_test:
        assert list(arms) == [
            "P0_PULLBACK",
            "H2_INITIAL_STOP",
            "X0_STRUCTURE_EXIT",
            "H2_X0_COMBINED",
        ]
        assert len({config.key for config in arms.values()}) == 4
        print("self-test: PASS")
        return

    manifest = json.loads(baseline.P0_MANIFEST.read_text(encoding="utf-8"))
    contexts: dict[str, tuple[Any, Any, int, int]] = {}
    for symbol, slug in baseline.ASSETS.items():
        hourly, funding, quality = baseline.load_snapshot(symbol, slug, manifest)
        book = transfer.build_book(symbol, hourly, quality, phase_hours=0)
        features = engine.build_features(book, hourly, funding)
        contexts[symbol] = (
            book,
            features,
            baseline.boundary(book, baseline.COMMON_START),
            baseline.boundary(book, baseline.DEVELOPMENT_END),
        )

    metric_rows: list[dict[str, Any]] = []
    arm_payload: dict[str, Any] = {}
    for arm_id, arm_long in arms.items():
        arm_payload[arm_id] = {
            "long_config": asdict(arm_long),
            "assets": {},
        }
        for symbol, (book, features, start, end) in contexts.items():
            full_results: dict[str, Any] = {}
            exit_counts: dict[str, Any] = {}
            for variant, short_leg in (
                ("combined", short_config),
                ("long_only", None),
            ):
                for stress, slippage, lag in (
                    ("base", engine.BASE_SLIPPAGE, 0),
                    ("stress_8bps", engine.STRESS_SLIPPAGE, 0),
                    ("one_day_extra_delay", engine.BASE_SLIPPAGE, 1),
                ):
                    result = run(
                        baseline,
                        engine,
                        book,
                        features,
                        arm_long,
                        short_leg,
                        start=start,
                        end=end,
                        slippage=slippage,
                        signal_lag=lag,
                    )
                    key = f"{variant}__{stress}"
                    full_results[key] = compact_metrics(result)
                    if stress == "base":
                        exit_counts[variant] = dict(
                            sorted(
                                Counter(
                                    row["exit_reason"] for row in result.trades
                                ).items()
                            )
                        )
                    metric_rows.append(
                        {
                            "arm_id": arm_id,
                            "symbol": symbol,
                            "variant": variant,
                            "scope": "full_development",
                            "window": "full_development",
                            "stress": stress,
                            **compact_metrics(result),
                        }
                    )
                for scope, windows in (
                    (
                        "calendar_year",
                        calendar_windows(book, start=start, end=end),
                    ),
                    (
                        "rolling_365d",
                        rolling_windows(start=start, end=end),
                    ),
                ):
                    for label, left, right in windows:
                        result = run(
                            baseline,
                            engine,
                            book,
                            features,
                            arm_long,
                            short_leg,
                            start=left,
                            end=right,
                            slippage=engine.BASE_SLIPPAGE,
                            signal_lag=0,
                        )
                        metric_rows.append(
                            {
                                "arm_id": arm_id,
                                "symbol": symbol,
                                "variant": variant,
                                "scope": scope,
                                "window": label,
                                "stress": "base",
                                **compact_metrics(result),
                            }
                        )
            arm_payload[arm_id]["assets"][symbol] = {
                "full": full_results,
                "exit_reason_counts": exit_counts,
            }
        arm_rows = [row for row in metric_rows if row["arm_id"] == arm_id]
        arm_payload[arm_id]["calendar_positive_share"] = {
            symbol: positive_share(
                [row for row in arm_rows if row["symbol"] == symbol],
                scope="calendar_year",
            )
            for symbol in baseline.ASSETS
        }
        arm_payload[arm_id]["rolling_positive_share"] = {
            symbol: positive_share(
                [row for row in arm_rows if row["symbol"] == symbol],
                scope="rolling_365d",
            )
            for symbol in baseline.ASSETS
        }

    parent = arm_payload["P0_PULLBACK"]
    for arm_id, value in arm_payload.items():
        asset_base = {
            symbol: asset["full"]["combined__base"]
            for symbol, asset in value["assets"].items()
        }
        value["hard_target_pass"] = all(
            metrics["equity_multiple"] >= 20.0
            and metrics["max_drawdown_pct"] >= -20.0
            for metrics in asset_base.values()
        )
        if arm_id == "P0_PULLBACK":
            value["soft_continue_pass"] = False
            value["soft_continue_note"] = "parent control"
            continue
        improves_shares = all(
            value["calendar_positive_share"][symbol]
            >= parent["calendar_positive_share"][symbol]
            and value["rolling_positive_share"][symbol]
            >= parent["rolling_positive_share"][symbol]
            for symbol in baseline.ASSETS
        )
        full_positive = all(
            asset["full"][f"combined__{stress}"]["equity_multiple"] > 1.0
            for asset in value["assets"].values()
            for stress in ("base", "stress_8bps", "one_day_extra_delay")
        )
        value["soft_continue_pass"] = bool(
            all(
                metrics["max_drawdown_pct"] >= -35.0
                for metrics in asset_base.values()
            )
            and full_positive
            and improves_shares
        )
        value["soft_continue_note"] = (
            "requires both MDD<=35%, positive base/stress/delay, and no "
            "calendar/rolling positive-share deterioration versus parent"
        )

    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "Binance-1D-MA7-Asset-Specific-Search",
        "campaign": "P2-D long risk/exit mechanisms",
        "status": "explore / not promoted / not live-ready",
        "evidence_role": "development-only; audit and prospective not read",
        "development": {
            "start": baseline.COMMON_START.isoformat(),
            "end_exclusive": baseline.DEVELOPMENT_END.isoformat(),
        },
        "short_config": asdict(short_config),
        "hard_target_hit_count": sum(
            value["hard_target_pass"] for value in arm_payload.values()
        ),
        "soft_continue_hit_count": sum(
            value["soft_continue_pass"] for value in arm_payload.values()
        ),
        "arms": arm_payload,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"binance_1d_ma7_p2d_long_risk_exit_mechanisms_{args.run_date}"
    (ARTIFACT_DIR / f"{stem}.json").write_text(
        json.dumps(clean_json(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    pd.DataFrame(metric_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_metrics.csv", index=False
    )
    print(
        json.dumps(
            clean_json(
                {
                    "hard_target_hit_count": payload[
                        "hard_target_hit_count"
                    ],
                    "soft_continue_hit_count": payload[
                        "soft_continue_hit_count"
                    ],
                    "arms": {
                        arm_id: {
                            "hard_target_pass": value["hard_target_pass"],
                            "soft_continue_pass": value[
                                "soft_continue_pass"
                            ],
                            "calendar_positive_share": value[
                                "calendar_positive_share"
                            ],
                            "rolling_positive_share": value[
                                "rolling_positive_share"
                            ],
                            "assets": {
                                symbol: asset["full"]["combined__base"]
                                for symbol, asset in value["assets"].items()
                            },
                        }
                        for arm_id, value in arm_payload.items()
                    },
                }
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

