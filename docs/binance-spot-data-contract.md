# Binance Spot 1h CTA 数据需求说明

这份文档用于说明我们要构建的 Binance 现货 CTA 策略需要什么数据、目录结构、字段格式和质量标准。目标是让数据采集工程可以稳定地产出策略可直接读取的 Parquet 数据。

## 1. 我们要做什么

我们要做一个针对 Binance 现货 USDT 交易对的 1 小时级趋势策略：

- 全市场扫描 Binance spot USDT pairs。
- 排除稳定币、法币、杠杆代币、inactive 交易对。
- 每小时收盘后读取最新 1h K 线。
- 计算趋势、动量、成交量、波动率和流动性因子。
- 输出当前应该关注、买入、持有、退出的币种和权重。

策略不是 tick 级高频交易。tick 数据可以作为原始数据层，但策略主输入应是清洗后的 `1h OHLCV`。

## 2. 总体数据分层

推荐在 `/Volumes/alpha-data/crypto-lake` 下维护正式数据湖：

```text
/Volumes/alpha-data/crypto-lake/
  raw/
    trades/
    orderbook/
  normalized/
    ohlcv/
  snapshots/
    universe/
  quality/
  checkpoints/
  logs/
```

当前已有的 `/Volumes/alpha-data/ticks/cx/binance_spot/...` 可以保留为 raw tick 采集层，但策略不要直接读取这些零散 tick 文件。

## 3. 必须产出的核心数据

### 3.1 Binance Spot 1h OHLCV

这是策略最重要的数据层，必须产出。

推荐路径：

```text
/Volumes/alpha-data/crypto-lake/normalized/ohlcv/
  exchange=binance/
    market_type=spot/
      timeframe=1h/
        symbol=BTC_USDT/
          date=2026-04-29/
            part-000000.parquet
```

字段要求：


| 字段             | 类型            | 必填  | 说明                               |
| -------------- | ------------- | --- | -------------------------------- |
| `ts`           | timestamp UTC | 是   | 1h bar 开始时间，必须 UTC               |
| `exchange`     | string        | 是   | 固定 `binance`                     |
| `market_type`  | string        | 是   | 固定 `spot`                        |
| `timeframe`    | string        | 是   | 固定 `1h`                          |
| `symbol`       | string        | 是   | 标准格式，如 `BTC/USDT`                |
| `base_asset`   | string        | 是   | 如 `BTC`                          |
| `quote_asset`  | string        | 是   | 如 `USDT`                         |
| `open`         | float64       | 是   | 该小时第一笔有效成交价                      |
| `high`         | float64       | 是   | 该小时最高有效成交价                       |
| `low`          | float64       | 是   | 该小时最低有效成交价                       |
| `close`        | float64       | 是   | 该小时最后一笔有效成交价                     |
| `volume`       | float64       | 是   | base volume，`sum(size)`          |
| `quote_volume` | float64       | 是   | quote volume，`sum(price * size)` |
| `trade_count`  | int64         | 是   | 有效成交笔数                           |
| `vwap`         | float64       | 是   | `quote_volume / volume`          |
| `is_closed`    | bool          | 是   | 是否已收盘，策略只能使用 `true`              |
| `source`       | string        | 是   | 如 `binance_aggTrade`             |
| `ingested_at`  | timestamp UTC | 是   | 数据写入时间                           |


唯一键：

```text
exchange + market_type + timeframe + symbol + ts
```

同一个唯一键不应出现多行。若重跑补数，应覆盖或去重，只保留最终版本。

## 4. Raw Trades 数据要求

raw trades 可以继续保留，作为审计和重新聚合来源。

推荐路径：

```text
/Volumes/alpha-data/crypto-lake/raw/trades/
  exchange=binance/
    market_type=spot/
      symbol=BTC_USDT/
        date=2026-04-29/
          part-000000.parquet
```

字段要求：


| 字段                 | 类型            | 必填  | 说明                            |
| ------------------ | ------------- | --- | ----------------------------- |
| `exchange`         | string        | 是   | `binance`                     |
| `market_type`      | string        | 是   | `spot`                        |
| `symbol`           | string        | 是   | `BTC/USDT`                    |
| `inst_id`          | string        | 是   | Binance 原始 symbol，如 `BTCUSDT` |
| `ts_ms`            | int64         | 是   | 成交事件时间，毫秒                     |
| `ts`               | timestamp UTC | 建议  | 由 `ts_ms` 转换                  |
| `trade_id`         | string        | 是   | Binance aggTrade id           |
| `price`            | float64       | 是   | 成交价                           |
| `size`             | float64       | 是   | base 数量                       |
| `side`             | string        | 是   | `buy` / `sell`                |
| `source_channel`   | string        | 是   | 如 `aggTrade`                  |
| `raw_payload_json` | string        | 建议  | 原始消息 JSON                     |
| `ingested_at`      | timestamp UTC | 是   | 入库时间                          |


