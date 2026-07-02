# Scripts

- `fetch_btc_binance_1h.py`：刷新最近两年 BTCUSDT 永续 `1h` K、资金费与合约快照，写入标准数据湖并输出质量证据。
- `research_btc_1h_adaptive_regime_search.py`：复用已审计的一次性 1h 执行内核，在 BTC 独立数据和固定三个月 locked OOS 上执行宽搜索。
- `audit_btc_1h_adaptive_regime_boundary.py`：对 prefit 预冻结冠军执行延迟、成本、仓位、单腿、参数邻域、月度、bootstrap 与生产能力审计。

两份 wrapper 都固定校验被复用引擎的 SHA-256；依赖脚本漂移时 fail closed，避免静默改变历史复现结果。
