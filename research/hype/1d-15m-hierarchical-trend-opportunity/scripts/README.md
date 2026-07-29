# Scripts

- [freeze_hype_d15_hto_dataset.py](freeze_hype_d15_hto_dataset.py)：刷新后硬审计标准数据湖，冻结完整 `15m` 快照、资金费快照与 recent-three-month locked OOS 边界；不计算 OOS 绩效。
- [hto_engine.py](hto_engine.py)：日线方向、`15m` 入场、实盘时序、成本、资金费与逐笔撮合内核。
- [search_hype_d15_hto_v1.py](search_hype_d15_hto_v1.py)：只用 prefit 的 50,000 组原始多机制广搜并冻结 V1。
- [ablate_hype_d15_hto_v1.py](ablate_hype_d15_hto_v1.py)：V1 的 34 个参数槽位与 10 个组件消融。
- [hto_v2.py](hto_v2.py)：V2 clean 参数接口及 V1 等价映射。
- [tune_hype_d15_hto_v2.py](tune_hype_d15_hto_v2.py)：clean 面 120,000 组风险/联合调优并冻结 V3。
- [audit_hype_d15_hto_v3_prefit.py](audit_hype_d15_hto_v3_prefit.py)：prefit 切片、CPCV、bootstrap、参数邻域、延迟/滑点压力和真实 `1m` 相位。
- [reveal_hype_d15_hto_v3_oos.py](reveal_hype_d15_hto_v3_oos.py)：冻结后一次性揭示 recent-three-month locked OOS；存在揭示产物时拒绝二次运行。
