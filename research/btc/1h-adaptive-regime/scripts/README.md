# Scripts

- `fetch_btc_binance_1h.py`：刷新最近两年 BTCUSDT 永续 `1h` K、资金费与合约快照，写入标准数据湖并输出质量证据。
- `research_btc_1h_adaptive_regime_search.py`：复用已审计的一次性 1h 执行内核，在 BTC 独立数据和固定三个月 locked OOS 上执行宽搜索。
- `audit_btc_1h_adaptive_regime_boundary.py`：对 prefit 预冻结冠军执行延迟、成本、仓位、单腿、参数邻域、月度、bootstrap 与生产能力审计。
- `btc_1h_ar_v1.py`：`BTC-1H-Adaptive-Regime-V1` 冻结配置、时间切分与逐笔复现入口。
- `research_btc_1h_ar_v1_full_ablation.py`：V1 两腿 `78/78` 字段槽全参数消融。
- `btc_1h_ar_v1_clean.py`：从 78 个原始槽缩到 27 个 active 参数的逐笔等价 clean interface。
- `research_btc_1h_ar_v1_clean_tune.py`：每腿 15 万组、12.25 万组合的 prefit-only 微调与 K+2/8 bps 前沿筛选。
- `audit_btc_1h_ar_v1_scaled_frontier.py`：缩放前沿、成本/延迟、55 个邻域、月度、bootstrap 与 forward-readiness 审计。
- `research_btc_1h_ar_v2_full_ablation.py`：V2 冻结参数两腿 `78/78` 字段槽全参数消融与单字段敏感性审计。
- `research_btc_1h_ar_v2_micro_tune.py`：基于 V2 消融前沿方向的受约束 active 参数微调。
- `btc_1h_ar_v3.py`：`BTC-1H-Adaptive-Regime-V3` 冻结配置、两腿合成与指标复现入口。
- `research_btc_1h_ar_v3_full_ablation.py`：V3 冻结参数两腿 `78/78` 字段槽全参数消融与单字段敏感性审计。
- `research_btc_1h_ar_v3_window_backtest.py`：V3 canonical/recent/calendar/half-year/monthly 多时间窗口回测。

这些 wrapper 固定校验被复用引擎的 SHA-256；依赖脚本漂移时 fail closed，避免静默改变历史复现结果。
