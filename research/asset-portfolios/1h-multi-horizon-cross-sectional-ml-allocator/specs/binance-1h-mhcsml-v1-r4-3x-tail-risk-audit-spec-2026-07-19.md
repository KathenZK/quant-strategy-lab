# BIN-1H-MHCSML-V1 R4 三倍敞口尾部风险审计规格

## 状态与授权边界

本规格只定义基础 prospective OOS 全部门槛通过后如何评估三倍敞口，不改变 `BIN-1H-MHCSML-V1 freeze R4` 的信号、模型、基础仓位或最终硬门槛。

- 基础版本：每批 sleeve `3.125%`，最大 12 批重叠，计划 gross cap `37.5%`。
- 三倍版本：冻结信号和每批入选腿完全不变，只把每条 `leg_exposure` 乘 `3`；每批 sleeve `9.375%`，最大计划 gross `112.5%`。
- 只有最终裁决器输出 `BASE_STRATEGY_RESEARCH_GATES_PASS` 且 `three_x_evaluation_authorized=true` 才能读取 revealed legs 并运行本审计。
- 基础版本任一门槛失败，本审计状态只能是 `NOT_AUTHORIZED`，不得用三倍结果挽救基础版本。
- 三倍审计即使通过，也不授权 promotion、dry-run 或 live。

## 账户和事件模型

初始账户权益为 `1.0`，使用 cross-margin 代理模型。每个小时按以下顺序处理：

1. 用该小时 mark K 线 `open` 计算已有仓位的未实现盈亏和入场前账户权益；
2. 对满足 `entry_time < funding_ts <= exit_time` 的已有空头仓位结算 funding，空头收到 `notional * funding_rate`；
3. 在计划退出时间按普通成交 K 线 `open` 平仓，实现 `notional * (1-exit/entry)`，扣退出侧成本；
4. 用退出和 funding 后、仍含其它仓位未实现盈亏的账户权益计算新批次名义本金；
5. 新腿 `notional = current_equity * frozen_leg_exposure * 3`，按普通 K 线 `open` 建立空头并扣入场侧成本；
6. 用该小时各 symbol 的 mark `high` 同时冲击全部空头，形成保守的小时内最坏权益和 maintenance margin；
7. 若最坏权益不高于 maintenance margin，场景记为强平并停止，不假设之后可以恢复。

普通权益：

```text
equity_open = cash_balance + sum(notional * (1 - mark_open / entry_open))
```

小时内最坏权益和维持保证金：

```text
worst_equity = cash_balance + sum(notional * (1 - mark_high / entry_open))
mark_notional = sum(notional * mark_high / entry_open)
maintenance_margin = maintenance_margin_rate * mark_notional
liquidated = worst_equity <= maintenance_margin
```

这里把不同币种同一小时的 mark high 同时发生视为联合压力，故比真实路径更保守。它不尝试复刻 Binance 每个历史时点的分层 risk bracket；改用多档统一 MMR 检查模型敏感性。

## 成本、funding 与场景

基础双边成本为 `0.28%`，每侧 `0.14%`；压力成本为 `1.5x`，每侧 `0.21%`。所有成本按开仓名义本金扣除。funding 使用实际结算事件，不按小时插值。

必须同时运行 6 个场景：

| 场景维度 | 值 |
| --- | --- |
| 成本倍数 | `1.0`, `1.5` |
| 统一 maintenance margin rate | `0.5%`, `1.0%`, `2.5%` |

每个场景报告累计收益、普通 open-to-open 最大回撤、联合 mark-high 最坏回撤、最小绝对保证金缓冲、最小保证金缓冲/权益、最大实际 gross、是否强平及强平时间。

## 一致性检查

运行三倍模拟前必须：

- 验证 master freeze SHA、最终裁决合同和 final adjudication；
- 验证 revealed legs/decisions SHA；
- 只使用 `strategy=r4` 的腿；
- 用真实 entry/exit open 和 `(entry,exit]` funding 重新计算每条基础单位收益，必须与 reveal 的 `trade_return` 对齐；
- 普通/mark/funding 键必须唯一，任一计划时点缺 mark open/high 或 funding 覆盖异常时 fail closed；
- 不允许改变信号、退出时间、币种、腿数或按结果选择 MMR 场景。

## 预先定义的三倍研究门禁

这些是三倍版本的附加风险门禁，不替代基础策略原始硬门槛：

1. 六个场景均不得触发强平；
2. `1.5x` 成本、`MMR=2.5%` 场景累计收益仍为正；
3. 六个场景普通最大回撤均不超过 `50%`；
4. 六个场景联合 mark-high 最坏回撤均不超过 `60%`；
5. 六个场景最小保证金缓冲必须为正；
6. 最大实际 gross 不得显著超过计划上限：容许价格漂移后上限 `1.50x` equity；超过则门禁失败但仍完整报告。

全部通过只记为 `THREE_X_TAIL_RISK_AUDIT_PASS / not promoted / not live-ready`；任一失败记 `THREE_X_TAIL_RISK_AUDIT_FAILED / not promoted / not live-ready`。无论结果如何，不得反向修改基础 R4。

## 交付

授权后输出：

- 6 场景 JSON/CSV；
- 逐小时账户权益、最坏权益、gross 和 maintenance margin；
- 强平事件或最小保证金缓冲锚点；
- 中文三倍尾部风险报告；
- 本次实际使用的 mark path 与 funding event 输入切片 Parquet；
- master、风险合同、最终裁决、reveal 报告、revealed legs/decisions、输入切片和全部输出 SHA 的 JSON 收据及 `.sha256` sidecar。

本规格在基础 OOS 揭盲前固定，因此三倍门槛不是看过结果后追加的选择性标准。
