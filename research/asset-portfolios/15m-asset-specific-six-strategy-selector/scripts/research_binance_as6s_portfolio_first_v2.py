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

from as6s_engine import (
    BASE_SLIPPAGE,
    REUSED_END,
    STARTS,
    funding_arrays,
    load_funding,
    load_symbol_frame,
)
from combine_hybrid_asset_specific_account import (
    LEGACY_PATH,
    REVEAL_PATH,
    UnifiedTrade,
    current_scenarios,
    legacy_scenarios,
    nonpreemptive,
    preemptive,
    single_sleeve_nonoverlap,
    strict_metrics,
)


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
OUTPUT = FAMILY_DIR / "artifacts/binance_as6s_portfolio_first_v2_candidate_2026-07-14.json"
TRADES_OUTPUT = FAMILY_DIR / "artifacts/binance_as6s_portfolio_first_v2_candidate_trades_2026-07-14.csv"

RESEARCH_START = pd.Timestamp("2024-07-14T00:00:00Z")
CURRENT_3M_START = pd.Timestamp("2026-04-14T09:00:00Z")
FUTURE_OOS_END = pd.Timestamp("2026-10-14T09:00:00Z")
SCENARIOS = ("base", "stress_8bps", "k_plus_2")
EXPOSURES = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0)
ACCOUNT_SCALES = (0.5, 0.75, 1.0)


def finite_pf(value: float) -> float:
    return 20.0 if math.isinf(value) else float(value)


def metric_utility(metric: dict[str, Any]) -> float:
    if metric["trades"] == 0:
        return -20.0
    return float(
        1.8 * math.log(max(1e-9, 1.0 + metric["total_return"]))
        + 0.75 * math.log(max(1e-6, finite_pf(metric["profit_factor"])))
        + 0.35 * metric["win_rate"]
        + 1.5 * metric["max_dd"]
        + 0.12 * math.log1p(metric["trades"])
    )


def choose_sleeve_exposure(
    scenarios: dict[str, list[UnifiedTrade]], start: pd.Timestamp
) -> tuple[float, dict[str, dict[str, Any]], bool]:
    audits: dict[float, dict[str, dict[str, Any]]] = {}
    for exposure in EXPOSURES:
        audits[exposure] = {
            scenario: strict_metrics(
                [replace(trade, exposure=exposure) for trade in single_sleeve_nonoverlap(rows)],
                start,
                REUSED_END,
            )
            for scenario, rows in scenarios.items()
        }
    valid = [
        exposure
        for exposure, metrics in audits.items()
        if metrics["base"]["total_return"] > 0.0
        and metrics["stress_8bps"]["total_return"] > 0.0
        and metrics["base"]["max_dd"] > -0.30
        and metrics["stress_8bps"]["max_dd"] > -0.30
        and metrics["k_plus_2"]["max_dd"] > -0.35
    ]
    if valid:
        chosen = max(valid, key=lambda exposure: metric_utility(audits[exposure]["base"]))
        return chosen, audits[chosen], True
    chosen = max(EXPOSURES, key=lambda exposure: metric_utility(audits[exposure]["base"]))
    return chosen, audits[chosen], False


def prepare_sleeves(
    all_sleeves: dict[str, dict[str, list[UnifiedTrade]]],
    starts: dict[str, pd.Timestamp],
) -> tuple[dict[str, dict[str, list[UnifiedTrade]]], dict[str, Any]]:
    raw_rows: list[dict[str, Any]] = []
    for sleeve, scenarios in all_sleeves.items():
        sample = next(iter(scenarios["base"]), None)
        symbol = sample.symbol if sample is not None else sleeve.split(":")[1]
        start = starts[symbol]
        exposure, through, exposure_robust = choose_sleeve_exposure(scenarios, start)
        recent = {
            scenario: strict_metrics(
                [replace(trade, exposure=exposure) for trade in single_sleeve_nonoverlap(rows)],
                CURRENT_3M_START,
                REUSED_END,
            )
            for scenario, rows in scenarios.items()
        }
        base = through["base"]
        eligible = (
            base["trades"] >= 8
            and base["total_return"] > 0.0
            and finite_pf(base["profit_factor"]) > 1.03
            and through["stress_8bps"]["total_return"] > 0.0
            and through["base"]["max_dd"] > -0.30
            and through["stress_8bps"]["max_dd"] > -0.30
        )
        robustness_count = sum(metric["total_return"] > 0.0 for metric in through.values())
        raw_quality = (
            0.58 * metric_utility(base)
            + 0.22 * metric_utility(through["stress_8bps"])
            + 0.10 * metric_utility(through["k_plus_2"])
            + 0.10 * metric_utility(recent["base"])
            + 0.10 * robustness_count
        )
        raw_rows.append(
            {
                "sleeve": sleeve,
                "symbol": symbol,
                "start": start,
                "exposure": exposure,
                "exposure_robust": exposure_robust,
                "eligible": eligible,
                "raw_quality": raw_quality,
                "through": through,
                "current_3m": recent,
            }
        )

    eligible_values = np.array(
        [row["raw_quality"] for row in raw_rows if row["eligible"]], dtype=float
    )
    if not len(eligible_values):
        raise RuntimeError("no positive-expectancy sleeve survived the relaxed sleeve gate")
    low = float(np.quantile(eligible_values, 0.05))
    high = float(np.quantile(eligible_values, 0.95))
    width = max(high - low, 1e-9)

    prepared: dict[str, dict[str, list[UnifiedTrade]]] = {}
    audit: dict[str, Any] = {}
    for row in raw_rows:
        quality = float(np.clip((row["raw_quality"] - low) / width, 0.0, 1.0))
        audit[row["sleeve"]] = {
            key: value for key, value in row.items() if key not in {"start", "raw_quality"}
        } | {"start": row["start"].isoformat(), "quality": quality}
        if not row["eligible"]:
            continue
        prepared[row["sleeve"]] = {
            scenario: [
                replace(
                    trade,
                    exposure=row["exposure"],
                    strength=float(0.70 * quality + 0.30 * (trade.raw_strength or quality)),
                )
                for trade in rows
            ]
            for scenario, rows in all_sleeves[row["sleeve"]].items()
        }
    return prepared, audit


