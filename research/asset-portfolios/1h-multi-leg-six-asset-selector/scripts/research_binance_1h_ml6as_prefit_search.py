from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import random
from typing import Any

import pandas as pd

from ml6as_engine import (
    BASE_SLIPPAGE,
    OOS_START,
    RESEARCH_START,
    SYMBOLS,
    TRAIN_END,
    Arm,
    RouteConfig,
    StrategyConfig,
    candidate_score,
    load_funding,
    load_symbol_frame,
    opportunity_metrics,
    portfolio_metrics,
    portfolio_score,
    random_config,
    replay_portfolio,
    simulate_opportunities,
)


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1h-multi-leg-six-asset-selector"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
ARMS: tuple[Arm, ...] = ("trend_pullback", "breakout", "mean_reversion")
SEED_BASE = 2026071401


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials-per-arm", type=int, default=4000)
    parser.add_argument("--keep-per-cell", type=int, default=8)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--reuse-cells", action="store_true")
    return parser.parse_args()


def _retain(rows: list[dict[str, Any]], row: dict[str, Any], keep: int) -> None:
    rows.append(row)
    rows.sort(key=lambda value: value["score"], reverse=True)
    del rows[keep:]


def search_symbol(
    symbol: str, *, trials_per_arm: int, keep_per_cell: int
) -> dict[str, list[dict[str, Any]]]:
    frame = load_symbol_frame(symbol, end=OOS_START)
    funding = load_funding(symbol, end=OOS_START)
    output: dict[str, list[dict[str, Any]]] = {}
    for arm_index, arm in enumerate(ARMS):
        seed = SEED_BASE + SYMBOLS.index(symbol) * 10_000_000 + arm_index * 1_000_000
        rng = random.Random(seed)
        retained: list[dict[str, Any]] = []
        positive = 0
        for index in range(trials_per_arm):
            cfg = random_config(symbol, arm, rng, index)
            opportunities = simulate_opportunities(
                frame, funding, cfg, end=OOS_START
            )
            train = opportunity_metrics(
                opportunities, start=RESEARCH_START, end=TRAIN_END
            )
            validation = opportunity_metrics(
                opportunities, start=TRAIN_END, end=OOS_START
            )
            prefit = opportunity_metrics(
                opportunities, start=RESEARCH_START, end=OOS_START
            )
            score = candidate_score(train, validation, prefit)
            if score <= -1e8:
                continue
            positive += 1
            row = {
                "score": score,
                "config": cfg.to_dict(),
                "train": train,
                "validation": validation,
                "prefit": prefit,
                "opportunities": len(opportunities),
            }
            _retain(retained, row, keep_per_cell)
        print(
            f"{symbol} {arm}: trials={trials_per_arm} viable={positive} "
            f"best={retained[0]['score'] if retained else None}",
            flush=True,
        )
        output[arm] = retained
    return output


def route_grid(route: str, occupancy: str) -> list[RouteConfig]:
    thresholds = (0.30, 0.40, 0.50, 0.60, 0.70)
    conflict_margins = (0.0,) if route == "independent" else (0.0, 0.05, 0.10, 0.20)
    if occupancy == "nonpreemptive":
        preempt_pairs = ((0.0, 0),)
    else:
        preempt_pairs = tuple(
            (margin, hold)
            for margin in (0.05, 0.10, 0.20, 0.30, 0.40)
            for hold in (2, 4, 8, 12, 24)
        )
    return [
        RouteConfig(
            route=route,
            occupancy=occupancy,
            entry_threshold=threshold,
            exposure=1.0,
            conflict_margin=conflict,
            preempt_margin=preempt_margin,
            min_hold_bars=min_hold,
        )
        for threshold in thresholds
        for conflict in conflict_margins
        for preempt_margin, min_hold in preempt_pairs
    ]


def optimize_route(
    opportunities: list[Any],
    *,
    route: str,
    occupancy: str,
    frames: dict[str, pd.DataFrame],
    fundings: dict[str, pd.DataFrame],
) -> dict[str, Any]:
    best: dict[str, Any] | None = None
    hard_hits = 0
    grid = route_grid(route, occupancy)
    exposures = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0)
    for index, route_cfg in enumerate(grid, start=1):
        base_trades = replay_portfolio(
            opportunities,
            route_cfg,
            frames=frames,
            fundings=fundings,
            start=RESEARCH_START,
            end=OOS_START,
        )
        for exposure in exposures:
            trades = [
                replace(
                    trade,
                    exposure=exposure,
                    net_return=trade.net_return * exposure,
                )
                for trade in base_trades
            ]
            train = portfolio_metrics(trades, start=RESEARCH_START, end=TRAIN_END)
            validation = portfolio_metrics(trades, start=TRAIN_END, end=OOS_START)
            prefit = portfolio_metrics(trades, start=RESEARCH_START, end=OOS_START)
            hard, score = portfolio_score(train, validation, prefit)
            actual_preemptive = bool(
                occupancy != "preemptive" or prefit["preemptions"] >= 5
            )
            hard = bool(hard and actual_preemptive)
            hard_hits += int(hard)
            sort_key = (
                int(hard),
                int(actual_preemptive),
                score,
                prefit["annual_multiple"],
                prefit["profit_factor"],
            )
            row = {
                "route_config": replace(route_cfg, exposure=exposure).to_dict(),
                "hard_prefit_pass": hard,
                "actual_preemptive_path": actual_preemptive,
                "score": score,
                "train": train,
                "validation": validation,
                "prefit": prefit,
                "sort_key": sort_key,
            }
            if best is None or sort_key > tuple(best["sort_key"]):
                best = row
        if index % 500 == 0:
            print(
                f"route={route}/{occupancy} progress={index}/{len(grid)} "
                f"hard_hits={hard_hits}",
                flush=True,
            )
    if best is None:
        raise RuntimeError(f"empty route grid: {route}/{occupancy}")
    best["grid_trials"] = len(grid) * len(exposures)
    best["hard_prefit_hits"] = hard_hits
    best.pop("sort_key", None)
    print(
        f"route={route}/{occupancy} hard_hits={hard_hits}/"
        f"{len(grid) * len(exposures)} "
        f"best_pass={best['hard_prefit_pass']} prefit={best['prefit']}",
        flush=True,
    )
    return best


