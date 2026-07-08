from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research_hype_5m_micro_scalp_search import (
    ARTIFACT_ROOT,
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
from research_hype_5m_micro_scalp_v1_2_registration_and_leverage_retest import v1_2_config
from research_hype_5m_micro_scalp_v1_simplified_combo_search import verify_raw_normalized_parity


RUN_ID = "2026-07-01"
FAMILY_ROOT = Path("research/hype/5m-micro-scalp")
ABLATION_ROOT = FAMILY_ROOT / "ablations"
CANONICAL_ROOT = FAMILY_ROOT / "specs"
RESEARCH_NOTE_ROOT = FAMILY_ROOT / "research-notes"

CONFIG_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_3_baseline_config_{RUN_ID}.json"
BASELINE_JSON_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_3_baseline_backtest_{RUN_ID}.json"
BASELINE_SUMMARY_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_3_baseline_backtest_summary_{RUN_ID}.csv"
BASELINE_SLICES_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_3_baseline_backtest_slices_{RUN_ID}.csv"
BASELINE_MONTHLY_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_3_baseline_backtest_monthly_{RUN_ID}.csv"
BASELINE_TRADES_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_3_baseline_backtest_trades_{RUN_ID}.csv"
BASELINE_NOTE_PATH = RESEARCH_NOTE_ROOT / f"hype-5m-micro-scalp-v1-3-baseline-backtest-{RUN_ID}.md"

ABLATION_SUMMARY_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_3_full_ablation_summary_{RUN_ID}.csv"
ABLATION_MONTHLY_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_3_full_ablation_monthly_{RUN_ID}.csv"
ABLATION_JSON_PATH = ARTIFACT_ROOT / f"hype_5m_micro_scalp_v1_3_full_ablation_{RUN_ID}.json"
ABLATION_MARKDOWN_PATH = ABLATION_ROOT / f"hype-5m-micro-scalp-v1-3-full-parameter-ablation-{RUN_ID}.md"
SPEC_MARKDOWN_PATH = CANONICAL_ROOT / "hype-5m-micro-scalp-v1-3-baseline-spec.md"

FEE_RATE_PER_FILL = 0.001
SLIPPAGE_RATE_PER_FILL = 4.0 / 10000.0

# V1.3 固定内核：entry_style 与 dormant 字段不再暴露在版本配置里。
ENGINE_INTERNAL_FIXED: dict[str, Any] = {
    "entry_style": "vwap_revert",
    "donchian": 96,
    "rsi_window": 7,
    "rsi_low": 40.0,
    "rsi_high": 76.0,
    "bb_z": 1.75,
    "pullback_bps": 100.0,
    "breakout_bps": 10.0,
    "min_dir_roc_bps": 70.0,
    "max_counter_roc_bps": 260.0,
    "wick_atr": 1.4,
    # V1.2 中已等效关闭的过滤，V1.3 从 schema 剔除并在此硬编码。
    "min_adx": 0.0,
    "max_atr_pct_bps": 9999.0,
}

V13_ACTIVE_FIELDS = [
    "side_mode",
    "ema_fast",
    "ema_slow",
    "ema_htf",
    "vwap_dev_bps",
    "max_chop",
    "min_rvol",
    "min_atr_pct_bps",
    "max_dist_ema_bps",
    "close_pos",
    "require_trend",
    "require_htf",
    "require_macd_turn",
    "require_body_dir",
    "tp_bps",
    "sl_bps",
    "max_hold_bars",
    "cooldown_bars",
]

REMOVED_FROM_V1_2 = [
    "donchian",
    "rsi_window",
    "rsi_low",
    "rsi_high",
    "bb_z",
    "pullback_bps",
    "breakout_bps",
    "min_dir_roc_bps",
    "max_counter_roc_bps",
    "wick_atr",
    "min_adx",
    "max_atr_pct_bps",
]


@dataclass(frozen=True, slots=True)
class V13ScalpConfig:
    name: str
    side_mode: str
    ema_fast: int
    ema_slow: int
    ema_htf: int
    vwap_dev_bps: float
    max_chop: float
    min_rvol: float
    min_atr_pct_bps: float
    max_dist_ema_bps: float
    close_pos: float
    require_trend: bool
    require_htf: bool
    require_macd_turn: bool
    require_body_dir: bool
    tp_bps: float
    sl_bps: float
    max_hold_bars: int
    cooldown_bars: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="HYPE-5M-Micro-Scalp-V1.3 simplified baseline backtest and full ablation."
    )
    parser.add_argument("--skip-ablation", action="store_true")
    parser.add_argument("--skip-raw-parity", action="store_true")
    return parser.parse_args()


