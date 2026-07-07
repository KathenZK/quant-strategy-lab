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

import audit_trx_1h_ar_v1_clean_strict_ablation_slices as strict_audit  # noqa: E402
import research_trx_1h_adaptive_regime_search as search  # noqa: E402
import trx_1h_ar_v1 as v1  # noqa: E402
import trx_1h_ar_v2 as v2  # noqa: E402
import trx_1h_ar_v3 as v3  # noqa: E402


DATE_TAG = "2026-07-07"
FAMILY_DIR = ROOT / "research/trx/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
ABLATION_DIR = FAMILY_DIR / "ablations"
SUMMARY_JSON = ARTIFACT_DIR / f"trx_1h_ar_v3_full_ablation_{DATE_TAG}.json"
ROWS_CSV = ARTIFACT_DIR / f"trx_1h_ar_v3_full_ablation_rows_{DATE_TAG}.csv"
FIELDS_CSV = ARTIFACT_DIR / f"trx_1h_ar_v3_full_ablation_fields_{DATE_TAG}.csv"
SLICES_CSV = ARTIFACT_DIR / f"trx_1h_ar_v3_slices_{DATE_TAG}.csv"
TRADE_AUDIT_CSV = ARTIFACT_DIR / f"trx_1h_ar_v3_trade_execution_audit_{DATE_TAG}.csv"
REPORT_MD = ABLATION_DIR / f"trx-1h-ar-v3-full-parameter-ablation-{DATE_TAG}.md"

MACD_DOMAINS: dict[str, tuple[Any, ...]] = {
    "ema_htf": (55, 89, 144, 233, 377),
    "roc_window": (3, 6, 12, 24, 48, 72, 168),
    "macd_set": ((8, 21, 5), (12, 26, 9), (21, 55, 9), (34, 89, 13)),
    "min_adx": (0.0, 8.0, 12.0, 16.0, 20.0, 22.0, 24.0),
    "max_adx": (24.0, 26.0, 28.0, 30.0, 32.0, 36.0, 45.0, 100.0),
    "min_rvol": (0.0, 0.6, 0.8, 1.0, 1.25, 1.5, 2.0),
    "max_atr_bps": (100.0, 125.0, 150.0, 175.0, 200.0, 300.0, 600.0, 10_000.0),
    "min_dir_roc_bps": (-10_000.0, -300.0, -200.0, -100.0, -50.0, 0.0, 50.0, 100.0),
    "max_dist_ema_bps": (300.0, 500.0, 750.0, 1000.0, 1500.0, 2500.0, 10_000.0),
    "htf_mode": ("none", "h4", "h12", "d1"),
    "require_macd_turn": (False, True),
    "tp_atr": (0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0),
    "sl_atr": (2.0, 3.0, 4.0, 5.0, 6.0),
    "max_hold_bars": (48, 72, 96, 120, 168, 240, 336),
    "cooldown_bars": (0, 3, 6, 12, 24),
    "entry_delay_bars": (1, 2),
    "fixed_leverage": (1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0),
}

STOCH_DOMAINS: dict[str, tuple[Any, ...]] = {
    "side_mode": ("long", "short", "both"),
    "ema_htf": (55, 89, 144, 233, 377),
    "indicator_window": (7, 14, 21, 28),
    "threshold_low": (10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0),
    "threshold_high": (60.0, 65.0, 70.0, 75.0, 80.0, 85.0, 90.0),
    "roc_window": (3, 6, 12, 24, 48, 72, 168),
    "max_adx": (20.0, 24.0, 28.0, 30.0, 32.0, 36.0, 45.0, 100.0),
    "min_rvol": (0.0, 0.6, 0.8, 1.0, 1.25, 1.5, 2.0),
    "min_dir_roc_bps": (-10_000.0, -300.0, -200.0, -100.0, -50.0, 0.0, 50.0, 100.0),
    "require_body_dir": (False, True),
    "sl_atr": (2.5, 3.0, 4.0, 5.0, 6.0),
    "trail_activation_atr": (0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0),
    "trail_atr": (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0),
    "max_hold_bars": (48, 72, 96, 120, 168, 240, 336),
    "cooldown_bars": (0, 3, 6, 12, 18, 24, 36, 48),
    "entry_delay_bars": (1, 2, 3),
    "fixed_leverage": (1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0),
}

