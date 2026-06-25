# TradFi V5 Regular-Only 批量诊断

> 迁移说明：本文由 legacy Cursor Canvas `tradfi-binance-v5-regular-batch.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：Cross-asset / transfer legacy Canvas。

全部 Binance TradFi USDT perpetual，使用 V5 多空动态杠杆，只允许美股 regular session 开仓。

Source: local Binance 15m data lake · funding not included · reports/tradfi_binance_v5_regular_batch.*

> **主结论**
> regular-only 全板块更稳：正收益和跑赢买持略多，平均收益和中位 MDD 都优于 regular+overnight。但 MU、WDC、MRVL 这类标的夜盘贡献很大，不能一刀切关闭 overnight。

## 批量概览

| 项目 | 结果 | 说明 |
| --- | --- | --- |
| 正收益 | 22 / 100 | regular+overnight 为 21 / 100 |
| 跑赢买持 | 36 / 100 | regular+overnight 为 35 / 100 |
| 交易 | 248 已平仓 / 12 未平仓 | regular+overnight 为 378 / 16 |
| 入场 | 260 regular / 0 overnight | 只限制开仓，持仓继续全时段管理 |
| 横截面收益 | 中位 0.00% / 平均 -3.07% | regular+overnight 为 -0.08% / -3.83% |
| 横截面回撤 | 中位 MDD -9.04% | regular+overnight 为 -11.62% |
| 相对 overnight | 38 更好 / 19 更差 / 43 无差异 | 平均多 +0.76pct，中位 0.00pct |

## 按类型汇总

| 类型 | 合约数 | 中位收益 | 平均收益 | 正收益 | 跑赢B&H | 中位MDD | 已平仓 | 未平仓 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| COMMODITY | 8 | -13.22% | -13.66% | 1 | 3 | -22.21% | 46 | 0 |
| EQUITY | 87 | 0.00% | -2.10% | 20 | 31 | -8.10% | 199 | 10 |
| KR_EQUITY | 3 | -7.53% | -6.31% | 0 | 1 | -8.97% | 2 | 0 |
| PREMARKET | 2 | 1.98% | 1.98% | 1 | 1 | -8.24% | 1 | 2 |

## Top 10

| Symbol | 类型 | 收益 | MDD | 已平仓 | 未平仓 | B&H | Edge |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MUUSDT | EQUITY | 72.25% | -15.47% | 9 | 0 | 127.19% | -54.94% |
| CRCLUSDT | EQUITY | 17.54% | -26.10% | 8 | 0 | -21.70% | 39.24% |
| MRVLUSDT | EQUITY | 16.54% | -13.28% | 3 | 0 | 47.39% | -30.85% |
| INTCUSDT | EQUITY | 13.99% | -20.33% | 10 | 0 | 85.18% | -71.19% |
| NBISUSDT | EQUITY | 12.28% | -9.12% | 1 | 1 | 7.50% | 4.78% |
| FLNCUSDT | EQUITY | 12.24% | -6.22% | 1 | 0 | -0.90% | 13.14% |
| ORCLUSDT | EQUITY | 11.02% | -14.63% | 1 | 0 | -20.02% | 31.04% |
| WDCUSDT | EQUITY | 11.01% | -11.65% | 3 | 0 | 35.15% | -24.14% |
| OPENAIUSDT | PREMARKET | 9.72% | -7.74% | 1 | 1 | 4.98% | 4.74% |
| AAPLUSDT | EQUITY | 8.61% | -4.74% | 3 | 0 | 9.79% | -1.18% |

## Bottom 10

| Symbol | 类型 | 收益 | MDD | 已平仓 | 未平仓 | B&H | Edge |
| --- | --- | --- | --- | --- | --- | --- | --- |
| COINUSDT | EQUITY | -38.41% | -41.84% | 6 | 1 | -20.94% | -17.47% |
| HOODUSDT | EQUITY | -28.96% | -33.32% | 8 | 1 | 16.16% | -45.12% |
| BABAUSDT | EQUITY | -28.95% | -30.20% | 4 | 0 | -25.43% | -3.52% |
| CLUSDT | COMMODITY | -28.40% | -35.85% | 5 | 0 | -11.63% | -16.77% |
| TSMUSDT | EQUITY | -25.58% | -30.49% | 7 | 0 | 15.81% | -41.39% |
| TSLAUSDT | EQUITY | -23.26% | -23.52% | 11 | 0 | -1.61% | -21.65% |
| XAGUSDT | COMMODITY | -22.77% | -25.88% | 9 | 0 | -16.85% | -5.92% |
| QCOMUSDT | EQUITY | -22.49% | -29.83% | 2 | 0 | -8.46% | -14.03% |
| CBRSUSDT | EQUITY | -22.02% | -28.29% | 2 | 0 | 3.52% | -25.54% |
| SNDKUSDT | EQUITY | -21.93% | -39.33% | 10 | 0 | 117.12% | -139.05% |

## regular-only 改善最多

| Symbol | Regular | Reg+Overnight | 差值 | Regular MDD | Reg+ON MDD |
| --- | --- | --- | --- | --- | --- |
| FLNCUSDT | 12.24% | -12.01% | 24.25pct | -6.22% | -16.18% |
| EWYUSDT | 3.82% | -19.08% | 22.90pct | -20.01% | -32.61% |
| INTCUSDT | 13.99% | -7.87% | 21.86pct | -20.33% | -26.99% |
| NVDAUSDT | -6.68% | -27.39% | 20.71pct | -11.49% | -27.92% |
| CLUSDT | -28.40% | -43.38% | 14.98pct | -35.85% | -52.76% |

## overnight 帮助最多

| Symbol | Regular | Reg+Overnight | 差值 | Regular MDD | Reg+ON MDD |
| --- | --- | --- | --- | --- | --- |
| MUUSDT | 72.25% | 165.00% | -92.75pct | -15.47% | -22.52% |
| WDCUSDT | 11.01% | 40.13% | -29.12pct | -11.65% | -11.65% |
| XAGUSDT | -22.77% | -6.92% | -15.85pct | -25.88% | -18.29% |
| MRVLUSDT | 16.54% | 29.82% | -13.28pct | -13.28% | -19.25% |
| CRWVUSDT | 3.46% | 15.87% | -12.41pct | -11.59% | -11.59% |

## 产物路径

| 文件 | 内容 |
| --- | --- |
| scripts/research_tradfi_binance_v5_regular_batch.py | V5 regular-only 批量脚本 |
| reports/tradfi_binance_v5_regular_batch.csv | 100 个合约 regular-only 总表 |
| reports/tradfi_binance_v5_regular_batch.json | JSON 摘要和配置 |
| reports/tradfi_binance_v5_regular_batch_trades.csv | 逐笔交易 |
| research/tradfi-binance-v5-regular-batch.md | Markdown 台账 |