清洗规则：

```text
price > 0
size > 0
ts_ms 不为空
trade_id 不为空
同一 symbol 下 trade_id 去重
使用事件时间 ts_ms 聚合，不要使用 ingested_at 聚合
```

注意：Binance 现货 raw payload 应该是 `aggTrade`，例如：

```json
{
  "e": "aggTrade",
  "s": "BTCUSDT",
  "a": 3946934964,
  "p": "77574.55000000",
  "q": "0.00056000",
  "T": 1777460920316,
  "m": true
}
```

如果看到 `1000PEPEUSDT`、`pu`、`MARKET/NA`、或 futures depth update 特征，不要混入 `binance spot` 数据层。

## 5. Raw Orderbook 数据要求

CTA 主策略不强依赖 orderbook，但 orderbook 对滑点、盘口深度、可成交性评估有价值。建议保留。

推荐至少保留 5 档盘口，或产出小时级摘要。

raw orderbook 字段建议：


| 字段                 | 类型            | 必填  | 说明                            |
| ------------------ | ------------- | --- | ----------------------------- |
| `exchange`         | string        | 是   | `binance`                     |
| `market_type`      | string        | 是   | `spot`                        |
| `symbol`           | string        | 是   | `BTC/USDT`                    |
| `inst_id`          | string        | 是   | `BTCUSDT`                     |
| `ts_ms`            | int64         | 是   | 盘口事件时间                        |
| `ts`               | timestamp UTC | 建议  | 由 `ts_ms` 转换                  |
| `best_bid`         | float64       | 是   | 最优买价                          |
| `best_ask`         | float64       | 是   | 最优卖价                          |
| `best_bid_size`    | float64       | 是   | 最优买量                          |
| `best_ask_size`    | float64       | 是   | 最优卖量                          |
| `spread_bps`       | float64       | 是   | `best_ask / best_bid - 1`，bps |
| `bid_depth_5`      | float64       | 建议  | 前 5 档买盘数量                     |
| `ask_depth_5`      | float64       | 建议  | 前 5 档卖盘数量                     |
| `bids_json`        | string        | 可选  | 前 N 档买盘                       |
| `asks_json`        | string        | 可选  | 前 N 档卖盘                       |
| `raw_payload_json` | string        | 建议  | 原始消息                          |
| `ingested_at`      | timestamp UTC | 是   | 入库时间                          |


## 6. Universe 快照

为了避免回测出现幸存者偏差，需要每天保存一次可交易 universe 快照。

推荐路径：

```text
/Volumes/alpha-data/crypto-lake/snapshots/universe/
  exchange=binance/
    market_type=spot/
      quote_asset=USDT/
        date=2026-04-29/
          universe.parquet
```

字段要求：


| 字段                   | 类型            | 必填  | 说明                       |
| -------------------- | ------------- | --- | ------------------------ |
| `snapshot_date`      | date          | 是   | 快照日期 UTC                 |
| `exchange`           | string        | 是   | `binance`                |
| `market_type`        | string        | 是   | `spot`                   |
| `symbol`             | string        | 是   | `BTC/USDT`               |
| `inst_id`            | string        | 是   | `BTCUSDT`                |
| `base_asset`         | string        | 是   | `BTC`                    |
| `quote_asset`        | string        | 是   | `USDT`                   |
| `active`             | bool          | 是   | 是否 active                |
| `is_stablecoin`      | bool          | 是   | 是否稳定币                    |
| `is_fiat`            | bool          | 是   | 是否法币                     |
| `is_leveraged_token` | bool          | 是   | 是否杠杆代币                   |
| `listed_at`          | timestamp UTC | 可选  | 若可获取                     |
| `raw_market_json`    | string        | 建议  | Binance/ccxt market 原始信息 |


过滤规则：

```text
只保留 quote_asset = USDT
只保留 market_type = spot
排除 inactive
排除稳定币 base，如 USDC/FDUSD/TUSD/DAI 等
排除法币 base，如 EUR/GBP/TRY 等
排除杠杆代币，如 BTCUP/BTCDOWN/BULL/BEAR/3L/3S
```