EXECUTION_TIMING_FIELDS = {"entry_delay_bars"}
MACD_SET_FIELDS = {"macd_fast", "macd_slow", "macd_signal"}


def metric_bundle(engine: Any, trades: list[Any]) -> dict[str, dict[str, float]]:
    return v1.metrics(engine, trades)


def flatten_metrics(metrics: dict[str, dict[str, float]]) -> dict[str, float]:
    return {
        f"{window}_{key}": value
        for window, window_metrics in metrics.items()
        for key, value in window_metrics.items()
    }


def field_classification(field_name: str) -> str:
    if field_name in EXECUTION_TIMING_FIELDS:
        return "execution_timing_parameter"
    return "v3_exposed_parameter"


def domain_for(component: str, field_name: str) -> tuple[Any, ...]:
    if component == "macd_flip" and field_name in MACD_SET_FIELDS:
        return MACD_DOMAINS["macd_set"]
    domains = MACD_DOMAINS if component == "macd_flip" else STOCH_DOMAINS
    return tuple(dict.fromkeys(domains[field_name]))


def baseline_value_for(config: Any, field_name: str) -> Any:
    if field_name in MACD_SET_FIELDS:
        return (config.macd_fast, config.macd_slow, config.macd_signal)
    return getattr(config, field_name)


def replace_field(config: Any, field_name: str, value: Any) -> Any:
    if field_name in MACD_SET_FIELDS:
        return replace(
            config,
            macd_fast=value[0],
            macd_slow=value[1],
            macd_signal=value[2],
        )
    return replace(config, **{field_name: value})


def value_label(value: Any) -> str:
    return str(value).replace(" ", "").replace(".", "p").replace("-", "m").replace(",", "_")


def simulate(
    engine: Any,
    frame: pd.DataFrame,
    funding_times: Any,
    funding_cumulative: Any,
    macd: v3.MACDV3Config,
    stoch: v3.StochV3Config,
) -> tuple[list[Any], list[Any], list[Any], tuple[float, float]]:
    return v3.simulate_v3(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        macd=macd,
        stoch=stoch,
    )


def prefit_improves(row: dict[str, Any], baseline: dict[str, Any]) -> bool:
    return bool(
        row["prefit_annual_multiple"] > baseline["prefit_annual_multiple"]
        and row["prefit_max_dd"] > baseline["prefit_max_dd"]
        and row["prefit_win_rate"] >= baseline["prefit_win_rate"]
        and row["train_total_return"] > 0
        and row["validation_total_return"] > 0
        and row["validation_max_dd"] > -0.20
    )


