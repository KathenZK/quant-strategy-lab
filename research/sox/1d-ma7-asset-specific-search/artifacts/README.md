# Artifacts

本目录保留 `SOX-1D-MA7-Asset-Specific-Search` 的机器证据：

- [机器摘要](sox_1d_ma7_asset_specific_search_summary_2026-08-05.json)：数据、来源 hash、共享控制、搜索合同、参数与四类时间窗口。
- [候选前沿](sox_1d_ma7_asset_specific_search_frontier_2026-08-05.csv)：development 稳健性排名前 `120` 的 long / short 配置。
- [多空配对](sox_1d_ma7_asset_specific_search_pairs_2026-08-05.csv)：前 `20 × 20` 配对的 development 排名。
- [窗口指标](sox_1d_ma7_asset_specific_search_metrics_2026-08-05.csv)：backward、development、exposed holdout、full 的 base / friction / delay。
- [逐年窗口](sox_1d_ma7_asset_specific_search_calendar_years_2026-08-05.csv)与[滚动三年](sox_1d_ma7_asset_specific_search_rolling_3y_2026-08-05.csv)。
- [近期切片](sox_1d_ma7_asset_specific_search_recent_2026-08-05.csv)：`1d/7d/1m/3m/6m/1y` audit。
- [完整交易](sox_1d_ma7_asset_specific_search_trades_2026-08-05.csv)。
- 权益路径：[共享参数](sox_1d_ma7_asset_specific_search_btc_eth_shared_zero_tuning_path_2026-08-05.csv) · [SOX combined](sox_1d_ma7_asset_specific_search_sox_development_combined_path_2026-08-05.csv) · [SOX long-only](sox_1d_ma7_asset_specific_search_sox_development_long_only_path_2026-08-05.csv) · [SOX short-only](sox_1d_ma7_asset_specific_search_sox_development_short_only_path_2026-08-05.csv)。

Yahoo 原始响应由既有 SOX 迁移家族保留，本目录摘要固定其路径与 SHA256，不复制原始数据。

## SMA20 零调参替换

- [机器摘要](sox_1d_ma20_substitution_summary_2026-08-05.json)与[窗口指标](sox_1d_ma20_substitution_metrics_2026-08-05.csv)。
- [逐年窗口](sox_1d_ma20_substitution_calendar_years_2026-08-05.csv)、[滚动三年](sox_1d_ma20_substitution_rolling_3y_2026-08-05.csv)与[近期切片](sox_1d_ma20_substitution_recent_2026-08-05.csv)。
- [完整交易](sox_1d_ma20_substitution_trades_2026-08-05.csv)。
- 权益路径：[MA20 combined](sox_1d_ma20_substitution_sox_ma20_combined_path_2026-08-05.csv) · [MA20 long-only](sox_1d_ma20_substitution_sox_ma20_long_only_path_2026-08-05.csv) · [MA20 short-only](sox_1d_ma20_substitution_sox_ma20_short_only_path_2026-08-05.csv)。
