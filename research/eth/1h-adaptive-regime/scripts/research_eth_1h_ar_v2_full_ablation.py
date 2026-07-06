from __future__ import annotations

import json
import sys
from dataclasses import asdict, fields, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import eth_1h_ar_v1 as v1  # noqa: E402
import eth_1h_ar_v2 as v2  # noqa: E402


DATE_TAG = "2026-07-06"
FAMILY_DIR = ROOT / "research/eth/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
ABLATION_DIR = FAMILY_DIR / "ablations"
SUMMARY_JSON = ARTIFACT_DIR / f"eth_1h_ar_v2_full_ablation_{DATE_TAG}.json"
ROWS_CSV = ARTIFACT_DIR / f"eth_1h_ar_v2_full_ablation_rows_{DATE_TAG}.csv"
FIELDS_CSV = ARTIFACT_DIR / f"eth_1h_ar_v2_full_ablation_fields_{DATE_TAG}.csv"
SLICES_CSV = ARTIFACT_DIR / f"eth_1h_ar_v2_slices_{DATE_TAG}.csv"
REPORT_MD = ABLATION_DIR / f"eth-1h-ar-v2-full-parameter-ablation-{DATE_TAG}.md"

WIN_FLOOR = 0.80
DD_FLOOR = -0.20

BB_DOMAINS: dict[str, tuple[Any, ...]] = {
    "ema_htf": (55, 89, 144, 233, 377),
    "indicator_window": (12, 20, 32, 48, 72, 96),
    "band_k": (1.5, 1.75, 2.0, 2.25, 2.5, 3.0),
    "roc_window": (6, 12, 24, 48, 72),
    "min_adx": (0.0, 16.0, 20.0, 24.0, 28.0, 32.0, 36.0),
    "min_rvol": (0.8, 1.0, 1.5, 2.0, 2.5, 3.0),
    "min_atr_bps": (0.0, 50.0, 75.0, 100.0, 125.0),
    "min_dir_roc_bps": (-10_000.0, -300.0, -200.0, -100.0, 0.0, 100.0, 200.0),
    "max_dist_ema_bps": (500.0, 750.0, 1000.0, 1500.0, 2500.0, 10_000.0),
    "max_aligned_funding_bps": (1.0, 2.0, 4.0, 8.0, 10_000.0),
    "tp_atr": (2.0, 2.5, 3.0, 3.5, 4.0, 5.0),
    "sl_atr": (1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0),
    "max_hold_bars": (12, 18, 24, 36, 48, 72),
    "fixed_leverage": (1.0, 1.5, 2.0, 2.5, 3.0, 3.5),
}

RSI_DOMAINS: dict[str, tuple[Any, ...]] = {
    "ema_htf": (89, 144, 233, 377),
    "indicator_window": (5, 7, 9, 14, 21),
    "threshold_low": (5.0, 10.0, 15.0, 20.0, 25.0, 30.0),
    "threshold_high": (55.0, 60.0, 65.0, 70.0, 75.0, 80.0),
    "roc_window": (3, 6, 12, 24, 48),
    "min_adx": (0.0, 8.0, 12.0, 16.0, 20.0, 24.0, 28.0),
    "max_adx": (30.0, 36.0, 45.0, 55.0, 100.0),
    "min_atr_bps": (0.0, 50.0, 75.0, 100.0, 125.0, 150.0),
    "min_dir_roc_bps": (-10_000.0, -300.0, -100.0, 0.0, 50.0, 100.0, 200.0),
    "max_dist_ema_bps": (500.0, 750.0, 1000.0, 1500.0, 2500.0, 10_000.0),
    "tp_atr": (1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0),
    "sl_atr": (1.0, 1.5, 2.0, 2.5, 3.0),
    "max_hold_bars": (6, 12, 18, 24, 36, 48),
    "cooldown_bars": (0, 3, 6, 12, 24),
    "fixed_leverage": (0.5, 1.0, 1.5, 2.0, 2.5),
}


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def flatten_metrics(metrics: dict[str, dict[str, float]]) -> dict[str, float]:
    return {
        f"{window}_{key}": value
        for window, window_metrics in metrics.items()
        for key, value in window_metrics.items()
    }


def field_domains(component: str) -> dict[str, tuple[Any, ...]]:
    return BB_DOMAINS if component == "bb_break" else RSI_DOMAINS


def value_label(value: Any) -> str:
    return str(value).replace(" ", "").replace(".", "p").replace("-", "m").replace(",", "_")


