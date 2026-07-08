# 研究产物

本目录保存 `HYPE-15M-Multi-Indicator-Intraday` 被 Markdown 报告引用、或复现结论所需的 JSON/CSV 证据。

## 保留证据

- `hype_15m_mii_search_summary.json`、`hype_15m_mii_search_ranking.csv`、`hype_15m_mii_search_top_trades.csv`：首次广泛搜索证据。
- `hype_15m_mii_full_ablation_2026-06-26.json`、`hype_15m_mii_full_ablation_summary_2026-06-26.csv`、`hype_15m_mii_full_ablation_validation_slices_2026-06-26.csv`、`hype_15m_mii_full_ablation_rolling_2026-06-26.csv`、`hype_15m_mii_full_ablation_weekly_2026-06-26.csv`、`hype_15m_mii_full_ablation_monthly_2026-06-26.csv`：旧 cache 口径消融与时间切片证据。
- `hype_15m_mii_surface_combo_optimization_2026-06-26.json`、`hype_15m_mii_surface_combo_optimization_summary_2026-06-26.csv`、`hype_15m_mii_surface_combo_optimization_slices_2026-06-26.csv`、`hype_15m_mii_surface_combo_optimization_rolling_2026-06-26.csv`、`hype_15m_mii_surface_combo_optimization_monthly_2026-06-26.csv`：表面改善参数组合优化证据。
- `hype_15m_mii_v1_full_ablation_2026-06-29.json`、`hype_15m_mii_v1_full_ablation_summary_2026-06-29.csv`、`hype_15m_mii_v1_full_ablation_slices_2026-06-29.csv`、`hype_15m_mii_v1_full_ablation_rolling_2026-06-29.csv`、`hype_15m_mii_v1_full_ablation_weekly_2026-06-29.csv`、`hype_15m_mii_v1_full_ablation_monthly_2026-06-29.csv`：V1 标准数据湖复现、可执行时序修正与全参数消融证据。
- `hype_15m_mii_clean_evolution_2026-06-29.json`、`hype_15m_mii_clean_evolution_ranking_2026-06-29.csv`、`hype_15m_mii_clean_evolution_pareto_2026-06-29.csv`、`hype_15m_mii_clean_evolution_slices_2026-06-29.csv`：删除 dormant 参数后的干净参数演化证据。
- `hype_15m_mii_delay_aware_selection_2026-06-29.json`、`hype_15m_mii_delay_aware_ranking_2026-06-29.csv`：K+2 延迟联合筛选证据。
- `hype_15m_mii_v11_lead_robustness_2026-06-29.json`、`hype_15m_mii_v11_lead_neighborhood_2026-06-29.csv`、`hype_15m_mii_v11_lead_stress_2026-06-29.csv`、`hype_15m_mii_v11_lead_monthly_2026-06-29.csv`、`hype_15m_mii_v11_lead_rolling90_2026-06-29.csv`：历史 `V1.1 diagnostic lead` 邻域、成本、延迟、方向和时间窗口压力证据；该临时命名已被当前 `HYPE-15M-MII-V1.1` 主观察基线 supersede。
- `hype_15m_mii_relaxed_dd_selection_2026-06-30.json`、`hype_15m_mii_relaxed_dd_exposure_ladder_2026-06-30.csv`：接受更大回撤后的高收益/高胜率诊断选择与暴露阶梯证据。
- `hype_15m_mii_fast_validation_ranking_2026-06-30.json`、`hype_15m_mii_fast_validation_ranking_2026-06-30.csv`：面向小额快速验证的频率/收益/回撤/胜率/Last90/K+2 综合排名证据。
- `hype_15m_mii_balanced_leverage_stress_2026-06-30.json`、`hype_15m_mii_balanced_leverage_stress_2026-06-30.csv`：放弃频率后的均衡观察版本 `1.75x/2x/3x` 暴露阶梯与 K+1/K+2 压力测试证据。
- `hype_15m_mii_v1_1_window_backtest_2026-06-30.json`、`hype_15m_mii_v1_1_window_backtest_2026-06-30.csv`：`HYPE-15M-MII-V1.1` 最近 `1w/1m/3m/6m/1y/all` 分窗口 K+1 与 K+2 回测证据。
- `hype_15m_mii_v1_1_trade_paths_2026-06-30.html`、`hype_15m_mii_v1_1_trade_paths_2026-06-30.json`、`hype_15m_mii_v1_1_trades_2026-06-30.csv`：`HYPE-15M-MII-V1.1` 逐笔交易路径图、摘要和交易清单；HTML 包含局部 K 线、RSI(7) 与 MACD(12,26,9)。
- `hype_15m_mii_v1_1_dynamic_take_profit_2026-06-30.json`、`hype_15m_mii_v1_1_dynamic_take_profit_ranking_2026-06-30.csv`、`hype_15m_mii_v1_1_dynamic_take_profit_exit_counts_2026-06-30.csv`：`HYPE-15M-MII-V1.1` 动态止盈网格排名、出场原因和摘要证据。
- `hype_15m_mii_v1_2_atr_bracket_exit_2026-06-30.json`、`hype_15m_mii_v1_2_atr_bracket_exit_ranking_2026-06-30.csv`、`hype_15m_mii_v1_2_atr_bracket_exit_counts_2026-06-30.csv`：`HYPE-15M-MII-V1.2` ATR bracket 动态止盈止损网格排名、出场原因和摘要证据。
- `hype_15m_mii_v1_2_window_slice_backtest_2026-06-30.json`、`hype_15m_mii_v1_2_window_slice_backtest_2026-06-30.csv`、`hype_15m_mii_v1_2_window_slice_rolling_2026-06-30.csv`、`hype_15m_mii_v1_2_window_slice_random_2026-06-30.csv`：`HYPE-15M-MII-V1.2` 固定窗口、滚动窗口和随机切片回测证据，包含交易数、收益、回撤、Sharpe/Sortino/Calmar。
- `hype_15m_mii_v1_2_atr_rvol_filter_ablation_2026-06-30.json`、`hype_15m_mii_v1_2_atr_rvol_filter_ablation_2026-06-30.csv`、`hype_15m_mii_v1_2_atr_rvol_filter_ablation_windows_2026-06-30.csv`：`HYPE-15M-MII-V1.2` 分别去掉 `ATR96 >= 0.75%`、`RVOL96 >= 1.0`、以及同时去掉二者的过滤消融证据。
- `hype_15m_mii_v1_2_macd_filter_ablation_2026-06-30.json`、`hype_15m_mii_v1_2_macd_filter_ablation_2026-06-30.csv`：`HYPE-15M-MII-V1.2` 去掉 `MACD(12,26,9)` 方向过滤后的信号漏入与全样本回测质量证据。
- `hype_15m_mii_v1_2_atr_dynamic_leverage_2026-07-01.json`、`hype_15m_mii_v1_2_atr_dynamic_leverage_2026-07-01.csv`、`hype_15m_mii_v1_2_atr_dynamic_leverage_windows_2026-07-01.csv`：`HYPE-15M-MII-V1.2` 固定 `2x`、固定 `2.5x`、固定 `3x`、以及按 `ATR96%` 线性变化的 `2x-3x` 动态杠杆对比证据。
- `hype_15m_mii_v1_3_profit_extension_2026-07-02.json`、`hype_15m_mii_v1_3_profit_extension_2026-07-02.csv`、`hype_15m_mii_v1_3_profit_extension_windows_2026-07-02.csv`：`HYPE-15M-MII-V1.3` 提高 TP、加强 RVOL 后提高 TP、分层止盈、动态 TP 和固定 `2.75x` sizing 的 K+1/K+2 诊断证据。
- `hype_15m_mii_v1_3_signal_drought_2026-07-06.json`、`hype_15m_mii_v1_3_signal_drought_2026-07-06.csv`：`HYPE-15M-MII-V1.3` 近期不开单诊断证据，拆解最近 `24h/72h/7d/15d/30d/90d` 的 RSI raw cross、ATR/RVOL/MACD 过滤和最终信号数。
- `hype_15m_mii_v1_3_trade_timing_atr_2026-07-06.json`、`hype_15m_mii_v1_3_trade_timing_monthly_2026-07-06.csv`、`hype_15m_mii_v1_3_trade_timing_quarter_2026-07-06.csv`、`hype_15m_mii_v1_3_trade_timing_trades_2026-07-06.csv`：`HYPE-15M-MII-V1.3` 开单时间与 ATR96 诊断证据，包含月度/季度/逐笔开单和入场 `ATR96%` 分布。
- `hype_15m_mii_v1_3_min_atr_grid_2026-07-06.json`、`hype_15m_mii_v1_3_min_atr_grid_fixed_2026-07-06.csv`、`hype_15m_mii_v1_3_min_atr_grid_rolling_2026-07-06.csv`、`hype_15m_mii_v1_3_min_atr_grid_rolling_summary_2026-07-06.csv`、`hype_15m_mii_v1_3_min_atr_grid_recent_api_2026-07-06.csv`：`HYPE-15M-MII-V1.3` `min_atr_pct96=50/55/60/65/70/75 bps` 网格诊断证据，包含标准数据湖固定窗口、滚动窗口和 current Binance API 最近窗口。
- `hype_15m_mii_v1_3_recent_trade_frequency_2026-07-08.json`、`hype_15m_mii_v1_3_recent_trade_frequency_weekly_2026-07-08.csv`、`hype_15m_mii_v1_3_recent_trade_frequency_windows_2026-07-08.csv`、`hype_15m_mii_v1_3_recent_trade_frequency_trades_2026-07-08.csv`：`HYPE-15M-MII-V1.3` current Binance API 最近 `90d` 周度开单频率、固定窗口频率和逐笔交易证据。
- `hype_15m_mii_v1_3_micro_tune_2026-07-08.json`、`hype_15m_mii_v1_3_micro_tune_full_2026-07-08.csv`、`hype_15m_mii_v1_3_micro_tune_windows_2026-07-08.csv`、`hype_15m_mii_v1_3_micro_tune_rolling_2026-07-08.csv`：`HYPE-15M-MII-V1.3` 提频微调网格证据（`126` 配置 K+1/K+2 全样本、分窗口和 `rvol0.9` 候选滚动对比）。
- `hype_15m_mii_v1_1_btc_eth_cross_asset_2026-06-30.json`、`hype_15m_mii_v1_1_btc_eth_cross_asset_2026-06-30.csv`：`HYPE-15M-MII-V1.1` 直接套用 Binance USD-M `BTCUSDT`、`ETHUSDT` `15m` API 数据的跨资产诊断证据；不是标准数据湖 promotion 证据。
