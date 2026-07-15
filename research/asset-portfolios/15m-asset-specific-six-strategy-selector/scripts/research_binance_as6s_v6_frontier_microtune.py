from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import random
from typing import Any

import pandas as pd

from as6s_engine import (
    ADX_WINDOWS,
    DONCHIAN_WINDOWS,
    EMA_WINDOWS,
    MACD_PAIRS,
    PREFIT_END,
    REUSED_END,
    RSI_WINDOWS,
    RVOL_WINDOWS,
    STARTS,
    StrategyConfig,
    load_funding,
    load_symbol_frame,
)
from as6s_live_safe_router import nonpreemptive
from combine_hybrid_asset_specific_account import strict_metrics
import research_binance_as6s_v5_frontier_full_ablation as ablation


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
MANIFEST = (
    FAMILY_DIR
    / "artifacts/binance_as6s_v5_joint_state_future_oos_freeze_2026-07-14.json"
)
OUTPUT = FAMILY_DIR / "artifacts/binance_as6s_v6_frontier_microtune_2026-07-15.json"
REPORT = FAMILY_DIR / "notes/binance-as6s-v6-frontier-microtune-2026-07-15.md"
RANDOM_CANDIDATES = 300
SHORTLIST = 18
SCENARIOS = ablation.SCENARIOS
TRAIN_END = pd.Timestamp("2025-10-14T09:00:00Z")
VALIDATION_1_END = pd.Timestamp("2026-01-14T09:00:00Z")


def neighbors(value: float, values: tuple[float, ...] | list[float]) -> list[float]:
    ordered = sorted(set(values))
    if value not in ordered:
        ordered.append(value)
        ordered.sort()
    index = ordered.index(value)
    return ordered[max(0, index - 1) : min(len(ordered), index + 2)]


def domains(base: StrategyConfig) -> dict[str, list[Any]]:
    output: dict[str, list[Any]] = {
        "side_mode": list(dict.fromkeys((base.side_mode, "both", "long", "short"))),
        "adx_window": neighbors(base.adx_window, list(ADX_WINDOWS)),
        "adx_min": neighbors(base.adx_min, [0.0, 15.0, 18.0, 21.0, 24.0, 28.0, 32.0, 36.0, 40.0]),
        "rvol_window": neighbors(base.rvol_window, list(RVOL_WINDOWS)),
        "rvol_min": neighbors(base.rvol_min, [0.0, 0.5, 0.75, 0.85, 1.0, 1.15, 1.3, 1.5, 1.75]),
        "min_atr_pct": sorted(set([0.0, base.min_atr_pct * 0.85, base.min_atr_pct, base.min_atr_pct * 1.15])),
        "max_atr_pct": sorted(set([base.max_atr_pct * 0.85, base.max_atr_pct, base.max_atr_pct * 1.15, float("inf")])),
        "max_atr_ratio": neighbors(base.max_atr_ratio, [1.2, 1.5, 1.8, 2.5, 99.0]),
        "require_h1": [base.require_h1, not base.require_h1],
        "require_body": [base.require_body, not base.require_body],
        "sl_atr": neighbors(base.sl_atr, [2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 9.0, 10.0, 12.0]),
        "max_hold_bars": neighbors(base.max_hold_bars, [8, 12, 16, 24, 32, 48, 72, 96, 192, 384, 576, 768]),
    }
    if base.mechanism in {"trend_state", "breakout"}:
        fast_values = [v for v in EMA_WINDOWS if 8 <= v <= 128]
        slow_values = [v for v in EMA_WINDOWS if v >= 64]
        output["ema_fast"] = neighbors(base.ema_fast, fast_values)
        output["ema_slow"] = neighbors(base.ema_slow, slow_values)
    if base.mechanism == "trend_state":
        output.update(
            {
                "threshold_long": neighbors(base.threshold_long, [0.0, 0.5, 1.0]),
                "max_dist_atr": neighbors(base.max_dist_atr, [1.0, 2.0, 3.0, 4.0, 6.0, 99.0]),
                "trail_activate_atr": neighbors(base.trail_activate_atr, [1.0, 2.0, 3.0, 4.0, 5.0]),
                "trail_atr": neighbors(base.trail_atr, [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]),
            }
        )
    elif base.mechanism == "breakout":
        output.update(
            {
                "indicator_window": neighbors(base.indicator_window, list(DONCHIAN_WINDOWS)),
                "tp_atr": neighbors(base.tp_atr, [1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0]),
            }
        )
    else:
        macd_index = list(MACD_PAIRS).index((base.aux_fast, base.aux_slow))
        macd_values = list(MACD_PAIRS)[max(0, macd_index - 1) : macd_index + 2]
        output.update(
            {
                "indicator_window": neighbors(base.indicator_window, list(RSI_WINDOWS)),
                "threshold_long": neighbors(base.threshold_long, [15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0]),
                "threshold_short": neighbors(base.threshold_short, [55.0, 60.0, 65.0, 70.0, 75.0, 80.0, 85.0]),
                "macd_pair": macd_values,
                "tp_atr": neighbors(base.tp_atr, [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5]),
            }
        )
    return output


