# BTC Research Index

本目录存放 Bitcoin 单资产策略家族。任何版本号都必须和市场、周期、机制一起引用。

## 当前研究线

- `BTC-1H-Adaptive-Regime`（`BTC-1H-AR`）：Binance USD-M Futures `BTCUSDT` perpetual `1h` 多指标自适应 regime 家族；V1 为 diagnostic baseline，V2 为 V1 clean scaled frontier paper-audit observation，V3 为 V2 micro-tune diagnostic observation；V3 已完成全参数消融与多窗口回测，未产生严格改善单字段，当前仍 `not live-ready`。

## 数据与执行口径

BTC 合约研究默认遵循仓库的 data-quality-first、Binance 成本和 live-executable 审计规则。未经 locked OOS、成本/延迟压力、参数邻域和生产状态机审计，不得标记为 candidate、paper-live、dry-run、handoff 或 live。
