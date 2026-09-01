---
research_classification: diagnostic_topic
---

# Binance-1D-MA7-Cross-Trend-Probability

- Alias：`BIN-1D-MA7-CTP`
- 市场/周期：Binance USD-M 永续完整 UTC 日K；先做 BTC/ETH/BNB/SOL，再用 `data/cache/binance_perp_1d_from_15m` 扩到全市场。
- 机制：收盘穿越 `SMA7` 后，统计 20 日先到顺向 `+2 ATR`、未先到反向 `-1 ATR` 的条件概率；再叠加斜率、放量和 7/30/60/90 日上涨/回撤比。
- 边界：不是 `BIN-1D-TPSA`、`BIN-1D-MA7-RC` 或 `HYPE-1D-MA7-ABT`；无订单、无成本、无策略版本。
- 当前状态：`explore / diagnostic-only / not promoted / not live-ready`；本 README 兼任临时主账。

## 入口

- [决策记录](decision-log.md)
- [冻结口径](specs/binance-1d-ma7-cross-trend-probability-contract-2026-08-31.md)
- [四币 SCOUT](diagnostics/binance-1d-ma7-cross-trend-probability-2026-08-31.md)
- [全市场 SCOUT](diagnostics/binance-1d-ma7-cross-trend-probability-all-market-2026-08-31.md)
- [HYPE 对照](diagnostics/binance-1d-ma7-cross-trend-probability-hype-vs-universe-2026-08-31.md)
- [四币脚本](scripts/research_binance_1d_ma7_cross_trend_probability.py)
- [全市场脚本](scripts/research_binance_1d_ma7_cross_trend_probability_all_market.py)
- [产物索引](artifacts/README.md)
