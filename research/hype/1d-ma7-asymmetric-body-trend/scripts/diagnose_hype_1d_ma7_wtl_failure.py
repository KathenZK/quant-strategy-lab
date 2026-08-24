"""Post-fail D+V-only causal ablation for the locked WTL Stage-C result."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
PREFIX = FAMILY_DIR / "artifacts/hype_1d_ma7_wide_trend_lifecycle_2026-08-10"
STAGE_C_PATH = Path(f"{PREFIX}_stage_c.json")
OUTPUT_PATH = Path(f"{PREFIX}_post_fail_ablation.json")
ORCHESTRATOR_PATH = SCRIPT_DIR / "research_hype_1d_ma7_wide_trend_lifecycle.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def module_flags(config: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        name
        for name, enabled in (
            ("entry", config["entry"]["kind"] != "off"),
            ("long_exit", config["long_exit"]["mode"] != "off"),
            ("short_exit", config["short_exit"]["mode"] != "off"),
            ("short_rsi", int(config["short_rsi"]["days"]) > 0),
        )
        if enabled
    )


def config_key(config: dict[str, Any], *, off_module: str | None = None) -> str:
    row = {
        "entry": config["entry"],
        "long_exit": config["long_exit"],
        "short_exit": config["short_exit"],
        "short_rsi": config["short_rsi"],
    }
    if off_module == "entry":
        row["entry"] = {"kind": "off", "scope": "both", "lookback": 0, "threshold": 0.0}
    elif off_module in {"long_exit", "short_exit"}:
        row[off_module] = {"mode": "off", "activation_atr": 0.0, "giveback": 0.0, "confirm_days": 0}
    elif off_module == "short_rsi":
        row["short_rsi"] = {"threshold": 0.0, "days": 0}
    return json.dumps(row, sort_keys=True, separators=(",", ":"))


def strict_except_v_floor(row: dict[str, Any]) -> bool:
    checks = row["prepass_gate"]["checks"]
    return all(value for key, value in checks.items() if key != "V_candidate_floor")


def representative_key(row: dict[str, Any]) -> tuple[Any, ...]:
    domains = row["prepass_gate"]["domains"]
    return (
        -min(domains[label]["comparison"]["return_delta_pp"] for label in ("D", "V")),
        -min(domains[label]["comparison"]["chronological_mdd_delta_pp"] for label in ("D", "V")),
        len(module_flags(row["config"])),
        row["arm_id"],
    )


def compact_run(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": run["status"],
        "arm_id": run["arm_id"],
        "metrics": run.get("metrics"),
        "activation_counts": run.get("activation_counts"),
        "trades_sha256": run.get("trades_sha256"),
    }


def evaluate_config(research: Any, engine: Any, risk: Any, adapter: Any, context: Any, config: Any) -> dict[str, Any]:
    domains = {}
    for label, window in (("D", research.D_FULL), ("V", research.V_FULL)):
        domains[label] = compact_run(
            research.run_one(
                engine=engine,
                risk=risk,
                adapter=adapter,
                context=context,
                window=window,
                config=config,
            )
        )
        domains[f"stress_{label}"] = compact_run(
            research.run_one(
                engine=engine,
                risk=risk,
                adapter=adapter,
                context=context,
                window=window,
                config=config,
                slippage=research.STRESS_SLIPPAGE,
            )
        )
        domains[f"funding_off_{label}"] = compact_run(
            research.run_one(
                engine=engine,
                risk=risk,
                adapter=adapter,
                context=context,
                window=window,
                config=config,
                include_funding=False,
            )
        )
    folds = [
        compact_run(
            research.run_one(
                engine=engine,
                risk=risk,
                adapter=adapter,
                context=context,
                window=window,
                config=config,
            )
        )
        for window in research.ROLLING_FOLDS
    ]
    return {
        "config": config.canonical(),
        "domains": domains,
        "folds": folds,
        "rolling": research.aggregate_folds(folds),
    }


def main() -> None:
    research = load_module(ORCHESTRATOR_PATH, "hype_wtl_failure_research")
    stage_c, stage_c_sha = research.read_locked(STAGE_C_PATH)
    if stage_c.get("status") != "FAIL" or stage_c.get("h_accessed"):
        raise RuntimeError("diagnostic requires locked Stage-C FAIL with H untouched")
    rows = stage_c["rows"]
    near = [row for row in rows if strict_except_v_floor(row)]
    by_v_trades = {
        count: sorted(
            [row for row in near if int(row["V"]["metrics"]["closed_trades"]) == count],
            key=representative_key,
        )
        for count in (1, 2)
    }
    representatives = [items[0] for items in by_v_trades.values() if items]

    lookup = {config_key(row["config"]): row for row in rows}
    factorial = {}
    for module in ("entry", "long_exit", "short_exit", "short_rsi"):
        comparisons = []
        for row in rows:
            if module not in module_flags(row["config"]):
                continue
            disabled = lookup.get(config_key(row["config"], off_module=module))
            if disabled is None:
                continue
            comparisons.append(
                {
                    "arm_id": row["arm_id"],
                    "disabled_arm_id": disabled["arm_id"],
                    "D_return_effect_pp": float(row["D"]["metrics"]["net_return_pct"]) - float(disabled["D"]["metrics"]["net_return_pct"]),
                    "D_mdd_effect_pp": float(row["D"]["metrics"]["chronological_1h_mdd_pct"]) - float(disabled["D"]["metrics"]["chronological_1h_mdd_pct"]),
                    "V_return_effect_pp": float(row["V"]["metrics"]["net_return_pct"]) - float(disabled["V"]["metrics"]["net_return_pct"]),
                    "V_mdd_effect_pp": float(row["V"]["metrics"]["chronological_1h_mdd_pct"]) - float(disabled["V"]["metrics"]["chronological_1h_mdd_pct"]),
                    "D_path_changed": row["D"]["trades_sha256"] != disabled["D"]["trades_sha256"],
                    "V_path_changed": row["V"]["trades_sha256"] != disabled["V"]["trades_sha256"],
                }
            )
        factorial[module] = {
            "comparison_count": len(comparisons),
            "D_path_changed_count": sum(item["D_path_changed"] for item in comparisons),
            "V_path_changed_count": sum(item["V_path_changed"] for item in comparisons),
            "positive_both_metrics_D_count": sum(item["D_return_effect_pp"] > 0.0 and item["D_mdd_effect_pp"] >= 0.0 for item in comparisons),
            "positive_both_metrics_V_count": sum(item["V_return_effect_pp"] > 0.0 and item["V_mdd_effect_pp"] >= 0.0 for item in comparisons),
            "rows": comparisons,
        }

    engine, risk, adapter, _, context = research.load_runtime()
    detailed = []
    for representative in representatives:
        config = engine.config_from_dict(representative["config"])
        variants = [config]
        variants.extend(engine.disable_module(config, module, "POSTFAIL") for module in config.enabled_modules())
        variants.extend(engine.keep_only_module(config, module) for module in config.enabled_modules())
        variants.extend(engine.adjacent_neighbors(config))
        unique = {engine.config_sha256(engine.WTLConfig("DEDUP", entry=row.entry, long_exit=row.long_exit, short_exit=row.short_exit, short_rsi=row.short_rsi)): row for row in variants}
        detailed.append(
            {
                "representative_arm_id": representative["arm_id"],
                "v_trade_count": representative["V"]["metrics"]["closed_trades"],
                "locked_prepass_gate": representative["prepass_gate"],
                "variant_count": len(unique),
                "variants": [evaluate_config(research, engine, risk, adapter, context, row) for row in sorted(unique.values(), key=lambda item: item.arm_id)],
            }
        )

    economic_clusters: dict[str, int] = {}
    for row in rows:
        key = f"{row['D']['trades_sha256']}:{row['V']['trades_sha256']}"
        economic_clusters[key] = economic_clusters.get(key, 0) + 1
    payload = {
        "schema": "hype-wtl-post-fail-ablation-v1",
        "status": "DIAGNOSTIC_ONLY",
        "stage_c_sha256": stage_c_sha,
        "h_accessed": False,
        "failure": {
            "combo_count": stage_c["combo_count"],
            "prepass_pass_count": stage_c["prepass_pass_count"],
            "strict_except_v_candidate_floor_count": len(near),
            "near_count_by_v_trades": {str(count): len(items) for count, items in by_v_trades.items()},
            "unique_DV_economic_paths": len(economic_clusters),
            "economic_path_cluster_sizes": sorted(economic_clusters.values(), reverse=True),
        },
        "representative_rows": [
            {
                "arm_id": row["arm_id"],
                "config": row["config"],
                "D": compact_run(row["D"]),
                "V": compact_run(row["V"]),
                "prepass_gate": row["prepass_gate"],
            }
            for row in representatives
        ],
        "factorial_leave_one_out": factorial,
        "detailed_multi_ablation": detailed,
        "interpretation_guard": "Post-fail D+V diagnostic only; cannot reopen WTL, select a WTL champion, or access H.",
    }
    research.write_locked(OUTPUT_PATH, payload)
    print(json.dumps({"status": payload["status"], "near": len(near), "detailed": len(detailed), "output": str(OUTPUT_PATH)}, sort_keys=True))


if __name__ == "__main__":
    main()

