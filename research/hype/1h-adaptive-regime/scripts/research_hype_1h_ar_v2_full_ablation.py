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
import research_hype_1h_ar_v1_full_ablation as v1_ablation  # noqa: E402
import research_hype_1h_ar_v2_clean_tune as v2  # noqa: E402


DATE_TAG = "2026-07-02"
FAMILY_DIR = ROOT / "research/hype/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
ABLATION_DIR = FAMILY_DIR / "ablations"
SUMMARY_JSON = ARTIFACT_DIR / f"hype_1h_ar_v2_full_ablation_{DATE_TAG}.json"
ROWS_CSV = ARTIFACT_DIR / f"hype_1h_ar_v2_full_ablation_rows_{DATE_TAG}.csv"
FIELDS_CSV = ARTIFACT_DIR / f"hype_1h_ar_v2_full_ablation_fields_{DATE_TAG}.csv"
WINDOWS_CSV = ARTIFACT_DIR / f"hype_1h_ar_v2_full_ablation_windows_{DATE_TAG}.csv"
REPORT_MD = ABLATION_DIR / f"hype-1h-ar-v2-full-parameter-ablation-{DATE_TAG}.md"

TRAIN_START = v1_ablation.TRAIN_START
PREFIT_END = v1_ablation.PREFIT_END


def signature(trades: list[base.Trade]) -> tuple[tuple[Any, ...], ...]:
    return v1_ablation.signature(trades)


