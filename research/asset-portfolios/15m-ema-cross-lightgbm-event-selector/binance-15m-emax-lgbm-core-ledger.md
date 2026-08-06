# Binance-15M-EMA-Cross-LightGBM-Event-Selector Core Ledger

## Family Identity

- 完整家族名：`Binance-15M-EMA-Cross-LightGBM-Event-Selector`
- 别名：`BIN-15M-EMAX-LGBM`
- 市场：Binance USD-M USDT 永续、point-in-time 动态币池、`15m`
- 机制：EMA21/96 交叉事件经 LightGBM 三分类打分后，以 ATR bracket 和超时规则交易。
- 边界：不是横截面定时调仓或 HYPE Factor-ML；不同周期 EMAX-LGBM 各自独立。

## Current State

- 当前版本：无登记版本；仅保留终局观察。
- 当前状态：`archived`。
- 结论：2026H1 锁定 OOS 因分数整体下移导致阈值以上事件近零，按预注册规则 `HARD-GATE-FAILED`。
- 下一门：仅 materially new mechanism 可另立研究线；已揭示窗口不得再用于本机制选参。

## Version Rules

- 本家族未登记 `Vx`；诊断批次不构成版本。
- 若重开，必须声明新增信息源或状态机变化，并使用新的未揭示 OOS。

## Version Table

| Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| `2026-07-24 locked-OOS observation` | `archived` | 交叉事件 + LightGBM 质量筛选 | OOS 阈值以上事件近零；特征消融毛优势约 `+0.13 ATR`，不足覆盖成本 | [锁定 OOS](diagnostics/bin-15m-emax-lgbm-p5-locked-oos-reveal-2026-07-24.md) · [特征消融](diagnostics/bin-15m-emax-feature-ablation-2026-07-29.md) | 机制归档；不 promotion |

## Shared Assumptions

- 数据：point-in-time 动态币池闭合 `15m` K；`2026-01`–`2026-06` 已揭示。
- 成本：Binance fee `0.001/fill`、slippage `4 bps/fill`；资金费按报告口径。
- 执行：闭合 K 交叉，next-open 入场，固定 ATR bracket，最长 96 根。
- 仓位：组合单仓，事件按冻结分数排序。

## Evidence Map

- 规格：[研究契约](specs/bin-15m-emax-lgbm-research-contract-2026-07-23.md)
- 诊断：[P1 基线](diagnostics/bin-15m-emax-lgbm-p1-baseline-2026-07-24.md) · [P4 组合](diagnostics/bin-15m-emax-lgbm-p4-portfolio-2026-07-24.md) · [P5 裁决](diagnostics/bin-15m-emax-lgbm-p5-locked-oos-reveal-2026-07-24.md)
- 决策：[decision-log.md](decision-log.md)
- 脚本与产物：[scripts/README.md](scripts/README.md) · [artifacts/README.md](artifacts/README.md)
