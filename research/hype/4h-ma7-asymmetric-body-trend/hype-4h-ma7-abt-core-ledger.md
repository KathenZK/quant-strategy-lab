# HYPE-4H-MA7-Asymmetric-Body-Trend Core Ledger

## Family Identity

- Full family name：`HYPE-4H-MA7-Asymmetric-Body-Trend`
- Alias：`HYPE-4H-MA7-ABT`
- Market / exchange / symbol / timeframe：Binance USD-M Futures，`HYPEUSDT` perpetual，UTC `4h`
- Mechanism：固定 `SMA7/ATR7` 的多空独立 reclaim、斜率确认、迟滞退出与 ATR 保护状态机。
- Boundary：来自日线 V1 的 direct transfer，但属于独立 4H 家族；不是源 V1 的升级，也不是 4H-BKSB 或 6H-RS4。

## Current State

- Current version：无 registered version。
- Current status：`explore / not promoted / not live-ready`。
- Bar-transfer：combined `-67.72%`、MDD `-77.47%`、105 笔。
- Clock-equivalent：combined `-2.61%`、MDD `-34.21%`、63 笔；long-only / short-only `+17.07% / -23.54%`。
- Robustness：clock-equivalent `8 bps=-7.41%`、额外延迟一根 `4h=-28.18%`、`2h` 相位 `-25.09%`；12 个滚动 90 日窗口仅 `5` 个为正。
- Baseline：同期计成本和 funding 的 `1x` buy-and-hold `+50.58%`。
- Runner：无 live spec、无 quant-runner implementation、无 dry-run/live instance。
- Blockers：全期绝对与超额收益失败；short-only 在两种时间合同和全部 12 个 clock rolling windows 均失败；long-only 相位翻负；多头首持仓 bar 无 hard stop；无 OOS/CPCV 或 runner parity。
- Next gate：停止迁移日线参数；若继续，须建立独立 4H 机制和预先冻结的 OOS 合同。当前不登记、不推进 runner。

## Version Rules

- 当前两个合同只是 official observations，不是 `V1/V2`。
- 登记首个版本必须冻结唯一的 4H 时间合同、完整多空规则、成本、相位、保护和 OOS 证据。
- MA 长度、bar 对齐、时间参数、单边删除或保护变化均是身份级变化。

## Version Table

| Observation | Status | Role / Core Idea | Key Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| Bar-transfer | `explore / not promoted / not live-ready` | 日线数字直接解释为 4H bar | `-67.72%`，MDD `-77.47%` | [迁移诊断](diagnostics/hype-4h-ma7-source-v1-transfer-2026-08-05.md) | 失败，不登记 |
| Clock-equivalent | `explore / not promoted / not live-ready` | 仅将 max-hold/cooldown 乘 `6` | `-2.61%`，MDD `-34.21%`；`2h=-25.09%` | [迁移诊断](diagnostics/hype-4h-ma7-source-v1-transfer-2026-08-05.md) | 无绝对/超额与相位稳定性，不登记 |

## Shared Assumptions

- Data：标准 Binance `HYPEUSDT` perpetual `1h` 数据湖聚合完整 4H；每 bar 恰有四根连续闭合 `1h`，质量 blocker 为 `0`。
- Indicator：`SMA7` 与 `ATR7` 均基于 4H bar。
- Cost：手续费 `0.001/fill`、不利滑点 `4 bps/fill`、真实事件时间 funding；另审计 `8 bps/fill`。
- Execution：闭合 4H 信号最早下一 4H open 成交；intrabar stop 使用真实 `1h` 顺序；固定约 `1x`、非加仓。
- Evidence role：全部历史已揭示，仅为 diagnostic evidence。

## Evidence Map

- [迁移合同](specs/hype-4h-ma7-source-v1-transfer-contract-2026-08-05.md)
- [迁移诊断](diagnostics/hype-4h-ma7-source-v1-transfer-2026-08-05.md)
- [机器摘要](artifacts/hype_4h_ma7_v1_transfer_summary_2026-08-05.json)
- [复现脚本](scripts/research_hype_4h_ma7_v1_transfer.py)
- [产物说明](artifacts/README.md)
- [决策记录](decision-log.md)
- [源日线 V1 主账](../1d-ma7-asymmetric-body-trend/hype-1d-ma7-abt-core-ledger.md)
