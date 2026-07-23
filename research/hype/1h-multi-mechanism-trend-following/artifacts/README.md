# Artifacts

本目录保存数据冻结 manifest、搜索 frontier、冻结候选、逐笔交易、权益路径、消融、调优、OOS reveal 与稳健性审计机器证据。

关键入口：

- `hype_1h_mmtf_dataset_freeze_2026-07-22.json`：数据与 OOS 边界冻结。
- `hype_1h_mmtf_v1_search_2026-07-22.json` 与 `_frontier.csv`：`48,000` 候选广搜及 V1。
- `hype_1h_mmtf_v1_ablation_2026-07-22.json/.csv`：V1 消融与 path-equal 证据。
- `hype_1h_mmtf_v2_clean_tune_2026-07-22.json`：V2 等价与 `60,000` 候选调优冻结。
- `hype_1h_mmtf_v3_prefit_robustness_2026-07-22.json`：OOS 前压力、MC、邻域、极端窗口、相位与状态机审计。
- `hype_1h_mmtf_v3_locked_oos_reveal_2026-07-22.json`：唯一一次 OOS 揭示与最终 NO-GO。
