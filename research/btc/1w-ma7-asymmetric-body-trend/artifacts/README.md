# Artifacts

本目录保留 `BTC-1W-MA7-Asymmetric-Body-Trend` 的周线零调参迁移证据：

- [机器摘要](btc_1w_ma7_v1_transfer_summary_2026-08-05.json)：数据质量、引擎适配、两种时间合同、相位与稳定性。
- [指标表](btc_1w_ma7_v1_transfer_metrics_2026-08-05.csv)：主相位的 combined / long-only / short-only、成本与延迟。
- [近期切片](btc_1w_ma7_v1_transfer_recent_2026-08-05.csv)：`1d/7d/1m/3m/6m/1y`。
- [相位审计](btc_1w_ma7_v1_transfer_phase_2026-08-05.csv)：周一 `0h` 与半周偏移 `84h`。
- [滚动 26 周](btc_1w_ma7_v1_transfer_rolling_26w_2026-08-05.csv)：每 `13w` 前进。
- [交易明细](btc_1w_ma7_v1_transfer_trades_2026-08-05.csv)：两种时间合同的多空逐笔。
- [Bar-transfer 路径](btc_1w_ma7_v1_transfer_bar_transfer_path_2026-08-05.csv)与[Clock-equivalent 路径](btc_1w_ma7_v1_transfer_clock_equivalent_path_2026-08-05.csv)。

原始 `1h` OHLCV 与 funding 继续由统一数据湖管理，本目录不复制市场数据。