def metric_columns(
    trades: list[base.Trade], full_end: pd.Timestamp
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    return v1_ablation.metric_columns(trades, full_end)


def di_field_variants() -> dict[str, list[Any]]:
    return {
        "ema_htf": [55, 144],
        "min_adx": [8.0, 20.0],
        "max_adx": [28.0, 45.0, 100.0],
        "min_rvol": [0.0, 1.5, 2.5],
        "max_atr_bps": [200.0, 300.0, 10_000.0],
        "roc_window": [12, 48],
        "min_dir_roc_bps": [-10_000.0, 0.0],
        "max_dist_ema_bps": [500.0, 1_000.0, 10_000.0],
        "htf_mode": ["none", "h4", "d1"],
        "require_body_dir": [False],
        "max_aligned_funding_bps": [2.0, 10_000.0],
        "tp_atr": [1.0, 2.0],
        "sl_atr": [3.0, 5.0],
        "max_hold_bars": [12, 24, 36],
        "fixed_leverage": [1.0, 2.0, 3.5],
    }


def stoch_field_variants() -> dict[str, list[Any]]:
    return {
        "indicator_window": [7, 14, 28],
        "threshold_low": [15.0, 20.0, 30.0, 35.0],
        "threshold_high": [55.0, 65.0, 70.0, 80.0],
        "ema_htf": [89, 144, 233],
        "min_adx": [0.0, 8.0, 20.0],
        "min_rvol": [0.0, 0.8, 1.5],
        "min_atr_bps": [0.0, 150.0, 250.0],
        "max_atr_bps": [300.0, 350.0, 600.0, 10_000.0],
        "max_dist_ema_bps": [500.0, 1_500.0, 10_000.0],
        "macd_fast": [12, 21, 34],
        "macd_slow": [26, 55, 89],
        "macd_signal": [9, 13],
        "require_macd_turn": [False],
        "sl_atr": [3.0, 5.0, 6.0],
        "trail_activation_atr": [0.5, 1.5, 2.0],
        "trail_atr": [0.5, 1.5, 2.0],
        "max_hold_bars": [6, 12, 18, 24],
        "cooldown_bars": [0, 12, 48],
        "fixed_leverage": [1.0, 1.5, 2.5, 3.0],
    }


def variants_for(
    *,
    component: str,
    cfg: v2.DICleanConfig | v2.StochCleanConfig,
) -> list[tuple[str, str, Any, v2.DICleanConfig | v2.StochCleanConfig]]:
    values_by_field = (
        di_field_variants() if component == "di_cross" else stoch_field_variants()
    )
    output: list[tuple[str, str, Any, v2.DICleanConfig | v2.StochCleanConfig]] = []
    for field_name, values in values_by_field.items():
        baseline = getattr(cfg, field_name)
        for value in values:
            if value == baseline:
                continue
            variant = replace(cfg, **{field_name: value})
            if isinstance(variant, v2.DICleanConfig) and variant.max_adx <= variant.min_adx:
                continue
            if (
                isinstance(variant, v2.StochCleanConfig)
                and variant.max_atr_bps <= variant.min_atr_bps
            ):
                continue
            label_value = str(value).replace(".", "p").replace("-", "m")
            output.append(
                (
                    f"{component}__{field_name}__{label_value}",
                    field_name,
                    value,
                    variant,
                )
            )
    return output


def simulate_component(
    *,
    frame: pd.DataFrame,
    funding_times: Any,
    funding_cumulative: Any,
    clean: v2.DICleanConfig | v2.StochCleanConfig,
    component: str,
    name: str,
) -> list[base.Trade]:
    cfg = (
        v2.di_to_base(clean, name)
        if component == "di_cross"
        else v2.stoch_to_base(clean, name)
    )
    return boundary.component_trades(frame, funding_times, funding_cumulative, cfg)


def ensure_extra_macd_features(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    close = result["close"].astype("float64")
    baseline = v2.StochCleanConfig()
    combos: set[tuple[int, int, int]] = {
        (baseline.macd_fast, baseline.macd_slow, baseline.macd_signal)
    }
    for _label, _field_name, _value, variant in variants_for(
        component="stoch_reversal", cfg=baseline
    ):
        assert isinstance(variant, v2.StochCleanConfig)
        combos.add((variant.macd_fast, variant.macd_slow, variant.macd_signal))
    for fast, slow, signal in combos:
        hist_col = f"macd_hist_{fast}_{slow}_{signal}"
        if hist_col in result.columns:
            continue
        line = close.ewm(span=fast, adjust=False, min_periods=fast).mean() - close.ewm(
            span=slow, adjust=False, min_periods=slow
        ).mean()
        signal_line = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
        result[f"macd_{fast}_{slow}_{signal}"] = line
        result[hist_col] = line - signal_line
    return result


def target_like_pass(values: dict[str, Any]) -> bool:
    holdout = {
        key.removeprefix("reused_holdout_"): value
        for key, value in values.items()
        if key.startswith("reused_holdout_")
    }
    full = {
        key.removeprefix("current_full_"): value
        for key, value in values.items()
        if key.startswith("current_full_")
    }
    return base.target_gate(holdout, full)


def pct(value: float) -> str:
    return base.pct(float(value))


def mult(value: float) -> str:
    return base.mult(float(value), digits=4)


def report_table_row(label: str, metric: dict[str, Any]) -> str:
    return (
        f"| {label} | `{mult(metric['annual_multiple'])}` | "
        f"`{pct(metric['total_return'])}` | `{pct(metric['max_dd'])}` | "
        f"`{pct(metric['win_rate'])}` | `{int(metric['trades'])}` | "
        f"`{metric['profit_factor']:.3f}` |"
    )


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    ABLATION_DIR.mkdir(parents=True, exist_ok=True)

    frame, funding, quality = base.load_data()
    frame = base.add_features(frame, funding)
    frame = ensure_extra_macd_features(frame)
    funding_times, funding_cumulative = base.funding_prefix(funding)
    full_end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(hours=1)

    di_clean = v2.DICleanConfig()
    stoch_clean = v2.StochCleanConfig()
    di_base = simulate_component(
        frame=frame,
        funding_times=funding_times,
        funding_cumulative=funding_cumulative,
        clean=di_clean,
        component="di_cross",
        name="HYPE_1H_AR_V2_DI",
    )
    stoch_base = simulate_component(
        frame=frame,
        funding_times=funding_times,
        funding_cumulative=funding_cumulative,
        clean=stoch_clean,
        component="stoch_reversal",
        name="HYPE_1H_AR_V2_STOCH",
    )
    baseline = base.merge_trade_sets(di_base, stoch_base, 1.0, 0.0)
    baseline_flat, baseline_windows = metric_columns(baseline, full_end)
    baseline_di_sig = signature(di_base)
    baseline_stoch_sig = signature(stoch_base)
    baseline_merged_sig = signature(baseline)

    rows: list[dict[str, Any]] = [
        {
            "label": "HYPE-1H-Adaptive-Regime-V2",
            "component": "ensemble",
            "field": "baseline",
            "value": "baseline",
            "component_path_equal": True,
            "merged_path_equal": True,
            "target_like_pass": target_like_pass(baseline_flat),
            **baseline_flat,
        }
    ]
    all_windows: list[dict[str, Any]] = [
        {"label": "HYPE-1H-Adaptive-Regime-V2", **item}
        for item in baseline_windows
    ]
    field_coverage = {
        "di_cross": {field.name for field in fields(v2.DICleanConfig)},
        "stoch_reversal": {field.name for field in fields(v2.StochCleanConfig)},
    }
    observed_coverage: dict[str, set[str]] = {"di_cross": set(), "stoch_reversal": set()}

    for component, clean, base_trades, other_trades, base_sig in (
        ("di_cross", di_clean, di_base, stoch_base, baseline_di_sig),
        ("stoch_reversal", stoch_clean, stoch_base, di_base, baseline_stoch_sig),
    ):
        leg_removed = other_trades
        flat, window_rows = metric_columns(leg_removed, full_end)
        rows.append(
            {
                "label": f"{component}__leg_removed",
                "component": component,
                "field": "leg_removed",
                "value": "leg_removed",
                "component_path_equal": False,
                "merged_path_equal": signature(leg_removed) == baseline_merged_sig,
                "target_like_pass": target_like_pass(flat),
                **flat,
            }
        )
        all_windows.extend(
            {"label": f"{component}__leg_removed", **item} for item in window_rows
        )

        for label, field_name, value, variant in variants_for(
            component=component, cfg=clean
        ):
            observed_coverage[component].add(field_name)
            component_trades = simulate_component(
                frame=frame,
                funding_times=funding_times,
                funding_cumulative=funding_cumulative,
                clean=variant,
                component=component,
                name=label,
            )
            if component == "di_cross":
                merged = base.merge_trade_sets(component_trades, stoch_base, 1.0, 0.0)
            else:
                merged = base.merge_trade_sets(di_base, component_trades, 1.0, 0.0)
            flat, window_rows = metric_columns(merged, full_end)
            rows.append(
                {
                    "label": label,
                    "component": component,
                    "field": field_name,
                    "value": value,
                    "component_path_equal": signature(component_trades) == base_sig,
                    "merged_path_equal": signature(merged) == baseline_merged_sig,
                    "target_like_pass": target_like_pass(flat),
                    **flat,
                }
            )
            all_windows.extend({"label": label, **item} for item in window_rows)

    missing = {
        component: sorted(field_coverage[component] - observed_coverage[component])
        for component in field_coverage
    }
    if any(missing.values()):
        raise RuntimeError(f"V2 clean ablation coverage missing fields: {missing}")

    rows_frame = pd.DataFrame(rows)
    rows_frame.to_csv(ROWS_CSV, index=False)
    pd.DataFrame(all_windows).to_csv(WINDOWS_CSV, index=False)

    field_rows: list[dict[str, Any]] = []
    for component, clean in (
        ("di_cross", di_clean),
        ("stoch_reversal", stoch_clean),
    ):
        for field_name in sorted(field_coverage[component]):
            subset = rows_frame.loc[
                (rows_frame["component"] == component)
                & (rows_frame["field"] == field_name)
            ]
            improved_prefit = subset[
                (subset["prefit_annual_multiple"] > baseline_flat["prefit_annual_multiple"])
                & (subset["prefit_max_dd"] > baseline_flat["prefit_max_dd"])
                & (subset["prefit_win_rate"] >= base.TARGET_WIN_RATE)
                & (~subset["merged_path_equal"])
            ]
            improved_current = subset[
                (
                    subset["current_full_annual_multiple"]
                    > baseline_flat["current_full_annual_multiple"]
                )
                & (subset["current_full_max_dd"] > baseline_flat["current_full_max_dd"])
                & (subset["current_full_win_rate"] >= base.TARGET_WIN_RATE)
                & (~subset["merged_path_equal"])
            ]
            field_rows.append(
                {
                    "component": component,
                    "field": field_name,
                    "baseline_value": getattr(clean, field_name),
                    "variant_rows": int(len(subset)),
                    "path_equal_rows": int(subset["merged_path_equal"].sum()),
                    "prefit_strict_improve_rows": int(len(improved_prefit)),
                    "current_strict_improve_rows": int(len(improved_current)),
                    "target_like_pass_rows": int(subset["target_like_pass"].sum()),
                    "best_prefit_annual_multiple": float(
                        subset["prefit_annual_multiple"].max()
                    ),
                    "best_current_full_annual_multiple": float(
                        subset["current_full_annual_multiple"].max()
                    ),
                }
            )
    fields_frame = pd.DataFrame(field_rows)
    fields_frame.to_csv(FIELDS_CSV, index=False)

    baseline_prefit = base.metrics(baseline, TRAIN_START, PREFIT_END)
    baseline_reused = base.metrics(baseline, PREFIT_END, full_end)
    baseline_current = base.metrics(baseline, TRAIN_START, full_end)
    prefit_strict = rows_frame[
        (rows_frame["prefit_annual_multiple"] > baseline_flat["prefit_annual_multiple"])
        & (rows_frame["prefit_max_dd"] > baseline_flat["prefit_max_dd"])
        & (rows_frame["prefit_win_rate"] >= base.TARGET_WIN_RATE)
        & (~rows_frame["merged_path_equal"])
    ].sort_values(["prefit_annual_multiple", "prefit_max_dd"], ascending=[False, False])
    current_strict = rows_frame[
        (rows_frame["current_full_annual_multiple"] > baseline_flat["current_full_annual_multiple"])
        & (rows_frame["current_full_max_dd"] > baseline_flat["current_full_max_dd"])
        & (rows_frame["current_full_win_rate"] >= base.TARGET_WIN_RATE)
        & (~rows_frame["merged_path_equal"])
    ].sort_values(
        ["current_full_annual_multiple", "current_full_max_dd"],
        ascending=[False, False],
    )
    target_like = rows_frame[
        (rows_frame["target_like_pass"]) & (~rows_frame["merged_path_equal"])
    ].sort_values(
        ["current_full_annual_multiple", "current_full_max_dd"],
        ascending=[False, False],
    )

    payload = {
        "family": "HYPE-1H-Adaptive-Regime",
        "version": "HYPE-1H-Adaptive-Regime-V2",
        "status": "clean_equivalent_diagnostic_baseline_not_live_ready",
        "date": DATE_TAG,
        "data_quality": quality,
        "data_end": full_end,
        "costs": {
            "fee_per_fill": base.FEE_PER_FILL,
            "slippage_per_fill": base.SLIPPAGE_PER_FILL,
            "funding": "actual_binance_history_per_trade",
        },
        "clean_field_counts": {
            "di_cross": len(field_coverage["di_cross"]),
            "stoch_reversal": len(field_coverage["stoch_reversal"]),
            "total": sum(len(items) for items in field_coverage.values()),
        },
        "coverage_missing": missing,
        "rows_including_baseline_and_leg_removed": int(len(rows_frame)),
        "baseline": {
            "prefit": baseline_prefit,
            "reused_holdout": baseline_reused,
            "current_full": baseline_current,
        },
        "prefit_strict_improve_rows": int(len(prefit_strict)),
        "current_strict_improve_rows": int(len(current_strict)),
        "target_like_pass_rows": int(len(target_like)),
        "top_prefit_strict": prefit_strict.head(20).to_dict(orient="records"),
        "top_current_strict": current_strict.head(20).to_dict(orient="records"),
        "target_like_rows": target_like.head(20).to_dict(orient="records"),
    }
    SUMMARY_JSON.write_text(
        json.dumps(base.json_safe(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    report_lines = [
        "# HYPE-1H-Adaptive-Regime-V2 全参数消融 - 2026-07-02",
        "",
        "## 结论",
        "",
        (
            "本轮以 `HYPE-1H-Adaptive-Regime-V2` clean baseline 为基线，"
            f"只覆盖 V2 clean 配置接口中的 `{payload['clean_field_counts']['total']}` 个字段槽："
            f"DI-cross `{payload['clean_field_counts']['di_cross']}` 个，"
            f"Stoch-reversal `{payload['clean_field_counts']['stoch_reversal']}` 个。"
        ),
        "",
        (
            f"共输出 `{len(rows_frame)}` 行（含 baseline 与两条 leg_removed 诊断行），"
            "coverage missing fields 为 `0`。"
        ),
        "",
        (
            f"单字段消融中，prefit 同时提高年化、降低回撤且胜率 `>=50%` 的行数为 "
            f"`{len(prefit_strict)}`；current full 同时提高年化、降低回撤且胜率 `>=50%` 的行数为 "
            f"`{len(current_strict)}`；完整 current full + reused holdout target-like 通过行数为 "
            f"`{len(target_like)}`。这些结果仍只作诊断，不构成新版本登记。"
        ),
        "",
        "## V2 当前数据复现",
        "",
        "| Window | Annual | Return | DD | Win | Trades | PF |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        report_table_row("Prefit", baseline_prefit),
        report_table_row("Reused holdout", baseline_reused),
        report_table_row("Current full", baseline_current),
        "",
        "## 字段覆盖",
        "",
        "| Component | Field | Baseline | Variant rows | Prefit improve | Current improve | Target-like pass |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in fields_frame.to_dict(orient="records"):
        report_lines.append(
            f"| `{row['component']}` | `{row['field']}` | `{row['baseline_value']}` | "
            f"`{row['variant_rows']}` | `{row['prefit_strict_improve_rows']}` | "
            f"`{row['current_strict_improve_rows']}` | `{row['target_like_pass_rows']}` |"
        )

    report_lines.extend(
        [
            "",
            "## Top current full 单字段改善诊断",
            "",
            "| Label | Current annual | Current DD | Current win | Current trades | Reused holdout annual | Reused holdout DD |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in current_strict.head(10).to_dict(orient="records"):
        report_lines.append(
            f"| `{row['label']}` | `{mult(row['current_full_annual_multiple'])}` | "
            f"`{pct(row['current_full_max_dd'])}` | `{pct(row['current_full_win_rate'])}` | "
            f"`{int(row['current_full_trades'])}` | `{mult(row['reused_holdout_annual_multiple'])}` | "
            f"`{pct(row['reused_holdout_max_dd'])}` |"
        )
    if current_strict.empty:
        report_lines.append("| - | - | - | - | - | - | - |")

    report_lines.extend(
        [
            "",
            "## Promotion 边界",
            "",
            "- 本轮是 V2 clean base 的 one-at-a-time 参数敏感性诊断，不使用 reused holdout 重新选参。",
            "- `target-like pass` 只代表 current full 与 reused holdout 在基础硬门槛形状上通过；它仍未包含 K+2、8 bps、真实 stop-market 滑点、生产 runner 和新增 forward trades。",
            "- Reused holdout 已在本家族多轮研究中解锁，不能重新包装为 untouched OOS。",
            "- 除非后续完成冻结参数后的 forward trades 与 live-executable 审计，否则不创建 V2.1/V3，不提升为 candidate、paper-live、dry-run、handoff 或 live。",
            "",
            "## 机器证据",
            "",
            f"- JSON：`artifacts/{SUMMARY_JSON.name}`",
            f"- 行级 CSV：`artifacts/{ROWS_CSV.name}`",
            f"- 字段级 CSV：`artifacts/{FIELDS_CSV.name}`",
            f"- 窗口 CSV：`artifacts/{WINDOWS_CSV.name}`",
            "",
            "复现：",
            "",
            "```bash",
            "uv run python research/hype/1h-adaptive-regime/scripts/research_hype_1h_ar_v2_full_ablation.py",
            "```",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(report_lines), encoding="utf-8")
    print(json.dumps(base.json_safe(payload), indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
