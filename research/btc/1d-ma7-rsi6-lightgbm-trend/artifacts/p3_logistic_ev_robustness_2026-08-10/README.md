# P3 Logistic-EV 稳健性机器证据

- [机器摘要](p3_development_summary.json)：固定 `1.00%` edge、combined/long/short 门禁、双 edge 压力、bootstrap 和 validation 状态。
- [P3 事件](p3_events.parquet)与[外层 OOS 预测](p3_outer_predictions.parquet)：与 P1/P2 identity 完全一致。
- [主 edge combined 交易](p3_main_edge_combined_trades.parquet)：固定 `1.00%` 下的 `47` 笔诊断交易。
- [candidate trades](p3_candidate_oos_trades.parquet)：完整门禁失败，因此为空。
- [bootstrap 全样本](p3_bootstrap_returns.parquet)：combined/long/short 各 `10,000` 次分层交易抽样。
- [系数稳定性](p3_coefficient_stability.json)、[最终 Logistic-EV 模型](p3_final_logistic_ev_model.json)与[manifest](p3_model_manifest.json)。

结论见[中文诊断](../../diagnostics/btc-1d-ma7-rsi6-logistic-ev-p3-robustness-2026-08-10.md)。P3 失败，validation 未揭示，无候选交易路径 HTML。
