from __future__ import annotations

import json
import sys
from dataclasses import asdict, fields, replace
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import research_trx_1h_adaptive_regime_search as search  # noqa: E402


base = search.load_engine()

FAMILY_DIR = ROOT / "research/trx/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
ABLATION_DIR = FAMILY_DIR / "ablations"
DATE_TAG = "2026-07-05"
SOURCE_JSON = ARTIFACT_DIR / "trx_1h_adaptive_regime_refine_2026-07-03.json"
SUMMARY_JSON = ARTIFACT_DIR / f"trx_1h_ar_v1_full_ablation_{DATE_TAG}.json"
ROWS_CSV = ARTIFACT_DIR / f"trx_1h_ar_v1_full_ablation_rows_{DATE_TAG}.csv"
FIELDS_CSV = ARTIFACT_DIR / f"trx_1h_ar_v1_full_ablation_fields_{DATE_TAG}.csv"
REPORT_MD = ABLATION_DIR / f"trx-1h-ar-v1-full-parameter-ablation-{DATE_TAG}.md"


CONTRACT_FIXED = {
    "name",
    "style",
    "side_mode",
    "exit_kind",
    "entry_delay_bars",
    "sizing_kind",
}

SEMANTIC_DORMANT = {
    "macd_flip": {
        "ema_fast",
        "ema_slow",
        "indicator_window",
        "threshold_low",
        "threshold_high",
        "band_k",
        "pullback_atr",
        "roc_threshold_bps",
        "require_body_dir",
        "trail_activation_atr",
        "trail_atr",
        "risk_fraction",
        "max_leverage",
    },
    "stoch_reversal": {
        "ema_fast",
        "ema_slow",
        "band_k",
        "pullback_atr",
        "roc_threshold_bps",
        "macd_fast",
        "macd_slow",
        "macd_signal",
        "htf_mode",
        "require_macd_turn",
        "max_aligned_funding_bps",
        "tp_atr",
        "risk_fraction",
        "max_leverage",
    },
}

NEUTRAL_FIXED = {
    "macd_flip": {"min_atr_bps", "max_aligned_funding_bps"},
    "stoch_reversal": {"min_adx", "min_atr_bps", "max_atr_bps", "max_dist_ema_bps"},
}


def metric_bundle(
    trades: list[Any],
    *,
    train_start: pd.Timestamp,
    train_end: pd.Timestamp,
    oos_start: pd.Timestamp,
    full_end: pd.Timestamp,
) -> dict[str, dict[str, float]]:
    return {
        "train": base.metrics(trades, train_start, train_end),
        "validation": base.metrics(trades, train_end, oos_start),
        "prefit": base.metrics(trades, train_start, oos_start),
        "holdout": base.metrics(trades, oos_start, full_end),
        "full": base.metrics(trades, train_start, full_end),
    }


def flatten_metrics(metrics: dict[str, dict[str, float]]) -> dict[str, float]:
    return {
        f"{window}_{key}": value
        for window, window_metrics in metrics.items()
        for key, value in window_metrics.items()
    }


def trade_signature(trades: list[Any]) -> tuple[tuple[Any, ...], ...]:
    return tuple(
        (
            trade.signal_i,
            trade.entry_i,
            trade.exit_i,
            trade.side,
            trade.exit_reason,
            round(trade.entry_price, 12),
            round(trade.exit_price, 12),
            round(trade.equity_ret, 12),
        )
        for trade in trades
    )


def component_score(
    trades: list[Any],
    *,
    train_start: pd.Timestamp,
    train_end: pd.Timestamp,
    oos_start: pd.Timestamp,
) -> float:
    train = base.metrics(trades, train_start, train_end)
    validation = base.metrics(trades, train_end, oos_start)
    prefit = base.metrics(trades, train_start, oos_start)
    return base.prefit_score(train, validation, prefit)


