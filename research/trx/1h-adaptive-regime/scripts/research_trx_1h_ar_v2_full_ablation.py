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


DATE_TAG = "2026-07-06"
FAMILY_DIR = ROOT / "research/trx/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
ABLATION_DIR = FAMILY_DIR / "ablations"
SUMMARY_JSON = ARTIFACT_DIR / f"trx_1h_ar_v2_full_ablation_{DATE_TAG}.json"
ROWS_CSV = ARTIFACT_DIR / f"trx_1h_ar_v2_full_ablation_rows_{DATE_TAG}.csv"
FIELDS_CSV = ARTIFACT_DIR / f"trx_1h_ar_v2_full_ablation_fields_{DATE_TAG}.csv"
SLICES_CSV = ARTIFACT_DIR / f"trx_1h_ar_v2_slices_{DATE_TAG}.csv"
TRADE_AUDIT_CSV = ARTIFACT_DIR / f"trx_1h_ar_v2_trade_execution_audit_{DATE_TAG}.csv"
REPORT_MD = ABLATION_DIR / f"trx-1h-ar-v2-full-parameter-ablation-{DATE_TAG}.md"

MACD_DOMAINS: dict[str, tuple[Any, ...]] = {
    "ema_htf": (55, 89, 144, 233, 377),
    "roc_window": (3, 6, 12, 24, 48, 72, 168),
    "macd_set": ((8, 21, 5), (12, 26, 9), (21, 55, 9), (34, 89, 13)),
    "min_adx": (0.0, 8.0, 12.0, 16.0, 20.0, 24.0),
    "max_adx": (24.0, 28.0, 30.0, 32.0, 36.0, 45.0, 100.0),
    "min_rvol": (0.0, 0.6, 0.8, 1.0, 1.25, 1.5, 2.0),
    "max_atr_bps": (150.0, 175.0, 200.0, 250.0, 300.0, 400.0, 600.0, 10_000.0),
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
    "side_mode": ("long", "both"),
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
    "cooldown_bars": (0, 6, 12, 18, 24, 36, 48),
    "entry_delay_bars": (1, 2, 3),
    "fixed_leverage": (1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0),
}

EXECUTION_TIMING_FIELDS = {"entry_delay_bars"}


def metric_bundle(engine: Any, trades: list[Any]) -> dict[str, dict[str, float]]:
    return {
        "train": engine.metrics(trades, v1.TRAIN_START, v1.TRAIN_END),
        "validation": engine.metrics(trades, v1.TRAIN_END, v1.PREFIT_END),
        "prefit": engine.metrics(trades, v1.TRAIN_START, v1.PREFIT_END),
        "holdout": engine.metrics(trades, v1.PREFIT_END, v1.FULL_END),
        "full": engine.metrics(trades, v1.TRAIN_START, v1.FULL_END),
    }


def flatten_metrics(metrics: dict[str, dict[str, float]]) -> dict[str, float]:
    return {
        f"{window}_{key}": value
        for window, window_metrics in metrics.items()
        for key, value in window_metrics.items()
    }


def strict_slice_rows(engine: Any, trades: list[Any]) -> list[dict[str, Any]]:
    windows = [
        ("last_1d", v1.FULL_END - pd.Timedelta(days=1)),
        ("last_7d", v1.FULL_END - pd.Timedelta(days=7)),
        ("last_1m", v1.FULL_END - pd.DateOffset(months=1)),
        ("last_3m", v1.FULL_END - pd.DateOffset(months=3)),
        ("last_6m", v1.FULL_END - pd.DateOffset(months=6)),
        ("last_1y", v1.FULL_END - pd.DateOffset(years=1)),
    ]
    return [
        {"window": name, "start": start, "end": v1.FULL_END, **engine.metrics(trades, start, v1.FULL_END)}
        for name, start in windows
    ]


def field_classification(field_name: str) -> str:
    if field_name in EXECUTION_TIMING_FIELDS:
        return "execution_timing_parameter"
    return "v2_exposed_parameter"


def domain_for(component: str, field_name: str) -> tuple[Any, ...]:
    if component == "macd_flip" and field_name in {"macd_fast", "macd_slow", "macd_signal"}:
        return MACD_DOMAINS["macd_set"]
    domains = MACD_DOMAINS if component == "macd_flip" else STOCH_DOMAINS
    return tuple(dict.fromkeys(domains[field_name]))


