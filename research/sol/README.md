# SOL Research Index

本目录存放 Solana 单资产策略家族。任何版本号都必须和市场、周期、机制一起引用；状态词定义见 [strategy-status-glossary.md](../../docs/research-governance/strategy-status-glossary.md)。

## 当前研究线

- `SOL-1H-Adaptive-Regime`（`SOL-1H-AR`）：[1h-adaptive-regime/](1h-adaptive-regime/README.md)。Binance USD-M Futures `SOLUSDT` perpetual `1h` 多指标自适应 regime 研究；V1、V2 已登记。2026-07-10 机制诊断确认 Donchian 可作为 core，VWAP short 是近期失效来源；`3-bar roc6+MACD confirm` 状态机把 reused holdout 改为 `+2.61%`，但只有 `3` 笔。该结构冻结为 `V2-SM-OBS` 等待 fresh forward，不登记 V3。当前 `registered / not promoted / not live-ready`。主账：[sol-1h-ar-core-ledger.md](1h-adaptive-regime/sol-1h-ar-core-ledger.md)。
