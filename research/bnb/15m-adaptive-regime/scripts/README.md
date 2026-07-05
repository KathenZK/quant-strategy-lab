# Scripts

- `fetch_bnb_binance_15m.py`：抓取并审计 Binance `BNBUSDT` perpetual 最近两年全部闭合 `15m` K、资金费和合约过滤器。
- `research_bnb_15m_market_character.py`：只用 prefit 区间分析 BNB 的趋势延续、急跌修复、波动/成交量状态及时段特征。
- `research_bnb_15m_adaptive_regime_search.py`：在最近三个月 locked OOS 前做分阶段广搜与精调，冻结唯一 primary 后一次性揭盲。

统一使用 `uv run python ...`。
