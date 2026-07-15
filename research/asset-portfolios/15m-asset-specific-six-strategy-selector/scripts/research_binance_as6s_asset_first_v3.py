from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timezone
import itertools
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import audit_binance_as6s_clean_rsi_hf_robustness as clean_audit
from as6s_engine import (
    BASE_SLIPPAGE,
    PREFIT_END,
    REUSED_END,
    STARTS,
    SYMBOLS,
    StrategyConfig,
    funding_arrays,
    load_funding,
    load_symbol_frame,
    select_nonoverlap,
    simulate_opportunities,
)
from combine_hybrid_asset_specific_account import (
    LEGACY_PATH,
    LEGACY_TRADES,
    UnifiedTrade,
    nonpreemptive,
    preemptive,
    strict_metrics,
)


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
FRONTIER_PATH = (
    FAMILY_DIR / "artifacts/binance_as6s_prefit_frontier_asset_first_2026-07-14.json"
)
CLEAN_DIR = FAMILY_DIR / "artifacts/per_asset_clean_rsi_hf_robustness"
OUTPUT = FAMILY_DIR / "artifacts/binance_as6s_asset_first_v3_candidate_2026-07-14.json"
TRADES_OUTPUT = (
    FAMILY_DIR / "artifacts/binance_as6s_asset_first_v3_candidate_trades_2026-07-14.csv"
)

RESEARCH_START = pd.Timestamp("2024-07-14T00:00:00Z")
ALL_SIX_ACTIVE_START = max(STARTS.values())
HISTORICAL_OOS_START = pd.Timestamp("2026-01-14T09:00:00Z")
CURRENT_3M_START = pd.Timestamp("2026-04-14T09:00:00Z")
SCENARIOS = ("base", "stress_8bps", "k_plus_2")
EXPOSURES = (0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0)
ACCOUNT_SCALES = (0.25, 0.33, 0.40, 0.50, 0.60, 0.75, 1.0, 1.25, 1.5)


def finite_pf(value: float) -> float:
    return min(float(value), 20.0)


def metric_with_frequency(
    trades: list[UnifiedTrade], start: pd.Timestamp, end: pd.Timestamp, scale: float
) -> dict[str, Any]:
    result = strict_metrics(trades, start, end, scale)
    days = max((end - start).total_seconds() / 86400.0, 1.0)
    return {**result, "trades_per_day": result["trades"] / days}


def sleeve_metrics(
    trades: list[UnifiedTrade], symbol: str, exposure: float
) -> dict[str, Any]:
    scaled = [replace(trade, exposure=exposure) for trade in trades]
    return {
        "prefit": metric_with_frequency(
            scaled, STARTS[symbol], PREFIT_END, 1.0
        ),
        "historical_oos": metric_with_frequency(
            scaled, HISTORICAL_OOS_START, PREFIT_END, 1.0
        ),
        "current_3m": metric_with_frequency(
            scaled, CURRENT_3M_START, REUSED_END, 1.0
        ),
        "through_current": metric_with_frequency(
            scaled, STARTS[symbol], REUSED_END, 1.0
        ),
    }


def choose_exposure(
    scenarios: dict[str, list[UnifiedTrade]], symbol: str
) -> tuple[float, dict[str, Any]]:
    audits: dict[float, dict[str, Any]] = {}
    for exposure in EXPOSURES:
        audits[exposure] = {
            scenario: sleeve_metrics(rows, symbol, exposure)
            for scenario, rows in scenarios.items()
        }
    valid = [
        exposure
        for exposure, audit in audits.items()
        if all(
            metrics_["through_current"]["total_return"] > 0.0
            and metrics_["through_current"]["max_dd"] > -0.20
            and metrics_["current_3m"]["total_return"] >= 0.0
            and metrics_["current_3m"]["max_dd"] > -0.20
            for metrics_ in audit.values()
        )
    ]
    candidates = valid or list(EXPOSURES)
    chosen = max(
        candidates,
        key=lambda exposure: (
            audits[exposure]["base"]["through_current"]["total_return"],
            audits[exposure]["base"]["current_3m"]["total_return"],
        ),
    )
    return chosen, audits[chosen]


