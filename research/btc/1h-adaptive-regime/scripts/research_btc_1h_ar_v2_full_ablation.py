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

import audit_btc_1h_ar_v1_scaled_frontier as scaled  # noqa: E402
import btc_1h_ar_v1 as v1  # noqa: E402
import btc_1h_ar_v1_clean as clean  # noqa: E402
import research_btc_1h_ar_v1_clean_tune as tune  # noqa: E402
import research_btc_1h_ar_v1_full_ablation as v1_ablation  # noqa: E402


FAMILY_DIR = ROOT / "research/btc/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
ABLATION_DIR = FAMILY_DIR / "ablations"
DATE_TAG = "2026-07-06"
SUMMARY_JSON = ARTIFACT_DIR / f"btc_1h_ar_v2_full_ablation_{DATE_TAG}.json"
ROWS_CSV = ARTIFACT_DIR / f"btc_1h_ar_v2_full_ablation_rows_{DATE_TAG}.csv"
FIELDS_CSV = ARTIFACT_DIR / f"btc_1h_ar_v2_full_ablation_fields_{DATE_TAG}.csv"
REPORT_MD = ABLATION_DIR / f"btc-1h-ar-v2-full-parameter-ablation-{DATE_TAG}.md"


def v2_configs(engine: Any) -> tuple[Any, Any]:
    return (
        replace(
            clean.keltner_to_base(engine, scaled.KELTNER),
            name="BTC_1H_AR_V2_KELTNER",
        ),
        replace(clean.cci_to_base(engine, scaled.CCI), name="BTC_1H_AR_V2_CCI"),
    )


def simulate_pair(
    engine: Any,
    frame: pd.DataFrame,
    funding_times: Any,
    funding_cumulative: Any,
    *,
    keltner: Any,
    cci: Any,
) -> tuple[list[Any], list[Any], list[Any], tuple[float, float]]:
    keltner_trades = v1.simulate_component(
        engine, frame, funding_times, funding_cumulative, keltner
    )
    cci_trades = v1.simulate_component(
        engine, frame, funding_times, funding_cumulative, cci
    )
    k_score = tune.leg_score(tune.prefit_metrics(engine, keltner_trades))
    c_score = tune.leg_score(tune.prefit_metrics(engine, cci_trades))
    merged = engine.merge_trade_sets(keltner_trades, cci_trades, k_score, c_score)
    return merged, keltner_trades, cci_trades, (k_score, c_score)


