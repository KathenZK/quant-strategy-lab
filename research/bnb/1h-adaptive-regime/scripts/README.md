# Scripts

- `fetch_bnb_binance_1h.py`：抓取并审计 Binance `BNBUSDT` perpetual 最近两年闭合 `1h` K、资金费和合约过滤器。
- `research_bnb_1h_adaptive_regime_search.py`：在最近三个月 locked OOS 前进行多指标宽搜索，冻结 finalists 后一次性揭盲。
- `research_bnb_1h_ar_cap3_highwin_search.py`：按最大 `3x` 杠杆约束重搜趋势/反转及 ensemble，优先寻找高胜率、DD 不超过 `20%` 的高收益前沿；只冻结唯一 primary 后揭盲 OOS。
- `research_bnb_1h_ar_v1_full_ablation.py`：对 `BNB-1H-Adaptive-Regime-V1` 做逐字段消融，识别交易路径完全不变的 no-op 参数并生成 clean spec 证据。
- `bnb_1h_ar_v2.py`：`BNB-1H-Adaptive-Regime-V2` clean 参数可执行定义；运行时验证与 V1 trade signature 相等并输出多时间窗口分片。
- `research_bnb_1h_ar_v2_full_ablation.py`：对 V2 全部活动字段做 one-at-a-time 域扫描，确认是否还存在可删除的无效参数。
- `research_bnb_1h_ar_v2_micro_tune.py`：V2 消融引导微调；leg 级采样 + ensemble 组合，选参只用 train/validation/prefit，唯一首选组合复用 locked OOS 一次作为观察值。
- `bnb_1h_ar_v3.py`：`BNB-1H-Adaptive-Regime-V3` 冻结参数的独立可执行定义；默认只复现并报告 prefit，不读取 reused OOS 作为选参依据。
- `research_bnb_1h_ar_v3_prefit_exit_filter_tune.py`：V3 附近的第一轮 prefit-only exit/filter 表面诊断；未内嵌 K+2/8bps，仅作历史观察。
- `research_bnb_1h_ar_v3_prefit_walkforward_tune.py`：V3 低自由度分阶段优化；冻结杠杆和 merge priority，内嵌 K+2、8bps 与四个 prefit 时间块，并做 component/方向风险归因。
- `audit_bnb_1h_ar_frozen_primary.py`：对唯一冻结 primary 做保守逐 K 回撤、成本/延迟、机械参数邻域和交易所精度边界审计；不用于 OOS 后调参。

运行统一使用 `uv run python ...`。