def num(value: float, digits: int = 3) -> str:
    if not np.isfinite(value):
        return "inf"
    return f"{value:.{digits}f}"


def v1_3_config(name: str = "HYPE-5M-Micro-Scalp-V1.3") -> V13ScalpConfig:
    """V1.3 = V1.2 有效参数，剔除 dormant 与等效关闭字段。"""
    return V13ScalpConfig(
        name=name,
        side_mode="both",
        ema_fast=21,
        ema_slow=192,
        ema_htf=192,
        vwap_dev_bps=65.0,
        max_chop=70.0,
        min_rvol=0.75,
        min_atr_pct_bps=35.0,
        max_dist_ema_bps=130.0,
        close_pos=0.76,
        require_trend=True,
        require_htf=True,
        require_macd_turn=True,
        require_body_dir=True,
        tp_bps=110.0,
        sl_bps=400.0,
        max_hold_bars=96,
        cooldown_bars=48,
    )


def to_engine_config(cfg: V13ScalpConfig) -> ScalpConfig:
    return ScalpConfig(
        name=cfg.name,
        side_mode=cfg.side_mode,
        ema_fast=cfg.ema_fast,
        ema_slow=cfg.ema_slow,
        ema_htf=cfg.ema_htf,
        vwap_dev_bps=cfg.vwap_dev_bps,
        max_chop=cfg.max_chop,
        min_rvol=cfg.min_rvol,
        min_atr_pct_bps=cfg.min_atr_pct_bps,
        max_dist_ema_bps=cfg.max_dist_ema_bps,
        close_pos=cfg.close_pos,
        require_trend=cfg.require_trend,
        require_htf=cfg.require_htf,
        require_macd_turn=cfg.require_macd_turn,
        require_body_dir=cfg.require_body_dir,
        tp_bps=cfg.tp_bps,
        sl_bps=cfg.sl_bps,
        max_hold_bars=cfg.max_hold_bars,
        cooldown_bars=cfg.cooldown_bars,
        **ENGINE_INTERNAL_FIXED,
    )


def config_key(cfg: V13ScalpConfig) -> tuple[tuple[str, Any], ...]:
    data = asdict(cfg)
    data.pop("name", None)
    return tuple(data.items())


def ablation_values(base: V13ScalpConfig) -> dict[str, list[Any]]:
    return {
        "side_mode": ["both", "long", "short"],
        "ema_fast": [8, 12, 21, 34],
        "ema_slow": [96, 144, 192, 288],
        "ema_htf": [96, 144, 192, 288],
        "vwap_dev_bps": [50.0, 60.0, 65.0, 75.0, 90.0, 120.0, 140.0],
        "max_chop": [42.0, 48.0, 55.0, 62.0, 70.0, 100.0],
        "min_rvol": [0.5, 0.75, 1.0, 1.25, 1.5],
        "min_atr_pct_bps": [0.0, 18.0, 25.0, 35.0, 50.0],
        "max_dist_ema_bps": [90.0, 130.0, 180.0, 260.0, 400.0, 9999.0],
        "close_pos": [0.58, 0.64, 0.70, 0.76, 0.82],
        "require_trend": [False, True],
        "require_htf": [False, True],
        "require_macd_turn": [False, True],
        "require_body_dir": [False, True],
        "tp_bps": [67.5, 75.0, 90.0, 110.0, 130.0],
        "sl_bps": [300.0, 400.0, 500.0, 650.0],
        "max_hold_bars": [48, 72, 96, 144, 192],
        "cooldown_bars": [0, 24, 36, 48, 72, 96],
    }


