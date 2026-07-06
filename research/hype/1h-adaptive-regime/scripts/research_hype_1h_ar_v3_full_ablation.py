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


DATE_TAG = "2026-07-06"
FAMILY_DIR = ROOT / "research/hype/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
ABLATION_DIR = FAMILY_DIR / "ablations"
SUMMARY_JSON = ARTIFACT_DIR / f"hype_1h_ar_v3_full_ablation_{DATE_TAG}.json"
ROWS_CSV = ARTIFACT_DIR / f"hype_1h_ar_v3_full_ablation_rows_{DATE_TAG}.csv"
FIELDS_CSV = ARTIFACT_DIR / f"hype_1h_ar_v3_full_ablation_fields_{DATE_TAG}.csv"
WINDOWS_CSV = ARTIFACT_DIR / f"hype_1h_ar_v3_full_ablation_windows_{DATE_TAG}.csv"
ROLLING_CSV = ARTIFACT_DIR / f"hype_1h_ar_v3_rolling_windows_{DATE_TAG}.csv"
REPORT_MD = ABLATION_DIR / f"hype-1h-ar-v3-full-parameter-ablation-{DATE_TAG}.md"

TRAIN_START = v1_ablation.TRAIN_START
PREFIT_END = v1_ablation.PREFIT_END


def v3_di_config() -> v2.DICleanConfig:
    return replace(v2.DICleanConfig(), min_dir_roc_bps=-10_000.0)


def v3_stoch_config() -> v2.StochCleanConfig:
    return replace(v2.StochCleanConfig(), threshold_high=55.0)


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
        "min_dir_roc_bps": [-200.0, 0.0],
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
        "threshold_high": [60.0, 65.0, 70.0, 80.0],
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


