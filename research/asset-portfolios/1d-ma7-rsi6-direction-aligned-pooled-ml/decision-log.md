# Decision Log

## 2026-08-10

决定在 BTC 单资产 P1–P3 未通过后建立独立五资产 pooled 家族：不再微调 BTC edge，以统一 development cutoff、防同期侧漏、方向对齐 MA7/K 线/RSI6 特征和 leave-one-asset-out 评估增加可辨识样本。证据：[P0 数据与特征合同](specs/binance-1d-ma7-rsi6-dapml-p0-data-feature-contract-2026-08-10.md)。

## 2026-08-10

首次 direct 审计发现 SOL 在 2022 年极端行情期间存在实际 `2h` funding，故在生成标签前撤销固定 `8h` 假设，改用官方实际 funding 事件和 `1h` mark bucket；相邻事件超过 `8h` 才视为缺失 blocker。证据：[P0 数据与特征合同](specs/binance-1d-ma7-rsi6-dapml-p0-data-feature-contract-2026-08-10.md)。

## 2026-08-10

P0 数据质量与 `2,091` 个 development 事件容量通过，冻结 Logistic-EV aligned 主候选、raw 对照、LightGBM 诊断、temporal OOS 与 leave-one-asset + time OOS 的 P1 合同；共同 sealed year 继续不揭示。证据：[P0 审计](diagnostics/binance-1d-ma7-rsi6-dapml-p0-data-capacity-2026-08-10.md) · [P1 合同](specs/binance-1d-ma7-rsi6-dapml-p1-pooled-development-contract-2026-08-10.md)。

## 2026-08-10

P1 三类门禁全部失败：主 Logistic-EV 没有可冻结路线，方向对齐不优于 raw，LightGBM 也缺少时间稳定与正向排序；决定不揭示共同 sealed year，并停止在同一标签/特征/edge 上微调。证据：[P1 诊断](diagnostics/binance-1d-ma7-rsi6-dapml-p1-pooled-development-2026-08-10.md)。
