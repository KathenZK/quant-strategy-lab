# Scripts

- `fetch_eth_binance_1h.py`：刷新最近两年 ETHUSDT 永续 `1h` K、资金费与合约快照，写入标准数据湖并输出质量证据。
- `research_eth_1h_adaptive_regime_search.py`：在 ETH 独立数据和固定三个月 locked OOS 上执行多指标宽搜索；复用经审计的一次性 `1h` 执行内核并固定校验 SHA-256，依赖漂移时 fail closed。
- `research_eth_1h_adaptive_regime_refine.py`：从首轮 prefit Pareto seed 生成邻域配置；最近三个月 OOS 不参与 seed、生成或排序。
- `eth_1h_ar_v1.py`：`ETH-1H-Adaptive-Regime-V1` 冻结配置、切分、组件优先级与逐笔复现入口。
- `research_eth_1h_ar_v1_full_ablation.py`：覆盖 V1 两腿 `78/78` 字段槽并生成删参分类。
- `eth_1h_ar_v1_clean.py`：只保留 33 个 active 参数的 clean interface，并 fail closed 校验与 V1 逐笔等价。
- `research_eth_1h_ar_v1_clean_tune.py`：每腿 15 万组、12.25 万组合的 prefit-only 微调与 K+2/8 bps 联合筛选。
- `audit_eth_1h_ar_v1_clean_tune.py`：冻结微调 observation 的成本/延迟、66 邻域、月度、bootstrap 与 live-readiness 审计。
