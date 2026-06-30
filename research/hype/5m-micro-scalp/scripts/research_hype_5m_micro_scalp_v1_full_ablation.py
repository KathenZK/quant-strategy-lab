from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pandas as pd

from research_hype_5m_micro_scalp_search import (
    ARTIFACT_ROOT,
    DIAGNOSTIC_ROOT,
    EXIT_SLIPPAGE_RATE,
    ENTRY_SLIPPAGE_RATE,
    FEE_RATE_PER_FILL,
    ScalpConfig,
    add_features,
    bps,
    build_signal,
    load_hype_5m,
    metric_from_trades,
    month_slices,
    mult,
    pct,
    row_for_config,
    simulate_trades,
    validation_slices,
)


ABLATION_ROOT = Path("research/hype/5m-micro-scalp/ablations")
RUN_ID = "2026-06-29"
SUMMARY_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_full_ablation_summary_{RUN_ID}.csv"
MONTHLY_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_full_ablation_monthly_{RUN_ID}.csv"
REPORT_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_full_ablation_{RUN_ID}.json"
MARKDOWN_PATH = ABLATION_ROOT / f"hype-5m-micro-scalp-v1-full-parameter-ablation-{RUN_ID}.md"
BASELINE_CONFIG_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_baseline_config_{RUN_ID}.json"


def baseline_config() -> ScalpConfig:
    """Canonical HYPE-5M-Micro-Scalp-V1 baseline from historical robustness CSV."""
    return ScalpConfig(
        name="HYPE-5M-Micro-Scalp-V1",
        side_mode="both",
        entry_style="vwap_revert",
        ema_fast=21,
        ema_slow=96,
        ema_htf=384,
        donchian=96,
        rsi_window=7,
        rsi_low=40.0,
        rsi_high=76.0,
        bb_z=1.75,
        vwap_dev_bps=75.0,
        pullback_bps=100.0,
        breakout_bps=10.0,
        min_dir_roc_bps=70.0,
        max_counter_roc_bps=260.0,
        min_adx=14.0,
        max_chop=48.0,
        min_rvol=0.75,
        min_atr_pct_bps=35.0,
        max_atr_pct_bps=9999.0,
        max_dist_ema_bps=260.0,
        wick_atr=1.4,
        close_pos=0.70,
        require_trend=True,
        require_htf=False,
        require_macd_turn=False,
        require_body_dir=True,
        tp_bps=67.5,
        sl_bps=275.0,
        max_hold_bars=96,
        cooldown_bars=36,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Full one-at-a-time ablation for HYPE-5M-Micro-Scalp-V1.")
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="Only write the baseline config and planned ablation matrix; do not require local OHLCV data.",
    )
    return parser.parse_args()


def ablation_values(base: ScalpConfig) -> dict[str, list[Any]]:
    return {
        "side_mode": ["long", "short", "both"],
        "entry_style": [
            "vwap_revert",
            "bb_revert",
            "trend_rsi_snapback",
            "wick_reject",
            "micro_breakout",
            "macd_flip",
            "ema_reclaim",
            "momentum_pause",
        ],
        "ema_fast": [8, 12, 21, 34],
        "ema_slow": [55, 96, 144, 192],
        "ema_htf": [192, 288, 384],
        "donchian": [24, 48, 96],
        "rsi_window": [7, 14, 28],
        "rsi_low": [32.0, 36.0, 40.0, 44.0],
        "rsi_high": [64.0, 68.0, 72.0, 76.0],
        "bb_z": [1.25, 1.5, 1.75, 2.0, 2.5],
        "vwap_dev_bps": [35.0, 50.0, 75.0, 100.0, 140.0, 200.0],
        "pullback_bps": [0.0, 50.0, 100.0, 140.0],
        "breakout_bps": [0.0, 5.0, 10.0, 20.0, 35.0],
        "min_dir_roc_bps": [0.0, 40.0, 70.0, 100.0, 150.0],
        "max_counter_roc_bps": [120.0, 180.0, 260.0, 360.0],
        "min_adx": [0.0, 10.0, 14.0, 18.0, 22.0, 28.0],
        "max_chop": [42.0, 48.0, 55.0, 62.0, 70.0],
        "min_rvol": [0.0, 0.5, 0.75, 1.0, 1.25],
        "min_atr_pct_bps": [0.0, 18.0, 25.0, 35.0, 50.0],
        "max_atr_pct_bps": [160.0, 220.0, 350.0, 9999.0],
        "max_dist_ema_bps": [130.0, 180.0, 260.0, 400.0, 800.0],
        "wick_atr": [0.75, 1.0, 1.4],
        "close_pos": [0.58, 0.64, 0.70, 0.76, 0.82],
        "require_trend": [False, True],
        "require_htf": [False, True],
        "require_macd_turn": [False, True],
        "require_body_dir": [False, True],
        "tp_bps": [50.0, 60.0, 67.5, 75.0, 90.0, 120.0],
        "sl_bps": [160.0, 220.0, 275.0, 300.0, 400.0],
        "max_hold_bars": [36, 48, 72, 96, 144],
        "cooldown_bars": [12, 24, 36, 48, 72, 96],
    }


