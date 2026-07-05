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

import sol_1h_ar_v1 as v1  # noqa: E402


FAMILY_DIR = ROOT / "research/sol/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
ABLATION_DIR = FAMILY_DIR / "ablations"
DATE_TAG = "2026-07-03"
SUMMARY_JSON = ARTIFACT_DIR / f"sol_1h_ar_v1_full_ablation_{DATE_TAG}.json"
ROWS_CSV = ARTIFACT_DIR / f"sol_1h_ar_v1_full_ablation_rows_{DATE_TAG}.csv"
FIELDS_CSV = ARTIFACT_DIR / f"sol_1h_ar_v1_full_ablation_fields_{DATE_TAG}.csv"
REPORT_MD = ABLATION_DIR / f"sol-1h-ar-v1-full-parameter-ablation-{DATE_TAG}.md"

CONTRACT_FIXED = {
    "name",
    "style",
    "side_mode",
    "exit_kind",
    "entry_delay_bars",
    "sizing_kind",
}

STYLE_FIELDS = {
    "ema_cross": {"ema_fast", "ema_slow"},
    "macd_flip": {"macd_fast", "macd_slow", "macd_signal"},
    "donchian_break": {"indicator_window"},
    "bb_revert": {"indicator_window", "band_k"},
    "bb_break": {"indicator_window", "band_k"},
    "rsi_reversal": {"indicator_window", "threshold_low", "threshold_high"},
    "stoch_reversal": {"indicator_window", "threshold_low", "threshold_high"},
    "cci_reversal": {"indicator_window", "threshold_high"},
    "williams_reversal": {
        "indicator_window",
        "threshold_low",
        "threshold_high",
    },
    "ema_pullback": {"ema_fast", "ema_slow", "pullback_atr"},
    "keltner_break": {"indicator_window", "band_k"},
    "squeeze_release": {"indicator_window", "threshold_low", "band_k"},
    "di_cross": set(),
    "vwap_revert": {"indicator_window", "band_k"},
    "momentum_break": {"roc_window", "roc_threshold_bps"},
    "wick_reject": {"threshold_low", "threshold_high", "band_k"},
}

ALWAYS_FILTER_FIELDS = {
    "ema_htf",
    "roc_window",
    "min_adx",
    "max_adx",
    "min_rvol",
    "min_atr_bps",
    "max_atr_bps",
    "min_dir_roc_bps",
    "max_dist_ema_bps",
    "htf_mode",
    "require_macd_turn",
    "require_body_dir",
    "max_aligned_funding_bps",
    "sl_atr",
    "max_hold_bars",
    "cooldown_bars",
}


def indicator_windows(engine: Any, style: str) -> list[int]:
    if style in {"bb_revert", "bb_break", "keltner_break", "squeeze_release"}:
        return list(engine.BAND_WINDOWS)
    if style == "donchian_break":
        return list(engine.DONCHIAN_WINDOWS)
    if style == "rsi_reversal":
        return list(engine.RSI_WINDOWS)
    if style == "stoch_reversal":
        return list(engine.STOCH_WINDOWS)
    if style in {"cci_reversal", "williams_reversal"}:
        return list(engine.CCI_WINDOWS)
    if style == "vwap_revert":
        return list(engine.VWAP_WINDOWS)
    return list(engine.BAND_WINDOWS)