def replace_field(config: Any, field_name: str, value: Any) -> Any:
    if field_name in {"macd_fast", "macd_slow", "macd_signal"}:
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
    macd: v2.MACDV2Config,
    stoch: v2.StochV2Config,
) -> tuple[list[Any], list[Any], list[Any], tuple[float, float]]:
    return v2.simulate_v2(
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
        and row["prefit_win_rate"] >= 0.50
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
    engine, frame, funding, quality = v2.load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)

    baseline_macd = v2.MACDV2Config()
    baseline_stoch = v2.StochV2Config()
    baseline_trades, macd_trades, stoch_trades, priorities = simulate(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        baseline_macd,
        baseline_stoch,
    )
    v1_trades, *_ = v1.simulate_v1(engine, frame, funding_times, funding_cumulative)
    if v1.trade_signature(v1_trades) != v1.trade_signature(baseline_trades):
        raise RuntimeError("V2 baseline drifted from V1 trade path")

    baseline_metrics = metric_bundle(engine, baseline_trades)
    baseline_flat = flatten_metrics(baseline_metrics)
    baseline_signature = v1.trade_signature(baseline_trades)
    component_signatures = {
        "macd_flip": v1.trade_signature(macd_trades),
        "stoch_reversal": v1.trade_signature(stoch_trades),
    }
    base_configs = [
        v2.macd_to_base(engine, baseline_macd),
        v2.stoch_to_base(engine, baseline_stoch),
    ]
    component_trades = {
        base_configs[0].name: macd_trades,
        base_configs[1].name: stoch_trades,
    }

    slice_rows = strict_slice_rows(engine, baseline_trades)
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
            "label": "TRX-1H-Adaptive-Regime-V2",
            "component": "ensemble",
            "field": "baseline",
            "baseline_value": "baseline",
            "value": "baseline",
            "classification": "baseline",
            "component_path_equal": True,
            "merged_path_equal": True,
            "prefit_strict_improve": False,
            **baseline_flat,
        }
    ]
    observed: dict[str, set[str]] = {"macd_flip": set(), "stoch_reversal": set()}
    field_sources = {
        "macd_flip": (baseline_macd, fields(v2.MACDV2Config)),
        "stoch_reversal": (baseline_stoch, fields(v2.StochV2Config)),
    }

    for component, (baseline_config, component_fields) in field_sources.items():
        for field in component_fields:
            field_name = field.name
            observed[component].add(field_name)
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
                    "baseline_value": getattr(baseline_config, field_name),
                    "value": value,
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
            field_rows.append(
                {
                    "component": component,
                    "field": field.name,
                    "baseline_value": getattr(baseline_config, field.name),
                    "classification": field_classification(field.name),
                    "variant_rows": int(len(subset)),
                    "component_path_equal_rows": int(subset["component_path_equal"].sum()),
                    "merged_path_equal_rows": int(subset["merged_path_equal"].sum()),
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
        "macd_flip": len(fields(v2.MACDV2Config)),
        "stoch_reversal": len(fields(v2.StochV2Config)),
    }
    exposed_slots["total"] = sum(exposed_slots.values())

    payload = {
        "family": "TRX-1H-Adaptive-Regime",
        "version": "TRX-1H-Adaptive-Regime-V2",
        "status": "registered_clean_parameter_version_full_ablation_complete_no_go_not_live_ready",
        "date": DATE_TAG,
        "source_version": "TRX-1H-Adaptive-Regime-V1",
        "trade_path_equal_to_v1": True,
        "data_quality": quality,
        "costs": {
            "fee_per_fill": engine.FEE_PER_FILL,
            "slippage_per_fill": engine.SLIPPAGE_PER_FILL,
            "funding": "actual_binance_history_per_trade",
        },
        "component_prefit_priority_scores": priorities,
        "baseline": baseline_metrics,
        "strict_slices": {
            row["window"]: {
                "annual_multiple": row["annual_multiple"],
                "total_return": row["total_return"],
                "max_dd": row["max_dd"],
                "win_rate": row["win_rate"],
                "trades": row["trades"],
            }
            for row in slice_rows
        },
        "v2_exposed_parameter_slots": {
            **exposed_slots,
            "coverage_missing": {
                "macd_flip": sorted(
                    {field.name for field in fields(v2.MACDV2Config)} - observed["macd_flip"]
                ),
                "stoch_reversal": sorted(
                    {field.name for field in fields(v2.StochV2Config)}
                    - observed["stoch_reversal"]
                ),
            },
        },
        "ablation_rows_including_baseline": len(rows_frame),
        "prefit_strict_improve_rows": len(strict),
        "top_prefit_strict": strict.head(30).to_dict(orient="records"),
        "execution_audit": {
            "audited_rows": int(len(audit_frame)),
            "merged_trades": int(len(baseline_trades)),
            "merged_full_window_trades": int(baseline_metrics["full"]["trades"]),
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
        "# TRX-1H-Adaptive-Regime-V2 全参数消融、分片与执行审计 - 2026-07-06",
        "",
        "## 结论",
        "",
        (
            "`TRX-1H-Adaptive-Regime-V2` 是 V1 clean-equivalent 参数面正式登记后的干净参数版本；"
            "本轮覆盖 V2 对外暴露的全部 clean 参数槽，完成 one-at-a-time 全参数消融、"
            "最近 `1d/7d/1m/3m/6m/1y` 分片和逐笔执行重放。"
        ),
        "",
        (
            f"V2 与 V1 逐交易路径完全一致；执行审计覆盖 merged `{len(baseline_trades)}` 笔交易"
            f"（full 指标窗口 `{int(baseline_metrics['full']['trades'])}` 笔）和组件交易；"
            f"违规计数 `{violation_count}`，merged 违规 `{merged_violations}`。"
            f"stop gap 按 open 成交 `{stop_gap_count}` 次；"
            f"有利 target gap 以 target 价保守记账 `{target_gap_count}` 次。"
        ),
        "",
        (
            "消融发现若干 prefit 单字段严格改善，但这些只用于诊断，不使用 reused holdout 或近期分片选参。"
            "V2 仍因收益目标、reused holdout、近期分片和 production runner 失败保持 "
            "`NO-GO / not promoted / not live-ready`。"
        ),
        "",
        "## V2 基线",
        "",
        "| Window | Annual / Return / DD / Win / Trades |",
        "| --- | --- |",
    ]
    for window in ("train", "validation", "prefit", "holdout", "full"):
        lines.append(f"| `{window}` | {metric_line(baseline_metrics[window])} |")
    lines.extend(
        [
            "",
            "## 严格近期分片",
            "",
            "| Slice | UTC Start | Annual / Return / DD / Win / Trades |",
            "| --- | --- | --- |",
        ]
    )
    for row in slice_rows:
        lines.append(f"| `{row['window']}` | `{row['start']}` | {metric_line(row)} |")
    lines.extend(
        [
            "",
            "## V2 参数消融",
            "",
            f"- V2 对外暴露 clean 字段槽：`{exposed_slots['total']}`；coverage missing：`{payload['v2_exposed_parameter_slots']['coverage_missing']}`。",
            f"- one-at-a-time 行数（含 baseline）：`{len(rows_frame)}`。",
            f"- prefit 严格改善行数：`{len(strict)}`；这些行未用于 holdout/近期分片选参。",
            "",
            "| Component | Field | Baseline | Classification | Variants | Component Equal | Merged Equal | Prefit Strict Improve |",
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
    lines.extend(
        [
            "",
            "## 不可实盘风险检查",
            "",
            f"- 入场时序：所有组件 `entry_delay_bars>=1`，信号闭合后下一根 open 入场：`{payload['execution_audit']['causal_entry_delay_all_ge_1']}`。",
            f"- 逐笔重放：违规总数 `{violation_count}`，merged 违规 `{merged_violations}`。",
            f"- stop 穿越：`stop_gap_open` 按 open 成交 `{stop_gap_count}` 次，未发现穿越 stop 后仍按旧 stop 价成交。",
            f"- target 穿越：有利 gap/open 以 target 价保守记账 `{target_gap_count}` 次，不构成乐观穿越收益。",
            "- 未来函数：信号使用闭合 `1h` K，`K+1 open` 入场；HTF/funding 特征按已知时间 `merge_asof` 对齐。未发现 OOS 排序或 K 内决策依赖。",
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
            "uv run python research/trx/1h-adaptive-regime/scripts/research_trx_1h_ar_v2_full_ablation.py",
            "```",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(search.json_safe(payload), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
