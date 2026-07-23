# Scripts

- `freeze_hype_1h_dataset.py`：审计 raw/normalized/funding，冻结数据终点与最近三个月 locked OOS，并写入哈希 manifest。
- `mmtf_engine.py`：本家族独立事件驱动回测内核；K+1 open、stop-first、gap-open、逐 fill 成本、funding、单净仓和 `<=3x`。
- `research_hype_1h_mmtf_v1_search.py`：五机制两阶段 prefit-only 广搜、多目标 frontier 与 V1 冻结；不加载 locked OOS。
- `research_hype_1h_mmtf_v1_ablation.py`：V1 功能组件、方向、风险预算与 dormant-field 全覆盖消融；不加载 locked OOS。
- `mmtf_v2.py`：删除 dormant/fixed 槽后的 12 参数 clean interface，并映射到通用事件驱动内核。
- `research_hype_1h_mmtf_v2_clean_tune.py`：验证 V2 与 V1 逐笔等价，再分风险轮、联合轮及滚动 30d 审计调优；不加载 locked OOS。
- `audit_hype_1h_mmtf_v3_prefit_robustness.py`：冻结代码哈希复核、MC3、有效参数邻域、K+2/8bps、极端窗口、真实 15m 重聚合 1h 相位和状态机静态审计；不加载 locked OOS。
- `reveal_hype_1h_mmtf_v3_locked_oos.py`：验证冻结哈希后唯一一次揭示 locked OOS，输出 full/OOS/slices/stress/MC 证据；产物存在时拒绝重跑。
- 后续消融、调优、reveal 与审计脚本在各阶段完成后登记于此。
