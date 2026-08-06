# Binance-1D-Turtle-Breakout Core Ledger

## Family Identity

- 完整家族名：`Binance-1D-Turtle-Breakout`
- 别名：`BIN-1D-TURTLE`
- 市场：Binance USD-M `HYPEUSDT`、`BTCUSDT`、`ETHUSDT` 永续，`1d`
- 机制：20 日 Donchian 突破入场、10 日反向通道退出，对照固定 1x 与风险定仓。
- 边界：不是 TSMOM、EWMAC 或 MA7 单资产选择；Turtle 通道与组合规则保持独立。

## Current State

- 当前版本：无登记版本；仅有 20/10 baseline 观察。
- 当前状态：`explore / not promoted / not live-ready`。
- 结论：固定 1x 三标的均亏损；低暴露风险定仓只降低损失，未改善信号收益。
- 下一门：若继续，须先提出 materially new mechanism，并完成执行时序与硬门禁。

## Version Rules

- `20/10` 固定/动态仓位结果是候选观察，不是版本。
- 通道、头寸构造或退出逻辑改变才可形成新版本候选；登记须有冻结 spec。

## Version Table

| Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| `20/10 baseline observation` | `explore / not promoted / not live-ready` | 20 日突破、10 日退出 | 固定 1x：HYPE `-26.04%`、BTC `-26.40%`、ETH `-45.61%`；风险定仓仍为负 | [基线诊断](diagnostics/binance-1d-turtle-breakout-2026-06-27.md) | 不登记、不 promotion |

## Shared Assumptions

- 数据：三标的 Binance 永续闭合日线，`2025-06-27` 至 `2026-06-26`。
- 成本：fee `0.001/fill`、slippage `4 bps/fill`；资金费依报告。
- 执行：闭合日线产生信号，禁止同 K 收盘回填；细节待审计。
- 仓位：固定 1x 与前 10 日低点风险定仓对照；后者改善来自极低平均暴露。

## Evidence Map

- 诊断：[20/10 基线](diagnostics/binance-1d-turtle-breakout-2026-06-27.md)
- 决策：[decision-log.md](decision-log.md)
- 脚本与产物：[scripts/](scripts/) · [artifacts/](artifacts/)
