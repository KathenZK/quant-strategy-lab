# 研究产物

本目录保存 `HYPE-15M-Multi-Indicator-Intraday` 被 Markdown 报告引用、或复现结论所需的 JSON/CSV 证据。

## 保留证据

- `hype_15m_mii_search_summary.json`、`hype_15m_mii_search_ranking.csv`、`hype_15m_mii_search_top_trades.csv`：首次广泛搜索证据。
- `hype_15m_mii_full_ablation_2026-06-26.json`、`hype_15m_mii_full_ablation_summary_2026-06-26.csv`、`hype_15m_mii_full_ablation_validation_slices_2026-06-26.csv`、`hype_15m_mii_full_ablation_rolling_2026-06-26.csv`、`hype_15m_mii_full_ablation_weekly_2026-06-26.csv`、`hype_15m_mii_full_ablation_monthly_2026-06-26.csv`：旧 cache 口径消融与时间切片证据。
- `hype_15m_mii_surface_combo_optimization_2026-06-26.json`、`hype_15m_mii_surface_combo_optimization_summary_2026-06-26.csv`、`hype_15m_mii_surface_combo_optimization_slices_2026-06-26.csv`、`hype_15m_mii_surface_combo_optimization_rolling_2026-06-26.csv`、`hype_15m_mii_surface_combo_optimization_monthly_2026-06-26.csv`：表面改善参数组合优化证据。
- `hype_15m_mii_v1_full_ablation_2026-06-29.json`、`hype_15m_mii_v1_full_ablation_summary_2026-06-29.csv`、`hype_15m_mii_v1_full_ablation_slices_2026-06-29.csv`、`hype_15m_mii_v1_full_ablation_rolling_2026-06-29.csv`、`hype_15m_mii_v1_full_ablation_weekly_2026-06-29.csv`、`hype_15m_mii_v1_full_ablation_monthly_2026-06-29.csv`：V1 标准数据湖复现、可执行时序修正与全参数消融证据。
- `hype_15m_mii_clean_evolution_2026-06-29.json`、`hype_15m_mii_clean_evolution_ranking_2026-06-29.csv`、`hype_15m_mii_clean_evolution_pareto_2026-06-29.csv`、`hype_15m_mii_clean_evolution_slices_2026-06-29.csv`：删除 dormant 参数后的干净参数演化证据。
- `hype_15m_mii_delay_aware_selection_2026-06-29.json`、`hype_15m_mii_delay_aware_ranking_2026-06-29.csv`：K+2 延迟联合筛选证据。
- `hype_15m_mii_v11_lead_robustness_2026-06-29.json`、`hype_15m_mii_v11_lead_neighborhood_2026-06-29.csv`、`hype_15m_mii_v11_lead_stress_2026-06-29.csv`、`hype_15m_mii_v11_lead_monthly_2026-06-29.csv`、`hype_15m_mii_v11_lead_rolling90_2026-06-29.csv`：V1.1 干净领先诊断版邻域、成本、延迟、方向和时间窗口压力证据。
- `hype_15m_mii_relaxed_dd_selection_2026-06-30.json`、`hype_15m_mii_relaxed_dd_exposure_ladder_2026-06-30.csv`：接受更大回撤后的高收益/高胜率诊断选择与暴露阶梯证据。
- `hype_15m_mii_fast_validation_ranking_2026-06-30.json`、`hype_15m_mii_fast_validation_ranking_2026-06-30.csv`：面向小额快速验证的频率/收益/回撤/胜率/Last90/K+2 综合排名证据。
- `hype_15m_mii_balanced_leverage_stress_2026-06-30.json`、`hype_15m_mii_balanced_leverage_stress_2026-06-30.csv`：放弃频率后的均衡观察版本 `1.75x/2x/3x` 暴露阶梯与 K+1/K+2 压力测试证据。
