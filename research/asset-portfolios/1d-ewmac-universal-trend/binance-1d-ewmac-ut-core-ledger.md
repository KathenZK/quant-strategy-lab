# Binance-1D-EWMAC-Universal-Trend Core Ledger

## Family Identity

- 完整家族名：`Binance-1D-EWMAC-Universal-Trend`
- 别名：`BIN-1D-EWMAC-UT`
- 市场：Binance USD-M USDT 永续、point-in-time 动态币池、`1d`
- 机制：多快慢 EWMAC forecast，长期波动率缩放与 top-N 风险预算组合。
- 边界：不是 MA7 asset-specific search、TSMOM 或 Turtle；这是 universal-rule 组合。

## Current State

- 当前版本：无登记版本；仅有 universal-rule 诊断观察。
- 当前状态：`explore / not promoted / not live-ready`。
- 结论：9 标的中 8 个净收益为正，换手与单资产 Sharpe 符合文献量级；但预注册 universal gate 仅 QQQ/SPY 全过，通用主张失败。
- 下一门：若继续，只能另立组合级聚合契约；不得把当前观察登记为版本。

## Version Rules

- 合同/诊断批次不是版本号。
- 只有机制、参数、成本与证据被冻结并由用户明确登记，才创建 `Vx`。

## Version Table

| Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| `universal-rule observation` | `explore / not promoted / not live-ready` | 多速 EWMAC universal trend | 9 标的 8 个净正；Sharpe `0.25–0.49`；仅 QQQ/SPY 全过门禁 | [诊断](diagnostics/xa-1d-ewmac-ut-universal-trend-2026-08-05.md) | 通用主张失败；可另立组合研究 |

## Shared Assumptions

- 数据：point-in-time 动态币池闭合日线；窗口见合同。
- 成本：fee `0.001/fill`、slippage `4 bps/fill`，含 funding。
- 执行：闭合 K forecast、下一日开盘调仓，无 protective stop。
- 仓位：top-N、单资产风险预算和组合 cap。

## Evidence Map

- 规格：[universal trend 合同](specs/xa-1d-ewmac-ut-universal-trend-contract-2026-08-05.md)
- 诊断：[universal trend 诊断](diagnostics/xa-1d-ewmac-ut-universal-trend-2026-08-05.md)
- 决策：[decision-log.md](decision-log.md)
- 脚本与产物：[scripts/](scripts/) · [artifacts/README.md](artifacts/README.md)
