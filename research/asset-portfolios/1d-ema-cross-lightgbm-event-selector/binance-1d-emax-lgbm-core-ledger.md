# Binance-1D-EMA-Cross-LightGBM-Event-Selector Core Ledger

## Family Identity

- 完整家族名：`Binance-1D-EMA-Cross-LightGBM-Event-Selector`
- 别名：`BIN-1D-EMAX-LGBM`
- 市场：Binance USD-M USDT 永续、point-in-time 动态币池、`1d`
- 机制：EMA 交叉事件经 LightGBM 三分类筛选，以 ATR bracket 和超时规则交易。
- 边界：与 15m/1h/4h 同机制目录互不继承版本或证据。

## Current State

- 当前版本：无登记版本；P1/P2 均为诊断观察。
- 当前状态：`archived`。
- 结论：空头事件毛优势真实，但集中在成簇崩盘波；预注册组合容量逆向选择，P2 kill gate 失败。
- 下一门：EMA 交叉机制四周期已关账；仅 materially new mechanism 可重开。

## Version Rules

- 周期独立；不得引用其他 timeframe 的版本号。
- 只有冻结参数与可复现证据后，用户明确登记才产生 `Vx`。

## Version Table

| Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| `P1/P2 observation` | `archived` | 1d EMA 交叉 + 事件评分 + 组合控制 | 空头净 `+0.733 ATR`、逐年全正；2022 利润占比 `383%`，组合 gate 失败 | [P1](diagnostics/bin-1d-emax-lgbm-p1-baseline-2026-07-24.md) · [P2](diagnostics/bin-1d-emax-lgbm-p2-portfolio-control-a-2026-07-27.md) | 家族归档 |

## Shared Assumptions

- 数据：Binance USD-M 日线和 point-in-time 可交易币池；窗口见 P1/P2。
- 成本：默认 fee `0.001/fill`、slippage `4 bps/fill`；funding 需显式处理。
- 执行：闭合日线信号、next-open 入场；不得使用未来币池或日内信息。
- 仓位：组合单仓或并发约束待研究合同明确。

## Evidence Map

- 规格：[组合合同](specs/bin-1d-emax-portfolio-contract-2026-07-27.md)
- 诊断：[P1 基线](diagnostics/bin-1d-emax-lgbm-p1-baseline-2026-07-24.md) · [P2 组合](diagnostics/bin-1d-emax-lgbm-p2-portfolio-control-a-2026-07-27.md)
- 决策：[decision-log.md](decision-log.md)
- 脚本：[scripts/README.md](scripts/README.md)
- 产物：[artifacts/README.md](artifacts/README.md)