def values_for_field(engine: Any, cfg: Any, field_name: str) -> list[Any]:
    values: dict[str, list[Any]] = {
        "name": [f"{cfg.name}_RENAMED"],
        "style": ["leg_removed"],
        "side_mode": ["both", "long", "short"],
        "ema_fast": list(engine.EMA_VALUES[:-1]),
        "ema_slow": list(engine.EMA_VALUES[1:]),
        "ema_htf": [55, 89, 144, 233, 377],
        "indicator_window": indicator_windows(engine, cfg.style),
        "threshold_low": [
            -95.0,
            -85.0,
            -70.0,
            -2.0,
            -1.0,
            0.0,
            0.15,
            0.25,
            0.35,
            15.0,
            25.0,
            35.0,
            40.0,
        ],
        "threshold_high": [
            -30.0,
            -15.0,
            -5.0,
            0.65,
            0.75,
            0.85,
            60.0,
            70.0,
            80.0,
            100.0,
            125.0,
            150.0,
            200.0,
        ],
        "band_k": [0.4, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 3.0, 4.0],
        "pullback_atr": [-0.75, -0.5, -0.25, 0.0, 0.25, 0.5, 0.75, 1.0],
        "roc_window": list(engine.ROC_WINDOWS),
        "roc_threshold_bps": [25.0, 50.0, 75.0, 100.0, 150.0, 200.0, 300.0, 500.0],
        "macd_fast": [item[0] for item in engine.MACD_SETS],
        "macd_slow": [item[1] for item in engine.MACD_SETS],
        "macd_signal": [item[2] for item in engine.MACD_SETS],
        "min_adx": [0.0, 8.0, 12.0, 16.0, 20.0, 24.0, 28.0, 32.0, 36.0, 40.0],
        "max_adx": [20.0, 24.0, 28.0, 32.0, 36.0, 40.0, 45.0, 55.0, 100.0],
        "min_rvol": [0.0, 0.4, 0.6, 0.8, 1.0, 1.25, 1.5, 2.0],
        "min_atr_bps": [0.0, 25.0, 50.0, 75.0, 100.0, 125.0, 150.0, 200.0],
        "max_atr_bps": [175.0, 200.0, 250.0, 300.0, 400.0, 600.0, 10_000.0],
        "min_dir_roc_bps": [
            -10_000.0,
            -300.0,
            -200.0,
            -100.0,
            -50.0,
            0.0,
            50.0,
            100.0,
            200.0,
            300.0,
        ],
        "max_dist_ema_bps": [
            200.0,
            300.0,
            500.0,
            750.0,
            1_000.0,
            1_500.0,
            2_500.0,
            10_000.0,
        ],
        "htf_mode": ["none", "h4", "h12", "d1"],
        "require_macd_turn": [False, True],
        "require_body_dir": [False, True],
        "max_aligned_funding_bps": [0.5, 1.0, 2.0, 4.0, 8.0, 10_000.0],
        "exit_kind": ["fixed", "trailing"],
        "tp_atr": [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0],
        "sl_atr": [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0],
        "trail_activation_atr": [0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0],
        "trail_atr": [0.4, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0],
        "max_hold_bars": [4, 6, 8, 12, 18, 24, 36, 48, 72, 96, 120, 168, 240, 336],
        "cooldown_bars": [0, 3, 6, 12, 18, 24, 36, 48],
        "entry_delay_bars": [1, 2, 3],
        "sizing_kind": ["fixed", "risk"],
        "fixed_leverage": [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 4.0, 5.0],
        "risk_fraction": [
            0.003,
            0.005,
            0.0075,
            0.01,
            0.0125,
            0.015,
            0.02,
            0.025,
            0.03,
            0.04,
        ],
        "max_leverage": [0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0],
    }
    return list(dict.fromkeys(values[field_name]))


def semantic_active_fields(cfg: Any) -> set[str]:
    active = set(ALWAYS_FILTER_FIELDS)
    active.update(STYLE_FIELDS[cfg.style])
    if cfg.require_macd_turn:
        active.update({"macd_fast", "macd_slow", "macd_signal"})
    if cfg.exit_kind == "fixed":
        active.add("tp_atr")
    else:
        active.update({"trail_activation_atr", "trail_atr"})
    if cfg.sizing_kind == "fixed":
        active.add("fixed_leverage")
    else:
        active.update({"risk_fraction", "max_leverage"})
    return active


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
        and row["train_total_return"] > 0.0
        and row["validation_total_return"] > 0.0
        and row["validation_max_dd"] > -0.20
    )


