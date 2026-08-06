# BIN-1H-PIC-V2 Risk-Invariant Candidate 冻结合同（2026-08-03）

## 1. 形成原因与版本边界

V1 在运行前只约束每次 add 成交后的 projected stop-out，不持续处理持仓期间的 funding 漂移。完整历史揭示后，ETH base 有 62 个 campaign、6,097 个持仓小时突破账户入场权益 `1%` 的 stop-out 损失上限，最坏为 `2.06%`。因此 V1 保持失败事实，不回写规则。

V2 是只修复风险不变量的 materially new 执行候选。它完整保留 V1 的 admission、方向、初始 probe、MFE 分层、半回吐减仓、原始 stop、24h validation、14d timeout、成本与 next-open 时序；不改变任何收益选择阈值。

## 2. 冻结风险状态机

- campaign 的硬风险上限仍为 entry equity 的 `1%`。
- add 的 operational stop-out budget 固定为 entry equity 的 `0.9%`，其余 `0.1%` 只作为下一次不利 funding 与执行误差缓冲，不得用于增加目标 quantity。
- 每根 `1h` bar 先按既有回测口径入账该 bar 的实际 funding；若持仓存在，立即按当前 open adverse fill 计算原始 stop adverse fill 下的 projected stop-out equity。
- projected stop-out 损失超过 `0.9%` 时，在同一 open 以 LIFO 顺序只减新增 layers，直到恢复到 `0.9%` 以内；该动作记录为 `risk_trim`，不触发永久 no-readd。
- 如果去掉全部新增 layers 后仍无法恢复 `0.9%`，以 `risk_budget_exhausted` 平掉原始 probe。禁止移动 stop、扩大风险预算或用未来盈利抵消当前风险超限。
- discretionary add 完成后仍须满足 `0.9%` operational stop-out budget 与 `3x` leverage cap；硬门禁审计继续按 `1%` 检查，任何 bar 超过即失败。
- 同一 bar 冲突顺序：open gap stop → 24h/14d time exit → 已挂 half-giveback reduce/add → entry → funding → risk maintenance → intrabar stop → close-derived next-bar state。

## 3. 冻结实验

- ETH 为执行候选，BTC/HYPE/SOL 同规则控制；Long/Short 对称。
- gross、base `10bps fee + 4bps slippage + funding`、8bps stress。
- 最近 `1d/7d/1m/3m/6m/1y`；ETH `120d window / 30d step` rolling。
- 预声明诊断臂：`full`、`probe_only`、`maintenance_no_buffer`（1.0% operational budget）、`buffer_no_maintenance`（0.9% 但不持续维护）。诊断臂不得替代 V2 主版本。

最低历史筛查门禁与 V1 相同：ETH base return `>0`、Sharpe `>0`、MDD `>-20%`、campaigns `>=30`、最近 6m 非负、rolling 正窗口 `>=60%`、8bps stress 非负、无 `1%` 风险/`3x` 杠杆 blocker，且 full base return 不低于 probe_only。

V2 由已揭示的 V1 全历史风险缺口形成。即使全部历史门禁通过，也只能保持 `explore` 或在用户明确要求后登记；必须取得新的 prospective OOS 才能进入 promotion review，不能直接生成 live spec、修改 manifest 或接入 quant-runner。
