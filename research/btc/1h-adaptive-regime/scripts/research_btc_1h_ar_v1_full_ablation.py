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

import btc_1h_ar_v1 as v1  # noqa: E402


FAMILY_DIR = ROOT / "research/btc/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
ABLATION_DIR = FAMILY_DIR / "ablations"
DATE_TAG = "2026-07-02"
SUMMARY_JSON = ARTIFACT_DIR / f"btc_1h_ar_v1_full_ablation_{DATE_TAG}.json"
ROWS_CSV = ARTIFACT_DIR / f"btc_1h_ar_v1_full_ablation_rows_{DATE_TAG}.csv"
FIELDS_CSV = ARTIFACT_DIR / f"btc_1h_ar_v1_full_ablation_fields_{DATE_TAG}.csv"
REPORT_MD = ABLATION_DIR / f"btc-1h-ar-v1-full-parameter-ablation-{DATE_TAG}.md"


SEMANTIC_DORMANT = {
    "keltner_break": {
        "ema_fast",
        "ema_slow",
        "ema_htf",
        "threshold_low",
        "threshold_high",
        "pullback_atr",
        "roc_threshold_bps",
        "macd_fast",
        "macd_slow",
        "macd_signal",
        "require_macd_turn",
        "require_body_dir",
        "trail_activation_atr",
        "trail_atr",
        "risk_fraction",
        "max_leverage",
    },
    "cci_reversal": {
        "ema_fast",
        "ema_slow",
        "threshold_low",
        "band_k",
        "pullback_atr",
        "roc_window",
        "roc_threshold_bps",
        "macd_fast",
        "macd_slow",
        "macd_signal",
        "min_dir_roc_bps",
        "htf_mode",
        "require_macd_turn",
        "require_body_dir",
        "max_aligned_funding_bps",
        "trail_activation_atr",
        "trail_atr",
        "risk_fraction",
        "max_leverage",
    },
}

NEUTRAL_FIXED = {
    "keltner_break": {"min_atr_bps", "max_adx", "max_dist_ema_bps"},
    "cci_reversal": {"min_adx"},
}

CONTRACT_FIXED = {
    "name",
    "style",
    "side_mode",
    "exit_kind",
    "entry_delay_bars",
    "sizing_kind",
}


