from __future__ import annotations

import json
import sys
from dataclasses import fields, replace
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import eth_1h_ar_v1 as v1  # noqa: E402
import eth_1h_ar_v2_1 as v21  # noqa: E402
import research_eth_1h_ar_v2_full_ablation as v2_ablation  # noqa: E402


DATE_TAG = "2026-07-07"
FAMILY_DIR = ROOT / "research/eth/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
ABLATION_DIR = FAMILY_DIR / "ablations"
SUMMARY_JSON = ARTIFACT_DIR / f"eth_1h_ar_v2_1_full_ablation_{DATE_TAG}.json"
ROWS_CSV = ARTIFACT_DIR / f"eth_1h_ar_v2_1_full_ablation_rows_{DATE_TAG}.csv"
FIELDS_CSV = ARTIFACT_DIR / f"eth_1h_ar_v2_1_full_ablation_fields_{DATE_TAG}.csv"
SLICES_CSV = ARTIFACT_DIR / f"eth_1h_ar_v2_1_slices_{DATE_TAG}.csv"
REPORT_MD = ABLATION_DIR / f"eth-1h-ar-v2-1-full-parameter-ablation-{DATE_TAG}.md"

json_safe = v2_ablation.json_safe
flatten_metrics = v2_ablation.flatten_metrics
value_label = v2_ablation.value_label
metric_line = v2_ablation.metric_line
field_domains = v2_ablation.field_domains
DD_FLOOR = v2_ablation.DD_FLOOR


