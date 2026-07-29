# Artifacts

2026-07-14 基线保留：

- [hype-15m-mhef-baseline-2026-07-14-summary.json](hype-15m-mhef-baseline-2026-07-14-summary.json)：配置、质量门、全区间指标与 recent slices。
- [hype-15m-mhef-baseline-2026-07-14-forecasts.csv](hype-15m-mhef-baseline-2026-07-14-forecasts.csv)：四条 forecast 与组合 forecast 路径。
- [hype-15m-mhef-baseline-2026-07-14-paths.csv](hype-15m-mhef-baseline-2026-07-14-paths.csv)：各运行的仓位、换手、资金费与权益路径。

结论入口见 [基线回测报告](../notes/hype-15m-mhef-baseline-backtest-2026-07-14.md)。

## 2026-07-28 V2 连续目标仓位

- [hype_15m_mhef_v2_dataset_freeze.json](hype_15m_mhef_v2_dataset_freeze.json)：数据质量、时间边界、基线配置与 hash。
- [hype_15m_mhef_v2_full_ablation.csv](hype_15m_mhef_v2_full_ablation.csv)：`17` 组组件/slot 消融。
- [hype_15m_mhef_v2_parameter_sensitivity.csv](hype_15m_mhef_v2_parameter_sensitivity.csv)：`45` 组逐参数敏感性。
- [hype_15m_mhef_v2_signal_grid.csv](hype_15m_mhef_v2_signal_grid.csv)：`432` 组 development-only 信号搜索。
- [hype_15m_mhef_v2_execution_grid.csv](hype_15m_mhef_v2_execution_grid.csv)：`480` 组 development-only 执行搜索。
- [hype_15m_mhef_v2_development_summary.json](hype_15m_mhef_v2_development_summary.json)：开发期基线、消融与冻结候选摘要。
- [hype_15m_mhef_v2_prefit_candidate.json](hype_15m_mhef_v2_prefit_candidate.json)：验证前冻结的唯一候选、配置 hash 与揭示状态。
- [hype_15m_mhef_v2_validation_summary.json](hype_15m_mhef_v2_validation_summary.json)：一次性 prefit validation、成本压力、buy-and-hold、bootstrap 与 NO-GO 决策。
- [hype_15m_mhef_v2_candidate_path.parquet](hype_15m_mhef_v2_candidate_path.parquet)：候选逐 K forecast/仓位/换手/funding/cost/equity 路径，终点仅到 `2026-04-28 08:00 UTC`。
- [hype_15m_mhef_v2_candidate_centered_ablation.csv](hype_15m_mhef_v2_candidate_centered_ablation.csv)：冻结候选中心 `71` 组 development-only 全参数消融与逐 K position hash。
- [hype_15m_mhef_v2_candidate_centered_ablation_summary.json](hype_15m_mhef_v2_candidate_centered_ablation_summary.json)：候选中心消融的分组最优、path-equal 与 dominance 摘要。

终局入口见 [V2 连续目标仓位研究](../notes/hype-15m-mhef-v2-continuous-target-research-2026-07-28.md)。
