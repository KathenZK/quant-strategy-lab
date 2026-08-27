# Artifacts

本目录保存 `NDX100-1D-MA7-RC` 各 observation 的可复现机器证据；不同 observation 的文件前缀严格隔离。

## 当前已生成

- `membership-sources/*.wikitext` + `source_manifest.json`：revision-pinned 原始成分表与 attribution。
- `ndx100_1d_ma7_rc_p0_membership_change_log.csv`：行级变更、来源层级、URL 与 override。
- `ndx100_1d_ma7_rc_p0_membership_snapshots.csv`：每个有效日后的证券快照。
- `ndx100_1d_ma7_rc_p0_membership_intervals.csv`：ticker/entity 连续成分区间。
- `ndx100_1d_ma7_rc_p0_membership_daily.parquet`：session-level point-in-time membership。
- `ndx100_1d_ma7_rc_p0_membership_audit.json`：重建完整性与限制。
- `ndx100_1d_ma7_rc_p0_membership_artifact_manifest.json`：配置、来源与全部成分产物的 bytes/SHA256。
- `ndx100_1d_ma7_rc_p0_massive_access_audit.json` 与 `...data_access_blocker.json`：credential 可认证但 2010 历史 entitlement 不足的机器证据，不含 credential value。

## Yahoo 当前成分 Y0

- `yahoo-current-cache/chart/`：103 个 ticker 的原始 chart response 缓存。
- `ndx100_1d_ma7_rc_y0_current_universe.csv`：`2026-08-21` terminal snapshot 的 `102` 条证券。
- `ndx100_1d_ma7_rc_y0_yahoo_prices.parquet`：split-only 调整后的诊断价格面板，含 raw / Yahoo adj-close provenance 字段。
- `ndx100_1d_ma7_rc_y0_yahoo_price_audit.json` 与 `...data_manifest.json`：覆盖、缺口、hash 与下载审计。
- `ndx100_1d_ma7_rc_y0_events.parquet`、single / three-way / robustness / gap / monotonicity / surface CSV：冻结公式的 Y0 统计结果。
- `ndx100_1d_ma7_rc_y0_cross_market_*.csv`：明确标记 `Nasdaq100CurrentYahoo` 的 Binance 对照表。
- `ndx100_1d_ma7_rc_y0_summary.json`：Y0 机器摘要。

Y0 是 survivorship-biased observation，不得与 historical P0 文件混用。

## Yahoo 历史成分 Y1

- `yahoo-historical-cache/chart/`：Y1 新下载的原始 chart response；下载器同时安全复用 Y0 cache。
- `ndx100_1d_ma7_rc_y1_historical_ticker_universe.csv`：P0 membership 的 `252` ticker 历史并集。
- `ndx100_1d_ma7_rc_y1_yahoo_ticker_prices.parquet` 与 `...fetch_audit.json`：Yahoo 返回的 split-only 日线与逐 ticker 请求审计。
- `ndx100_1d_ma7_rc_y1_member_price_mapping.parquet`：每个 PIT member-day 的 direct / unique entity lineage / missing 映射。
- `ndx100_1d_ma7_rc_y1_coverage_by_membership_ticker.csv`、`...coverage_by_year.csv`、`...lineage_fallback.csv`、`...missing_member_stock_days.csv`：覆盖与缺口明细。
- `ndx100_1d_ma7_rc_y1_coverage_audit.json`、`...coverage_blocker.json` 与 manifests：`81.18% < 99.5%` 的 fail-closed 机器证据。

Y1 未生成 events 或 expectancy CSV；不得把 Yahoo 的部分退市历史当作完整 point-in-time 研究结果。

## Yahoo 当前成分 Y2：Crypto ATR 路径迁移

- `ndx100_1d_ma7_rc_y2_events.parquet`：使用 Y0 完整价格、按 Crypto P2 同定义生成的 MA5/7/10 events。
- `...atr_path_stats.csv`、`...atr_path_breakout_stats.csv`：ATR-path 五档及 breakout range 交互。
- `...filter_expectancy_stats.csv`、`...filter_counts.csv`：裸 MA7、slope aligned 与 Crypto 外部方向格。
- `...crypto_transfer_incremental_contrasts.csv`：外部格相对同方向其余 MA7/斜率一致事件的双向聚类增量。
- `...vs_historical_rv_*.csv`：ATR path 60 与 RV252 同样本分离度。
- `...crypto_transfer_candidate_robustness.csv`：年份、QQQ phase、流动性与 MA5/7/10。
- `...cross_market_*.csv`、summary 与 manifest：Crypto/股票直接对照及机器裁决。

Y2 仍是 current-constituent survivorship-biased event study，未形成稳定优化，不是账户策略。

## Yahoo 当前成分 Y3：突破前市场结构图谱

- `ndx100_1d_ma7_rc_y3_events.parquet`：MA7/MA30 双向事件及严格截至 `t-1` 的结构特征。
- `...named_state_membership.parquet`：23 个可解释且可重叠的具名状态成员关系。
- `...baseline_stats.csv`、`...dimension_stats.csv`：裸突破基线与 11 类结构维度分桶。
- `...named_state_stats.csv`、`...named_state_contrasts.csv`：各状态 expectancy 及相对其余同 trigger/方向事件的双向聚类增量与 BH-FDR。
- `...named_state_ranking_20d.csv`：带年度正增量占比的 20D 排名。
- `...named_state_robustness.csv`：10/20/40D、分年、QQQ phase 与绝对 gap 1%/2%/3% 排除诊断。
- `...event_topology_stats.csv`、summary 与 manifest：MA7/MA30 同时跨越、机器裁决和文件哈希。

Y3 不含 ML 或个股横截面相对强弱。它仍是 current-constituent survivorship-biased 全样本假设图谱，不是策略或独立样本验证。

## key 与 entitlement 通过后才允许生成

- `massive-cache/`：task-local untrusted Massive response cache，不是 canonical normalized data lake。
- `identifier_map.csv`、`ticker_events.csv`、identifier/price audits。
- `events.parquet`、regime edges、single-variable/three-way/robustness/gap/monotonicity/surface CSV。
- cross-market native-history long/wide tables、基于 Binance 首末事件日的 common-window wide tables 与 P0 summary。

缺股票端时不得创建空 CSV 或伪造 NaN 行；阻塞状态只写 JSON。