def simulate_pair(
    configs: list[Any],
    *,
    frame: pd.DataFrame,
    funding_times: Any,
    funding_cumulative: Any,
    train_start: pd.Timestamp,
    train_end: pd.Timestamp,
    oos_start: pd.Timestamp,
) -> tuple[list[Any], dict[str, list[Any]], tuple[float, float]]:
    component_trades: dict[str, list[Any]] = {}
    priorities: list[float] = []
    for cfg in configs:
        trades = base.simulate_trades(
            frame,
            base.build_signal(frame, cfg),
            cfg,
            funding_times,
            funding_cumulative,
        )
        component_trades[cfg.name] = trades
        priorities.append(
            component_score(
                trades,
                train_start=train_start,
                train_end=train_end,
                oos_start=oos_start,
            )
        )
    merged = base.merge_trade_sets(
        component_trades[configs[0].name],
        component_trades[configs[1].name],
        priorities[0],
        priorities[1],
    )
    return merged, component_trades, (priorities[0], priorities[1])


def variant_values(component: str, cfg: Any) -> dict[str, list[Any]]:
    common = {
        "name": [f"{cfg.name}_RENAMED"],
        "style": ["leg_removed"],
        "require_macd_turn": [not cfg.require_macd_turn],
        "require_body_dir": [not cfg.require_body_dir],
        "entry_delay_bars": [2, 3],
        "sizing_kind": ["risk"],
    }
    if component == "macd_flip":
        return {
            **common,
            "side_mode": ["long", "short"],
            "ema_fast": [8, 13, 21],
            "ema_slow": [55, 144, 233],
            "ema_htf": [144, 233, 377],
            "indicator_window": [12, 48, 96],
            "threshold_low": [15.0, 30.0, 40.0],
            "threshold_high": [60.0, 75.0, 85.0],
            "band_k": [0.75, 1.5, 2.5],
            "pullback_atr": [-0.5, 0.0, 0.75],
            "roc_window": [3, 6, 24, 48],
            "roc_threshold_bps": [50.0, 150.0, 300.0],
            "macd_fast": [(8, 21, 5), (12, 26, 9), (21, 55, 9)],
            "macd_slow": [(8, 21, 5), (12, 26, 9), (21, 55, 9)],
            "macd_signal": [(8, 21, 5), (12, 26, 9), (21, 55, 9)],
            "min_adx": [0.0, 8.0, 16.0, 20.0],
            "max_adx": [24.0, 32.0, 45.0, 100.0],
            "min_rvol": [0.0, 0.8, 1.0, 2.0],
            "min_atr_bps": [25.0, 75.0, 125.0],
            "max_atr_bps": [175.0, 250.0, 400.0, 10_000.0],
            "min_dir_roc_bps": [-10_000.0, -300.0, 0.0, 100.0],
            "max_dist_ema_bps": [300.0, 500.0, 1_500.0, 10_000.0],
            "htf_mode": ["none", "h4", "d1"],
            "max_aligned_funding_bps": [0.5, 2.0, 8.0, 10_000.0],
            "exit_kind": ["trailing"],
            "tp_atr": [1.0, 1.5, 2.5, 4.0],
            "sl_atr": [2.0, 3.0, 5.0, 6.0],
            "trail_activation_atr": [0.75, 1.5, 4.0],
            "trail_atr": [0.75, 1.5, 3.0],
            "max_hold_bars": [72, 120, 240, 336],
            "cooldown_bars": [0, 6, 12, 24],
            "fixed_leverage": [1.0, 2.0, 3.0, 5.0],
            "risk_fraction": [0.005, 0.015, 0.03],
            "max_leverage": [1.0, 2.5, 5.0],
        }
    return {
        **common,
        "side_mode": ["both", "short"],
        "ema_fast": [13, 55, 144],
        "ema_slow": [89, 233, 377],
        "ema_htf": [55, 144, 233],
        "indicator_window": [7, 14, 28],
        "threshold_low": [15.0, 20.0, 30.0, 35.0],
        "threshold_high": [65.0, 75.0, 80.0],
        "band_k": [0.75, 1.5, 2.5],
        "pullback_atr": [-0.5, 0.0, 0.75],
        "roc_window": [6, 12, 24, 48],
        "roc_threshold_bps": [50.0, 150.0, 300.0],
        "macd_fast": [8, 12, 34],
        "macd_slow": [26, 55, 89],
        "macd_signal": [5, 9, 13],
        "min_adx": [8.0, 16.0, 24.0],
        "max_adx": [20.0, 24.0, 36.0, 100.0],
        "min_rvol": [0.0, 0.6, 1.5, 2.0],
        "min_atr_bps": [25.0, 75.0, 125.0],
        "max_atr_bps": [175.0, 250.0, 600.0, 10_000.0],
        "min_dir_roc_bps": [-10_000.0, -100.0, 0.0, 100.0],
        "max_dist_ema_bps": [300.0, 750.0, 1_500.0, 10_000.0],
        "htf_mode": ["h4", "h12", "d1"],
        "max_aligned_funding_bps": [0.5, 2.0, 8.0, 10_000.0],
        "exit_kind": ["fixed"],
        "tp_atr": [1.0, 2.0, 4.0, 6.0],
        "sl_atr": [2.0, 3.0, 4.0, 6.0],
        "trail_activation_atr": [1.0, 2.0, 4.0, 5.0],
        "trail_atr": [0.75, 1.0, 2.0, 3.0],
        "max_hold_bars": [72, 120, 240, 336],
        "cooldown_bars": [0, 6, 12, 48],
        "fixed_leverage": [1.0, 2.0, 4.0, 5.0],
        "risk_fraction": [0.005, 0.015, 0.03],
        "max_leverage": [1.0, 2.5, 5.0],
    }


