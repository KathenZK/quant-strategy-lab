from __future__ import annotations

import argparse
from dataclasses import asdict, replace
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import random
import sys
from typing import Any, Iterable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/4h-ma7-asymmetric-body-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
ENGINE_PATH = (
    ROOT
    / "research/hype/1d-ma7-asymmetric-body-trend/scripts"
    / "search_hype_1d_ma7_separated_trend.py"
)
ENGINE_SHA256 = "c376f8bd1bae814b0ba53687380ee1060cf3cc3095ae815ebb0311ed1aef59e1"
TRANSFER_PATH = FAMILY_DIR / "scripts/research_hype_4h_ma7_v1_transfer.py"
TRANSFER_SHA256 = (
    "4d39631cdb40b4d318c2f757110984fe5db41fa18d8578d35be8c3e04607e4e5"
)

FAMILY = "HYPE-4H-MA7-Asymmetric-Body-Trend"
BRANCH = "native-4h-ma7-trend-search"
DEVELOPMENT_END = pd.Timestamp("2026-01-01T00:00:00Z")
VALIDATION_END = pd.Timestamp("2026-04-01T00:00:00Z")
PHASES = (0, 1, 2, 3)
SEED = 20260806
SAMPLES_PER_SIDE = 8_000
SHORTLIST = 160
PAIR_POOL = 24

ENTRY_MODES = ("regime", "reclaim", "pullback_reclaim", "breakout")
SLOPE_LOOKBACK = (1, 2, 3, 5, 7, 10, 14)
SLOPE_MIN_ATR = (0.0, 0.01, 0.02, 0.05, 0.10, 0.20)
CONFIRM_BARS = (1, 2, 3, 5)
ENTRY_BUFFER_ATR = (0.0, 0.10, 0.25, 0.50, 0.75)
PULLBACK_LOOKBACK = (2, 3, 5, 7, 10, 14)
PULLBACK_TOUCH_ATR = (-0.50, -0.25, 0.0, 0.10, 0.25, 0.50)
BREAKOUT_LOOKBACK = (2, 3, 5, 7, 10, 14)
EXIT_CONFIRM_BARS = (1, 2, 3, 5)
EXIT_BUFFER_ATR = (0.0, 0.10, 0.25, 0.50, 0.75, 1.0, 1.5)
SLOPE_EXIT_LOOKBACK = (0, 1, 2, 3, 5, 7)
HARD_STOP_ATR = (1.5, 2.0, 3.0, 4.0, 5.0)
TRAIL_ATR = (0.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0)
MAX_HOLD_BARS = (0, 12, 24, 42, 60, 90, 180)
COOLDOWN_BARS = (0, 1, 2, 3, 6, 12)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search a native HYPE 4h fixed-SMA7 trend state machine."
    )
    parser.add_argument("--samples-per-side", type=int, default=SAMPLES_PER_SIDE)
    parser.add_argument("--shortlist", type=int, default=SHORTLIST)
    parser.add_argument("--pair-pool", type=int, default=PAIR_POOL)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument(
        "--run-date",
        default=datetime.now(UTC).date().isoformat(),
    )
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(path: Path, expected_hash: str, name: str) -> Any:
    digest = file_sha256(path)
    if digest != expected_hash:
        raise RuntimeError(
            f"{path.name} drift: expected {expected_hash}, got {digest}"
        )
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def random_config(engine: Any, side: int, rng: random.Random) -> Any:
    mode = rng.choice(ENTRY_MODES)
    pullback_lookback = (
        rng.choice(PULLBACK_LOOKBACK) if mode == "pullback_reclaim" else 2
    )
    pullback_touch = (
        rng.choice(PULLBACK_TOUCH_ATR)
        if mode in {"reclaim", "pullback_reclaim"}
        else 0.0
    )
    breakout_lookback = (
        rng.choice(BREAKOUT_LOOKBACK) if mode == "breakout" else 2
    )
    return engine.Config(
        side=side,
        entry_mode=mode,
        slope_lookback=rng.choice(SLOPE_LOOKBACK),
        slope_min_atr=rng.choice(SLOPE_MIN_ATR),
        confirm_days=rng.choice(CONFIRM_BARS),
        entry_buffer_atr=rng.choice(ENTRY_BUFFER_ATR),
        pullback_lookback=pullback_lookback,
        pullback_touch_atr=pullback_touch,
        breakout_lookback=breakout_lookback,
        exit_confirm_days=rng.choice(EXIT_CONFIRM_BARS),
        exit_buffer_atr=rng.choice(EXIT_BUFFER_ATR),
        slope_exit_lookback=rng.choice(SLOPE_EXIT_LOOKBACK),
        hard_stop_atr=rng.choice(HARD_STOP_ATR),
        trail_atr=rng.choice(TRAIL_ATR),
        max_hold_days=rng.choice(MAX_HOLD_BARS),
        cooldown_days=rng.choice(COOLDOWN_BARS),
    )


