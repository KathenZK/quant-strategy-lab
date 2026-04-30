# Crypto Lake 多交易所行情数据湖方案

这份方案给数据采集团队使用，目标是在 `/Volumes/alpha-data/crypto-lake` 建一套可长期维护的数据湖。它要同时满足两件事：

1. 后续可以存多个交易所、多个市场类型、多个周期的数据，比如 Binance/OKX/Bybit，spot/perp，1m/5m/1h/4h/1d。
2. 当前策略实验室可以直接读取，尤其是现货 CTA 策略需要的 `spot 1h OHLCV` 字段和语义必须对齐。

## 1. 总体原则

- 所有时间字段统一使用 UTC。
- 所有行情表使用 Parquet。
- 所有写入使用临时文件 + 原子 rename，避免研究端读到半文件。
- 同一个业务主键不能重复。OHLCV 的唯一键是：

```text
exchange + market_type + timeframe + symbol + ts
```

- 策略只能使用已收盘 K 线，`is_closed = true`。
- `symbol` 字段统一使用标准格式：`BTC/USDT`、`ETH/USDT:USDT`。
- 原始交易所 symbol 另存为 `inst_id`：`BTCUSDT`、`BTC-USDT-SWAP`。
- 数据湖可以保留 inactive、stablecoin、leveraged token，但 universe 快照里必须有字段标识，策略读取时再过滤。

## 2. 推荐目录结构

```text
/Volumes/alpha-data/crypto-lake/
  raw/
    trades/
    orderbook/
    klines/
  normalized/
    ohlcv/
    ticker/
    funding_rates/
    open_interest/
    basis_or_premium/
    liquidations/
  snapshots/
    universe/
  quality/
  checkpoints/
  logs/
```

### 2.1 Canonical 数据湖分区

长期标准层建议这样分区：

```text
normalized/ohlcv/
  exchange=binance/
    market_type=spot/
      timeframe=1h/
        date=2026-04-30/
          part-000000.parquet

normalized/ohlcv/
  exchange=okx/
    market_type=perp/
      timeframe=5m/
        date=2026-04-30/
          part-000000.parquet
```

这个结构适合长期扩展：

- `exchange`：`binance`、`okx`、`bybit`、`gateio`
- `market_type`：`spot`、`perp`
- `timeframe`：`1m`、`5m`、`15m`、`1h`、`4h`、`1d`
- `date`：按 K 线开始时间 `ts.date()` 分区，不是写入时间

每个 `date` 分区里可以是所有 symbol 放在一个或多个 `part-xxxxx.parquet` 里，不强制按 symbol 分目录。文件内部必须有 `symbol` 字段。

## 3. 项目接入要求

`crypto-lake` 是统一标准数据湖，不为某一个项目单独变形。所有研究、回测、交易和监控项目都应该适配数据湖标准，而不是要求数据湖反向适配项目。

项目读取数据时必须显式指定以下维度：

```text
exchange
market_type
timeframe
symbol
date range
```

例如现货 CTA 策略读取：

```text
exchange = binance
market_type = spot
timeframe = 1h
quote_asset = USDT
date range = 最近 90 天
```

接入方需要做到：

- 读取 `normalized/ohlcv` 时必须过滤 `timeframe`，避免把 `1m/5m/1h` 混在一起。
- 读取多交易所数据时必须过滤 `exchange` 和 `market_type`。
- 读取具体策略 universe 时，应结合 `snapshots/universe` 和策略过滤规则生成 symbol 列表。
- 当前项目如果还没有支持 `timeframe` 过滤，需要改项目代码，不应新增数据湖兼容目录。
- 数据湖只维护 canonical 层，不维护项目专属副本。

## 4. OHLCV 标准字段

`normalized/ohlcv` 必须包含以下字段：


| 字段             | 类型            | 必填  | 说明                                                |
| -------------- | ------------- | --- | ------------------------------------------------- |
| `ts`           | timestamp UTC | 是   | K 线开始时间                                           |
| `exchange`     | string        | 是   | 如 `binance`                                       |
| `market_type`  | string        | 是   | `spot` / `perp`                                   |
| `timeframe`    | string        | 是   | `1m` / `5m` / `1h` 等                              |
| `symbol`       | string        | 是   | 标准交易对，如 `BTC/USDT`                                |
| `inst_id`      | string        | 建议  | 交易所原始 id，如 `BTCUSDT`                              |
| `base_asset`   | string        | 是   | 如 `BTC`                                           |
| `quote_asset`  | string        | 是   | 如 `USDT`                                          |
| `open`         | float64       | 是   | 开盘价                                               |
| `high`         | float64       | 是   | 最高价                                               |
| `low`          | float64       | 是   | 最低价                                               |
| `close`        | float64       | 是   | 收盘价                                               |
| `volume`       | float64       | 是   | base volume                                       |
| `quote_volume` | float64       | 是   | quote volume，不能全 0                                |
| `trade_count`  | int64         | 是   | 成交笔数，不能全 0                                        |
| `vwap`         | float64       | 是   | `quote_volume / volume`，volume 为 0 时置空或 0 并在质量表标记 |
| `is_closed`    | bool          | 是   | 是否已收盘                                             |
| `source`       | string        | 是   | 如 `binance_kline_api`、`agg_trade_aggregation`     |
| `ingested_at`  | timestamp UTC | 是   | 写入时间                                              |


