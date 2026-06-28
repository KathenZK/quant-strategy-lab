from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SOURCE_PATH = Path(__file__).with_name("research_hype_6h_rs4_parameter_ablation.py")

FAMILY_ROOT = Path("research/hype/6h-rs4-regime-switch")
ARTIFACT_ROOT = FAMILY_ROOT / "artifacts"
DIAG_ROOT = FAMILY_ROOT / "diagnostics"

SUMMARY_JSON = ARTIFACT_ROOT / "hype_6h_rs4_simplified_backtest_summary_2026-06-28.json"
METRICS_CSV = ARTIFACT_ROOT / "hype_6h_rs4_simplified_backtest_metrics_2026-06-28.csv"
SLICE_CSV = ARTIFACT_ROOT / "hype_6h_rs4_simplified_backtest_slices_2026-06-28.csv"
ROLLING_CSV = ARTIFACT_ROOT / "hype_6h_rs4_simplified_backtest_rolling21d_2026-06-28.csv"
REPORT_MD = DIAG_ROOT / "hype-6h-rs4-simplified-backtest-2026-06-28.md"


def load_ablation_module() -> Any:
    spec = importlib.util.spec_from_file_location("hype_6h_rs4_parameter_ablation", SOURCE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {SOURCE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


abl = load_ablation_module()
base = abl.base


def pct(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "n/a"
    return f"{value * 100:.{digits}f}%"


def num(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "n/a"
    return f"{value:.{digits}f}"


def comparison_specs() -> list[Any]:
    baseline = abl.Rs4Spec(name="baseline", group="baseline")
    no_first = replace(
        baseline,
        name="simplified_no_first_flat_exemption",
        group="simplified",
        changed_parameter="remove_first_flat_exemption",
        changed_value="true",
        first_flat_exemption=False,
    )
    simplified = replace(
        no_first,
        name="simplified_final",
        changed_parameter="remove_first_flat_exemption_and_breakeven_guard",
        breakeven_guard=False,
    )
    return [baseline, no_first, simplified]


def metric_row(spec: Any, strategy: Any, slice_name: str, start: pd.Timestamp | None, end: pd.Timestamp | None) -> dict[str, Any]:
    row = base.metrics_for_returns(spec.name, strategy.frame, strategy.returns, strategy.positions, strategy.trades, start=start, end=end)
    row.update(
        {
            "strategy": spec.name,
            "slice": slice_name,
            "first_flat_exemption": spec.first_flat_exemption,
            "breakeven_guard": spec.breakeven_guard,
            "spec": json.dumps(asdict(spec), ensure_ascii=False, sort_keys=True),
        }
    )
    return row


def table_lines(frame: pd.DataFrame, columns: list[str]) -> list[str]:
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for _, row in frame.iterrows():
        rendered: list[str] = []
        for column in columns:
            value = row[column]
            if isinstance(value, float):
                if "return" in column or "drawdown" in column or column in {"delta_return", "delta_max_drawdown"}:
                    rendered.append(pct(value))
                else:
                    rendered.append(num(value))
            else:
                rendered.append(str(value))
        lines.append("| " + " | ".join(rendered) + " |")
    return lines


def with_delta(frame: pd.DataFrame, baseline: pd.Series) -> pd.DataFrame:
    result = frame.copy()
    result["delta_return"] = result["total_return"] - float(baseline["total_return"])
    result["delta_max_drawdown"] = result["max_drawdown"] - float(baseline["max_drawdown"])
    return result


def build_report(metrics: pd.DataFrame, slices: pd.DataFrame, rolling: pd.DataFrame) -> str:
    full = metrics[metrics["slice"] == "full"].copy()
    baseline = full[full["strategy"] == "baseline"].iloc[0]
    full = with_delta(full, baseline)

    fixed_slices = slices[
        (slices["strategy"] == "simplified_final")
        & (~slices["slice"].str.startswith("month_"))
    ].copy()
    baseline_fixed = slices[
        (slices["strategy"] == "baseline")
        & (~slices["slice"].str.startswith("month_"))
    ][["slice", "total_return", "max_drawdown"]].rename(
        columns={"total_return": "baseline_return", "max_drawdown": "baseline_max_drawdown"}
    )
    fixed_slices = fixed_slices.merge(baseline_fixed, on="slice", how="left")
    fixed_slices["delta_return"] = fixed_slices["total_return"] - fixed_slices["baseline_return"]
    fixed_slices["delta_max_drawdown"] = fixed_slices["max_drawdown"] - fixed_slices["baseline_max_drawdown"]

    monthly = slices[
        (slices["strategy"] == "simplified_final")
        & (slices["slice"].str.startswith("month_"))
    ].copy()
    rolling_final = rolling[rolling["strategy"] == "simplified_final"].copy()

    lines = [
        "# HYPE-6H-RS4 简化版回测 2026-06-28",
        "",
        "本报告接受全参数消融后的精简建议：保留 RS4 核心机制，固定 Donchian 与 ATR 参数为机制常量，并从 MFEu 状态机中移除两个近似死参数：`first_flat_exemption` 与 `breakeven_guard`。",
        "",
        "## 简化内容",
        "",
        "- 保留：`range_window=12`、`range_threshold=12%`、`MACD(8,21,5)`、`long_persist=2`、`MFE trigger/giveback=2.0/1.5 ATR`、`ER20>=0.35`、`long-only`、`Donchian 20/10`、`w=1.0`。",
        "- 移除：`first_flat_exemption`，不再对第一次空仓信号做额外豁免。",
        "- 移除：`breakeven_guard`，因为在当前收盘判断/次根开盘成交口径下此前消融完全无影响。",
        "- 固定不调：`donchian_entry`、`donchian_exit`、`atr_window`；它们仍作为机制常量存在，不再作为搜索参数。",
        "",
        "## 全样本对比",
        "",
        *table_lines(
            full,
            ["strategy", "total_return", "delta_return", "max_drawdown", "delta_max_drawdown", "sharpe", "trade_count"],
        ),
        "",
        "## 简化版固定时间片",
        "",
        *table_lines(
            fixed_slices,
            ["slice", "total_return", "delta_return", "max_drawdown", "delta_max_drawdown", "trade_count", "exposure"],
        ),
        "",
        "## 简化版月度与 21 天稳定性",
        "",
        f"- 正月份：`{int((monthly['total_return'] > 0).sum())}/{len(monthly)}`；最差月 `{pct(float(monthly['total_return'].min()))}`；中位月收益 `{pct(float(monthly['total_return'].median()))}`。",
        f"- 正 21 天窗口：`{int((rolling_final['total_return'] > 0).sum())}/{len(rolling_final)}`；最差 21 天 `{pct(float(rolling_final['total_return'].min()))}`；中位 21 天收益 `{pct(float(rolling_final['total_return'].median()))}`。",
        "",
        "## 结论",
        "",
    ]

    final = full[full["strategy"] == "simplified_final"].iloc[0]
    if abs(float(final["delta_return"])) < 0.01 and abs(float(final["delta_max_drawdown"])) < 0.005:
        lines.append("简化版与基线几乎等价，说明删掉的两个 MFEu 参数不是收益承重墙，可以从正式规格中移除。")
    else:
        lines.append("简化版相对基线有可见差异，需要保留本次报告作为规格变更证据，不应只口头删除参数。")
    lines.extend(
        [
            "但这只是参数精简，不改变上一份报告的状态判断：RS4 仍是 `diagnostic only / not promoted`，原因是 Bybit 全史、完整 funding、跨交易所和 live runner 状态机审计仍未完成。",
            "",
            "## 保留证据",
            "",
            f"- summary JSON：`{SUMMARY_JSON}`",
            f"- metrics CSV：`{METRICS_CSV}`",
            f"- slice CSV：`{SLICE_CSV}`",
            f"- rolling 21d CSV：`{ROLLING_CSV}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    DIAG_ROOT.mkdir(parents=True, exist_ok=True)

    frame_5m = base.load_5m_frame()
    funding = base.load_funding_rates()
    quality_5m = base.quality_checks_5m(frame_5m)
    bars_6h, quality_6h = base.resample_to_6h(frame_5m)

    fixed = abl.fixed_slices(bars_6h)
    month_windows = abl.monthly_slices(bars_6h)
    rolling_windows = abl.rolling_slices(bars_6h)

    metric_rows: list[dict[str, Any]] = []
    slice_rows: list[dict[str, Any]] = []
    rolling_rows: list[dict[str, Any]] = []

    for spec in comparison_specs():
        frame = abl.attach_features_for_spec(bars_6h, funding, spec)
        strategy = abl.run_spec(frame, spec)
        metric_rows.append(metric_row(spec, strategy, "full", None, None))
        for slice_name, (start, end) in fixed.items():
            slice_rows.append(metric_row(spec, strategy, slice_name, start, end))
        for slice_name, start, end in month_windows:
            slice_rows.append(metric_row(spec, strategy, slice_name, start, end))
        for slice_name, start, end in rolling_windows:
            rolling_rows.append(metric_row(spec, strategy, slice_name, start, end))

    metrics = pd.DataFrame(metric_rows)
    slices = pd.DataFrame(slice_rows)
    rolling = pd.DataFrame(rolling_rows)

    summary = {
        "strategy_family": "HYPE-6H-RS4-Regime-Switch",
        "status": "diagnostic_only_not_promoted",
        "change": "remove first_flat_exemption and breakeven_guard from MFEu parameter surface",
        "metrics": metrics.to_dict("records"),
        "quality_5m": quality_5m,
        "quality_6h": quality_6h,
        "funding": {
            "rows": int(len(funding)),
            "start_ts": str(funding["ts"].iloc[0]) if len(funding) else None,
            "end_ts": str(funding["ts"].iloc[-1]) if len(funding) else None,
        },
        "artifacts": {
            "summary_json": str(SUMMARY_JSON),
            "metrics_csv": str(METRICS_CSV),
            "slice_csv": str(SLICE_CSV),
            "rolling_csv": str(ROLLING_CSV),
            "report_md": str(REPORT_MD),
        },
    }

    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    metrics.to_csv(METRICS_CSV, index=False)
    slices.to_csv(SLICE_CSV, index=False)
    rolling.to_csv(ROLLING_CSV, index=False)
    REPORT_MD.write_text(build_report(metrics, slices, rolling), encoding="utf-8")
    print(json.dumps({"summary": str(SUMMARY_JSON), "report": str(REPORT_MD)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