def ensure_extra_macd_features(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    close = result["close"].astype("float64")
    baseline = v3_stoch_config()
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


def recent_window_rows(
    label: str, trades: list[base.Trade], full_end: pd.Timestamp
) -> list[dict[str, Any]]:
    windows = [
        ("last_7d", max(TRAIN_START, full_end - pd.Timedelta(days=7)), full_end),
        ("last_30d", max(TRAIN_START, full_end - pd.Timedelta(days=30)), full_end),
        ("last_90d", max(TRAIN_START, full_end - pd.Timedelta(days=90)), full_end),
        ("last_180d", max(TRAIN_START, full_end - pd.Timedelta(days=180)), full_end),
        ("last_365d", max(TRAIN_START, full_end - pd.Timedelta(days=365)), full_end),
    ]
    return [
        {"label": label, "window": name, "start": start, "end": end, **base.metrics(trades, start, end)}
        for name, start, end in windows
    ]


def rolling_window_rows(trades: list[base.Trade], full_end: pd.Timestamp) -> list[dict[str, Any]]:
    definitions = [
        ("rolling_7d_step7d", 7, 7),
        ("rolling_30d_step30d", 30, 30),
        ("rolling_90d_step30d", 90, 30),
        ("rolling_180d_step30d", 180, 30),
    ]
    rows: list[dict[str, Any]] = []
    for kind, window_days, step_days in definitions:
        cursor = TRAIN_START
        index = 1
        width = pd.Timedelta(days=window_days)
        step = pd.Timedelta(days=step_days)
        while cursor + width <= full_end:
            end = cursor + width
            rows.append(
                {
                    "kind": kind,
                    "window": f"{kind}_{index:03d}",
                    "start": cursor,
                    "end": end,
                    **base.metrics(trades, cursor, end),
                }
            )
            cursor += step
            index += 1
    return rows


def rolling_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frame = pd.DataFrame(rows)
    output: list[dict[str, Any]] = []
    for kind, group in frame.groupby("kind", sort=False):
        nonzero = group[group["trades"] > 0]
        output.append(
            {
                "kind": kind,
                "windows": int(len(group)),
                "zero_trade_windows": int((group["trades"] == 0).sum()),
                "positive_windows": int((group["total_return"] > 0).sum()),
                "median_trades": float(group["trades"].median()),
                "min_trades": int(group["trades"].min()),
                "max_trades": int(group["trades"].max()),
                "median_win_rate_nonzero": float(nonzero["win_rate"].median()) if len(nonzero) else 0.0,
                "worst_total_return": float(group["total_return"].min()),
                "best_total_return": float(group["total_return"].max()),
            }
        )
    return output


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

    di_clean = v3_di_config()
    stoch_clean = v3_stoch_config()
    di_base = simulate_component(
        frame=frame,
        funding_times=funding_times,
        funding_cumulative=funding_cumulative,
        clean=di_clean,
        component="di_cross",
        name="HYPE_1H_AR_V3_DI",
    )
    stoch_base = simulate_component(
        frame=frame,
        funding_times=funding_times,
        funding_cumulative=funding_cumulative,
        clean=stoch_clean,
        component="stoch_reversal",
        name="HYPE_1H_AR_V3_STOCH",
    )
    baseline = base.merge_trade_sets(di_base, stoch_base, 1.0, 0.0)
    baseline_flat, baseline_windows = metric_columns(baseline, full_end)
    baseline_di_sig = signature(di_base)
    baseline_stoch_sig = signature(stoch_base)
    baseline_merged_sig = signature(baseline)

    rows: list[dict[str, Any]] = [
        {
            "label": "HYPE-1H-Adaptive-Regime-V3",
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
        {"label": "HYPE-1H-Adaptive-Regime-V3", **item}
        for item in baseline_windows
    ]
    recent_rows = recent_window_rows("HYPE-1H-Adaptive-Regime-V3", baseline, full_end)
    rolling_rows = rolling_window_rows(baseline, full_end)
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
        all_windows.extend({"label": f"{component}__leg_removed", **item} for item in window_rows)

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
        raise RuntimeError(f"V3 clean ablation coverage missing fields: {missing}")

    rows_frame = pd.DataFrame(rows)
    rows_frame.to_csv(ROWS_CSV, index=False)
    pd.DataFrame(all_windows).to_csv(WINDOWS_CSV, index=False)
    pd.DataFrame(rolling_rows).to_csv(ROLLING_CSV, index=False)

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
            improved_current = subset[
                (subset["current_full_annual_multiple"] > baseline_flat["current_full_annual_multiple"])
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
                    "current_strict_improve_rows": int(len(improved_current)),
                    "target_like_pass_rows": int(subset["target_like_pass"].sum()),
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
    roll_summary = rolling_summary(rolling_rows)
    payload = {
        "family": "HYPE-1H-Adaptive-Regime",
        "version": "HYPE-1H-Adaptive-Regime-V3",
        "status": "diagnostic_registered_baseline_no_go_not_live_ready",
        "date": DATE_TAG,
        "data_quality": quality,
        "data_end": full_end,
        "costs": {
            "fee_per_fill": base.FEE_PER_FILL,
            "slippage_per_fill": base.SLIPPAGE_PER_FILL,
            "funding": "actual_binance_history_per_trade",
        },
        "configs": {
            "di_cross": asdict(di_clean),
            "stoch_reversal": asdict(stoch_clean),
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
            "recent_windows": recent_rows,
            "rolling_summary": roll_summary,
        },
        "current_strict_improve_rows": int(len(current_strict)),
        "target_like_pass_rows": int(len(target_like)),
        "top_current_strict": current_strict.head(20).to_dict(orient="records"),
        "target_like_rows": target_like.head(20).to_dict(orient="records"),
    }
    SUMMARY_JSON.write_text(
        json.dumps(base.json_safe(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    report_lines = [
        "# HYPE-1H-Adaptive-Regime-V3 全参数消融与时间片复核 - 2026-07-06",
        "",
        "## 结论",
        "",
        "`HYPE-1H-Adaptive-Regime-V3` 按用户要求登记为 V3 diagnostic baseline，来源为 V2 消融引导组合 `di_roc_off__stoch_th55`。",
        "",
        (
            f"本轮以 V3 为 baseline，覆盖 clean 配置接口 `{payload['clean_field_counts']['total']}` 个字段槽："
            f"DI-cross `{payload['clean_field_counts']['di_cross']}` 个，"
            f"Stoch-reversal `{payload['clean_field_counts']['stoch_reversal']}` 个；"
            f"输出 `{len(rows_frame)}` 行，coverage missing fields 为 `0`。"
        ),
        "",
        (
            f"V3 current full 为 `{mult(baseline_current['annual_multiple'])}`、"
            f"DD `{pct(baseline_current['max_dd'])}`、"
            f"胜率 `{pct(baseline_current['win_rate'])}`、"
            f"`{int(baseline_current['trades'])}` 笔；"
            f"reused holdout 为 `{mult(baseline_reused['annual_multiple'])}`、"
            f"DD `{pct(baseline_reused['max_dd'])}`。"
        ),
        "",
        (
            f"单字段消融中 current full 同时提高年化、降低回撤且胜率 `>=50%` 的行数为 "
            f"`{len(current_strict)}`；完整 current full + reused holdout target-like 通过行数为 "
            f"`{len(target_like)}`。"
        ),
        "",
        "结论：V3 比 V2 baseline 明显更强，但 reused holdout 年化仍低于 `10x`，且前序 K+2/8bps 组合压力已失败；仍维持 `NO-GO / not live-ready / not promoted`。",
        "",
        "## V3 参数",
        "",
        "### DI-cross",
        "",
        "```text",
        *[f"{key}={value}" for key, value in asdict(di_clean).items()],
        "```",
        "",
        "### Stoch-reversal",
        "",
        "```text",
        *[f"{key}={value}" for key, value in asdict(stoch_clean).items()],
        "```",
        "",
        "## V3 当前数据复现",
        "",
        "| Window | Annual | Return | DD | Win | Trades | PF |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        report_table_row("Prefit", baseline_prefit),
        report_table_row("Reused holdout", baseline_reused),
        report_table_row("Current full", baseline_current),
        "",
        "## 最近窗口",
        "",
        "| Window | Trades | Win | Return | DD | Annual |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in recent_rows:
        report_lines.append(
            f"| `{row['window']}` | `{int(row['trades'])}` | `{pct(row['win_rate'])}` | "
            f"`{pct(row['total_return'])}` | `{pct(row['max_dd'])}` | `{mult(row['annual_multiple'])}` |"
        )
    report_lines.extend(
        [
            "",
            "## 滚动窗口摘要",
            "",
            "| Rolling slice | Windows | Zero-trade | Positive | Trades median/min/max | Median win | Worst/Best return |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in roll_summary:
        report_lines.append(
            f"| `{row['kind']}` | `{row['windows']}` | `{row['zero_trade_windows']}` | "
            f"`{row['positive_windows']}` | `{row['median_trades']:.1f}/{row['min_trades']}/{row['max_trades']}` | "
            f"`{pct(row['median_win_rate_nonzero'])}` | `{pct(row['worst_total_return'])} / {pct(row['best_total_return'])}` |"
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
            "- V3 是用户指定登记的 diagnostic baseline，不是 live、paper-live、dry-run、candidate 或 handoff。",
            "- Reused holdout 已解锁，本轮消融不能把后段结果重新包装为 untouched OOS。",
            "- 后续若要继续，只能基于冻结后的新增 forward trades、K+2/滑点压力、真实 stop-market 滑点、生产 runner、重启恢复、交易所对账和 kill switch 证据推进。",
            "",
            "## 机器证据",
            "",
            f"- JSON：`artifacts/{SUMMARY_JSON.name}`",
            f"- 行级 CSV：`artifacts/{ROWS_CSV.name}`",
            f"- 字段级 CSV：`artifacts/{FIELDS_CSV.name}`",
            f"- 窗口 CSV：`artifacts/{WINDOWS_CSV.name}`",
            f"- 滚动窗口 CSV：`artifacts/{ROLLING_CSV.name}`",
            "",
            "复现：",
            "",
            "```bash",
            "uv run python research/hype/1h-adaptive-regime/scripts/research_hype_1h_ar_v3_full_ablation.py",
            "```",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(report_lines), encoding="utf-8")
    print(json.dumps(base.json_safe(payload), indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
