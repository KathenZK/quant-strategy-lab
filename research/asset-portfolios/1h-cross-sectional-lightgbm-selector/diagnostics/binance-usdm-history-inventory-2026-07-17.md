# Binance USD-M 历史数据清单与补齐诊断（2026-07-17）

## 结论

- 全市场历史研究不能直接使用补齐前的数据湖：本地 Binance perpetual `1h` 只有 BTC、ETH、SOL、BNB、TRX、HYPE 六币，共 `108,394` 行。
- 官方 Binance Vision 与当前 `exchangeInfo` 的历史并集包含 `793` 个 USDT perpetual 样式合约，其中 `139` 个已不在当前元数据清单。只按当前 `TRADING` 合约回填会产生明显幸存者偏差。
- 官方月归档清单包含：`19,749` 个 1h kline 压缩包、`20,016` 个 1h mark-price 压缩包、`18,954` 个 funding 压缩包；压缩体积合计约 `0.852 GiB`。
- funding 目录有 3 个合约存在内部月份缺口：`BNTUSDT`、`BTCSTUSDT`、`LITUSDT`。缺口必须显式记录，不能填成真实 0。
- 三个中文命名合约有成交 K 线但没有 mark-price 月归档；当前 2026-07 新上市合约不属于截止 2026-06 的研究窗。
- 旧 BTC CCXT 归一化文件与 Vision 重叠对拍显示 OHLC 一致，但旧 `quote_volume` 口径不一致、`trade_count` 为 0 且缺少 taker 字段。同步器改为使用官方 Vision 修复成交量结构字段，并保留 `legacy_source`。

## 冻结范围

- 历史归档：`2020-01` 至 `2026-06`。
- 锁定 OOS：`2026-04-01 00:00 <= ts < 2026-07-01 00:00 UTC`。
- 数据集：USD-M perpetual 1h kline、1h mark-price kline、funding。
- 历史来源：Binance Vision 月归档；每个 ZIP 下载 `.CHECKSUM` 并校验 SHA256。

## 产物与复现

- [历史清单脚本](../scripts/inventory_binance_usdm_history.py)
- [归档同步脚本](../scripts/sync_binance_usdm_history.py)
- [数据质量审计脚本](../scripts/audit_binance_usdm_history.py)
- 清单产物：`artifacts/binance_usdm_historical_inventory_2026-07-17.csv/json`
- 同步产物：标准 raw/normalized 数据湖月分区、原始 ZIP 与 checksum、逐批 JSONL manifest。

## 当前门禁

数据补齐和严格质量审计完成前，本家族保持 `explore / not promoted / not live-ready`，不得启动 LightGBM 训练，也不得读取锁定 OOS 的策略表现。
