from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import pandas as pd

from ml6as_engine import (
    FULL_END,
    OOS_START,
    RESEARCH_START,
    SYMBOLS,
    RouteConfig,
    StrategyConfig,
    load_funding,
    load_symbol_frame,
    portfolio_metrics,
    replay_portfolio,
    simulate_opportunities,
)
from research_binance_1h_ml6as_prefit_search import ARMS, route_grid
from research_binance_1h_ml6as_reveal_and_audit import hard_gate, quality_weight


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1h-multi-leg-six-asset-selector"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
PREFIT_PATH = ARTIFACT_DIR / "binance_1h_ml6as_prefit_search_2026-07-14.json"


def scored_opportunities(
    cfg: StrategyConfig,
    row: dict[str, Any],
    *,
    frames: dict[str, pd.DataFrame],
    fundings: dict[str, pd.DataFrame],
) -> list[Any]:
    weight = quality_weight(row)
    raw = simulate_opportunities(
        frames[cfg.symbol], fundings[cfg.symbol], cfg, end=FULL_END
    )
    return [
        replace(
            opportunity,
            score=min(1.0, 0.65 * opportunity.score + 0.35 * weight),
        )
        for opportunity in raw
    ]


def evaluate(
    opportunities: list[Any],
    route_cfg: RouteConfig,
    *,
    frames: dict[str, pd.DataFrame],
    fundings: dict[str, pd.DataFrame],
) -> dict[str, Any]:
    full_trades = replay_portfolio(
        opportunities,
        route_cfg,
        frames=frames,
        fundings=fundings,
        start=RESEARCH_START,
        end=FULL_END,
    )
    oos_trades = replay_portfolio(
        opportunities,
        route_cfg,
        frames=frames,
        fundings=fundings,
        start=OOS_START,
        end=FULL_END,
    )
    full = portfolio_metrics(full_trades, start=RESEARCH_START, end=FULL_END)
    oos = portfolio_metrics(oos_trades, start=OOS_START, end=FULL_END)
    return {
        "route_config": route_cfg.to_dict(),
        "full": full,
        "oos_flat_start": oos,
        "hard_gate": hard_gate(full, oos),
    }


def compact(row: dict[str, Any], label: str) -> dict[str, Any]:
    return {
        "label": label,
        "route": row["route_config"]["route"],
        "occupancy": row["route_config"]["occupancy"],
        "threshold": row["route_config"]["entry_threshold"],
        "exposure": row["route_config"]["exposure"],
        "conflict_margin": row["route_config"]["conflict_margin"],
        "preempt_margin": row["route_config"]["preempt_margin"],
        "min_hold_bars": row["route_config"]["min_hold_bars"],
        "full_trades": row["full"]["trades"],
        "full_win_rate": row["full"]["win_rate"],
        "full_return": row["full"]["total_return"],
        "full_max_dd": row["full"]["max_dd"],
        "oos_trades": row["oos_flat_start"]["trades"],
        "oos_win_rate": row["oos_flat_start"]["win_rate"],
        "oos_return": row["oos_flat_start"]["total_return"],
        "oos_max_dd": row["oos_flat_start"]["max_dd"],
        "preemptions": row["oos_flat_start"]["preemptions"],
        "hard_pass": row["hard_gate"]["all_pass"],
    }


