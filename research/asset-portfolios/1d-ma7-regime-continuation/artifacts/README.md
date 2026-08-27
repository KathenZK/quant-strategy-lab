# Artifacts

本目录保存 `BIN-1D-MA7-RC-P0R2` 的可复现机器产物。正式运行已生成并校验：

- 数据质量审计与历史 universe inventory；
- eligible daily panel 与 MA5/7/10 event panel；
- 单变量统计、三维 conditional expectancy、稳健性切片与表面诊断 CSV；
- machine-readable summary JSON、SHA256 manifest 与交互式 HTML dashboard。

主要入口：

- `binance_1d_ma7_rc_p0_summary.json`：machine summary；
- `binance_1d_ma7_rc_p0_interactive_dashboard.html`：交互式单变量与三维表；
- `binance_1d_ma7_rc_p0_{single_variable,three_way,robustness,surface_diagnostics}_stats.csv`：统计表；
- `binance_1d_ma7_rc_p0_events.parquet`：可复算事件 panel；完整 daily feature panel 属可再生成本地数据，不作为 durable artifact；
- `binance_1d_ma7_rc_p0_artifact_manifest.json`：文件 SHA256 与大小。

产物只服务 historical diagnostic，不构成策略注册、promotion 或 live-readiness 证据。

P1 新增：

- `binance_1d_ma7_rc_p1_ma_neighborhood_unconditional_stats.csv`：MA5/7/10 × 固定期限完整统计；
- `binance_1d_ma7_rc_p1_state_volatility_stats.csv`：四状态 × RV 五档统计；
- `binance_1d_ma7_rc_p1_filter_expectancy_stats.csv`：预声明过滤层 conditional expectancy；
- `binance_1d_ma7_rc_p1_filter_liquidity_stats.csv`：动态 Top20 / long-tail 稳健性；
- `binance_1d_ma7_rc_p1_{event_filter_counts,regime_event_counts,frequency_stats,frequency_timeseries}.csv`：过滤前后次数与日/周/月频率；
- `binance_1d_ma7_rc_p1_{summary,artifact_manifest}.json`：机器摘要与哈希清单。

P2 新增：

- `binance_1d_ma7_rc_p2_events.parquet`：不继承 RV252 eligibility、按 60-observation ATR path 重建的 MA5/7/10 事件；
- `binance_1d_ma7_rc_p2_{atr_path_stats,atr_path_breakout_stats}.csv`：ATR 路径五档及其与突破日 weak/normal/burst 的交叉统计；
- `binance_1d_ma7_rc_p2_{filter_expectancy_stats,filter_counts,frequency_stats,frequency_timeseries}.csv`：过滤层收益、样本和信号频率；
- `binance_1d_ma7_rc_p2_vs_historical_rv_{stats,diagnostics}.csv`：共同样本上的 ATR path 60 与 historical RV252 对比；
- `binance_1d_ma7_rc_p2_{robustness_stats,opposite_cells_robustness}.csv`：年份、BTC 阶段、流动性与 MA 邻域检查；后者明确为 outcome-exposed descriptive cells；
- `binance_1d_ma7_rc_p2_{summary,artifact_manifest}.json`：机器摘要与 SHA256 清单。

P3 新增：

- `binance_1d_ma7_rc_p3_data_sync_manifest.json`：2026-07 Vision checksum 归档与 2026-08 API 增量同步清单；
- `binance_1d_ma7_rc_p3_data_quality_audit.json`：60.27M 根 priority-union 15m K、完整 UTC 日聚合与 gap 审计；
- `binance_1d_ma7_rc_p3_events.parquet`：资产自身 observed-session 口径的 MA5/7/10 事件、可执行 next-open 标签与本地/leave-one-out breadth 特征；
- `binance_1d_ma7_rc_p3_fixed_rule_{stats,frequency,robustness}.csv`：固定规则、信号频率和方向/年份/资产切片；
- `binance_1d_ma7_rc_p3_ml_{predictions,metrics,score_quintiles,feature_importance}.*`：Logistic 与 LightGBM 的 expanding walk-forward / locked-confirmation 产物；
- `binance_1d_ma7_rc_p3_account_{metrics,equity,trades}.*`：最多五仓、双边成本、归零 fail-stop 的账户诊断；不含 funding；
- `binance_1d_ma7_rc_p3_{summary,artifact_manifest}.json`：`NO-GO` 机器裁决与 SHA256 清单。
