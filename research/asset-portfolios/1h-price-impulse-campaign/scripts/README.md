# Scripts

- `research_binance_1h_pic_v0.py`：复现数据审计、V0 真实 quantity campaign、方向控制、成本/stress、近期切片、rolling audit、消融与逐笔账本。
- `sync_eth_binance_15m.py`：从 Binance 官方 API 刷新 ETHUSDT perpetual 闭合 `15m` OHLCV/funding，写入 raw/normalized 日分区并 fail-closed 审计。
- `research_binance_1h_pic_v1.py`：复现 V1 `25% probe → 盈利分层 add → 半 MFE 只减至 probe` 的真实 lot/quantity、open-risk、成本、funding 与消融账本。
- `research_binance_1h_pic_v2.py`：复现 V2 `0.9%` operational budget、funding 入账后 LIFO `risk_trim` 与 `1%` 硬风险不变量。

```bash
PYTHONPATH=src .venv/bin/python research/asset-portfolios/1h-price-impulse-campaign/scripts/research_binance_1h_pic_v0.py
PYTHONPATH=src .venv/bin/python research/asset-portfolios/1h-price-impulse-campaign/scripts/research_binance_1h_pic_v1.py
PYTHONPATH=src .venv/bin/python research/asset-portfolios/1h-price-impulse-campaign/scripts/research_binance_1h_pic_v2.py
```