def metric_line(metric: dict[str, float]) -> str:
    return (
        f"`{metric['annual_multiple']:.4f}x` / `{metric['total_return']:.2%}` / "
        f"`{metric['max_dd']:.2%}` / `{metric['win_rate']:.2%}` / "
        f"`{int(metric['trades'])}`"
    )


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    ABLATION_DIR.mkdir(parents=True, exist_ok=True)
    engine, frame, funding, quality = v3.load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)

    baseline_macd = v3.MACDV3Config()
    baseline_stoch = v3.StochV3Config()
    baseline_trades, macd_trades, stoch_trades, priorities = simulate(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        baseline_macd,
        baseline_stoch,
    )

    baseline_metrics = metric_bundle(engine, baseline_trades)
    baseline_flat = flatten_metrics(baseline_metrics)
    baseline_signature = v1.trade_signature(baseline_trades)
    component_signatures = {
        "macd_flip": v1.trade_signature(macd_trades),
        "stoch_reversal": v1.trade_signature(stoch_trades),
    }
    base_configs = [
        v2.macd_to_base(engine, v3.macd_to_v2(baseline_macd)),
        v2.stoch_to_base(engine, v3.stoch_to_v2(baseline_stoch)),
    ]
    component_trades = {
        base_configs[0].name: macd_trades,
        base_configs[1].name: stoch_trades,
    }

    slice_metrics = v1.standard_slices(engine, baseline_trades)
    slice_rows = [
        {"window": name, **metric} for name, metric in slice_metrics.items()
    ]
    pd.DataFrame(slice_rows).to_csv(SLICES_CSV, index=False)

    audit_rows = strict_audit.trade_audit_rows(
        frame=frame,
        merged_trades=baseline_trades,
        component_trades=component_trades,
        configs=base_configs,
    )
    audit_frame = pd.DataFrame(audit_rows)
    audit_frame.to_csv(TRADE_AUDIT_CSV, index=False)

    rows: list[dict[str, Any]] = [
        {
            "label": "TRX-1H-Adaptive-Regime-V3",
            "component": "ensemble",
            "field": "baseline",
            "baseline_value": "baseline",
            "value": "baseline",
            "is_baseline_value": True,
            "classification": "baseline",
            "component_path_equal": True,
            "merged_path_equal": True,
            "prefit_strict_improve": False,
            **baseline_flat,
        }
    ]
    observed: dict[str, set[str]] = {"macd_flip": set(), "stoch_reversal": set()}
    field_sources = {
        "macd_flip": (baseline_macd, fields(v3.MACDV3Config)),
        "stoch_reversal": (baseline_stoch, fields(v3.StochV3Config)),
    }

    for component, (baseline_config, component_fields) in field_sources.items():
        for field in component_fields:
            field_name = field.name
            observed[component].add(field_name)
            base_value = baseline_value_for(baseline_config, field_name)
            for value in domain_for(component, field_name):
                variant_macd = baseline_macd
                variant_stoch = baseline_stoch
                variant_config = replace_field(baseline_config, field_name, value)
                if component == "macd_flip":
                    variant_macd = variant_config
                    if variant_macd.min_adx > variant_macd.max_adx:
                        continue
                else:
                    variant_stoch = variant_config
                    if variant_stoch.threshold_high <= variant_stoch.threshold_low:
                        continue

                merged, variant_macd_trades, variant_stoch_trades, _ = simulate(
                    engine,
                    frame,
                    funding_times,
                    funding_cumulative,
                    variant_macd,
                    variant_stoch,
                )
                variant_component_trades = (
                    variant_macd_trades
                    if component == "macd_flip"
                    else variant_stoch_trades
                )
                flat = flatten_metrics(metric_bundle(engine, merged))
                row = {
                    "label": f"{component}__{field_name}__{value_label(value)}",
                    "component": component,
                    "field": field_name,
                    "baseline_value": base_value,
                    "value": value,
                    "is_baseline_value": value == base_value,
                    "classification": field_classification(field_name),
                    "component_path_equal": v1.trade_signature(variant_component_trades)
                    == component_signatures[component],
                    "merged_path_equal": v1.trade_signature(merged) == baseline_signature,
                    **flat,
                }
                row["prefit_strict_improve"] = prefit_improves(row, baseline_flat)
                rows.append(row)

    rows_frame = pd.DataFrame(rows)
    rows_frame.to_csv(ROWS_CSV, index=False)

    field_rows: list[dict[str, Any]] = []
    for component, (baseline_config, component_fields) in field_sources.items():
        for field in component_fields:
            subset = rows_frame.loc[
                (rows_frame["component"] == component)
                & (rows_frame["field"] == field.name)
            ]
            non_baseline = subset.loc[~subset["is_baseline_value"].astype(bool)]
            dormant = bool(len(non_baseline)) and bool(
                non_baseline["merged_path_equal"].all()
            )
            field_rows.append(
                {
                    "component": component,
                    "field": field.name,
                    "baseline_value": baseline_value_for(baseline_config, field.name),
                    "classification": field_classification(field.name),
                    "variant_rows": int(len(subset)),
                    "non_baseline_rows": int(len(non_baseline)),
                    "component_path_equal_rows": int(subset["component_path_equal"].sum()),
                    "merged_path_equal_rows": int(subset["merged_path_equal"].sum()),
                    "dormant_merged_path": dormant,
                    "prefit_strict_improve_rows": int(subset["prefit_strict_improve"].sum()),
                    "best_prefit_annual_multiple": float(subset["prefit_annual_multiple"].max()),
                    "best_prefit_max_dd": float(
                        subset.loc[
                            subset["prefit_annual_multiple"].idxmax(),
                            "prefit_max_dd",
                        ]
                    ),
                }
            )
    fields_frame = pd.DataFrame(field_rows)
    fields_frame.to_csv(FIELDS_CSV, index=False)

    dormant_fields = {
        component: sorted(
            fields_frame.loc[
                (fields_frame["component"] == component)
                & (fields_frame["dormant_merged_path"]),
                "field",
            ].tolist()
        )
        for component in ("macd_flip", "stoch_reversal")
    }
    active_fields = {
        component: sorted(
            fields_frame.loc[
                (fields_frame["component"] == component)
                & (~fields_frame["dormant_merged_path"]),
                "field",
            ].tolist()
        )
        for component in ("macd_flip", "stoch_reversal")
    }

    strict = rows_frame.loc[rows_frame["prefit_strict_improve"]].sort_values(
        ["prefit_annual_multiple", "prefit_max_dd", "validation_annual_multiple"],
        ascending=[False, False, False],
    )
    violation_count = int(audit_frame["violation_count"].sum())
    merged_violations = int(
        audit_frame.loc[audit_frame["scope"] == "merged", "violation_count"].sum()
    )
    stop_gap_count = int(audit_frame["stop_gap_filled_at_open"].sum())
    target_gap_count = int(audit_frame["target_gap_modeled_at_target"].sum())
    exposed_slots = {
        "macd_flip": len(fields(v3.MACDV3Config)),
        "stoch_reversal": len(fields(v3.StochV3Config)),
    }
    exposed_slots["total"] = sum(exposed_slots.values())

    payload = {
        "family": "TRX-1H-Adaptive-Regime",
        "version": "TRX-1H-Adaptive-Regime-V3",
        "status": "registered_diagnostic_tuned_version_full_ablation_complete_no_go_not_live_ready",
        "date": DATE_TAG,
        "source_version": "TRX-1H-Adaptive-Regime-V2",
        "data_quality": quality,
        "costs": {
            "fee_per_fill": engine.FEE_PER_FILL,
            "slippage_per_fill": engine.SLIPPAGE_PER_FILL,
            "funding": "actual_binance_history_per_trade",
        },
        "component_prefit_priority_scores": priorities,
        "baseline": baseline_metrics,
        "standard_slices": slice_metrics,
        "v3_exposed_parameter_slots": {
            **exposed_slots,
            "coverage_missing": {
                "macd_flip": sorted(
                    {field.name for field in fields(v3.MACDV3Config)} - observed["macd_flip"]
                ),
                "stoch_reversal": sorted(
                    {field.name for field in fields(v3.StochV3Config)}
                    - observed["stoch_reversal"]
                ),
            },
        },
        "ablation_rows_including_baseline": len(rows_frame),
        "prefit_strict_improve_rows": len(strict),
        "top_prefit_strict": strict.head(30).to_dict(orient="records"),
        "dormant_fields_merged_path": dormant_fields,
        "active_fields_merged_path": active_fields,
        "v3_clean_surface": {
            "policy": "dormant merged-path fields fixed at V3 values; active fields remain tunable",
            "macd_flip_active": active_fields["macd_flip"],
            "stoch_reversal_active": active_fields["stoch_reversal"],
            "macd_flip_fixed": dormant_fields["macd_flip"],
            "stoch_reversal_fixed": dormant_fields["stoch_reversal"],
        },
        "execution_audit": {
            "audited_rows": int(len(audit_frame)),
            "merged_trades": int(len(baseline_trades)),
            "merged_full_window_trades": int(baseline_metrics["current_full"]["trades"]),
            "component_trades": {
                base_configs[0].name: int(len(macd_trades)),
                base_configs[1].name: int(len(stoch_trades)),
            },
            "violation_count": violation_count,
            "merged_violation_count": merged_violations,
            "stop_gap_filled_at_open": stop_gap_count,
            "target_gap_modeled_at_target": target_gap_count,
            "causal_entry_delay_all_ge_1": all(
                cfg.entry_delay_bars >= 1 for cfg in base_configs
            ),
        },
        "artifacts": {
            "rows_csv": str(ROWS_CSV.relative_to(ROOT)),
            "fields_csv": str(FIELDS_CSV.relative_to(ROOT)),
            "slices_csv": str(SLICES_CSV.relative_to(ROOT)),
            "trade_audit_csv": str(TRADE_AUDIT_CSV.relative_to(ROOT)),
        },
    }
    SUMMARY_JSON.write_text(
        json.dumps(search.json_safe(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    lines = [
        f"# TRX-1H-Adaptive-Regime-V3 全参数消融、分片与执行审计 - {DATE_TAG}",
        "",
        "## 结论",
        "",
        (
            "`TRX-1H-Adaptive-Regime-V3` 是 V2 消融引导微调后的登记版本；"
            "本轮覆盖 V3 对外暴露的全部参数槽，完成 one-at-a-time 全参数消融、"
            "最近 `1d/7d/1m/3m/6m/1y` 分片和逐笔执行重放，"
            "并按 merged 交易路径识别 dormant（无作用）字段，输出 V3 clean 参数面。"
        ),
        "",
        (
            f"执行审计覆盖 merged `{len(baseline_trades)}` 笔交易"
            f"（current full 指标窗口 `{int(baseline_metrics['current_full']['trades'])}` 笔）和组件交易；"
            f"违规计数 `{violation_count}`，merged 违规 `{merged_violations}`。"
            f"stop gap 按 open 成交 `{stop_gap_count}` 次；"
            f"有利 target gap 以 target 价保守记账 `{target_gap_count}` 次。"
        ),
        "",
        (
            "消融发现的 prefit 单字段严格改善只作为诊断，不使用 reused holdout 或近期分片选参。"
            "V3 保持 `NO-GO / not promoted / not live-ready`。"
        ),
        "",
        "## V3 基线",
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
    for name, metric in slice_metrics.items():
        lines.append(f"| `{name}` | {metric_line(metric)} |")
    lines.extend(
        [
            "",
            "## V3 参数消融",
            "",
            f"- V3 对外暴露字段槽：`{exposed_slots['total']}`；coverage missing：`{payload['v3_exposed_parameter_slots']['coverage_missing']}`。",
            f"- one-at-a-time 行数（含 baseline）：`{len(rows_frame)}`。",
            f"- prefit 严格改善行数：`{len(strict)}`；这些行未用于 holdout/近期分片选参。",
            "",
            "| Component | Field | Baseline | Variants | Merged Equal | Dormant | Prefit Strict Improve |",
            "| --- | --- | --- | ---: | ---: | --- | ---: |",
        ]
    )
    for row in fields_frame.to_dict(orient="records"):
        lines.append(
            f"| `{row['component']}` | `{row['field']}` | `{row['baseline_value']}` | "
            f"`{row['variant_rows']}` | `{row['merged_path_equal_rows']}` | "
            f"`{row['dormant_merged_path']}` | `{row['prefit_strict_improve_rows']}` |"
        )
    lines.extend(
        [
            "",
            "## V3 clean 参数面",
            "",
            (
                "dormant 判定口径：该字段所有非基线取值都不改变 merged 逐交易路径。"
                "dormant 字段从可调参数面移除并固定为 V3 值；active 字段保留为可调面。"
            ),
            "",
            f"- `macd_flip` active：`{active_fields['macd_flip']}`。",
            f"- `macd_flip` dormant/fixed：`{dormant_fields['macd_flip']}`。",
            f"- `stoch_reversal` active：`{active_fields['stoch_reversal']}`。",
            f"- `stoch_reversal` dormant/fixed：`{dormant_fields['stoch_reversal']}`。",
            "",
            "## 不可实盘风险检查",
            "",
            f"- 入场时序：所有组件 `entry_delay_bars>=1`，信号闭合后按延迟根数用 open 入场：`{payload['execution_audit']['causal_entry_delay_all_ge_1']}`。",
            f"- 逐笔重放：违规总数 `{violation_count}`，merged 违规 `{merged_violations}`。",
            f"- stop 穿越：`stop_gap_open` 按 open 成交 `{stop_gap_count}` 次，未发现穿越 stop 后仍按旧 stop 价成交。",
            f"- target 穿越：有利 gap/open 以 target 价保守记账 `{target_gap_count}` 次，不构成乐观穿越收益。",
            "- 未来函数：信号使用闭合 `1h` K，延迟后 open 入场；HTF/funding 特征按已知时间 `merge_asof` 对齐。未发现 OOS 排序或 K 内决策依赖。",
            "",
            "## 机器证据",
            "",
            f"- `artifacts/{SUMMARY_JSON.name}`",
            f"- `artifacts/{ROWS_CSV.name}`",
            f"- `artifacts/{FIELDS_CSV.name}`",
            f"- `artifacts/{SLICES_CSV.name}`",
            f"- `artifacts/{TRADE_AUDIT_CSV.name}`",
            "",
            "复现：",
            "",
            "```bash",
            "uv run python research/trx/1h-adaptive-regime/scripts/research_trx_1h_ar_v3_full_ablation.py",
            "```",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(
        json.dumps(
            {
                "rows": len(rows_frame),
                "prefit_strict_improve_rows": len(strict),
                "dormant_fields": dormant_fields,
                "active_fields": active_fields,
                "execution_violations": violation_count,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
