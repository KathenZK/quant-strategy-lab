# Artifacts

本目录保存15分钟价格运动学的机器 JSON、未来路径基准、固定分箱、模型、相空间和相位敏感性产物；它们不是策略或 live 证据。

- `hype_15m_pkc_research_2026-08-02.json`：数据、冻结合同、样本、模型和方向门槛。
- `hype_15m_pkc_label_summary_2026-08-02.csv`：Train/Validation 无条件未来路径。
- `hype_15m_pkc_univariate_bins_2026-08-02.csv` / `...effects...csv`：固定五分位与12小时 block-bootstrap。
- `hype_15m_pkc_model_metrics_2026-08-02.csv` / `...coefficients...csv`：Baseline/Full OOF 与 Validation。
- `hype_15m_pkc_phase_space_2026-08-02.csv` / `...phase_sensitivity...csv`：速度—加速度网格与四分钟相位。
- `hype_15m_pkc_labelled_observations_2026-08-02.parquet`：prospective 起点前的逐锚点因果特征和标签。
