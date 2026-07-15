from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import random
from typing import Any

import pandas as pd

from as6s_engine import PREFIT_END, REUSED_END, STARTS
from as6s_live_safe_router import nonpreemptive
from combine_hybrid_asset_specific_account import strict_metrics
import research_binance_as6s_v5_legacy_exact_full_ablation as full


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
MANIFEST = (
    FAMILY_DIR
    / "artifacts/binance_as6s_v5_joint_state_future_oos_freeze_2026-07-14.json"
)
ABLATION = FAMILY_DIR / "artifacts/binance_as6s_v5_legacy_exact_full_ablation_2026-07-15.json"
CLEAN_SURFACE = FAMILY_DIR / "artifacts/binance_as6s_v6_clean_surface_2026-07-15.json"
OUTPUT = FAMILY_DIR / "artifacts/binance_as6s_v6_legacy_microtune_2026-07-15.json"
REPORT = FAMILY_DIR / "notes/binance-as6s-v6-legacy-microtune-2026-07-15.md"
TRAIN_END = pd.Timestamp("2025-10-14T09:00:00Z")
VALIDATION_1_END = pd.Timestamp("2026-01-14T09:00:00Z")
RANDOM_CANDIDATES = 300
SHORTLIST = 18
SCENARIOS = full.SCENARIOS


def metrics_by_window(rows: list[Any], start: pd.Timestamp) -> dict[str, Any]:
    selected = nonpreemptive(rows, start=start, end=REUSED_END)
    windows = {
        "train": (start, TRAIN_END),
        "validation_1": (TRAIN_END, VALIDATION_1_END),
        "validation_2": (VALIDATION_1_END, PREFIT_END),
        "prefit": (start, PREFIT_END),
        "current_diagnostic": (PREFIT_END, REUSED_END),
        "through_cutoff": (start, REUSED_END),
    }
    return {
        name: strict_metrics(selected, left, right)
        for name, (left, right) in windows.items()
    }


def selection_score(metrics: dict[str, Any]) -> float:
    train = metrics["train"]
    val1 = metrics["validation_1"]
    val2 = metrics["validation_2"]
    prefit = metrics["prefit"]
    current = metrics["current_diagnostic"]
    if prefit["trades"] < 18 or val1["trades"] < 2 or val2["trades"] < 2:
        return -1e12
    return float(
        1.7 * math.log(max(prefit["annual_multiple"], 1e-9))
        + 0.8 * math.log(max(train["annual_multiple"], 1e-9))
        + 0.9 * math.log(max(val1["annual_multiple"], 1e-9))
        + 1.1 * math.log(max(val2["annual_multiple"], 1e-9))
        + 2.1 * prefit["win_rate"]
        + val1["win_rate"]
        + 1.2 * val2["win_rate"]
        + 4.0 * min(prefit["max_dd"], val1["max_dd"], val2["max_dd"])
        + 0.15 * math.log1p(prefit["trades"])
        + 20.0 * min(0.0, train["total_return"])
        + 24.0 * min(0.0, val1["total_return"])
        + 28.0 * min(0.0, val2["total_return"])
        + 20.0 * min(0.0, current["total_return"])
        + 14.0 * min(0.0, current["max_dd"] + 0.25)
    )


def robust_score(scenarios: dict[str, Any]) -> float:
    value = selection_score(scenarios["base_4bps_k1"]["metrics"])
    for name in ("stress_8bps_k1", "base_4bps_k2"):
        metrics = scenarios[name]["metrics"]
        prefit = metrics["prefit"]
        current = metrics["current_diagnostic"]
        value += 0.5 * math.log(max(prefit["annual_multiple"], 1e-9))
        value += prefit["win_rate"] + 2.0 * prefit["max_dd"]
        value += 18.0 * min(0.0, current["total_return"])
        value += 12.0 * min(0.0, current["max_dd"] + 0.25)
    return float(value)


