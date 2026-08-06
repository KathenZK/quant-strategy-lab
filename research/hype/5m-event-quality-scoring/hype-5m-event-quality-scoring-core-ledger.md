# HYPE-5M-Event-Quality-Scoring Core Ledger

## Family Identity

- 完整家族名：`HYPE-5M-Event-Quality-Scoring`
- 别名：`HYPE-5M-EQS`
- 市场：Binance USD-M `HYPEUSDT` 永续，`5m`
- 机制：从多类规则事件中生成候选，以滚动历史 config/style/side 均值评分并按分位数交易。
- 边界：seed 来自 HYPE-5M-Micro-Scalp，但本家族不继承其版本或 promotion。

## Current State

- 当前 baseline：`Seeded-V0 / current_70_20_10__q80`。
- `Seeded-V1 / no_wick_no_breakout__cfg_side_88_12__q80` strict seed-generation audit 失败，仅保留 selection-bias 证据。
- 状态：全家族 `not promoted / not live-ready`；固定 seed-universe 收益不能作为 paper/live 候选。
- 下一门：严格滚动 seed 的新 V2 搜索；strict OOS 为正前不做 runner 对账或部署。

## Version Rules

- `Generic-V0` 是无 seed 的通用事件基线；`Seeded-V0` 引入 relaxed historical seeds。
- `V0.1` 只做 style prune/权重消融；`Seeded-V1` 将固定 seed 最优观察正式命名。
- 新版本必须从严格无前视 config universe 生成 seed；固定历史 seed 微调不构成 V2。

## Version Table

| Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| `Generic-V0` | no-go | 多源事件 + 低依赖 WF ranker | 252277 事件，paper gate `0` | [diagnostic](diagnostics/hype-5m-event-quality-v0-2026-06-27.md) | 不提升 |
| `Seeded-V0` | fixed-seed diagnostic | `0.70 cfg + 0.20 style + 0.10 side`，q80 | 633 笔、`+61.81%`、PF `1.128`、DD `-26.94%` | [baseline](diagnostics/hype-5m-seeded-event-quality-v0-2026-06-27.md) · [ablation](diagnostics/hype-5m-seeded-event-quality-v0-ablation-2026-06-27.md) | Base 证据 |
| `Seeded-V0.1-Style-Prune` | fixed-seed diagnostic | 去 wick/breakout，`0.875 cfg + 0.125 side` | 549 笔、`+287.61%`、PF `1.425`、DD `-16.30%` | [prune](diagnostics/hype-5m-seeded-event-quality-v01-style-prune-2026-06-27.md) · [full ablation](diagnostics/hype-5m-seeded-event-quality-v01-full-ablation-2026-06-27.md) | 只作 V2 参考 |
| `Seeded-V1` | fixed-seed diagnostic / anti-leakage failed | 正式冻结 V0.1 首位 | strict 493 笔、`-61.16%`、PF `0.843`、DD `-65.94%` | [feasibility](diagnostics/hype-5m-seeded-v1-live-feasibility-2026-06-27.md) · [strict audit](diagnostics/hype-5m-seeded-v1-strict-seed-audit-2026-06-27.md) | 不再是 audit lead |

## Shared Assumptions

- 数据/seed：固定 baseline 使用 relaxed rounds train 指标前 100 config；该 universe 已被证明有 selection bias。
- 成本：entry slippage `10.73 bps`、fee `4.1466 bps/fill`、exit slippage `-2.64 bps`。
- 执行：闭合 K、next-open、固定 TP/SL、stop-first、gap 按 open、timeout next-open。
- V1 成本压力：额外 RT 10bps 仍 PF `1.247`；20bps PF `1.090`/DD `-29.74%`；30bps 转负。
- live blockers：anti-leakage、路径/保护单、真实滑点、重启恢复、missing data、kill switch 与 dry-run reconciliation。

## Evidence Map

- 严格审计：[hype-5m-seeded-v1-strict-seed-audit-2026-06-27.md](diagnostics/hype-5m-seeded-v1-strict-seed-audit-2026-06-27.md)
- 实盘可行性：[hype-5m-seeded-v1-live-feasibility-2026-06-27.md](diagnostics/hype-5m-seeded-v1-live-feasibility-2026-06-27.md)
- 决策：[decision-log.md](decision-log.md)
- 脚本/产物：[scripts/](scripts/) · [artifacts/](artifacts/)
