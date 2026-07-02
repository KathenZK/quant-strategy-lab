from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

RANKING_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_v17_1_full_ablation_ranking.csv")
SENSITIVITY_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_v17_1_full_ablation_sensitivity.csv")
PRUNE_CSV_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_v17_1_parameter_prune_audit.csv")
MARKDOWN_PATH = Path(
    "research/hype/15m-ema-crossover/diagnostics/hype-ema-x-v17-1-parameter-prune-audit-2026-07-01.md"
)

OFFICIAL_DEFAULTS: dict[str, str] = {
    "hq_scale": "1.1",
    "lq_scale": "1.0",
    "hq_enabled": "true",
    "lq_enabled": "true",
    "hq_min_score": "7",
    "lq_min_score": "5",
    "lq_max_score": "6",
    "lq_max_dist_ema96": "0.04",
    "lq_max_atr_ratio": "1.1",
    "late_max_age": "384",
    "late_dist_ema96": "0.075",
    "cooldown_bars": "12",
    "min_prev_pnl": "-0.03",
    "min_prev_mfe_atr": "3.0",
    "warning_source": "either",
    "confirm_mode": "ema21",
    "min_mfe_atr": "4.0",
    "warning_exit_min_capture": "0.35",
    "volume_warning_mode": "no_mfi_div",
    "exit_rvol": "2.0",
    "wick_min": "0.55",
    "osc_min_score": "2",
    "hard_exit_mode": "swing96",
    "hard_exit_bars": "1",
    "entry_max_regime_age": "128",
    "entry_max_dist_ema96": "0.08",
    "stop_atr": "8.0",
}

INACTIVE_MODULES = {
    "reentry_mode": "none",
    "require_pullback": "false",
    "pullback_buffer": "0.0",
    "entry_min_rvol96": "0.0",
    "entry_max_move48": "0.0",
    "fallback_adx": "0.0",
    "segment_exit_mode": "none",
    "confirm_window": "24",
}


def pct(value: float) -> str:
    return f"{value * 100:+.2f}%"


def classify_parameters(ranking: pd.DataFrame, sensitivity: pd.DataFrame) -> pd.DataFrame:
    base = ranking.loc[ranking.parameter == "baseline"].iloc[0]
    base_ret = float(base["return"])
    base_dd = float(base["max_dd"])
    base_trades = int(base["trades"])
    base_wr = float(base["win_rate"])

    rows: list[dict[str, object]] = []
    for param, group in ranking[ranking.parameter != "baseline"].groupby("parameter", sort=False):
        exact = (
            (group["return"] == base_ret)
            & (group["max_dd"] == base_dd)
            & (group["trades"] == base_trades)
            & (group["win_rate"] == base_wr)
        )
        all_exact = bool(exact.all())
        any_exact = bool(exact.any())
        ret_range = float(group["return"].max() - group["return"].min())
        dd_range = float(group["max_dd"].max() - group["max_dd"].min())
        trades_range = int(group["trades"].max() - group["trades"].min())
        sens = sensitivity.loc[sensitivity.parameter == param]
        best_delta = float(sens["best_return_delta"].iloc[0]) if len(sens) else 0.0
        worst_ret = float(sens["worst_return"].iloc[0]) if len(sens) else float(group["return"].min())

        if all_exact:
            verdict = "noop"
            action = "从官方规格删除；保留代码默认值即可"
        elif param in INACTIVE_MODULES and worst_ret < base_ret * 0.85:
            verdict = "inactive_harmful"
            action = "保持关闭；不要写进 live spec"
        elif any_exact and trades_range == 0 and ret_range < 1.0:
            verdict = "noop_band"
            action = "官方值周围存在宽无效带；规格只保留当前官方点"
        elif best_delta > 0.5:
            verdict = "sizing_or_risk_knob"
            action = "有效风险旋钮；V17.1 仅 hq_scale 已使用"
        elif worst_ret < base_ret * 0.75 and best_delta <= 0.01:
            verdict = "defensive_only"
            action = "偏离 baseline 显著变差；保留当前官方值"
        else:
            verdict = "core"
            action = "核心有效参数；保留"

        rows.append(
            {
                "parameter": param,
                "verdict": verdict,
                "action": action,
                "official_default": OFFICIAL_DEFAULTS.get(param, INACTIVE_MODULES.get(param, "")),
                "candidates": int(len(group)),
                "exact_match_candidates": int(exact.sum()),
                "return_range_pct": ret_range * 100,
                "dd_range_pct": dd_range * 100,
                "trades_range": trades_range,
                "best_return_delta_pct": best_delta * 100,
                "worst_return_pct": worst_ret * 100,
            }
        )
    return pd.DataFrame(rows).sort_values(["verdict", "return_range_pct"], ascending=[True, False])


