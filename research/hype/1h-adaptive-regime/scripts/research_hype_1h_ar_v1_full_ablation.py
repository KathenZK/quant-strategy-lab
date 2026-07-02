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

import audit_hype_1h_adaptive_regime_boundary as boundary  # noqa: E402
import research_hype_1h_adaptive_regime_search as base  # noqa: E402


DATE_TAG = "2026-07-02"
FAMILY_DIR = ROOT / "research/hype/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
ABLATION_DIR = FAMILY_DIR / "ablations"
SUMMARY_JSON = ARTIFACT_DIR / f"hype_1h_ar_v1_full_ablation_{DATE_TAG}.json"
ROWS_CSV = ARTIFACT_DIR / f"hype_1h_ar_v1_full_ablation_rows_{DATE_TAG}.csv"
FIELDS_CSV = ARTIFACT_DIR / f"hype_1h_ar_v1_full_ablation_fields_{DATE_TAG}.csv"
WINDOWS_CSV = ARTIFACT_DIR / f"hype_1h_ar_v1_full_ablation_windows_{DATE_TAG}.csv"
REPORT_MD = ABLATION_DIR / f"hype-1h-ar-v1-full-parameter-ablation-{DATE_TAG}.md"

TRAIN_START = pd.Timestamp("2025-07-14T10:00:00Z")
TRAIN_END = pd.Timestamp("2026-01-23T23:18:00Z")
PREFIT_END = pd.Timestamp("2026-04-13T03:39:00Z")

# These fields are not referenced by the corresponding style/execution branch.
STRUCTURAL_DORMANT: dict[str, set[str]] = {
    "di_cross": {
        "ema_fast",
        "ema_slow",
        "indicator_window",
        "threshold_low",
        "threshold_high",
        "band_k",
        "pullback_atr",
        "roc_threshold_bps",
        "macd_fast",
        "macd_slow",
        "macd_signal",
        "require_macd_turn",
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
        "tp_atr",
        "risk_fraction",
        "max_leverage",
    },
}

# These switches/bounds are deliberately disabled or tautological at V1.
DISABLED_OR_FIXED: dict[str, set[str]] = {
    "di_cross": {
        "side_mode",
        "min_atr_bps",
        "exit_kind",
        "cooldown_bars",
        "entry_delay_bars",
        "sizing_kind",
    },
    "stoch_reversal": {
        "side_mode",
        "max_adx",
        "roc_window",
        "min_dir_roc_bps",
        "htf_mode",
        "require_body_dir",
        "max_aligned_funding_bps",
        "exit_kind",
        "entry_delay_bars",
        "sizing_kind",
    },
}


def signature(trades: list[base.Trade]) -> tuple[tuple[Any, ...], ...]:
    return tuple(
        (
            trade.entry_i,
            trade.exit_i,
            trade.side,
            trade.entry_price,
            trade.exit_price,
            trade.exit_reason,
            trade.exposure,
            trade.net_ret_1x,
            trade.equity_ret,
        )
        for trade in trades
    )


def windows(full_end: pd.Timestamp) -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
    return {
        "train": (TRAIN_START, TRAIN_END),
        "validation": (TRAIN_END, PREFIT_END),
        "prefit": (TRAIN_START, PREFIT_END),
        "reused_holdout": (PREFIT_END, full_end),
        "current_full": (TRAIN_START, full_end),
        "last_30d": (max(TRAIN_START, full_end - pd.Timedelta(days=30)), full_end),
        "last_60d": (max(TRAIN_START, full_end - pd.Timedelta(days=60)), full_end),
        "last_90d": (max(TRAIN_START, full_end - pd.Timedelta(days=90)), full_end),
    }


