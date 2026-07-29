# HYPE-15M-SDS Artifacts

本目录保存 `HYPE-15M-Sequential-Drift-State` 的数据冻结、回测汇总、逐笔交易、资金曲线和逐 K 状态证据。JSON/CSV/Parquet 是机器证据；研究结论以家族 Markdown 报告和主账为准。

Kalman/CUSUM/结构确认机制的冻结搜索合同、排名、消融和逐 K Kalman 状态使用 `hype_15m_sds_kcs_*` 前缀；本机制没有读取已经揭示的 reused OOS。

KCS 全参数消融使用 `hype_15m_sds_kcs_full_ablation*`；完整 CSV 包含每个单变量的 train/validation 指标、样本门槛与 baseline 成交/权益路径等价标记。
