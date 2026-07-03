# BNBUSDT 永续合约 1h 数据质量审计 - 2026-07-03

## 结论

本轮 Binance USD-M Futures `BNBUSDT` perpetual `1h` 最近两年数据通过研究前置质量门槛，可以进入策略搜索。

## 数据范围

- Binance server time：`2026-07-03T06:26:26.564Z`。
- 闭合 K 线：`17,520` 根。
- UTC：`2024-07-03T06:00:00Z` 至 `2026-07-03T05:00:00Z`。
- 时间粒度：`1h`；预期端点间行数也是 `17,520`。
- 数据源：Binance Futures Kline API；market type 为 USD-M perpetual。

## 质量检查

- missing bars：`0`。
- raw duplicates / normalized duplicates：`0 / 0`。
- OHLC、volume、quote volume、trade count、VWAP、source、closed flag critical null：全部 `0`。
- 非法 OHLC、负成交量、负成交额、负成交笔数、VWAP 越界：全部 `0`。
- 未闭合 K 混入：`0`。
- raw/normalized 的 open、high、low、close、volume、quote volume、trade count 不一致：全部 `0`。
- raw/normalized 日分区：各 `731` 个。

## 资金费与合约快照

- 资金费记录：`2,190` 行；UTC `2024-07-03T08:00:00.001Z` 至 `2026-07-03T00:00:00Z`。
- funding rate null：`0`；最大相邻间隔约 `8.000004` 小时。
- 合约状态：`TRADING`；contract type：`PERPETUAL`；margin asset：`USDT`。
- tick size：`0.010`；market quantity step：`0.01`；market minimum quantity：`0.01`；minimum notional：`5 USDT`。
- 当前 `triggerProtect=0.0500`、`marketTakeBound=0.05`、`liquidationFee=0.0125`；合约声明支持 `MARKET`、`STOP_MARKET`、`TAKE_PROFIT_MARKET` 和 `TRAILING_STOP_MARKET`，但条件单实际下单必须走当前 `/fapi/v1/algoOrder` 语义，不能沿用旧 `/fapi/v1/order` 假设。

## 保留证据

- `research/bnb/1h-adaptive-regime/artifacts/bnb_binance_1h_data_quality_2y.json`
- `research/bnb/1h-adaptive-regime/artifacts/bnb_binance_1h_closed_klines_2y.parquet`
- `research/bnb/1h-adaptive-regime/artifacts/bnb_binance_funding_history_2y.csv`
- `data/raw/ohlcv/exchange=binance/market_type=perp/timeframe=1h/date=*/symbol=bnb_usdt_usdt.parquet`
- `data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=1h/date=*/symbol=bnb_usdt_usdt.parquet`
