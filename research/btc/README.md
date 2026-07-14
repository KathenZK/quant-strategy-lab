# BTC Research Index

本目录存放 Bitcoin 单资产策略家族。任何版本号都必须和市场、周期、机制一起引用；状态词定义见 [strategy-status-glossary.md](../../docs/research-governance/strategy-status-glossary.md)。

## 当前研究线

- `BTC-1H-Adaptive-Regime`（`BTC-1H-AR`）：[1h-adaptive-regime/](1h-adaptive-regime/README.md)。Binance USD-M Futures `BTCUSDT` perpetual `1h` 多指标自适应 regime 家族；V1-V4 已登记；V4 参数邻域已判定局部耗尽，VWAP short-only、wick transition-only、MACD replace-Keltner 三条结构优化路线均为 `0` 严格 gate 命中，未产生 V5；当前 `registered / not promoted / not live-ready`。主账：[btc-1h-ar-core-ledger.md](1h-adaptive-regime/btc-1h-ar-core-ledger.md)。
