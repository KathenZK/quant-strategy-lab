# Artifacts

- `binance_1d_ma7dc_data_quality_2026-08-04.json`：源数据与完整 UTC 日线质量审计。
- `binance_1d_ma7dc_daily_states_2026-08-04.csv`：逐日状态与未来标签，仅供复现诊断，不是交易清单。
- `binance_1d_ma7dc_feature_metrics_2026-08-04.csv`：连续特征 IC、bootstrap CI 与分块稳定性。
- `binance_1d_ma7dc_baseline_metrics_2026-08-04.csv`：MA7 方向条件结果相对同方向无条件市场漂移的增量。
- `binance_1d_ma7dc_deviation_quintiles_2026-08-04.csv`：因果 expanding 偏离五分位结果。
- `binance_1d_ma7dc_state_metrics_2026-08-04.csv`：MA7 状态条件结果。
- `binance_1d_ma7dc_block_metrics_2026-08-04.csv`：7 日主 horizon 的四块 baseline、状态与偏离 quintile 稳定性结果，含各块 UTC 范围。
- `binance_1d_ma7dc_recent_slices_2026-08-04.csv`：数据终点锚定的近期切片。
- `binance_1d_ma7dc_gate_summary_2026-08-04.csv`：预声明四门判断。
- `binance_1d_ma7dc_summary_2026-08-04.json`：合同、质量与结论摘要。
- `binance_1d_ma7dc_campaign_swings_2026-08-04.csv`：独立 ATR ZigZag completed swings。
- `binance_1d_ma7dc_campaign_tracks_2026-08-04.csv`：每个 swing 的 MA7 对齐、next-open 进入、退出、捕获与回吐明细。
- `binance_1d_ma7dc_campaign_track_metrics_2026-08-04.csv`：资产、阈值、时长范围以及 cross1/cross2 单次与重入对照汇总。
- `binance_1d_ma7dc_campaign_track_summary_2026-08-04.json`：截图命题的冻结门禁结果。
- `binance_1d_ma7dc_tolerance_exit_tracks_2026-08-04.csv`：三条固定退出臂的逐 swing 单次与重入轨道、hard stop、MFE、回撤和成本明细。
- `binance_1d_ma7dc_tolerance_exit_metrics_2026-08-04.csv`：资产、方向、时长桶和退出臂的固定汇总。
- `binance_1d_ma7dc_tolerance_exit_recent_slices_2026-08-04.csv`：按数据终点锚定的 `1d/7d/1m/3m/6m/1y` entry 切片。
- `binance_1d_ma7dc_tolerance_exit_summary_2026-08-04.json`：预声明比较门禁与数据质量摘要。
