# 六币 15m 与 Funding 数据质量审计（2026-07-14）

## 结论

本家族的数据门禁通过，`blocker_count = 0`。六个币的 15m K 线均连续、无重复、无空值；funding 使用 Binance 官方月度历史归档补齐，并用 API 补到当前尾部。

## 截止时点与范围

- 抓取截止：`2026-07-14T11:30:00Z`
- BTC / ETH / SOL / BNB / TRX：从 `2024-07-14T00:00:00Z` 开始
- HYPE：从 Binance USD-M 上市后 `2025-05-30T10:30:00Z` 开始

## 15m K 线

| Symbol | Rows | First open | Last open | Missing | Duplicate | Null |
|---|---:|---|---|---:|---:|---:|
| BTCUSDT | 70,126 | 2024-07-14 00:00Z | 2026-07-14 11:15Z | 0 | 0 | 0 |
| ETHUSDT | 70,126 | 2024-07-14 00:00Z | 2026-07-14 11:15Z | 0 | 0 | 0 |
| SOLUSDT | 70,126 | 2024-07-14 00:00Z | 2026-07-14 11:15Z | 0 | 0 | 0 |
| BNBUSDT | 70,126 | 2024-07-14 00:00Z | 2026-07-14 11:15Z | 0 | 0 | 0 |
| TRXUSDT | 70,126 | 2024-07-14 00:00Z | 2026-07-14 11:15Z | 0 | 0 | 0 |
| HYPEUSDT | 39,364 | 2025-05-30 10:30Z | 2026-07-14 11:15Z | 0 | 0 | 0 |

## Funding

| Symbol | Rows | First time | Last time | Max gap | Blocker |
|---|---:|---|---|---:|---:|
| BTCUSDT | 2,192 | 2024-07-14 00:00Z | 2026-07-14 08:00Z | 8h | 0 |
| ETHUSDT | 2,192 | 2024-07-14 00:00Z | 2026-07-14 08:00Z | 8h | 0 |
| SOLUSDT | 2,192 | 2024-07-14 00:00Z | 2026-07-14 08:00Z | 8h | 0 |
| BNBUSDT | 2,192 | 2024-07-14 00:00Z | 2026-07-14 08:00Z | 8h | 0 |
| TRXUSDT | 2,192 | 2024-07-14 00:00Z | 2026-07-14 08:00Z | 8h | 0 |
| HYPEUSDT | 2,459 | 2025-05-30 12:00Z | 2026-07-14 08:00Z | 8h | 0 |

## 可复现证据

- 结构化报告：[`../artifacts/binance_six_asset_15m_data_quality_2026-07-14.json`](../artifacts/binance_six_asset_15m_data_quality_2026-07-14.json)
- 同步与审计脚本：[`../scripts/sync_and_audit_binance_six_asset_15m_data.py`](../scripts/sync_and_audit_binance_six_asset_15m_data.py)

报告记录了每个下载归档的 URL、SHA-256、raw/normalized 路径及行级质量统计。