当前策略最少依赖这些字段：

```text
ts, exchange, symbol, market_type, base_asset, quote_asset,
open, high, low, close, volume, source
```

但为了流动性、成交质量和后续滑点模型，`quote_volume`、`trade_count`、`vwap` 必须真实填充，不能长期用 0 占位。

## 5. Binance Spot 1h 数据要求

当前 CTA 策略需要优先交付：

```text
exchange = binance
market_type = spot
quote_asset = USDT
timeframe = 1h
history = 最近 90 天起
symbols = Binance active USDT spot 全市场
```

数量口径：

- Binance 当前 active USDT spot 约 `431` 个交易对。
- 策略 universe 会排除稳定币、法币、杠杆代币和异常 symbol，约 `420` 个。
- 数据湖的 universe snapshot 可以保留全部 `431/659` 个 USDT spot 交易对，但 OHLCV 至少要覆盖 active 交易对。

交付标准：

- 过去 90 天内，正常老币每个 symbol 应该约 `2160` 根 1h K 线。
- 新上市币可以少于 90 天，但要从上市后第一根可获取 K 线开始。
- 最新数据每小时更新一次，建议在整点后 3-5 分钟拉取上一小时已收盘 K 线。
- 不要写当前未收盘的 K 线；如果保留，必须 `is_closed=false`，策略读取层必须过滤掉。

## 6. 多 timeframe 规范

同一个 exchange / market_type / symbol 可以存多个周期：

```text
timeframe=1m
timeframe=5m
timeframe=1h
timeframe=4h
timeframe=1d
```

要求：

- 每个 timeframe 单独分区。
- 不同 timeframe 不要写进同一个 Parquet 文件。
- `ts` 都表示 bar 开始时间。
- `date` 分区都用 `ts.date()`。
- 从低周期聚合高周期时，必须只使用完整低周期 bar。

推荐聚合关系：

```text
raw trades -> 1m OHLCV -> 5m/15m/1h OHLCV
```

如果直接从交易所 kline API 拉 1h，也可以作为第一阶段交付，但需要保证字段完整，特别是 `quote_volume` 和 `trade_count`。

## 7. 多交易所 symbol 标准

统一对外字段：

```text
exchange: binance / okx / bybit / gateio
market_type: spot / perp
symbol: BTC/USDT 或 BTC/USDT:USDT
inst_id: 交易所原始 symbol
base_asset: BTC
quote_asset: USDT
settle_asset: USDT   # perp 建议增加
contract_type: linear / inverse / spot   # 衍生品建议增加
```

示例：


| exchange | market_type | symbol          | inst_id         |
| -------- | ----------- | --------------- | --------------- |
| binance  | spot        | `BTC/USDT`      | `BTCUSDT`       |
| binance  | perp        | `BTC/USDT:USDT` | `BTCUSDT`       |
| okx      | spot        | `BTC/USDT`      | `BTC-USDT`      |
| okx      | perp        | `BTC/USDT:USDT` | `BTC-USDT-SWAP` |


## 8. Universe 快照

路径：

```text
snapshots/universe/
  exchange=binance/
    market_type=spot/
      quote_asset=USDT/
        date=2026-04-30/
          universe.parquet
```

字段：


| 字段                   | 类型            | 必填  | 说明           |
| -------------------- | ------------- | --- | ------------ |
| `snapshot_date`      | date          | 是   | UTC 日期       |
| `exchange`           | string        | 是   | 交易所          |
| `market_type`        | string        | 是   | 市场类型         |
| `symbol`             | string        | 是   | 标准交易对        |
| `inst_id`            | string        | 是   | 原始交易所 id     |
| `base_asset`         | string        | 是   | base         |
| `quote_asset`        | string        | 是   | quote        |
| `active`             | bool          | 是   | 是否 active    |
| `is_stablecoin`      | bool          | 是   | 是否稳定币        |
| `is_fiat`            | bool          | 是   | 是否法币         |
| `is_leveraged_token` | bool          | 是   | 是否杠杆 token   |
| `listed_at`          | timestamp UTC | 可选  | 上市时间         |
| `delisted_at`        | timestamp UTC | 可选  | 下架时间         |
| `raw_market_json`    | string        | 建议  | 原始 market 信息 |


