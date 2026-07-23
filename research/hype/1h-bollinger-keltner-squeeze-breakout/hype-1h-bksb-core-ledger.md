# HYPE-1H-Bollinger-Keltner-Squeeze-Breakout Core Ledger

## Family Identity

- 完整名称：`HYPE-1H-Bollinger-Keltner-Squeeze-Breakout`
- 别名：`HYPE-1H-BKSB`
- 市场：Binance USD-M Futures `HYPEUSDT` perpetual
- 周期：`1h`
- 机制：Bollinger 进入 Keltner 后释放，价格突破压缩区间时顺方向入场。
- 边界：不是 `HYPE-1H-Adaptive-Regime`、`HYPE-1H-MMTF` 或其他周期 BKSB 的版本。

## Current State

- 当前状态：`explore / not promoted / not live-ready`
- 已登记版本：无
- 当前观察：冻结基础规则净收益 `-51.71%`、MaxDD `-68.32%`、165 笔、PF `0.814`；最低可行性门槛 `4/8`。最近 `3m/6m` 为正但 development/validation/full 失败。
- Live readiness：无候选、无 live spec、无 runner、无 dry-run。
- 下一决策门：不在已见近期窗口调参；若重开，需预先提出新机制并使用新的 prospective OOS。

## Version Rules

- 只有明确冻结、可复现并通过基础收益/回撤与执行审计的机制才可登记 `V1`。
- BB/KC 倍数、窗口、止损或 timeout 网格不自动构成版本。
- 其他周期是独立 family，不共享版本号或状态。

## Version Table

| Observation / Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| 2026-07-23 基础规则诊断 | explore / not promoted / not live-ready | `BB(20,2)` inside `KC(20,1.5)` 后压缩区间突破 | `-51.71% / -68.32% MaxDD / 165 trades / PF 0.814` | [诊断](diagnostics/hype-1h-bksb-baseline-2026-07-23.md) | 全样本失败；不登记版本 |

## Shared Assumptions

- 数据：从闭合、连续 Binance HYPEUSDT `15m` 聚合完整 UTC `1h` 桶，质量 blocker `0`。
- 成本：每 fill 手续费 `0.001`、adverse slippage `4 bps`、实际 funding。
- 执行：K0 闭合、K1 open、固定 `1x`、真实 15m 子柱止损、单持仓。

## Evidence Map

- [诊断报告](diagnostics/hype-1h-bksb-baseline-2026-07-23.md)
- [决策日志](decision-log.md)
- [消费脚本](scripts/run_baseline.py)
- [共享内核](../../_shared-kernels/bollinger-keltner-squeeze-breakout/README.md)
- [汇总 JSON](artifacts/hype-1h-bksb-baseline-2026-07-23-summary.json)

