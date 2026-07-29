# HYPE-15M-SDS Scripts

- `refresh_hype_15m_sds_dataset.py`：刷新 Binance HYPEUSDT 15m OHLCV/funding 并写入标准数据湖。
- `freeze_hype_15m_sds_dataset.py`：在绩效揭示前冻结数据、基线参数、代码哈希与 reused OOS 合同。
- `sds_engine.py`：逐 K 状态估计和 live-realistic 单净仓回测内核。
- `research_hype_15m_sds_baseline.py`：一次性揭示冻结顺序漂移基线。
- `diagnose_hype_15m_sds_baseline_cost.py`：只在 prefit 比较冻结成本与零成本，不读取 locked OOS。
- `research_hype_15m_sds_regression_search.py`：严格只读 prefit 的滚动回归状态搜索。
- `research_hype_15m_sds_breakout_retest_search.py`：严格只读 prefit 的“趋势发现 → armed → 回踩重测 → active”状态搜索。
- `research_hype_15m_sds_kalman_cusum_structure.py`：严格只读 prefit 的 causal Kalman + Page CUSUM + Donchian/efficiency 状态搜索、消融和成本审计。
- `research_hype_15m_sds_kcs_full_ablation.py`：冻结 KCS 失败参考，对全部 active 信号、状态机和风险参数执行 one-at-a-time 消融与成交路径哈希审计。