Universe 快照每天至少保存一次，回测必须能按历史日期还原当时可交易 universe，避免幸存者偏差。

## 9. Quality 表

路径建议：

```text
quality/
  exchange=binance/
    market_type=spot/
      timeframe=1h/
        date=2026-04-30/
          quality.parquet
```

字段：


| 字段                       | 类型            | 说明                     |
| ------------------------ | ------------- | ---------------------- |
| `date`                   | date          | 检查日期                   |
| `exchange`               | string        | 交易所                    |
| `market_type`            | string        | 市场类型                   |
| `timeframe`              | string        | 周期                     |
| `symbol`                 | string        | 标准交易对                  |
| `row_count`              | int64         | 当日 bar 数               |
| `expected_closed_bars`   | int64         | 截止检查时间应有的已收盘 bar 数     |
| `missing_closed_bars`    | int64         | 缺失已收盘 bar 数            |
| `duplicate_bars`         | int64         | 重复 bar 数               |
| `null_close_rows`        | int64         | close 为空               |
| `bad_price_rows`         | int64         | open/high/low/close 非法 |
| `high_lt_low_rows`       | int64         | high < low             |
| `zero_volume_rows`       | int64         | volume 为 0             |
| `zero_quote_volume_rows` | int64         | quote_volume 为 0       |
| `zero_trade_count_rows`  | int64         | trade_count 为 0        |
| `latest_closed_bar_ts`   | timestamp UTC | 最新已收盘 K 线              |
| `quote_volume_24h`       | float64       | 最近 24h quote volume    |
| `checked_at`             | timestamp UTC | 检查时间                   |


注意：

- `missing_closed_bars` 只能检查“当前时间之前已经应该收盘”的 K 线，不要把当天未来还没发生的小时算成缺失。
- `quote_volume_24h` 不能全 0，否则策略无法做流动性过滤。
- quality 表不是只看错误，也要能帮助策略过滤低流动性标的。

## 10. Checkpoint 和日志

每个采集任务需要记录 checkpoint：

```text
checkpoints/
  exchange=binance/
    market_type=spot/
      dataset=ohlcv/
        timeframe=1h/
          checkpoint.parquet
```

建议字段：

```text
exchange
market_type
timeframe
symbol
last_success_ts
last_attempt_at
last_success_at
last_error
rows_written
source
```

日志至少保留：

- 本次任务开始/结束时间
- 请求了哪些 symbol
- 成功/失败数量
- 每个失败 symbol 的错误原因
- 写入了哪些 partition

## 11. 增量写入规则

每小时更新流程建议：

1. 读取 universe snapshot，得到 active symbol。
2. 对每个 symbol 找 checkpoint 的 `last_success_ts`。
3. 从 `last_success_ts + timeframe` 开始拉取。
4. 只保留已收盘 bar。
5. 写入 `date=YYYY-MM-DD` 分区。
6. 对同一唯一键去重或覆盖。
7. 更新 quality。
8. 更新 checkpoint。

重跑补数时：

- 可以覆盖目标日期分区，或写临时文件后合并去重。
- 不允许同一唯一键产生多行。
- 不允许因为重跑导致历史日期的 `ingested_at` 混乱影响业务时间；业务时间永远看 `ts`。

## 12. 验收标准

第一阶段交付验收：

- `normalized/ohlcv` 有 Binance spot 1h 最近 90 天数据。
- active USDT spot 覆盖不少于 `420` 个策略候选币。
- 老币每个 symbol 约 `2160` 根 1h K 线。
- 新币从上市后第一根 K 线开始。
- `quote_volume`、`trade_count`、`vwap` 不得全 0。
- `is_closed=true` 的 K 线不能包含当前未收盘小时。
- `quality` 表能正确识别缺失、重复、非法价格、0 成交量。
- `snapshots/universe` 每天一份，字段足够过滤 stablecoin/fiat/leveraged/inactive。
- 接入项目必须能按 `exchange/market_type/timeframe/symbol/date range` 过滤数据，不混入其他周期。

当前策略可用性的最低验证方式：

```bash
./.venv/bin/quant-strategy-lab scan-spot-cta \
  --workflow-config configs/workflows/strategies/spot_cta_trend.binance.spot.1h.local.yaml \
  --use-local-universe \
  --min-avg-dollar-volume 0 \
  --min-history-bars 120 \
  --max-symbols 0 \
  -c configs/app/binance-spot-1h-local.yaml
```

如果这条命令要直接读 `/Volumes/alpha-data/crypto-lake`，策略项目必须支持从 canonical 层读取并显式过滤 `timeframe=1h`。不要为 `quant-strategy-lab` 单独生成兼容目录。