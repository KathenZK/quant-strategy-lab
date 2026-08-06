# Binance-4H-EMA-Cross-LightGBM-Event-Selector Core Ledger

## Family Identity

- 完整家族名：`Binance-4H-EMA-Cross-LightGBM-Event-Selector`
- 别名：`BIN-4H-EMAX-LGBM`
- 市场：Binance USD-M USDT 永续、point-in-time 动态币池、`4h`
- 机制：EMA 交叉事件经 LightGBM 三分类筛选，以 ATR bracket 和超时规则交易。
- 边界：不继承 15m/1h/1d 证据；不同周期单独审计。

## Current State

- 当前版本：无登记版本；V3 是立项标签，因 gate 失败未登记。
- 当前状态：`explore / not promoted / not live-ready`。
- 结论：local+trend 事件级越过成本墙；V3 组合 MaxDD `-19.4%` 且评分有增值，但 83% 盈利集中 2022、四年仅两年为正。
- 下一门：V3 不登记；只有解决跨年集中度的 materially new mechanism 才可重开。

## Version Rules

- 周期独立；phase 标签不等同版本。
- 冻结模型、阈值、执行和证据后，用户明确登记才产生 `Vx`。

## Version Table

| Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| `V3 project observation` | `explore / not promoted / not live-ready` | local+trend 精简选择器组合 | MaxDD `-19.4%`；83% 盈利集中 2022；四年两年正 | [V3 判决](diagnostics/bin-4h-emax-v3-portfolio-2026-07-30.md) | gate 失败，不登记 |

## Shared Assumptions

- 数据：Binance USD-M 闭合 `4h` K 与 point-in-time 可交易币池。
- 成本：默认 fee `0.001/fill`、slippage `4 bps/fill`；funding 必须显式处理。
- 执行：闭合 K 信号、next-open 入场，ATR bracket/超时待合同冻结。
- 仓位：组合冲突和容量约束待明确。

## Evidence Map

- 规格：[V3 合同](specs/bin-4h-emax-v3-lean-selector-portfolio-contract-2026-07-30.md)
- 诊断：[V3 组合](diagnostics/bin-4h-emax-v3-portfolio-2026-07-30.md) · [local+trend](diagnostics/bin-4h-emax-local-trend-selector-2026-07-29.md) · [P1](diagnostics/bin-4h-emax-lgbm-p1-baseline-2026-07-24.md)
- 决策：[decision-log.md](decision-log.md)
- 脚本：[scripts/README.md](scripts/README.md)
- 产物：[artifacts/README.md](artifacts/README.md)