def configs_for_sleeve(
    baseline: Any,
    groups: list[dict[str, Any]],
    removed_fields: set[str],
    *,
    seed: int,
) -> list[Any]:
    eligible = [
        group
        for group in groups
        if group["updates"] and not set(group["fields"]).issubset(removed_fields)
    ]
    candidates = {json.dumps(asdict(baseline), sort_keys=True): baseline}
    for group in eligible:
        for updates in group["updates"]:
            cfg = replace(baseline, **updates)
            if cfg.min_adx > cfg.max_adx or cfg.min_atr_bps > cfg.max_atr_bps:
                continue
            if cfg.threshold_low >= cfg.threshold_high:
                continue
            candidates[json.dumps(asdict(cfg), sort_keys=True)] = cfg
    rng = random.Random(seed)
    attempts = 0
    while len(candidates) < RANDOM_CANDIDATES and attempts < RANDOM_CANDIDATES * 100:
        attempts += 1
        selected = rng.sample(eligible, k=rng.randint(2, min(5, len(eligible))))
        updates: dict[str, Any] = {}
        for group in selected:
            updates.update(rng.choice(group["updates"]))
        cfg = replace(baseline, **updates)
        if cfg.min_adx > cfg.max_adx or cfg.min_atr_bps > cfg.max_atr_bps:
            continue
        if cfg.threshold_low >= cfg.threshold_high:
            continue
        candidates[json.dumps(asdict(cfg), sort_keys=True)] = cfg
    return list(candidates.values())[:RANDOM_CANDIDATES]


