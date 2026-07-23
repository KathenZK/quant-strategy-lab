# HYPE-1D-Bollinger-Keltner-Squeeze-Breakout Core Ledger

## Family Identity

- 完整名称：`HYPE-1D-Bollinger-Keltner-Squeeze-Breakout`
- 别名：`HYPE-1D-BKSB`
- 市场：Binance USD-M Futures `HYPEUSDT` perpetual
- 周期：`1d`
- 机制：Bollinger 进入 Keltner 后释放，价格突破压缩区间时顺方向入场。
- 边界：不是 `HYPE-1D-MHEF`、`HYPE-1D-PT` 或其他周期 BKSB 的版本。

## Current State

- 当前状态：`explore / not promoted / not live-ready`
- 已登记版本：无
- 当前观察：冻结基础规则净收益 `-34.73%`、MaxDD `-55.40%`、7 笔、PF `0.405`；最低可行性门槛 `2/8`。短 horizon 事件均值为正但仅 8 个事件且 bootstrap 区间跨零。
- Live readiness：无候选、无 live spec、无 runner、无 dry-run。
- 下一决策门：等待显著更多独立日线事件；不得把当前 8 个已见事件用于调参。

## Version Rules

- 只有明确冻结、可复现并通过基础收益/回撤与执行审计的机制才可登记 `V1`。
- BB/KC 倍数、窗口、止损或 timeout 网格不自动构成版本。
- 其他周期是独立 family，不共享版本号或状态。

## Version Table

| Observation / Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| 2026-07-23 基础规则诊断 | explore / not promoted / not live-ready | `BB(20,2)` inside `KC(20,1.5)` 后压缩区间突破 | `-34.73% / -55.40% MaxDD / 7 trades / PF 0.405` | [诊断](diagnostics/hype-1d-bksb-baseline-2026-07-23.md) | 亏损且样本不足；不登记版本 |

## Shared Assumptions

- 数据：从闭合、连续 Binance HYPEUSDT `15m` 聚合完整 UTC `1d` 桶，质量 blocker `0`。
- 成本：每 fill 手续费 `0.001`、adverse slippage `4 bps`、实际 funding。
- 执行：K0 闭合、K1 open、固定 `1x`、真实 15m 子柱止损、单持仓。

## Evidence Map

- [诊断报告](diagnostics/hype-1d-bksb-baseline-2026-07-23.md)
- [决策日志](decision-log.md)
- [消费脚本](scripts/run_baseline.py)
- [共享内核](../../_shared-kernels/bollinger-keltner-squeeze-breakout/README.md)
- [汇总 JSON](artifacts/hype-1d-bksb-baseline-2026-07-23-summary.json)

