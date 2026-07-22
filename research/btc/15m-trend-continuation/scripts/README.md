# Scripts

从仓库根目录运行：

```bash
uv run python research/btc/15m-trend-continuation/scripts/refresh_and_audit_btc_15m_long_data.py --timeout 60
uv run python research/btc/15m-trend-continuation/scripts/analyze_btc_15m_trend_structure.py
uv run python research/btc/15m-trend-continuation/scripts/research_btc_15m_low_vol_compression_breakout.py
uv run python research/btc/15m-trend-continuation/scripts/audit_btc_15m_lvcb_candidate.py
uv run python research/btc/15m-trend-continuation/scripts/research_btc_15m_lvcb_iterations.py
uv run python research/btc/15m-trend-continuation/scripts/research_btc_15m_lvcb_short_search.py
```

- [`refresh_and_audit_btc_15m_long_data.py`](refresh_and_audit_btc_15m_long_data.py)：把官方 BTCUSDT perpetual `15m` 与 funding 扩展到 `2020-01-01`，通过 DQ 后写入标准数据湖。
- [`analyze_btc_15m_trend_structure.py`](analyze_btc_15m_trend_structure.py)：固定成本门槛的非重叠趋势事件研究，只作机制诊断。
- [`research_btc_15m_low_vol_compression_breakout.py`](research_btc_15m_low_vol_compression_breakout.py)：执行冻结 signal/exit 搜索、开发门禁、双倍成本、复用期、自然年和近期切片审计。
- [`audit_btc_15m_lvcb_candidate.py`](audit_btc_15m_lvcb_candidate.py)：对冻结候选做 deterministic five-trade block bootstrap。
- [`research_btc_15m_lvcb_iterations.py`](research_btc_15m_lvcb_iterations.py)：按 TB 风格执行六轮单机制父子迭代、双倍成本、近期切片、180d 滚动窗口和诊断 walk-forward。
- [`research_btc_15m_lvcb_short_search.py`](research_btc_15m_lvcb_short_search.py)：执行空头专属压缩、EMA、Donchian 与退出参数搜索，并冻结一次 reused diagnostic 揭示。