def ablation_matrix(base: V13ScalpConfig) -> list[V13ScalpConfig]:
    configs = [base]
    seen = {config_key(base)}
    for param, values in ablation_values(base).items():
        base_value = getattr(base, param)
        for value in values:
            if value == base_value:
                continue
            cfg = replace(base, name=f"V1.3__{param}__{value}", **{param: value})
            if cfg.ema_fast >= cfg.ema_slow:
                continue
            key = config_key(cfg)
            if key in seen:
                continue
            seen.add(key)
            configs.append(cfg)
    return configs


def add_changed_columns(row: dict[str, Any], cfg: V13ScalpConfig, base: V13ScalpConfig) -> dict[str, Any]:
    for field in V13_ACTIVE_FIELDS:
        row[f"cfg_{field}"] = getattr(cfg, field)
    if cfg.name == base.name:
        row["changed_param"] = "BASELINE"
        row["changed_value"] = ""
        row["is_baseline"] = True
        return row
    for key, value in asdict(cfg).items():
        if key == "name":
            continue
        if value != getattr(base, key):
            row["changed_param"] = key
            row["changed_value"] = str(value)
            row["is_baseline"] = False
            return row
    raise RuntimeError(f"could not identify changed param for {cfg.name}")


def add_metric_deltas(summary: pd.DataFrame) -> pd.DataFrame:
    base = summary.loc[summary["is_baseline"].eq(True)].iloc[0]
    result = summary.copy()
    for metric in (
        "signals",
        "full_trades",
        "full_trades_per_day",
        "full_annualized_multiple",
        "full_profit_factor",
        "full_win_rate",
        "full_avg_trade",
        "full_max_dd",
        "recent_30d_total_return",
        "val_2026_03_01_to_2026_06_01_profit_factor",
        "fwd_2026_06_01_to_latest_profit_factor",
    ):
        result[f"delta_{metric}"] = result[metric] - base[metric]
    numeric_checks = [
        "signals",
        "full_trades",
        "full_annualized_multiple",
        "full_profit_factor",
        "full_win_rate",
        "full_avg_trade",
        "full_max_dd",
        "recent_30d_total_return",
    ]
    delta_frame = result[[f"delta_{metric}" for metric in numeric_checks]].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    result["identical_to_baseline"] = delta_frame.abs().max(axis=1) <= 1e-12
    return result


