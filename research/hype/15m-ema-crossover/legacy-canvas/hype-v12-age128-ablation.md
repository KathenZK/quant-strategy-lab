# HYPE V12.4 age128 参数消融

> 迁移说明：本文由 legacy Cursor Canvas `hype-v12-age128-ablation.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：HYPE-EMA-X legacy Canvas。

Baseline：V12.4 cap35 + swing96 hard exit + no_mfi_div + entry_max_regime_age=128。每次只改一个参数；segment 这类默认关闭模块用合理启用组合测试。

Source: Binance HYPEUSDT perp 15m data lake · 2025-05-30 10:30 UTC → 2026-06-01 03:00 UTC · artifacts/hype_state_machine_v12_age128_ablation.json.

> **结论**
> age128 + entry_max_dist_ema96<=8% 是本轮最值得继续推进的版本：1Y 收益 +1573.15%，最大回撤 -20.39%，Sharpe 4.28，交易 27 笔。它不是靠放宽交易数量抬收益，而是过滤离 EMA96 过远的追高/追空入场。

### 关键指标

| 指标 | 数值 |
| --- | --- |
| 最佳折中收益 | +1573.15% |
| 最佳折中回撤 | -20.39% |
| 最佳折中 Sharpe | 4.28 |
| 最佳折中胜率 | 85.19% |

## Top 候选

| 排序 | 参数 | 取值 | 1Y收益 | 最大回撤 | Sharpe | 交易数 | 胜率 | 收益变化 | 判断 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | entry_max_dist_ema96 | 0.08 | +1573.15% | -20.39% | 4.28 | 27 | 85.19% | +314.72pp | 最佳折中：收益、回撤、Sharpe 同时优于 age128 baseline |
| 2 | entry_max_regime_age | 0 | +1587.09% | -37.53% | 3.23 | 60 | 65.00% | +328.66pp | 等价于取消 age 过滤，收益高但回撤回到 V12.3 水平 |
| 3 | entry_max_dist_ema96 | 0.10 | +1488.43% | -20.39% | 4.17 | 27 | 85.19% | +230.00pp | 和 dist08 同样降回撤，但收益略低 |
| 4 | entry_max_regime_age | 256 | +1512.85% | -37.53% | 3.65 | 39 | 74.36% | +254.42pp | 放宽 age 增加收益，但 drawdown 明显变差 |
| 5 | entry_max_move48 | 0.12 | +1450.43% | -20.39% | 4.18 | 27 | 85.19% | +192.00pp | 也能降低回撤，但收益低于 dist08 |
| baseline | V12.4 age128 | baseline | +1258.43% | -29.47% | 3.94 | 28 | 82.14% | 0 | 当前偏好版本 |

### 收益 / 回撤对比

X 轴：候选规则；Y 轴：百分比。收益为净值增长，回撤为最大回撤绝对值。

原 Canvas 使用图表展示；这里保留图表底层数据。

| 分类 | 1Y return (%) | max drawdown abs (%) |
| --- | --- | --- |
| baseline | 1258.43 | 29.47 |
| dist08 | 1573.15 | 20.39 |
| dist10 | 1488.43 | 20.39 |
| move12 | 1450.43 | 20.39 |
| age0 | 1587.09 | 37.53 |
| age256 | 1512.85 | 37.53 |

### 敏感度 Top 参数

X 轴：参数；Y 轴：同参数候选的收益跨度，单位为净值倍数。

原 Canvas 使用图表展示；这里保留图表底层数据。

| 分类 | return range (x) |
| --- | --- |
| hard exit | 12.06 |
| confirm | 9.54 |
| age | 8.41 |
| warning | 6.94 |
| exit rvol | 5.57 |
| vol mode | 5.03 |
| segment | 4.5 |

## 参数敏感度

| 参数 | 候选数 | 收益跨度 | 回撤跨度 | 最佳收益取值 | 最佳回撤取值 | 结论 |
| --- | --- | --- | --- | --- | --- | --- |
| hard_exit_mode | 7 | 12.06x | 3.53pp | none | swing24 | 硬退出结构非常敏感；不建议改成 EMA 或短 swing |
| confirm_mode | 7 | 9.54x | 5.32pp | ema21_or_donchian | atr_trail | EMA21 仍是主确认；更慢确认会砍收益 |
| entry_max_regime_age | 5 | 8.41x | 17.13pp | 0 | 64 | age 是主要收益/回撤旋钮；128 是风险折中点 |
| warning_source | 2 | 6.94x | 9.15pp | either | either | osc 单独较差；either 与 volume 基线无差异 |
| exit_rvol | 3 | 5.57x | 0.00pp | 2.5 | 3.0 | 在 no_mfi_div 下多数阈值不影响核心路径 |
| volume_warning_mode | 4 | 5.03x | 0.00pp | blowoff_only | mfi_rvol_exit_wick35 | no_mfi_div 仍是合理默认，重新引入 MFI 变差 |
| segment_min_mfe_atr | 2 | 4.50x | 0.00pp | 6.0 | 2.0 | 分段参数整体砍收益，不适合 age128 |
| wick_min | 3 | 4.05x | 0.00pp | 0.45 | 0.35 | 更宽/更严长影线阈值都不如基线 |
| stop_atr | 4 | 3.96x | 5.96pp | 8.0 | 7.0 | 8ATR 略好，过紧/过宽都降低收益 |
| segment_exit_mode | 5 | 3.15x | 0.00pp | ema55_adx22 | adx22 | 分段退出对 age128 是负贡献 |
| entry_max_dist_ema96 | 2 | 0.85x | 0.00pp | 0.08 | 0.10 | 最稳定的正贡献参数 |
| entry_max_move48 | 2 | 0.36x | 0.87pp | 0.12 | 0.12 | 正贡献，但弱于 dist08 |
| reentry_mode | 2 | 0.00x | 0.00pp | breakout48 | breakout48 | 当前再入场逻辑不适合 age128 |

### 不建议继续加的方向

| 改动 | 1Y收益 | 最大回撤 | Sharpe | 原因 |
| --- | --- | --- | --- | --- |
| fallback_adx=18 | +206.29% | -29.47% | 2.37 | ADX fallback 过早切断趋势，收益下降约 1052pp |
| fallback_adx=22 | +181.82% | -24.67% | 2.31 | 回撤小一点，但收益被砍到不可接受 |
| reentry_mode=breakout48/96 | +469.47% | -29.58% | 3.15 | 再入场没有吃回趋势，反而错过主段利润 |
| segment_exit_mode=adx18 | +366.18% | -29.47% | 2.98 | 分段退出把 age128 的长趋势利润切碎 |
| confirm_mode=ema96 | +349.80% | -33.30% | 2.29 | 确认太慢，亏损/回吐更重 |
| confirm_mode=donchian | +320.00% | -31.07% | 2.26 | 结构确认过慢，不如 EMA21 |

> **下一步**
> 先不要直接把 age128 改成 age0 或 age256。虽然它们收益更高，但回撤重新扩大到 -37.53%。更稳的下一轮是测试 age128 + dist08 的横向窗口表现，并把它和 age128 + move48_12 做组合/窗口回测。

## 产物路径

| 文件 | 内容 |
| --- | --- |
| scripts/research_hype_state_machine_v12_age128_ablation.py | V12.4 age128 单因子全参数消融脚本 |
| artifacts/hype_state_machine_v12_age128_ablation_ranking.csv | 全候选排名 |
| artifacts/hype_state_machine_v12_age128_ablation_sensitivity.csv | 按参数聚合的敏感度 |
| artifacts/hype_state_machine_v12_age128_ablation.json | 结构化报告 |
| artifacts/hype_state_machine_v12_age128_ablation_diagnostics_summary.csv | baseline 交易路径诊断摘要 |
