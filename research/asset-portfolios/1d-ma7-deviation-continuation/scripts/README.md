# Scripts

- [research_binance_1d_ma7dc.py](research_binance_1d_ma7dc.py)：加载已审计的 HYPE/BTC/ETH 数据，聚合完整 UTC 日 K，构建因果 SMA7 状态并导出延续、偏离、restart、分块与近期切片证据。
- [audit_binance_1d_ma7dc_campaign_tracking.py](audit_binance_1d_ma7dc_campaign_tracking.py)：用独立 ATR ZigZag completed swings 评分 SMA7 作为持仓轨道的对齐速度、趋势捕获、浮盈保留和错误退出。

```bash
.venv/bin/python research/asset-portfolios/1d-ma7-deviation-continuation/scripts/research_binance_1d_ma7dc.py
.venv/bin/python research/asset-portfolios/1d-ma7-deviation-continuation/scripts/audit_binance_1d_ma7dc_campaign_tracking.py
```
