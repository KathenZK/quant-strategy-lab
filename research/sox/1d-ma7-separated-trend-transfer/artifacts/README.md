# Artifacts

本目录保留 `SOX-1D-MA7-Separated-Trend-Transfer` 的 Yahoo 数据与回测证据：

- [Yahoo 原始响应](sox_yahoo_chart_1d_raw_2026-08-05.json)：`^SOX` chart API 完整日线响应。
- [标准化日线](sox_yahoo_1d_normalized_2026-08-05.csv)：session date、UTC timestamp、OHLC、volume、adjusted close。
- [机器摘要](sox_1d_ma7_v1_transfer_summary_2026-08-05.json)：来源、SHA256、数据质量、参数、窗口与稳定性。
- [指标表](sox_1d_ma7_v1_transfer_metrics_2026-08-05.csv)：全历史和 HYPE 日历重叠窗口。
- [近期切片](sox_1d_ma7_v1_transfer_recent_2026-08-05.csv)：combined / long-only / short-only 的 `1d/7d/1m/3m/6m/1y`。
- [逐年窗口](sox_1d_ma7_v1_transfer_calendar_years_2026-08-05.csv)与[滚动三年](sox_1d_ma7_v1_transfer_rolling_3y_2026-08-05.csv)。
- [完整交易](sox_1d_ma7_v1_transfer_trades_2026-08-05.csv)与[组合权益路径](sox_1d_ma7_v1_transfer_path_2026-08-05.csv)。

## SMA5 替换

- [机器摘要](sox_1d_sma5_substitution_summary_2026-08-05.json)与[指标表](sox_1d_sma5_substitution_metrics_2026-08-05.csv)。
- [近期切片](sox_1d_sma5_substitution_recent_2026-08-05.csv)、[逐年窗口](sox_1d_sma5_substitution_calendar_years_2026-08-05.csv)与[滚动三年](sox_1d_sma5_substitution_rolling_3y_2026-08-05.csv)。
- [SMA5 交易](sox_1d_sma5_substitution_trades_2026-08-05.csv)与[SMA5 组合路径](sox_1d_sma5_substitution_path_2026-08-05.csv)。