def route_metrics(
    selected: tuple[str, ...],
    prepared: dict[str, dict[str, list[UnifiedTrade]]],
    *,
    scale: float,
    scenario: str = "base",
) -> tuple[list[UnifiedTrade], dict[str, Any], dict[str, Any]]:
    items = [trade for sleeve in selected for trade in prepared[sleeve][scenario]]
    trades = nonpreemptive(items, start=RESEARCH_START, end=REUSED_END)
    full = strict_metrics(trades, RESEARCH_START, REUSED_END, scale)
    recent = strict_metrics(trades, CURRENT_3M_START, REUSED_END, scale)
    return trades, full, recent


def portfolio_search_score(full: dict[str, Any], recent: dict[str, Any]) -> float:
    full_win_gap = min(0.0, full["win_rate"] - 0.80)
    recent_win_gap = min(0.0, recent["win_rate"] - 0.80)
    full_trade_gap = min(0.0, (full["trades"] - 200) / 200.0)
    recent_trade_gap = min(0.0, (recent["trades"] - 30) / 30.0)
    dd_gap = min(0.0, full["max_dd"] + 0.20)
    recent_dd_gap = min(0.0, recent["max_dd"] + 0.20)
    return float(
        3.2 * math.log(max(1e-9, 1.0 + full["total_return"]))
        + 1.4 * math.log(max(1e-9, 1.0 + recent["total_return"]))
        + 2.0 * full["win_rate"]
        + 1.2 * recent["win_rate"]
        + 1.2 * full["max_dd"]
        + 0.5 * recent["max_dd"]
        + 14.0 * full_win_gap
        + 8.0 * recent_win_gap
        + 4.0 * full_trade_gap
        + 2.0 * recent_trade_gap
        + 12.0 * dd_gap
        + 6.0 * recent_dd_gap
    )


def search_subsets(
    prepared: dict[str, dict[str, list[UnifiedTrade]]],
    *,
    beam_width: int = 36,
    max_depth: int = 18,
) -> tuple[list[dict[str, Any]], dict[tuple[str, ...], dict[str, Any]]]:
    sleeves = tuple(sorted(prepared))
    cache: dict[tuple[str, ...], dict[str, Any]] = {}

    def evaluate(selected: tuple[str, ...]) -> dict[str, Any]:
        selected = tuple(sorted(selected))
        if selected not in cache:
            _, full, recent = route_metrics(selected, prepared, scale=1.0)
            cache[selected] = {
                "selected": selected,
                "full": full,
                "current_3m": recent,
                "score": portfolio_search_score(full, recent),
            }
        return cache[selected]

    beam: list[tuple[str, ...]] = [tuple()]
    frontier: list[dict[str, Any]] = []
    for _depth in range(1, min(max_depth, len(sleeves)) + 1):
        proposals: set[tuple[str, ...]] = set()
        for selected in beam:
            for sleeve in sleeves:
                if sleeve not in selected:
                    proposals.add(tuple(sorted((*selected, sleeve))))
        evaluated = [evaluate(selected) for selected in proposals]
        frontier.extend(evaluated)
        evaluated.sort(key=lambda row: row["score"], reverse=True)
        beam = [row["selected"] for row in evaluated[:beam_width]]

    frontier.sort(key=lambda row: row["score"], reverse=True)
    return frontier, cache