def quality_from_metrics(audit: dict[str, Any]) -> float:
    base = audit["base"]["through_current"]
    recent = audit["base"]["current_3m"]
    stress = audit["stress_8bps"]["through_current"]
    delayed = audit["k_plus_2"]["through_current"]
    return float(
        0.9 * math.log(max(base["annual_multiple"], 1e-9))
        + 0.5 * math.log(max(recent["annual_multiple"], 1e-9))
        + 2.0 * base["win_rate"]
        + 0.8 * recent["win_rate"]
        + 0.4 * math.log(max(finite_pf(base["profit_factor"]), 1e-9))
        + 0.3 * math.log(max(stress["annual_multiple"], 1e-9))
        + 0.2 * math.log(max(delayed["annual_multiple"], 1e-9))
        + 2.0 * min(
            base["max_dd"], stress["max_dd"], delayed["max_dd"]
        )
    )


def legacy_universe() -> tuple[dict[str, dict[str, list[UnifiedTrade]]], dict[str, Any]]:
    ledger = json.loads(LEGACY_PATH.read_text(encoding="utf-8"))
    frame = pd.read_csv(LEGACY_TRADES)
    frame["entry_ts"] = pd.to_datetime(frame["entry_ts"], utc=True)
    frame["exit_ts"] = pd.to_datetime(frame["exit_ts"], utc=True)
    selected_keys: list[str] = []
    for key, result in ledger["results"].items():
        base = result["base"]
        stress = result["stress_8bps"]
        current = base["reused"]
        if (
            base["through_reused"]["win_rate"] >= 0.80
            and base["through_reused"]["total_return"] > 0.0
            and base["through_reused"]["max_dd"] > -0.23
            and stress["through_reused"]["total_return"] > 0.0
            and stress["through_reused"]["max_dd"] > -0.23
            and (current["total_return"] >= 0.0 or current["trades"] < 3)
        ):
            selected_keys.append(key)

    universe: dict[str, dict[str, list[UnifiedTrade]]] = {}
    audit: dict[str, Any] = {}
    for key in selected_keys:
        asset, style = key.split(":", maxsplit=1)
        symbol = f"{asset}USDT"
        sleeve = f"legacy1h:{symbol}:{style}"
        rows = frame.loc[(frame["asset"] == asset) & (frame["style"] == style)]
        scenarios: dict[str, list[UnifiedTrade]] = {}
        for scenario in SCENARIOS:
            scenario_rows = rows.loc[rows["scenario"] == scenario]
            scenarios[scenario] = [
                UnifiedTrade(
                    sleeve=sleeve,
                    symbol=symbol,
                    mechanism=style,
                    source_timeframe="1h",
                    side=int(row.side),
                    entry_ts=row.entry_ts,
                    exit_ts=row.exit_ts,
                    entry_price=float(row.entry_price),
                    net_return_1x=float(row.net_ret_1x),
                    mae_return_1x=float(row.mae_1x),
                    raw_strength=0.0,
                    cooldown_hours=int(row.cooldown_bars),
                    strength=0.0,
                    exposure=float(row.exposure),
                    exit_reason=str(row.exit_reason),
                )
                for row in scenario_rows.itertuples()
            ]
        exposure = float(rows["exposure"].median())
        metrics_by_scenario = {
            scenario: sleeve_metrics(
                [replace(trade, exposure=1.0) for trade in trades],
                symbol,
                exposure,
            )
            for scenario, trades in scenarios.items()
        }
        quality = quality_from_metrics(metrics_by_scenario)
        universe[sleeve] = {
            scenario: [replace(trade, strength=quality) for trade in trades]
            for scenario, trades in scenarios.items()
        }
        audit[sleeve] = {
            "source": "legacy_asset_specific_1h",
            "symbol": symbol,
            "mechanism": style,
            "exposure": exposure,
            "quality_raw": quality,
            "metrics": metrics_by_scenario,
        }
    return universe, audit


