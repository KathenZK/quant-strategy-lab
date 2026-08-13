# Artifacts

本目录保留 `BTC-1D-Qingze-Critical-Point-Trend` 基线诊断证据：

- [机器摘要](btc_1d_qingze_critical_point_summary_2026-08-07.json)：合同、数据质量、变体指标与产物清单。
- [变体指标](btc_1d_qingze_critical_point_metrics_2026-08-07.csv)：SMA55/60、A/B 与加码对照。
- [近期切片](btc_1d_qingze_critical_point_recent_2026-08-07.csv)：主基线最近 `1d/7d/1m/3m/6m/1y`。
- [逐笔交易](btc_1d_qingze_critical_point_trades_2026-08-07.csv)：11 个完整 campaign。
- [逐次成交事件](btc_1d_qingze_critical_point_events_2026-08-07.csv)：入场、加码与退出 fills。
- [完整路径](btc_1d_qingze_critical_point_path_2026-08-07.csv)：OHLC、SMA、信号、stop、仓位与净值。
- [交互交易路径图](btc_1d_qingze_critical_point_trade_path_2026-08-07.html)：完整 K 线、SMA、净值、入出场连线与交易表。

参数搜索与锁定验证证据：

- [搜索机器摘要](btc_1d_qingze_parameter_search_summary_2026-08-07.json)：切分、搜索空间、rank 1、基线与锁定 validation。
- [20,000 组候选](btc_1d_qingze_parameter_search_candidates_2026-08-07.csv)与[Development Top 100](btc_1d_qingze_parameter_search_frontier_2026-08-07.csv)。
- [Top 20 锁定验证](btc_1d_qingze_parameter_search_validation_2026-08-07.csv)：只作邻域诊断，不用于重选 rank 1。
- [Rank 1 development 交易](btc_1d_qingze_parameter_search_selected_development_trades_2026-08-07.csv)。
- [Rank 1 validation 交易](btc_1d_qingze_parameter_search_selected_validation_trades_2026-08-07.csv)、[成交事件](btc_1d_qingze_parameter_search_selected_validation_events_2026-08-07.csv)与[完整路径](btc_1d_qingze_parameter_search_selected_validation_path_2026-08-07.csv)。
- [Rank 1 validation 近期切片](btc_1d_qingze_parameter_search_selected_validation_recent_2026-08-07.csv)：`1d/7d/1m/3m/6m`；validation 短于一年。
- [Rank 1 validation 交互图](btc_1d_qingze_parameter_search_selected_validation_trade_path_2026-08-07.html)。

可信小时 OHLCV、funding 与有限 open-interest 分区继续由统一数据湖管理，本目录不复制市场数据。
