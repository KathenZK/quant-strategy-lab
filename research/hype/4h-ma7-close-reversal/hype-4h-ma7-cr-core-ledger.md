# HYPE-4H-MA7-Close-Reversal Core Ledger

## Family Identity

- Full name：`HYPE-4H-MA7-Close-Reversal`
- Alias：`HYPE-4H-MA7-CR`
- Market：Binance USD-M `HYPEUSDT` perpetual
- Timeframe：UTC `4h`
- Mechanism：闭合 `4h` 的 `close` 相对 `SMA7` 决定下一期开盘的 `+1x/-1x` 目标；跨线时直接反手。
- Collision：不是 `HYPE-4H-MA7-Asymmetric-Body-Trend`，不含 reclaim 等待、斜率过滤、ATR buffer、stop 或 cooldown。

## Current State

- Current version：无。
- Status：`explore / not promoted / not live-ready`。
- Runner：无 live spec、无 quant-runner implementation、无 dry-run/live instance。
- Baseline：全期 base `-90.01%`、MDD `-91.66%`、PF `0.65`；gross 无交易成本仍 `-52.34%`；最后 `120d` base `-17.05%`。
- Robustness：`8 bps=-93.61%`、额外延迟一根 `4h=-66.20%`；四个整点相位全部亏损；12 个滚动 90 日窗口仅 2 个为正。
- Live-readiness blocker：绝对与超额收益失败；无 hard stop 或交易所驻留保护；全历史已揭示，无 prospective OOS。
- Next gate：本零参数基准停止；任何 buffer、确认、flat zone 或最短持仓须另立预冻结机制。当前不登记。

## Version Rules

- `Vx` 只在用户明确要求登记时创建。
- 改 MA 长度、增加 buffer/确认、允许空仓、stop、cooldown 或非收盘触发均是新机制观察，不属于本零参数基准。
- 相位、近期或成本结果是审计，不构成版本。

## Version Table

| Observation | Status | Role | Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| Close-reversal baseline | `explore / not promoted / not live-ready` | 零参数始终持仓 MA7 反手基准 | Base `-90.01%`；gross `-52.34%`；556 次反手 | [基准诊断](diagnostics/hype-4h-ma7-close-reversal-baseline-2026-08-06.md) | 机制失败，不登记 |

## Shared Assumptions

- `SMA7` 基于七根完整 `4h` 收盘。
- 信号在收盘确认，下一根 `4h` open 成交；约 `1x`、非加仓。
- Binance fee `0.001/fill`、slippage `4 bps/fill`、实际 funding；反手按两次 fill。

## Evidence Map

- [家族入口](README.md)
- [冻结合同](specs/hype-4h-ma7-close-reversal-contract-2026-08-06.md)
- [基准诊断](diagnostics/hype-4h-ma7-close-reversal-baseline-2026-08-06.md)
- [机器摘要](artifacts/hype_4h_ma7_close_reversal_summary_2026-08-06.json)
- [复现脚本](scripts/research_hype_4h_ma7_close_reversal.py)
- [决策记录](decision-log.md)
- [机器证据](artifacts/README.md)
