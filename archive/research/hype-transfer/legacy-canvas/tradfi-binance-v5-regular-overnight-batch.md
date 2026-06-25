# TradFi V5 Regular+Overnight 批量诊断

> 迁移说明：本文由 legacy Cursor Canvas `tradfi-binance-v5-regular-overnight-batch.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：Cross-asset / transfer legacy Canvas。

全部 Binance TradFi USDT perpetual，使用 V5 多空动态杠杆，只允许 regular+overnight 时段开仓，并按 24/5 去掉周末。

Source: local Binance 15m data lake · funding not included to match existing V5 diagnostic · reports/tradfi_binance_v5_regular_overnight_batch.*

> **主结论**
> V5 regular+overnight 对 MU 很强，但不能直接推广到全 TradFi：100 个里只有 21 个正收益，35 个跑赢买持。它更适合筛候选，而不是统一上线。

## 批量概览

| 项目 | 结果 | 说明 |
| --- | --- | --- |
| 合约数 | 100 | Binance USD-M TRADIFI_PERPETUAL |
| 正收益 | 21 / 100 | V5 regular+overnight 去周末 |
| 跑赢买持 | 35 / 100 | 同窗口 buy & hold |
| 跑赢 B0 去周末诊断 | 34 / 100 | 对比上一轮原版 HYPE V35 去周末诊断 |
| 交易 | 378 已平仓 / 16 未平仓 | 收益包含 open_at_end mark-to-market |
| 入场分布 | 227 regular / 167 overnight | 只限制开仓时段，持仓继续全时段管理 |
| 横截面收益 | 中位 -0.08% / 平均 -3.83% | 中位 MDD -11.62%，active allocation 均值 2.44x |

## 按类型汇总

| 类型 | 合约数 | 中位收益 | 平均收益 | 正收益 | 跑赢B&H | 中位MDD | 已平仓 | 未平仓 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| COMMODITY | 8 | -10.84% | -14.12% | 2 | 3 | -24.86% | 86 | 0 |
| EQUITY | 87 | 0.00% | -2.88% | 18 | 31 | -10.88% | 286 | 13 |
| KR_EQUITY | 3 | -11.39% | -8.33% | 0 | 0 | -14.87% | 5 | 1 |
| PREMARKET | 2 | 2.97% | 2.97% | 1 | 1 | -9.12% | 1 | 2 |

## Top 10

| Symbol | 类型 | 收益 | MDD | 已平仓 | 未平仓 | B&H | Edge | 多头贡献 | 空头贡献 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MUUSDT | EQUITY | 165.00% | -22.52% | 13 | 0 | 127.19% | 37.81% | 112.75% | 0.00% |
| WDCUSDT | EQUITY | 40.13% | -11.65% | 5 | 0 | 35.15% | 4.98% | 38.15% | 0.00% |
| MRVLUSDT | EQUITY | 29.82% | -19.25% | 6 | 0 | 47.39% | -17.57% | 38.28% | -6.78% |
| CRWVUSDT | EQUITY | 15.87% | -11.59% | 1 | 1 | 9.62% | 6.25% | 12.40% | 0.00% |
| NBISUSDT | EQUITY | 12.28% | -9.12% | 1 | 1 | 7.50% | 4.78% | 12.41% | 0.00% |
| COPPERUSDT | COMMODITY | 10.55% | -13.64% | 13 | 0 | 4.95% | 5.60% | 4.19% | 14.17% |
| DELLUSDT | EQUITY | 10.07% | -8.91% | 0 | 1 | 17.16% | -7.09% | 0.00% | 0.00% |
| OPENAIUSDT | PREMARKET | 9.06% | -8.30% | 1 | 1 | 4.98% | 4.08% | 12.35% | 0.00% |
| DRAMUSDT | EQUITY | 6.59% | -27.31% | 2 | 1 | 11.86% | -5.27% | 0.00% | 1.06% |
| CRCLUSDT | EQUITY | 6.39% | -33.47% | 13 | 0 | -21.70% | 28.09% | 36.30% | -15.25% |

## Bottom 10

| Symbol | 类型 | 收益 | MDD | 已平仓 | 未平仓 | B&H | Edge | 多头贡献 | 空头贡献 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| COINUSDT | EQUITY | -52.62% | -55.16% | 11 | 1 | -20.94% | -31.68% | -52.88% | -11.43% |
| CLUSDT | COMMODITY | -43.38% | -52.76% | 8 | 0 | -11.63% | -31.75% | -13.06% | -36.57% |
| TSLAUSDT | EQUITY | -34.30% | -34.52% | 13 | 0 | -1.61% | -32.69% | -33.53% | 0.92% |
| BZUSDT | COMMODITY | -31.45% | -48.16% | 11 | 0 | -11.22% | -20.23% | -1.52% | -27.23% |
| CBRSUSDT | EQUITY | -30.77% | -33.06% | 3 | 0 | 3.52% | -34.29% | -22.67% | -11.34% |
| HOODUSDT | EQUITY | -29.61% | -40.65% | 12 | 1 | 16.16% | -45.77% | -8.82% | -10.98% |
| NVDAUSDT | EQUITY | -27.39% | -27.92% | 9 | 0 | 3.08% | -30.47% | -19.02% | -6.38% |
| TSMUSDT | EQUITY | -26.38% | -37.02% | 9 | 0 | 15.81% | -42.19% | -21.57% | -1.42% |
| MSTRUSDT | EQUITY | -23.37% | -36.62% | 10 | 0 | -29.72% | 6.35% | -28.99% | 13.86% |
| BABAUSDT | EQUITY | -23.35% | -30.13% | 5 | 0 | -25.43% | 2.08% | -15.47% | -6.12% |

## 产物路径

| 文件 | 内容 |
| --- | --- |
| scripts/research_tradfi_binance_v5_regular_overnight_batch.py | V5 regular+overnight 全 TradFi 批量脚本 |
| reports/tradfi_binance_v5_regular_overnight_batch.csv | 100 个合约最终总表 |
| reports/tradfi_binance_v5_regular_overnight_batch.json | JSON 摘要和配置 |
| reports/tradfi_binance_v5_regular_overnight_batch_trades.csv | 逐笔交易，含 open_at_end |
| research/tradfi-binance-v5-regular-overnight-batch.md | Markdown 台账 |