def variant_values(component: str) -> dict[str, list[Any]]:
    common = {
        "name": [f"BTC_1H_AR_V2_{component.upper()}_RENAMED"],
        "style": ["leg_removed"],
        "require_macd_turn": [True],
        "require_body_dir": [True],
        "exit_kind": ["trailing"],
        "entry_delay_bars": [2, 3],
        "sizing_kind": ["risk"],
    }
    if component == "keltner_break":
        return {
            **common,
            "side_mode": ["long", "short"],
            "ema_fast": [34, 89],
            "ema_slow": [89, 233],
            "ema_htf": [89, 144],
            "indicator_window": [12, 32, 48],
            "threshold_low": [15.0, 40.0],
            "threshold_high": [60.0, 85.0],
            "band_k": [1.75, 2.25, 2.5, 3.0],
            "pullback_atr": [-0.5, 0.0],
            "roc_window": [12, 48, 72],
            "roc_threshold_bps": [100.0, 500.0],
            "macd_fast": [12, 21],
            "macd_slow": [26, 55],
            "macd_signal": [9, 13],
            "min_adx": [32.0, 36.0, 44.0, 48.0],
            "max_adx": [45.0, 10000.0],
            "min_rvol": [0.8, 1.0, 1.5, 2.0],
            "min_atr_bps": [50.0, 100.0],
            "max_atr_bps": [150.0, 250.0, 300.0, 10000.0],
            "min_dir_roc_bps": [-10000.0, -100.0, 0.0, 100.0],
            "max_dist_ema_bps": [500.0, 1000.0, 2500.0, 100000.0],
            "htf_mode": ["none", "h12", "d1"],
            "max_aligned_funding_bps": [2.0, 8.0, 10000.0],
            "tp_atr": [1.0, 1.25, 2.0, 2.5],
            "sl_atr": [3.5, 4.5, 5.5, 6.0],
            "trail_activation_atr": [0.75, 1.5, 4.0],
            "trail_atr": [0.75, 1.0, 2.5],
            "max_hold_bars": [72, 120, 168, 216],
            "cooldown_bars": [3, 6, 12, 24],
            "fixed_leverage": [1.2, 1.6, 2.0, 2.4],
            "risk_fraction": [0.005, 0.01, 0.03],
            "max_leverage": [1.0, 3.0, 5.0],
        }
    return {
        **common,
        "side_mode": ["both", "short"],
        "ema_fast": [55, 144],
        "ema_slow": [144, 377],
        "ema_htf": [89, 144, 233],
        "indicator_window": [14, 40, 72],
        "threshold_low": [20.0, 35.0],
        "threshold_high": [75.0, 100.0, 150.0, 200.0],
        "band_k": [0.75, 2.5],
        "pullback_atr": [0.0, 0.75],
        "roc_window": [24, 72],
        "roc_threshold_bps": [100.0, 500.0],
        "macd_fast": [8, 12],
        "macd_slow": [21, 26],
        "macd_signal": [5, 13],
        "min_adx": [8.0, 16.0, 24.0],
        "max_adx": [36.0, 40.0, 55.0, 100.0],
        "min_rvol": [0.0, 1.0, 1.5, 2.0],
        "min_atr_bps": [50.0, 100.0, 150.0],
        "max_atr_bps": [300.0, 400.0, 10000.0],
        "min_dir_roc_bps": [-200.0, 0.0, 100.0],
        "max_dist_ema_bps": [500.0, 1000.0, 1500.0, 10000.0],
        "htf_mode": ["h4", "h12", "d1"],
        "max_aligned_funding_bps": [1.0, 2.0, 4.0, 8.0],
        "tp_atr": [3.5, 4.0, 5.0, 6.0],
        "sl_atr": [1.0, 1.25, 2.0, 2.5],
        "trail_activation_atr": [1.0, 2.0, 3.0],
        "trail_atr": [0.75, 1.0, 2.0],
        "max_hold_bars": [48, 96, 120],
        "cooldown_bars": [0, 12, 36, 72],
        "fixed_leverage": [2.0, 2.4, 3.0, 3.5],
        "risk_fraction": [0.005, 0.02, 0.03],
        "max_leverage": [1.0, 3.0, 5.0],
    }


def flatten_metrics(metrics: dict[str, dict[str, float]]) -> dict[str, float]:
    return {
        f"{window}_{key}": value
        for window, window_metrics in metrics.items()
        for key, value in window_metrics.items()
    }


def prefit_improves(row: dict[str, Any], baseline: dict[str, Any]) -> bool:
    return bool(
        row["prefit_annual_multiple"] > baseline["prefit_annual_multiple"]
        and row["prefit_max_dd"] > baseline["prefit_max_dd"]
        and row["prefit_win_rate"] >= 0.50
        and row["train_total_return"] > 0
        and row["validation_total_return"] > 0
        and row["validation_max_dd"] > -0.20
    )


def active_gate(row: dict[str, Any]) -> bool:
    return bool(
        row["train_total_return"] > 0
        and row["validation_total_return"] > 0
        and row["prefit_total_return"] > 0
        and row["train_max_dd"] > -0.20
        and row["validation_max_dd"] > -0.20
        and row["prefit_max_dd"] > -0.20
        and row["train_win_rate"] >= 0.50
        and row["validation_win_rate"] >= 0.50
        and row["prefit_win_rate"] >= 0.50
    )


def fmt_pct(value: float) -> str:
    return f"{value:.2%}"


def fmt_mult(value: float) -> str:
    return f"{value:.4f}x"


