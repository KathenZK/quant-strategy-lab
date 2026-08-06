# MU 股票 OHLCV 统一数据湖迁移（2026-08-05）

## 结论

原 `data/external/us_equities` 下 Polygon/Yahoo MU 股票数据已迁入统一
`data/raw/ohlcv`，旧目录在源文件 SHA256、CSV/Parquet 等价性、目标文件
SHA256、行数和 round-trip 校验全部通过后删除。

市场身份固定为 NASDAQ / equity / MU；Polygon 与 Yahoo 只作为 `source`，
不冒充交易所。迁移清单见
[`mu-equity-ohlcv-migration-2026-08-05.json`](../artifacts/mu-equity-ohlcv-migration-2026-08-05.json)，
复现脚本见
[`migrate_mu_equity_ohlcv.py`](../scripts/migrate_mu_equity_ohlcv.py)。

## 迁移结果

| 来源 | 周期 | UTC 范围 | 行数 | 日分区 |
| --- | --- | --- | ---: | ---: |
| `polygon_api` | `15m` | 2025-06-17 08:00 → 2026-06-16 23:45 | 15,951 | 270 |
| `yahoo_finance` | `15m` | 2026-03-24 08:00 → 2026-06-17 08:14:05 | 3,772 | 60 |
| `yahoo_finance` | `1d` | 2025-06-16 13:30 → 2026-06-16 13:30 | 252 | 252 |

目标根目录：

```text
data/raw/ohlcv/exchange=nasdaq/market_type=equity/timeframe=15m/source=polygon_api/
data/raw/ohlcv/exchange=nasdaq/market_type=equity/timeframe=15m/source=yahoo_finance/
data/raw/ohlcv/exchange=nasdaq/market_type=equity/timeframe=1d/source=yahoo_finance/
```

总计 19,975 行、582 个 UTC 日分区。数据湖结构与字段口径见
[`docs/data-lake-spec.md`](../../../docs/data-lake-spec.md)。

## 数据质量状态

三组源数据的核心 `ts/OHLCV` 均无 null、重复时间戳或非法 OHLC，但当前统一标为
`raw_unaccepted`：

- Polygon 15m 缺少标准 `quote_volume/is_closed`；原生 `transactions` 保留，
  未静默改写为标准字段。
- Yahoo 15m 缺少 `quote_volume/trade_count/vwap/is_closed`，末尾还有 1 条
  `08:14:05 UTC` 非 15 分钟网格时间戳。
- Yahoo 1d 缺少 `quote_volume/trade_count/vwap/is_closed`；原生 `adj_close`
  保留，未猜测 OHLC 调整口径。
- 股票休市、节假日、盘前盘后缺口尚未接入交易所日历，不能使用加密货币 24/7
  连续性规则判定缺 K。

因此本次迁移只完成存储统一与 provenance 固定，不把这些数据写入 normalized
层，也不改变任何既有研究结论。补齐 session-aware 连续性、闭合状态和字段来源
审计前，它们不得支持新策略登记、promotion 或 live-ready 结论。
