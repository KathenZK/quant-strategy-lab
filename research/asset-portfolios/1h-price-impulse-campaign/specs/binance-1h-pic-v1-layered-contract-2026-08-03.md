# BIN-1H-PIC-V1 Layered Candidate 冻结合同（2026-08-03）

## 1. 机制变化

V1 保留 V0 的数据、`4h scaled impulse >= 1.0`、方向、`1R` 原始 stop、24h validation、14d timeout、成本和 next-open 时序；只改变仓位生命周期：

- 完整 campaign 计划风险仍为账户权益 `1%`，但 probe 只使用完整 planned quantity 的 `25%`。
- MFE 首次达到 `0.5R/1R/2R` 后，在下一根 `1h open` 尝试把总 quantity 提高至完整计划量的 `50%/75%/100%`。
- 每次 add 至少间隔 `4h`；必须按当时 mark 扣预计退出成本后净浮盈为正；亏损中禁止增加 quantity。
- add quantity 同时受 `3x` leverage 和 projected stop-out 约束。假设新增仓以当前 open adverse fill 成交、全仓在原始 stop adverse fill 退出后，campaign equity 不得低于 entry equity 的 `99%`；不足的风险预算只允许部分 add，不能移动 stop 来强行容纳目标 quantity。
- MFE 达 `2R` 后，如果已闭合 close 的 progress 跌破 peak MFE 的 `50%`，下一根 open 只减到最初 probe quantity；之后永久禁止重新加仓。原始 probe 继续使用初始 stop 或 14d timeout追踪右尾。
- 同一 bar stop 与其他动作冲突时，先执行 stop；quantity 变化只使用下一根 open。

这不是 V0 的参数优化：V0 是固定满额 quantity + 半 MFE 全平；V1 是 probe-confirm-layer + half-giveback 去风险的离散订单状态机，需要真实 resize 执行能力。

## 2. 冻结实验

- ETH 是执行候选，BTC/HYPE/SOL 原样控制；Long/Short 对称。
- gross、base `10bps fee + 4bps slippage + funding`、8bps stress。
- 最近 `1d/7d/1m/3m/6m/1y`；120d window / 30d step rolling。
- 预声明消融：`probe_only`、`no_half_reduce`、`full_entry_no_add`；不得把消融改成 V1 主版本。

最低历史筛查门禁：ETH base return `>0`、Sharpe `>0`、MDD `>-20%`、campaigns `>=30`、6m 非负、rolling 正窗口 `>=60%`、8bps stress 非负、无风险/杠杆/时序 blocker，且 full base return 不低于 probe_only。由于规则形成时 V0 全历史已揭示，即使全部通过也只能登记候选并等待新 prospective OOS，不能直接 promotion。

