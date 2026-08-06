# Artifacts

本目录保留 `MU-1D-MA7-Separated-Trend-Transfer` 的双市场零调参证据：

- [机器摘要](mu_1d_ma7_dual_market_transfer_summary_2026-08-05.json)：两 route 的合同、数据质量、窗口、相位和稳定性。
- [窗口指标](mu_1d_ma7_dual_market_transfer_metrics_2026-08-05.csv)：full available 与共同日历窗口。
- [近期切片](mu_1d_ma7_dual_market_transfer_recent_2026-08-05.csv)：combined / long-only / short-only；数据不足的窗口不伪报。
- [Binance 相位审计](mu_1d_ma7_dual_market_transfer_phase_2026-08-05.csv)：`0h/12h` 日界线。
- [滚动 90 日](mu_1d_ma7_dual_market_transfer_rolling_90d_2026-08-05.csv)：双市场稳定性窗口。
- [完整交易](mu_1d_ma7_dual_market_transfer_trades_2026-08-05.csv)：按 market 与 variant 标记。
- [双市场日线对齐](mu_1d_ma7_dual_market_transfer_daily_alignment_2026-08-05.csv)：同日历日期的 close 与收益对齐。
- [Binance 组合路径](mu_1d_ma7_dual_market_transfer_binance_path_2026-08-05.csv)与[Nasdaq 组合路径](mu_1d_ma7_dual_market_transfer_nasdaq_path_2026-08-05.csv)。

原始数据继续由统一数据湖管理，本目录不复制市场数据。

## Binance 剔除周末

- [机器摘要](mu_1d_ma7_binance_weekday_filter_summary_2026-08-05.json)：原始、字面删除与可执行 weekday-signal 三种口径。
- [窗口指标](mu_1d_ma7_binance_weekday_filter_metrics_2026-08-05.csv)：全窗口和 Nasdaq 共同窗口。
- [相位审计](mu_1d_ma7_binance_weekday_filter_phase_2026-08-05.csv)：`0h/12h` 多空对比。
- [交易明细](mu_1d_ma7_binance_weekday_filter_trades_2026-08-05.csv)：三种口径的逐笔变化。
