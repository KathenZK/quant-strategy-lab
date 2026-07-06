# ETH Research Index

本目录存放 Ethereum 单资产策略家族。任何版本号都必须和市场、周期、机制一起引用。

## 当前研究线

- `ETH-1H-Adaptive-Regime`（`ETH-1H-AR`）：Binance USD-M Futures `ETHUSDT` perpetual `1h` 多指标自适应 regime 家族；V1 已登记为 diagnostic baseline，V2 已登记为 clean tuned diagnostic observation，V2.1 已登记为 high-win tuned diagnostic observation；V2.1 current full 达 `3.0277x / -19.55% / 87.50%`，但 reused holdout 为负且压力测试穿越回撤边界；当前 `NO-GO / not promoted / not live-ready`。

## 数据与执行口径

ETH 合约研究默认遵循仓库的 data-quality-first、Binance 成本和 live-executable 审计规则。未经 locked OOS、成本/延迟压力、参数邻域和生产状态机审计，不得标记为 candidate、paper-live、dry-run、handoff 或 live。
