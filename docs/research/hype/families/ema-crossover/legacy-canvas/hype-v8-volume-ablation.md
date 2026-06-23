# HYPE V8 Volume Overlay Ablation

> 迁移说明：本文由 legacy Cursor Canvas `hype-v8-volume-ablation.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：HYPE-EMA-X legacy Canvas。

固定当前 V8 基线，只替换一个参数，观察收益、回撤、Sharpe、交易数和退出结构变化。

Source: Binance HYPEUSDT perp 15m data lake · 2025-05-30 10:30 UTC → 2026-06-01 03:00 UTC · reports/hype_ema_volume_overlay_v8_ablation.json.

> **结论**
> 最干净的改进是 wick_min=0.55：1Y 收益从 +493.56% 提升到 +530.65%，最大回撤保持 -27.63%。adx_exit=18 收益最高，但最大回撤扩大到 -32.13%，不建议直接替换当前基线。

### 关键指标

| 指标 | 数值 |
| --- | --- |
| V8 baseline return | +493.56% |
| V8 baseline max DD | -27.63% |
| Best clean candidate | +530.65% |
| Most sensitive parameter | cooldown |

## 基线与关键候选

| 口径 | 参数 | 收益 | 最大回撤 | Sharpe | 交易数 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| V8 baseline | full_exit / xrv2 / mfe4 / fb1 / cd0 / stop9 / adx22 / adxb3 | +493.56% | -27.63% | 2.85 | 97 | 当前 V8 基线 |
| V6 no overlay | 移除量能衰竭覆盖，只保留 V6 动态 3x | +454.08% | -26.77% | 2.66 | 49 | 收益少 39.47pct，但交易路径更少 |
| Best single-factor return | adx_exit=18 | +540.39% | -32.13% | 2.83 | 96 | 收益最高，但回撤扩大明显 |
| Best clean candidate | wick_min=0.55 | +530.65% | -27.63% | 2.94 | 97 | 收益和 Sharpe 提升，回撤不增加 |

### 参数敏感度

X 轴：参数；Y 轴：fitness range。数值越大，单参数变化对结果越敏感。

> 图表数据未能完全自动解析，请按源 Canvas 复核。

### 分支对比

full_exit、half_reduce、no_overlay 在同一数据窗口下比较。

| 分支 | 收益 | 最大回撤 | Sharpe | 交易数 | 退出结构 | 判断 |
| --- | --- | --- | --- | --- | --- | --- |
| full_exit | +493.56% | -27.63% | 2.85 | 97 | 55 volume_exhaustion；38 trend_break；3 stop_loss；1 opposite_cross | 最佳分支 |
| half_reduce | +284.95% | -21.93% | 2.78 | 49 | 最终仍主要由 trend_break 退出；27 次减仓 | 回撤更低，但收益明显不如全平 |
| no_overlay V6 | +454.08% | -26.77% | 2.66 | 49 | 47 trend_break；1 stop_loss；1 opposite_cross | 交易少，但收益低于 V8 overlay |

## 全参数消融汇总

| 参数 | 候选值 | 最佳值 | 最佳收益 | 最佳回撤 | 最差值 | 最差收益 | 收益范围 | 判断 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cooldown_bars | 0 / 16 / 32 / 64 / 96 | 0 | +493.56% | -27.63% | 96 | +118.52% | 3.75 | 最敏感；开启冷却会错过同一 regime 内再入场，不建议开启 |
| adx_exit | 18 / 20 / 22 / 24 / 26 / 28 | 18 | +540.39% | -32.13% | 28 | +219.44% | 3.21 | 收益弹性大，但低阈值会放大回撤；当前 22 更均衡 |
| reduce_fraction | 0.25 / 0.33 / 0.5 / 0.67 / 0.75 / 1.0 | 0.25 | +374.30% | -24.35% | 1.0 | +136.87% | 2.37 | 仅 half_reduce 分支有效；整体仍不如 full_exit |
| action | full_exit / half_reduce | full_exit | +493.56% | -27.63% | half_reduce | +284.95% | 2.09 | 量能衰竭后全平明显优于减半仓 |
| fail_bars | 1 / 2 / 3 / 4 | 1 | +493.56% | -27.63% | 2 | +336.92% | 1.57 | 确认越慢越容易回吐；1 根确认最优 |
| min_mfe_atr | 1.5 / 2 / 2.5 / 3 / 4 / 5 / 6 | 4 | +493.56% | -27.63% | 1.5 | +352.38% | 1.41 | 过早触发会切碎趋势；4ATR 是当前平衡点 |
| stop_atr | 6 / 7.5 / 9 / 10.5 / 12 | 12 | +519.98% | -27.63% | 6 | +451.61% | 0.68 | 更宽灾难止损略增收益；需要额外看极端行情风险 |
| adx_exit_bars | 1 / 2 / 3 / 4 / 5 | 2 | +501.66% | -27.00% | 4 | +437.75% | 0.64 | 2 根趋势坏掉确认略优于当前 3 根 |
| wick_min | 0.25 / 0.35 / 0.45 / 0.55 / 0.65 | 0.55 | +530.65% | -27.63% | 0.25 | +493.56% | 0.37 | 最干净的提升项；收益和 Sharpe 提升且回撤不增加 |
| exit_rvol | 1.2 / 1.5 / 2 / 2.5 / 3 | 1.2 | +505.87% | -31.22% | 3 | +465.21% | 0.41 | 更早触发能提高收益，但回撤扩大；2.0 更均衡 |
| overlay | V8 overlay / no_overlay V6 | V8 overlay | +493.56% | -27.63% | no_overlay | +454.08% | 0.39 | 量能衰竭覆盖相对 V6 增加约 39.47pct 收益 |

## V8.1 候选

以下是单因素提升项，下一步应做组合搜索，不应简单叠加后直接作为正式版本。

| 候选 | 收益 | 最大回撤 | Sharpe | 收益变化 | 回撤变化 | 判断 |
| --- | --- | --- | --- | --- | --- | --- |
| adx_exit=18 | +540.39% | -32.13% | 2.83 | +46.83pct | -4.50pct | 高收益高回撤，不直接替换基线 |
| wick_min=0.55 | +530.65% | -27.63% | 2.94 | +37.10pct | 0.00pct | 优先进入 V8.1 组合搜索 |
| stop_atr=12 | +519.98% | -27.63% | 2.91 | +26.42pct | 0.00pct | 可进入 V8.1，但需关注极端回撤 |
| adx_exit_bars=2 | +501.66% | -27.00% | 2.88 | +8.10pct | +0.63pct | 小幅稳健改善 |
| exit_rvol=1.2 | +505.87% | -31.22% | 2.91 | +12.31pct | -3.60pct | 收益提升但回撤代价明显 |
| no_overlay V6 | +454.08% | -26.77% | 2.66 | -39.47pct | +0.86pct | 证明 overlay 提升有效 |

### 产物路径

| 文件 | 内容 |
| --- | --- |
| scripts/research_hype_ema_volume_overlay_v8_ablation.py | V8 单因素消融脚本 |
| reports/hype_ema_volume_overlay_v8_ablation.json | 结构化消融报告 |
| reports/hype_ema_volume_overlay_v8_ablation_summary.csv | 参数敏感度汇总 |
| reports/hype_ema_volume_overlay_v8_ablation_detail.csv | 每个参数候选值的完整明细 |

## 自动转换复核提示

以下组件存在降级转换提示，建议人工抽查源 Canvas：

- `chart`
