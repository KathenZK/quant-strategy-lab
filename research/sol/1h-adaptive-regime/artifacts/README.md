# Artifacts

本目录保存 `SOL-1H-Adaptive-Regime` 的可复现数据、搜索排名、交易路径和审计产物。非 Markdown 文件默认由仓库 `.gitignore` 忽略，但由对应脚本确定性生成。

- `sol_binance_1h_closed_klines_2y.parquet`：本次研究精确使用的最近两年闭合 K。
- `sol_binance_funding_history_2y.csv`：同窗口 Binance 历史资金费。
- `sol_binance_1h_data_quality_2y.json`：数据质量、路径、校验值和合约过滤器快照。
- `sol_1h_adaptive_regime_*_2026-07-03.*`：宽搜索摘要、prefit 排名、locked finalists、时间切片和冠军交易路径。
