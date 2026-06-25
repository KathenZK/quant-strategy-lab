# HYPE V35 指标退出反手消融

> 迁移说明：本文由 legacy Cursor Canvas `hype-v35-indicator-exit-reverse-ablation.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：HYPE-EMA-TB legacy Canvas。

测试假设：V35 由 ADX 指标退出时，原方向趋势可能走坏，能否直接做反向单。注意这里不是止损反手，而是 indicator_exit 反手。

数据：Binance HYPE/USDT:USDT 15m · 2025-05-30 至 2026-06-01 03:00 UTC · V35 其余参数不变 · 含 8.5bps 成本与 funding。

## Full Window 对比

| 版本 | 规则 | 收益 | 最大回撤 | Sharpe | 交易数 | 胜率 | 退出结构 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| V35 base | 指标退出后空仓，等待正常 V35 信号 | +6474.19% | -23.49% | 4.94 | 100 | 80.00% | TP77 / 指标9 / SL14 |
| No-chain same open reverse | 仅原始 V35 仓位 indicator_exit 后，同一 open 平仓并反手；反手仓退出后不再继续反手 | +7378.17% | -23.49% | 5.05 | 109 | 78.90% | TP79 / 指标16 / SL14 |
| No-chain next open reverse | 仅原始 V35 仓位 indicator_exit 后，下一根 open 反手；反手仓退出后不再继续反手 | +6002.87% | -25.03% | 4.82 | 109 | 78.90% | TP78 / 指标16 / SL15 |
| Chain same open reverse | 每次 indicator_exit 都继续反手，允许 ping-pong 链 | +6706.78% | -25.26% | 4.84 | 160 | 65.00% | TP85 / 指标60 / SL15 |
| Chain next open reverse | 每次 indicator_exit 后下一根 open 继续反手，允许 ping-pong 链 | +8113.74% | -24.34% | 5.04 | 145 | 71.03% | TP84 / 指标46 / SL15 |

## No-chain 固定窗口

| 窗口 | V35收益 | V35回撤 | same-open收益 | same-open回撤 | next-open收益 | next-open回撤 |
| --- | --- | --- | --- | --- | --- | --- |
| 1m | +81.12% | -22.16% | +96.76% | -22.16% | +84.13% | -22.16% |
| 3m | +289.16% | -22.16% | +322.76% | -22.16% | +295.63% | -22.16% |
| 6m | +1613.80% | -22.16% | +1918.77% | -22.16% | +1788.42% | -22.16% |
| Full | +6474.19% | -23.49% | +7378.17% | -23.49% | +6002.87% | -25.03% |

## 反手仓自身归因

| 口径 | 反手仓数 | 反手仓累计PnL | 反手仓胜率 | 退出结构 | 判断 |
| --- | --- | --- | --- | --- | --- |
| No-chain same open | 9 | +17.03% | 66.7% | TP2 / 指标7 / SL0 | 两笔反手空单打到 5ATR 止盈，是收益提升来源 |
| No-chain next open | 9 | -3.13% | 66.7% | TP1 / 指标7 / SL1 | 延迟一根 K 后少吃到两笔反转收益，还多一笔止损 |
| Chain same open | 60 | +32.00% | 40.0% | TP8 / 指标51 / SL1 | 交易数暴增，ping-pong 噪音多，回撤更深 |
| Chain next open | 46 | +38.26% | 50.0% | TP7 / 指标38 / SL1 | 收益最高但规则复杂、交易数暴增且回撤略差 |

## No-chain same-open 的 9 笔反手仓

| 日期 | 方向 | 退出 | PnL | 备注 |
| --- | --- | --- | --- | --- |
| 2025-06-30 | short | indicator_exit | -1.65% | 小亏 |
| 2025-07-14 | short | indicator_exit | +0.60% | 小赚 |
| 2025-08-23 | short | indicator_exit | +2.41% | 小赚 |
| 2025-08-27 | short | indicator_exit | -3.39% | 亏损 |
| 2025-11-26 | short | indicator_exit | -0.35% | 小亏 |
| 2025-11-27 | short | indicator_exit | +1.33% | 小赚 |
| 2025-12-06 | long | indicator_exit | +0.08% | 基本持平 |
| 2026-02-03 | short | take_profit | +9.00% | 关键贡献 |
| 2026-05-24 | short | take_profit | +9.00% | 关键贡献 |

## 结论

> **提示**
> 指标退出反手和止损反手不同：no-chain same-open 版本在样本内确实提升收益且不增加最大回撤。但样本只有 9 笔，收益提升集中在 2 笔反手空单止盈，不能直接当新主策略。

| 问题 | 结论 | 依据 |
| --- | --- | --- |
| 是否有效 | no-chain same-open 有效 | 收益 +7378% 高于 V35，最大回撤不变，Sharpe 提升到 5.05。 |
| 为什么不是所有反手都好 | 不能允许无限链式反手 | chain 版本交易数暴增到 145-160，胜率下降，回撤更深。 |
| 实盘可执行性 | same-open 需要谨慎实现 | 指标退出本来就在下一根 open 市价平仓；同一 open 平后反手可执行，但实际成交会有滑点。 |
| 样本风险 | 只有 9 个原始 indicator_exit 样本 | 收益提升主要来自 2 笔反手空单止盈，过拟合风险高，需要样本外 dry-run 观察。 |
| 建议 | 可列为 V35A 观察分支，不直接替换 V35 | 先在 paper/live-dry-run 里记录 indicator_exit 后反手信号，不急着实盘启用。 |