def frontier_universe(
    frames: dict[str, pd.DataFrame], funding: dict[str, pd.DataFrame]
) -> tuple[dict[str, dict[str, list[UnifiedTrade]]], dict[str, Any]]:
    source = json.loads(FRONTIER_PATH.read_text(encoding="utf-8"))
    universe: dict[str, dict[str, list[UnifiedTrade]]] = {}
    audit: dict[str, Any] = {}
    for symbol in SYMBOLS:
        eligible = source["symbols"][symbol]["eligible_ranking"]
        chosen: dict[str, dict[str, Any]] = {}
        for row in eligible:
            chosen.setdefault(row["mechanism"], row)
        for mechanism, row in chosen.items():
            config = StrategyConfig.from_dict(row["config"])
            sleeve = f"frontier15m:{symbol}:{mechanism}:{config.config_id}"
            scenarios: dict[str, list[UnifiedTrade]] = {}
            for scenario, slippage, delay in (
                ("base", BASE_SLIPPAGE, 1),
                ("stress_8bps", 0.0008, 1),
                ("k_plus_2", BASE_SLIPPAGE, 2),
            ):
                opportunities = select_nonoverlap(
                    simulate_opportunities(
                        frames[symbol],
                        funding[symbol],
                        config,
                        end=REUSED_END,
                        slippage=slippage,
                        entry_delay_bars=delay,
                    ),
                    start=STARTS[symbol],
                    end=REUSED_END,
                )
                scenarios[scenario] = [
                    UnifiedTrade(
                        sleeve=sleeve,
                        symbol=symbol,
                        mechanism=mechanism,
                        source_timeframe="15m",
                        side=item.side,
                        entry_ts=item.entry_ts,
                        exit_ts=item.exit_ts,
                        entry_price=item.entry_fill,
                        net_return_1x=item.net_return_1x,
                        mae_return_1x=item.mae_return_1x,
                        raw_strength=item.score,
                        exit_reason=item.exit_reason,
                    )
                    for item in opportunities
                ]
            exposure, metrics_by_scenario = choose_exposure(scenarios, symbol)
            quality = quality_from_metrics(metrics_by_scenario)
            universe[sleeve] = {
                scenario: [
                    replace(
                        trade,
                        exposure=exposure,
                        strength=float(quality + 0.25 * trade.raw_strength),
                    )
                    for trade in rows
                ]
                for scenario, rows in scenarios.items()
            }
            audit[sleeve] = {
                "source": "prefit_frontier_asset_first",
                "symbol": symbol,
                "mechanism": mechanism,
                "config": config.to_dict(),
                "exposure": exposure,
                "quality_raw": quality,
                "metrics": metrics_by_scenario,
                "frontier_hard80": row["hard80"],
            }
    return universe, audit