def prefit_strict_improves(row: dict[str, Any], baseline: dict[str, Any]) -> bool:
    """相对 V2.1 的严格改善：收益更高、胜率更高、回撤更小，且 train/validation 稳健。"""
    return bool(
        row["prefit_annual_multiple"] > baseline["prefit_annual_multiple"]
        and row["prefit_win_rate"] > baseline["prefit_win_rate"]
        and row["prefit_max_dd"] > baseline["prefit_max_dd"]
        and row["train_total_return"] > 0.0
        and row["validation_total_return"] > 0.0
        and row["train_max_dd"] > DD_FLOOR
        and row["validation_max_dd"] > DD_FLOOR
    )


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    ABLATION_DIR.mkdir(parents=True, exist_ok=True)
    engine, frame, funding, quality = v21.load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    baseline_bb, baseline_rsi = v21.v2_1_configs()
    baseline_trades, bb_trades, rsi_trades, priorities = v21.simulate_v2_1(
        engine, frame, funding_times, funding_cumulative
    )
    baseline_metrics = v21.metrics(engine, baseline_trades)
    baseline_flat = flatten_metrics(baseline_metrics)
    baseline_signature = v1.trade_signature(baseline_trades)
    component_signatures = {
        "bb_break": v1.trade_signature(bb_trades),
        "rsi_reversal": v1.trade_signature(rsi_trades),
    }
    slice_rows = [
        {"window": name, **metric}
        for name, metric in v21.standard_slices(engine, baseline_trades).items()
    ]
    pd.DataFrame(slice_rows).to_csv(SLICES_CSV, index=False)

    rows: list[dict[str, Any]] = [
        {
            "label": "ETH-1H-Adaptive-Regime-V2.1",
            "component": "ensemble",
            "field": "baseline",
            "baseline_value": "baseline",
            "value": "baseline",
            "component_path_equal": True,
            "merged_path_equal": True,
            "prefit_strict_improve": False,
            **baseline_flat,
        }
    ]
    field_sources = {
        "bb_break": (baseline_bb, fields(type(baseline_bb))),
        "rsi_reversal": (baseline_rsi, fields(type(baseline_rsi))),
    }
    observed: dict[str, set[str]] = {"bb_break": set(), "rsi_reversal": set()}

    for component, (baseline_config, component_fields) in field_sources.items():
        domains = field_domains(component)
        missing = {field.name for field in component_fields} - set(domains)
        if missing:
            raise RuntimeError(
                f"{component} V2.1 ablation specs missing fields: {sorted(missing)}"
            )
        for field in component_fields:
            field_name = field.name
            observed[component].add(field_name)
            for value in domains[field_name]:
                if value == getattr(baseline_config, field_name):
                    continue
                test_config = replace(baseline_config, **{field_name: value})
                if component == "rsi_reversal":
                    if test_config.threshold_high <= test_config.threshold_low:
                        continue
                    if test_config.min_adx > test_config.max_adx:
                        continue
                variant_bb = test_config if component == "bb_break" else baseline_bb
                variant_rsi = test_config if component == "rsi_reversal" else baseline_rsi
                merged, variant_bb_trades, variant_rsi_trades, _ = v21.simulate_v2_1(
                    engine,
                    frame,
                    funding_times,
                    funding_cumulative,
                    bb_break=variant_bb,
                    rsi=variant_rsi,
                )
                variant_component_trades = (
                    variant_bb_trades if component == "bb_break" else variant_rsi_trades
                )
                flat = flatten_metrics(v21.metrics(engine, merged))
                row = {
                    "label": f"{component}__{field_name}__{value_label(value)}",
                    "component": component,
                    "field": field_name,
                    "baseline_value": getattr(baseline_config, field_name),
                    "value": value,
                    "component_path_equal": v1.trade_signature(variant_component_trades)
                    == component_signatures[component],
                    "merged_path_equal": v1.trade_signature(merged) == baseline_signature,
                    **flat,
                }
                row["prefit_strict_improve"] = prefit_strict_improves(row, baseline_flat)
                rows.append(row)

    rows_frame = pd.DataFrame(rows)

    field_rows: list[dict[str, Any]] = []
    for component, (baseline_config, component_fields) in field_sources.items():
        for field in component_fields:
            subset = rows_frame.loc[
                (rows_frame["component"] == component)
                & (rows_frame["field"] == field.name)
            ]
            variant_rows = int(len(subset))
            merged_equal_rows = int(subset["merged_path_equal"].sum())
            classification = (
                "merged_path_inert_remove"
                if variant_rows > 0 and merged_equal_rows == variant_rows
                else "active_tunable"
            )
            if subset.empty:
                best_prefit_annual = float("nan")
                best_prefit_dd = float("nan")
            else:
                best_idx = subset["prefit_annual_multiple"].idxmax()
                best_prefit_annual = float(subset.loc[best_idx, "prefit_annual_multiple"])
                best_prefit_dd = float(subset.loc[best_idx, "prefit_max_dd"])
            field_rows.append(
                {
                    "component": component,
                    "field": field.name,
                    "baseline_value": getattr(baseline_config, field.name),
                    "classification": classification,
                    "variant_rows": variant_rows,
                    "component_path_equal_rows": int(subset["component_path_equal"].sum()),
                    "merged_path_equal_rows": merged_equal_rows,
                    "prefit_strict_improve_rows": int(subset["prefit_strict_improve"].sum()),
                    "best_prefit_annual_multiple": best_prefit_annual,
                    "best_prefit_max_dd": best_prefit_dd,
                }
            )
    fields_frame = pd.DataFrame(field_rows)

    classification_map = {
        (row["component"], row["field"]): row["classification"]
        for row in field_rows
    }
    rows_frame["classification"] = rows_frame.apply(
        lambda item: classification_map.get((item["component"], item["field"]), "baseline"),
        axis=1,
    )
    rows_frame.to_csv(ROWS_CSV, index=False)
    fields_frame.to_csv(FIELDS_CSV, index=False)

    strict = rows_frame.loc[rows_frame["prefit_strict_improve"]].sort_values(
        ["prefit_annual_multiple", "prefit_win_rate", "prefit_max_dd"],
        ascending=[False, False, False],
    )
    inert_fields = {
        "bb_break": sorted(
            row["field"]
            for row in field_rows
            if row["component"] == "bb_break"
            and row["classification"] == "merged_path_inert_remove"
        ),
        "rsi_reversal": sorted(
            row["field"]
            for row in field_rows
            if row["component"] == "rsi_reversal"
            and row["classification"] == "merged_path_inert_remove"
        ),
    }
    active_counts = {
        component: sum(
            1
            for row in field_rows
            if row["component"] == component
            and row["classification"] == "active_tunable"
        )
        for component in ("bb_break", "rsi_reversal")
    }

    payload = {
        "family": "ETH-1H-Adaptive-Regime",
        "version": "ETH-1H-Adaptive-Regime-V2.1",
        "status": "registered_v2_1_full_ablation_complete_no_go_not_live_ready",
        "date": DATE_TAG,
        "data_quality": quality,
        "costs": {
            "fee_per_fill": engine.FEE_PER_FILL,
            "slippage_per_fill": engine.SLIPPAGE_PER_FILL,
            "funding": "actual_binance_history_per_trade",
        },
        "component_prefit_priority_scores": priorities,
        "baseline": baseline_metrics,
        "standard_slices": {row["window"]: row for row in slice_rows},
        "v2_1_exposed_parameter_slots": {
            "bb_break": len(fields(type(baseline_bb))),
            "rsi_reversal": len(fields(type(baseline_rsi))),
            "total": len(fields(type(baseline_bb))) + len(fields(type(baseline_rsi))),
            "coverage_missing": {
                "bb_break": sorted(
                    {field.name for field in fields(type(baseline_bb))}
                    - observed["bb_break"]
                ),
                "rsi_reversal": sorted(
                    {field.name for field in fields(type(baseline_rsi))}
                    - observed["rsi_reversal"]
                ),
            },
        },
        "classification_rule": (
            "one-at-a-time domain 内所有变体 merged 逐笔路径均与 V2.1 相同的字段"
            "判定为 merged_path_inert_remove（无意义参数，删除/硬编码）"
        ),
        "inert_fields": inert_fields,
        "active_tunable_counts": {
            **active_counts,
            "total": sum(active_counts.values()),
        },
        "ablation_rows_including_baseline": len(rows_frame),
        "prefit_strict_improve_rows": len(strict),
        "top_prefit_strict": strict.head(30).to_dict(orient="records"),
        "artifacts": {
            "rows_csv": str(ROWS_CSV.relative_to(ROOT)),
            "fields_csv": str(FIELDS_CSV.relative_to(ROOT)),
            "slices_csv": str(SLICES_CSV.relative_to(ROOT)),
        },
    }
    SUMMARY_JSON.write_text(
        json.dumps(json_safe(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    lines = [
        f"# ETH-1H-Adaptive-Regime-V2.1 全参数消融 - {DATE_TAG}",
        "",
        "## 结论",
        "",
        (
            "本轮覆盖 `ETH-1H-Adaptive-Regime-V2.1` 两条腿全部 `29/29` 个 clean 参数槽，"
            "完成 one-at-a-time 全参数消融。判定规则：domain 内所有变体的 merged 逐笔路径"
            "都与 V2.1 完全相同的字段，视为无意义参数（`merged_path_inert_remove`），"
            "从后续 clean tuning surface 删除或硬编码；其余保留为 `active_tunable`。"
        ),
        "",
        (
            f"分类结果：active tunable `{payload['active_tunable_counts']['total']}` 个"
            f"（bb_break `{active_counts['bb_break']}`、rsi_reversal `{active_counts['rsi_reversal']}`）；"
            f"merged-path inert `{29 - payload['active_tunable_counts']['total']}` 个。"
            f"one-at-a-time 行数（含 baseline）`{len(rows_frame)}`；"
            f"相对 V2.1“收益更高、胜率更高、回撤更小”的严格改善行 `{len(strict)}`。"
        ),
        "",
        "reused holdout 与近期分片只作冻结后审计，不参与删参或选参。",
        "",
        "## V2.1 基线",
        "",
        "| Window | Annual / Return / DD / Win / Trades |",
        "| --- | --- |",
    ]
    for window in ("train", "validation", "prefit", "reused_holdout", "current_full"):
        lines.append(f"| `{window}` | {metric_line(baseline_metrics[window])} |")
    lines.extend(
        [
            "",
            "## 标准近期分片",
            "",
            "| Slice | Annual / Return / DD / Win / Trades |",
            "| --- | --- |",
        ]
    )
    for row in slice_rows:
        lines.append(f"| `{row['window']}` | {metric_line(row)} |")
    lines.extend(
        [
            "",
            "## 字段分类",
            "",
            "| Component | Field | Baseline | Classification | Variants | Component Equal | Merged Equal | Strict Improve |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in fields_frame.to_dict(orient="records"):
        lines.append(
            f"| `{row['component']}` | `{row['field']}` | `{row['baseline_value']}` | "
            f"`{row['classification']}` | `{row['variant_rows']}` | "
            f"`{row['component_path_equal_rows']}` | `{row['merged_path_equal_rows']}` | "
            f"`{row['prefit_strict_improve_rows']}` |"
        )
    if not strict.empty:
        lines.extend(
            [
                "",
                "## 相对 V2.1 严格改善单字段 Top 10",
                "",
                "| Label | Prefit annual | Prefit DD | Prefit win | Full annual | Full DD | Full win |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in strict.head(10).to_dict(orient="records"):
            lines.append(
                f"| `{row['label']}` | `{row['prefit_annual_multiple']:.4f}x` | "
                f"`{row['prefit_max_dd']:.2%}` | `{row['prefit_win_rate']:.2%}` | "
                f"`{row['current_full_annual_multiple']:.4f}x` | "
                f"`{row['current_full_max_dd']:.2%}` | `{row['current_full_win_rate']:.2%}` |"
            )
    lines.extend(
        [
            "",
            "## 删参结论",
            "",
            f"- bb_break inert 字段：`{inert_fields['bb_break'] or '无'}`。",
            f"- rsi_reversal inert 字段：`{inert_fields['rsi_reversal'] or '无'}`。",
            "- inert 字段在 V2.1 clean interface 中硬编码为 V2.1 冻结值，不进入后续微调搜索面。",
            "",
            "## 机器证据",
            "",
            f"- `artifacts/{SUMMARY_JSON.name}`",
            f"- `artifacts/{ROWS_CSV.name}`",
            f"- `artifacts/{FIELDS_CSV.name}`",
            f"- `artifacts/{SLICES_CSV.name}`",
            "",
            "复现：",
            "",
            "```bash",
            "uv run python research/eth/1h-adaptive-regime/scripts/research_eth_1h_ar_v2_1_full_ablation.py",
            "```",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(
        json.dumps(
            json_safe(
                {
                    "inert_fields": inert_fields,
                    "active_tunable_counts": payload["active_tunable_counts"],
                    "ablation_rows_including_baseline": len(rows_frame),
                    "prefit_strict_improve_rows": len(strict),
                }
            ),
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
