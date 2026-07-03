# TRXUSDT Binance perpetual 1h 数据质量审计 - 2026-07-03

## 结论

本轮精确研究帧通过 data-quality-first gate，可以进入参数搜索。该结论只覆盖本次冻结数据快照，不代表策略有效。

## 数据身份

- Source：Binance USD-M Futures FAPI `TRXUSDT` perpetual Kline API。
- Timeframe：`1h`。
- Binance server cutoff：`2026-07-03T06:12:06.644000+00:00`。
- 闭合 K：`17,520` 根。
- UTC 范围：`2024-07-03T06:00:00+00:00` 至 `2026-07-03T05:00:00+00:00`。
- 预期连续行数：`17,520`。
- 最近三个月 locked OOS：`2026-04-03T06:00:00+00:00` 至 `2026-07-03T06:00:00+00:00`（右开）。

## 质量检查

| Check | Result |
| --- | ---: |
| missing bars | `0` |
| duplicate raw keys | `0` |
| duplicate normalized keys | `0` |
| critical nulls | `0` |
| OHLC/volume/trade-count violations | `0` |
| normalized non-closed bars | `0` |
| raw/normalized OHLCV mismatch | `0` |
| zero-volume bars | `0` |
| blocker count | `0` |

## 资金费

- rows：`2,190`。
- UTC：`2024-07-03T08:00:00.001000+00:00` 至 `2026-07-03T00:00:00+00:00`。
- null rates：`0`。
- 最大相邻间隔：约 `8.000004h`，符合历史结算时间毫秒偏移；回测按实际时间戳逐笔归属。

## 合约过滤器快照

- status / type：`TRADING` / `PERPETUAL`。
- `tickSize=0.00001`，`stepSize=1`，`minQty=1`，`MIN_NOTIONAL=5 USDT`。
- `MARKET_LOT_SIZE.maxQty=5,000,000`。
- 上线时间：`2020-01-15T08:05:00+00:00`。

这些过滤器将进入 live-executable 数量与价格取整审计；研究回测的收益率核算不依赖一个假定账户余额。

## 可复现证据

- `research/trx/1h-adaptive-regime/artifacts/trx_binance_1h_closed_klines_2y.parquet`
- `research/trx/1h-adaptive-regime/artifacts/trx_binance_1h_data_quality_2y.json`
- `research/trx/1h-adaptive-regime/artifacts/trx_binance_funding_history_2y.csv`
- `research/trx/1h-adaptive-regime/artifacts/trx_binance_contract_snapshot_2026-07-03.json`
- 数据湖 raw/normalized 日分区：各 `731` 个。

精确快照 SHA-256：

- closed klines Parquet：`d8fce752d09940954a41751e0d96d888e3bb1a80879e74bb31941a667fd66356`
- funding CSV：`0a0b932209ab4236bbac7b875e851ea7adffc9a79fa071aa63f7d81aed8050c3`
- quality JSON：`96640403f76108d5940bf11ed51a88b4b003cb9fa4f77410b77a39145a540769`
- contract snapshot JSON：`bb69c438a84c6d19777ad3f5e63eed213f673d9e166b263ffc698febe161a9c0`