def render_markdown(ranking: pd.DataFrame, table: pd.DataFrame) -> str:
    base = ranking.loc[ranking.parameter == "baseline"].iloc[0]
    noop = table.loc[table.verdict == "noop"]
    noop_band = table.loc[table.verdict == "noop_band"]
    inactive = table.loc[table.verdict == "inactive_harmful"]
    defensive = table.loc[table.verdict == "defensive_only"]
    knobs = table.loc[table.verdict == "sizing_or_risk_knob"]
    core = table.loc[table.verdict == "core"]

    lines = [
        "# HYPE-EMA-X-V17.1 全参数消融与精简口径",
        "",
        "日期：2026-07-01",
        "",
        "Canonical ledger：`hype-ema-x-core-ledger.md`",
        "",
        "## 方法",
        "",
        "- 脚本：`research_hype_v17_1_full_ablation.py`",
        "- 基准：`HYPE-EMA-X-V17.1`（`hq_scale=1.1`，`lq_scale=1.0`）",
        "- 数据切片：`<= 2026-06-01 03:00 UTC`，rolling 1Y",
        f"- 候选数：`{len(ranking) - 1}` 个单参数消融 + baseline",
        f"- Baseline 复现：收益 `{pct(float(base['return']))}`，回撤 `{pct(float(base['max_dd']))}`，",
        f"  `{int(base['trades'])}` 笔，胜率 `{pct(float(base['win_rate']))}`",
        "",
        "判定口径：",
        "",
        "- **noop**：所有消融取值与 baseline 成交路径完全一致（收益/回撤/笔数/胜率相同）。",
        "- **noop_band**：部分消融取值无效，说明官方点附近存在宽无效带。",
        "- **inactive_harmful**：模块默认关闭；一旦打开明显伤害收益。",
        "- **defensive_only**：只能守 baseline，调参不能改善且偏离会显著变差。",
        "- **sizing_or_risk_knob**：主要改变风险预算，不是信号识别器。",
        "",
        "## 结论摘要",
        "",
        "V17.1 官方规则里写了大量参数，但 **146 项消融** 表明其中相当一部分在当前 HYPE 1Y 样本上 **从未改变实际成交**。",
        "这不是说代码没算这些字段，而是说它们对 **33 笔成交路径** 没有边际贡献。",
        "",
        "应保留的是：**方向/基础信号、HQ/LQ 分流、普通入场窗口、late re-entry、动态仓位、预警+EMA21 出场、swing96 结构退出**。",
        "应从 live spec 删除或保持关闭的是：**OBV/CMF/hot-edge 卫星附加过滤、confirm_window 调参、",
        "pullback/reentry/breakout 补单、segment/fallback 分段退出、以及样本内从未触发的 stop 距离调参**。",
        "",
        "## 1. 可剔除（noop：对成交无影响）",
        "",
        "| 参数 | 官方默认 | 消融结论 | 处理 |",
        "| --- | --- | --- | --- |",
    ]
    for row in noop.itertuples():
        lines.append(
            f"| `{row.parameter}` | `{row.official_default or '-'}` | "
            f"{row.exact_match_candidates}/{row.candidates} 个取值与 baseline 完全相同 | 从规格删除 |"
        )

    lines.extend(["", "## 2. 宽无效带（官方值可保留，邻域调参无效）", "", "| 参数 | 官方默认 | 无效带观察 | 处理 |", "| --- | --- | --- | --- |"])
    for row in noop_band.itertuples():
        lines.append(
            f"| `{row.parameter}` | `{row.official_default}` | "
            f"{row.exact_match_candidates}/{row.candidates} 个取值无效；return_range `{row.return_range_pct:.1f}%` | 规格只写官方点 |"
        )

    lines.extend(["", "## 3. 保持关闭的模块（打开会伤收益）", "", "| 参数 | 默认 | 最差收益 | 处理 |", "| --- | --- | --- | --- |"])
    for row in inactive.itertuples():
        lines.append(
            f"| `{row.parameter}` | `{row.official_default or INACTIVE_MODULES.get(row.parameter, '-')}` | "
            f"`{pct(row.worst_return_pct / 100)}` | 不写进 live spec |"
        )

    lines.extend(["", "## 4. 风险旋钮（有效，但属于仓位预算）", "", "| 参数 | 最佳消融 | 收益增量 | 判断 |", "| --- | --- | ---: | --- |"])
    for row in knobs.itertuples():
        lines.append(
            f"| `{row.parameter}` | 见 sensitivity | `{row.best_return_delta_pct:+.1f}%` | "
            f"{'V17.1 已用' if row.parameter == 'hq_scale' else '不升格官方' } |"
        )

    lines.extend(["", "## 5. 核心有效参数（必须保留）", ""])
    core_params = [
        ("方向/基础信号", "ema_spread, ADX28, vol_surge192, h1 确认, atr_ratio<=1.8"),
        ("HQ 主信号", "trend_score>=7"),
        ("LQ 卫星", "trend_score 5-6, dir_dist_ema96<=4%, atr_ratio<=1.1"),
        ("普通入场", "regime_age<=128, dist_ema96<=8%, 下一根 open"),
        ("Late re-entry", "late_max_age=384, late_dist=7.5%, cooldown=12, min_prev_pnl=-3%, min_prev_mfe=3ATR"),
        ("仓位", "dynamic allocation max 3x; V17.1: HQ×1.1, LQ×1.0"),
        ("预警出场", "min_mfe=4ATR, warning either, capture>=35%, confirm EMA21"),
        ("量能预警", "no_mfi_div, exit_rvol=2.0, wick_min=0.55"),
        ("振荡预警", "1h RSI/KDJ/MACD, osc_min_score=2"),
        ("结构退出", "hard_exit_mode=swing96, hard_exit_bars=1"),
    ]
    lines.append("| 模块 | 保留参数 |")
    lines.append("| --- | --- |")
    for module, params in core_params:
        lines.append(f"| {module} | `{params}` |")

    lines.extend(["", "## 6. 防守型参数（不能删，但也不应为了提收益去改）", "", "| 参数 | 官方默认 | return_range | 说明 |", "| --- | --- | ---: | --- |"])
    for row in defensive.itertuples():
        lines.append(
            f"| `{row.parameter}` | `{row.official_default or '-'}` | `{row.return_range_pct:.1f}%` | 偏离 baseline 明显变差 |"
        )

    lines.extend(
        [
            "",
            "## 7. 精简后官方口径（建议写法）",
            "",
            "下面是把无效项剔除后，V17.1 应写入 live spec / handoff 的最小集合。",
            "策略身份不变，仍叫 `HYPE-EMA-X-V17.1`。",
            "",
            "### 信号",
            "",
            "- 基础：`atr18` EMA regime 信号（多/空阈值见主台账）。",
            "- HQ：`trend_score >= 7`。",
            "- LQ：`trend_score` 5–6 且 `dir_dist_ema96 <= 4%` 且 `atr_ratio96_672 <= 1.1`。",
            "- **删除**：`lq_require_obv`、`lq_require_cmf`、`lq_require_not_hot_edge`。",
            "",
            "### 入场",
            "",
            "- 普通：`regime_age <= 128`，`dir_dist_ema96 <= 8%`，收盘确认、下一根 open。",
            "- Late：`late_max_age=384`，`late_dist_ema96=7.5%`，`cooldown=12`，`min_prev_pnl=-3%`，`min_prev_mfe_atr=3`。",
            "- **删除**：`require_pullback`、`reentry_mode`、`entry_min_rvol96`、`entry_max_move48`。",
            "",
            "### 仓位",
            "",
            "- `allocation = min(3, target_atr / atr_pct672)`；HQ `×1.1`，LQ `×1.0`。",
            "",
            "### 出场",
            "",
            "- 硬止损：`stop_atr=8`（保留规则，但当前 1Y 样本 0 笔触发；不宜为了调参删规则）。",
            "- 结构：`swing96`，破位后下一根 open。",
            "- 利润保护：`min_mfe_atr=4`，`warning_source=either`，`warning_exit_min_capture=35%`，`confirm_mode=ema21`。",
            "- 量能：`no_mfi_div`，`exit_rvol=2.0`，`wick_min=0.55`。",
            "- 振荡：`osc_min_score=2`（1h）。",
            "- **删除/保持关闭**：`fallback_adx`、`segment_exit_*`、`confirm_window` 调参、`hard_exit_bars>1` 试验项。",
            "",
            "## 8. 重要限制",
            "",
            "1. **noop 不等于逻辑无用**：例如 `stop_atr` 在 8–12 之间结果相同，是因为样本内没有 stop_loss；实盘仍必须保留止损规则。",
            "2. **LQ 只有 4 笔**：`lq_max_atr_ratio`、`lq_scale` 等卫星参数对总收益敏感，但证据薄，不宜借消融结果继续加复杂卫星过滤。",
            "3. **`hq_scale` 是最强收益旋钮**：继续放大 HQ 会越过 20% 回撤边界；V17.1 的 1.1 已是风险预算上限附近。",
            "4. **不建议为增样本去放宽 HQ 过滤**：那会退回 V16 路线，不是 V17.1 精简。",
            "",
            "## 产物",
            "",
            f"- 全量消融：`artifacts/hype_v17_1_full_ablation_ranking.csv`",
            f"- 敏感性：`artifacts/hype_v17_1_full_ablation_sensitivity.csv`",
            f"- 剔除表：`artifacts/hype_v17_1_parameter_prune_audit.csv`",
            f"- 本报告：`diagnostics/hype-ema-x-v17-1-parameter-prune-audit-2026-07-01.md`",
            f"- V18 干净规格：`canonical-specs/hype-ema-x-v18-baseline-spec.md`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    ranking = pd.read_csv(RANKING_PATH)
    sensitivity = pd.read_csv(SENSITIVITY_PATH)
    table = classify_parameters(ranking, sensitivity)
    PRUNE_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(PRUNE_CSV_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(ranking, table), encoding="utf-8")
    print(f"wrote={MARKDOWN_PATH}")
    print(f"prune_csv={PRUNE_CSV_PATH}")
    print(table.groupby("verdict").size().to_string())


if __name__ == "__main__":
    main()
