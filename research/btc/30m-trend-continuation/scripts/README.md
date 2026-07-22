# BTC-30M-Trend-Continuation 脚本

按顺序复现：

```bash
uv run python research/btc/30m-trend-continuation/scripts/refresh_and_audit_btc_30m_long_data.py --timeout 60
uv run python research/btc/15m-trend-continuation/scripts/refresh_and_audit_btc_15m_long_data.py --timeout 60
uv run python research/btc/30m-trend-continuation/scripts/research_btc_30m_trend_continuation.py
uv run python research/btc/30m-trend-continuation/scripts/research_btc_30m_channel_trends.py
uv run python research/btc/30m-trend-continuation/scripts/research_btc_30m_expanded_compression.py
```

- [`refresh_and_audit_btc_30m_long_data.py`](refresh_and_audit_btc_30m_long_data.py)：获取原生 Binance `30m` K 线与官方 funding，执行数据质量审计并写入标准 data lake。
- [`research_btc_30m_trend_continuation.py`](research_btc_30m_trend_continuation.py)：低频压缩延续搜索，并用偏移 `30m` 做相位审计。
- [`research_btc_30m_channel_trends.py`](research_btc_30m_channel_trends.py)：Donchian/Keltner、EMA、波动、成交量和退出联合搜索。
- [`research_btc_30m_expanded_compression.py`](research_btc_30m_expanded_compression.py)：放宽压缩、突破和 ATR 上限的反证搜索。
