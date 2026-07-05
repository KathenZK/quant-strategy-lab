# Artifacts

此目录保存 `TRX-1H-Adaptive-Regime` 的精确两年研究帧、数据质量元数据、合约过滤器快照、搜索排名、交易明细和稳健性审计结果。

非 Markdown 产物默认由 `.gitignore` 忽略，但可由本 family 的脚本确定性重建；持久报告只引用本目录内的正式产物。

本轮主要证据：

- `trx_binance_1h_closed_klines_2y.parquet` / `trx_binance_1h_data_quality_2y.json`
- `trx_1h_adaptive_regime_search_2026-07-03.json` 与 prefit/ranking/slices/trades CSV
- `trx_1h_adaptive_regime_refine_2026-07-03.json` 与 prefit/ranking/slices/trades CSV
- `trx_1h_persistent_regime_boundary_2026-07-03.json/.csv`
- `trx_1h_live_feasibility_2026-07-03.json`
- `trx_1h_ar_v1base_full_ablation_2026-07-03.json`、`trx_1h_ar_v1base_full_ablation_rows_2026-07-03.csv`、`trx_1h_ar_v1base_full_ablation_fields_2026-07-03.csv`
- `trx_1h_ar_v2_strict_ablation_slices_2026-07-03.json`、`trx_1h_ar_v2_strict_ablation_rows_2026-07-03.csv`、`trx_1h_ar_v2_strict_ablation_fields_2026-07-03.csv`、`trx_1h_ar_v2_strict_slices_2026-07-03.csv`、`trx_1h_ar_v2_trade_execution_audit_2026-07-03.csv`
- `trx_1h_ar_recent_adaptation_search_2026-07-03.json`、`trx_1h_ar_recent_adaptation_ranking_2026-07-03.csv`、`trx_1h_ar_recent_adaptation_slices_2026-07-03.csv`、`trx_1h_ar_recent_adaptation_top_trades_2026-07-03.csv`、`trx_1h_ar_recent_adaptation_trade_audit_2026-07-03.csv`
