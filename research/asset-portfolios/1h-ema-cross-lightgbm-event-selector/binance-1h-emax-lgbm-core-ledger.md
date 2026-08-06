# Binance-1H-EMA-Cross-LightGBM-Event-Selector Core Ledger

## Family Identity

- 完整家族名：`Binance-1H-EMA-Cross-LightGBM-Event-Selector`
- 别名：`BIN-1H-EMAX-LGBM`
- 市场：Binance USD-M USDT 永续、point-in-time 动态币池、`1h`
- 机制：EMA 交叉事件经 LightGBM 三分类打分，以 ATR bracket 和超时规则交易。
- 边界：不继承 15m/4h/1d 版本；与 AR-MAE 无关。

## Current State

- 当前版本：无登记版本；P1、复用窗口与 local+trend 均为诊断观察。
- 当前状态：`archived`。
- 结论：成本减半、空头残差存在但逼空月脆弱；1d 终局失败后 EMA 交叉四周期整体关账。
- 下一门：仅 materially new mechanism 可重开；复用窗口不构成干净 OOS。

## Version Rules

- phase 观察不构成 `Vx`。
- 模型特征、标签、阈值、执行和成本全部冻结后，才可由用户登记版本。

## Version Table

| Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| `P1/local+trend observation` | `archived` | 1h EMA 交叉 + 事件筛选 | 空头残差存在但逼空月脆弱；无可 promotion 组合 | [P1](diagnostics/bin-1h-emax-lgbm-p1-baseline-2026-07-24.md) · [local+trend](diagnostics/bin-1h-emax-local-trend-selector-2026-07-29.md) | 归档 |

## Shared Assumptions

- 数据：point-in-time universe、闭合 `1h` K；`2026H1` 锁定 OOS。
- 成本：fee `0.001/fill`、slippage `4 bps/fill`；funding 需计入。
- 执行：闭合 K 交叉、next-open 入场、固定 ATR bracket 和超时。
- 仓位：组合单仓，候选按冻结分数排序。

## Evidence Map

- 规格：[local+trend 合同](specs/bin-1h-emax-local-trend-selector-contract-2026-07-29.md)
- 诊断：[P1](diagnostics/bin-1h-emax-lgbm-p1-baseline-2026-07-24.md) · [复用窗口审计](diagnostics/bin-1h-emax-lgbm-2026h1-reused-audit-2026-07-24.md) · [local+trend](diagnostics/bin-1h-emax-local-trend-selector-2026-07-29.md)
- 决策：[decision-log.md](decision-log.md)
- 脚本与产物：[scripts/README.md](scripts/README.md) · [artifacts/README.md](artifacts/README.md)
