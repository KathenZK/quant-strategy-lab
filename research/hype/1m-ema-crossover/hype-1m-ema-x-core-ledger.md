# HYPE-1M-EMA-Crossover Core Ledger

## Family Identity

- 完整家族名：`HYPE-1M-EMA-Crossover`
- 别名：`HYPE-1M-EMA-X`
- 市场：Binance USD-M `HYPEUSDT` 永续，`1m`
- 机制：EMA crossover / slope 与 body/volatility filter 驱动方向切换。
- 碰撞警告：不是 `HYPE-15M-EMA-Crossover`，不得继承其 `V13` 等版本身份。

## Current State

- 当前版本：无正式登记版本；首选观察规则 `HYPE-1M-EMA-Crossover-TRAIL-144-1597`。
- 当前状态：`explore / not promoted / not live-ready`。
- 结论：已有 live-executable 搜索、偏离止盈和 V35 filter 迁移诊断；试验 sizing `2x`、硬上限 `3x`，但尚无 forward/funding/重启审计。
- 下一门：完成 forward 验证、成本与 runner 幂等/恢复审计后，才可讨论登记或 promotion。

## Version Rules

- 15m 参数移植不构成本家族版本。
- 只有独立参数、执行状态机和证据冻结后，用户明确登记才创建 `Vx`。

## Version Table

| Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| `TRAIL-144-1597 observation` | `explore / not promoted / not live-ready` | 1m EMA crossover + trailing | 当前首选；试验 sizing `2x`、硬上限 `3x` | [首轮搜索](diagnostics/hype-1m-ema-crossover-live-search-2026-06-25.md) | 未登记，待 forward |

## Shared Assumptions

- 数据：Binance `HYPEUSDT` 闭合 `1m` K；缺口、重复与时间边界需先审计。
- 成本：fee `0.001/fill`、slippage `4 bps/fill`，且需额外评估 1m 冲击。
- 执行：closed-bar-only，下一根可执行价格；不得同 K 回填。
- 仓位：单仓；高换手下的风险预算尚未冻结。

## Evidence Map

- 诊断：[首轮搜索](diagnostics/hype-1m-ema-crossover-live-search-2026-06-25.md) · [偏离止盈](diagnostics/hype-1m-ema-deviation-take-profit-2026-06-27.md) · [V35 filter](diagnostics/hype-1m-ema-v35-filter-overlay-2026-06-27.md)
- 决策：[decision-log.md](decision-log.md)
- 脚本：[scripts/](scripts/)
- 产物：[artifacts/README.md](artifacts/README.md)
