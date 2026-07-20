# 产物入口

本目录保存 `BTC-15M-EMA-Trend-Breakout` 数据质量与 V40 模板迁移研究的机器可读证据，不作为标准行情数据的替代存储。最终结论见[诊断报告](../diagnostics/btc-15m-ema-tb-v40-transfer-2026-07-17.md)。

## 数据质量

- [btc_binance_15m_data_quality_latest.json](btc_binance_15m_data_quality_latest.json)：最新审计报告，包含数据窗口、写入目标、funding archive SHA256、逐项质量结果与 blocker 总数。

标准 raw/normalized OHLCV 和 funding 写在仓库统一的 [`data/`](../../../../data/) 数据湖；本目录不复制完整行情。`--no-write` 模式不会创建或更新任何产物，只向标准输出打印同结构 JSON。

## V40 模板迁移

- [btc_15m_v40_frozen_splits_2026-07-17.json](btc_15m_v40_frozen_splits_2026-07-17.json)：冻结 train、validation、sealed holdout 边界与数据/内核 SHA。
- [btc_15m_v40_search_summary_2026-07-17.json](btc_15m_v40_search_summary_2026-07-17.json)：基线、搜索空间、Stage 1/2 计数及门禁汇总。
- [btc_15m_v40_candidate_metrics_2026-07-17.csv](btc_15m_v40_candidate_metrics_2026-07-17.csv)：全部候选指标、父项、组件和门禁失败项。
- [btc_15m_v40_frozen_selection_2026-07-17.json](btc_15m_v40_frozen_selection_2026-07-17.json)：揭示前冻结的 `diagnostic_near_miss`，明确不是 candidate。
- [btc_15m_v40_holdout_reveal_2026-07-17.json](btc_15m_v40_holdout_reveal_2026-07-17.json)：第 `1` 次且唯一一次 holdout 揭示、方向消融、近期切片及 post-reveal gate。
- [btc_15m_v40_holdout_trades_2026-07-17.csv](btc_15m_v40_holdout_trades_2026-07-17.csv)：holdout 逐笔交易。
- [btc_15m_v40_holdout_equity_2026-07-17.csv](btc_15m_v40_holdout_equity_2026-07-17.csv)：holdout 逐根净值。
- [btc_15m_v40_dev_walk_forward_2026-07-17.csv](btc_15m_v40_dev_walk_forward_2026-07-17.csv)：冻结参数 development walk-forward。

以上 selection 与 reveal 产物通过 payload/SHA 相互绑定；不得覆盖后重解释为 candidate，也不得用于登记 V1。
