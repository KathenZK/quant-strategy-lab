# Artifacts

本目录保留 `HYPE-1D-MA7-Machine-Learning-Trend` 的机器可审计结果、逐折指标、验证交易和完整交易路径 HTML。

- `hype_1d_ma7_mlt_p0_365d_train_validation_2026-08-27_summary.json`：P0 总摘要与 `ML_NO_EDGE` 裁决。
- `*_ml_candidates.csv` / `*_rule_candidates.csv`：冻结的 72 个 ML 与 4,320 个规则候选训练内逐折指标。
- `*_validation_predictions.csv` / `*_validation_trades.csv` / `*_validation_path.csv`：一次性验证预测、逐笔与净值路径。
- `*_trade_paths.html`：完整验证 K 线、ML/规则净值与每笔 entry-exit 连线，支持拖动和缩放。
- `*_v7_1_descriptive_reference.json`：exact V7.1 同起止时间的已揭示历史参考，不是 clean OOS。
- 每个产物均有 `.sha256` sidecar。
