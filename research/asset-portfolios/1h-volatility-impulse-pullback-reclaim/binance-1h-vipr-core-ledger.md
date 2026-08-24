# Binance-1H-Volatility-Impulse-Pullback-Reclaim Core Ledger

## Family Identity

- Full family name：`Binance-1H-Volatility-Impulse-Pullback-Reclaim`
- Alias：`BIN-1H-VIPR`
- Market / timeframe：Binance USD-M perpetual；原生闭合 `1h`
- Universe：`BTCUSDT / ETHUSDT / BNBUSDT / SOLUSDT / TRXUSDT`
- Mechanism：volatility-normalized Donchian impulse 建 root；严格后继 bar 完成 pullback 与 reclaim 后，下一小时 open 入场，固定 ATR stop/target/timeout。
- Collision warning：不继承 `BIN-1H-PIC`、`BIN-1H-MA7-RHT`、LMML、DAPML 或 HYPE ABT 的身份、参数和 promotion 证据。

## Current State

- Current version：无；P1 development 八配置已完成并 `HARD-GATE-FAILED`，holdout 未揭示。
- Status：`explore / not promoted / not live-ready`。
- Development：五资产只在 `2024-05-25 UTC` 前选择统一规则。
- Locked holdout：`[2024-06-01, 2025-05-20) UTC` roots；development 通过才允许一次性揭示。
- HYPE boundary：实际读取 HYPE rows/files 均为零；失败后不设 transfer。
- Runner：无 live spec、无 implementation、无 dry-run/live instance。
- Blocker：八配置 mean 均为负、PF `0.645–0.720`，全部资产和 `180d` block 均无正结果。
- Next gate：本家族不再推进；新机制必须引入与局部价格路径独立的信息源。

## Version Rules

- P0 数据、P1 rule-based development/holdout 与任何单资产 observation 均不构成正式版本。
- 登记版本必须冻结 root、pending state、entry、bracket、timeout、成本、参数和逐笔证据。
- 改变 timeframe、root 来源、reclaim 定义、bracket、timeout 或引入 ML / asset-specific 参数均是 materially new mechanism。

## Version Table

| Observation | Status | Role / Core Idea | Evidence | Decision |
| --- | --- | --- | --- | --- |
| P0/P1 | `explore / HARD-GATE-FAILED` | 原生 1h impulse → pullback → reclaim，统一规则与 locked holdout | [合同](specs/binance-1h-vipr-p0-p1-contract-2026-08-10.md) · [失败诊断](diagnostics/binance-1h-vipr-p1-development-2026-08-10.md) | 八配置 development 全失败；holdout 未揭示 |

## Shared Assumptions

- Data：direct Binance FAPI `1h` 与官方 funding/mark；缺 K、重复、非闭合或身份错误均 fail closed。
- Timing：信号只用闭合 bar；entry 在下一小时 open；bracket 从 entry bar 起生效，同 bar 双触发按 stop first。
- Cost：fee `0.001/fill`；主结果 `4bps/fill` adverse slippage，另报 `8/12bps` 与 actual funding。
- Sizing：固定 `0.25x` isolated research sleeve；无 pyramiding、无动态 sizing。

## Evidence Map

- [P0/P1 预冻结合同](specs/binance-1h-vipr-p0-p1-contract-2026-08-10.md)
- [P1 development 失败诊断](diagnostics/binance-1h-vipr-p1-development-2026-08-10.md)
- [前驱 RHT 失败诊断](../1h-ma7-root-hazard-timing/diagnostics/binance-1h-ma7-rht-p1-development-2026-08-10.md)
- [决策记录](decision-log.md)
- [产物索引](artifacts/README.md)