def clean_rsi_universe(
    frames: dict[str, pd.DataFrame], funding: dict[str, pd.DataFrame]
) -> tuple[dict[str, dict[str, list[UnifiedTrade]]], dict[str, Any]]:
    universe: dict[str, dict[str, list[UnifiedTrade]]] = {}
    audit: dict[str, Any] = {}
    scenario_map = {
        "base": clean_audit.Scenario("base", 0.0004, 1),
        "stress_8bps": clean_audit.Scenario("stress_8bps", 0.0008, 1),
        "k_plus_2": clean_audit.Scenario("k_plus_2", 0.0004, 2),
    }
    for symbol in SYMBOLS:
        path = CLEAN_DIR / (
            f"{symbol.lower()}_clean_rsi_hf_robustness_2026-07-14.json"
        )
        if not path.exists():
            continue
        source = json.loads(path.read_text(encoding="utf-8"))
        candidates = source["portfolio_eligible"] or source["hard80"]
        if not candidates:
            continue
        # This sleeve is the account's frequency filler.  Single-sleeve win rate
        # may dip slightly below 80% in one diagnostic slice; the account-level
        # 80% gate remains hard, so select the robust candidate with the largest
        # usable signal cadence rather than another low-frequency quality maximum.
        candidate = max(
            candidates,
            key=lambda row: row["base_4bps_k1"]["through_current"][
                "trades_per_day"
            ],
        )
        config = clean_audit.Config(**candidate["config"])
        sleeve = f"cleanrsi15m:{symbol}:{config.signal.name}:{config.exit.name}"
        raw = frames[symbol][["ts", "open", "high", "low", "close", "volume"]]
        features = clean_audit.evolution.add_rsi_features(
            clean_audit.evolution.add_features(raw, [])
        )
        market = clean_audit.mii.build_market_arrays(features)
        state = clean_audit.mii.signal_state(features, config.signal)
        funding_times, funding_prefix = funding_arrays(funding[symbol])
        scenarios: dict[str, list[UnifiedTrade]] = {}
        for scenario_name, scenario in scenario_map.items():
            raw_trades = clean_audit.robust_trades(
                market,
                state,
                config.exit,
                funding_times,
                funding_prefix,
                slippage=scenario.slippage,
                entry_delay_bars=scenario.entry_delay_bars,
            )
            selected = clean_audit.select_nonoverlap(raw_trades, config.filter)
            scenarios[scenario_name] = [
                UnifiedTrade(
                    sleeve=sleeve,
                    symbol=symbol,
                    mechanism="clean_rsi_reversal",
                    source_timeframe="15m",
                    side=trade.direction,
                    entry_ts=trade.entry_ts,
                    exit_ts=trade.exit_ts,
                    entry_price=trade.entry_price,
                    net_return_1x=trade.raw_return,
                    mae_return_1x=trade.min_path_return,
                    raw_strength=0.0,
                    exit_reason=trade.exit_reason,
                )
                for trade in selected
            ]
        exposure, metrics_by_scenario = choose_exposure(scenarios, symbol)
        quality = quality_from_metrics(metrics_by_scenario)
        universe[sleeve] = {
            scenario: [
                replace(trade, exposure=exposure, strength=quality)
                for trade in rows
            ]
            for scenario, rows in scenarios.items()
        }
        audit[sleeve] = {
            "source": "asset_specific_clean_rsi_hf",
            "symbol": symbol,
            "mechanism": "clean_rsi_reversal",
            "config": asdict(config),
            "exposure": exposure,
            "quality_raw": quality,
            "metrics": metrics_by_scenario,
            "robust_hard80": candidate["hard80"],
        }
    return universe, audit


def normalize_strengths(
    universe: dict[str, dict[str, list[UnifiedTrade]]], audit: dict[str, Any]
) -> dict[str, dict[str, list[UnifiedTrade]]]:
    values = np.array([row["quality_raw"] for row in audit.values()], dtype=float)
    low = float(np.quantile(values, 0.05))
    high = float(np.quantile(values, 0.95))
    width = max(high - low, 1e-9)
    output: dict[str, dict[str, list[UnifiedTrade]]] = {}
    for sleeve, scenarios in universe.items():
        normalized = float(
            np.clip((audit[sleeve]["quality_raw"] - low) / width, 0.0, 1.0)
        )
        audit[sleeve]["quality"] = normalized
        output[sleeve] = {
            scenario: [
                replace(
                    trade,
                    strength=float(
                        0.75 * normalized
                        + 0.25 * np.clip(trade.raw_strength, 0.0, 1.0)
                    ),
                )
                for trade in rows
            ]
            for scenario, rows in scenarios.items()
        }
    return output


def route(
    selected: tuple[str, ...],
    universe: dict[str, dict[str, list[UnifiedTrade]]],
    scenario: str,
) -> list[UnifiedTrade]:
    items = [trade for sleeve in selected for trade in universe[sleeve][scenario]]
    return nonpreemptive(items, start=RESEARCH_START, end=REUSED_END)


