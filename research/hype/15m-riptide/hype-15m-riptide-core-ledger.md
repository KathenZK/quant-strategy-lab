# HYPE-15M-Riptide Core Ledger

## Family Identity

- 完整家族名：`HYPE-15M-Riptide`
- 别名：`HYPE-15M-RIPTIDE`
- 市场：Binance USD-M `HYPEUSDT` 永续，`15m`
- 机制：外部 `V13` 的波动状态切点与 walk-forward 规则，本地按缓存数据复现审计。
- 碰撞警告：本地尚未登记 `V13`；不得把外部命名当作本仓库 promotion。

## Current State

- 当前版本：无登记版本；`HYPE-15M-Riptide-V13` 仅为外部规格复现观察。
- 当前状态：`explore / not promoted / not live-ready`。
- 结论：缓存口径机制和 WF 大体成立，但固定 `cut_hi=104.7` 未完全对齐；缺标准数据湖、真实 1h K、funding 与逐笔对账。
- 下一门：补齐标准数据并逐笔对齐 signal/entry/exit；完成前不得讨论 dry-run。

## Version Rules

- 概念草案不是版本。
- 只有 signal/state machine、成本、参数和可复现证据冻结后，用户明确登记才创建 `Vx`。

## Version Table

| Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| `external V13 cache observation` | `explore / not promoted / not live-ready` | 固定切点 + 150d rolling WF | 默认成本后固定 `+57.47%`/MDD `-34.56%`；WF `+38.75%`/MDD `-15.82%` | [缓存审计](diagnostics/hype-15m-riptide-v13-cache-audit-2026-06-30.md) | 未对齐，不登记 |

## Shared Assumptions

- 数据：当前为 legacy 15m cache，1h RV 由 15m 聚合；缺标准 raw/normalized 和真实 funding。
- 成本：fee `0.001/fill`、slippage `4 bps/fill`；funding 尚未纳入。
- 执行：闭合 K；逐笔 signal/entry/exit 尚未与外部规格对账。
- 仓位：按外部规格观察；本仓库未授权 runner。

## Evidence Map

- 诊断：[V13 缓存复现审计](diagnostics/hype-15m-riptide-v13-cache-audit-2026-06-30.md)
- 决策：[decision-log.md](decision-log.md)
- 脚本：[scripts/](scripts/)
- 产物：[artifacts/README.md](artifacts/README.md)
