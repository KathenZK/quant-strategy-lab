# SOL Research Index

本目录存放 Solana 单资产策略家族。任何版本号都必须和市场、周期、机制一起引用。版本级指标与证据以各家族 core ledger 为唯一事实源。

## 当前研究线

- `SOL-1H-Adaptive-Regime`（`SOL-1H-AR`）：`1h-adaptive-regime/`。Binance USD-M Futures `SOLUSDT` perpetual `1h` 多指标自适应 regime 研究；V1、V2 已登记，reused holdout 未达硬目标；当前 `NO-GO / not promoted / not live-ready`。主账：`1h-adaptive-regime/sol-1h-ar-core-ledger.md`。

## 数据与执行口径

SOL 合约研究遵循仓库的 data-quality-first、Binance 成本和 live-executable 审计规则。未经 locked OOS、成交延迟、成本压力、参数邻域和生产状态机审计，不得标记为 candidate、dry-run、handoff 或 live。状态词定义见 `../strategy-status-glossary.md`。