def unique_configs(
    engine: Any,
    side: int,
    rng: random.Random,
    count: int,
) -> list[Any]:
    output: list[Any] = []
    seen: set[tuple[Any, ...]] = set()
    while len(output) < count:
        config = random_config(engine, side, rng)
        if config.key in seen:
            continue
        seen.add(config.key)
        output.append(config)
    return output


def run_route(
    engine: Any,
    transfer: Any,
    book: Any,
    features: Any,
    long_config: Any | None,
    short_config: Any | None,
    *,
    start: int,
    end: int,
    slippage: float | None = None,
    signal_lag: int = 0,
    retain: bool = False,
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
        retain=retain,
        **kwargs,
    )
    for trade in result.trades:
        entry_ts = pd.Timestamp(trade["entry_ts"])
        exit_ts = pd.Timestamp(trade["exit_ts"])
        holding_hours = (exit_ts - entry_ts).total_seconds() / 3_600.0
        trade["holding_hours"] = holding_hours
        trade["bars_held"] = int(max(0.0, holding_hours) // 4)
    if retain:
        return transfer.normalize_sharpe(result)
    sharpe = result.metrics.get("sharpe")
    if sharpe is not None and np.isfinite(sharpe):
        result.metrics["sharpe"] = float(sharpe) * math.sqrt(6.0)
    return result


def run_single(
    engine: Any,
    transfer: Any,
    book: Any,
    features: Any,
    config: Any,
    *,
    start: int,
    end: int,
) -> Any:
    return run_route(
        engine,
        transfer,
        book,
        features,
        config if config.side > 0 else None,
        config if config.side < 0 else None,
        start=start,
        end=end,
    )


def stage1_search(
    engine: Any,
    transfer: Any,
    configs: Iterable[Any],
    book: Any,
    features: Any,
    *,
    development_end: int,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for index, config in enumerate(configs, start=1):
        result = run_single(
            engine,
            transfer,
            book,
            features,
            config,
            start=0,
            end=development_end,
        )
        metrics = result.metrics
        eligible = (
            metrics["closed_trades"] >= 8
            and metrics["max_drawdown_pct"] >= -45.0
            and metrics["equity_multiple"] > 0.0
            and not metrics["bankrupt_intraday"]
        )
        score = (
            math.log(max(float(metrics["equity_multiple"]), 1e-12))
            + 0.01 * min(30, int(metrics["closed_trades"]))
            - max(0.0, abs(float(metrics["max_drawdown_pct"])) / 100.0 - 0.35)
            if eligible
            else -math.inf
        )
        rows.append({"config": config, "stage1_score": score, **metrics})
        if index % 2_000 == 0:
            print(f"stage1 side={config.side}: {index}", flush=True)
    return pd.DataFrame(rows).sort_values(
        ["stage1_score", "equity_multiple"],
        ascending=[False, False],
    )


def route_selection_evaluation(
    engine: Any,
    transfer: Any,
    book: Any,
    features: Any,
    long_config: Any | None,
    short_config: Any | None,
    *,
    development_end: int,
    validation_end: int,
    prefit_trade_minimum: int,
) -> dict[str, Any]:
    development_mid = development_end // 2
    windows = {
        "development": (0, development_end),
        "development_early": (0, development_mid),
        "development_late": (development_mid, development_end),
        "validation": (development_end, validation_end),
        "selection_prefit": (0, validation_end),
    }
    metrics: dict[str, dict[str, Any]] = {}
    for label, (start, end) in windows.items():
        metrics[label] = run_route(
            engine,
            transfer,
            book,
            features,
            long_config,
            short_config,
            start=start,
            end=end,
        ).metrics
    metrics["selection_prefit_stress_8bps"] = run_route(
        engine,
        transfer,
        book,
        features,
        long_config,
        short_config,
        start=0,
        end=validation_end,
        slippage=engine.STRESS_SLIPPAGE,
    ).metrics
    metrics["selection_prefit_delay_1bar"] = run_route(
        engine,
        transfer,
        book,
        features,
        long_config,
        short_config,
        start=0,
        end=validation_end,
        signal_lag=1,
    ).metrics
    scored_labels = (
        "development",
        "development_early",
        "development_late",
        "validation",
        "selection_prefit_stress_8bps",
        "selection_prefit_delay_1bar",
    )
    equities = [
        float(metrics[label]["equity_multiple"]) for label in scored_labels
    ]
    worst_mdd = min(
        float(item["max_drawdown_pct"]) for item in metrics.values()
    )
    hard_pass = (
        metrics["development"]["closed_trades"] >= 8
        and metrics["validation"]["closed_trades"] >= 3
        and metrics["selection_prefit"]["closed_trades"]
        >= prefit_trade_minimum
        and metrics["development"]["equity_multiple"] > 1.0
        and metrics["validation"]["equity_multiple"] > 1.0
        and metrics["selection_prefit_stress_8bps"]["equity_multiple"] > 1.0
        and metrics["selection_prefit_delay_1bar"]["equity_multiple"] > 1.0
        and worst_mdd >= -40.0
        and not any(item["bankrupt_intraday"] for item in metrics.values())
    )
    log_equities = np.log(np.maximum(equities, 1e-12))
    worst_log_equity = float(np.min(log_equities))
    median_log_equity = float(np.median(log_equities))
    prefit_log_equity = math.log(
        max(
            float(metrics["selection_prefit"]["equity_multiple"]),
            1e-12,
        )
    )
    robust_score = (
        worst_log_equity
        + 0.5 * median_log_equity
        + 0.25 * prefit_log_equity
        - 1.5 * max(0.0, abs(worst_mdd) / 100.0 - 0.35)
        + 0.01
        * min(30, int(metrics["selection_prefit"]["closed_trades"]))
    )
    return {
        "hard_pass": hard_pass,
        "robust_score": robust_score,
        "worst_log_equity": worst_log_equity,
        "median_log_equity": median_log_equity,
        "prefit_log_equity": prefit_log_equity,
        "worst_window_mdd_pct": worst_mdd,
        "metrics": metrics,
    }


def stability_audit(
    engine: Any,
    transfer: Any,
    configs: Iterable[Any],
    book: Any,
    features: Any,
    *,
    development_end: int,
    validation_end: int,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for config in configs:
        evaluated = route_selection_evaluation(
            engine,
            transfer,
            book,
            features,
            config if config.side > 0 else None,
            config if config.side < 0 else None,
            development_end=development_end,
            validation_end=validation_end,
            prefit_trade_minimum=12,
        )
        metrics = evaluated["metrics"]
        rows.append(
            {
                "route": "long_only" if config.side > 0 else "short_only",
                "config": config,
                "long_config": config if config.side > 0 else None,
                "short_config": config if config.side < 0 else None,
                "hard_pass": evaluated["hard_pass"],
                "robust_score": evaluated["robust_score"],
                "worst_log_equity": evaluated["worst_log_equity"],
                "median_log_equity": evaluated["median_log_equity"],
                "prefit_log_equity": evaluated["prefit_log_equity"],
                "worst_window_mdd_pct": evaluated["worst_window_mdd_pct"],
                "development_return_pct": metrics["development"][
                    "net_return_pct"
                ],
                "validation_return_pct": metrics["validation"][
                    "net_return_pct"
                ],
                "prefit_return_pct": metrics["selection_prefit"][
                    "net_return_pct"
                ],
                "prefit_stress_return_pct": metrics[
                    "selection_prefit_stress_8bps"
                ]["net_return_pct"],
                "prefit_delay_return_pct": metrics[
                    "selection_prefit_delay_1bar"
                ]["net_return_pct"],
                "development_trades": metrics["development"]["closed_trades"],
                "validation_trades": metrics["validation"]["closed_trades"],
                "prefit_trades": metrics["selection_prefit"]["closed_trades"],
                "selection_metrics": metrics,
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["hard_pass", "robust_score", "prefit_return_pct"],
        ascending=[False, False, False],
    )


def pair_search(
    engine: Any,
    transfer: Any,
    long_configs: Iterable[Any],
    short_configs: Iterable[Any],
    book: Any,
    features: Any,
    *,
    development_end: int,
    validation_end: int,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for long_config in long_configs:
        for short_config in short_configs:
            evaluated = route_selection_evaluation(
                engine,
                transfer,
                book,
                features,
                long_config,
                short_config,
                development_end=development_end,
                validation_end=validation_end,
                prefit_trade_minimum=15,
            )
            metrics = evaluated["metrics"]
            rows.append(
                {
                    "route": "combined",
                    "long_config": long_config,
                    "short_config": short_config,
                    "hard_pass": evaluated["hard_pass"],
                    "robust_score": evaluated["robust_score"],
                    "worst_log_equity": evaluated["worst_log_equity"],
                    "median_log_equity": evaluated["median_log_equity"],
                    "prefit_log_equity": evaluated["prefit_log_equity"],
                    "worst_window_mdd_pct": evaluated[
                        "worst_window_mdd_pct"
                    ],
                    "development_return_pct": metrics["development"][
                        "net_return_pct"
                    ],
                    "validation_return_pct": metrics["validation"][
                        "net_return_pct"
                    ],
                    "prefit_return_pct": metrics["selection_prefit"][
                        "net_return_pct"
                    ],
                    "prefit_stress_return_pct": metrics[
                        "selection_prefit_stress_8bps"
                    ]["net_return_pct"],
                    "prefit_delay_return_pct": metrics[
                        "selection_prefit_delay_1bar"
                    ]["net_return_pct"],
                    "development_trades": metrics["development"][
                        "closed_trades"
                    ],
                    "validation_trades": metrics["validation"][
                        "closed_trades"
                    ],
                    "prefit_trades": metrics["selection_prefit"][
                        "closed_trades"
                    ],
                    "selection_metrics": metrics,
                }
            )
    return pd.DataFrame(rows).sort_values(
        [
            "hard_pass",
            "worst_log_equity",
            "median_log_equity",
            "prefit_log_equity",
        ],
        ascending=[False, False, False, False],
    )


def select_route(
    long_stable: pd.DataFrame,
    short_stable: pd.DataFrame,
    pairs: pd.DataFrame,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for frame in (long_stable, short_stable, pairs):
        candidates.extend(frame.to_dict(orient="records"))
    candidates.sort(
        key=lambda row: (
            bool(row["hard_pass"]),
            float(row["worst_log_equity"]),
            float(row["median_log_equity"]),
            float(row["prefit_log_equity"]),
        ),
        reverse=True,
    )
    if not candidates:
        raise RuntimeError("no selectable routes")
    return candidates[0]


def buy_and_hold_window(
    engine: Any,
    book: Any,
    features: Any,
    *,
    start: int,
    end: int,
    slippage: float = 0.0004,
) -> dict[str, Any]:
    opens = np.r_[book.open, float(book.quality["terminal_open"])]
    entry_price = float(opens[start])
    exit_price = float(opens[end])
    cost_rate = engine.FEE + slippage
    qty, equity, entry_turnover = engine._target_quantity(
        1.0,
        0.0,
        1,
        entry_price,
        cost_rate,
    )
    funding_payment = 0.0
    for index in range(start, end):
        for event in features.funding_events[index]:
            payment = qty * event.price * event.rate
            equity -= payment
            funding_payment += payment
    equity += qty * (exit_price - entry_price)
    exit_cost = abs(qty) * exit_price * cost_rate
    equity -= exit_cost
    return {
        "start_ts": pd.Timestamp(
            [*book.ts, book.terminal_ts][start]
        ).isoformat(),
        "end_ts": pd.Timestamp(
            [*book.ts, book.terminal_ts][end]
        ).isoformat(),
        "equity_multiple": equity,
        "net_return_pct": (equity - 1.0) * 100.0,
        "funding_pct_initial": funding_payment * 100.0,
        "cost_pct_initial": (
            entry_turnover * cost_rate + exit_cost
        )
        * 100.0,
    }


def final_audit(
    engine: Any,
    transfer: Any,
    book: Any,
    features: Any,
    long_config: Any | None,
    short_config: Any | None,
    *,
    development_end: int,
    validation_end: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], Any]:
    windows = {
        "development": (0, development_end),
        "validation": (development_end, validation_end),
        "locked_evaluation": (validation_end, book.count),
        "selection_prefit": (0, validation_end),
        "full": (0, book.count),
    }
    output: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    retained_full: Any | None = None
    for label, (start, end) in windows.items():
        scenarios = {
            "base": {"slippage": None, "signal_lag": 0},
            "stress_8bps": {
                "slippage": engine.STRESS_SLIPPAGE,
                "signal_lag": 0,
            },
            "delay_1bar": {"slippage": None, "signal_lag": 1},
        }
        output[label] = {}
        for scenario, kwargs in scenarios.items():
            retain = label == "full" and scenario == "base"
            result = run_route(
                engine,
                transfer,
                book,
                features,
                long_config,
                short_config,
                start=start,
                end=end,
                slippage=kwargs["slippage"],
                signal_lag=kwargs["signal_lag"],
                retain=retain,
            )
            output[label][scenario] = result.metrics
            rows.append(
                {
                    "window": label,
                    "scenario": scenario,
                    **result.metrics,
                }
            )
            if retain:
                retained_full = result
        output[label]["buy_and_hold"] = buy_and_hold_window(
            engine,
            book,
            features,
            start=start,
            end=end,
        )
    if retained_full is None:
        raise RuntimeError("full retained result missing")
    return output, rows, retained_full


def component_audit(
    engine: Any,
    transfer: Any,
    book: Any,
    features: Any,
    long_config: Any | None,
    short_config: Any | None,
    *,
    validation_end: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    variants = (
        ("combined", long_config, short_config),
        ("long_only", long_config, None),
        ("short_only", None, short_config),
    )
    for variant, long_leg, short_leg in variants:
        if long_leg is None and short_leg is None:
            continue
        for window, start, end in (
            ("locked_evaluation", validation_end, book.count),
            ("full", 0, book.count),
        ):
            result = run_route(
                engine,
                transfer,
                book,
                features,
                long_leg,
                short_leg,
                start=start,
                end=end,
            )
            rows.append({"variant": variant, "window": window, **result.metrics})
    return rows


def phase_audit(
    engine: Any,
    transfer: Any,
    books: dict[int, Any],
    features_by_phase: dict[int, Any],
    long_config: Any | None,
    short_config: Any | None,
) -> list[dict[str, Any]]:
    common_start = max(book.ts[0] for book in books.values())
    common_end = min(book.terminal_ts for book in books.values())
    rows: list[dict[str, Any]] = []
    for phase, book in sorted(books.items()):
        start = int(book.ts.searchsorted(common_start, side="left"))
        timestamps = pd.DatetimeIndex([*book.ts, book.terminal_ts])
        end = int(timestamps.searchsorted(common_end, side="right") - 1)
        result = run_route(
            engine,
            transfer,
            book,
            features_by_phase[phase],
            long_config,
            short_config,
            start=start,
            end=end,
        )
        rows.append(
            {
                "phase_hours": phase,
                "common_start": common_start.isoformat(),
                "common_end": common_end.isoformat(),
                **result.metrics,
            }
        )
    return rows


def rolling_90d(
    engine: Any,
    transfer: Any,
    book: Any,
    features: Any,
    long_config: Any | None,
    short_config: Any | None,
) -> list[dict[str, Any]]:
    window_bars = 90 * 6
    step_bars = 30 * 6
    timestamps = pd.DatetimeIndex([*book.ts, book.terminal_ts])
    rows: list[dict[str, Any]] = []
    start = 0
    while start + window_bars <= book.count:
        end = start + window_bars
        result = run_route(
            engine,
            transfer,
            book,
            features,
            long_config,
            short_config,
            start=start,
            end=end,
        )
        rows.append(
            {
                "window_index": len(rows),
                "window_start": timestamps[start].isoformat(),
                "window_end": timestamps[end].isoformat(),
                **result.metrics,
            }
        )
        start += step_bars
    return rows


def relevant_neighborhood_fields(config: Any) -> dict[str, tuple[Any, ...]]:
    fields: dict[str, tuple[Any, ...]] = {
        "entry_mode": ENTRY_MODES,
        "slope_lookback": SLOPE_LOOKBACK,
        "slope_min_atr": SLOPE_MIN_ATR,
        "confirm_days": CONFIRM_BARS,
        "entry_buffer_atr": ENTRY_BUFFER_ATR,
        "exit_confirm_days": EXIT_CONFIRM_BARS,
        "exit_buffer_atr": EXIT_BUFFER_ATR,
        "slope_exit_lookback": SLOPE_EXIT_LOOKBACK,
        "hard_stop_atr": HARD_STOP_ATR,
        "trail_atr": TRAIL_ATR,
        "max_hold_days": MAX_HOLD_BARS,
        "cooldown_days": COOLDOWN_BARS,
    }
    if config.entry_mode in {"reclaim", "pullback_reclaim"}:
        fields["pullback_touch_atr"] = PULLBACK_TOUCH_ATR
    if config.entry_mode == "pullback_reclaim":
        fields["pullback_lookback"] = PULLBACK_LOOKBACK
    if config.entry_mode == "breakout":
        fields["breakout_lookback"] = BREAKOUT_LOOKBACK
    return fields


def neighborhood_audit(
    engine: Any,
    transfer: Any,
    book: Any,
    features: Any,
    long_config: Any | None,
    short_config: Any | None,
    *,
    validation_end: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for side_name, config in (
        ("long", long_config),
        ("short", short_config),
    ):
        if config is None:
            continue
        for field, options in relevant_neighborhood_fields(config).items():
            current = getattr(config, field)
            option_list = list(options)
            if field == "entry_mode":
                replacements = [value for value in option_list if value != current]
            else:
                position = option_list.index(current)
                replacements = option_list[
                    max(0, position - 1) : min(len(option_list), position + 2)
                ]
                replacements = [value for value in replacements if value != current]
            for value in replacements:
                variant = replace(config, **{field: value})
                long_leg = variant if config.side > 0 else long_config
                short_leg = variant if config.side < 0 else short_config
                full = run_route(
                    engine,
                    transfer,
                    book,
                    features,
                    long_leg,
                    short_leg,
                    start=0,
                    end=book.count,
                ).metrics
                locked = run_route(
                    engine,
                    transfer,
                    book,
                    features,
                    long_leg,
                    short_leg,
                    start=validation_end,
                    end=book.count,
                ).metrics
                rows.append(
                    {
                        "side": side_name,
                        "field": field,
                        "base_value": current,
                        "variant_value": value,
                        "full_return_pct": full["net_return_pct"],
                        "full_mdd_pct": full["max_drawdown_pct"],
                        "full_trades": full["closed_trades"],
                        "locked_return_pct": locked["net_return_pct"],
                        "locked_mdd_pct": locked["max_drawdown_pct"],
                        "locked_trades": locked["closed_trades"],
                    }
                )
    return rows


def phase_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    returns = np.asarray([row["net_return_pct"] for row in rows], dtype=float)
    native = float(rows[0]["net_return_pct"])
    non_native = returns[1:]
    ratio = (
        float(np.median(non_native) / native)
        if native > 0.0 and len(non_native)
        else math.nan
    )
    mean_abs = abs(float(np.mean(returns)))
    cv = (
        float(np.std(returns, ddof=1) / mean_abs)
        if len(returns) > 1 and mean_abs > 0.0
        else math.nan
    )
    return {
        "positive_phases": int((returns > 0.0).sum()),
        "phase_count": len(rows),
        "median_return_pct": float(np.median(returns)),
        "native_return_pct": native,
        "non_native_median_to_native_ratio": ratio,
        "return_cv": cv,
        "integer_hour_phase_pass": bool(
            np.median(returns) > 0.0
            and np.isfinite(ratio)
            and ratio >= 0.40
            and np.isfinite(cv)
            and cv < 0.75
        ),
        "half_hour_phase_gate": "incomplete: source resolution is 1h",
    }


def config_json(config: Any | None) -> str:
    return "" if config is None else json.dumps(asdict(config), sort_keys=True)


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: clean_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json(item) for item in value]
    if isinstance(value, np.generic):
        return clean_json(value.item())
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def export_search_frame(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.drop(columns=["selection_metrics"], errors="ignore").copy()
    for column in ("config", "long_config", "short_config"):
        if column in output:
            output[column] = output[column].map(config_json)
    return output


def write_outputs(
    *,
    args: argparse.Namespace,
    engine: Any,
    transfer: Any,
    base: Any,
    books: dict[int, Any],
    features_by_phase: dict[int, Any],
    development_end: int,
    validation_end: int,
    long_stage1: pd.DataFrame,
    short_stage1: pd.DataFrame,
    long_stable: pd.DataFrame,
    short_stable: pd.DataFrame,
    pairs: pd.DataFrame,
    selected: dict[str, Any],
) -> None:
    book = books[0]
    features = features_by_phase[0]
    long_config = selected.get("long_config")
    short_config = selected.get("short_config")
    audits, metric_rows, full_result = final_audit(
        engine,
        transfer,
        book,
        features,
        long_config,
        short_config,
        development_end=development_end,
        validation_end=validation_end,
    )
    components = component_audit(
        engine,
        transfer,
        book,
        features,
        long_config,
        short_config,
        validation_end=validation_end,
    )
    phases = phase_audit(
        engine,
        transfer,
        books,
        features_by_phase,
        long_config,
        short_config,
    )
    phase_result = phase_summary(phases)
    rolling = rolling_90d(
        engine,
        transfer,
        book,
        features,
        long_config,
        short_config,
    )
    recent = engine.recent_slices(full_result)
    neighborhood = neighborhood_audit(
        engine,
        transfer,
        book,
        features,
        long_config,
        short_config,
        validation_end=validation_end,
    )
    bootstrap = (
        base.bootstrap_trades(
            full_result.trades,
            samples=5_000,
            seed=args.seed + 99,
        )
        if full_result.trades
        else {"samples": 0, "reason": "no closed trades"}
    )
    locked = audits["locked_evaluation"]
    full = audits["full"]
    locked_excess_return_pct = (
        float(locked["base"]["net_return_pct"])
        - float(locked["buy_and_hold"]["net_return_pct"])
    )
    suitable = bool(
        selected["hard_pass"]
        and locked["base"]["equity_multiple"] > 1.0
        and locked["stress_8bps"]["equity_multiple"] > 1.0
        and locked["base"]["closed_trades"] >= 3
        and full["base"]["max_drawdown_pct"] >= -40.0
        and not full["base"]["bankrupt_intraday"]
        and locked_excess_return_pct > 0.0
        and phase_result["integer_hour_phase_pass"]
    )
    decision = {
        "selection_hard_pass": bool(selected["hard_pass"]),
        "locked_base_positive": locked["base"]["equity_multiple"] > 1.0,
        "locked_stress_positive": locked["stress_8bps"]["equity_multiple"] > 1.0,
        "locked_delay_positive": locked["delay_1bar"]["equity_multiple"] > 1.0,
        "locked_trade_count_sufficient": locked["base"]["closed_trades"] >= 3,
        "full_mdd_within_40pct": full["base"]["max_drawdown_pct"] >= -40.0,
        "locked_excess_return_pct": locked_excess_return_pct,
        "locked_excess_positive": locked_excess_return_pct > 0.0,
        "integer_hour_phase_pass": phase_result["integer_hour_phase_pass"],
        "half_hour_phase_gate": "incomplete",
        "neighborhood_gate": "reported without pre-frozen numeric threshold",
        "suitable_historical_candidate": suitable,
        "status": "explore / not promoted / not live-ready",
        "promotion_effect": "none",
    }
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": FAMILY,
        "branch": BRANCH,
        "status": "explore / not promoted / not live-ready",
        "contract": {
            "fixed_indicator": "SMA7 / ATR7 on 4h",
            "seed": args.seed,
            "samples_per_side": args.samples_per_side,
            "shortlist": args.shortlist,
            "pair_pool": args.pair_pool,
            "development_end_exclusive": DEVELOPMENT_END.isoformat(),
            "validation_end_exclusive": VALIDATION_END.isoformat(),
            "locked_evaluation_role": (
                "selection-isolated but researcher-exposed; not clean OOS"
            ),
            "fee_per_fill": engine.FEE,
            "base_slippage_per_fill": engine.BASE_SLIPPAGE,
            "stress_slippage_per_fill": engine.STRESS_SLIPPAGE,
            "execution": (
                "closed 4h signal -> next 4h open; 1h intrabar stop order; "
                "event-time funding"
            ),
        },
        "source_modules": {
            "engine": {
                "path": str(ENGINE_PATH.relative_to(ROOT)),
                "sha256": ENGINE_SHA256,
            },
            "four_hour_data_execution": {
                "path": str(TRANSFER_PATH.relative_to(ROOT)),
                "sha256": TRANSFER_SHA256,
            },
        },
        "data_quality": {str(key): value.quality for key, value in books.items()},
        "search_counts": {
            "long_stage1": len(long_stage1),
            "short_stage1": len(short_stage1),
            "long_stability": len(long_stable),
            "short_stability": len(short_stable),
            "pairs": len(pairs),
            "long_hard_pass": int(long_stable["hard_pass"].sum()),
            "short_hard_pass": int(short_stable["hard_pass"].sum()),
            "pair_hard_pass": int(pairs["hard_pass"].sum()),
        },
        "selected": {
            "route": selected["route"],
            "hard_pass": bool(selected["hard_pass"]),
            "robust_score": selected["robust_score"],
            "worst_log_equity": selected["worst_log_equity"],
            "median_log_equity": selected["median_log_equity"],
            "prefit_log_equity": selected["prefit_log_equity"],
            "long_config": (
                None if long_config is None else asdict(long_config)
            ),
            "short_config": (
                None if short_config is None else asdict(short_config)
            ),
            "selection_metrics": selected["selection_metrics"],
        },
        "audits": audits,
        "components": components,
        "phase_audit": phases,
        "phase_summary": phase_result,
        "rolling_90d": rolling,
        "recent_slices": recent,
        "neighborhood": neighborhood,
        "trade_bootstrap": bootstrap,
        "decision": decision,
        "warning": (
            "All price history is researcher-exposed. Locked evaluation was "
            "not used for selection but is not clean prospective OOS."
        ),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = "hype_4h_ma7_native_trend"
    date = args.run_date
    summary_path = ARTIFACT_DIR / f"{stem}_summary_{date}.json"
    summary_path.write_text(
        json.dumps(
            clean_json(payload),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    frontier = pd.concat(
        [
            long_stable.head(args.shortlist),
            short_stable.head(args.shortlist),
        ],
        ignore_index=True,
    )
    export_search_frame(frontier).to_csv(
        ARTIFACT_DIR / f"{stem}_frontier_{date}.csv",
        index=False,
    )
    export_search_frame(pairs.head(200)).to_csv(
        ARTIFACT_DIR / f"{stem}_pairs_{date}.csv",
        index=False,
    )
    pd.DataFrame(metric_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_metrics_{date}.csv",
        index=False,
    )
    pd.DataFrame(components).to_csv(
        ARTIFACT_DIR / f"{stem}_components_{date}.csv",
        index=False,
    )
    pd.DataFrame(phases).to_csv(
        ARTIFACT_DIR / f"{stem}_phase_{date}.csv",
        index=False,
    )
    pd.DataFrame(rolling).to_csv(
        ARTIFACT_DIR / f"{stem}_rolling_90d_{date}.csv",
        index=False,
    )
    pd.DataFrame(recent).to_csv(
        ARTIFACT_DIR / f"{stem}_recent_{date}.csv",
        index=False,
    )
    pd.DataFrame(neighborhood).to_csv(
        ARTIFACT_DIR / f"{stem}_neighborhood_{date}.csv",
        index=False,
    )
    pd.DataFrame(full_result.trades).to_csv(
        ARTIFACT_DIR / f"{stem}_trades_{date}.csv",
        index=False,
    )
    pd.DataFrame(full_result.path).to_csv(
        ARTIFACT_DIR / f"{stem}_path_{date}.csv",
        index=False,
    )
    print(
        json.dumps(
            clean_json(
                {
                    "summary": str(summary_path.relative_to(ROOT)),
                    "search_counts": payload["search_counts"],
                    "selected": payload["selected"],
                    "locked_evaluation": locked,
                    "full": full,
                    "phase_summary": phase_result,
                    "decision": decision,
                }
            ),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        flush=True,
    )


def self_test(engine: Any) -> None:
    rng = random.Random(7)
    long_config = random_config(engine, 1, rng)
    short_config = random_config(engine, -1, rng)
    assert long_config.side == 1 and short_config.side == -1
    assert long_config.entry_mode in ENTRY_MODES
    assert short_config.entry_mode in ENTRY_MODES
    assert long_config.hard_stop_atr > 0.0
    assert short_config.hard_stop_atr > 0.0
    configs = unique_configs(engine, 1, rng, 100)
    assert len(configs) == 100
    assert len({item.key for item in configs}) == 100
    lower_weighted_higher_worst = {
        "hard_pass": True,
        "worst_log_equity": 0.20,
        "median_log_equity": 0.30,
        "prefit_log_equity": 0.40,
        "robust_score": 0.50,
        "prefit_return_pct": 10.0,
    }
    higher_weighted_lower_worst = {
        "hard_pass": True,
        "worst_log_equity": 0.10,
        "median_log_equity": 0.90,
        "prefit_log_equity": 1.00,
        "robust_score": 2.00,
        "prefit_return_pct": 100.0,
    }
    selected = select_route(
        pd.DataFrame([lower_weighted_higher_worst]),
        pd.DataFrame([higher_weighted_lower_worst]),
        pd.DataFrame(),
    )
    assert selected["worst_log_equity"] == 0.20
    print("self-test: PASS")


def main() -> None:
    args = parse_args()
    engine = load_module(ENGINE_PATH, ENGINE_SHA256, "hype_4h_native_engine")
    if args.self_test:
        self_test(engine)
        return
    transfer = load_module(
        TRANSFER_PATH,
        TRANSFER_SHA256,
        "hype_4h_native_transfer",
    )
    base = transfer.load_module(
        transfer.BASE_PATH,
        transfer.BASE_SHA256,
        "hype_4h_native_base",
    )
    parent = base.load_parent()
    data_engine = parent.load_engine()
    hourly, hourly_quality = data_engine.audit_and_load_market(ROOT, "1h")
    funding, funding_quality = data_engine.load_and_audit_funding(ROOT)
    books = {
        phase: transfer.build_book(
            base,
            hourly,
            hourly_quality,
            funding_quality,
            phase_hours=phase,
        )
        for phase in PHASES
    }
    features_by_phase = {
        phase: transfer.build_features(engine, book, hourly, funding)
        for phase, book in books.items()
    }
    book = books[0]
    development_end = int(
        book.ts.searchsorted(DEVELOPMENT_END, side="left")
    )
    validation_end = int(
        book.ts.searchsorted(VALIDATION_END, side="left")
    )
    if (
        development_end <= 0
        or validation_end <= development_end
        or validation_end >= book.count
        or pd.Timestamp(book.ts[development_end]) != DEVELOPMENT_END
        or pd.Timestamp(book.ts[validation_end]) != VALIDATION_END
        or book.terminal_ts - VALIDATION_END < pd.Timedelta(days=90)
    ):
        raise RuntimeError("frozen time split unavailable")
    rng = random.Random(args.seed)
    long_configs = unique_configs(engine, 1, rng, args.samples_per_side)
    short_configs = unique_configs(engine, -1, rng, args.samples_per_side)
    features = features_by_phase[0]
    long_stage1 = stage1_search(
        engine,
        transfer,
        long_configs,
        book,
        features,
        development_end=development_end,
    )
    short_stage1 = stage1_search(
        engine,
        transfer,
        short_configs,
        book,
        features,
        development_end=development_end,
    )
    long_shortlist = list(long_stage1.head(args.shortlist)["config"])
    short_shortlist = list(short_stage1.head(args.shortlist)["config"])
    long_stable = stability_audit(
        engine,
        transfer,
        long_shortlist,
        book,
        features,
        development_end=development_end,
        validation_end=validation_end,
    )
    short_stable = stability_audit(
        engine,
        transfer,
        short_shortlist,
        book,
        features,
        development_end=development_end,
        validation_end=validation_end,
    )
    pairs = pair_search(
        engine,
        transfer,
        long_stable.head(args.pair_pool)["config"],
        short_stable.head(args.pair_pool)["config"],
        book,
        features,
        development_end=development_end,
        validation_end=validation_end,
    )
    selected = select_route(long_stable, short_stable, pairs)
    write_outputs(
        args=args,
        engine=engine,
        transfer=transfer,
        base=base,
        books=books,
        features_by_phase=features_by_phase,
        development_end=development_end,
        validation_end=validation_end,
        long_stage1=long_stage1,
        short_stage1=short_stage1,
        long_stable=long_stable,
        short_stable=short_stable,
        pairs=pairs,
        selected=selected,
    )


if __name__ == "__main__":
    main()