def valid_config(cfg: Any) -> bool:
    return bool(
        cfg.ema_fast < cfg.ema_slow
        and cfg.min_adx <= cfg.max_adx
        and cfg.min_atr_bps <= cfg.max_atr_bps
    )


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    ABLATION_DIR.mkdir(parents=True, exist_ok=True)
    engine, frame, funding, quality = v1.load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    configs = v1.v1_configs(engine)
    baseline_trades, component_trades, priorities = v1.simulate_v1(
        engine, frame, funding_times, funding_cumulative
    )
    baseline_signature = v1.trade_signature(baseline_trades)
    baseline_flat = flatten_metrics(v1.metrics(engine, baseline_trades))
    component_signatures = [v1.trade_signature(item) for item in component_trades]
    field_names = {field.name for field in fields(engine.StrategyConfig)}
    rows: list[dict[str, Any]] = [
        {
            "label": "SOL-1H-Adaptive-Regime-V1",
            "component": "ensemble",
            "field": "baseline",
            "value": "baseline",
            "component_path_equal": True,
            "merged_path_equal": True,
            "prefit_strict_improve": False,
            **baseline_flat,
        }
    ]
    observed: dict[str, set[str]] = {
        f"leg{index + 1}_{cfg.style}": set() for index, cfg in enumerate(configs)
    }

    for component_index, base_cfg in enumerate(configs):
        component = f"leg{component_index + 1}_{base_cfg.style}"
        for field_name in sorted(field_names):
            observed[component].add(field_name)
            candidates = values_for_field(engine, base_cfg, field_name)
            for value in candidates:
                if value == getattr(base_cfg, field_name):
                    continue
                label_value = str(value).replace(".", "p").replace("-", "m")
                label = f"{component}__{field_name}__{label_value}"
                if field_name == "style" and value == "leg_removed":
                    variant_configs = tuple(
                        cfg
                        for index, cfg in enumerate(configs)
                        if index != component_index
                    )
                    if variant_configs:
                        merged, variant_legs, _variant_priorities = v1.simulate_v1(
                            engine,
                            frame,
                            funding_times,
                            funding_cumulative,
                            configs=variant_configs,
                        )
                    else:
                        merged, variant_legs = [], []
                    changed_component_trades: list[Any] = []
                else:
                    changes = {field_name: value}
                    if field_name in {"macd_fast", "macd_slow", "macd_signal"}:
                        position = {
                            "macd_fast": 0,
                            "macd_slow": 1,
                            "macd_signal": 2,
                        }[field_name]
                        macd = next(
                            item for item in engine.MACD_SETS if item[position] == value
                        )
                        changes = {
                            "macd_fast": macd[0],
                            "macd_slow": macd[1],
                            "macd_signal": macd[2],
                        }
                    variant = replace(base_cfg, **changes)
                    if not valid_config(variant):
                        continue
                    variant_configs_list = list(configs)
                    variant_configs_list[component_index] = variant
                    merged, variant_legs, _variant_priorities = v1.simulate_v1(
                        engine,
                        frame,
                        funding_times,
                        funding_cumulative,
                        configs=tuple(variant_configs_list),
                    )
                    changed_component_trades = variant_legs[component_index]
                flat = flatten_metrics(v1.metrics(engine, merged))
                row = {
                    "label": label,
                    "component": component,
                    "field": field_name,
                    "baseline_value": getattr(base_cfg, field_name),
                    "value": value,
                    "semantic_active": field_name in semantic_active_fields(base_cfg),
                    "component_path_equal": (
                        False
                        if field_name == "style"
                        else v1.trade_signature(changed_component_trades)
                        == component_signatures[component_index]
                    ),
                    "merged_path_equal": v1.trade_signature(merged)
                    == baseline_signature,
                    **flat,
                }
                row["prefit_strict_improve"] = prefit_improves(row, baseline_flat)
                rows.append(row)

    coverage_missing = {
        component: sorted(field_names - fields_seen)
        for component, fields_seen in observed.items()
    }
    if any(coverage_missing.values()):
        raise RuntimeError(f"Ablation coverage missing: {coverage_missing}")

    rows_frame = pd.DataFrame(rows)
    field_rows: list[dict[str, Any]] = []
    for component_index, cfg in enumerate(configs):
        component = f"leg{component_index + 1}_{cfg.style}"
        semantic = semantic_active_fields(cfg)
        for field_name in sorted(field_names):
            subset = rows_frame.loc[
                (rows_frame["component"] == component)
                & (rows_frame["field"] == field_name)
            ]
            all_component_equal = bool(subset["component_path_equal"].all())
            if field_name in CONTRACT_FIXED:
                classification = "contract_fixed"
            elif field_name not in semantic:
                classification = "baseline_fixed_remove"
            elif all_component_equal:
                classification = "neutral_fixed_remove"
            else:
                classification = "active_tunable"
            field_rows.append(
                {
                    "component": component,
                    "field": field_name,
                    "baseline_value": getattr(cfg, field_name),
                    "classification": classification,
                    "variant_rows": int(len(subset)),
                    "component_path_equal_rows": int(
                        subset["component_path_equal"].sum()
                    ),
                    "merged_path_equal_rows": int(subset["merged_path_equal"].sum()),
                    "prefit_strict_improve_rows": int(
                        subset["prefit_strict_improve"].sum()
                    ),
                }
            )
    fields_frame = pd.DataFrame(field_rows)
    classification_map = {
        (row["component"], row["field"]): row["classification"] for row in field_rows
    }
    rows_frame["classification"] = rows_frame.apply(
        lambda row: (
            "baseline"
            if row["component"] == "ensemble"
            else classification_map[(row["component"], row["field"])]
        ),
        axis=1,
    )
    rows_frame.to_csv(ROWS_CSV, index=False)
    fields_frame.to_csv(FIELDS_CSV, index=False)

    strict = rows_frame.loc[rows_frame["prefit_strict_improve"]].sort_values(
        ["prefit_annual_multiple", "prefit_max_dd", "validation_annual_multiple"],
        ascending=[False, False, False],
    )
    classification_counts = (
        fields_frame["classification"].value_counts().sort_index().to_dict()
    )
    components = [f"leg{index + 1}_{cfg.style}" for index, cfg in enumerate(configs)]
    clean_surface = {
        component: fields_frame.loc[
            (fields_frame["component"] == component)
            & (fields_frame["classification"] == "active_tunable"),
            "field",
        ].tolist()
        for component in components
    }
    payload = {
        "family": "SOL-1H-Adaptive-Regime",
        "version": "SOL-1H-Adaptive-Regime-V1",
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
            "components": len(configs),
            "total": len(field_names) * len(configs),
            "coverage_missing": coverage_missing,
        },
        "classification_counts": classification_counts,
        "rows_including_baseline": len(rows_frame),
        "component_prefit_priority_scores": priorities,
        "baseline": v1.metrics(engine, baseline_trades),
        "prefit_strict_improve_rows": len(strict),
        "top_prefit_strict": strict.head(30).to_dict(orient="records"),
        "clean_surface": clean_surface,
    }
    SUMMARY_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    baseline = payload["baseline"]
    lines = [
        "# SOL-1H-Adaptive-Regime-V1 全参数消融 - 2026-07-03",
        "",
        "## 结论",
        "",
        (
            f"已覆盖 V1 `{len(configs)}` 条腿全部 `{len(field_names) * len(configs)}` 个 "
            f"StrategyConfig 字段槽，coverage missing 为 `0`。"
        ),
        "",
        f"分类结果：`{classification_counts}`。只有 `active_tunable` 进入 clean tuning surface；其余字段删除或硬编码。",
        "",
        (
            "one-at-a-time 变体中，严格满足 prefit 年化更高、回撤更小、胜率 >=50%、"
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
            "| Component | Field | Baseline | Classification | Variants | Component equal | Merged equal | Strict improve |",
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
            "## 选择边界",
            "",
            "- 删参只依据 V1 代码语义与路径等价性；不使用 reused holdout 决定保留字段。",
            "- 后续微调只读取 train、validation 与 prefit；reused holdout 已解锁，只作冻结候选复用审计。",
            "- V1 身份不因 clean surface 或微调而改变；除非用户另行登记，不创建新版本号。",
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
            "uv run python research/sol/1h-adaptive-regime/scripts/research_sol_1h_ar_v1_full_ablation.py",
            "```",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
