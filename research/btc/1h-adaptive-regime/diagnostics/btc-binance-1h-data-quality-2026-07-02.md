# BTCUSDT Binance 永续 1h 数据质量报告 - 2026-07-02

## 结论

`PASS`。本次研究使用的最近两年闭合 K 无缺口、无重复、无关键空值、无 OHLC 约束违规，raw 与 normalized 数值逐列一致。

## 数据身份

- 市场：`Binance USD-M Futures`。
- 合约：`BTCUSDT` / `BTC/USDT:USDT`。
- 周期：`1h`。
- UTC：`2024-07-02T10:00:00+00:00` 至 `2026-07-02T09:00:00+00:00`。
- 闭合 K：`17520` 根；理论连续行数：`17520`。

## 硬质量检查

- missing bars：`0`。
- duplicate raw/normalized：`0` / `0`。
- critical nulls：`{"ts": 0, "open": 0, "high": 0, "low": 0, "close": 0, "volume": 0, "quote_volume": 0, "trade_count": 0, "vwap": 0, "source": 0, "is_closed": 0}`。
- OHLCV violations：`{"high_lt_open_or_close": 0, "low_gt_open_or_close": 0, "high_lt_low": 0, "nonpositive_ohlc": 0, "negative_volume": 0, "negative_quote_volume": 0, "negative_trade_count": 0, "vwap_outside_hilo": 0, "normalized_bar_not_closed_at_cutoff": 0, "raw_closed_flag_at_or_after_cutoff": 0}`。
- raw/normalized mismatch：`{"open": 0, "high": 0, "low": 0, "close": 0, "volume": 0, "quote_volume": 0, "trade_count": 0}`。
- blocker count：`0`。

## 资金费与合约快照

- funding：`2190` 行，`2024-07-02T16:00:00+00:00` 至 `2026-07-02T08:00:00+00:00`，null=`0`。
- 合约状态：`TRADING`；tickSize=`0.10`，market stepSize=`0.001`，min notional=`50` USDT。

## 校验值

- close sum：`1530578785.0`。
- volume sum：`140606222.25`。
- quote volume sum：`11790647636631.182`。
- trade count sum：`2732088946`。