def metric_table_lines(metrics: dict[str, dict[str, float]]) -> list[str]:
    lines = [
        "| Window | Annual | Return | DD | Win | Trades | PF |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for window in ("train", "validation", "prefit", "reused_holdout", "current_full"):
        metric = metrics[window]
        lines.append(
            f"| `{window}` | `{fmt_mult(metric['annual_multiple'])}` | "
            f"`{fmt_pct(metric['total_return'])}` | `{fmt_pct(metric['max_dd'])}` | "
            f"`{fmt_pct(metric['win_rate'])}` | `{int(metric['trades'])}` | "
            f"`{metric['profit_factor']:.3f}` |"
        )
    return lines


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    ABLATION_DIR.mkdir(parents=True, exist_ok=True)
    engine, frame, funding, quality = v1.load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    keltner, cci = v2_configs(engine)
    baseline_trades, keltner_trades, cci_trades, priorities = simulate_pair(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        keltner=keltner,
        cci=cci,
    )
    baseline_signature = v1.trade_signature(baseline_trades)
    baseline_metrics = v1.metrics(engine, baseline_trades)
    baseline_flat = flatten_metrics(baseline_metrics)
    component_signatures = {
        "keltner_break": v1.trade_signature(keltner_trades),
        "cci_reversal": v1.trade_signature(cci_trades),
    }
    rows: list[dict[str, Any]] = [
        {
            "label": "BTC-1H-Adaptive-Regime-V2",
            "component": "ensemble",
            "field": "baseline",
            "baseline_value": "baseline",
            "value": "baseline",
            "classification": "baseline",
            "component_path_equal": True,
            "merged_path_equal": True,
            "prefit_strict_improve": False,
            "prefit_active_gate": active_gate(baseline_flat),
            **baseline_flat,
        }
    ]
    field_names = {field.name for field in fields(engine.StrategyConfig)}
    observed: dict[str, set[str]] = {
        "keltner_break": set(),
        "cci_reversal": set(),
    }

    for component, base_cfg, base_component_trades, other_cfg in (
        ("keltner_break", keltner, keltner_trades, cci),
        ("cci_reversal", cci, cci_trades, keltner),
    ):
        values_by_field = variant_values(component)
        missing_specs = field_names - set(values_by_field)
        if missing_specs:
            raise RuntimeError(
                f"{component} ablation specs missing fields: {sorted(missing_specs)}"
            )
        for field_name in sorted(field_names):
            observed[component].add(field_name)
            for value in values_by_field[field_name]:
                label_value = str(value).replace(".", "p").replace("-", "m")
                label = f"{component}__{field_name}__{label_value}"
                if field_name == "style" and value == "leg_removed":
                    if component == "keltner_break":
                        merged = cci_trades
                        component_trades = []
                    else:
                        merged = keltner_trades
                        component_trades = []
                else:
                    variant = replace(base_cfg, **{field_name: value})
                    if variant.ema_fast >= variant.ema_slow:
                        continue
                    if variant.min_adx > variant.max_adx:
                        continue
                    if variant.min_atr_bps > variant.max_atr_bps:
                        continue
                    if component == "keltner_break":
                        merged, component_trades, _other, _priority = simulate_pair(
                            engine,
                            frame,
                            funding_times,
                            funding_cumulative,
                            keltner=variant,
                            cci=other_cfg,
                        )
                    else:
                        merged, _other, component_trades, _priority = simulate_pair(
                            engine,
                            frame,
                            funding_times,
                            funding_cumulative,
                            keltner=other_cfg,
                            cci=variant,
                        )
                flat = flatten_metrics(v1.metrics(engine, merged))
                row = {
                    "label": label,
                    "component": component,
                    "field": field_name,
                    "baseline_value": getattr(base_cfg, field_name),
                    "value": value,
                    "classification": v1_ablation.classification(component, field_name),
                    "component_path_equal": (
                        False
                        if field_name == "style"
                        else v1.trade_signature(component_trades)
                        == component_signatures[component]
                    ),
                    "merged_path_equal": v1.trade_signature(merged)
                    == baseline_signature,
                    **flat,
                }
                row["prefit_strict_improve"] = prefit_improves(row, baseline_flat)
                row["prefit_active_gate"] = active_gate(row)
                rows.append(row)

    coverage_missing = {
        component: sorted(field_names - fields_seen)
        for component, fields_seen in observed.items()
    }
    if any(coverage_missing.values()):
        raise RuntimeError(f"Ablation coverage missing: {coverage_missing}")

    rows_frame = pd.DataFrame(rows)
    rows_frame.to_csv(ROWS_CSV, index=False)
    field_rows: list[dict[str, Any]] = []
    for component, cfg in (("keltner_break", keltner), ("cci_reversal", cci)):
        for field_name in sorted(field_names):
            subset = rows_frame.loc[
                (rows_frame["component"] == component)
                & (rows_frame["field"] == field_name)
            ]
            best_idx = subset["prefit_annual_multiple"].idxmax()
            worst_idx = subset["prefit_annual_multiple"].idxmin()
            field_rows.append(
                {
                    "component": component,
                    "field": field_name,
                    "baseline_value": getattr(cfg, field_name),
                    "classification": v1_ablation.classification(component, field_name),
                    "variant_rows": int(len(subset)),
                    "component_path_equal_rows": int(
                        subset["component_path_equal"].sum()
                    ),
                    "merged_path_equal_rows": int(subset["merged_path_equal"].sum()),
                    "prefit_strict_improve_rows": int(
                        subset["prefit_strict_improve"].sum()
                    ),
                    "prefit_active_gate_rows": int(subset["prefit_active_gate"].sum()),
                    "best_label": str(subset.loc[best_idx, "label"]),
                    "best_prefit_annual_multiple": float(
                        subset.loc[best_idx, "prefit_annual_multiple"]
                    ),
                    "best_prefit_max_dd": float(
                        subset.loc[best_idx, "prefit_max_dd"]
                    ),
                    "worst_label": str(subset.loc[worst_idx, "label"]),
                    "worst_prefit_annual_multiple": float(
                        subset.loc[worst_idx, "prefit_annual_multiple"]
                    ),
                    "worst_prefit_max_dd": float(
                        subset.loc[worst_idx, "prefit_max_dd"]
                    ),
                }
            )
    fields_frame = pd.DataFrame(field_rows)
    fields_frame.to_csv(FIELDS_CSV, index=False)

    strict = rows_frame.loc[rows_frame["prefit_strict_improve"]].sort_values(
        ["prefit_annual_multiple", "prefit_max_dd", "validation_annual_multiple"],
        ascending=[False, False, False],
    )
    active = rows_frame.loc[
        rows_frame["prefit_active_gate"] & (rows_frame["component"] != "ensemble")
    ].sort_values(
        ["prefit_annual_multiple", "prefit_max_dd", "validation_annual_multiple"],
        ascending=[False, False, False],
    )
    classification_counts = (
        fields_frame["classification"].value_counts().sort_index().to_dict()
    )
    payload = {
        "family": "BTC-1H-Adaptive-Regime",
        "version": "BTC-1H-Adaptive-Regime-V2",
        "status": "full_parameter_ablation_complete_paper_audit_observation_not_live_ready",
        "date": DATE_TAG,
        "data_quality": quality,
        "costs": {
            "fee_per_fill": engine.FEE_PER_FILL,
            "slippage_per_fill": engine.SLIPPAGE_PER_FILL,
            "funding": "actual_binance_history_per_trade",
        },
        "field_slots": {
            "per_component": len(field_names),
            "total": len(field_names) * 2,
            "coverage_missing": coverage_missing,
        },
        "classification_counts": classification_counts,
        "rows_including_baseline": len(rows_frame),
        "component_prefit_priority_scores": priorities,
        "baseline": baseline_metrics,
        "prefit_strict_improve_rows": len(strict),
        "prefit_active_gate_variant_rows": len(active),
        "top_prefit_strict": strict.head(30).to_dict(orient="records"),
        "top_prefit_active_gate": active.head(30).to_dict(orient="records"),
        "field_summary": fields_frame.to_dict(orient="records"),
    }
    SUMMARY_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    lines = [
        "# BTC-1H-Adaptive-Regime-V2 全参数消融 - 2026-07-06",
        "",
        "## 结论",
        "",
        (
            f"已覆盖 V2 两条腿全部 `{len(field_names) * 2}` 个 StrategyConfig 字段槽，"
            f"Keltner `{len(field_names)}` 个、CCI `{len(field_names)}` 个，coverage missing 为 `0`。"
        ),
        "",
        (
            f"分类结果：`{classification_counts}`。本轮仍沿用 V1 全消融的字段语义分类："
            "active tunable 为 V2 clean surface 可调项；contract fixed 为执行合同常量；"
            "baseline/neutral fixed 为代码语义上不影响当前 leg 或固定删除的槽。"
        ),
        "",
        (
            f"相对 V2 基线，one-at-a-time 变体中同时满足 prefit 年化更高、回撤更小、"
            f"胜率 >=50%、train/validation 同正且 validation DD<20% 的行数为 `{len(strict)}`。"
            "这些只是单字段敏感性观察，不构成 V2.1 或 promotion。"
        ),
        "",
        "## V2 基线",
        "",
        *metric_table_lines(baseline_metrics),
        "",
        "## 全字段覆盖与消融摘要",
        "",
        "| Component | Field | Baseline | Classification | Variants | Path equal | Strict improve | Active gate | Best prefit | Worst prefit |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in fields_frame.to_dict(orient="records"):
        lines.append(
            f"| `{row['component']}` | `{row['field']}` | `{row['baseline_value']}` | "
            f"`{row['classification']}` | `{row['variant_rows']}` | "
            f"`{row['merged_path_equal_rows']}` | `{row['prefit_strict_improve_rows']}` | "
            f"`{row['prefit_active_gate_rows']}` | "
            f"`{fmt_mult(row['best_prefit_annual_multiple'])}` | "
            f"`{fmt_mult(row['worst_prefit_annual_multiple'])}` |"
        )
    lines.extend(
        [
            "",
            "## Prefit 严格改善单字段 Top 20",
            "",
            "| Label | Prefit annual | Prefit DD | Prefit win | Validation annual | Validation DD | Reused holdout annual | Reused holdout DD |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in strict.head(20).to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{fmt_mult(row['prefit_annual_multiple'])}` | "
            f"`{fmt_pct(row['prefit_max_dd'])}` | `{fmt_pct(row['prefit_win_rate'])}` | "
            f"`{fmt_mult(row['validation_annual_multiple'])}` | "
            f"`{fmt_pct(row['validation_max_dd'])}` | "
            f"`{fmt_mult(row['reused_holdout_annual_multiple'])}` | "
            f"`{fmt_pct(row['reused_holdout_max_dd'])}` |"
        )
    if strict.empty:
        lines.append("| - | - | - | - | - | - | - | - |")
    lines.extend(
        [
            "",
            "## 选择边界",
            "",
            "- 本轮是 V2 冻结参数的 one-at-a-time 全字段敏感性消融，不做组合搜索。",
            "- reused holdout 已在 V1/V2 研究中解锁，只能作为复用审计列展示，不得用于新版本选参。",
            "- V2 仍为 paper-audit observation；没有新增 forward trades、production runner、重启恢复、交易所对账、missing-bar fail-closed、kill switch 和真实 stop-market 滑点证据。",
            "",
            "## 机器证据",
            "",
            f"- `artifacts/{SUMMARY_JSON.name}`",
            f"- `artifacts/{ROWS_CSV.name}`",
            f"- `artifacts/{FIELDS_CSV.name}`",
            "",
            "复现：",
            "",
            "```bash",
            "uv run research/btc/1h-adaptive-regime/scripts/research_btc_1h_ar_v2_full_ablation.py",
            "```",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
