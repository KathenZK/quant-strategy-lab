# HYPE V30 K1 Open vs K1 Close

> 迁移说明：本文由 legacy Cursor Canvas `hype-v30-k1-open-close-comparison.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：HYPE-EMA-TB legacy Canvas。

比较 K0 close 信号确认后，直接在 K1 open 进场，和等 K1 close 再进场两种可执行口径。

Source: local Binance, Hyperliquid, OKX HYPE 15m data lake. Existing 8.5bps cost included; no extra slippage.

## 结论

| 项目 | 判断 | 证据 |
| --- | --- | --- |
| 核心结论 | K1 close 明显优于 K1 open | 三家交易所都是 K1 close 收益更高、回撤更低 |
| 原因 | K1 close 跳过了整根 K1 的插针风险 | K1 open 会从 K1 开盘开始承担 high/low 止损风险 |
| 但不是 +2188% 来源 | K1 close 仍远低于 legacy | Binance full K1 close +572.27%，不是 +2188% |
| 实盘口径 | K1 open 最自然；K1 close 可实盘但要定义成延迟收盘入场策略 | 收盘价成交需要滑点假设 |

## Full Window

| 交易所 | 入场口径 | 收益 | 最大回撤 | Sharpe | 交易数 | 胜率 | 止盈 / 指标 / timeout / 止损 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Binance | K1 open | +447.02% | -34.30% | 2.99 | 79 | 75.64% | 54 / 16 / 1 / 7 |
| Binance | K1 close | +572.27% | -25.54% | 3.48 | 80 | 77.22% | 57 / 16 / 0 / 6 |
| Hyperliquid | K1 open | +184.87% | -41.29% | 2.13 | 68 | 71.64% | 46 / 8 / 3 / 10 |
| Hyperliquid | K1 close | +360.06% | -28.60% | 3.06 | 66 | 73.85% | 46 / 11 / 3 / 5 |
| OKX | K1 open | +354.20% | -36.07% | 2.55 | 83 | 73.17% | 58 / 13 / 2 / 9 |
| OKX | K1 close | +614.35% | -29.49% | 3.47 | 82 | 75.31% | 57 / 16 / 2 / 6 |

## Aligned Window

| 交易所 | 入场口径 | 收益 | 最大回撤 | Sharpe | 交易数 | 胜率 | 止盈 / 指标 / timeout / 止损 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Binance | K1 open | +270.69% | -34.30% | 2.74 | 69 | 75.00% | 46 / 14 / 1 / 7 |
| Binance | K1 close | +485.15% | -25.54% | 3.84 | 69 | 77.94% | 50 / 13 / 0 / 5 |
| Hyperliquid | K1 open | +184.87% | -41.29% | 2.13 | 68 | 71.64% | 46 / 8 / 3 / 10 |
| Hyperliquid | K1 close | +360.06% | -28.60% | 3.06 | 66 | 73.85% | 46 / 11 / 3 / 5 |
| OKX | K1 open | +196.69% | -36.07% | 2.19 | 74 | 71.23% | 50 / 12 / 2 / 9 |
| OKX | K1 close | +361.35% | -29.49% | 3.19 | 72 | 73.24% | 49 / 14 / 2 / 6 |

## 口径定义

| 口径 | 定义 | 说明 |
| --- | --- | --- |
| K1 open | K0 close 出信号，K1 open 买入 | 最自然的已收盘信号实盘口径 |
| K1 close | K0 close 出信号，K1 整根不交易，K1 close 买入 | 可实盘，但本质是延迟收盘入场过滤 |
| 差异来源 | K1 open 承担 K1 high/low 止损路径；K1 close 不承担 | 所以 K1 close 更像跳过一根风险确认 K |
