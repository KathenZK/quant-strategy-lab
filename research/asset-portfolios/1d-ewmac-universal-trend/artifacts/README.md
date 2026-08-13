# Artifacts — XA-1D-EWMAC-UT

## P2/P3/P4 组合级（由 [`run_ewmac_portfolio.py`](../scripts/run_ewmac_portfolio.py) 生成；P2 前缀 `xa_1d_ewmac_pf`，P3 前缀 `xa_1d_ewmac_pf3`，P4 前缀 `xa_1d_ewmac_pf4`；P4 summary 含 SPY 组合价值诊断与换手分解）

- `..._summary_<date>.json`：汇总（参数、两窗口两台账指标、LOO、门禁判定；P3 含新 ETF 数据质量与 scale 变更频率）。
- `..._metrics_<date>.csv` / `_yearly_<date>.csv` / `_recent_<date>.csv` / `_loo_<date>.csv`。
- `..._cluster_yearly_<date>.csv`：逐集群逐年 PnL 贡献（压力台账，收益单位加法近似）。
- `..._equity_<date>.parquet` / `.png`：组合权益路径（两台账 + SPY 对照）。

## P1 单资产（由 [`run_ewmac_universal_trend.py`](../scripts/run_ewmac_universal_trend.py) 生成）：

- `xa_1d_ewmac_ut_summary_<date>.json`：汇总报告（参数、数据质量、每资产指标、门禁判定）。
- `xa_1d_ewmac_ut_metrics_<date>.csv`：每资产 × 成本口径指标表。
- `xa_1d_ewmac_ut_yearly_<date>.csv`：逐自然年净收益。
- `xa_1d_ewmac_ut_recent_<date>.csv`：近期分片（1d/7d/1m/3m/6m/1y，仅审计）。
- `xa_1d_ewmac_ut_equity_<date>.parquet` / `.png`：每资产策略 vs 买入持有权益路径。
- `yahoo_raw/`：Yahoo 原始 JSON 留档 + `manifest_<date>.json`（URL、SHA256）。

临时试跑输出放系统临时目录，不入本目录。
