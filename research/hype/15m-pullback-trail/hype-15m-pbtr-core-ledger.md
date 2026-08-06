# HYPE-15M-Pullback-Trail Core Ledger

## Family Identity

- 完整家族名：`HYPE-15M-Pullback-Trail`
- 别名：`HYPE-15M-PBTR`
- 市场：Binance USD-M `HYPEUSDT` 永续，`15m`
- 机制：趋势过滤后的回踩入场，独立 trailing/protection stop 退出。
- 碰撞警告：不是 `HYPE-5M-Pullback-Trail`；版本、指标和执行证据不可互借。

## Current State

- 当前版本：无登记版本；有 V3.3 迁移与 bracket 搜索两条观察。
- 当前状态：`explore / not promoted / not live-ready`。
- 结论：5m V3.3 直接迁移仍存在 trailing 解锁后 stop 不可执行问题；bracket 候选 OOS 样本过短。
- 下一门：先修复实时 stop 状态机，并取得足够 OOS；当前不得登记或 promotion。

## Version Rules

- baseline 与试验标签不是 `Vx`。
- 入场机制、stop 状态机、成本口径冻结并通过审计后，才可明确登记版本。

## Version Table

| Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| `V3.3 transplant observation` | `explore / not promoted / not live-ready` | 5m V3.3 向 15m 直接迁移 | trailing 解锁后 stop 可执行性未修复 | [迁移诊断](diagnostics/hype-15m-pullback-trail-v3-3-migration-2026-06-30.md) | 不登记 |
| `bracket observation` | `explore / not promoted / not live-ready` | 回踩事件 + 固定 bracket | 代表行 `ema21_96_pb0.015_long_nocandle__ret32>=600__tp2_sl4_tx24`；OOS 过短 | [搜索诊断](diagnostics/hype-15m-pullback-trail-bracket-search-2026-06-30.md) | 保留观察 |

## Shared Assumptions

- 数据：Binance `HYPEUSDT` 闭合 `15m` K；窗口见两份诊断。
- 成本：fee `0.001/fill`、slippage `4 bps/fill`；funding 尚未完整纳入。
- 执行：闭合 K 产生状态，trailing/protection stop 必须按实时可执行顺序审计。
- 仓位：单仓；当前不授权 runner。

## Evidence Map

- 诊断：[V3.3 迁移](diagnostics/hype-15m-pullback-trail-v3-3-migration-2026-06-30.md) · [bracket 搜索](diagnostics/hype-15m-pullback-trail-bracket-search-2026-06-30.md)
- 决策：[decision-log.md](decision-log.md)
- 脚本：[scripts/](scripts/)
- 产物：[artifacts/README.md](artifacts/README.md)