## 7. 1h OHLCV 聚合规则

从 raw trades 聚合 1h OHLCV：

```sql
SELECT
  time_bucket(INTERVAL '1 hour', ts) AS ts,
  first(price ORDER BY ts_ms, trade_id) AS open,
  max(price) AS high,
  min(price) AS low,
  last(price ORDER BY ts_ms, trade_id) AS close,
  sum(size) AS volume,
  sum(price * size) AS quote_volume,
  count(*) AS trade_count,
  sum(price * size) / nullif(sum(size), 0) AS vwap
FROM trades
WHERE price > 0
  AND size > 0
GROUP BY 1
ORDER BY 1;
```

`is_closed` 规则：

```text
当前小时未结束时，is_closed = false
策略读取时只能使用 is_closed = true
建议 normalized/ohlcv 里只写已收盘 bar，或明确标注 is_closed
```

## 8. 数据质量检查

每次同步/聚合后，至少产出一份 quality report。

推荐路径：

```text
/Volumes/alpha-data/crypto-lake/quality/
  exchange=binance/
    market_type=spot/
      timeframe=1h/
        date=2026-04-29/
          quality.parquet
```

每个 symbol 检查：


| 检查项                       | 标准    |
| ------------------------- | ----- |
| `bad_price_rows`          | 必须为 0 |
| `bad_size_rows`           | 必须为 0 |
| `duplicate_trade_id_rows` | 应为 0  |
| `ohlcv_duplicate_bars`    | 必须为 0 |
| `ohlcv_null_close`        | 必须为 0 |
| `ohlcv_low_le_0`          | 必须为 0 |
| `ohlcv_high_lt_low`       | 必须为 0 |
| `missing_closed_1h_bars`  | 需要记录  |
| `latest_closed_bar_ts`    | 需要记录  |
| `row_count`               | 需要记录  |
| `quote_volume_24h`        | 需要记录  |


如果出现以下情况，应阻止进入策略层：

```text
price <= 0
size <= 0
OHLCV low <= 0
high < low
close 为空
同一 symbol + timeframe + ts 重复
把 futures/perp 数据混进 spot
```

## 9. 写入要求

为了避免读到半写入文件：

```text
先写临时文件，例如 .tmp/part-xxx.parquet
写完并校验成功后 rename/move 到正式目录
不要直接覆盖正在被读取的 parquet 文件
```

并发要求：

```text
同一数据层同一 symbol/timeframe 同一时刻只能有一个 writer
可以多 reader
策略机器只读 normalized 数据，不写 raw/normalized
```

## 10. 保留周期

建议：

```text
raw trades: 至少保留 30-90 天；如果空间允许可保留更久
raw orderbook: 至少保留 7-30 天，或只保留摘要
normalized 1h OHLCV: 长期保留，至少 2-4 年
universe snapshots: 长期保留
quality reports: 长期保留
```

1h CTA 策略至少需要：

```text
最近 500-1000 根 1h K线
也就是至少 20-40 天数据
```

正式回测建议保留：

```text
1-4 年 1h OHLCV
```

## 11. 交付验收标准

第一阶段交付：

- Binance spot USDT universe 快照。
- 至少 20 个高流动性 spot symbols。
- 连续 7 天以上 raw trades。
- 对应连续 7 天以上 `1h OHLCV`。
- 每天 quality report。

第二阶段交付：

- Binance spot USDT 全市场。
- 连续 30-60 天以上 `1h OHLCV`。
- 自动增量同步。
- 每小时收盘后 5 分钟内完成最新 closed bar 写入。

最终目标：

- Binance spot USDT 全市场长期数据湖。
- 策略侧可以直接读取 `normalized/ohlcv` 做 1h CTA 监控、回测和 paper trading。

## 12. 对当前样本数据的判断

目前 `/Volumes/alpha-data/ticks/cx/binance_spot` 这版方向是对的：

- 是 Binance spot `aggTrade`。
- `PEPEUSDT` 这类 symbol 符合现货语义。
- 抽样没有发现 `price=0` 或 `size=0`。
- 可以作为 raw trades 数据源。

但当前样本只覆盖约几分钟到一天，不足以支持策略。下一步重点不是重做 raw tick，而是：

```text
继续扩展采集覆盖
补 normalized 1h OHLCV
补 universe 快照
补 quality report
确保 spot/perp 严格隔离
```