def main() -> None:
    argparse.ArgumentParser(
        description=(
            "Run post-reveal BIN-1H-ML6AS failure-surface diagnostics. "
            "Outputs are never eligible for strategy selection."
        )
    ).parse_args()
    payload = json.loads(PREFIT_PATH.read_text(encoding="utf-8"))
    frames = {symbol: load_symbol_frame(symbol, end=FULL_END) for symbol in SYMBOLS}
    fundings = {symbol: load_funding(symbol, end=FULL_END) for symbol in SYMBOLS}

    selected_ids = {item["config_id"] for item in payload["selected_configs"]}
    opportunities_by_config: dict[str, list[Any]] = {}
    for symbol in SYMBOLS:
        for arm in ARMS:
            for row in payload["cell_search_results"][symbol][arm]:
                cfg = StrategyConfig.from_dict(row["config"])
                opportunities_by_config[cfg.config_id] = scored_opportunities(
                    cfg, row, frames=frames, fundings=fundings
                )
    selected_opportunities = [
        opportunity
        for config_id in selected_ids
        for opportunity in opportunities_by_config[config_id]
    ]

    ablations: dict[str, Any] = {}
    for variant, frozen in payload["portfolio_variants"].items():
        route_cfg = RouteConfig.from_dict(frozen["route_config"])
        variant_rows: dict[str, Any] = {}
        variant_rows["full"] = evaluate(
            selected_opportunities,
            route_cfg,
            frames=frames,
            fundings=fundings,
        )
        for symbol in SYMBOLS:
            subset = [item for item in selected_opportunities if item.symbol != symbol]
            variant_rows[f"without_{symbol}"] = evaluate(
                subset, route_cfg, frames=frames, fundings=fundings
            )
        for arm in ARMS:
            without = [item for item in selected_opportunities if item.arm != arm]
            only = [item for item in selected_opportunities if item.arm == arm]
            variant_rows[f"without_{arm}"] = evaluate(
                without, route_cfg, frames=frames, fundings=fundings
            )
            variant_rows[f"only_{arm}"] = evaluate(
                only, route_cfg, frames=frames, fundings=fundings
            )
        for exposure in (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0):
            variant_rows[f"exposure_{exposure:g}x"] = evaluate(
                selected_opportunities,
                replace(route_cfg, exposure=exposure),
                frames=frames,
                fundings=fundings,
            )
        ablations[variant] = variant_rows
        print(f"completed ablations {variant}", flush=True)

    surface_rows: list[dict[str, Any]] = []
    for route in ("independent", "fused"):
        for occupancy in ("nonpreemptive", "preemptive"):
            for base_cfg in route_grid(route, occupancy):
                for exposure in (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0):
                    route_cfg = replace(base_cfg, exposure=exposure)
                    row = evaluate(
                        selected_opportunities,
                        route_cfg,
                        frames=frames,
                        fundings=fundings,
                    )
                    surface_rows.append(compact(row, "frozen_route_surface"))
        print(f"completed route surface {route}", flush=True)

    local_rows: list[dict[str, Any]] = []
    baseline_cfg = RouteConfig.from_dict(
        payload["portfolio_variants"]["independent_nonpreemptive"]["route_config"]
    )
    for symbol in SYMBOLS:
        for arm in ARMS:
            rows = payload["cell_search_results"][symbol][arm]
            selected_cell_id = rows[0]["config"]["config_id"]
            for rank, candidate in enumerate(rows[1:], start=2):
                replacement_id = candidate["config"]["config_id"]
                ids = (selected_ids - {selected_cell_id}) | {replacement_id}
                opportunities = [
                    opportunity
                    for config_id in ids
                    for opportunity in opportunities_by_config[config_id]
                ]
                row = evaluate(
                    opportunities,
                    baseline_cfg,
                    frames=frames,
                    fundings=fundings,
                )
                local_rows.append(
                    {
                        **compact(row, f"{symbol}/{arm}/rank_{rank}"),
                        "replaced_config": selected_cell_id,
                        "replacement_config": replacement_id,
                    }
                )
        print(f"completed local perturbations {symbol}", flush=True)

    surface_frame = pd.DataFrame(surface_rows)
    local_frame = pd.DataFrame(local_rows)
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "post_reveal_diagnostic_not_eligible_for_selection",
        "ablation_variants": ablations,
        "route_surface": {
            "rows": len(surface_rows),
            "hard_passes": int(surface_frame["hard_pass"].sum()),
            "oos_win_ge_80": int((surface_frame["oos_win_rate"] >= 0.80).sum()),
            "oos_positive": int((surface_frame["oos_return"] > 0.0).sum()),
            "oos_dd_lt_20": int((surface_frame["oos_max_dd"] > -0.20).sum()),
            "best_oos_win_rate": float(surface_frame["oos_win_rate"].max()),
            "best_oos_return": float(surface_frame["oos_return"].max()),
        },
        "local_top8_perturbation": {
            "rows": len(local_rows),
            "hard_passes": int(local_frame["hard_pass"].sum()),
            "oos_win_ge_80": int((local_frame["oos_win_rate"] >= 0.80).sum()),
            "oos_positive": int((local_frame["oos_return"] > 0.0).sum()),
            "best_oos_win_rate": float(local_frame["oos_win_rate"].max()),
            "best_oos_return": float(local_frame["oos_return"].max()),
        },
    }
    output = ARTIFACT_DIR / "binance_1h_ml6as_failure_surface_2026-07-14.json"
    output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    surface_frame.to_csv(
        ARTIFACT_DIR / "binance_1h_ml6as_route_surface_2026-07-14.csv",
        index=False,
    )
    local_frame.to_csv(
        ARTIFACT_DIR / "binance_1h_ml6as_local_top8_perturbation_2026-07-14.csv",
        index=False,
    )
    print(json.dumps({key: result[key] for key in result if key != "ablation_variants"}, indent=2))


if __name__ == "__main__":
    main()
