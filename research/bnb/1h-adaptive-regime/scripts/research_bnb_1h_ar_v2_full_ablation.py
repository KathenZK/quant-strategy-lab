"""BNB-1H-Adaptive-Regime-V2 full parameter ablation.

One-at-a-time domain sweep over every V2 active field. A field is only
declared removable if every tested domain value leaves the full trade path
unchanged. Metrics are reported per window for mechanism understanding and
prefit-only tuning guidance; this script never selects on locked OOS.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def load_v2() -> Any:
    spec = importlib.util.spec_from_file_location("bnb_1h_ar_v2", SCRIPT_DIR / "bnb_1h_ar_v2.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load bnb_1h_ar_v2.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v2 = load_v2()

FAMILY_DIR = ROOT / "research/bnb/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
ABLATION_DIR = FAMILY_DIR / "ablations"
DATE_TAG = "2026-07-07"
SUMMARY_JSON = ARTIFACT_DIR / f"bnb_1h_ar_v2_full_ablation_{DATE_TAG}.json"
ROWS_CSV = ARTIFACT_DIR / f"bnb_1h_ar_v2_full_ablation_rows_{DATE_TAG}.csv"
FIELDS_CSV = ARTIFACT_DIR / f"bnb_1h_ar_v2_full_ablation_fields_{DATE_TAG}.csv"
REPORT_MD = ABLATION_DIR / f"bnb-1h-ar-v2-full-parameter-ablation-{DATE_TAG}.md"

EXECUTION_TIMING_FIELDS = {"entry_delay_bars"}

# One-at-a-time sweep domains for the V2 active fields (baseline value excluded
# automatically). exit_kind is swept jointly with representative trail params.
EMA_PULLBACK_DOMAINS: dict[str, tuple[Any, ...]] = {
    "side_mode": ("long", "short"),
    "ema_fast": (21, 34, 89, 144),
    "ema_slow": (55, 144, 233, 377),
    "ema_htf": (55, 89, 144, 233),
    "pullback_atr": (-0.5, 0.0, 0.25, 0.5, 0.75),
    "min_rvol": (0.0, 0.6, 0.8, 1.25, 1.5, 2.0),
    "min_atr_bps": (0.0, 25.0, 75.0, 100.0),
    "max_dist_ema_bps": (150.0, 500.0, 750.0, 1_000.0, 10_000.0),
    "tp_atr": (1.0, 1.5, 2.0, 2.5, 4.0, 5.0, 6.0),
    "sl_atr": (2.0, 2.5, 3.0, 4.0, 6.0),
    "max_hold_bars": (48, 72, 96, 120, 240, 336),
    "cooldown_bars": (0, 3, 12, 24, 48),
    "fixed_leverage": (1.0, 1.5, 2.5, 3.0),
    "entry_delay_bars": (2, 3),
}

WICK_REJECT_DOMAINS: dict[str, tuple[Any, ...]] = {
    "side_mode": ("long", "short"),
    "threshold_low": (0.25, 0.30, 0.40, 0.45),
    "threshold_high": (0.75, 0.80, 0.90),
    "band_k": (0.25, 0.75, 1.0, 1.25, 1.5),
    "min_adx": (0.0, 12.0, 16.0, 20.0, 28.0, 32.0),
    "min_rvol": (0.0, 1.0, 1.5, 2.5, 3.0),
    "htf_mode": ("none", "h4", "d1"),
    "tp_atr": (0.75, 1.5, 2.0, 3.0),
    "sl_atr": (2.0, 3.0, 4.0, 6.0),
    "max_hold_bars": (24, 48, 96, 120, 168),
    "cooldown_bars": (0, 6, 12, 48),
    "fixed_leverage": (0.5, 1.0, 1.5, 2.0),
    "entry_delay_bars": (2, 3),
}

EXIT_KIND_VARIANTS: tuple[tuple[float, float], ...] = ((1.0, 1.0), (2.0, 1.5), (4.0, 1.5))


def flatten_metrics(metrics: dict[str, dict[str, float]]) -> dict[str, float]:
    return {
        f"{window}_{key}": value
        for window, window_metrics in metrics.items()
        for key, value in window_metrics.items()
    }


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    ABLATION_DIR.mkdir(parents=True, exist_ok=True)
    ctx = v2.load_context()
    engine = ctx["engine"]
    frame = ctx["frame"]
    funding_times = ctx["funding_times"]
    funding_cumulative = ctx["funding_cumulative"]
    split = ctx["split"]

    configs = v2.v2_configs(engine)
    baseline_trades = v2.simulate_strategy(
        engine, frame, funding_times, funding_cumulative, configs
    )
    baseline_oos = v2.simulate_strategy(
        engine, frame, funding_times, funding_cumulative, configs, start=split["oos_start"]
    )
    v1_trades = v2.simulate_strategy(
        engine, frame, funding_times, funding_cumulative, v2.v1_configs(engine, ctx["freeze"])
    )
    if v2.trade_signature(v1_trades) != v2.trade_signature(baseline_trades):
        raise RuntimeError("V2 baseline drifted from the V1 trade path")

    baseline_metrics = v2.metric_bundle(engine, baseline_trades, baseline_oos, split)
    baseline_flat = flatten_metrics(baseline_metrics)
    baseline_sig = v2.trade_signature(baseline_trades)

    def evaluate(variant_configs: tuple[Any, ...]) -> tuple[dict[str, float], bool]:
        trades = v2.simulate_strategy(
            engine, frame, funding_times, funding_cumulative, variant_configs
        )
        oos = v2.simulate_strategy(
            engine,
            frame,
            funding_times,
            funding_cumulative,
            variant_configs,
            start=split["oos_start"],
        )
        metrics = flatten_metrics(v2.metric_bundle(engine, trades, oos, split))
        same = v2.trade_signature(trades) == baseline_sig
        return metrics, same

    rows: list[dict[str, Any]] = []

    # Component removal.
    for index, removed in enumerate(configs):
        kept = tuple(cfg for i, cfg in enumerate(configs) if i != index)
        kept_priorities = tuple(
            p for i, p in enumerate(v2.PRIORITIES) if i != index
        )
        trades = v2.simulate_strategy(
            engine, frame, funding_times, funding_cumulative, kept, kept_priorities
        )
        oos = v2.simulate_strategy(
            engine,
            frame,
            funding_times,
            funding_cumulative,
            kept,
            kept_priorities,
            start=split["oos_start"],
        )
        metrics = flatten_metrics(v2.metric_bundle(engine, trades, oos, split))
        row: dict[str, Any] = {
            "variant_type": "component_removed",
            "component": removed.style,
            "field": "component",
            "value": "removed",
            "same_full_signature": False,
        }
        row.update(metrics)
        rows.append(row)

    # One-at-a-time field sweeps.
    domain_sets = (
        (0, "ema_pullback", EMA_PULLBACK_DOMAINS),
        (1, "wick_reject", WICK_REJECT_DOMAINS),
    )
    for index, component, domains in domain_sets:
        target = configs[index]
        for field_name, values in domains.items():
            for value in values:
                if value == getattr(target, field_name):
                    continue
                variant = list(configs)
                variant[index] = replace(target, **{field_name: value})
                metrics, same = evaluate(tuple(variant))
                row = {
                    "variant_type": "field_sweep",
                    "component": component,
                    "field": field_name,
                    "value": value,
                    "same_full_signature": same,
                }
                row.update(metrics)
                rows.append(row)
        # exit_kind flip with representative trail settings.
        for activation, trail in EXIT_KIND_VARIANTS:
            variant = list(configs)
            variant[index] = replace(
                target,
                exit_kind="trailing",
                trail_activation_atr=activation,
                trail_atr=trail,
            )
            metrics, same = evaluate(tuple(variant))
            row = {
                "variant_type": "field_sweep",
                "component": component,
                "field": "exit_kind",
                "value": f"trailing_a{activation}_t{trail}",
                "same_full_signature": same,
            }
            row.update(metrics)
            rows.append(row)

    rows_frame = pd.DataFrame(rows)
    for key, value in baseline_flat.items():
        rows_frame[f"delta_{key}"] = rows_frame[key] - value
    rows_frame.to_csv(ROWS_CSV, index=False)

    sweep = rows_frame.loc[rows_frame["variant_type"] == "field_sweep"]
    field_rows: list[dict[str, Any]] = []
    for (component, field_name), group in sweep.groupby(["component", "field"]):
        all_same = bool(group["same_full_signature"].all())
        if field_name in EXECUTION_TIMING_FIELDS:
            classification = "execution_timing_parameter"
        elif all_same:
            classification = "remove_noop"
        else:
            classification = "active"
        field_rows.append(
            {
                "component": component,
                "field": field_name,
                "classification": classification,
                "variants": len(group),
                "path_changing_variants": int((~group["same_full_signature"]).sum()),
                "best_prefit_annual": float(group["prefit_annual_multiple"].max()),
                "worst_prefit_dd": float(group["prefit_max_dd"].min()),
            }
        )
    fields_frame = pd.DataFrame(field_rows).sort_values(["classification", "component", "field"])
    fields_frame.to_csv(FIELDS_CSV, index=False)

    active_count = int((fields_frame["classification"] == "active").sum())
    noop_count = int((fields_frame["classification"] == "remove_noop").sum())
    total_fields = len(fields_frame)

    # Prefit-only improvement candidates for tuning guidance (no OOS selection).
    improved = sweep.loc
    improved = sweep[
        (sweep["prefit_annual_multiple"] > baseline_flat["prefit_annual_multiple"])
        & (sweep["prefit_max_dd"] >= baseline_flat["prefit_max_dd"])
        & (sweep["prefit_win_rate"] >= 0.85)
        & (sweep["train_total_return"] > 0)
        & (sweep["validation_total_return"] > 0)
        & (sweep["validation_max_dd"] > -0.20)
    ].sort_values("prefit_annual_multiple", ascending=False)

    summary = {
        "family": "BNB-1H-Adaptive-Regime",
        "version": "BNB-1H-Adaptive-Regime-V2",
        "status": "v2_full_ablation_complete_not_promoted",
        "baseline": baseline_metrics,
        "rows": len(rows_frame),
        "fields_total": total_fields,
        "fields_active": active_count,
        "fields_remove_noop": noop_count,
        "prefit_improvement_candidates": int(len(improved)),
        "artifacts": {
            "rows_csv": str(ROWS_CSV.relative_to(ROOT)),
            "fields_csv": str(FIELDS_CSV.relative_to(ROOT)),
        },
    }
    SUMMARY_JSON.write_text(
        json.dumps(v2.json_safe(summary), indent=2, ensure_ascii=False), encoding="utf-8"
    )

    def fmt(metric: dict[str, float]) -> str:
        return (
            f"`{metric['annual_multiple']:.2f}x` / `{metric['total_return'] * 100:.2f}%` / "
            f"`{metric['max_dd'] * 100:.2f}%` / `{metric['win_rate'] * 100:.2f}%` / "
            f"`{int(metric['trades'])}`"
        )

    lines = [
        "# BNB-1H-Adaptive-Regime-V2 全参数消融 - 2026-07-07",
        "",
        "## 结论",
        "",
        f"V2 全参数消融完成：`{total_fields}` 个受检字段中 `{active_count}` 个为 active（存在改变交易路径的取值），`{noop_count}` 个在全部扫描取值下交易路径不变（可移除）。V2 仍为 `diagnostic observation / not promoted / not live-ready`；本报告不用于 OOS 后验选参。",
        "",
        f"- Baseline prefit：{fmt(baseline_metrics['prefit'])}。",
        f"- Baseline locked OOS：{fmt(baseline_metrics['holdout'])}。",
        f"- Baseline full：{fmt(baseline_metrics['full'])}。",
        f"- 消融 rows：`{len(rows_frame)}`（含 component removal 与 exit_kind 联动变体）。",
        "",
        "## 字段分类",
        "",
        "| Component | Field | Classification | Variants | Path-changing |",
        "| --- | --- | --- | ---: | ---: |",
    ]
    for _, row in fields_frame.iterrows():
        lines.append(
            f"| `{row['component']}` | `{row['field']}` | `{row['classification']}` | "
            f"`{row['variants']}` | `{row['path_changing_variants']}` |"
        )
    lines.extend(
        [
            "",
            "## Prefit 改进方向（仅供微调，不构成版本变更）",
            "",
            "以下单字段变体在 train/validation/prefit 上不差于 baseline 且 prefit 年化更高；它们改变交易路径，只能作为微调搜索的方向输入：",
            "",
        ]
    )
    if improved.empty:
        lines.append("- 无（单字段变化没有同时改善 prefit 收益且不恶化回撤的方向）。")
    else:
        for _, row in improved.head(15).iterrows():
            lines.append(
                f"- `{row['component']}.{row['field']}={row['value']}`：prefit "
                f"`{row['prefit_annual_multiple']:.2f}x / {row['prefit_max_dd'] * 100:.2f}% / "
                f"{row['prefit_win_rate'] * 100:.2f}%`。"
            )
    lines.extend(
        [
            "",
            "## Component removal",
            "",
            "| Removed | Prefit | Locked OOS | Full |",
            "| --- | --- | --- | --- |",
        ]
    )
    removal = rows_frame.loc[rows_frame["variant_type"] == "component_removed"]
    for _, row in removal.iterrows():
        lines.append(
            f"| `{row['component']}` | `{row['prefit_annual_multiple']:.2f}x / "
            f"{row['prefit_max_dd'] * 100:.2f}% / {row['prefit_win_rate'] * 100:.2f}%` | "
            f"`{row['holdout_annual_multiple']:.2f}x / {row['holdout_max_dd'] * 100:.2f}% / "
            f"{row['holdout_win_rate'] * 100:.2f}%` | `{row['full_annual_multiple']:.2f}x / "
            f"{row['full_max_dd'] * 100:.2f}% / {row['full_win_rate'] * 100:.2f}%` |"
        )
    lines.extend(
        [
            "",
            "## 产物",
            "",
            f"- `{SUMMARY_JSON.relative_to(ROOT)}`",
            f"- `{ROWS_CSV.relative_to(ROOT)}`",
            f"- `{FIELDS_CSV.relative_to(ROOT)}`",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(v2.json_safe(summary), indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
