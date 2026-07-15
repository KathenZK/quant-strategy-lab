# Binance 六币 1H 数据质量与 Funding 归档补齐（2026-07-14）

## 结论

`PASS`。六币共同研究窗口已统一为 `2025-05-30 10:00 UTC` 至 `2026-07-14 08:00 UTC`，每币 `9,839` 根已收盘 `1h` K 线；缺口、重复、关键空值、OHLC 违规、未收盘 K 线和 raw/normalized 对账误差均为 `0`。数据质量 blocker 总数为 `0`，可以进入 prefit 搜索。

锁定 OOS 固定为 `[2026-04-14 09:00 UTC, 2026-07-14 09:00 UTC)`；prefit 为 `[2025-05-30 10:00 UTC, 2026-04-14 09:00 UTC)`。后续参数、交易臂、评分权重、抢占规则和候选筛选禁止读取 OOS 结果。

## 数据来源与补齐方式

- OHLCV：Binance USD-M Futures `GET /fapi/v1/klines`，六币共同窗口全量重拉，只保留 Binance server time 前已收盘 K 线，同时写入 `data/raw/ohlcv/` 与 `data/normalized/ohlcv/` 日分区。
- Funding 历史：Binance 官方历史归档 `data/futures/um/monthly/fundingRate/`，下载 `2025-05` 至 `2026-06` 共 `14` 个月/币，并逐文件验证官方 `.CHECKSUM`。
- Funding 补尾：Binance USD-M Futures `GET /fapi/v1/fundingRate`，覆盖最近 `45` 天；与月度归档重叠时按规范化结算时间去重，API 行优先。
- Funding 写入：原始解析结果进入 `data/raw/funding_rates/`，规范化结果进入 `data/normalized/funding_rates/`，同时更新现有研究兼容路径 `data/normalized/funding/.../funding.parquet`。
- 官方依据：[Binance Public Data](https://github.com/binance/binance-public-data) 说明 USD-M Futures 历史数据按 daily/monthly 归档并提供 checksum；归档文件来自 [Binance Data Collection](https://data.binance.vision/)。

## OHLCV 质量结果

| Symbol | Rows | UTC first | UTC last | Missing | Duplicate | Critical null | Raw/normalized mismatch | Blocker |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |
| BTCUSDT | 9,839 | 2025-05-30 10:00 | 2026-07-14 08:00 | 0 | 0 | 0 | 0 | 0 |
| ETHUSDT | 9,839 | 2025-05-30 10:00 | 2026-07-14 08:00 | 0 | 0 | 0 | 0 | 0 |
| SOLUSDT | 9,839 | 2025-05-30 10:00 | 2026-07-14 08:00 | 0 | 0 | 0 | 0 | 0 |
| BNBUSDT | 9,839 | 2025-05-30 10:00 | 2026-07-14 08:00 | 0 | 0 | 0 | 0 | 0 |
| TRXUSDT | 9,839 | 2025-05-30 10:00 | 2026-07-14 08:00 | 0 | 0 | 0 | 0 | 0 |
| HYPEUSDT | 9,839 | 2025-05-30 10:00 | 2026-07-14 08:00 | 0 | 0 | 0 | 0 | 0 |

逐列核对 `open/high/low/close/volume/quote_volume/trade_count`；同时检查高低价关系、非正 OHLC、负成交量和 `is_closed`，均无违规。

## Funding 质量结果

| Symbol | Rows | UTC first | UTC last | Max gap | Duplicate | Null rate | Archive/API rows | Blocker |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |
| BTCUSDT | 1,230 | 2025-05-30 16:00 | 2026-07-14 08:00 | 8h | 0 | 0 | 1,095 / 135 | 0 |
| ETHUSDT | 1,230 | 2025-05-30 16:00 | 2026-07-14 08:00 | 8h | 0 | 0 | 1,095 / 135 | 0 |
| SOLUSDT | 1,230 | 2025-05-30 16:00 | 2026-07-14 08:00 | 8h | 0 | 0 | 1,095 / 135 | 0 |
| BNBUSDT | 1,230 | 2025-05-30 16:00 | 2026-07-14 08:00 | 8h | 0 | 0 | 1,095 / 135 | 0 |
| TRXUSDT | 1,230 | 2025-05-30 16:00 | 2026-07-14 08:00 | 8h | 0 | 0 | 1,095 / 135 | 0 |
| HYPEUSDT | 2,459 | 2025-05-30 12:00 | 2026-07-14 08:00 | 8h | 0 | 0 | 2,190 / 269 | 0 |

历史归档只提供 funding rate、结算时间和间隔，不提供 `mark_price`，所以归档行的可选 `mark_price` 为空；策略资金费计算只依赖结算时间和 `funding_rate`，这不是 blocker。HYPE 在样本期内存在 `4h` funding 频率，其他五币主要为 `8h`，回测必须按实际结算事件计费，不能假设固定 `8h`。

## 证据

- 可复现脚本：[sync_and_audit_binance_six_asset_1h_data.py](../scripts/sync_and_audit_binance_six_asset_1h_data.py)
- 完整质量 JSON：[binance_six_asset_1h_data_quality_2026-07-14.json](../artifacts/binance_six_asset_1h_data_quality_2026-07-14.json)