def candidate_configs(base: StrategyConfig, seed: int) -> list[StrategyConfig]:
    rng = random.Random(seed)
    field_domains = domains(base)
    candidates = {json.dumps(asdict(base), sort_keys=True, default=str): base}
    # One-at-a-time neighborhood makes every retained dimension observable.
    for field, values in field_domains.items():
        for value in values:
            if field == "macd_pair":
                cfg = replace(base, aux_fast=value[0], aux_slow=value[1])
            else:
                cfg = replace(base, **{field: value})
            if cfg.ema_fast and cfg.ema_slow and cfg.ema_fast >= cfg.ema_slow:
                continue
            if cfg.max_atr_pct <= cfg.min_atr_pct:
                continue
            if cfg.mechanism == "reversal" and cfg.threshold_long >= cfg.threshold_short:
                continue
            candidates[json.dumps(asdict(cfg), sort_keys=True, default=str)] = cfg
    while len(candidates) < RANDOM_CANDIDATES:
        updates: dict[str, Any] = {}
        for field, values in field_domains.items():
            value = rng.choice(values)
            if field == "macd_pair":
                updates["aux_fast"], updates["aux_slow"] = value
            else:
                updates[field] = value
        cfg = replace(base, **updates)
        if cfg.ema_fast and cfg.ema_slow and cfg.ema_fast >= cfg.ema_slow:
            continue
        if cfg.max_atr_pct <= cfg.min_atr_pct:
            continue
        if cfg.mechanism == "reversal" and cfg.threshold_long >= cfg.threshold_short:
            continue
        candidates[json.dumps(asdict(cfg), sort_keys=True, default=str)] = cfg
    return list(candidates.values())[:RANDOM_CANDIDATES]


def window_metrics(trades: list[Any], symbol: str) -> dict[str, Any]:
    selected = nonpreemptive(trades, start=STARTS[symbol], end=REUSED_END)
    windows = {
        "train": (STARTS[symbol], TRAIN_END),
        "validation_1": (TRAIN_END, VALIDATION_1_END),
        "validation_2": (VALIDATION_1_END, PREFIT_END),
        "prefit": (STARTS[symbol], PREFIT_END),
        "current_diagnostic": (PREFIT_END, REUSED_END),
        "through_cutoff": (STARTS[symbol], REUSED_END),
    }
    return {
        name: strict_metrics(selected, start, end)
        for name, (start, end) in windows.items()
    }


def selection_score(metrics: dict[str, Any]) -> float:
    train = metrics["train"]
    val1 = metrics["validation_1"]
    val2 = metrics["validation_2"]
    prefit = metrics["prefit"]
    current = metrics["current_diagnostic"]
    if prefit["trades"] < 12 or val1["trades"] < 2 or val2["trades"] < 2:
        return -1e12
    return float(
        1.6 * math.log(max(prefit["annual_multiple"], 1e-9))
        + 0.8 * math.log(max(train["annual_multiple"], 1e-9))
        + 0.9 * math.log(max(val1["annual_multiple"], 1e-9))
        + 1.1 * math.log(max(val2["annual_multiple"], 1e-9))
        + 2.0 * prefit["win_rate"]
        + 0.8 * val1["win_rate"]
        + 1.0 * val2["win_rate"]
        + 3.5 * min(prefit["max_dd"], val1["max_dd"], val2["max_dd"])
        + 0.15 * math.log1p(prefit["trades"])
        + 18.0 * min(0.0, train["total_return"])
        + 22.0 * min(0.0, val1["total_return"])
        + 26.0 * min(0.0, val2["total_return"])
        + 14.0 * min(0.0, current["total_return"])
        + 12.0 * min(0.0, current["max_dd"] + 0.25)
    )


def robust_score(scenarios: dict[str, Any]) -> float:
    base = scenarios["base_4bps_k1"]["metrics"]
    score = selection_score(base)
    for name in ("stress_8bps_k1", "base_4bps_k2"):
        metric = scenarios[name]["metrics"]
        prefit = metric["prefit"]
        current = metric["current_diagnostic"]
        score += 0.45 * math.log(max(prefit["annual_multiple"], 1e-9))
        score += 0.8 * prefit["win_rate"] + 1.8 * prefit["max_dd"]
        score += 12.0 * min(0.0, current["total_return"])
        score += 10.0 * min(0.0, current["max_dd"] + 0.25)
    return float(score)