def classification(component: str, field: str) -> str:
    if field in CONTRACT_FIXED:
        return "contract_fixed"
    if field in SEMANTIC_DORMANT[component]:
        return "baseline_fixed_remove"
    if field in NEUTRAL_FIXED[component]:
        return "neutral_fixed_remove"
    return "active_tunable"


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
        f"`{metric['annual_multiple']:.4f}x` | `{metric['total_return']:.2%}` | "
        f"`{metric['max_dd']:.2%}` | `{metric['win_rate']:.2%}` | "
        f"`{int(metric['trades'])}` | `{metric['profit_factor']:.3f}`"
    )


def main() -> None:
    if not SOURCE_JSON.exists():
        raise FileNotFoundError("Run the TRX refinement before V1 ablation")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    ABLATION_DIR.mkdir(parents=True, exist_ok=True)

    source = json.loads(SOURCE_JSON.read_text(encoding="utf-8"))
    frame, funding, quality = search.load_data()
    frame = base.add_features(frame, funding)
    funding_times, funding_cumulative = base.funding_prefix(funding)

    raw_start = pd.Timestamp(frame["ts"].iloc[0])
    full_end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(hours=1)
    train_start = raw_start + pd.Timedelta(days=search.WARMUP_DAYS)
    oos_start = full_end - pd.DateOffset(months=search.LOCKED_OOS_MONTHS)
    train_end = train_start + (oos_start - train_start) * 0.65

    config_names = str(source["best"]["config_names"]).split("+")
    configs = [
        base.StrategyConfig(**source["retained_configs"][name])
        for name in config_names
    ]
    component_by_style = {cfg.style: cfg for cfg in configs}
    required_styles = {"macd_flip", "stoch_reversal"}
    if set(component_by_style) != required_styles:
        raise RuntimeError(f"Unexpected V1 styles: {sorted(component_by_style)}")

    baseline_trades, component_trades, priorities = simulate_pair(
        configs,
        frame=frame,
        funding_times=funding_times,
        funding_cumulative=funding_cumulative,
        train_start=train_start,
        train_end=train_end,
        oos_start=oos_start,
    )
    baseline_metrics = metric_bundle(
        baseline_trades,
        train_start=train_start,
        train_end=train_end,
        oos_start=oos_start,
        full_end=full_end,
    )
    baseline_flat = flatten_metrics(baseline_metrics)

    expected = source["best"]
    for window in ("train", "validation", "prefit", "holdout", "full"):
        for metric in ("trades", "annual_multiple", "max_dd", "win_rate"):
            observed = float(baseline_metrics[window][metric])
            recorded = float(expected[f"{window}_{metric}"])
            if abs(observed - recorded) > 1e-12:
                raise RuntimeError(
                    f"Baseline reproduction drift at {window}.{metric}: "
                    f"{observed} != {recorded}"
                )

    baseline_signature = trade_signature(baseline_trades)
    component_signatures = {
        cfg.style: trade_signature(component_trades[cfg.name]) for cfg in configs
    }
    rows: list[dict[str, Any]] = [
        {
            "label": "TRX-1H-Adaptive-Regime-V1",
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
    field_names = {field.name for field in fields(base.StrategyConfig)}
    observed: dict[str, set[str]] = {style: set() for style in required_styles}

    for component in ("macd_flip", "stoch_reversal"):
        base_cfg = component_by_style[component]
        other_cfg = next(cfg for cfg in configs if cfg.name != base_cfg.name)
        values_by_field = variant_values(component, base_cfg)
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
                    component_variant_trades: list[Any] = []
                    merged = component_trades[other_cfg.name]
                else:
                    if (
                        component == "macd_flip"
                        and field_name in {"macd_fast", "macd_slow", "macd_signal"}
                    ):
                        variant = replace(
                            base_cfg,
                            macd_fast=value[0],
                            macd_slow=value[1],
                            macd_signal=value[2],
                        )
                    else:
                        variant = replace(base_cfg, **{field_name: value})
                    if variant.ema_fast >= variant.ema_slow:
                        continue
                    if variant.min_adx > variant.max_adx:
                        continue
                    if variant.min_atr_bps > variant.max_atr_bps:
                        continue
                    variant_configs = (
                        [variant, other_cfg]
                        if configs[0].name == base_cfg.name
                        else [other_cfg, variant]
                    )
                    merged, variant_component_trades, _variant_priorities = simulate_pair(
                        variant_configs,
                        frame=frame,
                        funding_times=funding_times,
                        funding_cumulative=funding_cumulative,
                        train_start=train_start,
                        train_end=train_end,
                        oos_start=oos_start,
                    )
                    component_variant_trades = variant_component_trades[variant.name]
                flat = flatten_metrics(
                    metric_bundle(
                        merged,
                        train_start=train_start,
                        train_end=train_end,
                        oos_start=oos_start,
                        full_end=full_end,
                    )
                )
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
                        else trade_signature(component_variant_trades)
                        == component_signatures[component]
                    ),
                    "merged_path_equal": trade_signature(merged) == baseline_signature,
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
    rows_frame.to_csv(ROWS_CSV, index=False)

    field_rows: list[dict[str, Any]] = []
    for component in ("macd_flip", "stoch_reversal"):
        cfg = component_by_style[component]
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
                    "merged_path_equal_rows": int(subset["merged_path_equal"].sum()),
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
    clean_surface = {
        component: fields_frame.loc[
            (fields_frame["component"] == component)
            & fields_frame["classification"].isin(["contract_fixed", "active_tunable"]),
            "field",
        ].tolist()
        for component in ("macd_flip", "stoch_reversal")
    }
    removed_fields = {
        component: fields_frame.loc[
            (fields_frame["component"] == component)
            & fields_frame["classification"].isin(
                ["baseline_fixed_remove", "neutral_fixed_remove"]
            ),
            "field",
        ].tolist()
        for component in ("macd_flip", "stoch_reversal")
    }
    v1_clean_equivalent_components = {
        component: {
            field: asdict(component_by_style[component])[field]
            for field in clean_surface[component]
        }
        for component in ("macd_flip", "stoch_reversal")
    }

    payload = {
        "family": "TRX-1H-Adaptive-Regime",
        "baseline_version": "TRX-1H-Adaptive-Regime-V1",
        "clean_version": "TRX-1H-Adaptive-Regime-V1-clean-equivalent",
        "status": "full_parameter_ablation_complete_v1_clean_equivalent_no_go_not_live_ready",
        "date": DATE_TAG,
        "source_observation": source["best"]["name"],
        "data_quality": quality,
        "costs": {
            "fee_per_fill": base.FEE_PER_FILL,
            "slippage_per_fill": base.SLIPPAGE_PER_FILL,
            "funding": "actual_binance_history_per_trade",
        },
        "field_slots": {
            "per_component": len(field_names),
            "total": len(field_names) * 2,
            "coverage_missing": coverage_missing,
        },
        "classification_counts": classification_counts,
        "rows_including_baseline": len(rows_frame),
        "component_prefit_priority_scores": {
            configs[0].name: priorities[0],
            configs[1].name: priorities[1],
        },
        "baseline": baseline_metrics,
        "prefit_strict_improve_rows": len(strict),
        "top_prefit_strict": strict.head(30).to_dict(orient="records"),
        "clean_surface": clean_surface,
        "removed_fields": removed_fields,
        "v1_clean_equivalent_components": v1_clean_equivalent_components,
        "v1_clean_behavior": "identical_to_v1_when removed fields keep engine defaults/neutral constants",
    }
    SUMMARY_JSON.write_text(
        json.dumps(search.json_safe(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    lines = [
        "# TRX-1H-Adaptive-Regime-V1 全参数消融 - 2026-07-05",
        "",
        "## 结论",
        "",
        (
            f"已覆盖 V1 两个组件全部 `{len(field_names) * 2}` 个 StrategyConfig 字段槽，"
            f"MACD `{len(field_names)}` 个、Stochastic `{len(field_names)}` 个，coverage missing 为 `0`。"
        ),
        "",
        (
            f"分类结果：`{classification_counts}`。`baseline_fixed_remove` 与 "
            "`neutral_fixed_remove` 从 V1 clean-equivalent 参数面移除；`contract_fixed` 作为实现常量保留，"
            "但不再作为可调搜索参数。该 clean-equivalent 参数面已于 2026-07-06 按用户指令正式登记为 "
            "`TRX-1H-Adaptive-Regime-V2`。"
        ),
        "",
        (
            f"one-at-a-time 变体中，严格满足 prefit 年化更高、回撤更小、胜率 >=50%、"
            f"train/validation 同正且 validation DD<20% 的行数为 `{len(strict)}`。"
        ),
        "",
        "V1 clean-equivalent 是 V1 的删参干净版，行为等价边界仍为 `NO-GO / not promoted / not live-ready`；"
        "后续正式版本名为 `TRX-1H-Adaptive-Regime-V2`，但它不是 candidate、paper-live、dry-run、handoff 或 live 版本。",
        "",
        "## V1 基线",
        "",
        "| Window | Annual | Return | DD | Win | Trades | PF |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for window in ("train", "validation", "prefit", "holdout", "full"):
        lines.append(f"| `{window}` | {metric_line(baseline_metrics[window])} |")
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
            "## V1 Clean-equivalent 参数面",
            "",
            f"- `macd_flip` 保留字段：`{clean_surface['macd_flip']}`。",
            f"- `macd_flip` 移除字段：`{removed_fields['macd_flip']}`。",
            f"- `stoch_reversal` 保留字段：`{clean_surface['stoch_reversal']}`。",
            f"- `stoch_reversal` 移除字段：`{removed_fields['stoch_reversal']}`。",
            "",
            "## Prefit 严格改善单字段 Top 20",
            "",
            "| Label | Prefit annual | Prefit DD | Prefit win | Validation annual | Validation DD | Holdout annual | Holdout DD |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in strict.head(20).to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{row['prefit_annual_multiple']:.4f}x` | "
            f"`{row['prefit_max_dd']:.2%}` | `{row['prefit_win_rate']:.2%}` | "
            f"`{row['validation_annual_multiple']:.4f}x` | "
            f"`{row['validation_max_dd']:.2%}` | "
            f"`{row['holdout_annual_multiple']:.4f}x` | "
            f"`{row['holdout_max_dd']:.2%}` |"
        )
    if strict.empty:
        lines.append("| - | - | - | - | - | - | - | - |")
    lines.extend(
        [
            "",
            "## 选择边界",
            "",
            "- V1 登记的是既有领先观察值，不改变其 OOS 亏损和 hard-gate 失败事实。",
            "- V1 clean-equivalent 只移除语义休眠字段和 neutral fixed 字段；不使用 locked OOS 选择新参数；该 clean-equivalent 参数面后续登记为 `TRX-1H-Adaptive-Regime-V2`。",
            "- V2 后续若重新搜索，只能读取 train/validation/prefit；当前 locked OOS 已解锁，只能作复用审计。",
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
            "uv run python research/trx/1h-adaptive-regime/scripts/research_trx_1h_ar_v1_full_ablation.py",
            "```",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(search.json_safe(payload), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
