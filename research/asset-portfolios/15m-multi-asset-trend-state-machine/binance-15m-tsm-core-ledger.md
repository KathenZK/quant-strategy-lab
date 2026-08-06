# Binance-15M-Multi-Asset-Trend-State-Machine Core Ledger

## Family Identity

- 完整家族名：`Binance-15M-Multi-Asset-Trend-State-Machine`
- 别名：`BIN-15M-TSM`
- 市场：Binance USD-M USDT 永续、point-in-time ADV30 前 120 币池、`15m`
- 机制：每根闭合 K 重估 `LONG/FLAT/SHORT`，以 EMA spread/ATR 迟滞确认驱动换仓和两层波动率目标。
- 边界：不是 EMAX-LGBM 事件策略、1D TSMOM 或单资产 EMA-TB。

## Current State

- 当前版本：无登记版本；仅保留 P1/P2/locked-OOS 观察。
- 当前状态：`archived`。
- 结论：P1/P2 通过后，锁定 OOS 段级 PF `1.162 < 1.2`，按合同判 `HARD-GATE-FAILED`。
- 下一门：已揭示 `2026H1` 不得复用；重开须 materially new mechanism。

## Version Rules

- P0/P1/P2 是诊断阶段，不是 `Vx`。
- 修约后的 EMA336/1536 核只是一条观察，不因样本内通过而自动登记。

## Version Table

| Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| `P2 locked-OOS observation` | `archived` | 4h 等效 EMA336/1536 三态核 + 组合波动目标 | P2 净 `+111.3%`、MaxDD `-28.3%`；locked OOS PF `1.162` | [P2 基线](diagnostics/bin-15m-tsm-p2-portfolio-baseline-2026-07-28.md) · [OOS 揭示](diagnostics/bin-15m-tsm-locked-oos-reveal-2026-07-28.md) | 门禁失败并归档 |

## Shared Assumptions

- 数据：闭合 `15m` K、point-in-time 币池；已揭示窗口永久污染。
- 成本：Binance fee `0.001/fill`、slippage `4 bps/fill`，资金费按合同计入。
- 执行：状态在闭合 K 更新，下一根 open 换仓，4 根确认。
- 仓位：单资产与组合两层波动率目标。

## Evidence Map

- 规格：[冻结研究契约](specs/bin-15m-tsm-research-contract-2026-07-28.md)
- 诊断：[P1 段基线](diagnostics/bin-15m-tsm-p1-segment-baseline-2026-07-28.md) · [P2 组合](diagnostics/bin-15m-tsm-p2-portfolio-baseline-2026-07-28.md) · [锁定 OOS](diagnostics/bin-15m-tsm-locked-oos-reveal-2026-07-28.md)
- 决策：[decision-log.md](decision-log.md)
- 脚本与产物：[scripts/README.md](scripts/README.md) · [artifacts/README.md](artifacts/README.md)
