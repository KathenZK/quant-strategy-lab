# Scripts

- `fetch_bnb_binance_1h.py`：抓取并审计 Binance `BNBUSDT` perpetual 最近两年闭合 `1h` K、资金费和合约过滤器。
- `research_bnb_1h_adaptive_regime_search.py`：在最近三个月 locked OOS 前进行多指标宽搜索，冻结 finalists 后一次性揭盲。
- `research_bnb_1h_ar_cap3_highwin_search.py`：按最大 `3x` 杠杆约束重搜趋势/反转及 ensemble，优先寻找高胜率、DD 不超过 `20%` 的高收益前沿；只冻结唯一 primary 后揭盲 OOS。
- `research_bnb_1h_ar_v1_full_ablation.py`：对 `BNB-1H-Adaptive-Regime-V1` 做逐字段消融，识别交易路径完全不变的 no-op 参数并生成 clean spec 证据。
- `audit_bnb_1h_ar_frozen_primary.py`：对唯一冻结 primary 做保守逐 K 回撤、成本/延迟、机械参数邻域和交易所精度边界审计；不用于 OOS 后调参。

运行统一使用 `uv run python ...`。