def route_score(
    full: dict[str, Any], recent: dict[str, Any], symbol_count: int
) -> float:
    frequency = recent["trades_per_day"]
    return float(
        2.8 * math.log(max(1.0 + full["total_return"], 1e-9))
        + 1.8 * math.log(max(1.0 + recent["total_return"], 1e-9))
        + 2.5 * full["win_rate"]
        + 1.8 * recent["win_rate"]
        + 1.5 * full["max_dd"]
        + 1.0 * recent["max_dd"]
        + 0.15 * math.log1p(full["trades"])
        + 0.08 * symbol_count
        + 30.0 * min(0.0, full["win_rate"] - 0.80)
        + 20.0 * min(0.0, recent["win_rate"] - 0.80)
        + 18.0 * min(0.0, full["max_dd"] + 0.20)
        + 12.0 * min(0.0, recent["max_dd"] + 0.20)
        + 5.0 * min(0.0, frequency - 0.75)
        + 2.0 * min(0.0, 2.25 - frequency)
    )


def search_subsets(
    universe: dict[str, dict[str, list[UnifiedTrade]]],
    audit: dict[str, Any],
    *,
    beam_width: int = 60,
) -> tuple[tuple[str, ...], list[dict[str, Any]]]:
    sleeves = tuple(sorted(universe))
    cache: dict[tuple[str, ...], dict[str, Any]] = {}

    def evaluate(selected: tuple[str, ...]) -> dict[str, Any]:
        selected = tuple(sorted(selected))
        if selected not in cache:
            scenario_metrics: dict[str, Any] = {}
            for scenario in SCENARIOS:
                trades = route(selected, universe, scenario)
                scenario_metrics[scenario] = {
                    "full": metric_with_frequency(
                        trades, RESEARCH_START, REUSED_END, 1.0
                    ),
                    "current_3m": metric_with_frequency(
                        trades, CURRENT_3M_START, REUSED_END, 1.0
                    ),
                }
            full = scenario_metrics["base"]["full"]
            recent = scenario_metrics["base"]["current_3m"]
            symbol_count = len({audit[sleeve]["symbol"] for sleeve in selected})
            robustness_penalty = sum(
                24.0 * min(0.0, value["full"]["win_rate"] - 0.80)
                + 16.0 * min(0.0, value["current_3m"]["win_rate"] - 0.80)
                + 20.0 * min(0.0, value["full"]["max_dd"] + 0.20)
                + 14.0 * min(0.0, value["current_3m"]["max_dd"] + 0.20)
                + 8.0 * min(0.0, value["full"]["total_return"])
                + 6.0 * min(0.0, value["current_3m"]["total_return"])
                for value in scenario_metrics.values()
            )
            robust_return = sum(
                0.45 * math.log(max(1.0 + value["full"]["total_return"], 1e-9))
                + 0.25
                * math.log(max(1.0 + value["current_3m"]["total_return"], 1e-9))
                for value in scenario_metrics.values()
            )
            cache[selected] = {
                "selected": selected,
                "full": full,
                "current_3m": recent,
                "scenarios": scenario_metrics,
                "symbol_count": symbol_count,
                "score": (
                    route_score(full, recent, symbol_count)
                    + robust_return
                    + robustness_penalty
                ),
            }
        return cache[selected]

    beam: list[tuple[str, ...]] = [tuple()]
    frontier: list[dict[str, Any]] = []
    for _depth in range(1, len(sleeves) + 1):
        proposals = {
            tuple(sorted((*selected, sleeve)))
            for selected in beam
            for sleeve in sleeves
            if sleeve not in selected
        }
        evaluated = [evaluate(selected) for selected in proposals]
        frontier.extend(evaluated)
        evaluated.sort(key=lambda row: row["score"], reverse=True)
        beam = [row["selected"] for row in evaluated[:beam_width]]
    frontier.sort(key=lambda row: row["score"], reverse=True)
    passing = [
        row
        for row in frontier
        if all(
            value["full"]["win_rate"] >= 0.80
            and value["current_3m"]["win_rate"] >= 0.80
            # Sleeve-level leverage is scaled only after route selection.  Keep
            # diversified high-cadence paths here and let the account scale
            # enforce the final 20% drawdown gate.
            and value["full"]["max_dd"] > -0.60
            and value["current_3m"]["max_dd"] > -0.60
            and value["full"]["total_return"] > 0.0
            and value["current_3m"]["total_return"] > 0.0
            for value in row["scenarios"].values()
        )
    ]
    full_frequency_target = [
        row
        for row in passing
        if row["scenarios"]["base"]["full"]["trades_per_day"] >= 0.75
    ]
    recent_frequency_target = [
        row
        for row in passing
        if row["scenarios"]["base"]["current_3m"]["trades_per_day"] >= 0.75
    ]
    chosen = (full_frequency_target or recent_frequency_target or passing or frontier)[0]
    return tuple(chosen["selected"]), frontier[:200]


