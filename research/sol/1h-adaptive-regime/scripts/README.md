# Scripts

- `fetch_sol_binance_1h.py`：从 Binance FAPI 拉取运行时最近两年 `SOLUSDT` perpetual `1h` 闭合 K、资金费和合约过滤器，写入标准 raw/normalized 数据湖并执行硬质量审计。
- `research_sol_1h_adaptive_regime_search.py`：在 locked 三个月 OOS 之外进行 curated + random 多指标/执行参数搜索，预冻结 finalist 后才一次性评估 OOS。
- `research_sol_1h_adaptive_regime_refine.py`：从第一轮 prefit CSV 按固定规则选择 train/validation Pareto seed，生成高密度参数邻域；邻域生成与排序不读取 OOS。
- `audit_sol_1h_adaptive_regime_boundary.py`：对最终预冻结冠军执行 K+2/K+3、成本、仓位缩放、单腿、one-at-a-time 邻域、月度、bootstrap 与 live-executable 缺口审计。

统一从仓库根目录使用 `uv run python ...` 执行。
