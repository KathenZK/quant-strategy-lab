# 研究脚本

本目录保存 `Binance-15M-Multi-Indicator-Intraday-Transfer` 的一次性跨资产迁移诊断脚本。

## 当前脚本

- `research_binance_15m_mii_btc_eth_constrained_search.py`：直接拉取 Binance USD-M `BTCUSDT`、`ETHUSDT` `15m` API K 线，在 `HYPE-15M-MII-V1.1` 机制内做受约束微调搜索，并输出 K+1/K+2、分窗口、CSV/JSON 和诊断报告。
