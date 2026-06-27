# Binance TradFi 原版 HYPE V35 批量诊断

> 迁移说明：本文由 legacy Cursor Canvas `tradfi-binance-v35-batch.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：Cross-asset / transfer legacy Canvas。

自动筛选 Binance USD-M `TRADIFI_PERPETUAL` USDT 合约，拉取 15m K线并运行原版 HYPE V35。去周末诊断表示原版 B0 只过滤周末开仓。

Source: Binance FAPI · since 2026-04-01 UTC · Result files in archive/reports/legacy/tradfi_binance_hype_v35_original_batch_final.*

> **主结论**
> 原版 V35 不能直接泛化到整个 TradFi 板块：B0 去周末诊断只有 23 个正收益、34 个跑赢买持。商品类整体最差；权益类分化明显，适合先作为候选池筛选，再逐个做 session-aware 和动态杠杆迁移。

## 批量概览

| 项目 | 结果 | 说明 |
| --- | --- | --- |
| TradFi USDT perpetual | 100 | Binance exchangeInfo: contractType=TRADIFI_PERPETUAL |
| B0 去周末诊断正收益 | 23 / 100 | 原版 HYPE V35，仅过滤周末开仓；不是主账正式版本 |
| B0 去周末诊断跑赢买持 | 34 / 100 | 同窗口 buy & hold 对照 |
| 周末过滤改善 | 34 个改善 / 9 个变差 | 去周末 - B0 平均 +1.45pct，中位 0.00pct |
| 历史 funding | 62 ok / 38 blocked | blocked 合约以空 funding 跑价格路径诊断 |
| 零交易 | 29 / 100 | 多为样本太短或 warmup 后信号不足 |

## 按类型汇总

| 类型 | 合约数 | 中位收益 | 平均收益 | 正收益数 | 跑赢B&H | 中位MDD |
| --- | --- | --- | --- | --- | --- | --- |
| COMMODITY | 8 | -16.45% | -16.36% | 0 | 2 | -22.40% |
| EQUITY | 87 | 0.00% | -2.28% | 21 | 31 | -5.41% |
| KR_EQUITY | 3 | -26.56% | -13.47% | 1 | 1 | -26.56% |
| PREMARKET | 2 | -1.12% | -1.12% | 1 | 0 | -8.46% |

## B0 去周末诊断 Top 15

| Symbol | 类型 | Bars | 去周末收益 | MDD | Trades | B&H | Edge vs B&H | Funding |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MUUSDT | EQUITY | 6892 | 25.47% | -27.44% | 34 | 127.19% | -101.72% | funding blocked |
| MRVLUSDT | EQUITY | 3241 | 24.40% | -27.26% | 19 | 47.39% | -22.99% | ok |
| EWYUSDT | EQUITY | 7521 | 24.28% | -6.26% | 11 | 39.83% | -15.55% | ok |
| WDCUSDT | EQUITY | 2187 | 20.80% | -15.95% | 14 | 35.15% | -14.35% | funding blocked |
| SOXLUSDT | EQUITY | 3241 | 19.55% | -19.76% | 10 | 12.08% | 7.47% | funding blocked |
| ARMUSDT | EQUITY | 2187 | 18.90% | -0.30% | 2 | 10.84% | 8.06% | ok |
| CRWVUSDT | EQUITY | 2955 | 17.77% | -0.49% | 2 | 9.62% | 8.15% | ok |
| DRAMUSDT | EQUITY | 2953 | 16.94% | -0.60% | 3 | 11.86% | 5.08% | ok |
| HYUNDAIUSDT | KR_EQUITY | 1556 | 15.79% | -2.63% | 3 | -5.19% | 20.98% | funding blocked |
| QNTXUSDT | EQUITY | 1920 | 14.08% | -14.60% | 6 | 11.08% | 3.00% | funding blocked |
| SNDKUSDT | EQUITY | 6891 | 11.42% | -35.88% | 24 | 117.12% | -105.70% | funding blocked |
| EWTUSDT | EQUITY | 1610 | 11.00% | -1.56% | 3 | 8.18% | 2.82% | ok |
| PLTRUSDT | EQUITY | 7521 | 10.85% | -9.99% | 12 | -10.03% | 20.88% | funding blocked |
| JPMUSDT | EQUITY | 2955 | 9.48% | -0.34% | 4 | 11.87% | -2.39% | ok |
| CRCLUSDT | EQUITY | 7521 | 7.41% | -33.45% | 27 | -21.70% | 29.11% | ok |

## B0 去周末诊断 Bottom 15

| Symbol | 类型 | Bars | 去周末收益 | MDD | Trades | B&H | Edge vs B&H | Funding |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| COINUSDT | EQUITY | 7521 | -51.18% | -53.15% | 20 | -20.94% | -30.24% | ok |
| CLUSDT | COMMODITY | 7485 | -39.55% | -49.19% | 15 | -11.63% | -27.92% | ok |
| RKLBUSDT | EQUITY | 2953 | -37.20% | -37.20% | 3 | -3.22% | -33.98% | funding blocked |
| AVGOUSDT | EQUITY | 5643 | -31.97% | -34.50% | 11 | -4.71% | -27.26% | ok |
| TSLAUSDT | EQUITY | 7521 | -31.40% | -31.23% | 18 | -1.61% | -29.79% | funding blocked |
| USARUSDT | EQUITY | 4107 | -29.96% | -35.39% | 8 | -4.08% | -25.88% | funding blocked |
| SAMSUNGUSDT | KR_EQUITY | 1557 | -29.65% | -29.65% | 3 | 16.10% | -45.75% | funding blocked |
| SKHYNIXUSDT | KR_EQUITY | 1557 | -26.56% | -26.56% | 2 | 28.38% | -54.94% | funding blocked |
| XPTUSDT | COMMODITY | 7521 | -24.95% | -24.95% | 18 | -18.32% | -6.63% | ok |
| BZUSDT | COMMODITY | 7485 | -23.05% | -31.58% | 20 | -11.22% | -11.83% | ok |
| INTCUSDT | EQUITY | 7521 | -22.93% | -37.37% | 31 | 85.18% | -108.11% | ok |
| MSTRUSDT | EQUITY | 7521 | -22.45% | -27.14% | 17 | -29.72% | 7.27% | funding blocked |
| NVDAUSDT | EQUITY | 7521 | -21.11% | -21.11% | 13 | 3.08% | -24.19% | funding blocked |
| LITEUSDT | EQUITY | 3243 | -18.74% | -36.05% | 11 | 5.15% | -23.89% | ok |
| FLNCUSDT | EQUITY | 2954 | -18.56% | -18.56% | 2 | -0.90% | -17.66% | ok |

## 产物路径

| 文件 | 内容 |
| --- | --- |
| scripts/research_tradfi_binance_original_v35_batch.py | 批量识别、下载、回测脚本 |
| scripts/fetch_binance_perp_symbol_data.py | Binance FAPI OHLCV/funding 抓取脚本，funding 已改为分窗 |
| archive/reports/legacy/tradfi_binance_hype_v35_original_batch_final.csv | 100 个合约 x B0/去周末诊断 的最终总表 |
| archive/reports/legacy/tradfi_binance_hype_v35_original_batch_final.json | 最终 JSON 结果 |
| archive/reports/legacy/tradfi_binance_hype_v35_original_batch_trades_final.csv | 全部交易明细 |
| research/tradfi-binance-v35-batch.md | Markdown 台账 |
