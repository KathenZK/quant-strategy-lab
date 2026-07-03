# TRX Research Index

本目录存放 TRON（TRX）单资产策略家族。任何版本号都必须和市场、周期、机制一起引用。

## 当前研究线

- `TRX-1H-Adaptive-Regime`（`TRX-1H-AR`）：Binance USD-M Futures `TRXUSDT` perpetual `1h` 多指标自适应 regime 广泛搜索；最近三个月为 locked OOS；`V1base` 为领先观察值 diagnostic baseline，`V2` 为全参数消融后的 clean baseline；当前结论为 `NO-GO / not promoted / not live-ready`。

## 数据与执行口径

TRX 合约研究遵循仓库的 data-quality-first、Binance 成本和 live-executable 审计规则。未经 locked OOS、成本/延迟压力、参数邻域、订单过滤器和生产状态机审计，不得标记为 candidate、paper-live、dry-run、handoff 或 live。
