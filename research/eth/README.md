# ETH Research Index

本目录存放 Ethereum 单资产策略家族。任何版本号都必须和市场、周期、机制一起引用。版本级指标与证据以各家族 core ledger 为唯一事实源。

## 当前研究线

- `ETH-1H-Adaptive-Regime`（`ETH-1H-AR`）：`1h-adaptive-regime/`。Binance USD-M Futures `ETHUSDT` perpetual `1h` 多指标自适应 regime 家族；V1、V2、V2.1、V3 已登记，reused holdout 仍为负；当前 `NO-GO / not promoted / not live-ready`。主账：`1h-adaptive-regime/eth-1h-ar-core-ledger.md`。

## 数据与执行口径

ETH 合约研究默认遵循仓库的 data-quality-first、Binance 成本和 live-executable 审计规则。未经 locked OOS、成本/延迟压力、参数邻域和生产状态机审计，不得标记为 candidate、dry-run、handoff 或 live。状态词定义见 `../strategy-status-glossary.md`。
