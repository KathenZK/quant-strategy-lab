# ETHUSDT Binance 永续 1h 数据质量审计 - 2026-07-03

## 结论

本次研究使用的最近两年 `ETHUSDT` 永续 `1h` 数据通过硬性质量门槛，`blocker_count=0`，允许进入策略搜索。数据结论仅对应下列精确时间窗与校验和。

## 数据身份

- 市场：Binance USD-M Futures。
- 合约：`ETHUSDT` perpetual；标准 symbol：`ETH/USDT:USDT`。
- 周期：`1h`。
- Binance server time cutoff：`2026-07-03T05:58:56.977Z`。
- 闭合 K UTC：`2024-07-03T05:00:00Z` 至 `2026-07-03T04:00:00Z`。
- raw rows：`17,521`；闭合 raw/normalized rows：`17,520 / 17,520`。
- 预期连续 rows：`17,520`。
- 数据源：`binance_futures_kline_api`。

## 硬检查

- missing bars：`0`。
- raw/normalized duplicate：`0 / 0`。
- 关键字段空值：`0`。
- 非法 OHLC、负 volume/quote volume/trade count：`0`。
- VWAP 超出 high/low：`0`。
- raw/normalized OHLCV、quote volume、trade count mismatch：`0`。
- cutoff 后或仍在形成的 K 被误标为 closed：`0`；`05:00` 正在形成的 K 已排除。
- zero-volume bars：`0`。

## 资金费与合约快照

- 资金费：`2,190` 条，UTC `2024-07-03T08:00:00.001Z` 至 `2026-07-03T00:00:00Z`，null=`0`，最大间隔约 `8.000004h`。
- 合约状态：`TRADING`；类型：`PERPETUAL`；margin asset：`USDT`。
- tick size：`0.01`；quantity step：`0.001`；market min qty：`0.001`；min notional：`20 USDT`。

## 精确证据与校验和

- exact research frame：`research/eth/1h-adaptive-regime/artifacts/eth_binance_1h_closed_klines_2y.parquet`。
- data-quality JSON：`research/eth/1h-adaptive-regime/artifacts/eth_binance_1h_data_quality_2y.json`。
- normalized funding：`data/normalized/funding/exchange=binance/market_type=perp/symbol=eth_usdt_usdt/funding.parquet`。
- `close_sum=49,447,114.11`。
- `volume_sum=3,297,634,789.872`。
- `quote_volume_sum=9,156,971,841,231.988`。
- `trade_count_sum=4,237,703,300`。

## 复现

```bash
uv run python research/eth/1h-adaptive-regime/scripts/fetch_eth_binance_1h.py
```

该命令按 Binance server time 重新定义“最近两年”，因此未来刷新会改变端点与校验和；需要复现本次实验时应保留 exact research frame。
