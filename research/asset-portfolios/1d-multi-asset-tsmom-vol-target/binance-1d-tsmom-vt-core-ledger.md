# Binance-1D-Multi-Asset-TSMOM-Vol-Target Core Ledger

## Family Identity

- 完整家族名：`Binance-1D-Multi-Asset-TSMOM-Vol-Target`
- 别名：`BIN-1D-TSMOM-VT`
- 市场：Binance USD-M USDT 永续、point-in-time 动态币池、`1d`
- 机制：多 lookback 时间序列动量投票、EWMA 波动率缩放、组合波动目标。
- 边界：不是 EWMAC forecast、Turtle 突破或 15m TSM 状态机。

## Current State

- 当前版本：无登记版本；P0 为观察，P1 合同已冻结但尚未跑数。
- 当前状态：`explore / not promoted / not live-ready`。
- 结论：P0 毛收益 2021–2025 逐年为正、两腿互补且波动目标准确；每日全量再平衡成本与 funding 吃掉 2021 以外净利，4 条门禁过 2 条。
- 下一门：P1 只改再平衡缓冲带与频率，不改信号/仓位层；按冻结 kill gate 裁决。

## Version Rules

- P0/P1 是诊断阶段，不是版本。
- lookback 或波动缩放小改不应把失败机制包装为新 `Vx`。

## Version Table

| Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| `P0 demo observation` | `explore / not promoted / not live-ready` | 多周期 TSMOM + vol target | 毛收益逐年正；实现波动 `20.8%` vs 目标 `20%`；成本后仅 2021 净正 | [P0 诊断](diagnostics/bin-1d-tsmom-vt-p0-demo-2026-07-27.md) | 不登记；进入 P1 执行诊断 |

## Shared Assumptions

- 数据：point-in-time 动态币池闭合日线；窗口见合同。
- 成本：fee `0.001/fill`、slippage `4 bps/fill`，资金费按报告计入。
- 执行：闭合 K 计算、next-open 调仓，禁止未来 universe。
- 仓位：单资产波动缩放、组合目标波动率与杠杆 cap。

## Evidence Map

- 规格：[P0 演示合同](specs/bin-1d-tsmom-vt-demo-contract-2026-07-27.md) · [P1 执行合同](specs/bin-1d-tsmom-vt-p1-rebalance-execution-contract-2026-08-05.md)
- 诊断：[P0 demo](diagnostics/bin-1d-tsmom-vt-p0-demo-2026-07-27.md)
- 决策：[decision-log.md](decision-log.md)
- 脚本与产物：[scripts/README.md](scripts/README.md) · [artifacts/README.md](artifacts/README.md)
