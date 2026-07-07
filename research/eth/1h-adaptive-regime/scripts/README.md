# Scripts

- `fetch_eth_binance_1h.py`：刷新最近两年 ETHUSDT 永续 `1h` K、资金费与合约快照，写入标准数据湖并输出质量证据。
- `research_eth_1h_adaptive_regime_search.py`：在 ETH 独立数据和固定三个月 locked OOS 上执行多指标宽搜索；复用经审计的一次性 `1h` 执行内核并固定校验 SHA-256，依赖漂移时 fail closed。
- `research_eth_1h_adaptive_regime_refine.py`：从首轮 prefit Pareto seed 生成邻域配置；最近三个月 OOS 不参与 seed、生成或排序。
- `eth_1h_ar_v1.py`：`ETH-1H-Adaptive-Regime-V1` 冻结配置、切分、组件优先级与逐笔复现入口。
- `research_eth_1h_ar_v1_full_ablation.py`：覆盖 V1 两腿 `78/78` 字段槽并生成删参分类。
- `eth_1h_ar_v1_clean.py`：只保留 29 个 active 参数的 clean interface，并 fail closed 校验与 V1 逐笔等价。
- `research_eth_1h_ar_v1_clean_tune.py`：每腿 15 万组、12.25 万组合的 prefit-only 微调与 K+2/8 bps 联合筛选。
- `audit_eth_1h_ar_v1_clean_tune.py`：冻结微调 observation 的成本/延迟、66 邻域、月度、bootstrap 与 live-readiness 审计。
- `eth_1h_ar_v2.py`：`ETH-1H-Adaptive-Regime-V2` 冻结 clean 参数、标准分片与逐笔复现入口。
- `research_eth_1h_ar_v2_full_ablation.py`：覆盖 V2 `29/29` 个 clean 参数槽的 one-at-a-time 全参数消融。
- `research_eth_1h_ar_v2_ablation_guided_tune.py`：基于 V2 消融域重新搜索 `win>=80%`、DD `<20%` 的高胜率组合观察值。
- `eth_1h_ar_v2_1.py`：`ETH-1H-Adaptive-Regime-V2.1` 冻结 clean 参数与逐笔复现入口。
- `research_eth_1h_ar_v2_1_full_ablation.py`：覆盖 V2.1 `29/29` 个 clean 参数槽的全参数消融，并按 merged-path inert 规则判定无意义参数。
- `eth_1h_ar_v2_1_clean.py`：删除 2 个 inert 字段后的 27 参数 V2.1 clean interface，fail closed 校验与 V2.1 逐笔等价。
- `research_eth_1h_ar_v2_1_clean_tune.py`：在 27 参数干净面上搜索相对 V2.1 收益更高、胜率更高、回撤更小的组合，并做 K+2/8 bps 稳健排序与冻结后审计。
