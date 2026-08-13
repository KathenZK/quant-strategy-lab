# P2 Expected-Return 机器证据

- [机器摘要](p2_development_summary.json)：事件一致性、模型消融、nested edge、经济/排序门禁和 validation 封存状态。
- [P2 事件](p2_events.parquet)：与 P1 完全一致的 `449` 个 development 事件。
- [外层 OOS 预测](p2_outer_predictions.parquet)：八个预注册回归/对照模型的 predicted edge、阈值与选择。
- [外层 OOS SHAP](p2_outer_shap.parquet)、[SHAP 汇总](p2_core_shap_summary.csv)与[核心特征分箱](p2_core_feature_dependence.json)。
- [最终 L2 模型](p2_final_lgbm_l2_core_model.txt)与[模型 manifest](p2_final_core_model_manifest.json)。
- [selected OOS trades](p2_selected_oos_trades.parquet)：P2 主模型没有通过完整门禁，因此为空。

结论见[中文诊断](../../diagnostics/btc-1d-ma7-rsi6-lgbm-p2-expected-return-2026-08-10.md)。P2 主模型失败，Logistic-EV 仅是后续 P3 线索；validation 未揭示，无交易路径 HTML。
