# BTC V2E Keltner-ADX Transfer Test

> 迁移说明：本文由 legacy Cursor Canvas `btc-v2a-keltner-adx-backtest.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：Cross-asset / transfer legacy Canvas。

V2E 记录的是：将 HYPE 的 V2A Keltner-ADX 趋势突破参数原样迁移到 Binance BTC/USDT 永续 15m 数据上回测。

Source: local data lake + Binance Futures gap refresh. Costs include 8.5 bps round-trip trading cost and funding.

## BTC 分窗口结果

| 窗口 | 策略收益 | 最大回撤 | 交易数 | 买持收益 | 买持回撤 |
| --- | --- | --- | --- | --- | --- |
| 1w | +0.00% | +0.00% | 0 | -1.64% | -4.70% |
| 1m | -1.43% | -2.92% | 2 | -4.56% | -9.94% |
| 3m | +1.08% | -4.88% | 6 | +10.16% | -13.58% |
| 6m | -0.88% | -5.91% | 9 | -17.39% | -38.32% |
| 1y | -7.84% | -13.13% | 20 | -31.16% | -52.22% |

## 与 HYPE V2A 对比

| 标的 | 1y收益 | 1y回撤 | Sharpe | 交易数 | 最大仓位 |
| --- | --- | --- | --- | --- | --- |
| BTC V2E | -7.84% | -13.13% | -0.71 | 20 | 2.0x |
| HYPE V2A reference | +131.99% | -7.09% | 3.46 | 12 | 2.0x |

## 数据覆盖

| 数据 | 行数 | 开始 | 结束 |
| --- | --- | --- | --- |
| BTC 15m OHLCV | 36,210 | 2025-05-15 00:00 UTC | 2026-05-27 04:15 UTC |
| BTC funding | 494 non-zero funding rows | 2025-05-15 00:00 UTC | 2026-05-27 04:15 UTC |
| 补齐数据 | 1,137 OHLCV rows + 35 funding rows | 2026-05-15 08:15 UTC | 2026-05-27 04:15 UTC |

## 结论

V2E 直接迁移到 BTC 后没有泛化：1y 策略收益为 -7.84%，最大回撤 -13.13%，虽然好于同期 BTC 买持回撤， 但没有获得正收益。该机制在 BTC 上需要重新搜索 ADX、成交量、Keltner 宽度和风控参数，不能直接复用 HYPE 参数。
