# HYPE V30 Full Legacy Close Sensitivity

> 迁移说明：本文由 legacy Cursor Canvas `hype-v30-full-legacy-close-sensitivity.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：HYPE-EMA-TB legacy Canvas。

按完整 legacy delayed-close 事件循环复跑：入场、退出、冷却都使用 shift(1) 信号并在当前 15m close 附近执行。

Source: local Binance, Hyperliquid, OKX HYPE 15m data lake. Existing 8.5bps cost included; slippage rows add adverse close fill slippage.

## 结论

| 项目 | 判断 | 证据 |
| --- | --- | --- |
| 核心结论 | 完整 delayed-close 事件循环可以接近 legacy 高收益 | Binance full 0bps 为 +1917.48%，明显高于单纯 K1 close 的 +572.27% |
| 但对成交价很敏感 | 加 5bps/10bps 不利滑点后大幅缩水 | Binance full +1917.48% -> +1293.27% -> +671.62% |
| 跨交易所 | HL/OKX 没有 Binance 那么夸张 | HL 0bps +517.37%，OKX 0bps +569.26% |
| 上线含义 | 规则可实盘，但必须命名为 delayed-close execution | 不能假设精确 close 成交；需要收盘前 IOC limit / market 的滑点模型 |

## Full Window

| 交易所 | 成交模型 | 收益 | 最大回撤 | Sharpe | 交易数 | 胜率 | 止盈 / 指标 / timeout / 止损 | 跳过 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Binance | close 0bps | +1917.48% | -16.81% | 5.17 | 82 | 83.95% | 64 / 14 / 1 / 2 | 0 |
| Binance | close 5bps | +1293.27% | -21.59% | 4.55 | 82 | 81.48% | 62 / 15 / 1 / 3 | 0 |
| Binance | close 10bps | +671.62% | -26.28% | 3.49 | 81 | 77.50% | 58 / 16 / 2 / 4 | 0 |
| Hyperliquid | close 0bps | +517.37% | -24.60% | 3.57 | 67 | 77.27% | 49 / 10 / 3 / 4 | 0 |
| Hyperliquid | close 5bps | +328.66% | -25.02% | 2.82 | 67 | 74.24% | 47 / 10 / 4 / 5 | 0 |
| Hyperliquid | close 10bps | +314.12% | -25.45% | 2.75 | 66 | 73.85% | 46 / 11 / 4 / 4 | 0 |
| OKX | close 0bps | +569.26% | -29.26% | 3.17 | 85 | 75.00% | 60 / 14 / 3 / 7 | 0 |
| OKX | close 5bps | +444.99% | -29.67% | 2.89 | 85 | 73.81% | 60 / 15 / 2 / 7 | 0 |
| OKX | close 10bps | +283.56% | -33.67% | 2.44 | 83 | 71.95% | 57 / 17 / 1 / 7 | 0 |

## Aligned Window

| 交易所 | 成交模型 | 收益 | 最大回撤 | Sharpe | 交易数 | 胜率 | 止盈 / 指标 / timeout / 止损 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Binance | close 0bps | +1267.92% | -16.81% | 5.29 | 71 | 84.29% | 56 / 11 / 1 / 2 |
| Binance | close 5bps | +859.85% | -21.59% | 4.59 | 71 | 81.43% | 54 / 12 / 1 / 3 |
| Binance | close 10bps | +445.01% | -26.28% | 3.43 | 70 | 76.81% | 50 / 13 / 2 / 4 |
| Hyperliquid | close 0bps | +517.37% | -24.60% | 3.57 | 67 | 77.27% | 49 / 10 / 3 / 4 |
| Hyperliquid | close 5bps | +328.66% | -25.02% | 2.82 | 67 | 74.24% | 47 / 10 / 4 / 5 |
| Hyperliquid | close 10bps | +314.12% | -25.45% | 2.75 | 66 | 73.85% | 46 / 11 / 4 / 4 |
| OKX | close 0bps | +408.23% | -29.26% | 3.18 | 75 | 74.32% | 52 / 13 / 3 / 6 |
| OKX | close 5bps | +318.91% | -29.67% | 2.87 | 75 | 72.97% | 52 / 14 / 2 / 6 |
| OKX | close 10bps | +198.43% | -33.67% | 2.36 | 73 | 70.83% | 49 / 16 / 1 / 6 |

## IOC Limit Skip Model

| 交易所 | 模型 | 收益 | 最大回撤 | Sharpe | 交易数 | 跳过入场 |
| --- | --- | --- | --- | --- | --- | --- |
| Binance | IOC 5bps skip | +444.91% | -30.77% | 3.03 | 75 | 60 |
| Binance | IOC 10bps skip | +417.46% | -30.77% | 2.89 | 75 | 50 |
| Hyperliquid | IOC 5bps skip | +310.53% | -19.12% | 3.09 | 60 | 59 |
| Hyperliquid | IOC 10bps skip | +295.84% | -23.11% | 2.87 | 65 | 47 |
| OKX | IOC 5bps skip | +810.45% | -32.31% | 3.76 | 78 | 76 |
| OKX | IOC 10bps skip | +507.20% | -32.31% | 3.11 | 78 | 63 |

## 方法说明

| 模型 | 定义 | 说明 |
| --- | --- | --- |
| close 0bps | 当前 K 收盘价精确成交 | 理论上最乐观，不含收盘滑点 |
| close 5bps / 10bps | 每次入场和平仓都加不利滑点 | 更贴近收盘前市价/IOC 的现实成本 |
| IOC skip | 若当前 close 相对上一根 close 已朝入场方向滑出阈值，则跳过 | 粗略模拟限价未成交；不是订单簿级精确模型 |