def choose_account_scale(
    selected: tuple[str, ...],
    universe: dict[str, dict[str, list[UnifiedTrade]]],
) -> tuple[float, list[dict[str, Any]]]:
    max_exposure = max(
        trade.exposure
        for sleeve in selected
        for trade in universe[sleeve]["base"]
    )
    rows: list[dict[str, Any]] = []
    for scale in ACCOUNT_SCALES:
        if scale * max_exposure > 3.0 + 1e-12:
            continue
        scenarios: dict[str, Any] = {}
        for scenario in SCENARIOS:
            trades = route(selected, universe, scenario)
            scenarios[scenario] = {
                "full": metric_with_frequency(
                    trades, RESEARCH_START, REUSED_END, scale
                ),
                "current_3m": metric_with_frequency(
                    trades, CURRENT_3M_START, REUSED_END, scale
                ),
            }
        valid = all(
            value[window]["total_return"] > 0.0
            and value[window]["max_dd"] > -0.20
            and value[window]["win_rate"] >= 0.80
            for value in scenarios.values()
            for window in ("full", "current_3m")
        )
        rows.append({"scale": scale, "valid": valid, "scenarios": scenarios})
    valid_rows = [row for row in rows if row["valid"]]
    chosen = max(
        valid_rows or rows,
        key=lambda row: row["scenarios"]["base"]["full"]["annual_multiple"],
    )
    return float(chosen["scale"]), rows


def all_slices(
    trades: list[UnifiedTrade], scale: float
) -> dict[str, Any]:
    windows = {
        "1d": REUSED_END - pd.Timedelta(days=1),
        "7d": REUSED_END - pd.Timedelta(days=7),
        "1m": REUSED_END - pd.DateOffset(months=1),
        "3m": REUSED_END - pd.DateOffset(months=3),
        "6m": REUSED_END - pd.DateOffset(months=6),
        "1y": REUSED_END - pd.DateOffset(years=1),
        "historical_oos": HISTORICAL_OOS_START,
        "all_six_active": ALL_SIX_ACTIVE_START,
        "full": RESEARCH_START,
    }
    return {
        name: metric_with_frequency(trades, start, REUSED_END, scale)
        for name, start in windows.items()
    }