def choose_account_scale(
    selected: tuple[str, ...], prepared: dict[str, dict[str, list[UnifiedTrade]]]
) -> tuple[float, list[dict[str, Any]]]:
    max_exposure = max(
        trade.exposure
        for sleeve in selected
        for trade in prepared[sleeve]["base"]
    )
    rows: list[dict[str, Any]] = []
    for scale in ACCOUNT_SCALES:
        if scale * max_exposure > 3.0 + 1e-12:
            continue
        metrics: dict[str, Any] = {}
        for scenario in SCENARIOS:
            _, full, recent = route_metrics(selected, prepared, scale=scale, scenario=scenario)
            metrics[scenario] = {"full": full, "current_3m": recent}
        base = metrics["base"]
        gate = (
            base["full"]["trades"] >= 200
            and base["full"]["win_rate"] >= 0.80
            and base["full"]["max_dd"] > -0.20
            and base["full"]["total_return"] > 0.0
            and base["current_3m"]["trades"] >= 30
            and base["current_3m"]["win_rate"] >= 0.80
            and base["current_3m"]["max_dd"] > -0.20
            and base["current_3m"]["total_return"] > 0.0
            and all(metrics[name]["full"]["total_return"] > 0.0 for name in SCENARIOS)
            and all(metrics[name]["full"]["max_dd"] > -0.20 for name in SCENARIOS)
        )
        rows.append({"scale": scale, "metrics": metrics, "diagnostic_gate": gate})
    valid = [row for row in rows if row["diagnostic_gate"]]
    chosen = max(
        valid or rows,
        key=lambda row: row["metrics"]["base"]["full"]["annual_multiple"],
    )
    return float(chosen["scale"]), rows


def standard_slices(trades: list[UnifiedTrade], scale: float) -> dict[str, Any]:
    starts = {
        "1d": REUSED_END - pd.Timedelta(days=1),
        "7d": REUSED_END - pd.Timedelta(days=7),
        "1m": REUSED_END - pd.DateOffset(months=1),
        "3m": REUSED_END - pd.DateOffset(months=3),
        "6m": REUSED_END - pd.DateOffset(months=6),
        "1y": REUSED_END - pd.DateOffset(years=1),
    }
    return {
        name: strict_metrics(trades, max(RESEARCH_START, start), REUSED_END, scale)
        for name, start in starts.items()
    }