def metric_line(metric: dict[str, float]) -> str:
    return (
        f"`{metric['annual_multiple']:.4f}x` / `{metric['total_return']:.2%}` / "
        f"`{metric['max_dd']:.2%}` / `{metric['win_rate']:.2%}` / "
        f"`{int(metric['trades'])}`"
    )


def prefit_strict_improves(row: dict[str, Any], baseline: dict[str, Any]) -> bool:
    return bool(
        row["prefit_annual_multiple"] > baseline["prefit_annual_multiple"]
        and row["prefit_max_dd"] > baseline["prefit_max_dd"]
        and row["train_total_return"] > 0.0
        and row["validation_total_return"] > 0.0
        and row["prefit_total_return"] > 0.0
        and row["train_max_dd"] > DD_FLOOR
        and row["validation_max_dd"] > DD_FLOOR
        and row["prefit_max_dd"] > DD_FLOOR
        and row["prefit_win_rate"] >= 0.50
    )


def high_win_prefit_gate(row: dict[str, Any], baseline: dict[str, Any]) -> bool:
    return bool(
        row["prefit_annual_multiple"] > baseline["prefit_annual_multiple"]
        and row["train_total_return"] > 0.0
        and row["validation_total_return"] > 0.0
        and row["prefit_total_return"] > 0.0
        and row["train_max_dd"] > DD_FLOOR
        and row["validation_max_dd"] > DD_FLOOR
        and row["prefit_max_dd"] > DD_FLOOR
        and row["train_win_rate"] >= WIN_FLOOR
        and row["validation_win_rate"] >= WIN_FLOOR
        and row["prefit_win_rate"] >= WIN_FLOOR
    )


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    ABLATION_DIR.mkdir(parents=True, exist_ok=True)
    engine, frame, funding, quality = v2.load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    baseline_bb, baseline_rsi = v2.v2_configs()
    baseline_trades, bb_trades, rsi_trades, priorities = v2.simulate_v2(
        engine, frame, funding_times, funding_cumulative
    )
    baseline_metrics = v2.metrics(engine, baseline_trades)
    baseline_flat = flatten_metrics(baseline_metrics)
    baseline_signature = v1.trade_signature(baseline_trades)
    component_signatures = {
        "bb_break": v1.trade_signature(bb_trades),
        "rsi_reversal": v1.trade_signature(rsi_trades),
    }
    slice_rows = [
        {"window": name, **metric}
        for name, metric in v2.standard_slices(engine, baseline_trades).items()
    ]
    pd.DataFrame(slice_rows).to_csv(SLICES_CSV, index=False)

    rows: list[dict[str, Any]] = [
        {
            "label": "ETH-1H-Adaptive-Regime-V2",
            "component": "ensemble",
            "field": "baseline",
            "baseline_value": "baseline",
            "value": "baseline",
            "classification": "baseline",
            "component_path_equal": True,
            "merged_path_equal": True,
            "prefit_strict_improve": False,
            "prefit_high_win_gate": False,
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
            raise RuntimeError(f"{component} V2 ablation specs missing fields: {sorted(missing)}")
        for field in component_fields:
            field_name = field.name
            observed[component].add(field_name)
            for value in domains[field_name]:
                if value == getattr(baseline_config, field_name):
                    continue
                if component == "rsi_reversal":
                    test_config = replace(baseline_config, **{field_name: value})
                    if test_config.threshold_high <= test_config.threshold_low:
                        continue
                    if test_config.min_adx > test_config.max_adx:
                        continue
                else:
                    test_config = replace(baseline_config, **{field_name: value})
                variant_bb = test_config if component == "bb_break" else baseline_bb
                variant_rsi = test_config if component == "rsi_reversal" else baseline_rsi
                merged, variant_bb_trades, variant_rsi_trades, _ = v2.simulate_v2(
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
                flat = flatten_metrics(v2.metrics(engine, merged))
                row = {
                    "label": f"{component}__{field_name}__{value_label(value)}",
                    "component": component,
                    "field": field_name,
                    "baseline_value": getattr(baseline_config, field_name),
                    "value": value,
                    "classification": "v2_exposed_parameter",
                    "component_path_equal": v1.trade_signature(variant_component_trades)
                    == component_signatures[component],
                    "merged_path_equal": v1.trade_signature(merged) == baseline_signature,
                    **flat,
                }
                row["prefit_strict_improve"] = prefit_strict_improves(row, baseline_flat)
                row["prefit_high_win_gate"] = high_win_prefit_gate(row, baseline_flat)
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
                    "classification": "v2_exposed_parameter",
                    "variant_rows": int(len(subset)),
                    "component_path_equal_rows": int(subset["component_path_equal"].sum()),
                    "merged_path_equal_rows": int(subset["merged_path_equal"].sum()),
                    "prefit_strict_improve_rows": int(subset["prefit_strict_improve"].sum()),
                    "prefit_high_win_gate_rows": int(subset["prefit_high_win_gate"].sum()),
                    "best_prefit_annual_multiple": best_prefit_annual,
                    "best_prefit_max_dd": best_prefit_dd,
                }
            )
    fields_frame = pd.DataFrame(field_rows)
    fields_frame.to_csv(FIELDS_CSV, index=False)

    strict = rows_frame.loc[rows_frame["prefit_strict_improve"]].sort_values(
        ["prefit_annual_multiple", "prefit_max_dd", "validation_annual_multiple"],
        ascending=[False, False, False],
    )
    high_win = rows_frame.loc[rows_frame["prefit_high_win_gate"]].sort_values(
        ["prefit_annual_multiple", "validation_annual_multiple", "prefit_win_rate"],
        ascending=[False, False, False],
    )

    payload = {
        "family": "ETH-1H-Adaptive-Regime",
        "version": "ETH-1H-Adaptive-Regime-V2",
        "status": "registered_v2_full_ablation_complete_no_go_not_live_ready",
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
        "v2_exposed_parameter_slots": {
            "bb_break": len(fields(type(baseline_bb))),
            "rsi_reversal": len(fields(type(baseline_rsi))),
            "total": len(fields(type(baseline_bb))) + len(fields(type(baseline_rsi))),
            "coverage_missing": {
                "bb_break": sorted({field.name for field in fields(type(baseline_bb))} - observed["bb_break"]),
                "rsi_reversal": sorted({field.name for field in fields(type(baseline_rsi))} - observed["rsi_reversal"]),
            },
        },
        "ablation_rows_including_baseline": len(rows_frame),
        "prefit_strict_improve_rows": len(strict),
        "prefit_high_win_gate_rows": len(high_win),
        "top_prefit_strict": strict.head(30).to_dict(orient="records"),
        "top_prefit_high_win": high_win.head(30).to_dict(orient="records"),
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
        "# ETH-1H-Adaptive-Regime-V2 全参数消融 - 2026-07-06",
        "",
        "## 结论",
        "",
        (
            "`ETH-1H-Adaptive-Regime-V2` 已覆盖两条腿全部 `29/29` 个 clean 参数槽，"
            "完成 one-at-a-time 全参数消融。reused holdout 与近期分片只作冻结后审计，不参与选参。"
        ),
        "",
        (
            f"本轮 one-at-a-time 行数（含 baseline）为 `{len(rows_frame)}`；"
            f"prefit 严格改善行数 `{len(strict)}`；"
            f"满足 train/validation/prefit `win>=80%`、DD `<20%` 且 prefit annual 高于 V2 的单字段行数 `{len(high_win)}`。"
        ),
        "",
        "## V2 基线",
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
            "## 字段覆盖",
            "",
            "| Component | Field | Baseline | Variants | Component Equal | Merged Equal | Strict Improve | High-Win Gate |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in fields_frame.to_dict(orient="records"):
        lines.append(
            f"| `{row['component']}` | `{row['field']}` | `{row['baseline_value']}` | "
            f"`{row['variant_rows']}` | `{row['component_path_equal_rows']}` | "
            f"`{row['merged_path_equal_rows']}` | `{row['prefit_strict_improve_rows']}` | "
            f"`{row['prefit_high_win_gate_rows']}` |"
        )
    if not high_win.empty:
        lines.extend(
            [
                "",
                "## High-Win 单字段 Top 10",
                "",
                "| Label | Prefit annual | Prefit DD | Prefit win | Validation annual | Validation win | Current full annual | Current full win |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in high_win.head(10).to_dict(orient="records"):
            lines.append(
                f"| `{row['label']}` | `{row['prefit_annual_multiple']:.4f}x` | "
                f"`{row['prefit_max_dd']:.2%}` | `{row['prefit_win_rate']:.2%}` | "
                f"`{row['validation_annual_multiple']:.4f}x` | `{row['validation_win_rate']:.2%}` | "
                f"`{row['current_full_annual_multiple']:.4f}x` | `{row['current_full_win_rate']:.2%}` |"
            )
    lines.extend(
        [
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
            "uv run python research/eth/1h-adaptive-regime/scripts/research_eth_1h_ar_v2_full_ablation.py",
            "```",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(json_safe(payload), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
