# HYPE-1H-Multi-Mechanism-Trend-Following Core Ledger

## Family Identity

- Full name：`HYPE-1H-Multi-Mechanism-Trend-Following`
- Alias：`HYPE-1H-MMTF`
- Market：Binance USD-M Futures `HYPEUSDT` perpetual `1h`
- Boundary：独立纯趋势家族；不继承 `HYPE-1H-Adaptive-Regime` 或其他 HYPE 家族的版本、参数与结论。

## Current State

- 当前状态：`explore / not promoted / not live-ready`。
- 当前版本：尚未登记；原始搜索完成并冻结后才登记 `V1`。
- 下一决策门：冻结原始基线、完成有效路径消融与 clean-surface 调优，再一次性揭示 locked OOS。

## Version Rules

- `V1` 固定原始可执行基线身份，登记不等于 promotion。
- path-equal 清洁化版本可登记为 `V2 clean-equivalent`；成交路径发生变化时必须作为新的诊断版本并说明差异。
- 未完成 locked OOS、压力与 live-executable 门禁的版本保持 `not promoted / not live-ready`。

## Version Table

| Version | Status | Role | Evidence | Decision |
| --- | --- | --- | --- | --- |
| - | explore | 原始多机制搜索进行中 | [数据冻结](diagnostics/hype-1h-mmtf-data-freeze-2026-07-22.md) | 尚无登记版本 |

## Shared Assumptions

- 闭合 `1h` K 信号，最早下一根 open 成交；单净仓；总杠杆不超过 `3x`。
- fee `0.001/fill`、base slippage `4 bps/fill`、逐时段真实 funding；stop-first、gap-open 保守成交。
- 最终硬门槛：完整样本与 locked OOS 同时达到 annual equity factor `>=20x`、win rate `>=80%`、MDD `<20%`，且交易数分别至少 `60/15`。

## Evidence Map

- [数据冻结与质量报告](diagnostics/hype-1h-mmtf-data-freeze-2026-07-22.md)
- [决策记录](decision-log.md)
