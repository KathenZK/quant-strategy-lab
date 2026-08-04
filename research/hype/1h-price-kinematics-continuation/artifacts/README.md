# Artifacts

本目录保存价格运动学研究的机器 JSON、分箱统计、相空间网格、滚动样本外预测和稳健性 CSV。生成物只证明统计诊断，不是策略回测或 live 证据。

- `hype_1h_pkc_research_2026-08-02.json`：数据合同、样本数、冻结模型结果、方向门槛和 prospective 状态。
- `hype_1h_pkc_label_summary_2026-08-02.csv`：Train/Validation 无条件未来路径基准。
- `hype_1h_pkc_univariate_bins_2026-08-02.csv` / `...effects...csv`：固定分箱与 block-bootstrap 顶底效应。
- `hype_1h_pkc_model_metrics_2026-08-02.csv` / `...coefficients...csv`：Baseline/Full 的 OOF、Validation 指标和固定模型系数。
- `hype_1h_pkc_phase_space_2026-08-02.csv` / `...phase_sensitivity...csv`：速度—加速度网格与四锚点相位。
- `hype_1h_pkc_labelled_observations_2026-08-02.parquet`：prospective 起点前的逐锚点因果特征和未来标签。
