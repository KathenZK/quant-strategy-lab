# Artifacts — XA-1D-EWMAC-UT

保留的可复现证据（由 [`run_ewmac_universal_trend.py`](../scripts/run_ewmac_universal_trend.py) 生成）：

- `xa_1d_ewmac_ut_summary_<date>.json`：汇总报告（参数、数据质量、每资产指标、门禁判定）。
- `xa_1d_ewmac_ut_metrics_<date>.csv`：每资产 × 成本口径指标表。
- `xa_1d_ewmac_ut_yearly_<date>.csv`：逐自然年净收益。
- `xa_1d_ewmac_ut_recent_<date>.csv`：近期分片（1d/7d/1m/3m/6m/1y，仅审计）。
- `xa_1d_ewmac_ut_equity_<date>.parquet` / `.png`：每资产策略 vs 买入持有权益路径。
- `yahoo_raw/`：Yahoo 原始 JSON 留档 + `manifest_<date>.json`（URL、SHA256）。

临时试跑输出放系统临时目录，不入本目录。
