# Scripts

- `fetch_sol_binance_1h.py`：从 Binance FAPI 拉取运行时最近两年 `SOLUSDT` perpetual `1h` 闭合 K、资金费和合约过滤器，写入标准 raw/normalized 数据湖并执行硬质量审计。
- `research_sol_1h_adaptive_regime_search.py`：在 locked 三个月 OOS 之外进行 curated + random 多指标/执行参数搜索，预冻结 finalist 后才一次性评估 OOS。
- `audit_sol_1h_adaptive_regime_boundary.py`：对最终预冻结冠军执行 K+2/K+3、成本、仓位缩放、单腿、one-at-a-time 邻域、月度、bootstrap 与 live-executable 缺口审计。
- `sol_1h_ar_v1.py`：固定 `SOL-1H-Adaptive-Regime-V1` 的 `donchian_break + bb_revert` ensemble，校验广搜指标漂移并导出 V1 配置 JSON。
- `research_sol_1h_ar_v1_full_ablation.py`：登记 V1 后覆盖每条腿全部配置字段，输出路径等价、严格改善和 clean-surface 分类，并写入 `ablations/sol-1h-ar-v1-full-parameter-ablation-2026-07-03.md`。
- `sol_1h_ar_v1_clean.py`：从消融 JSON 动态构建 clean 配置类型，把非 active 字段从调参接口移除，要求 V1 逐笔签名完全相等，并写入 `notes/sol-1h-ar-v1-clean-interface-2026-07-03.md`。
- `research_sol_1h_ar_v1_clean_tune.py`：基于消融保留字段做高密度微调；选择不使用 reused OOS，胜率只要求适中且评分在 `65%` 封顶，并写入 `notes/sol-1h-ar-v1-clean-parameter-tune-2026-07-03.md`。
- `research_sol_1h_ar_high_win_target_search.py`：`10x / 80% / <20% DD` 高胜率硬目标重新搜索；沿用 V1 冻结研究帧，最近三个月按 reused holdout 只审计不选参，并写入 `diagnostics/sol-1h-ar-high-win-target-search-2026-07-07.md`。
- `research_sol_1h_ar_v2_mechanism_redesign.py`：V2 双腿贡献、收益结构、entry gate、fixed/trailing exit 与风险分配对照；选择只用 train/validation/prefit。
- `research_sol_1h_ar_v2_staged_exit.py`：V2 部分止盈、延伸目标、次 K 保本 stop 与快速失效次根 open 退出诊断。
- `research_sol_1h_ar_v2_leg_governor.py`：VWAP satellite 在 stop/亏损后的在线 cooldown 治理诊断；验证事后暂停能否修复 regime 失效。
- `research_sol_1h_ar_v2_vwap_state_machine.py`：把 VWAP 偏离事件改写为 `arm → confirm → expire` 状态机；confirm 使用闭合 K，下一根 open 入场。
- `audit_sol_1h_ar_v3_fresh_forward.py`：使用刷新数据重放 V3，并审计 `2026-07-03` 之后的新增 forward 交易。

统一从仓库根目录使用 `uv run python ...` 执行。