def main() -> None:
    reveal = json.loads(REVEAL_PATH.read_text(encoding="utf-8"))
    legacy = json.loads(LEGACY_PATH.read_text(encoding="utf-8"))
    current, current_starts = current_scenarios(reveal)
    old, old_starts = legacy_scenarios(legacy)
    all_sleeves = {**current, **old}
    starts = {**current_starts, **old_starts}
    prepared, sleeve_audit = prepare_sleeves(all_sleeves, starts)

    frontier, _cache = search_subsets(prepared)
    diagnostic_candidates = [
        row
        for row in frontier
        if row["full"]["trades"] >= 200
        and row["full"]["win_rate"] >= 0.80
        and row["full"]["max_dd"] > -0.20
        and row["current_3m"]["trades"] >= 30
        and row["current_3m"]["win_rate"] >= 0.80
        and row["current_3m"]["max_dd"] > -0.20
    ]
    chosen_search = max(
        diagnostic_candidates or frontier,
        key=lambda row: (row["score"], row["full"]["annual_multiple"]),
    )
    selected = tuple(chosen_search["selected"])
    account_scale, scale_grid = choose_account_scale(selected, prepared)

    bars = {symbol: load_symbol_frame(symbol, end=REUSED_END) for symbol in STARTS}
    funding = {
        symbol: funding_arrays(load_funding(symbol, end=REUSED_END)) for symbol in STARTS
    }
    preemption_grid: list[dict[str, Any]] = []
    base_items = [trade for sleeve in selected for trade in prepared[sleeve]["base"]]
    for threshold, margin, hold in itertools.product(
        (0.70, 0.80, 0.90), (0.05, 0.10, 0.20), (2, 4, 8, 16)
    ):
        trades = preemptive(
            base_items,
            start=RESEARCH_START,
            end=REUSED_END,
            threshold=threshold,
            margin=margin,
            min_hold_hours=hold,
            bars=bars,
            funding=funding,
            slippage=BASE_SLIPPAGE,
        )
        full = strict_metrics(trades, RESEARCH_START, REUSED_END, account_scale)
        recent = strict_metrics(trades, CURRENT_3M_START, REUSED_END, account_scale)
        preemption_grid.append(
            {
                "threshold": threshold,
                "margin": margin,
                "min_hold_hours": hold,
                "full": full,
                "current_3m": recent,
                "score": portfolio_search_score(full, recent),
            }
        )
    frozen_preemption = max(preemption_grid, key=lambda row: row["score"])

    comparisons: dict[str, Any] = {}
    trade_rows: list[dict[str, Any]] = []
    for mode in ("nonpreemptive", "strong_breakout_preemptive"):
        scenario_results: dict[str, Any] = {}
        base_mode_trades: list[UnifiedTrade] = []
        for scenario in SCENARIOS:
            items = [trade for sleeve in selected for trade in prepared[sleeve][scenario]]
            if mode == "nonpreemptive":
                trades = nonpreemptive(items, start=RESEARCH_START, end=REUSED_END)
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
            scenario_results[scenario] = {
                "full": strict_metrics(trades, RESEARCH_START, REUSED_END, account_scale),
                "current_3m": strict_metrics(
                    trades, CURRENT_3M_START, REUSED_END, account_scale
                ),
            }
            if scenario == "base":
                base_mode_trades = trades
                trade_rows.extend(
                    {"mode": mode, "scenario": scenario, **asdict(trade)} for trade in trades
                )
        base = scenario_results["base"]
        checks = {
            "full_trades_ge_200": base["full"]["trades"] >= 200,
            "full_win_rate_ge_80pct": base["full"]["win_rate"] >= 0.80,
            "full_max_dd_lt_20pct": base["full"]["max_dd"] > -0.20,
            "full_return_positive": base["full"]["total_return"] > 0.0,
            "current_3m_trades_ge_30": base["current_3m"]["trades"] >= 30,
            "current_3m_win_rate_ge_80pct": base["current_3m"]["win_rate"] >= 0.80,
            "current_3m_max_dd_lt_20pct": base["current_3m"]["max_dd"] > -0.20,
            "current_3m_return_positive": base["current_3m"]["total_return"] > 0.0,
            "stress_positive_dd_lt_20pct": (
                scenario_results["stress_8bps"]["full"]["total_return"] > 0.0
                and scenario_results["stress_8bps"]["full"]["max_dd"] > -0.20
            ),
            "k_plus_2_positive_dd_lt_20pct": (
                scenario_results["k_plus_2"]["full"]["total_return"] > 0.0
                and scenario_results["k_plus_2"]["full"]["max_dd"] > -0.20
            ),
        }
        comparisons[mode] = {
            "scenarios": scenario_results,
            "recent_slices": standard_slices(base_mode_trades, account_scale),
            "checks": checks,
            "current_diagnostic_pass": all(checks.values()),
            "final_future_oos_pass": None,
        }

    pd.DataFrame(trade_rows).to_csv(TRADES_OUTPUT, index=False)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "family": "Binance-15M-Asset-Specific-Six-Strategy-Selector",
        "candidate_label": "portfolio-first-v2-observation",
        "status": "explore; not registered; not promoted; not live-ready",
        "research_rule": (
            "individual sleeves have no win-rate floor; final account win rate must be >=80%"
        ),
        "research_window": [RESEARCH_START.isoformat(), REUSED_END.isoformat()],
        "current_3m_role": "research diagnostic and optimization; not final OOS",
        "future_oos": {
            "window": [REUSED_END.isoformat(), FUTURE_OOS_END.isoformat()],
            "status": "locked and unavailable",
        },
        "costs": {
            "fee_per_fill": 0.001,
            "base_slippage_per_fill": 0.0004,
            "stress_slippage_per_fill": 0.0008,
        },
        "source_sleeves": len(all_sleeves),
        "eligible_sleeves": len(prepared),
        "selected_sleeves": list(selected),
        "account_scale": account_scale,
        "max_effective_exposure": max(
            account_scale * trade.exposure
            for sleeve in selected
            for trade in prepared[sleeve]["base"]
        ),
        "sleeve_audit": sleeve_audit,
        "search": {
            "method": "beam forward subset search on account-level metrics",
            "beam_width": 36,
            "max_depth": 18,
            "evaluated_subsets": len(_cache),
            "diagnostic_gate_subsets": len(diagnostic_candidates),
            "chosen_search_row": chosen_search,
            "scale_grid": scale_grid,
            "frozen_preemption": frozen_preemption,
        },
        "comparisons": comparisons,
        "trades_csv": str(TRADES_OUTPUT.relative_to(ROOT)),
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(OUTPUT),
                "source_sleeves": len(all_sleeves),
                "eligible_sleeves": len(prepared),
                "selected_sleeves": len(selected),
                "evaluated_subsets": len(_cache),
                "diagnostic_gate_subsets": len(diagnostic_candidates),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
