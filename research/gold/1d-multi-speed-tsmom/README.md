# GOLD-1D-Multi-Speed-TSMOM

- Alias：`GOLD-1D-MS-TSMOM`
- 市场/周期：Stooq `GC.F` Gold-COMEX continuous futures，UTC session-date `1d`
- 机制：月末 `sign(1M/3M/12M return)` 等权，60-day center-of-mass EWMA 波动率缩放至单资产 10% 目标波动。
- 当前状态：`explore / not promoted / not live-ready`

## 边界

独立黄金期货家族，不是 BTC 经典 EWMAC 或多资产 TSMOM 的迁移。当前输入为社区保留的
Stooq `GC.F` 1985–2021 快照；连续合约换月/调整方法未获逐合约核验，只能作为
`raw_unaccepted` 探索数据。Yahoo `GC=F` 2000–2026 候选因 441 行 OHLC 不自洽被拒绝。

## 入口

- 主账：[gold-1d-ms-tsmom-core-ledger.md](gold-1d-ms-tsmom-core-ledger.md)
- 决策记录：[decision-log.md](decision-log.md)
- 基线契约：[specs/gold-1d-ms-tsmom-baseline-2026-08-18.md](specs/gold-1d-ms-tsmom-baseline-2026-08-18.md)
- 基线诊断：[diagnostics/gold-1d-ms-tsmom-backtest-2026-08-18.md](diagnostics/gold-1d-ms-tsmom-backtest-2026-08-18.md)
- 2022–2026 近期扩展：[diagnostics/gold-1d-ms-tsmom-recent-2026-08-18.md](diagnostics/gold-1d-ms-tsmom-recent-2026-08-18.md)
- Lab 事实源与多资产交接：
  [lab-handoff-2026-08-19.md](../../asset-portfolios/1d-tradfi-futures-tsmom/lab-handoff-2026-08-19.md)
- 脚本：[scripts/README.md](scripts/README.md)
- 产物：[artifacts/README.md](artifacts/README.md)