def metric_columns(
    trades: list[base.Trade], full_end: pd.Timestamp
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    flat: dict[str, Any] = {}
    window_rows: list[dict[str, Any]] = []
    for name, (start, end) in windows(full_end).items():
        values = base.metrics(trades, start, end)
        for key, value in values.items():
            flat[f"{name}_{key}"] = value
        window_rows.append({"window": name, "start": start, "end": end, **values})
    return flat, window_rows


def variant_definitions(
    component: str, cfg: base.StrategyConfig
) -> list[tuple[str, tuple[str, ...], dict[str, Any] | None]]:
    variants: list[tuple[str, tuple[str, ...], dict[str, Any] | None]] = [
        (f"{component}__style__leg_removed", ("style",), None),
        (f"{component}__side_mode__long", ("side_mode",), {"side_mode": "long"}),
        (f"{component}__side_mode__short", ("side_mode",), {"side_mode": "short"}),
        (
            f"{component}__ema_pair__8_55",
            ("ema_fast", "ema_slow"),
            {"ema_fast": 8, "ema_slow": 55},
        ),
        (
            f"{component}__ema_pair__55_233",
            ("ema_fast", "ema_slow"),
            {"ema_fast": 55, "ema_slow": 233},
        ),
        (f"{component}__ema_htf__144", ("ema_htf",), {"ema_htf": 144}),
        (
            f"{component}__indicator_window__14",
            ("indicator_window",),
            {"indicator_window": 14},
        ),
        (
            f"{component}__indicator_window__28",
            ("indicator_window",),
            {"indicator_window": 28},
        ),
        (
            f"{component}__threshold_low__20",
            ("threshold_low",),
            {"threshold_low": 20.0},
        ),
        (
            f"{component}__threshold_low__35",
            ("threshold_low",),
            {"threshold_low": 35.0},
        ),
        (
            f"{component}__threshold_high__55",
            ("threshold_high",),
            {"threshold_high": 55.0},
        ),
        (
            f"{component}__threshold_high__70",
            ("threshold_high",),
            {"threshold_high": 70.0},
        ),
        (f"{component}__band_k__0p5", ("band_k",), {"band_k": 0.5}),
        (f"{component}__band_k__2", ("band_k",), {"band_k": 2.0}),
        (
            f"{component}__pullback_atr__m0p5",
            ("pullback_atr",),
            {"pullback_atr": -0.5},
        ),
        (
            f"{component}__pullback_atr__1",
            ("pullback_atr",),
            {"pullback_atr": 1.0},
        ),
        (f"{component}__roc_window__12", ("roc_window",), {"roc_window": 12}),
        (f"{component}__roc_window__48", ("roc_window",), {"roc_window": 48}),
        (
            f"{component}__roc_threshold__25",
            ("roc_threshold_bps",),
            {"roc_threshold_bps": 25.0},
        ),
        (
            f"{component}__roc_threshold__500",
            ("roc_threshold_bps",),
            {"roc_threshold_bps": 500.0},
        ),
        (
            f"{component}__macd_set__12_26_9",
            ("macd_fast", "macd_slow", "macd_signal"),
            {"macd_fast": 12, "macd_slow": 26, "macd_signal": 9},
        ),
        (
            f"{component}__macd_set__34_89_13",
            ("macd_fast", "macd_slow", "macd_signal"),
            {"macd_fast": 34, "macd_slow": 89, "macd_signal": 13},
        ),
        (f"{component}__min_adx__0", ("min_adx",), {"min_adx": 0.0}),
        (f"{component}__min_adx__20", ("min_adx",), {"min_adx": 20.0}),
        (f"{component}__max_adx__28", ("max_adx",), {"max_adx": 28.0}),
        (f"{component}__max_adx__100", ("max_adx",), {"max_adx": 100.0}),
        (f"{component}__min_rvol__0", ("min_rvol",), {"min_rvol": 0.0}),
        (f"{component}__min_rvol__1p5", ("min_rvol",), {"min_rvol": 1.5}),
        (
            f"{component}__min_atr_bps__100",
            ("min_atr_bps",),
            {"min_atr_bps": 100.0},
        ),
        (
            f"{component}__min_atr_bps__250",
            ("min_atr_bps",),
            {"min_atr_bps": 250.0},
        ),
        (
            f"{component}__max_atr_bps__300",
            ("max_atr_bps",),
            {"max_atr_bps": 300.0},
        ),
        (
            f"{component}__max_atr_bps__10000",
            ("max_atr_bps",),
            {"max_atr_bps": 10_000.0},
        ),
        (
            f"{component}__min_dir_roc__off",
            ("min_dir_roc_bps",),
            {"min_dir_roc_bps": -10_000.0},
        ),
        (
            f"{component}__min_dir_roc__0",
            ("min_dir_roc_bps",),
            {"min_dir_roc_bps": 0.0},
        ),
        (
            f"{component}__max_dist_ema__500",
            ("max_dist_ema_bps",),
            {"max_dist_ema_bps": 500.0},
        ),
        (
            f"{component}__max_dist_ema__10000",
            ("max_dist_ema_bps",),
            {"max_dist_ema_bps": 10_000.0},
        ),
        (f"{component}__htf_mode__none", ("htf_mode",), {"htf_mode": "none"}),
        (f"{component}__htf_mode__h4", ("htf_mode",), {"htf_mode": "h4"}),
        (f"{component}__htf_mode__d1", ("htf_mode",), {"htf_mode": "d1"}),
        (
            f"{component}__require_macd_turn__toggle",
            ("require_macd_turn",),
            {"require_macd_turn": not cfg.require_macd_turn},
        ),
        (
            f"{component}__require_body_dir__toggle",
            ("require_body_dir",),
            {"require_body_dir": not cfg.require_body_dir},
        ),
        (
            f"{component}__funding_cap__2",
            ("max_aligned_funding_bps",),
            {"max_aligned_funding_bps": 2.0},
        ),
        (
            f"{component}__funding_cap__off",
            ("max_aligned_funding_bps",),
            {"max_aligned_funding_bps": 10_000.0},
        ),
        (
            f"{component}__exit_kind__toggle",
            ("exit_kind",),
            {"exit_kind": "trailing" if cfg.exit_kind == "fixed" else "fixed"},
        ),
        (f"{component}__tp_atr__1", ("tp_atr",), {"tp_atr": 1.0}),
        (f"{component}__tp_atr__2", ("tp_atr",), {"tp_atr": 2.0}),
        (f"{component}__sl_atr__3", ("sl_atr",), {"sl_atr": 3.0}),
        (f"{component}__sl_atr__5", ("sl_atr",), {"sl_atr": 5.0}),
        (
            f"{component}__trail_activation__0p5",
            ("trail_activation_atr",),
            {"trail_activation_atr": 0.5},
        ),
        (
            f"{component}__trail_activation__2",
            ("trail_activation_atr",),
            {"trail_activation_atr": 2.0},
        ),
        (f"{component}__trail_atr__0p5", ("trail_atr",), {"trail_atr": 0.5}),
        (f"{component}__trail_atr__2", ("trail_atr",), {"trail_atr": 2.0}),
        (
            f"{component}__max_hold__6",
            ("max_hold_bars",),
            {"max_hold_bars": 6},
        ),
        (
            f"{component}__max_hold__24",
            ("max_hold_bars",),
            {"max_hold_bars": 24},
        ),
        (
            f"{component}__cooldown__0",
            ("cooldown_bars",),
            {"cooldown_bars": 0},
        ),
        (
            f"{component}__cooldown__12",
            ("cooldown_bars",),
            {"cooldown_bars": 12},
        ),
        (
            f"{component}__cooldown__48",
            ("cooldown_bars",),
            {"cooldown_bars": 48},
        ),
        (
            f"{component}__entry_delay__2",
            ("entry_delay_bars",),
            {"entry_delay_bars": 2},
        ),
        (
            f"{component}__sizing_kind__risk",
            ("sizing_kind",),
            {"sizing_kind": "risk"},
        ),
        (
            f"{component}__fixed_leverage__1",
            ("fixed_leverage",),
            {"fixed_leverage": 1.0},
        ),
        (
            f"{component}__fixed_leverage__3p5",
            ("fixed_leverage",),
            {"fixed_leverage": 3.5},
        ),
        (
            f"{component}__risk_fraction__0p005",
            ("risk_fraction",),
            {"risk_fraction": 0.005},
        ),
        (
            f"{component}__risk_fraction__0p04",
            ("risk_fraction",),
            {"risk_fraction": 0.04},
        ),
        (
            f"{component}__max_leverage__1",
            ("max_leverage",),
            {"max_leverage": 1.0},
        ),
        (
            f"{component}__max_leverage__5",
            ("max_leverage",),
            {"max_leverage": 5.0},
        ),
    ]
    # Remove exact baseline duplicates, which otherwise provide no perturbation evidence.
    unique: list[tuple[str, tuple[str, ...], dict[str, Any] | None]] = []
    seen: set[tuple[tuple[str, Any], ...] | tuple[str, ...]] = set()
    for label, changed, values in variants:
        if values is not None and all(getattr(cfg, key) == value for key, value in values.items()):
            continue
        key: tuple[tuple[str, Any], ...] | tuple[str, ...]
        key = tuple(sorted(values.items())) if values is not None else changed
        if key in seen:
            continue
        seen.add(key)
        unique.append((label, changed, values))
    return unique


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    ABLATION_DIR.mkdir(parents=True, exist_ok=True)
    left, right, left_priority, right_priority, source_payload = boundary.load_boundary()
    frame, funding, quality = base.load_data()
    frame = base.add_features(frame, funding)
    funding_times, funding_cumulative = base.funding_prefix(funding)
    full_end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(hours=1)

    baseline, left_base, right_base = boundary.ensemble_trades(
        frame,
        funding_times,
        funding_cumulative,
        left,
        right,
        left_priority,
        right_priority,
    )
    baseline_flat, baseline_windows = metric_columns(baseline, full_end)
    baseline_left_sig = signature(left_base)
    baseline_right_sig = signature(right_base)
    baseline_merged_sig = signature(baseline)

    rows: list[dict[str, Any]] = [
        {
            "label": "HYPE-1H-Adaptive-Regime-V1",
            "component": "ensemble",
            "changed_fields": "baseline",
            "changed_values": "baseline",
            "component_path_equal": True,
            "merged_path_equal": True,
            **baseline_flat,
        }
    ]
    all_windows: list[dict[str, Any]] = [
        {"label": "HYPE-1H-Adaptive-Regime-V1", **item}
        for item in baseline_windows
    ]
    coverage: dict[str, set[str]] = {"di_cross": set(), "stoch_reversal": set()}

    for component, cfg in (("di_cross", left), ("stoch_reversal", right)):
        for label, changed_fields, values in variant_definitions(component, cfg):
            coverage[component].update(changed_fields)
            if values is None:
                if component == "di_cross":
                    component_trades = []
                    merged = right_base
                    comparison = baseline_left_sig
                else:
                    component_trades = []
                    merged = left_base
                    comparison = baseline_right_sig
            else:
                variant = replace(cfg, **values)
                if variant.max_adx <= variant.min_adx or variant.max_atr_bps <= variant.min_atr_bps:
                    continue
                component_trades = boundary.component_trades(
                    frame, funding_times, funding_cumulative, variant
                )
                if component == "di_cross":
                    merged = base.merge_trade_sets(
                        component_trades,
                        right_base,
                        left_priority,
                        right_priority,
                    )
                    comparison = baseline_left_sig
                else:
                    merged = base.merge_trade_sets(
                        left_base,
                        component_trades,
                        left_priority,
                        right_priority,
                    )
                    comparison = baseline_right_sig
            flat, variant_windows = metric_columns(merged, full_end)
            component_equal = signature(component_trades) == comparison
            merged_equal = signature(merged) == baseline_merged_sig
            rows.append(
                {
                    "label": label,
                    "component": component,
                    "changed_fields": ",".join(changed_fields),
                    "changed_values": json.dumps(values, sort_keys=True) if values is not None else "leg_removed",
                    "component_path_equal": component_equal,
                    "merged_path_equal": merged_equal,
                    **flat,
                }
            )
            all_windows.extend({"label": label, **item} for item in variant_windows)

    parameter_fields = {field.name for field in fields(base.StrategyConfig)} - {"name"}
    for component in coverage:
        missing = parameter_fields - coverage[component]
        if missing:
            raise RuntimeError(f"{component} full-ablation coverage missing fields: {sorted(missing)}")

    rows_frame = pd.DataFrame(rows)
    rows_frame.to_csv(ROWS_CSV, index=False)
    pd.DataFrame(all_windows).to_csv(WINDOWS_CSV, index=False)

    field_rows: list[dict[str, Any]] = []
    for component in ("di_cross", "stoch_reversal"):
        for field_name in sorted(parameter_fields):
            mask = (rows_frame["component"] == component) & rows_frame[
                "changed_fields"
            ].str.split(",").apply(lambda values: field_name in values)
            subset = rows_frame.loc[mask]
            expected_class = (
                "structural_dormant"
                if field_name in STRUCTURAL_DORMANT[component]
                else (
                    "disabled_or_fixed"
                    if field_name in DISABLED_OR_FIXED[component]
                    else "active"
                )
            )
            all_component_equal = bool(subset["component_path_equal"].all())
            all_merged_equal = bool(subset["merged_path_equal"].all())
            remove_from_clean_config = expected_class in {
                "structural_dormant",
                "disabled_or_fixed",
            }
            field_rows.append(
                {
                    "component": component,
                    "field": field_name,
                    "baseline_value": getattr(left if component == "di_cross" else right, field_name),
                    "expected_class": expected_class,
                    "variant_rows": int(len(subset)),
                    "all_component_paths_equal": all_component_equal,
                    "all_merged_paths_equal": all_merged_equal,
                    "remove_from_v2_clean_config": remove_from_clean_config,
                    "evidence_note": (
                        "code branch does not reference field"
                        if expected_class == "structural_dormant"
                        else (
                            "V1 switch is fixed or bound intentionally disables filter"
                            if expected_class == "disabled_or_fixed"
                            else "field changes signal/filter/exit/sizing behavior"
                        )
                    ),
                }
            )
    fields_frame = pd.DataFrame(field_rows)
    fields_frame.to_csv(FIELDS_CSV, index=False)

    baseline_current = base.metrics(baseline, TRAIN_START, full_end)
    baseline_prefit = base.metrics(baseline, TRAIN_START, PREFIT_END)
    baseline_reused = base.metrics(baseline, PREFIT_END, full_end)
    strict_dominance = rows_frame[
        (rows_frame["prefit_annual_multiple"] > baseline_flat["prefit_annual_multiple"])
        & (rows_frame["prefit_max_dd"] > baseline_flat["prefit_max_dd"])
        & (rows_frame["prefit_win_rate"] >= 0.50)
        & (~rows_frame["merged_path_equal"])
    ].sort_values(
        ["prefit_annual_multiple", "prefit_max_dd"], ascending=[False, False]
    )
    payload = {
        "family": "HYPE-1H-Adaptive-Regime",
        "version": "HYPE-1H-Adaptive-Regime-V1",
        "status": "diagnostic_baseline_not_live_ready",
        "date": DATE_TAG,
        "source_boundary": source_payload["best"]["name"],
        "data_quality": quality,
        "data_end": full_end,
        "costs": {
            "fee_per_fill": base.FEE_PER_FILL,
            "slippage_per_fill": base.SLIPPAGE_PER_FILL,
            "funding": "actual_binance_history_per_trade",
        },
        "component_configs": {
            "di_cross": asdict(left),
            "stoch_reversal": asdict(right),
        },
        "baseline": {
            "prefit": baseline_prefit,
            "reused_holdout": baseline_reused,
            "current_full": baseline_current,
        },
        "coverage": {
            "config_fields_excluding_name": len(parameter_fields),
            "components": 2,
            "field_slots": len(parameter_fields) * 2,
            "ablation_rows_including_baseline": int(len(rows_frame)),
            "missing_fields": {
                component: sorted(parameter_fields - coverage[component])
                for component in coverage
            },
        },
        "classification": {
            "structural_dormant_fields": int(
                (fields_frame["expected_class"] == "structural_dormant").sum()
            ),
            "disabled_or_fixed_fields": int(
                (fields_frame["expected_class"] == "disabled_or_fixed").sum()
            ),
            "active_fields": int((fields_frame["expected_class"] == "active").sum()),
            "remove_from_v2_clean_config": int(
                fields_frame["remove_from_v2_clean_config"].sum()
            ),
        },
        "prefit_strict_dominance_rows": int(len(strict_dominance)),
        "top_prefit_strict_dominance": strict_dominance.head(20).to_dict(orient="records"),
    }
    SUMMARY_JSON.write_text(
        json.dumps(base.json_safe(payload), indent=2, ensure_ascii=False), encoding="utf-8"
    )

    removable = fields_frame.loc[fields_frame["remove_from_v2_clean_config"]]
    active = fields_frame.loc[~fields_frame["remove_from_v2_clean_config"]]
    report_lines = [
        "# HYPE-1H-Adaptive-Regime-V1 全参数消融 - 2026-07-02",
        "",
        "## 结论",
        "",
        f"本轮以冻结的 `DI-cross + Stoch-reversal` 边界组合登记为 `HYPE-1H-Adaptive-Regime-V1`，并覆盖 `StrategyConfig` 除 metadata `name` 外全部 `{len(parameter_fields)}` 个字段、两条腿共 `{len(parameter_fields) * 2}` 个 field slots。",
        "",
        f"共输出 `{len(rows_frame)}` 行（含 baseline）；coverage missing fields 为 `0`。识别 structural dormant `{payload['classification']['structural_dormant_fields']}` 个、disabled/fixed switch `{payload['classification']['disabled_or_fixed_fields']}` 个、active `{payload['classification']['active_fields']}` 个。V2 将从配置接口移除前两类共 `{payload['classification']['remove_from_v2_clean_config']}` 个 field slots，但会在专用状态机中硬编码必要的 K+1、退出类型和双向机制。",
        "",
        "## V1 当前数据复现",
        "",
        "| Window | Annual | Return | DD | Win | Trades | PF |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, metric in (
        ("Prefit", baseline_prefit),
        ("Reused holdout", baseline_reused),
        ("Current full", baseline_current),
    ):
        report_lines.append(
            f"| {label} | `{base.mult(metric['annual_multiple'])}` | `{base.pct(metric['total_return'])}` | `{base.pct(metric['max_dd'])}` | `{base.pct(metric['win_rate'])}` | `{int(metric['trades'])}` | `{metric['profit_factor']:.3f}` |"
        )
    report_lines.extend(
        [
            "",
            "## 将从 V2 配置接口移除的字段",
            "",
            "| Component | Field | Class | Baseline | Component path equal | Note |",
            "| --- | --- | --- | --- | ---: | --- |",
        ]
    )
    for row in removable.to_dict(orient="records"):
        report_lines.append(
            f"| `{row['component']}` | `{row['field']}` | `{row['expected_class']}` | `{row['baseline_value']}` | `{row['all_component_paths_equal']}` | {row['evidence_note']} |"
        )
    report_lines.extend(
        [
            "",
            "## V2 继续保留和可微调的 active 字段",
            "",
            "| Component | Field | Baseline | Variant rows |",
            "| --- | --- | --- | ---: |",
        ]
    )
    for row in active.to_dict(orient="records"):
        report_lines.append(
            f"| `{row['component']}` | `{row['field']}` | `{row['baseline_value']}` | `{row['variant_rows']}` |"
        )
    report_lines.extend(
        [
            "",
            "## 防过拟合与实盘边界",
            "",
            f"- 消融中 prefit 同时提高年化并降低回撤、胜率 `>=50%` 的单字段行：`{len(strict_dominance)}`。它们只用于决定 V2 微调方向，不使用 reused holdout 排名。",
            "- 所有交易继续使用 closed-bar signal、K+1 open 入场、入场即保护止损、stop gap-open、同 K stop-first、每 fill `0.001` fee + `4 bps` slippage 和实际 funding。",
            "- Reused holdout 已在上一轮研究中解锁，本轮只能作为诊断窗口，不能重新包装为 untouched OOS。",
            "- V1/V2 在 K+2 和高滑点压力未通过前均不得提升为 candidate、paper-live、dry-run、handoff 或 live。",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(report_lines), encoding="utf-8")
    print(json.dumps(base.json_safe(payload), indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()

