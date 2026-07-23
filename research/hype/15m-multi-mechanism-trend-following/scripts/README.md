# Scripts

- `refresh_hype_15m_dataset.py`：刷新 Binance HYPEUSDT 15m closed OHLCV、funding 与合约快照，写入标准数据湖并在本家族保留质量证据。
- `freeze_hype_15m_dataset.py`：对标准数据湖做 raw/normalized 全量一致性审计，冻结最后三个月 OOS 边界与输入哈希；不计算任何策略绩效。
- `mmtf_engine.py`：多机制信号、K+1/stop-first/gap-open、fee/slippage/funding 单净仓回测内核。
- `research_hype_15m_mmtf_v1_search.py`：V1 两阶段广搜与多目标前沿。
- `research_hype_15m_mmtf_v1_ablation.py`：V1 全接线消融与 trade-signature 检查。
- `mmtf_v2.py`：V2/V3 clean config adapter。
- `research_hype_15m_mmtf_v2_clean_tune.py`：clean surface 风险轮、联合轮与 rolling audit。
- `audit_hype_15m_mmtf_v3_prefit_robustness.py`：揭示前 MC、邻域、成本、delay、funding、phase、极端窗口审计。
- `reveal_hype_15m_mmtf_v3_locked_oos.py`：一次性 locked OOS 揭示；输出已存在时 fail closed。
