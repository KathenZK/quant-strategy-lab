# SOL Research Index

本目录存放 Solana 单资产策略家族。任何版本号都必须和市场、周期、机制一起引用。

## 当前研究线

- `SOL-1H-Adaptive-Regime`（`SOL-1H-AR`）：Binance USD-M Futures `SOLUSDT` perpetual `1h` 多指标自适应 regime 研究；`SOL-1H-Adaptive-Regime-V1` 已登记为 diagnostic baseline，`SOL-1H-Adaptive-Regime-V2` 已登记为高胜率最佳观察值 diagnostic observation。V2 full annual `2.07x`、DD `-17.41%`、win `93.91%`，但最近三个月 reused holdout annual `0.70x`、win `66.67%`，且未达到 `10x / 80% / <20% DD` 硬目标；当前仍为 `NO-GO / not promoted / not live-ready`。

## 数据与执行口径

SOL 合约研究遵循仓库的 data-quality-first、Binance 成本和 live-executable 审计规则。未经 locked OOS、成交延迟、成本压力、参数邻域和生产状态机审计，不得标记为 candidate、paper-live、dry-run、handoff 或 live。
