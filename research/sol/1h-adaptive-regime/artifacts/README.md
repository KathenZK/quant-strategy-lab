# Artifacts

本目录保存 `SOL-1H-Adaptive-Regime` 的可复现数据、搜索排名、交易路径和审计产物。非 Markdown 文件默认由仓库 `.gitignore` 忽略，但由对应脚本确定性生成。

- `sol_binance_1h_closed_klines_2y.parquet`：本次研究精确使用的最近两年闭合 K。
- `sol_binance_funding_history_2y.csv`：同窗口 Binance 历史资金费。
- `sol_binance_1h_data_quality_2y.json`：数据质量、路径、校验值和合约过滤器快照。
- `sol_1h_adaptive_regime_*_2026-07-03.*`：宽搜索摘要、prefit 排名、locked finalists、时间切片和冠军交易路径。
- `sol_1h_ar_v1_config_2026-07-03.json`：`SOL-1H-Adaptive-Regime-V1` 冻结配置、复现指标和近期分片。
- `sol_1h_ar_v1_full_ablation_*_2026-07-03.*`：V1 全参数消融摘要、逐行结果和字段分类。
- `sol_1h_ar_v1_clean_config_2026-07-03.json`：V1 clean interface 与逐笔等价校验摘要。
- `sol_1h_ar_v1_clean_tune_2026-07-03.json`、`sol_1h_ar_v1_tune_*_2026-07-03.csv`：clean surface 微调观察与交易路径；不自动形成新版本。
- `sol_1h_ar_high_win_*_2026-07-07.*`：`10x / 80% / <20% DD` 高胜率硬目标搜索摘要、prefit 排名、finalists、时间切片和最佳观察交易路径。
