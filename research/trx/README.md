# TRX Research Index

本目录存放 TRON（TRX）单资产策略家族。任何版本号都必须和市场、周期、机制一起引用。

## 当前研究线

- `TRX-1H-Adaptive-Regime`（`TRX-1H-AR`）：Binance USD-M Futures `TRXUSDT` perpetual `1h` 多指标自适应 regime 广泛搜索；最近三个月为 reused locked OOS；`V1` 为领先观察值 diagnostic baseline，`V2` 为正式登记的 clean 参数版本，且已完成 V2 全参数消融 `36/36`、one-at-a-time `211` 行、执行重放违规 `0`；V2 消融引导微调观察值已登记为 `V3`，current full 提升至 `5.686x annual / -17.17% DD / 92.47% win`，但 reused holdout 胜率 `77.78%`，不 promotion；V3 全参数说明见 `1h-adaptive-regime/canonical-specs/trx-1h-ar-v3-parameter-spec-2026-07-06.md`；后续近期适配复搜 `80,800` 个 unique configs 仍无 recent hard hit，当前结论为 `NO-GO / not promoted / not live-ready`。

## 数据与执行口径

TRX 合约研究遵循仓库的 data-quality-first、Binance 成本和 live-executable 审计规则。未经 locked OOS、成本/延迟压力、参数邻域、订单过滤器和生产状态机审计，不得标记为 candidate、paper-live、dry-run、handoff 或 live。
