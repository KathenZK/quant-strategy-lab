# Binance HYPEUSDT 永续 1h 全量数据质量报告 - 2026-07-01

## 结论

本轮已拉取 Binance USD-M Futures `HYPEUSDT` 从上线时段至运行时最后一根闭合 `1h` K 的全部可得数据，质量审计通过，无 data-quality blocker。

## 覆盖

- Binance server time：`2026-07-01 07:14:01.604 UTC`。
- Contract onboard time：`2025-05-30 10:30:00 UTC`。
- 第一根 K open time：`2025-05-30 10:00:00 UTC`；这是包含上线后半小时成交的首个 listing-hour K，完整保留。
- 最后一根闭合 K open time：`2026-07-01 07:00:00 UTC`。
- 闭合 K：`9,526` 根。
- UTC endpoint 间 expected：`9,526` 根。
- missing：`0`；raw duplicate：`0`；normalized duplicate：`0`。
- raw 日分区：`398`；normalized 日分区：`398`。
- funding：`2,380` 条，`2025-05-30 12:00:00.006 UTC` 至 `2026-07-01 04:00:00.001 UTC`，最大相邻间隔 `8h`。

## 字段审计

- `ts/open/high/low/close/volume/quote_volume/trade_count/vwap/source/is_closed` 空值均为 `0`。
- nonpositive OHLC、`high<max(open,close)`、`low>min(open,close)`、`high<low` 均为 `0`。
- negative volume、negative quote volume、negative trade count 均为 `0`。
- nonzero-volume VWAP 超出 high/low：`0`。
- raw 与 normalized 的 OHLC、volume、quote volume、trade count mismatch 均为 `0`。
- `is_closed=True`：`9,526/9,526`。
- source：`binance_futures_kline_api`，`9,526/9,526`。

## 文件

- Raw：`data/raw/ohlcv/exchange=binance/market_type=perp/timeframe=1h/date=*/symbol=hype_usdt_usdt.parquet`。
- Normalized：`data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=1h/date=*/symbol=hype_usdt_usdt.parquet`。
- 合并 K：`research/hype/1h-adaptive-regime/artifacts/hype_binance_1h_closed_klines.parquet`。
- Funding：`research/hype/1h-adaptive-regime/artifacts/hype_binance_funding_history.csv`。
- 完整 metadata：`research/hype/1h-adaptive-regime/artifacts/hype_binance_1h_data_quality.json`。

校验值：

- K Parquet SHA-256：`f2e71b23489ce745477b11f77c03368f12b7c7abd6cf8b9e37707f8ab7431d31`。
- Funding CSV SHA-256：`3de2954515752930a1cae46faef5219100b54c3aeeb03c36bf4d6c8415af1109`。

## 当前合约过滤器快照

- status：`TRADING`；contract type：`PERPETUAL`。
- tick size：`0.00100`。
- lot step：`0.01`；market min qty：`0.01`；market max qty：`20000`。
- min notional：`5 USDT`。
- percent-price：up `1.1500`、down `0.8500`。

复现：

```bash
uv run python research/hype/1h-adaptive-regime/scripts/fetch_hype_binance_1h.py --refresh
```

