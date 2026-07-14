# Artifacts

此目录保存 BTC 1h 数据质量、搜索排名、交易明细、切片和审计输出。大体积生成物默认由 `.gitignore` 忽略，但均可由 `scripts/` 复现。

2026-07-02 核心证据：

- `btc_1h_ar_v1_config_2026-07-02.json`
- `btc_1h_ar_v1_full_ablation_2026-07-02.json`
- `btc_1h_ar_v1_full_ablation_rows_2026-07-02.csv`
- `btc_1h_ar_v1_full_ablation_fields_2026-07-02.csv`
- `btc_1h_ar_v1_clean_config_2026-07-02.json`
- `btc_1h_ar_v1_clean_tune_2026-07-02.json`
- `btc_1h_ar_v1_tune_keltner_pool_2026-07-02.csv`
- `btc_1h_ar_v1_tune_cci_pool_2026-07-02.csv`
- `btc_1h_ar_v1_tune_pairs_2026-07-02.csv`
- `btc_1h_ar_v1_tune_selected_trades_2026-07-02.csv`
- `btc_1h_ar_v1_scaled_frontier_audit_2026-07-02.json`
- `btc_1h_ar_v1_scaled_frontier_neighborhood_2026-07-02.csv`
- `btc_1h_ar_v1_scaled_frontier_monthly_2026-07-02.csv`
- `btc_1h_ar_v1_scaled_frontier_trades_2026-07-02.csv`
- `btc_binance_1h_data_quality_2y.json`
- `btc_1h_adaptive_regime_search_2026-07-02.json`
- `btc_1h_adaptive_regime_prefit_2026-07-02.csv`
- `btc_1h_adaptive_regime_ranking_2026-07-02.csv`
- `btc_1h_adaptive_regime_boundary_audit_2026-07-02.json`
- `btc_1h_adaptive_regime_audit_scenarios_2026-07-02.csv`
- `btc_1h_adaptive_regime_neighborhood_2026-07-02.csv`
- `btc_1h_adaptive_regime_monthly_2026-07-02.csv`

2026-07-06 V2 全参数消融证据：

- `btc_1h_ar_v2_full_ablation_2026-07-06.json`
- `btc_1h_ar_v2_full_ablation_rows_2026-07-06.csv`
- `btc_1h_ar_v2_full_ablation_fields_2026-07-06.csv`

2026-07-06 V2 微调观察证据：

- `btc_1h_ar_v2_micro_tune_2026-07-06.json`
- `btc_1h_ar_v2_micro_tune_grid_2026-07-06.csv`
- `btc_1h_ar_v2_micro_tune_selected_trades_2026-07-06.csv`

2026-07-06 V3 冻结配置、全参数消融与多窗口回测证据：

- `btc_1h_ar_v3_config_2026-07-06.json`
- `btc_1h_ar_v3_full_ablation_2026-07-06.json`
- `btc_1h_ar_v3_full_ablation_rows_2026-07-06.csv`
- `btc_1h_ar_v3_full_ablation_fields_2026-07-06.csv`
- `btc_1h_ar_v3_window_backtest_2026-07-06.json`
- `btc_1h_ar_v3_window_backtest_windows_2026-07-06.csv`
- `btc_1h_ar_v3_window_backtest_trades_2026-07-06.csv`

2026-07-07 V3 参数必要性审计与最小表面微调证据：

- `btc_1h_ar_v3_param_necessity_2026-07-07.json`
- `btc_1h_ar_v3_minimal_micro_tune_2026-07-07.json`
- `btc_1h_ar_v3_minimal_micro_tune_grid_2026-07-07.csv`
- `btc_1h_ar_v3_minimal_micro_tune_selected_trades_2026-07-07.csv`

2026-07-07 V4 最小等价干净参数与多窗口回测证据：

- `btc_1h_ar_v4_config_2026-07-07.json`
- `btc_1h_ar_v4_window_backtest_2026-07-07.json`
- `btc_1h_ar_v4_window_backtest_windows_2026-07-07.csv`
- `btc_1h_ar_v4_window_backtest_trades_2026-07-07.csv`

2026-07-10 V4 新腿增量与结构优化证据：

- `btc_1h_ar_v4_new_leg_increment_2026-07-10.json`
- `btc_1h_ar_v4_new_leg_increment_rows_2026-07-10.csv`

2026-07-13 V4 结构优化顺序验证证据：

- `btc_1h_ar_v4_structural_trials_2026-07-13.json`
- `btc_1h_ar_v4_structural_trials_rows_2026-07-13.csv`

本轮没有通过 gate 的新增腿，三态 router 按停止条件跳过，因此不生成 router CSV。
