# Scripts

- `fetch_hype_binance_1h.py`：从 Binance FAPI 拉取 HYPEUSDT 永续全部闭合 `1h` K、全部可得资金费和当前合约过滤器，写入标准 raw/normalized 数据湖；使用 UTC datetime 与 Binance server cutoff 直接判断闭合，并对 normalized unclosed / raw false-closed 执行硬 blocker。
- `research_hype_1h_adaptive_regime_search.py`：在时间顺序 train/validation/locked holdout 框架下搜索和审计 `HYPE-1H-Adaptive-Regime`。
- `research_hype_1h_adaptive_regime_refine.py`：只读取第一轮 prefit train/validation 排名，在 Pareto 边界周围生成 `180,000` 个 unique neighbors；finalists 冻结后才读取 holdout。
- `audit_hype_1h_adaptive_regime_boundary.py`：复现最强 ensemble，执行 K+2/K+3、成本、暴露、单腿、active-field、月度、bootstrap 和实盘状态机审计。
- `research_hype_1h_ar_v1_full_ablation.py`：登记 V1，并覆盖两条腿 `76/76` 字段槽的全量 one-at-a-time 消融。
- `research_hype_1h_ar_v2_clean_tune.py`：用 clean dataclass 精确复现 V1 为 V2，验证三层交易签名等价，并执行首轮 active 参数微调。
- `research_hype_1h_ar_v2_full_ablation.py`：覆盖 V2 clean 配置接口 `34` 个字段槽的 one-at-a-time 全参数消融，并输出 V2 专用 ablation 报告。
- `research_hype_1h_ar_v2_ablation_combo_retest.py`：复测 V2 全参数消融提示的少量 DI/Stoch 组合，并同时输出 base K+1、K+2 和 8 bps 压力结果。
- `research_hype_1h_ar_v3_full_ablation.py`：将 `di_roc_off__stoch_th55` 作为 V3 baseline，覆盖 clean 配置接口 `34` 个字段槽的 one-at-a-time 全参数消融，并输出最近窗口与滚动窗口复核。
- `research_hype_1h_ar_v3_prune_and_tune.py`：验证移除 V3 中 `9` 个 dormant 字段槽后逐笔路径与 V3 exact equal，再只用 prefit（含 K+1/K+2/8bps 三场景 gate）对剪枝后 `25` 个字段槽做网格微调，冻结后揭示 reused holdout 与压力结果。
- `audit_hype_1h_ar_v4_pressure_optimization.py`：用精确单账户联合状态机对账 V4，修正“两腿独立模拟后合并”的 cooldown 路径偏差，并对止损、最长持仓、trailing、固定/风险封顶仓位执行压力优先搜索。
- `audit_hype_1h_ar_v2_tune_frontier.py`：对基础达标微调前沿执行 K+2、成本、暴露和相邻参数审计。
- `research_hype_1h_ar_v2_live_robust_tune.py`：只用 prefit 的 K+1/K+2/8 bps 三场景联合 gate 扩大搜索；后段仅作冻结后诊断。

仓库执行口径：`uv run python <script>`。
