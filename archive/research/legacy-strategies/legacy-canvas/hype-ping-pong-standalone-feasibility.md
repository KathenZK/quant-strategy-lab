# HYPE Ping-Pong 策略独立性分析

> 迁移说明：本文由 legacy Cursor Canvas `hype-ping-pong-standalone-feasibility.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：Legacy strategy Canvas。

目标：判断 V35 indicator_exit 后反手的 ping-pong 行为，是否能脱离 V35 主策略单独成为一个新策略。

数据：Binance HYPE/USDT:USDT 15m · 2025-05-30 至 2026-06-01 03:00 UTC · 含 8.5bps 成本与 funding。

## Full Overlay vs Satellite-Only

| 模型 | 规则 | 收益 | 最大回撤 | Sharpe | 交易数 | 判断 |
| --- | --- | --- | --- | --- | --- | --- |
| V35A full overlay | V35 原始仓位 indicator_exit 后同 open 反手一次；反手仓退出后不再继续反手 | +7378.17% | -23.49% | 5.05 | 109 | V35 + 9 笔反手增强 |
| V35A satellite-only | 不交易 V35 主仓，只在虚拟 V35 indicator_exit 后交易一次反手仓 | +13.75% | -5.07% | 1.40 | 9 | 单独 alpha 很弱，样本极少 |
| V35B full overlay | V35 任意仓位 indicator_exit 后下一根 open 反手，允许链式 ping-pong | +8113.74% | -24.34% | 5.04 | 145 | 高收益，但交易数和路径依赖上升 |
| V35B satellite-only | 不交易 V35 主仓，只交易虚拟 V35 indicator_exit 后的链式反手仓 | +18.60% | -21.26% | 0.82 | 46 | 收益/回撤比差，不适合作独立主策略 |

## V35B Chain 贡献分解

| 链条 | 交易数 | 链条复合PnL | 退出路径 | 说明 |
| --- | --- | --- | --- | --- |
| 2026-02-03 | 1 | +8.78% | take_profit | 单笔反手空单直接止盈，是 V35A/V35B 的关键贡献 |
| 2025-11-26 ~ 11-28 | 6 | +8.12% | 5 次 indicator + 1 次 TP | 链式 ping-pong 最成功案例之一 |
| 2026-05-24 ~ 05-26 | 3 | +7.59% | 2 次 indicator + 1 次 TP | 另一个关键贡献链 |
| 2025-07-14 | 5 | +6.09% | 4 次 indicator + 1 次 TP | 短时间多次翻转后止盈 |
| 2025-08-27 | 3 | +5.51% | 2 次 indicator + 1 次 TP | 正贡献 |
| 2025-06-30 ~ 07-01 | 3 | +4.72% | 2 次 indicator + 1 次 TP | 正贡献 |
| 2025-12-06 ~ 12-07 | 24 | -8.35% | 23 次 indicator + 1 次 TP | 典型 ping-pong 噪音链，手续费和小亏吞噬收益 |
| 2025-08-23 ~ 08-24 | 1 | -13.04% | stop_loss | 链式策略的尾部亏损 |

## V35A No-Chain 的 9 笔反手仓

| 日期 | 方向 | 退出 | PnL | 说明 |
| --- | --- | --- | --- | --- |
| 2026-02-03 | short | take_profit | +8.78% | 关键贡献 |
| 2026-05-24 | short | take_profit | +8.65% | 关键贡献 |
| 2025-08-23 | short | indicator_exit | +1.97% | 小赚 |
| 2025-11-27 | short | indicator_exit | +1.03% | 小赚 |
| 2025-07-14 | short | indicator_exit | +0.09% | 基本持平 |
| 2025-12-06 | long | indicator_exit | -0.31% | 小亏 |
| 2025-11-26 | short | indicator_exit | -0.63% | 小亏 |
| 2025-06-30 | short | indicator_exit | -2.02% | 亏损 |
| 2025-08-27 | short | indicator_exit | -3.81% | 最大单笔亏损 |

## 结论

> **提示**
> Ping-pong 不是一个足够强的独立主策略；它更像 V35 indicator_exit 后的 overlay。V35A/V35B 可以继续作为影子观察分支，但不建议单独实盘。

| 问题 | 结论 | 依据 |
| --- | --- | --- |
| 能不能写成独立策略 | 可以写，但不建议作为独立主策略 | satellite-only 只有 +13.75% / +18.60%，交易样本 9 或 46 笔，收益回撤比远弱于 V35。 |
| 为什么 full overlay 看起来强 | 它是 V35 的退出后增强层 | 触发点来自 V35 原始仓位的 indicator_exit；没有 V35 主仓提供上下文，ping-pong 本身不够强。 |
| 最大问题 | 样本少 + ping-pong 噪音链 | V35A 只有 9 个 seed；V35B 有一条 24 笔链最终 -8.35%，说明链式反手会产生无效震荡交易。 |
| 更合理落地 | 做 V35 overlay / 影子分支 | 先在 live-dry-run 里记录 indicator_exit 后 no-chain same-open 与 chain next-open 两套影子收益，不直接动主仓。 |
| 正式编号建议 | V35A / V35B 保持观察 | V35A 较干净；V35B 收益高但路径依赖更强。都不应替代 V35 主线。 |
