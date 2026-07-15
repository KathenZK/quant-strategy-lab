#!/usr/bin/env python3
"""Verify V6 full-leg ablation and clean-surface microtune coverage.

This audit reads only retained artifacts whose research cutoff is before the
locked future OOS window. It does not load market data or modify the freeze.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FAMILY_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS = FAMILY_DIR / "artifacts"


def load(name: str) -> dict[str, Any]:
    path = ARTIFACTS / name
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def require_no_future_read(name: str, payload: dict[str, Any]) -> None:
    require(
        payload.get("future_oos_read") is False,
        f"{name} must explicitly record future_oos_read=false",
    )


def count(value: Any) -> int:
    """Accept artifacts that store either an explicit count or retained rows."""
    return value if isinstance(value, int) else len(value)


def main() -> None:
    freeze = load("binance_as6s_v6_mark_joint_future_oos_freeze_2026-07-15.json")
    frontier_ablation = load("binance_as6s_v5_frontier_full_ablation_2026-07-15.json")
    clean_rsi_ablation = load("binance_as6s_v5_clean_rsi_full_ablation_2026-07-15.json")
    legacy_ablation = load("binance_as6s_v5_legacy_exact_full_ablation_2026-07-15.json")
    clean_surface = load("binance_as6s_v6_clean_surface_2026-07-15.json")
    frontier_tune = load("binance_as6s_v6_frontier_microtune_2026-07-15.json")
    clean_rsi_tune = load("binance_as6s_v6_clean_rsi_microtune_2026-07-15.json")
    legacy_tune = load("binance_as6s_v6_legacy_microtune_2026-07-15.json")
    final_audit = load(
        "binance_as6s_v6_mark_clean_rsi_joint_candidate_audit_2026-07-15.json"
    )

    historical_artifacts = {
        "frontier_ablation": frontier_ablation,
        "clean_rsi_ablation": clean_rsi_ablation,
        "legacy_ablation": legacy_ablation,
        "clean_surface": clean_surface,
        "frontier_tune": frontier_tune,
        "clean_rsi_tune": clean_rsi_tune,
        "legacy_tune": legacy_tune,
        "final_audit": final_audit,
    }
    for name, payload in historical_artifacts.items():
        require_no_future_read(name, payload)

    selected = set(freeze["selected_sleeves"])
    require(len(selected) == 15, "freeze must contain exactly 15 unique sleeves")

    frontier_sleeves = set(frontier_ablation["results"])
    clean_rsi_sleeves = {clean_rsi_ablation["sleeve"]}
    legacy_sleeves = set(legacy_ablation["results"])
    ablated = frontier_sleeves | clean_rsi_sleeves | legacy_sleeves
    require(len(frontier_sleeves) == 8, "frontier ablation must cover 8 sleeves")
    require(len(clean_rsi_sleeves) == 1, "clean-RSI ablation must cover 1 sleeve")
    require(len(legacy_sleeves) == 6, "legacy ablation must cover 6 sleeves")
    require(ablated == selected, "source full-ablation sleeves must equal frozen sleeves")

    for sleeve, row in frontier_ablation["results"].items():
        require("baseline" in row["variants"], f"{sleeve} lacks ablation baseline")
        require(len(row["variants"]) >= 15, f"{sleeve} has incomplete component variants")
        require(
            len(row["structural_not_removed"]) >= 2,
            f"{sleeve} must identify structural/risk fields not zeroed",
        )
    require(
        count(frontier_ablation["variant_evaluations"]) == 138,
        "frontier variant evaluation count drifted",
    )

    for sleeve, row in legacy_ablation["results"].items():
        require(
            len(row["parameter_groups"]) == 34,
            f"{sleeve} must classify all 34 legacy parameter groups",
        )
    require(
        count(legacy_ablation["parameter_groups"]) == 204,
        "legacy parameter-group count must be 6 x 34",
    )
    require(
        count(legacy_ablation["variant_evaluations"]) == 381,
        "legacy variant evaluation count drifted",
    )
    require(
        count(clean_rsi_ablation["variant_evaluations"]) == 10,
        "clean-RSI component evaluation count drifted",
    )

    clean_sleeves = set(clean_surface["sleeves"])
    require(clean_sleeves == selected, "clean surface must cover every frozen sleeve")
    require(clean_surface["summary"]["sleeves"] == 15, "clean surface count drifted")
    for sleeve, row in clean_surface["sleeves"].items():
        removed = set(row["remove_fields"])
        retained = set(row["retain_fields"])
        tunable = set(row["microtune_fields"])
        require(not removed & retained, f"{sleeve} has removed/retained overlap")
        require(tunable <= retained, f"{sleeve} tunes a field outside clean surface")

    tuned = (
        set(frontier_tune["results"])
        | {clean_rsi_tune["sleeve"]}
        | set(legacy_tune["results"])
    )
    require(tuned == selected, "microtune coverage must equal frozen sleeves")

    frontier_generated = sum(
        count(row["generated_candidates"]) for row in frontier_tune["results"].values()
    )
    legacy_generated = sum(
        count(row["generated_candidates"]) for row in legacy_tune["results"].values()
    )
    clean_rsi_generated = count(clean_rsi_tune["generated_candidates"])
    require(frontier_generated == 2400, "frontier microtune count drifted")
    require(legacy_generated == 1800, "legacy microtune count drifted")
    require(clean_rsi_generated == 500, "clean-RSI microtune count drifted")

    route_summary: dict[str, Any] = {}
    expected_routes = {"nonpreemptive", "strong_breakout_preemptive"}
    require(set(final_audit["results"]) == expected_routes, "final audit routes drifted")
    for route, row in final_audit["results"].items():
        drops = {item["sleeve"] for item in row["drop_ablation"]}
        substitutions = set(row["option_substitution_by_sleeve"])
        require(drops == selected, f"{route} drop ablation does not cover 15 sleeves")
        require(
            substitutions == selected,
            f"{route} option substitution does not cover 15 sleeves",
        )
        require(not row["dispensable_sleeves"], f"{route} still has a dispensable sleeve")
        require(len(row["scale_neighborhood"]) == 7, f"{route} scale neighborhood drifted")
        if route == "strong_breakout_preemptive":
            require(len(row["router_neighborhood"]) == 7, "preemptive router grid drifted")
        route_summary[route] = {
            "drop_ablation_sleeves": len(drops),
            "single_option_substitutions": len(row["option_substitution_neighborhood"]),
            "scale_neighbors": len(row["scale_neighborhood"]),
            "router_neighbors": len(row["router_neighborhood"]),
            "dispensable_sleeves": row["dispensable_sleeves"],
        }

    output = {
        "result": "PASS",
        "version": freeze["version"],
        "research_cutoff_exclusive": freeze["selection_end_exclusive"],
        "future_oos_read": False,
        "selected_sleeves": len(selected),
        "source_full_ablation": {
            "frontier_sleeves": len(frontier_sleeves),
            "frontier_variant_evaluations": count(frontier_ablation["variant_evaluations"]),
            "clean_rsi_sleeves": len(clean_rsi_sleeves),
            "clean_rsi_variant_evaluations": count(clean_rsi_ablation["variant_evaluations"]),
            "legacy_sleeves": len(legacy_sleeves),
            "legacy_parameter_groups": count(legacy_ablation["parameter_groups"]),
            "legacy_variant_evaluations": count(legacy_ablation["variant_evaluations"]),
        },
        "clean_surface": clean_surface["summary"],
        "microtune": {
            "frontier_candidates": frontier_generated,
            "clean_rsi_candidates": clean_rsi_generated,
            "legacy_candidates": legacy_generated,
            "total_candidates": frontier_generated + clean_rsi_generated + legacy_generated,
        },
        "final_account_audit": route_summary,
        "freeze_unchanged": True,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
