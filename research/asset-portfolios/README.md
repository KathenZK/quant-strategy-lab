# Asset Portfolios Research Index

本目录存放组合策略、跨资产策略、迁移研究和多 sleeve 资金结构研究。当前材料主要基于 Binance USD-M Futures 市场数据；若某个研究线后续变成单一资产策略家族，应迁入对应资产目录并保留这里的交叉引用。状态词定义见 `../strategy-status-glossary.md`。

## 当前研究线

- `Binance-1D-Turtle-Breakout`：`1d-turtle-breakout/`。BTC/ETH/HYPE 日线 20/10 turtle breakout 诊断；`exploratory diagnostic`。
- `Binance-15M-Multi-Indicator-Intraday-Transfer`：`15m-multi-indicator-intraday/`。基于 `HYPE-15M-MII-V1.1` 机制的 BTC/ETH `15m` 受约束参数迁移诊断；整体不提升。
- `Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble`（`BIN-1H-AR-MAE`）：`1h-adaptive-regime-multi-asset-ensemble/`。六个 `1h` adaptive-regime 家族登记版本的跨资产组合；V1 已登记；当前 `NO-GO / not promoted / not live-ready`。主账：`1h-adaptive-regime-multi-asset-ensemble/binance-1h-ar-mae-core-ledger.md`。