def monthly_for_configs(frame: pd.DataFrame, cfg_by_name: dict[str, V13ScalpConfig], names: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    months = month_slices(frame)
    for name in names:
        engine_cfg = to_engine_config(cfg_by_name[name])
        trades, _ = simulate_trades(frame, build_signal(frame, engine_cfg), engine_cfg)
        for item in months:
            rows.append(
                {
                    "name": name,
                    "month": item["name"],
                    "month_start": item["start"],
                    "month_end": item["end"],
                    **metric_from_trades(trades, start=item["start"], end=item["end"]),
                }
            )
    return pd.DataFrame(rows)


def variant_table(rows: pd.DataFrame, base: pd.Series, limit: int = 15) -> list[str]:
    output = [
        "| name | changed | trades/day | trades | ann | PF | win | avg | maxDD | VAL PF | FWD PF | recent30 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in rows.head(limit).to_dict(orient="records"):
        changed = f"{item.get('changed_param')}={item.get('changed_value')}" if item.get("changed_param") != "BASELINE" else "BASELINE"
        output.append(
            f"| `{item['name']}` | `{changed}` | `{float(item['full_trades_per_day']):.2f}` | `{int(item['full_trades'])}` | "
            f"`{mult(float(item['full_annualized_multiple']))}` | `{num(float(item['full_profit_factor']))}` | "
            f"`{pct(float(item['full_win_rate']))}` | `{bps(float(item['full_avg_trade']))}` | "
            f"`{pct(float(item['full_max_dd']))}` | `{num(float(item['val_2026_03_01_to_2026_06_01_profit_factor']))}` | "
            f"`{num(float(item['fwd_2026_06_01_to_latest_profit_factor']))}` | `{pct(float(item['recent_30d_total_return']))}` |"
        )
    return output


def render_spec_markdown(base_row: pd.Series, quality: dict[str, Any], parity: dict[str, Any] | None) -> str:
    cfg = v1_3_config()
    lines = [
        "# HYPE-5M-Micro-Scalp-V1.3 基线规格",
        "",
        "Family id：`HYPE-5M-Micro-Scalp`",
        "",
        "版本：`HYPE-5M-Micro-Scalp-V1.3`",
        "",
        "父版本：`HYPE-5M-Micro-Scalp-V1.2`",
        "",
        "状态：`paper-audit observation / not live-ready`",
        "",
        "## 一句话定义",
        "",
        "V1.3 是 V1.2 的精简登记版：保留 `vwap_revert` 下全部有效参数，剔除 V1.2 中 dormant 字段与等效关闭的 `min_adx` / `max_atr_pct_bps`。交易逻辑与 V1.2 一致，仅配置 schema 更干净。",
        "",
        "## 相对 V1.2 剔除的字段",
        "",
        f"- dormant（`vwap_revert` 不使用）：`{', '.join(REMOVED_FROM_V1_2[:-2])}`。",
        f"- 等效关闭：`min_adx`、`max_atr_pct_bps`（引擎内部固定为不过滤）。",
        "",
        "## 数据、执行与成本口径",
        "",
        f"- 市场：Binance HYPEUSDT perpetual `5m`。",
        f"- 数据范围：UTC `{quality['start_ts']}` 至 `{quality['end_ts']}`，共 `{quality['rows']}` 根 K。",
        f"- raw/normalized 对齐：`{parity if parity is not None else 'skipped'}`。",
        "- 信号：只使用已经收盘的 K 线。",
        "- 入场：信号 K 后下一根 open，按方向加入 `4 bps` 不利滑点。",
        "- 退出：入场后立即设置固定 TP/SL bracket；退出成交加入 `4 bps` 不利滑点。",
        "- 同 K 同时触及 TP/SL：保守按 stop-first。",
        "- gap 穿越 stop/target：按该 K open 市价成交。",
        "- timeout：最长持仓结束后按下一根 open 退出。",
        f"- 手续费：`{FEE_RATE_PER_FILL}` / fill；默认仓位 `1x`。",
        "",
        "## V1.3 默认 1x 回测摘要",
        "",
        f"- trades：`{int(base_row['full_trades'])}`；trades/day：`{float(base_row['full_trades_per_day']):.2f}`。",
        f"- annualized equity multiple：`{mult(float(base_row['full_annualized_multiple']))}`；全区间收益：`{pct(float(base_row['full_total_return']))}`。",
        f"- win：`{pct(float(base_row['full_win_rate']))}`；PF：`{num(float(base_row['full_profit_factor']))}`；平均单笔：`{bps(float(base_row['full_avg_trade']))}`。",
        f"- maxDD：`{pct(float(base_row['full_max_dd']))}`；最差单笔：`{pct(float(base_row['full_worst_trade']))}`。",
        f"- VAL PF：`{num(float(base_row['val_2026_03_01_to_2026_06_01_profit_factor']))}`；FWD PF：`{num(float(base_row['fwd_2026_06_01_to_latest_profit_factor']))}`。",
        "",
        "## V1.3 参数总表（仅有效字段）",
        "",
        "| 参数 | V1.3 值 | 说明 |",
        "| --- | ---: | --- |",
    ]
    descriptions = {
        "side_mode": "多空双向。",
        "ema_fast": "快 EMA；趋势方向与距 EMA 过滤。",
        "ema_slow": "慢 EMA；`require_trend=true` 时决定多空允许方向。",
        "ema_htf": "高阶 EMA；`require_htf=true` 时要求价格同侧。",
        "vwap_dev_bps": "相对 vwap96 或 day_vwap 的偏离触发阈值（bps）。",
        "max_chop": "Chop14 上限。",
        "min_rvol": "RVOL96 下限。",
        "min_atr_pct_bps": "ATR14 百分比下限。",
        "max_dist_ema_bps": "收盘价距 EMA21 最大偏离（bps）。",
        "close_pos": "K 线收盘位置过滤；多头要求靠近上部，空头靠近下部。",
        "require_trend": "必须顺 EMA fast/slow 趋势。",
        "require_htf": "价格须在 HTF EMA 同方向一侧。",
        "require_macd_turn": "MACD histogram 同向或转向。",
        "require_body_dir": "多头阳线、空头阴线。",
        "tp_bps": "固定止盈距离。",
        "sl_bps": "固定止损距离。",
        "max_hold_bars": "最长持仓 K 数。",
        "cooldown_bars": "平仓后冷却 K 数。",
    }
    for field in V13_ACTIVE_FIELDS:
        lines.append(f"| `{field}` | `{getattr(cfg, field)}` | {descriptions[field]} |")
    lines.extend(
        [
            "",
            "## 固定内核（不在 V1.3 配置表暴露）",
            "",
            f"- `entry_style=vwap_revert`",
            f"- `min_adx=0`、`max_atr_pct_bps=9999`（不过滤）",
            f"- dormant 引擎占位：`donchian/rsi/bb/pullback/breakout/roc/wick` 固定常量，不参与信号。",
            "",
            "## 推进边界",
            "",
            "V1.3 不改变 V1.2 的 live-executable 审计缺口；版本精简不等于 promotion。",
            "",
            "## 关联产物",
            "",
            f"- 脚本：`research/hype/5m-micro-scalp/scripts/research_hype_5m_micro_scalp_v1_3_simplified_ablation.py`",
            f"- Config JSON：`{CONFIG_PATH}`",
            f"- 消融：`{ABLATION_MARKDOWN_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def render_ablation_markdown(summary: pd.DataFrame, quality: dict[str, Any], parity: dict[str, Any] | None) -> str:
    base = summary.loc[summary["is_baseline"].eq(True)].iloc[0]
    variants = summary.loc[summary["is_baseline"].eq(False)].copy()
    grouped = (
        variants.groupby("changed_param")
        .agg(
            variants=("name", "count"),
            identical=("identical_to_baseline", "sum"),
            best_ann=("full_annualized_multiple", "max"),
            best_pf=("full_profit_factor", "max"),
            best_dd=("full_max_dd", "max"),
            worst_ann=("full_annualized_multiple", "min"),
        )
        .reset_index()
        .sort_values(["identical", "best_ann"], ascending=[False, False])
    )
    active_top = variants.loc[~variants["identical_to_baseline"].eq(True)].sort_values("full_annualized_multiple", ascending=False).head(15)
    fragile = variants.loc[~variants["identical_to_baseline"].eq(True)].sort_values("full_annualized_multiple", ascending=True).head(12)
    lines = [
        "# HYPE-5M-Micro-Scalp-V1.3 全参数消融 2026-07-01",
        "",
        "Family id：`HYPE-5M-Micro-Scalp`",
        "",
        "本报告对 V1.3 精简 schema 的 `18` 个有效字段做 one-at-a-time 消融。`entry_style` 固定为 `vwap_revert`，不再测试 dormant 字段。",
        "",
        "## 数据与执行",
        "",
        f"- 数据：Binance HYPEUSDT perpetual `5m`，`{quality['start_ts']}` 到 `{quality['end_ts']}`，`{quality['rows']}` 根 K。",
        f"- raw/normalized 对齐：`{parity if parity is not None else 'skipped'}`。",
        f"- 成本：fee `{FEE_RATE_PER_FILL * 10000:.1f} bps`/fill，slippage `{SLIPPAGE_RATE_PER_FILL * 10000:.1f} bps`/fill（双边不利）。",
        "",
        "## V1.3 基线",
        "",
        f"- configs evaluated：`{len(summary)}`（`1` baseline + `{len(summary) - 1}` variants）。",
        f"- trades `{int(base['full_trades'])}`，trades/day `{float(base['full_trades_per_day']):.2f}`，ann `{mult(float(base['full_annualized_multiple']))}`。",
        f"- win `{pct(float(base['full_win_rate']))}`，PF `{num(float(base['full_profit_factor']))}`，avg `{bps(float(base['full_avg_trade']))}`，maxDD `{pct(float(base['full_max_dd']))}`。",
        "",
        "## 参数组摘要",
        "",
        "| parameter | variants | identical | best ann | best PF | best DD | worst ann |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in grouped.to_dict(orient="records"):
        lines.append(
            f"| `{row['changed_param']}` | `{int(row['variants'])}` | `{int(row['identical'])}` | "
            f"`{mult(float(row['best_ann']))}` | `{num(float(row['best_pf']))}` | `{pct(float(row['best_dd']))}` | `{mult(float(row['worst_ann']))}` |"
        )
    lines.extend(["", "## Top Variants", "", *variant_table(active_top, base, 15)])
    lines.extend(["", "## Fragile Variants", "", *variant_table(fragile, base, 12)])
    lines.extend(
        [
            "",
            "## 结论",
            "",
            "- V1.3 schema 已剔除 V1.2 dormant 与等效关闭字段；消融只覆盖真实可调参数。",
            "- 本报告只说明参数敏感性，不构成 live-ready 证明。",
            "",
            "## 产物",
            "",
            f"- 脚本：`research/hype/5m-micro-scalp/scripts/research_hype_5m_micro_scalp_v1_3_simplified_ablation.py`",
            f"- Summary CSV：`{ABLATION_SUMMARY_PATH}`",
            f"- Monthly CSV：`{ABLATION_MONTHLY_PATH}`",
            f"- JSON：`{ABLATION_JSON_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def render_baseline_note(
    v13_row: pd.Series,
    v12_row: pd.Series,
    quality: dict[str, Any],
    parity: dict[str, Any] | None,
    parity_ok: bool,
) -> str:
    lines = [
        "# HYPE-5M-Micro-Scalp-V1.3 基线回测 2026-07-01",
        "",
        "Family id：`HYPE-5M-Micro-Scalp`",
        "",
        "V1.3 自 V1.2 剔除 dormant 与等效关闭参数，仅保留 `18` 个有效字段；本报告验证两者在相同成本下是否逐笔一致。",
        "",
        "## 数据与成本",
        "",
        f"- 数据：`{quality['start_ts']}` 到 `{quality['end_ts']}`，`{quality['rows']}` 根 K。",
        f"- raw/normalized：`{parity if parity is not None else 'skipped'}`。",
        f"- fee `{FEE_RATE_PER_FILL}`/fill，slippage `{SLIPPAGE_RATE_PER_FILL * 10000:.1f} bps`/fill。",
        "",
        "## V1.3 基线",
        "",
        f"- trades `{int(v13_row['full_trades'])}`，trades/day `{float(v13_row['full_trades_per_day']):.2f}`。",
        f"- ann `{mult(float(v13_row['full_annualized_multiple']))}`，PF `{num(float(v13_row['full_profit_factor']))}`，win `{pct(float(v13_row['full_win_rate']))}`。",
        f"- avg `{bps(float(v13_row['full_avg_trade']))}`，maxDD `{pct(float(v13_row['full_max_dd']))}`。",
        "",
        "## 与 V1.2 一致性",
        "",
        f"- V1.2 ann `{mult(float(v12_row['full_annualized_multiple']))}`，PF `{num(float(v12_row['full_profit_factor']))}`，trades `{int(v12_row['full_trades'])}`。",
        f"- 指标逐笔等价：`{'是' if parity_ok else '否'}`。",
        "",
        "## 产物",
        "",
        f"- JSON：`{BASELINE_JSON_PATH}`",
        f"- Trades CSV：`{BASELINE_TRADES_PATH}`",
        f"- Spec：`{SPEC_MARKDOWN_PATH}`",
    ]
    return "\n".join(lines) + "\n"


def assert_data_quality(quality: dict[str, Any], parity: dict[str, Any]) -> None:
    blockers: list[str] = []
    if int(quality["missing_bars"]) != 0:
        blockers.append(f"missing_bars={quality['missing_bars']}")
    if int(quality["duplicate_ts"]) != 0:
        blockers.append(f"duplicate_ts={quality['duplicate_ts']}")
    if any(int(value) != 0 for value in quality["nulls"].values()):
        blockers.append(f"nulls={quality['nulls']}")
    if any(int(value) != 0 for value in quality["ohlcv_violations"].values()):
        blockers.append(f"ohlcv_violations={quality['ohlcv_violations']}")
    if int(parity["timestamp_mismatch"]) != 0 or any(int(value) != 0 for value in parity["field_mismatches"].values()):
        blockers.append(f"raw_normalized_parity={parity}")
    if blockers:
        raise RuntimeError("data quality blockers: " + "; ".join(blockers))


def apply_cost_model() -> None:
    import research_hype_5m_micro_scalp_search as engine

    engine.FEE_RATE_PER_FILL = FEE_RATE_PER_FILL
    engine.ENTRY_SLIPPAGE_RATE = SLIPPAGE_RATE_PER_FILL
    engine.EXIT_SLIPPAGE_RATE = SLIPPAGE_RATE_PER_FILL


def run_baseline(frame: pd.DataFrame, quality: dict[str, Any], parity: dict[str, Any] | None) -> tuple[pd.Series, pd.Series, bool]:
    slices = validation_slices(frame)
    v13 = v1_3_config()
    v12 = v1_2_config()
    v13_engine = to_engine_config(v13)
    v13_row, slice_rows, trades = row_for_config(frame, v13_engine, slices)
    v12_row, _, v12_trades = row_for_config(frame, v12, slices)

    parity_ok = len(trades) == len(v12_trades)
    if parity_ok:
        for left, right in zip(trades, v12_trades, strict=True):
            if (
                left.entry_ts != right.entry_ts
                or left.exit_ts != right.exit_ts
                or left.side != right.side
                or abs(left.net_ret_1x - right.net_ret_1x) > 1e-12
            ):
                parity_ok = False
                break

    trade_frame = pd.DataFrame([asdict(trade) for trade in trades])
    summary = pd.DataFrame([v13_row])
    slices_frame = pd.DataFrame(slice_rows)
    monthly = monthly_for_configs(frame, {v13.name: v13}, [v13.name])

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    RESEARCH_NOTE_ROOT.mkdir(parents=True, exist_ok=True)
    CANONICAL_ROOT.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(asdict(v13), indent=2) + "\n", encoding="utf-8")
    summary.to_csv(BASELINE_SUMMARY_PATH, index=False)
    slices_frame.to_csv(BASELINE_SLICES_PATH, index=False)
    monthly.to_csv(BASELINE_MONTHLY_PATH, index=False)
    trade_frame.to_csv(BASELINE_TRADES_PATH, index=False)
    SPEC_MARKDOWN_PATH.write_text(render_spec_markdown(v13_row, quality, parity), encoding="utf-8")
    BASELINE_NOTE_PATH.write_text(render_baseline_note(v13_row, v12_row, quality, parity, parity_ok), encoding="utf-8")
    BASELINE_JSON_PATH.write_text(
        json.dumps(
            {
                "strategy_family": "HYPE-5M-Micro-Scalp",
                "version": "HYPE-5M-Micro-Scalp-V1.3",
                "parent_version": "HYPE-5M-Micro-Scalp-V1.2",
                "status": "paper-audit observation / not live-ready",
                "removed_fields": REMOVED_FROM_V1_2,
                "active_fields": V13_ACTIVE_FIELDS,
                "engine_internal_fixed": ENGINE_INTERNAL_FIXED,
                "v1_2_trade_path_parity": parity_ok,
                "data_quality": quality,
                "raw_normalized_parity": parity,
                "cost_model": {
                    "fee_rate_per_fill": FEE_RATE_PER_FILL,
                    "slippage_rate_per_fill": SLIPPAGE_RATE_PER_FILL,
                },
                "config": asdict(v13),
                "baseline_metrics": v13_row,
                "v1_2_metrics": v12_row,
            },
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        "V1.3 baseline:",
        f"trades={int(v13_row['full_trades'])}",
        f"ann={float(v13_row['full_annualized_multiple']):.3f}",
        f"pf={float(v13_row['full_profit_factor']):.3f}",
        f"maxDD={float(v13_row['full_max_dd']):.3f}",
    )
    print(f"V1.2 parity: {parity_ok}")
    return pd.Series(v13_row), pd.Series(v12_row), parity_ok


def run_ablation(frame: pd.DataFrame, quality: dict[str, Any], parity: dict[str, Any] | None) -> pd.DataFrame:
    base = v1_3_config()
    configs = ablation_matrix(base)
    slices = validation_slices(frame)
    rows: list[dict[str, Any]] = []
    cfg_by_name: dict[str, V13ScalpConfig] = {}
    for idx, cfg in enumerate(configs, start=1):
        engine_cfg = to_engine_config(cfg)
        row, _, _ = row_for_config(frame, engine_cfg, slices)
        rows.append(add_changed_columns(row, cfg, base))
        cfg_by_name[cfg.name] = cfg
        if idx % 20 == 0 or idx == len(configs):
            print(f"ablation {idx}/{len(configs)} {cfg.name}", flush=True)
    summary = add_metric_deltas(pd.DataFrame(rows)).sort_values(["is_baseline", "full_annualized_multiple"], ascending=[False, False])
    monthly = monthly_for_configs(frame, cfg_by_name, list(cfg_by_name))
    ABLATION_ROOT.mkdir(parents=True, exist_ok=True)
    summary.to_csv(ABLATION_SUMMARY_PATH, index=False)
    monthly.to_csv(ABLATION_MONTHLY_PATH, index=False)
    ABLATION_MARKDOWN_PATH.write_text(render_ablation_markdown(summary, quality, parity), encoding="utf-8")
    ABLATION_JSON_PATH.write_text(
        json.dumps(
            {
                "strategy_family": "HYPE-5M-Micro-Scalp",
                "version": "HYPE-5M-Micro-Scalp-V1.3",
                "configs": int(len(summary)),
                "active_fields": V13_ACTIVE_FIELDS,
                "removed_fields": REMOVED_FROM_V1_2,
                "data_quality": quality,
                "raw_normalized_parity": parity,
                "baseline": summary.loc[summary["is_baseline"].eq(True)].to_dict(orient="records"),
                "top": summary.loc[~summary["is_baseline"].eq(True)]
                .sort_values("full_annualized_multiple", ascending=False)
                .head(30)
                .to_dict(orient="records"),
                "fragile": summary.loc[~summary["is_baseline"].eq(True)]
                .sort_values("full_annualized_multiple", ascending=True)
                .head(30)
                .to_dict(orient="records"),
                "outputs": {
                    "markdown": str(ABLATION_MARKDOWN_PATH),
                    "summary": str(ABLATION_SUMMARY_PATH),
                    "monthly": str(ABLATION_MONTHLY_PATH),
                },
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    args = parse_args()
    frame_raw, quality = load_hype_5m()
    parity = None if args.skip_raw_parity else verify_raw_normalized_parity(frame_raw)
    if parity is not None:
        assert_data_quality(quality, parity)
    apply_cost_model()
    frame = add_features(frame_raw)
    run_baseline(frame, quality, parity)
    if not args.skip_ablation:
        summary = run_ablation(frame, quality, parity)
        print(summary.loc[summary["is_baseline"].eq(True), ["full_trades", "full_annualized_multiple", "full_profit_factor"]].to_string(index=False))
        print(f"wrote {ABLATION_MARKDOWN_PATH}")


if __name__ == "__main__":
    main()
