# BIN-15M-EMAX-LGBM P0 数据冻结诊断（2026-07-24）

## 范围与来源

- 数据：Binance Vision 官方月归档 USD-M `15m` kline，790 个 USDT 永续（含退市），`2020-01`–`2026-06`，共 19,749 个归档月、压缩 2.01 GiB，逐 ZIP SHA256 对照官方 CHECKSUM 校验。
- 落湖：`data/{raw,normalized}/ohlcv/exchange=binance/market_type=perp/timeframe=15m/source=binance_vision_monthly/month=*/`；与既有 7 币遗留日分区按 `(ts, symbol)` 键去重（月分区剔除重叠键 631,884 行），**遗留日分区文件零改动**——原因：[`HYPE-15M-MMTF` 数据冻结](../../../hype/15m-multi-mechanism-trend-following/diagnostics/hype-15m-mmtf-data-freeze-2026-07-22.md)已按合并 SHA256 锁定 HYPE 15m 湖分区，不允许 1h 线当年那种 enrich 改写。
- funding 与 `1h` mark price 复用 CSLGBM 已同步的月归档；funding 覆盖全部 kline 符号（缺失=0）。
- 清单与审计工件：[binance_usdm_15m_inventory_2026-07-23.csv](../artifacts/binance_usdm_15m_inventory_2026-07-23.csv)、[binance_usdm_15m_quality_audit.json](../artifacts/binance_usdm_15m_quality_audit.json)、同步 manifest（`artifacts/binance_usdm_15m_sync_manifest_*.jsonl`）。

## 审计结果（union 视图 = 遗留日分区 + Vision 月分区）

- 总行数 56,462,323，791 个符号；`(ts, symbol)` 重复键 **0**；OHLC 违规 **0**；OHLC/volume 空值 **0**。
- 连续性：711 个符号零缺口；中位缺口率 0；24 个符号缺口率 >1%，其中绝大多数是 2026 年新上的**代币化股票/商品/ETF 永续**（GOOGL、TSLA、SPY、XAU 等，只在标的市场交易时段有 K 线，缺口是设计属性）。
- 遗留 vs 归档 OHLC 抽样对拍（BTC×2 月、SOL、HYPE，共 11,808 行）：BTC 2024-03 有 5 处、SOL 2025-01 有 4 处数值差异，量级为 API 实时数据与归档修订的已知差异；Vision 归档为权威，遗留行保持原样（不可改写，见上）。
- 已知异常（均不构成本家族 blocker，已被币池规则自动排除）：
  - `XMR_USDT_USDT`（非规范符号格式）：106,465 行 `quote_volume` 为空、时间延伸到 2026-05（币安 XMR 2024 年初已退市），判定为历史非标准导入；ADV 计算为 NaN，永远不合格。Vision 真 XMR 数据为独立 `XMR/USDT:USDT`，不受污染。
  - `date=2026-04-01` 下 100 个精简 schema 文件（无 symbol/quote_volume 列，代币化股票探索性导入，共 352,212 行）：研究读取层显式排除（`symbol IS NOT NULL`），审计单独计数。
  - 遗留 7 币日分区无 taker 字段：taker 特征在这些行显式为 NaN，LightGBM 原生处理缺失；不做静默填充。
- 代币化股票/商品永续（非 COIN underlying）通过 exchangeInfo `underlyingType` 过滤 + 稳定币/法币基础黑名单从训练池与交易池排除。

## 结论

- P0 kill gate（主流合约无法解释的大面积缺口）：**未触发**，数据可用于研究面。
- 数据边界冻结：开发窗 `2020-01-01`–`2025-12-31`，锁定 OOS `2026-01-01`–`2026-06-30`（reused holdout，曾被 CSLGBM 揭示过）。
