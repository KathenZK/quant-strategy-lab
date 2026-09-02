# Artifacts

本目录保留 `BIN-1D-MA7-CTP` 的机器可审计事件表与条件概率格子。

- [binance_1d_ma7_ctp_events_2026-08-31.csv](binance_1d_ma7_ctp_events_2026-08-31.csv)：逐笔穿越事件、斜率、放量、7/30/60/90 日路径和前瞻标签。
- [binance_1d_ma7_ctp_rates_2026-08-31.csv](binance_1d_ma7_ctp_rates_2026-08-31.csv)：分样本、分币、分方向、分过滤器的发生率与 Wilson 区间。
- [binance_1d_ma7_ctp_path_rates_2026-08-31.csv](binance_1d_ma7_ctp_path_rates_2026-08-31.csv)：上涨/回撤比、最大回撤、最大上涨和价格位置分桶。
- [binance_1d_ma7_ctp_summary_2026-08-31.json](binance_1d_ma7_ctp_summary_2026-08-31.json)：数据质量、事件计数和裁决摘要。
- [binance_1d_ma7_ctp_all_market_events_2026-08-31.parquet](binance_1d_ma7_ctp_all_market_events_2026-08-31.parquet)：全市场逐笔穿越事件。
- [binance_1d_ma7_ctp_all_market_rates_2026-08-31.csv](binance_1d_ma7_ctp_all_market_rates_2026-08-31.csv)：全市场过滤发生率。
- [binance_1d_ma7_ctp_all_market_path_rates_2026-08-31.csv](binance_1d_ma7_ctp_all_market_path_rates_2026-08-31.csv)：全市场路径分桶。
- [binance_1d_ma7_ctp_all_market_symbol_rates_2026-08-31.csv](binance_1d_ma7_ctp_all_market_symbol_rates_2026-08-31.csv)：分币裸穿越发生率。
- [binance_1d_ma7_ctp_all_market_quality_2026-08-31.json](binance_1d_ma7_ctp_all_market_quality_2026-08-31.json)：入选/剔除与完整日质量。
- [binance_1d_ma7_ctp_all_market_summary_2026-08-31.json](binance_1d_ma7_ctp_all_market_summary_2026-08-31.json)：全市场宇宙与裁决摘要。
- [binance_1d_ma7_ctp_hype_vs_universe_2026-08-31.json](binance_1d_ma7_ctp_hype_vs_universe_2026-08-31.json)：HYPE 相对全市场、同窗口和上市队列的对照摘要。P1 未读取该文件。

## P1 Cross-Conditioned Entry-Value Modeling

- [binance_1d_ma7_ctp_p1_feature_spec.json](binance_1d_ma7_ctp_p1_feature_spec.json)：读标签前冻结的 T1/T0 特征块与 F0–F3 方案。
- [binance_1d_ma7_ctp_p1_contract_lock.json](binance_1d_ma7_ctp_p1_contract_lock.json)：合同与 feature spec SHA256。
- [binance_1d_ma7_ctp_p1_event_panel_summary.json](binance_1d_ma7_ctp_p1_event_panel_summary.json)：101,187 条 MA7 事件审计。
- [binance_1d_ma7_ctp_p1_oof_predictions.parquet](binance_1d_ma7_ctp_p1_oof_predictions.parquet)：D1-D3 OOF；HYPE 0 行。
- [binance_1d_ma7_ctp_p1_historical_test_predictions.parquet](binance_1d_ma7_ctp_p1_historical_test_predictions.parquet)：2025+ 一次性历史测试预测。
- [binance_1d_ma7_ctp_p1_fold_metrics.parquet](binance_1d_ma7_ctp_p1_fold_metrics.parquet)：训练/验证并列指标。
- [binance_1d_ma7_ctp_p1_decile_metrics.parquet](binance_1d_ma7_ctp_p1_decile_metrics.parquet)：概率十分位与成本后净收益。
- [binance_1d_ma7_ctp_p1_feature_importance.parquet](binance_1d_ma7_ctp_p1_feature_importance.parquet)：gain / SHAP / permutation。
- [binance_1d_ma7_ctp_p1_prehistorical_lock.json](binance_1d_ma7_ctp_p1_prehistorical_lock.json)：读取 2025+ 前锁定的模型身份。
- [binance_1d_ma7_ctp_p1_model_card.json](binance_1d_ma7_ctp_p1_model_card.json)：模型卡；not live-ready。
- [binance_1d_ma7_ctp_p1_summary.json](binance_1d_ma7_ctp_p1_summary.json)：裁决与隔离汇总。
- [binance_1d_ma7_ctp_p1_manifest.json](binance_1d_ma7_ctp_p1_manifest.json)：产物 SHA256。

## P2 Pooled-Minimal MA7 Cross Stability Audit

- [binance_1d_ma7_ctp_p2_feature_spec.json](binance_1d_ma7_ctp_p2_feature_spec.json)：读标签前冻结的 F0/F1 极简特征合同。
- [binance_1d_ma7_ctp_p2_contract_lock.json](binance_1d_ma7_ctp_p2_contract_lock.json)：P2 合同、feature spec 与 P1 feature spec SHA256。
- [binance_1d_ma7_ctp_p2_oof_predictions.parquet](binance_1d_ma7_ctp_p2_oof_predictions.parquet)：D1-D3 OOF；只含 `<2025-01-01`，HYPE 0 行。
- [binance_1d_ma7_ctp_p2_fold_metrics.parquet](binance_1d_ma7_ctp_p2_fold_metrics.parquet)：全部候选的训练/验证并列指标及分层诊断。
- [binance_1d_ma7_ctp_p2_decile_metrics.parquet](binance_1d_ma7_ctp_p2_decile_metrics.parquet)：锁定 pooled 模型概率十分位与成本后事件收益。
- [binance_1d_ma7_ctp_p2_model_card.json](binance_1d_ma7_ctp_p2_model_card.json)：单一 pooled 模型卡；无 2025+ 预测，not live-ready。
- [binance_1d_ma7_ctp_p2_summary.json](binance_1d_ma7_ctp_p2_summary.json)：裁决、隔离、稳定性和重训冻结摘要。
- [binance_1d_ma7_ctp_p2_manifest.json](binance_1d_ma7_ctp_p2_manifest.json)：P2 产物 SHA256。

## P3 Independent Context Feature Block Audit

- [binance_1d_ma7_ctp_p3_feature_spec.json](binance_1d_ma7_ctp_p3_feature_spec.json)：读标签前冻结的 B0 与 B1-B4 单块增量特征合同。
- [binance_1d_ma7_ctp_p3_contract_lock.json](binance_1d_ma7_ctp_p3_contract_lock.json)：P3 合同、feature spec 与未读标签事件审计 SHA256。
- [binance_1d_ma7_ctp_p3_summary.json](binance_1d_ma7_ctp_p3_summary.json)：训练前 `DATA_BLOCK_NOT_READY` 裁决与严格样本时点门禁失败摘要。
- [binance_1d_ma7_ctp_p3_manifest.json](binance_1d_ma7_ctp_p3_manifest.json)：P3 失败审计产物 SHA256；因训练前停止，不包含 OOF 或增量比较 parquet。