def main() -> None:
    args = parse_args()
    if args.trials_per_arm <= 0 or args.keep_per_cell <= 0:
        raise ValueError("trial and retention counts must be positive")
    previous_output = ARTIFACT_DIR / "binance_1h_ml6as_prefit_search_2026-07-14.json"
    if args.reuse_cells:
        previous = json.loads(previous_output.read_text(encoding="utf-8"))
        search_results = previous["cell_search_results"]
        search_meta = previous["search"]
        print(f"reused cell search from {previous_output}", flush=True)
    else:
        search_results: dict[str, dict[str, list[dict[str, Any]]]] = {}
        with ProcessPoolExecutor(max_workers=min(args.workers, len(SYMBOLS))) as pool:
            futures = {
                pool.submit(
                    search_symbol,
                    symbol,
                    trials_per_arm=args.trials_per_arm,
                    keep_per_cell=args.keep_per_cell,
                ): symbol
                for symbol in SYMBOLS
            }
            for future in as_completed(futures):
                symbol = futures[future]
                search_results[symbol] = future.result()
                print(f"completed {symbol}", flush=True)
        search_meta = {
            "seed_base": SEED_BASE,
            "trials_per_arm": args.trials_per_arm,
            "cells": len(SYMBOLS) * len(ARMS),
            "total_strategy_trials": args.trials_per_arm * len(SYMBOLS) * len(ARMS),
            "keep_per_cell": args.keep_per_cell,
        }
    missing = [
        f"{symbol}/{arm}"
        for symbol in SYMBOLS
        for arm in ARMS
        if not search_results.get(symbol, {}).get(arm)
    ]
    if missing:
        raise RuntimeError(f"no viable configs for cells: {missing}")

    frames = {symbol: load_symbol_frame(symbol, end=OOS_START) for symbol in SYMBOLS}
    fundings = {symbol: load_funding(symbol, end=OOS_START) for symbol in SYMBOLS}
    selected_configs: list[StrategyConfig] = []
    all_opportunities: list[Any] = []
    for symbol in SYMBOLS:
        for arm in ARMS:
            selected_row = search_results[symbol][arm][0]
            cfg = StrategyConfig.from_dict(selected_row["config"])
            selected_configs.append(cfg)
            prefit = selected_row["prefit"]
            validation = selected_row["validation"]
            profitable = (
                prefit["total_return"] > 0.0
                and validation["total_return"] > 0.0
                and prefit["profit_factor"] > 1.0
            )
            quality = (
                min(
                    1.0,
                    0.30
                    + 0.35 * prefit["win_rate"]
                    + 0.20 * validation["win_rate"]
                    + 0.15 * min(prefit["profit_factor"] / 2.0, 1.0),
                )
                if profitable
                else 0.25
            )
            opportunities = simulate_opportunities(
                frames[symbol], fundings[symbol], cfg, end=OOS_START
            )
            all_opportunities.extend(
                replace(
                    opportunity,
                    score=min(1.0, 0.65 * opportunity.score + 0.35 * quality),
                )
                for opportunity in opportunities
            )
    variants: dict[str, Any] = {}
    for route in ("independent", "fused"):
        for occupancy in ("nonpreemptive", "preemptive"):
            key = f"{route}_{occupancy}"
            variants[key] = optimize_route(
                all_opportunities,
                route=route,
                occupancy=occupancy,
                frames=frames,
                fundings=fundings,
            )

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "family": "Binance-1H-Multi-Leg-Six-Asset-Selector",
        "stage": "prefit_only_oos_unread",
        "windows": {
            "research_start": RESEARCH_START.isoformat(),
            "train_end": TRAIN_END.isoformat(),
            "oos_start_locked": OOS_START.isoformat(),
        },
        "costs": {
            "fee_per_fill": 0.001,
            "slippage_per_fill": BASE_SLIPPAGE,
            "funding": "actual_binance_settlement_events",
        },
        "search": search_meta,
        "selected_configs": [cfg.to_dict() for cfg in selected_configs],
        "cell_search_results": search_results,
        "portfolio_variants": variants,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    output = ARTIFACT_DIR / "binance_1h_ml6as_prefit_search_2026-07-14.json"
    output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"wrote {output}", flush=True)


if __name__ == "__main__":
    main()
