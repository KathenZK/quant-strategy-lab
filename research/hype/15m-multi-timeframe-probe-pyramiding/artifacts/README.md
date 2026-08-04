# Artifacts

本目录保存 `HYPE-15M-MTPP` 的机器可读结果、campaign/action/equity 明细和同路径事件归因。文件只有在对应 diagnostics 报告引用后才属于耐久证据。

- `hype_15m_mtpp_research_2026-08-03.json`：数据合同、政策结果、成本梯度、recent slices、五段结果与事件归因主结果。
- `hype_15m_mtpp_policy_metrics_2026-08-03.csv`：Long/Short × `1%/3%/10%` × 五政策指标。
- `hype_15m_mtpp_contiguous_blocks_2026-08-03.csv`：五个连续时间块的全政策复跑。
- `hype_15m_mtpp_{long,short}_paired_events_2026-08-03.csv`：相同入口事件级政策结果。
- `hype_15m_mtpp_*_campaigns.csv`、`*_actions.csv`、`*_equity.parquet`：逐政策交易账本、动作和权益路径。