def evaluate(
    sleeve: str,
    audit: dict[str, Any],
    frame: pd.DataFrame,
    funding: pd.DataFrame,
    cfg: StrategyConfig,
    scenario: str,
) -> dict[str, Any]:
    slippage, delay = SCENARIOS[scenario]
    raw = ablation.simulate(
        frame,
        funding,
        cfg,
        frozenset(),
        slippage=slippage,
        delay=delay,
    )
    trades = ablation.unified(sleeve, audit, cfg.mechanism, raw)
    return {
        "opportunities": len(trades),
        "metrics": window_metrics(trades, audit["symbol"]),
    }


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    results: dict[str, Any] = {}
    frames: dict[str, pd.DataFrame] = {}
    funding: dict[str, pd.DataFrame] = {}
    for sleeve in manifest["selected_sleeves"]:
        audit = manifest["sleeve_configs"][sleeve]
        if audit["source"] != "prefit_frontier_asset_first":
            continue
        symbol = audit["symbol"]
        if symbol not in frames:
            frames[symbol] = load_symbol_frame(symbol, end=REUSED_END)
            funding[symbol] = load_funding(symbol, end=REUSED_END)
        base = StrategyConfig.from_dict(audit["config"])
        candidates = candidate_configs(base, seed=20260715 + len(results) * 101)
        base_rows: list[dict[str, Any]] = []
        for index, cfg in enumerate(candidates):
            metrics = evaluate(
                sleeve,
                audit,
                frames[symbol],
                funding[symbol],
                cfg,
                "base_4bps_k1",
            )
            base_rows.append(
                {
                    "index": index,
                    "config": asdict(cfg),
                    "base_4bps_k1": metrics,
                    "selection_score": selection_score(metrics["metrics"]),
                    "is_baseline": cfg == base,
                }
            )
        ranked = sorted(base_rows, key=lambda row: row["selection_score"], reverse=True)
        baseline_row = next(row for row in base_rows if row["is_baseline"])
        shortlist = ranked[:SHORTLIST]
        if baseline_row not in shortlist:
            shortlist.append(baseline_row)
        robust_rows: list[dict[str, Any]] = []
        for row in shortlist:
            cfg = StrategyConfig.from_dict(row["config"])
            scenarios = {"base_4bps_k1": row["base_4bps_k1"]}
            for scenario in ("stress_8bps_k1", "base_4bps_k2"):
                scenarios[scenario] = evaluate(
                    sleeve,
                    audit,
                    frames[symbol],
                    funding[symbol],
                    cfg,
                    scenario,
                )
            robust_rows.append(
                {
                    **row,
                    "scenarios": scenarios,
                    "robust_score": robust_score(scenarios),
                }
            )
        robust_rows.sort(key=lambda row: row["robust_score"], reverse=True)
        preferred = robust_rows[0]
        results[sleeve] = {
            "symbol": symbol,
            "mechanism": base.mechanism,
            "generated_candidates": len(candidates),
            "shortlist": len(robust_rows),
            "baseline": baseline_row,
            "preferred": preferred,
            "robust_ranking": robust_rows,
        }

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "v6_frontier_clean_neighborhood_microtune_not_registered",
        "research_cutoff_exclusive": REUSED_END.isoformat(),
        "future_oos_read": False,
        "frozen_v5_modified": False,
        "selection_policy": (
            "rank on train/validation/prefit; current three months is veto/penalty only; "
            "shortlist retested under 8bps K+1 and 4bps K+2"
        ),
        "random_candidates_per_sleeve": RANDOM_CANDIDATES,
        "shortlist_per_sleeve": SHORTLIST,
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
        "# BIN-15M-AS6S V6 frontier局部微调（2026-07-15）",
        "",
        "每条腿先生成300个基线邻域组合；排序只使用train/validation/prefit，当前三个月只作负收益与回撤惩罚，前18名再复测8 bps和K+2。未读取未来OOS，未修改V5。",
        "",
        f"- 腿：`{len(results)}`",
        f"- 生成配置：`{sum(row['generated_candidates'] for row in results.values())}`",
        f"- preferred不同于V5基线：`{changed}`",
        "",
        "| 腿 | preferred是否变化 | base prefit年化倍数 | base当前3m收益 | 8bps当前3m收益 | K+2当前3m收益 |",
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
            "preferred仍只是账户重组候选；只有替换回六币联合状态后仍满足整体胜率、回撤、频率和成本门禁才会保留。",
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
