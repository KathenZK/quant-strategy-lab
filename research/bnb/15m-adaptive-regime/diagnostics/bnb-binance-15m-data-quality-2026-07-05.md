# BNBUSDT 永续合约 15m 数据质量审计 - 2026-07-05

## 结论

本轮 Binance USD-M Futures `BNBUSDT` perpetual `15m` 最近两年数据通过研究前置质量门槛，可以进入策略搜索。

## 数据范围

- Binance server time：`2026-07-05T14:57:58.746Z`。
- 闭合 K 线：`70,080` 根。
- UTC：`2024-07-05T14:45:00Z` 至 `2026-07-05T14:30:00Z`。
- 端点间预期行数：`70,080`。
- 来源：Binance Futures Kline API；market type 为 USD-M perpetual。

## 质量检查

- missing bars：`0`；raw/normalized duplicates：`0 / 0`。
- OHLC、volume、quote volume、trade count、VWAP、source、closed flag critical null：全部 `0`。
- 非法 OHLC、负 volume/quote volume、未闭合 K、cutoff 之后 K：全部 `0`。
- raw/normalized 的 open、high、low、close、volume、quote volume、trade count mismatch：全部 `0`。
- raw/normalized 日分区：各 `731` 个。

## 资金费与合约过滤器

- funding：`2,190` 行，UTC `2024-07-05T16:00:00Z` 至 `2026-07-05T08:00:00.001Z`；null=`0`。
- 合约状态：`TRADING`；`PERPETUAL`；margin asset `USDT`。
- tick size `0.010`；market quantity step/minimum `0.01`；minimum notional `5 USDT`。
- `triggerProtect=0.0500`、`marketTakeBound=0.05`、`liquidationFee=0.0125`。

## 保留证据

- `research/bnb/15m-adaptive-regime/artifacts/bnb_binance_15m_data_quality_2y.json`
- `research/bnb/15m-adaptive-regime/artifacts/bnb_binance_15m_closed_klines_2y.parquet`
- `research/bnb/15m-adaptive-regime/artifacts/bnb_binance_funding_history_2y.csv`
- `data/raw/ohlcv/exchange=binance/market_type=perp/timeframe=15m/date=*/symbol=bnb_usdt_usdt.parquet`
- `data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m/date=*/symbol=bnb_usdt_usdt.parquet`