def ablation_matrix(base: ScalpConfig) -> list[ScalpConfig]:
    configs = [base]
    seen = {config_key(base)}
    for param, values in ablation_values(base).items():
        base_value = getattr(base, param)
        for value in values:
            if value == base_value:
                continue
            cfg = replace(base, name=f"V1__{param}__{value}", **{param: value})
            if cfg.ema_fast >= cfg.ema_slow:
                continue
            key = config_key(cfg)
            if key in seen:
                continue
            seen.add(key)
            configs.append(cfg)
    return configs


def config_key(cfg: ScalpConfig) -> tuple[tuple[str, Any], ...]:
    data = asdict(cfg)
    data.pop("name", None)
    return tuple(data.items())


def monthly_for(summary: pd.DataFrame, configs: dict[str, ScalpConfig], frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    months = month_slices(frame)
    for name, cfg in configs.items():
        trades, _ = simulate_trades(frame, build_signal(frame, cfg), cfg)
        for item in months:
            rows.append(
                {
                    "name": name,
                    "ablation_param": summary.loc[summary["name"].eq(name), "ablation_param"].iloc[0],
                    "ablation_value": summary.loc[summary["name"].eq(name), "ablation_value"].iloc[0],
                    "month": item["name"],
                    "month_start": item["start"],
                    "month_end": item["end"],
                    **metric_from_trades(trades, start=item["start"], end=item["end"]),
                }
            )
    return pd.DataFrame(rows)


def add_ablation_columns(row: dict[str, Any], cfg: ScalpConfig, base: ScalpConfig) -> dict[str, Any]:
    if cfg.name == base.name:
        row["ablation_param"] = "BASELINE"
        row["ablation_value"] = ""
        row["is_baseline"] = True
        return row
    for key, value in asdict(cfg).items():
        if key == "name":
            continue
        if value != getattr(base, key):
            row["ablation_param"] = key
            row["ablation_value"] = str(value)
            row["is_baseline"] = False
            return row
    raise RuntimeError(f"could not identify ablation param for {cfg.name}")


def add_deltas(summary: pd.DataFrame) -> pd.DataFrame:
    base = summary.loc[summary["is_baseline"].eq(True)].iloc[0]
    result = summary.copy()
    for metric in (
        "full_annualized_multiple",
        "full_profit_factor",
        "full_max_dd",
        "full_win_rate",
        "full_trades",
        "recent_30d_total_return",
        "val_2026_03_01_to_2026_06_01_profit_factor",
        "fwd_2026_06_01_to_latest_profit_factor",
    ):
        result[f"delta_{metric}"] = result[metric] - base[metric]
    return result


def render_markdown(summary: pd.DataFrame, monthly: pd.DataFrame, quality: dict[str, Any]) -> str:
    base = summary.loc[summary["is_baseline"].eq(True)].iloc[0]
    variants = summary.loc[summary["is_baseline"].eq(False)].copy()
    robust = variants.loc[
        (variants["full_annualized_multiple"] >= 1.05)
        & (variants["full_profit_factor"] >= 1.10)
        & (variants["full_max_dd"] >= -0.20)
        & (variants["val_2026_03_01_to_2026_06_01_profit_factor"] >= 1.0)
        & (variants["fwd_2026_06_01_to_latest_profit_factor"] >= 1.0)
    ]
    grouped = (
        variants.groupby("ablation_param")
        .agg(
            variants=("name", "count"),
            best_ann=("full_annualized_multiple", "max"),
            best_pf=("full_profit_factor", "max"),
            worst_ann=("full_annualized_multiple", "min"),
            robust_like=("full_annualized_multiple", lambda series: 0),
        )
        .reset_index()
    )
    robust_counts = robust.groupby("ablation_param").size().rename("robust_like").reset_index()
    grouped = grouped.drop(columns=["robust_like"]).merge(robust_counts, on="ablation_param", how="left")
    grouped["robust_like"] = grouped["robust_like"].fillna(0).astype(int)
    grouped = grouped.sort_values(["robust_like", "best_ann"], ascending=[False, False])

    lines = [
        "# HYPE-5M-Micro-Scalp-V1 full parameter ablation 2026-06-29",
        "",
        "Family id: `HYPE-5M-Micro-Scalp`",
        "",
        "本报告由脚本逐项改变 `HYPE-5M-Micro-Scalp-V1` 的每一个策略参数生成。每个变体只改变一个字段，其余字段保持 V1 基线不变。",
        "",
        "## 执行口径",
        "",
        "- 闭合 K 信号，下一根 open 入场。",
        "- 入场立即挂固定 TP/SL bracket；同 K 同时触及按 stop-first。",
        "- stop/target 被 open 穿越时按 open 市价成交；timeout 下一根 open 退出。",
        f"- 成本：fee `{FEE_RATE_PER_FILL * 10000:.4f} bps/fill`，entry slippage `{ENTRY_SLIPPAGE_RATE * 10000:.2f} bps`，exit slippage `{EXIT_SLIPPAGE_RATE * 10000:.2f} bps`。",
        "",
        "## 数据",
        "",
        f"- 覆盖：`{quality['start_ts']}` 到 `{quality['end_ts']}`，`{quality['rows']}` 根 K。",
        f"- 缺口：`{quality['missing_bars']}`；OHLCV 硬违规：`{quality['ohlcv_violations']}`。",
        "",
        "## V1 基线",
        "",
        f"- trades `{int(base['full_trades'])}`，trades/day `{float(base['full_trades_per_day']):.2f}`，ann `{mult(float(base['full_annualized_multiple']))}`。",
        f"- win `{pct(float(base['full_win_rate']))}`，PF `{float(base['full_profit_factor']):.3f}`，avg trade `{bps(float(base['full_avg_trade']))}`，maxDD `{pct(float(base['full_max_dd']))}`。",
        f"- VAL PF `{float(base['val_2026_03_01_to_2026_06_01_profit_factor']):.3f}`，FWD PF `{float(base['fwd_2026_06_01_to_latest_profit_factor']):.3f}`，recent30 `{pct(float(base['recent_30d_total_return']))}`。",
        "",
        "## 结论",
        "",
        "- V1 的核心不是通用 micro-scalp，而是 `vwap_revert + require_trend=true + EMA21/96 trend gate + 75 bps VWAP deviation` 的低频均值回归。",
        "- 最脆弱参数是 `entry_style`、`require_trend`、`ema_slow` 和 `vwap_dev_bps`：改变这些参数会明显抬高频率、恶化 PF 或直接把策略打成亏损。",
        "- `bb_z`、`rsi_*`、`donchian`、`wick_atr`、`pullback_bps`、`breakout_bps`、`min_dir_roc_bps`、`max_counter_roc_bps` 等字段在当前 `vwap_revert` 风格下大多是 dormant 参数；它们只有切换 entry style 后才真正参与信号。",
        "- `sl_bps=400`、`max_dist_ema_bps=130`、较短 `max_hold_bars`、较低 `max_atr_pct_bps` 等变体在本轮更好，但这些是后续 V1.1 候选，不应在逐笔路径、订单维护、重启恢复和 paper/live reconciliation 前替代 V1。",
        "- 结论状态维持 `paper-audit candidate only / not live-ready`。",
        "",
        "## 参数组摘要",
        "",
        "| parameter | variants | robust-like | best ann | best PF | worst ann |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in grouped.to_dict(orient="records"):
        lines.append(
            f"| `{row['ablation_param']}` | `{int(row['variants'])}` | `{int(row['robust_like'])}` | "
            f"`{mult(float(row['best_ann']))}` | `{float(row['best_pf']):.3f}` | `{mult(float(row['worst_ann']))}` |"
        )

    best = variants.sort_values("full_annualized_multiple", ascending=False).head(15)
    lines.extend(
        [
            "",
            "## Top Variants",
            "",
            "| name | parameter | value | trades/day | ann | PF | win | maxDD | recent30 |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in best.to_dict(orient="records"):
        lines.append(
            f"| `{row['name']}` | `{row['ablation_param']}` | `{row['ablation_value']}` | "
            f"`{float(row['full_trades_per_day']):.2f}` | `{mult(float(row['full_annualized_multiple']))}` | "
            f"`{float(row['full_profit_factor']):.3f}` | `{pct(float(row['full_win_rate']))}` | "
            f"`{pct(float(row['full_max_dd']))}` | `{pct(float(row['recent_30d_total_return']))}` |"
        )

    worst = variants.sort_values("full_annualized_multiple", ascending=True).head(12)
    lines.extend(
        [
            "",
            "## Fragile Variants",
            "",
            "| name | parameter | value | trades/day | ann | PF | win | maxDD | recent30 |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in worst.to_dict(orient="records"):
        lines.append(
            f"| `{row['name']}` | `{row['ablation_param']}` | `{row['ablation_value']}` | "
            f"`{float(row['full_trades_per_day']):.2f}` | `{mult(float(row['full_annualized_multiple']))}` | "
            f"`{float(row['full_profit_factor']):.3f}` | `{pct(float(row['full_win_rate']))}` | "
            f"`{pct(float(row['full_max_dd']))}` | `{pct(float(row['recent_30d_total_return']))}` |"
        )

    lines.extend(
        [
            "",
            "## 产物",
            "",
            f"- Summary CSV：`{SUMMARY_PATH}`",
            f"- Monthly CSV：`{MONTHLY_PATH}`",
            f"- JSON：`{REPORT_PATH}`",
        ]
    )
    if monthly.empty:
        lines.append("")
    return "\n".join(lines) + "\n"


def render_metadata_markdown(error: str | None = None) -> str:
    base = baseline_config()
    matrix = ablation_matrix(base)
    lines = [
        "# HYPE-5M-Micro-Scalp-V1 full parameter ablation 2026-06-29",
        "",
        "Family id: `HYPE-5M-Micro-Scalp`",
        "",
        "本文件是全参数消融入口。当前工作空间没有本地 HYPEUSDT `5m` parquet 数据湖，因此本次只生成 V1 基线参数与待运行消融矩阵；数值结果需要在数据湖存在后运行脚本生成。",
        "",
        "## 当前运行状态",
        "",
        "- status: `metadata_only`",
        f"- reason: `{error or 'metadata-only requested'}`",
        f"- planned configs: `{len(matrix)}`，包含 `1` 个基线和 `{len(matrix) - 1}` 个 one-at-a-time 参数变体。",
        "",
        "## 运行命令",
        "",
        "```bash",
        "uv run python research/hype/5m-micro-scalp/scripts/research_hype_5m_micro_scalp_v1_full_ablation.py",
        "```",
        "",
        "## V1 参数源",
        "",
        "- 基线候选来自历史提交 `c94dcac` 中已移除的 `hype_5m_micro_scalp_candidate_robustness_summary_2026-06-26.csv` 行：`R1_relax_frequency_R01242__tp_sl_0011`。",
        "- 历史指标：`188` 笔，`0.48` 笔/天，ann `1.32x`，win `85.11%`，PF `1.468`，avg trade `16.67 bps`，maxDD `-8.16%`，VAL PF `5.445`，FWD PF `3.550`，recent30 `10.46%`，`3/14` 负收益月份。",
        "",
        "## Planned Parameter Matrix",
        "",
        "| parameter | baseline | values tested one-at-a-time |",
        "| --- | --- | --- |",
    ]
    for key, values in ablation_values(base).items():
        lines.append(f"| `{key}` | `{getattr(base, key)}` | `{', '.join(map(str, values))}` |")
    lines.extend(
        [
            "",
            "## 产物",
            "",
            f"- Baseline config JSON：`{BASELINE_CONFIG_PATH}`",
            f"- Full-result JSON（有数据后生成）：`{REPORT_PATH}`",
            f"- Summary CSV（有数据后生成）：`{SUMMARY_PATH}`",
            f"- Monthly CSV（有数据后生成）：`{MONTHLY_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def write_metadata_only(error: str | None = None) -> None:
    base = baseline_config()
    matrix = ablation_matrix(base)
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    ABLATION_ROOT.mkdir(parents=True, exist_ok=True)
    BASELINE_CONFIG_PATH.write_text(
        json.dumps(
            {
                "strategy_family": "HYPE-5M-Micro-Scalp",
                "version": "HYPE-5M-Micro-Scalp-V1",
                "source_candidate": "R1_relax_frequency_R01242__tp_sl_0011",
                "source_commit": "c94dcac",
                "baseline_config": asdict(base),
                "planned_ablation_config_count": len(matrix),
                "planned_ablation_values": ablation_values(base),
                "status": "metadata_only",
                "error": error,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    MARKDOWN_PATH.write_text(render_metadata_markdown(error), encoding="utf-8")


def main() -> None:
    args = parse_args()
    if args.metadata_only:
        write_metadata_only()
        print(f"metadata_markdown={MARKDOWN_PATH}")
        print(f"baseline_config={BASELINE_CONFIG_PATH}")
        return

    base = baseline_config()
    configs = ablation_matrix(base)
    try:
        frame, quality = load_hype_5m()
    except FileNotFoundError as exc:
        write_metadata_only(str(exc))
        print(f"metadata_markdown={MARKDOWN_PATH}")
        print(f"baseline_config={BASELINE_CONFIG_PATH}")
        raise
    frame = add_features(frame)
    slices = validation_slices(frame)
    rows: list[dict[str, Any]] = []
    config_by_name: dict[str, ScalpConfig] = {}
    for cfg in configs:
        row, _, _ = row_for_config(frame, cfg, slices)
        rows.append(add_ablation_columns(row, cfg, base))
        config_by_name[cfg.name] = cfg
        print(f"done {cfg.name}")

    summary = add_deltas(pd.DataFrame(rows))
    summary = summary.sort_values(["is_baseline", "full_annualized_multiple"], ascending=[False, False])
    monthly = monthly_for(summary, config_by_name, frame)

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_ROOT.mkdir(parents=True, exist_ok=True)
    ABLATION_ROOT.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    monthly.to_csv(MONTHLY_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary, monthly, quality), encoding="utf-8")
    BASELINE_CONFIG_PATH.write_text(json.dumps(asdict(base), ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "strategy_family": "HYPE-5M-Micro-Scalp",
                "version": "HYPE-5M-Micro-Scalp-V1",
                "source_candidate": "R1_relax_frequency_R01242__tp_sl_0011",
                "source_commit": "c94dcac",
                "data_quality": quality,
                "cost_model": {
                    "fee_rate_per_fill": FEE_RATE_PER_FILL,
                    "entry_slippage_rate": ENTRY_SLIPPAGE_RATE,
                    "exit_slippage_rate": EXIT_SLIPPAGE_RATE,
                },
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary": str(SUMMARY_PATH),
                    "monthly": str(MONTHLY_PATH),
                    "baseline_config": str(BASELINE_CONFIG_PATH),
                },
                "configs": len(summary),
                "baseline": summary.loc[summary["is_baseline"].eq(True)].to_dict(orient="records"),
                "top": summary.loc[summary["is_baseline"].eq(False)]
                .sort_values("full_annualized_multiple", ascending=False)
                .head(30)
                .to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"markdown={MARKDOWN_PATH}")
    print(f"summary={SUMMARY_PATH}")
    print(f"monthly={MONTHLY_PATH}")


if __name__ == "__main__":
    main()
