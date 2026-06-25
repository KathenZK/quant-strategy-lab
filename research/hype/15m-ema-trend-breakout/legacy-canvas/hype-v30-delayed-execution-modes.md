# HYPE V30 Delayed Execution Modes

> 迁移说明：本文由 legacy Cursor Canvas `hype-v30-delayed-execution-modes.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：HYPE-EMA-TB legacy Canvas。

测试旧口径能否实盘化：信号在 bar[t] close 确认，刻意延迟 1 根 15m K，再分别用 close、next open、VWAP 近似成交。

Source: local Binance, Hyperliquid, OKX HYPE 15m data lake. Existing 8.5bps cost included; slip table adds extra 5bps per fill.

## 结论

| 项目 | 判断 | 证据 |
| --- | --- | --- |
| 核心结论 | 延迟 1 根 K 可以实盘化，但复现不了 +2188% | Binance 三种可执行延迟模式 full 大约 +267% 到 +606%，不是 legacy +2188% |
| 最接近稳定水平 | delay close / delay next open | Binance full +579.95% / +605.89%；HL +365.62% / +386.29%；OKX +622.08% / +621.28% |
| VWAP 口径 | 不稳定，且数据源差异明显 | Binance VWAP full +267.39%；HL/OKX 的 vwap 字段基本贴近 close |
| 滑点敏感性 | 5bps/side 后仍有收益，但明显缩水 | Binance delay close +579.95% -> +469.82%；HL +365.62% -> +259.31%；OKX +622.08% -> +430.30% |

## Full Window - No Extra Slippage

| 交易所 | 成交方式 | 收益 | 最大回撤 | Sharpe | 交易数 | 胜率 | 止盈 / 指标 / timeout / 止损 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Binance | delay close | +579.95% | -25.54% | 3.50 | 80 | 77.22% | 57 / 16 / 0 / 6 |
| Binance | delay next open | +605.89% | -25.57% | 3.49 | 80 | 77.22% | 57 / 15 / 1 / 6 |
| Binance | delay VWAP | +267.39% | -30.90% | 2.26 | 80 | 72.15% | 53 / 15 / 2 / 9 |
| Hyperliquid | delay close | +365.62% | -28.60% | 3.09 | 66 | 73.85% | 46 / 11 / 3 / 5 |
| Hyperliquid | delay next open | +386.29% | -28.57% | 3.18 | 66 | 73.85% | 47 / 11 / 2 / 5 |
| Hyperliquid | delay VWAP | +365.62% | -28.60% | 3.09 | 66 | 73.85% | 46 / 11 / 3 / 5 |
| OKX | delay close | +622.08% | -29.49% | 3.49 | 82 | 75.31% | 57 / 16 / 2 / 6 |
| OKX | delay next open | +621.28% | -29.46% | 3.50 | 82 | 75.31% | 57 / 16 / 2 / 6 |
| OKX | delay VWAP | +622.08% | -29.49% | 3.49 | 82 | 75.31% | 57 / 16 / 2 / 6 |

## Full Window - Extra 5bps/Side Slippage

| 交易所 | 成交方式 | 收益 | 最大回撤 | Sharpe | 交易数 | 胜率 | 止盈 / 指标 / timeout / 止损 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Binance | delay close | +469.82% | -25.86% | 3.21 | 80 | 75.95% | 56 / 17 / 0 / 6 |
| Binance | delay next open | +458.52% | -25.99% | 3.18 | 80 | 75.95% | 56 / 17 / 0 / 6 |
| Binance | delay VWAP | +360.41% | -30.01% | 2.65 | 79 | 74.36% | 54 / 15 / 2 / 7 |
| Hyperliquid | delay close | +259.31% | -28.74% | 2.63 | 66 | 72.31% | 45 / 11 / 3 / 6 |
| Hyperliquid | delay next open | +325.29% | -28.78% | 2.92 | 66 | 73.85% | 46 / 11 / 3 / 5 |
| Hyperliquid | delay VWAP | +254.07% | -28.81% | 2.61 | 66 | 72.31% | 45 / 11 / 3 / 6 |
| OKX | delay close | +430.30% | -30.14% | 3.02 | 82 | 72.84% | 56 / 18 / 1 / 6 |
| OKX | delay next open | +481.13% | -30.45% | 3.18 | 82 | 74.07% | 57 / 17 / 1 / 6 |
| OKX | delay VWAP | +419.37% | -30.48% | 2.99 | 82 | 72.84% | 56 / 18 / 1 / 6 |

## Aligned Window

| 交易所 | 成交方式 | 无额外滑点收益 | 无额外滑点回撤 | 5bps收益 | 5bps回撤 |
| --- | --- | --- | --- | --- | --- |
| Binance | delay close | +491.84% | -25.54% | +402.28% | -25.86% |
| Binance | delay next open | +515.10% | -25.57% | +394.50% | -25.99% |
| Binance | delay VWAP | +152.83% | -30.90% | +221.94% | -30.01% |
| Hyperliquid | delay close | +365.62% | -28.60% | +259.31% | -28.74% |
| Hyperliquid | delay next open | +386.29% | -28.57% | +325.29% | -28.78% |
| Hyperliquid | delay VWAP | +365.62% | -28.60% | +254.07% | -28.81% |
| OKX | delay close | +366.34% | -29.49% | +246.34% | -30.14% |
| OKX | delay next open | +365.75% | -29.46% | +280.20% | -30.45% |
| OKX | delay VWAP | +366.34% | -29.49% | +239.84% | -30.48% |

## 方法口径

| 模式 | 定义 | 说明 |
| --- | --- | --- |
| delay close | t close 出信号，跳过一根，t+1 close 成交 | 最接近旧口径的可实盘版本；收盘成交用 close 近似 |
| delay next open | t close 出信号，跳过一根，t+2 open 成交 | 更容易实盘复现；不用抢收盘价 |
| delay VWAP | t close 出信号，t+1 bar 用 vwap 近似成交 | 近似挂 VWAP/TWAP；同 bar 止盈止损不做排序假设，保护从下一根开始 |
| slip 5bps | 每次进出场额外 5bps 不利滑点 | 在原 8.5bps 成本之外叠加 |
