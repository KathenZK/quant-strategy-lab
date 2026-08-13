# P1 Pooled Development Artifacts

- [p1_summary.json](p1_summary.json)：三个模型的 temporal / leave-one-asset 路线级 compact 指标与总判定。
- [p1_report.json](p1_report.json)：nested edge、全部 fold、分资产、bootstrap 与 recent slices 完整报告。
- [p1_interpretability.json](p1_interpretability.json)：Logistic 系数稳定性、LightGBM gain 与典型事件。
- [p1_model_states.json](p1_model_states.json)：每折 scaler、系数或 feature gain、mean win/loss 与状态 hash。
- [p1_events.parquet](p1_events.parquet)：冻结的 `2,091` 个 development 事件。
- [p1_outer_predictions.parquet](p1_outer_predictions.parquet)：temporal OOS 与 leave-one-asset + time OOS 预测。

P1 未通过，不生成 trade-path HTML。结论见 [P1 诊断](../../diagnostics/binance-1d-ma7-rsi6-dapml-p1-pooled-development-2026-08-10.md)。
