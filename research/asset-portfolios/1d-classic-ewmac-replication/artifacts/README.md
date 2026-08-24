# Artifacts — XA-1D-CLASSIC-EWMAC

由 [`run_classic_ewmac_replication.py`](../scripts/run_classic_ewmac_replication.py) 生成，前缀为 `xa_1d_classic_ewmac_replication_<date>`。

- `_summary.json`：参数、资产池、数据质量、三本台账指标、benchmark 与组合诊断。
- `_metrics.csv`：三本台账主指标。
- `_yearly.csv`：逐年净收益。
- `_recent.csv`：近期 `1d/7d/1m/3m/6m/1y` 分片。
- `_crisis.csv`：GFC、COVID、2022 压力窗口的策略与基准表现。
- `_class_yearly.csv`：按资产类别聚合的逐年 PnL 贡献。
- `_equity.parquet`：策略三本台账权益路径；只有显式传入 `--plot` 时才额外生成 `_equity.png`。
- `yahoo_raw/`：Yahoo 原始 JSON 与 `manifest_<date>.json`，记录 URL 与 SHA256。

临时试跑输出不得引用为长期证据；报告引用的结果必须在本目录留档。