def evaluate(
    *,
    engine: Any,
    frame: pd.DataFrame,
    prefix: tuple[Any, Any],
    sleeve: str,
    audit: dict[str, Any],
    cfg: Any,
    scenario: str,
) -> dict[str, Any]:
    slippage, delay = SCENARIOS[scenario]
    engine.SLIPPAGE_PER_FILL = slippage
    scenario_cfg = replace(cfg, entry_delay_bars=delay)
    raw = full.legacy.simulate_stateless(
        engine,
        frame,
        scenario_cfg,
        *prefix,
    )
    unified = full.to_unified(sleeve, audit, scenario_cfg, raw)
    return {
        "opportunities": len(unified),
        "metrics": metrics_by_window(unified, STARTS[audit["symbol"]]),
    }


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    ablation = json.loads(ABLATION.read_text(encoding="utf-8"))
    clean_surface = json.loads(CLEAN_SURFACE.read_text(encoding="utf-8"))
    contexts, captured, featured, prefixes = full.prepare()
    results: dict[str, Any] = {}
    for sleeve in manifest["selected_sleeves"]:
        audit = manifest["sleeve_configs"][sleeve]
        if audit["source"] != "legacy_asset_specific_1h":
            continue
        asset = audit["symbol"].removesuffix("USDT")
        baseline = next(
            cfg
            for name, cfg in captured.items()
            if name.startswith(asset) and cfg.style == audit["mechanism"]
        )
        groups = full.replacement_groups(baseline, featured[asset])
        active_groups = {
            name
            for name, row in ablation["results"][sleeve]["parameter_groups"].items()
            if row["classification"] == "active_tunable"
        }
        groups = [group for group in groups if group["label"] in active_groups]
        configs = configs_for_sleeve(
            baseline,
            groups,
            set(clean_surface["sleeves"][sleeve]["remove_fields"]),
            seed=20260715 + len(results) * 211,
        )
        engine = contexts[asset]["engine"]
        rows: list[dict[str, Any]] = []
        for config in configs:
            metric = evaluate(
                engine=engine,
                frame=featured[asset],
                prefix=prefixes[asset],
                sleeve=sleeve,
                audit=audit,
                cfg=config,
                scenario="base_4bps_k1",
            )
            rows.append(
                {
                    "config": asdict(config),
                    "base_4bps_k1": metric,
                    "selection_score": selection_score(metric["metrics"]),
                    "is_baseline": config == baseline,
                }
            )
        rows.sort(key=lambda row: row["selection_score"], reverse=True)
        baseline_row = next(row for row in rows if row["is_baseline"])
        shortlist = rows[:SHORTLIST]
        if baseline_row not in shortlist:
            shortlist.append(baseline_row)
        robust_rows: list[dict[str, Any]] = []
        for row in shortlist:
            cfg = type(baseline)(**row["config"])
            scenarios = {"base_4bps_k1": row["base_4bps_k1"]}
            for scenario in ("stress_8bps_k1", "base_4bps_k2"):
                scenarios[scenario] = evaluate(
                    engine=engine,
                    frame=featured[asset],
                    prefix=prefixes[asset],
                    sleeve=sleeve,
                    audit=audit,
                    cfg=cfg,
                    scenario=scenario,
                )
            robust_rows.append(
                {**row, "scenarios": scenarios, "robust_score": robust_score(scenarios)}
            )
        robust_rows.sort(key=lambda row: row["robust_score"], reverse=True)
        results[sleeve] = {
            "symbol": audit["symbol"],
            "mechanism": audit["mechanism"],
            "generated_candidates": len(configs),
            "active_clean_groups": [group["label"] for group in groups],
            "baseline": baseline_row,
            "preferred": robust_rows[0],
            "robust_ranking": robust_rows,
        }

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "v6_legacy_clean_surface_microtune_not_registered",
        "research_cutoff_exclusive": REUSED_END.isoformat(),
        "future_oos_read": False,
        "frozen_v5_modified": False,
        "selection_policy": (
            "clean fields only; train/validation/prefit ranking; current diagnostic veto; "
            "shortlist rerun at 8bps K+1 and 4bps K+2"
        ),
        "sleeves": len(results),
        "results": results,
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    changed = sum(
        row["preferred"]["config"] != row["baseline"]["config"]
        for row in results.values()
    )
    lines = [
        "# BIN-15M-AS6S V6 六条旧1h腿clean微调（2026-07-15）",
        "",
        "只组合消融后仍活跃的字段；每腿最多300个OAT及2-5字段局部组合，当前三个月只作负收益/回撤惩罚，shortlist复测8 bps和K+2。",
        "",
        f"- 腿：`{len(results)}`",
        f"- 生成配置：`{sum(row['generated_candidates'] for row in results.values())}`",
        f"- preferred不同于V5基线：`{changed}`",
        "",
        "| 腿 | 是否变化 | base prefit年化 | base当前3m收益 | 8bps当前3m收益 | K+2当前3m收益 |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for sleeve, row in results.items():
        preferred = row["preferred"]
        scenarios = preferred["scenarios"]
        lines.append(
            f"| `{sleeve}` | {'是' if preferred['config'] != row['baseline']['config'] else '否'} | "
            f"{scenarios['base_4bps_k1']['metrics']['prefit']['annual_multiple']:.3f}x | "
            f"{scenarios['base_4bps_k1']['metrics']['current_diagnostic']['total_return']:+.2%} | "
            f"{scenarios['stress_8bps_k1']['metrics']['current_diagnostic']['total_return']:+.2%} | "
            f"{scenarios['base_4bps_k2']['metrics']['current_diagnostic']['total_return']:+.2%} |"
        )
    lines.extend(
        [
            "",
            "preferred只进入联合账户替换池；旧腿内部杠杆字段已外置，最终暴露继续由账户合同限制在3x以内。",
            "",
            f"结构化结果：[`{OUTPUT.name}`](../artifacts/{OUTPUT.name})。",
        ]
    )
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(OUTPUT.relative_to(ROOT)),
                "report": str(REPORT.relative_to(ROOT)),
                "sleeves": len(results),
                "generated_candidates": sum(
                    row["generated_candidates"] for row in results.values()
                ),
                "preferred_changed": changed,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
