# Scripts

- `fetch_sol_binance_1h.py`：从 Binance FAPI 拉取运行时最近两年 `SOLUSDT` perpetual `1h` 闭合 K、资金费和合约过滤器，写入标准 raw/normalized 数据湖并执行硬质量审计。
- `research_sol_1h_adaptive_regime_search.py`：在 locked 三个月 OOS 之外进行 curated + random 多指标/执行参数搜索，预冻结 finalist 后才一次性评估 OOS。
- `audit_sol_1h_adaptive_regime_boundary.py`：对最终预冻结冠军执行 K+2/K+3、成本、仓位缩放、单腿、one-at-a-time 邻域、月度、bootstrap 与 live-executable 缺口审计。
- `sol_1h_ar_v1.py`：固定 `SOL-1H-Adaptive-Regime-V1` 的 `donchian_break + bb_revert` ensemble，校验广搜指标漂移并导出 V1 配置 JSON。
- `research_sol_1h_ar_v1_full_ablation.py`：登记 V1 后覆盖每条腿全部配置字段，输出路径等价、严格改善和 clean-surface 分类，并写入 `ablations/sol-1h-ar-v1-full-parameter-ablation-2026-07-03.md`。
- `sol_1h_ar_v1_clean.py`：从消融 JSON 动态构建 clean 配置类型，把非 active 字段从调参接口移除，要求 V1 逐笔签名完全相等，并写入 `research-notes/sol-1h-ar-v1-clean-interface-2026-07-03.md`。
- `research_sol_1h_ar_v1_clean_tune.py`：基于消融保留字段做高密度微调；选择不使用 reused OOS，胜率只要求适中且评分在 `65%` 封顶，并写入 `research-notes/sol-1h-ar-v1-clean-parameter-tune-2026-07-03.md`。

统一从仓库根目录使用 `uv run python ...` 执行。
