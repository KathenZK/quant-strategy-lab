# HYPE V12 State Machine

> 迁移说明：本文由 legacy Cursor Canvas `hype-v12-state-machine.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：HYPE-EMA-X legacy Canvas。

V12 将量能衰竭和震荡指标降级为 warning，只有价格结构 confirm 后才退出，目标是减少 V8/V10 的过早平仓。

Source: Binance HYPEUSDT perp 15m data lake · 2025-05-30 10:30 UTC → 2026-06-01 03:00 UTC · reports/hype_state_machine_v12.json.

> **结论**
> V12.6 把 age128 和 segment ADX 叠加后，低回撤进一步成立，但收益被明显砍掉。age128 单独已经能把坏入场率降到 14.29%、回撤降到 -29.47%；再叠加 ADX 分段不会进一步降低回撤，只会切掉利润。

### 关键指标

| 指标 | 数值 |
| --- | --- |
| 高收益候选 | +1601.37% |
| 低回撤候选 | +1258.43% |
| 最低回撤测试 | -20.39% |
| 最低回撤收益 | +432.32% |

## 候选对比

| 版本 | 规则 | 1Y收益 | 最大回撤 | Sharpe | 交易数 | 胜率 | 平均持仓K | 退出结构 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V6 baseline | V6 dynamic 3x | +454.08% | -26.77% | 2.66 | 49 | 69.39% | 67.55 | 47 trend_break；1 stop_loss；1 opposite_cross |
| V8 clean | volume exhaustion 直接退出 | +530.65% | -27.63% | 2.94 | 97 | 71.13% | 31.03 | 55 volume_exhaustion；38 trend_break；3 stop_loss；1 opposite_cross |
| V12 高收益 | volume warning + EMA21 confirm；无 ADX fallback | +792.86% | -43.20% | 2.72 | 76 | 76.32% | 75.75 | 63 warning_confirm_volume；11 stop_loss；2 opposite_cross |
| V12.1 swing96 hard | 保留高收益版；增加 96 根结构低/高点破坏硬退出 | +1205.06% | -37.53% | 3.25 | 79 | 72.15% | 64.54 | 62 warning_confirm_volume；12 hard_swing96；4 stop_loss；1 opposite_cross |
| V12.2 no MFI div | 保留 swing96 hard；volume warning 去掉 MFI divergence，只保留 blowoff / effort-fail | +1547.98% | -37.53% | 3.24 | 65 | 66.15% | 99.65 | 43 warning_confirm_volume；17 hard_swing96；4 stop_loss；1 opposite_cross |
| V12.3 cap35 | 保留 V12.2；warning_confirm 退出要求当前捕获 >=35% MFE | +1587.09% | -37.53% | 3.23 | 60 | 65.00% | 113.03 | 36 warning_confirm_volume；19 hard_swing96；4 stop_loss；1 opposite_cross |
| V12.4 age128 | 保留 V12.3；只允许 EMA regime 前 128 根内入场 | +1258.43% | -29.47% | 3.94 | 28 | 82.14% | 120.32 | 21 warning_confirm_volume；5 hard_swing96；2 stop_loss |
| V12.4 move48_12 | 保留 V12.3；入场前 48 根同向涨跌幅不得超过 12% | +1601.37% | -36.97% | 3.27 | 59 | 66.10% | 114.12 | 36 warning_confirm_volume；19 hard_swing96；3 stop_loss；1 opposite_cross |
| V12.5 segment ADX18 | 趋势已有 4ATR MFE 后，ADX28 < 18 连续 3 根先退出，等待后续再入场 | +1092.86% | -31.85% | 3.37 | 62 | 72.58% | 71.81 | 33 segment_adx；20 warning_confirm_volume；5 hard_swing96；3 stop_loss；1 opposite_cross |
| V12.6 age128 + ADX22 | 只允许 regime 前 128 根入场；已有 4ATR MFE 后 ADX28 < 22 分段退出 | +473.49% | -29.47% | 3.42 | 28 | 85.71% | 71.50 | 16 segment_adx；11 warning_confirm_volume；1 stop_loss |
| V12.6 age128 + move48 + ADX18 | regime 前 128 根入场，且 48 根同向涨跌幅 <=12%；ADX18 分段退出 | +432.32% | -20.39% | 3.30 | 27 | 77.78% | 75.26 | 14 segment_adx；12 warning_confirm_volume；1 stop_loss |
| V12.5 segment EMA55 | 趋势已有 4ATR MFE 后，跌破/升破 EMA55 且捕获 >=35% MFE 先退出 | +728.09% | -37.53% | 2.69 | 62 | 69.35% | 88.58 | 18 segment_ema55；25 warning_confirm_volume；14 hard_swing96；4 stop_loss；1 opposite_cross |
| V12.2 blowoff only | 保留 swing96 hard；volume warning 只保留放量长影线 blowoff | +1275.52% | -37.53% | 2.96 | 63 | 63.49% | 113.27 | 37 warning_confirm_volume；21 hard_swing96；4 stop_loss；1 opposite_cross |
| V12.1 swing96 + ADX18 | swing96 硬退出 + ADX18 连续 3 根 fallback | +527.24% | -31.85% | 2.79 | 82 | 63.41% | 41.85 | 46 warning_confirm_volume；29 fallback；3 stop_loss；3 hard_swing96；1 opposite_cross |
| V12 收益/回撤折中 | volume warning + ATR trail 10ATR confirm；ADX22 fallback | +470.99% | -26.77% | 2.71 | 50 | 70.00% | 65.62 | 43 fallback_trend_break；6 warning_confirm_volume；1 opposite_cross |
| V12 慢 EMA 确认 | volume warning + EMA96 confirm；ADX22 fallback | +466.72% | -27.10% | 2.69 | 49 | 69.39% | 66.69 | 41 fallback_trend_break；6 warning_confirm_volume；1 stop_loss；1 opposite_cross |

### 收益与回撤

X 轴：候选版本；Y 轴：百分比。收益为期末净值减 1，回撤为最大净值回撤绝对值。

原 Canvas 使用图表展示；这里保留图表底层数据。

| 分类 | 1Y return (%) | max drawdown abs (%) |
| --- | --- | --- |
| V12.4 hi | 1601.37 | 36.97 |
| age128 | 1258.43 | 29.47 |
| seg ADX | 1092.86 | 31.85 |
| age+ADX22 | 473.49 | 29.47 |
| age+move+ADX | 432.32 | 20.39 |

### V12 路径诊断

X 轴：V12 候选；Y 轴：交易占比。分类沿用 V11 诊断规则。

原 Canvas 使用图表展示；这里保留图表底层数据。

| 分类 | bad_entry (%) | max drawdown abs (%) | win_rate (%) |
| --- | --- | --- | --- |
| V12.3 | 30.0 | 37.53 | 65.0 |
| move48 | 28.81 | 36.97 | 66.1 |
| age256 | 20.51 | 37.53 | 74.36 |
| age128 | 14.29 | 29.47 | 82.14 |

## Top Ranking 摘要

| 排序 | warning / confirm | 关键参数 | 1Y收益 | 最大回撤 | Sharpe | 交易数 |
| --- | --- | --- | --- | --- | --- | --- |
| V12.4 | V12.3 + move48 <=12% | 高收益候选 | +1601.37% | -36.97% | 3.27 | 59 |
| V12.4 | V12.3 + regime age <=128 | 低回撤候选 | +1258.43% | -29.47% | 3.94 | 28 |
| V12.6 | age128 + segment ADX22 | 低回撤组合测试 | +473.49% | -29.47% | 3.42 | 28 |
| V12.6 | age128 + move48 + segment ADX18 | 最低回撤测试 | +432.32% | -20.39% | 3.30 | 27 |
| V12.5 | segment ADX18 | 趋势弱化分段退出 | +1092.86% | -31.85% | 3.37 | 62 |
| V12.5 | segment EMA55 | 价格结构分段退出 | +728.09% | -37.53% | 2.69 | 62 |
| V12.3 | swing96 hard + no MFI + cap35 | warning exit capture >=35% | +1587.09% | -37.53% | 3.23 | 60 |
| V12.2 | swing96 hard + no MFI div | 只保留 blowoff / effort-fail | +1547.98% | -37.53% | 3.24 | 65 |
| V12.2 | swing96 hard + blowoff only | 只保留放量长影线 | +1275.52% | -37.53% | 2.96 | 63 |
| V12.1 | volume + EMA21 + swing96 hard | mfe4 / no fallback | +1205.06% | -37.53% | 3.25 | 79 |
| V12.1 | volume + EMA21 + swing96 hard | mfe4 / ADX18 fallback | +527.24% | -31.85% | 2.79 | 82 |
| 1 | volume + EMA21 | mfe4 / no fallback | +792.86% | -43.20% | 2.72 | 76 |
| 2 | volume + EMA21/Donchian | mfe4 / no fallback | +792.86% | -43.20% | 2.72 | 76 |
| 3 | either + EMA21 | mfe4 / no fallback | +792.86% | -43.20% | 2.72 | 76 |
| 4 | volume + ATR trail 10ATR | mfe2 / ADX18 | +594.04% | -31.33% | 2.83 | 47 |
| 5 | osc + EMA96 | mfe2 / ADX18 | +591.25% | -31.33% | 2.76 | 46 |
| 风险约束最佳 | volume + ATR trail 10ATR | mfe2 / ADX22 | +470.99% | -26.77% | 2.71 | 50 |

## V12.1 Hard Exit 结论

> **swing96 是这一轮最有效的硬趋势失效**
> EMA96 break 太敏感，swing24/48 会切碎趋势；96 根结构高低点破坏更符合“趋势真的坏了”的定义。它减少了大止损，同时没有过度牺牲利润奔跑。

## 为什么早退率仍高

| 发现 | 数据 | 判断 |
| --- | --- | --- |
| 早退来源 | 49 笔早退全部是 warning_confirm_volume | swing96 解决大止损，不解决量能 warning 误报 |
| MFI divergence | 49 笔早退里 45 笔包含 MFI 背离 | 强趋势中 MFI 往往先背离，但价格还会继续走 |
| 确认滞后 | warning 到 EMA21 confirm 平均 20.7 根 K，中位 18 根 K | 退出发生在正常回踩 EMA21 后，而不是趋势真正反转 |
| 诊断口径 | 早退单中位捕获率 52.61%；严重早退仅 6/79 | headline 早退率偏严，很多是趋势分段而非完全卖飞 |
| 再入场 | 49 笔早退里 28 笔在 32 根内同向再入场，18 笔下一单为正 | 策略靠再入场吃回一部分延续，但仍有滑点和切仓损耗 |
| V12.3 修复 | capture <35% 且后续 >=4ATR 的严重早退从 6 笔降到 0 | 低捕获率回踩确认不再允许平仓，继续交给下一次确认或 swing96 hard exit |

## 坏入场怎么降

| 方法 | 效果 | 取舍 |
| --- | --- | --- |
| entry_max_regime_age <=128 | 坏入场率 30.00% -> 14.29%；回撤 -37.53% -> -29.47% | 交易数 60 -> 28，样本更少但风险收益比最好 |
| entry_max_regime_age <=256 | 坏入场率 30.00% -> 20.51%；收益仍 +1512.85% | 回撤没有明显下降，适合中间口径 |
| entry_max_move48 <=12% | 收益 +1601.37%，回撤 -36.97%，stop_loss 4 -> 3 | 坏入场率只降到 28.81%，主要降低最差亏损而非坏单数量 |
| entry_max_dist_ema96 <=8% | 收益 +1616.40%，stop_loss 4 -> 3 | 坏入场率仍 30%，更像止损优化，不是坏入场优化 |
| entry_min_rvol96 >=1.2 | 收益 +1599.29%，但回撤扩大到 -39.93% | 不建议，量能门槛没有降低坏入场 |

## 分段趋势实验

| 分段方式 | 结果 | 判断 |
| --- | --- | --- |
| ADX18 分段 | 1Y +1092.86%，回撤 -31.85%，62 笔交易 | 能降低回撤，但收益明显低于 V12.4 高收益候选 |
| ADX22 分段 | 1Y +1061.37%，回撤 -31.95%，62 笔交易 | 更早退出，收益略低，胜率更高 |
| EMA55 分段 | 1Y +728.09%，回撤 -37.53% | 切碎趋势，收益损失大，不建议 |
| age128 入场过滤 | 1Y +1258.43%，回撤 -29.47%，28 笔交易 | 比分段退出更有效降低坏入场和回撤，但样本少 |
| age128 + ADX22 | 1Y +473.49%，回撤 -29.47%，28 笔交易 | 回撤没有优于 age128，收益大幅下降 |
| age128 + move48 + ADX18 | 1Y +432.32%，回撤 -20.39%，27 笔交易 | 回撤最低，但收益牺牲过大 |
| 结论 | 分段退出不是主优化方向 | 高回撤来自深回踩和坏入场；优先控制入场时机，其次用 swing96 hard exit |

## 诊断结果

| 候选 | 交易数 | 早退率 | 坏入场率 | 好捕获率 | 拿过头率 | 判断 |
| --- | --- | --- | --- | --- | --- | --- |
| V12.6 age128+ADX22 | 28 | 71.43% | 14.29% | 7.14% | 0.00% | 坏入场不变，收益远低于 age128 单独，说明分段退出切掉了主要利润段 |
| V12.6 age128+move48+ADX18 | 27 | 66.67% | 18.52% | 3.70% | 3.70% | 回撤最低，但收益损失过大，只适合作极端稳健参考 |
| V12.5 segment ADX18 | 62 | 62.90% | 22.58% | 1.61% | 4.84% | 分段退出能降回撤，但收益低于 V12.4；更像稳健分支 |
| V12.5 segment EMA55 | 62 | 58.06% | 29.03% | 1.61% | 0.00% | EMA55 分段切得太碎，利润奔跑明显受损 |
| V12.4 age128 | 28 | 64.29% | 14.29% | 3.57% | 7.14% | 坏入场最低、回撤明显改善，但交易数变少，需要警惕样本不足 |
| V12.4 move48_12 | 59 | 52.54% | 28.81% | 5.08% | 5.08% | 收益和回撤 Pareto 最好，但坏入场只小幅下降 |
| V12.3 cap35 | 60 | 51.67% | 30.00% | 5.00% | 5.00% | 严重早退 0 笔；普通早退仍有，但不再是低捕获率卖飞 |
| V12.2 no MFI div | 65 | 52.31% | 26.15% | 4.62% | 12.31% | 当前最强候选：去掉 MFI 背离后少切趋势，收益和持仓时长都提高 |
| V12.2 blowoff only | 63 | 50.79% | 30.16% | 3.17% | 11.11% | 早退率最低，但 Sharpe 低于 no_mfi_div，说明 effort-fail 仍有辅助价值 |
| V12.1 swing96 | 79 | 62.03% | 18.99% | 2.53% | 10.13% | 硬退出减少大止损，但不解决 volume warning 在趋势中段误报 |
| V12 高收益 | 76 | 65.79% | 17.11% | 2.63% | 10.53% | 高收益来自更宽松持有，但止损次数升到 11，回撤显著放大 |
| V12 收益/回撤折中 | 50 | 60.00% | 30.00% | 4.00% | 2.00% | 风险接近 V6，但 43/50 笔仍由 ADX fallback 结束，状态机贡献有限 |
| V12 慢 EMA 确认 | 49 | 57.14% | 30.61% | 4.08% | 4.08% | 路径几乎退回 V6，只多了少数 warning_confirm_volume 退出 |

### V12 状态机规则

| 模块 | 规则 |
| --- | --- |
| 入场 | 沿用 V6：EMA96/384 regime 方向 + ADX/成交量/1h 确认；按 ATR672 动态 max 3x 仓位 |
| warning | MFE 达到 2ATR 或 4ATR 后才监听量能衰竭或高周期震荡信号；warning 不直接平仓 |
| confirm | warning 后等待价格结构确认：EMA21/55/96、Donchian 24/48/96、ATR trail 5/7.5/10ATR |
| fallback | 可选 ADX28 < 18/22 连续 3 根退出；关闭 fallback 时收益提高但回撤明显放大 |
| reentry | 测试 none、breakout48、breakout96；同一 EMA regime 内可要求新高/新低突破再进 |

## 下一步判断

> **不要直接把 V12 high return 当实盘候选**
> V12 high return 证明“先 warning、再 confirm”方向能让利润跑更久，但回撤过大。下一版应该优先重写趋势失效定义：用 swing structure 或高低点序列确认趋势破坏，而不是继续围绕顶部指标加条件。

## 产物路径

| 文件 | 内容 |
| --- | --- |
| scripts/research_hype_state_machine_v12.py | V12 状态机回测与参数网格 |
| scripts/research_hype_state_machine_v12_hard_exit.py | V12.1 hard trend invalidation focused 测试 |
| reports/hype_state_machine_v12.json | V12 结构化结果报告 |
| reports/hype_state_machine_v12_ranking.csv | 完整参数排名 |
| reports/hype_state_machine_v12_hard_exit.json | V12.1 硬趋势失效测试报告 |
| reports/hype_state_machine_v12_hard_exit_ranking.csv | V12.1 hard-exit 参数排名 |
| reports/hype_state_machine_v12_1_early_exit_analysis.json | V12.1 早退原因拆解 |
| reports/hype_state_machine_v12_1_early_exit_detail.csv | V12.1 早退逐笔特征 |
| reports/hype_state_machine_v12_top_trades.csv | 最高收益 V12 逐笔交易 |
| reports/hype_state_machine_v12_diagnostics.json | V12 候选交易路径诊断 |
| reports/hype_state_machine_v12_diagnostics_detail.csv | V12 候选逐笔 MFE / MAE / 捕获率明细 |
| hype-ema-crossover-evolution.canvas.tsx | 主版本台账已补 V9-V12 |
