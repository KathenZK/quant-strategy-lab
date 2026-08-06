# HYPE-1M-MA-Pullback-Scalp Core Ledger

## Family Identity

- 完整家族名：`HYPE-1M-MA-Pullback-Scalp`
- 别名：`HYPE-1M-MA-PBS`
- 市场：Binance USD-M `HYPEUSDT` 永续，`1m`
- 机制：短均线趋势中的回踩恢复入场，快速止损/止盈/超时退出。
- 碰撞警告：不是 `HYPE-5M-MA-Pullback-Scalp` 或 Pullback-Trail。

## Current State

- 当前版本：无登记版本。
- 当前状态：`explore / not promoted / not live-ready`。
- 结论：首轮 6740 组可执行搜索中，`>=60` 笔样本无盈利配置，`0` 个通过 paper gate。
- 下一门：当前机制/成本模型下停止参数微调；重开须改变可执行机制。

## Version Rules

- timeframe 迁移和参数草案不是版本。
- 入场/退出状态机、成本与证据冻结并由用户明确登记后，才创建 `Vx`。

## Version Table

| Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| `6740-grid observation` | `explore / not promoted / not live-ready` | MA pullback scalp 可执行搜索 | 6740 组；`>=60` 笔无盈利；paper gate `0` 通过 | [搜索诊断](diagnostics/hype-1m-ma-pullback-scalp-search-2026-06-26.md) | 不登记、不 promotion |

## Shared Assumptions

- 数据：Binance `HYPEUSDT` 闭合 `1m` K；需审计缺口与微观时序。
- 成本：fee `0.001/fill`、slippage `4 bps/fill` 只是下限，需压力测试。
- 执行：closed-bar-only、下一 tick/open 可执行；stop 不得使用陈旧价格。
- 仓位：单仓、短持有；restart 与 missing-bar 行为待定义。

## Evidence Map

- 诊断：[首轮可执行搜索](diagnostics/hype-1m-ma-pullback-scalp-search-2026-06-26.md)
- 决策：[decision-log.md](decision-log.md)
- 脚本：[scripts/](scripts/)
- 产物：[artifacts/README.md](artifacts/README.md)
