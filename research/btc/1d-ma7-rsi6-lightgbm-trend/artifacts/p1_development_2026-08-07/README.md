# P1 Development 机器证据

- [机器摘要](p1_development_summary.json)：数据、成本、事件、模型消融、nested 阈值、门禁与 validation 封存状态。
- [事件与标签](p1_events.parquet)：`449` 个完整 development MA7 穿越事件。
- [外层 OOS 预测](p1_outer_predictions.parquet)：六个预注册模型/特征组的四折概率和阈值。
- [外层 OOS SHAP](p1_outer_shap.parquet)与[SHAP 汇总](p1_core_shap_summary.csv)。
- [核心特征分箱](p1_core_feature_dependence.json)与[最终树 split](p1_final_core_split_thresholds.json)。
- [最终 development 模型](p1_final_core_model.txt)与[模型 manifest](p1_final_core_model_manifest.json)。
- [selected OOS trades](p1_selected_oos_trades.parquet)：P1 门禁下为 `0` 笔，保留空表证明没有把空仓包装为候选。

结论见[中文诊断](../../diagnostics/btc-1d-ma7-rsi6-lgbm-p1-development-2026-08-07.md)。P1 失败，validation 未揭示，无交易路径 HTML。