def main() -> None:
    frames = {symbol: load_symbol_frame(symbol, end=REUSED_END) for symbol in SYMBOLS}
    funding_frames = {
        symbol: load_funding(symbol, end=REUSED_END) for symbol in SYMBOLS
    }
    old, old_audit = legacy_universe()
    frontier, frontier_audit = frontier_universe(frames, funding_frames)
    clean, clean_metrics = clean_rsi_universe(frames, funding_frames)
    raw_universe = {**old, **frontier, **clean}
    sleeve_audit = {**old_audit, **frontier_audit, **clean_metrics}
    universe = normalize_strengths(raw_universe, sleeve_audit)
    selected, frontier_rows = search_subsets(universe, sleeve_audit)
    account_scale, scale_grid = choose_account_scale(selected, universe)

    bars = frames
    funding = {
        symbol: funding_arrays(frame) for symbol, frame in funding_frames.items()
    }
    base_items = [
        trade for sleeve in selected for trade in universe[sleeve]["base"]
    ]
    preemption_grid: list[dict[str, Any]] = []
    for threshold, margin, min_hold in itertools.product(
        (0.65, 0.75, 0.85), (0.05, 0.10, 0.20), (1, 2, 4, 8)
    ):
        trades = preemptive(
            base_items,
            start=RESEARCH_START,
            end=REUSED_END,
            threshold=threshold,
            margin=margin,
            min_hold_hours=min_hold,
            bars=bars,
            funding=funding,
            slippage=BASE_SLIPPAGE,
        )
        full = metric_with_frequency(
            trades, RESEARCH_START, REUSED_END, account_scale
        )
        recent = metric_with_frequency(
            trades, CURRENT_3M_START, REUSED_END, account_scale
        )
        preemption_grid.append(
            {
                "threshold": threshold,
                "margin": margin,
                "min_hold_hours": min_hold,
                "full": full,
                "current_3m": recent,
                "score": route_score(
                    full,
                    recent,
                    len({sleeve_audit[sleeve]["symbol"] for sleeve in selected}),
                ),
            }
        )
    passing_preempt = [
        row
        for row in preemption_grid
        if row["full"]["win_rate"] >= 0.80
        and row["current_3m"]["win_rate"] >= 0.80
        and row["full"]["max_dd"] > -0.20
        and row["current_3m"]["max_dd"] > -0.20
    ]
    frozen_preemption = max(
        passing_preempt or preemption_grid, key=lambda row: row["score"]
    )
    max_selected_exposure = max(
        trade.exposure
        for sleeve in selected
        for trade in universe[sleeve]["base"]
    )
    preemptive_scale_grid: list[dict[str, Any]] = []
    for scale in ACCOUNT_SCALES:
        if scale * max_selected_exposure > 3.0 + 1e-12:
            continue
        scenario_metrics: dict[str, Any] = {}
        for scenario in SCENARIOS:
            items = [
                trade for sleeve in selected for trade in universe[sleeve][scenario]
            ]
            trades = preemptive(
                items,
                start=RESEARCH_START,
                end=REUSED_END,
                threshold=frozen_preemption["threshold"],
                margin=frozen_preemption["margin"],
                min_hold_hours=frozen_preemption["min_hold_hours"],
                bars=bars,
                funding=funding,
                slippage=0.0008 if scenario == "stress_8bps" else BASE_SLIPPAGE,
            )
            scenario_metrics[scenario] = {
                "full": metric_with_frequency(
                    trades, RESEARCH_START, REUSED_END, scale
                ),
                "current_3m": metric_with_frequency(
                    trades, CURRENT_3M_START, REUSED_END, scale
                ),
            }
        valid = all(
            value[window]["total_return"] > 0.0
            and value[window]["max_dd"] > -0.20
            and value[window]["win_rate"] >= 0.80
            for value in scenario_metrics.values()
            for window in ("full", "current_3m")
        )
        preemptive_scale_grid.append(
            {"scale": scale, "valid": valid, "scenarios": scenario_metrics}
        )
    valid_preemptive_scales = [
        row for row in preemptive_scale_grid if row["valid"]
    ]
    preemptive_account_scale = float(
        max(
            valid_preemptive_scales or preemptive_scale_grid,
            key=lambda row: row["scenarios"]["base"]["full"][
                "annual_multiple"
            ],
        )["scale"]
    )

    comparisons: dict[str, Any] = {}
    output_trades: list[dict[str, Any]] = []
    for mode in ("nonpreemptive", "strong_breakout_preemptive"):
        comparisons[mode] = {"scenarios": {}}
        mode_scale = (
            account_scale
            if mode == "nonpreemptive"
            else preemptive_account_scale
        )
        for scenario in SCENARIOS:
            items = [
                trade for sleeve in selected for trade in universe[sleeve][scenario]
            ]
            if mode == "nonpreemptive":
                trades = nonpreemptive(
                    items, start=RESEARCH_START, end=REUSED_END
                )
            else:
                trades = preemptive(
                    items,
                    start=RESEARCH_START,
                    end=REUSED_END,
                    threshold=frozen_preemption["threshold"],
                    margin=frozen_preemption["margin"],
                    min_hold_hours=frozen_preemption["min_hold_hours"],
                    bars=bars,
                    funding=funding,
                    slippage=0.0008 if scenario == "stress_8bps" else BASE_SLIPPAGE,
                )
            comparisons[mode]["scenarios"][scenario] = all_slices(
                trades, mode_scale
            )
            if scenario == "base":
                output_trades.extend(
                    {
                        "mode": mode,
                        "scenario": scenario,
                        "account_scale": mode_scale,
                        **asdict(trade),
                    }
                    for trade in trades
                )
    comparisons["nonpreemptive"]["frozen_params"] = {
        "account_scale": account_scale
    }
    comparisons["strong_breakout_preemptive"]["frozen_params"] = {
        "account_scale": preemptive_account_scale,
        "threshold": frozen_preemption["threshold"],
        "margin": frozen_preemption["margin"],
        "min_hold_hours": frozen_preemption["min_hold_hours"],
    }

    diagnostic_gates: dict[str, Any] = {}
    for mode, comparison in comparisons.items():
        base = comparison["scenarios"]["base"]
        stress = comparison["scenarios"]["stress_8bps"]
        delayed = comparison["scenarios"]["k_plus_2"]
        checks = {
            "full_win_rate_ge_80pct": base["full"]["win_rate"] >= 0.80,
            "current_3m_win_rate_ge_80pct": base["3m"]["win_rate"] >= 0.80,
            "full_max_dd_lt_20pct": base["full"]["max_dd"] > -0.20,
            "current_3m_max_dd_lt_20pct": base["3m"]["max_dd"] > -0.20,
            "stress_full_positive_dd_lt_20pct": (
                stress["full"]["total_return"] > 0.0
                and stress["full"]["max_dd"] > -0.20
            ),
            "k_plus_2_full_positive_dd_lt_20pct": (
                delayed["full"]["total_return"] > 0.0
                and delayed["full"]["max_dd"] > -0.20
            ),
            "frequency_target_0_75_to_2_25_per_day": (
                0.75 <= base["all_six_active"]["trades_per_day"] <= 2.25
            ),
        }
        diagnostic_gates[mode] = {
            "checks": checks,
            "current_diagnostic_pass": all(checks.values()),
            "final_future_oos_pass": None,
            "final_future_oos_reason": (
                "future [2026-07-14T09:00Z, 2026-10-14T09:00Z) data unavailable"
            ),
        }

    pd.DataFrame(output_trades).to_csv(TRADES_OUTPUT, index=False)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "family": "Binance-15M-Asset-Specific-Six-Strategy-Selector",
        "stage": "asset_first_v3_diagnostic_not_registered_not_live_ready",
        "research_route": (
            "qualify asset-specific sleeves first, then search a global single-position "
            "subset; compare nonpreemptive and strong-breakout preemptive routing"
        ),
        "future_final_oos": {
            "start": REUSED_END.isoformat(),
            "end": "2026-10-14T09:00:00+00:00",
            "status": "locked_unavailable",
        },
        "candidate_sleeves": list(universe),
        "selected_sleeves": list(selected),
        "sleeve_audit": sleeve_audit,
        "subset_frontier": frontier_rows,
        "account_scale_grid": scale_grid,
        "preemption_grid": preemption_grid,
        "preemptive_account_scale_grid": preemptive_scale_grid,
        "comparisons": comparisons,
        "diagnostic_gates": diagnostic_gates,
        "trades_csv": str(TRADES_OUTPUT.relative_to(ROOT)),
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(OUTPUT),
                "candidate_sleeves": len(universe),
                "selected_sleeves": len(selected),
                "account_scale": account_scale,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