def variant_values(component: str) -> dict[str, list[Any]]:
    common = {
        "name": [f"BTC_1H_AR_V1_{component.upper()}_RENAMED"],
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
            "threshold_high": [60.0, 70.0],
            "band_k": [2.0, 2.25, 2.75, 3.0],
            "pullback_atr": [-0.5, 0.0],
            "roc_window": [12, 48],
            "roc_threshold_bps": [100.0, 500.0],
            "macd_fast": [12, 21],
            "macd_slow": [26, 55],
            "macd_signal": [9, 13],
            "min_adx": [0.0, 28.0, 32.0, 40.0],
            "max_adx": [45.0, 10000.0],
            "min_rvol": [0.0, 0.6, 1.0, 1.25],
            "min_atr_bps": [50.0, 100.0],
            "max_atr_bps": [150.0, 250.0, 300.0, 10000.0],
            "min_dir_roc_bps": [-10000.0, -100.0, 50.0, 100.0],
            "max_dist_ema_bps": [500.0, 1000.0, 2500.0, 100000.0],
            "htf_mode": ["none", "h4", "h12"],
            "max_aligned_funding_bps": [1.0, 4.0, 8.0, 10000.0],
            "tp_atr": [1.0, 1.25, 2.0, 2.5],
            "sl_atr": [3.0, 3.5, 4.5, 5.0],
            "trail_activation_atr": [0.75, 1.5, 4.0],
            "trail_atr": [0.75, 1.0, 2.5],
            "max_hold_bars": [72, 96, 168, 240],
            "cooldown_bars": [0, 3, 12, 24],
            "fixed_leverage": [2.0, 2.5, 3.5, 4.0],
            "risk_fraction": [0.005, 0.01, 0.03],
            "max_leverage": [1.0, 3.0, 5.0],
        }
    return {
        **common,
        "side_mode": ["both", "short"],
        "ema_fast": [55, 144],
        "ema_slow": [144, 377],
        "ema_htf": [89, 233],
        "indicator_window": [14, 40, 72],
        "threshold_low": [20.0, 35.0],
        "threshold_high": [100.0, 150.0, 200.0],
        "band_k": [0.75, 2.5],
        "pullback_atr": [0.0, 0.75],
        "roc_window": [24, 72],
        "roc_threshold_bps": [100.0, 500.0],
        "macd_fast": [8, 12],
        "macd_slow": [21, 26],
        "macd_signal": [5, 13],
        "min_adx": [8.0, 16.0, 24.0],
        "max_adx": [30.0, 45.0, 100.0],
        "min_rvol": [0.0, 1.0, 1.25, 2.0],
        "min_atr_bps": [0.0, 75.0, 100.0],
        "max_atr_bps": [200.0, 250.0, 400.0, 600.0, 10000.0],
        "min_dir_roc_bps": [-200.0, 0.0, 100.0],
        "max_dist_ema_bps": [500.0, 750.0, 1500.0, 2500.0, 10000.0],
        "htf_mode": ["h4", "h12", "d1"],
        "max_aligned_funding_bps": [1.0, 2.0, 4.0, 8.0],
        "tp_atr": [3.0, 3.5, 4.5, 5.0],
        "sl_atr": [0.75, 1.0, 1.5, 2.0],
        "trail_activation_atr": [1.0, 2.0, 3.0],
        "trail_atr": [0.75, 1.0, 2.0],
        "max_hold_bars": [72, 120, 168],
        "cooldown_bars": [0, 12, 36, 48],
        "fixed_leverage": [3.0, 3.5, 4.5, 5.0],
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


def classification(component: str, field: str) -> str:
    if field in CONTRACT_FIXED:
        return "contract_fixed"
    if field in SEMANTIC_DORMANT[component]:
        return "baseline_fixed_remove"
    if field in NEUTRAL_FIXED[component]:
        return "neutral_fixed_remove"
    return "active_tunable"


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    ABLATION_DIR.mkdir(parents=True, exist_ok=True)
    engine, frame, funding, quality = v1.load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    keltner, cci = v1.v1_configs(engine)
    baseline_trades, keltner_trades, cci_trades, priorities = v1.simulate_v1(
        engine, frame, funding_times, funding_cumulative
    )
    baseline_signature = v1.trade_signature(baseline_trades)
    baseline_flat = flatten_metrics(v1.metrics(engine, baseline_trades))
    component_signatures = {
        "keltner_break": v1.trade_signature(keltner_trades),
        "cci_reversal": v1.trade_signature(cci_trades),
    }
    rows: list[dict[str, Any]] = [
        {
            "label": "BTC-1H-Adaptive-Regime-V1",
            "component": "ensemble",
            "field": "baseline",
            "value": "baseline",
            "classification": "baseline",
            "component_path_equal": True,
            "merged_path_equal": True,
            "prefit_strict_improve": False,
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
                        merged, component_trades, _other, _priority = v1.simulate_v1(
                            engine,
                            frame,
                            funding_times,
                            funding_cumulative,
                            keltner=variant,
                            cci=other_cfg,
                        )
                    else:
                        merged, _other, component_trades, _priority = v1.simulate_v1(
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
                    "classification": classification(component, field_name),
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
                row["prefit_strict_improve"] = prefit_improves(
                    row, baseline_flat
                )
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
            field_rows.append(
                {
                    "component": component,
                    "field": field_name,
                    "baseline_value": getattr(cfg, field_name),
                    "classification": classification(component, field_name),
                    "variant_rows": int(len(subset)),
                    "component_path_equal_rows": int(
                        subset["component_path_equal"].sum()
                    ),
                    "merged_path_equal_rows": int(
                        subset["merged_path_equal"].sum()
                    ),
                    "prefit_strict_improve_rows": int(
                        subset["prefit_strict_improve"].sum()
                    ),
                    "best_prefit_annual_multiple": float(
                        subset["prefit_annual_multiple"].max()
                    ),
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
    classification_counts = (
        fields_frame["classification"].value_counts().sort_index().to_dict()
    )
    payload = {
        "family": "BTC-1H-Adaptive-Regime",
        "version": "BTC-1H-Adaptive-Regime-V1",
        "status": "full_parameter_ablation_complete_not_promoted",
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
        "baseline": v1.metrics(engine, baseline_trades),
        "prefit_strict_improve_rows": len(strict),
        "top_prefit_strict": strict.head(30).to_dict(orient="records"),
        "clean_surface": {
            component: fields_frame.loc[
                (fields_frame["component"] == component)
                & (
                    fields_frame["classification"].isin(
                        ["contract_fixed", "active_tunable"]
                    )
                ),
                "field",
            ].tolist()
            for component in ("keltner_break", "cci_reversal")
        },
    }
    SUMMARY_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    baseline = payload["baseline"]
    lines = [
        "# BTC-1H-Adaptive-Regime-V1 全参数消融 - 2026-07-02",
        "",
        "## 结论",
        "",
        (
            f"已覆盖 V1 两条腿全部 `{len(field_names) * 2}` 个 StrategyConfig 字段槽，"
            f"Keltner `{len(field_names)}` 个、CCI `{len(field_names)}` 个，coverage missing 为 `0`。"
        ),
        "",
        (
            f"分类结果：`{classification_counts}`。其中 baseline fixed 与 neutral fixed "
            "字段从后续 clean tuning surface 移除；contract fixed 字段保留为实现常量，不进入搜索。"
        ),
        "",
        (
            f"one-at-a-time 变体中，严格满足 prefit 年化更高、回撤更小、胜率 >=50%、"
            f"train/validation 同正且 validation DD<20% 的行数为 `{len(strict)}`。"
        ),
        "",
        "## V1 基线",
        "",
        "| Window | Annual | Return | DD | Win | Trades | PF |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for window in ("train", "validation", "prefit", "reused_holdout", "current_full"):
        metric = baseline[window]
        lines.append(
            f"| `{window}` | `{metric['annual_multiple']:.4f}x` | "
            f"`{metric['total_return']:.2%}` | `{metric['max_dd']:.2%}` | "
            f"`{metric['win_rate']:.2%}` | `{int(metric['trades'])}` | "
            f"`{metric['profit_factor']:.3f}` |"
        )
    lines.extend(
        [
            "",
            "## 全字段覆盖与删参分类",
            "",
            "| Component | Field | Baseline | Classification | Variants | Component equal | Merged equal | Prefit strict improve |",
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
            "## Prefit 严格改善单字段 Top 20",
            "",
            "| Label | Prefit annual | Prefit DD | Prefit win | Validation annual | Validation DD | Reused holdout annual | Reused holdout DD |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in strict.head(20).to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{row['prefit_annual_multiple']:.4f}x` | "
            f"`{row['prefit_max_dd']:.2%}` | `{row['prefit_win_rate']:.2%}` | "
            f"`{row['validation_annual_multiple']:.4f}x` | "
            f"`{row['validation_max_dd']:.2%}` | "
            f"`{row['reused_holdout_annual_multiple']:.4f}x` | "
            f"`{row['reused_holdout_max_dd']:.2%}` |"
        )
    if strict.empty:
        lines.append("| - | - | - | - | - | - | - | - |")
    lines.extend(
        [
            "",
            "## 选择边界",
            "",
            "- 删参只依据代码语义、V1 状态与路径等价性；不使用 reused holdout 决定保留字段。",
            "- 后续微调只读取 train、validation 与 prefit；reused holdout 已解锁，只作冻结候选的复用审计。",
            "- V1 的版本身份不因 clean surface 或微调而改变；除非另行登记，不创建新版本号。",
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
            "uv run research/btc/1h-adaptive-regime/scripts/research_btc_1h_ar_v1_full_ablation.py",
            "```",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
