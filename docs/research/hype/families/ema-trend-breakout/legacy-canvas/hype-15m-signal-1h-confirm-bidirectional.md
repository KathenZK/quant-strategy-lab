# HYPE 15m Signal + 1h Confirm Bidirectional

> 迁移说明：本文由 legacy Cursor Canvas `hype-15m-signal-1h-confirm-bidirectional.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：HYPE-EMA-TB legacy Canvas。

测试 15m Keltner-ADX 信号 + 1h 方向确认的双向版本，空头单独使用更低目标波动和更短持仓时间。

Source: local Binance HYPE/USDT perp data lake, 2025-05-30 to 2026-05-26 UTC. Includes 8.5 bps trading cost and funding.

## 分窗口结果

| 窗口 | 策略收益 | 最大回撤 | 交易数 | 多/空 | Sharpe |
| --- | --- | --- | --- | --- | --- |
| 1w | +24.09% | -9.68% | 7 | 7 / 0 | 12.87 |
| 1m | +27.72% | -11.24% | 18 | 16 / 2 | 5.75 |
| 3m | +45.04% | -12.96% | 42 | 39 / 3 | 3.28 |
| 6m | +92.11% | -15.34% | 82 | 58 / 24 | 3.38 |
| 1y | +154.90% | -16.94% | 145 | 94 / 51 | 2.87 |

## 对比

| 版本 | 1y收益 | 1y回撤 | 交易数 | 结论 |
| --- | --- | --- | --- | --- |
| V2A 1h信号只做多 | +131.99% | -7.09% | 12 | 低频、低回撤主线 |
| 15m信号只做多 | +120.16% | -13.86% | 63 | 交易更多但回撤扩大 |
| 15m信号双向 | +154.90% | -16.94% | 145 | 收益更高，但回撤和交易噪音继续扩大 |

## 最佳双向参数

| 参数 | 值 |
| --- | --- |
| 多头入场 | 15m close > EMA96 + 2.0 * ATR192 |
| 多头过滤 | 15m EMA96 > EMA384 且上行；ADX28 >= 22；+DI > -DI；volume surge >= 0.5；1h EMA 确认 |
| 空头入场 | 15m close < EMA96 - 2.0 * ATR192 |
| 空头过滤 | 15m EMA96 < EMA384 且下行；ADX28 >= 26；-DI > +DI；volume surge >= 1.0；1h bear ADX/DI 确认 |
| 多头仓位 | min(1.5x, 0.012 / ATR672) |
| 空头仓位 | min(1.0x, 0.002 / ATR672) |
| 多头风控 | 6ATR 止损；6ATR 止盈；10ATR trailing；最长约 3 天 |
| 空头风控 | 2ATR 止损；4ATR 止盈；6ATR trailing；最长约 12 小时 |
| 冷却 | 8 根 15m，约 2 小时 |

## 结论

双向 15m 信号版确实提高了收益，1y 从只做多的 +120.16% 提到 +154.90%，但最大回撤也从 -13.86% 扩大到 -16.94%， 交易数增加到 145 次。它更适合作为高频进攻研究分支，不适合作为低回撤主线。
