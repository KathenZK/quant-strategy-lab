# HYPE-15M-Bollinger-Keltner-Squeeze-Breakout Core Ledger

## Family Identity

- 完整名称：`HYPE-15M-Bollinger-Keltner-Squeeze-Breakout`
- 别名：`HYPE-15M-BKSB`
- 市场：Binance USD-M Futures `HYPEUSDT` perpetual
- 周期：`15m`
- 机制：Bollinger 进入 Keltner 后释放，价格突破压缩区间时顺方向入场。
- 边界：不是 `HYPE-15M-Keltner-Trend-Breakout` 或 `HYPE-15M-MMTF` 的版本。

## Current State

- 当前状态：`explore / not promoted / not live-ready`
- 已登记版本：无
- 当前观察：冻结基础规则净收益 `-93.16%`、MaxDD `-94.31%`、641 笔、PF `0.570`；最低可行性门槛 `1/8`。
- Live readiness：无候选、无 live spec、无 runner、无 dry-run。
- 下一决策门：只有预先提出、显著减少噪声交易且不使用本次结果调参的新机制才可重开。

## Version Rules

- 只有明确冻结、可复现并通过基础收益/回撤与执行审计的机制才可登记 `V1`。
- BB/KC 倍数、窗口、止损或 timeout 网格不自动构成版本。
- 其他周期是独立 family，不共享版本号或状态。

## Version Table

| Observation / Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| 2026-07-23 基础规则诊断 | explore / not promoted / not live-ready | `BB(20,2)` inside `KC(20,1.5)` 后压缩区间突破 | `-93.16% / -94.31% MaxDD / 641 trades / PF 0.570` | [诊断](diagnostics/hype-15m-bksb-baseline-2026-07-23.md) | 失败；不登记版本 |

## Shared Assumptions

- 数据：闭合 Binance HYPEUSDT `15m`，截至 `2026-07-23 05:45 UTC`，质量 blocker `0`。
- 成本：每 fill 手续费 `0.001`、adverse slippage `4 bps`、实际 funding。
- 执行：K0 闭合、K1 open、固定 `1x`、15m 子柱止损、单持仓。

## Evidence Map

- [诊断报告](diagnostics/hype-15m-bksb-baseline-2026-07-23.md)
- [决策日志](decision-log.md)
- [消费脚本](scripts/run_baseline.py)
- [共享内核](../../_shared-kernels/bollinger-keltner-squeeze-breakout/README.md)
- [汇总 JSON](artifacts/hype-15m-bksb-baseline-2026-07-23-summary.json)

