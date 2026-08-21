# Artifacts

本目录保留 BTC/ETH 固定 MA7 分资产与共享参数搜索证据：

- [最近1至4年策略横向排名](binance_btceth_recent_horizon_ranking_2026-08-13.csv) · [跨窗口摘要](binance_btceth_recent_horizon_ranking_2026-08-13_summary.csv) · [机器摘要](binance_btceth_recent_horizon_ranking_2026-08-13.json)。

- [机器摘要](binance_btc_eth_1d_ma7_asset_specific_search_summary_2026-08-05.json)：合同、数据质量、固定参数及 development / holdout / full 审计。
- [单边候选前沿](binance_btc_eth_1d_ma7_asset_specific_search_frontier_2026-08-05.csv)。
- [组合候选](binance_btc_eth_1d_ma7_asset_specific_search_pairs_2026-08-05.csv)。
- [窗口、成本与延迟指标](binance_btc_eth_1d_ma7_asset_specific_search_metrics_2026-08-05.csv)。
- [日界相位](binance_btc_eth_1d_ma7_asset_specific_search_phase_2026-08-05.csv)。
- [滚动 180 日](binance_btc_eth_1d_ma7_asset_specific_search_rolling_180d_2026-08-05.csv)。
- [近期切片](binance_btc_eth_1d_ma7_asset_specific_search_recent_2026-08-05.csv)。
- [逐笔交易](binance_btc_eth_1d_ma7_asset_specific_search_trades_2026-08-05.csv)。
- 六份 `*_path_2026-08-05.csv`：三组选择分别应用到 BTC/ETH 的完整 combined 权益路径。

## 共享参数 HYPE control

- [机器摘要](binance_ma7_shared_params_on_hype_summary_2026-08-05.json)
- [指标表](binance_ma7_shared_params_on_hype_metrics_2026-08-05.csv)
- [相位审计](binance_ma7_shared_params_on_hype_phase_2026-08-05.csv)
- [滚动 90 日](binance_ma7_shared_params_on_hype_rolling_90d_2026-08-05.csv)
- [近期切片](binance_ma7_shared_params_on_hype_recent_2026-08-05.csv)
- [逐笔交易](binance_ma7_shared_params_on_hype_trades_2026-08-05.csv)
- [组合路径](binance_ma7_shared_params_on_hype_path_2026-08-05.csv)
- [fresh aligned机器证据](binance_ma7_shared_params_on_hype_fresh_aligned_2026-08-12.json)：对齐当前 HYPE fresh API 窗口，完整日 `438d` 复算。
- [fresh aligned指标表](binance_ma7_shared_params_on_hype_fresh_aligned_2026-08-12_metrics.csv)
- [fresh aligned近期切片](binance_ma7_shared_params_on_hype_fresh_aligned_2026-08-12_recent.csv)
- [fresh aligned逐笔交易](binance_ma7_shared_params_on_hype_fresh_aligned_2026-08-12_trades.csv)
- [fresh aligned组合路径](binance_ma7_shared_params_on_hype_fresh_aligned_2026-08-12_path.csv)
- [fresh aligned SHA256](binance_ma7_shared_params_on_hype_fresh_aligned_2026-08-12.sha256)
- [BTC HYPE-aligned机器证据](binance_ma7_shared_params_on_btc_hype_aligned_2026-08-12.json)
- [ETH HYPE-aligned机器证据](binance_ma7_shared_params_on_eth_hype_aligned_2026-08-12.json)
- [BTC/ETH HYPE-aligned SHA256](binance_ma7_shared_params_btc_eth_hype_aligned_2026-08-12.sha256)
- [BTC V1交易路径](binance_ma7_shared_params_v1_btc_trade_path_2026-08-12.html)
- [ETH V1交易路径](binance_ma7_shared_params_v1_eth_trade_path_2026-08-12.html)
- [V1交易路径 SHA256](binance_ma7_shared_params_v1_trade_paths_2026-08-12.sha256)

## V2（P2-C parent）

- [机器摘要](binance_1d_ma7_as_search_v2_2026-08-17.json)
- [窗口/压力/近期切片指标](binance_1d_ma7_as_search_v2_2026-08-17_metrics.csv)
- [逐笔交易](binance_1d_ma7_as_search_v2_2026-08-17_trades.csv)
- [组合路径](binance_1d_ma7_as_search_v2_2026-08-17_path.csv)
- [BTC V2交易路径](binance_1d_ma7_as_search_v2_btc_trade_path_2026-08-17.html)
- [ETH V2交易路径](binance_1d_ma7_as_search_v2_eth_trade_path_2026-08-17.html)
- [V2交易路径 SHA256](binance_1d_ma7_as_search_v2_trade_paths_2026-08-17.sha256)

## 平多即反手空诊断

- [机器摘要](binance_ma7_long_exit_short_reversal_2026-08-06_summary.json)
- [窗口、压力与延迟指标](binance_ma7_long_exit_short_reversal_2026-08-06_metrics.csv)
- [逐笔交易与入场来源](binance_ma7_long_exit_short_reversal_2026-08-06_trades.csv)
- [近期切片](binance_ma7_long_exit_short_reversal_2026-08-06_recent.csv)
- [相位检查](binance_ma7_long_exit_short_reversal_2026-08-06_phase.csv)

原始 `1h` OHLCV 与 funding 由统一数据湖管理，本目录不复制市场数据。
