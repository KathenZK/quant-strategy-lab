# SOX-1D-MA7-Separated-Trend-Transfer Core Ledger

## Family Identity

- Full family name：`SOX-1D-MA7-Separated-Trend-Transfer`
- Alias：`SOX-1D-MA7-ST-XFER`
- Market / source / timeframe：Yahoo Finance `^SOX` PHLX Semiconductor price index，America/New_York session `1d`
- Mechanism：`HYPE-1D-MA7-Asymmetric-Body-Trend-V1` 的固定 SMA7 多空分离参数零调参跨市场迁移。
- Boundary：指数不可直接交易；不是 SOXX ETF、期货或期权，不继承任何 live-readiness。

## Current State

- Current version：无；SOX 迁移线未登记版本。
- Current status：`explore / not promoted / not live-ready`。
- Full result：`1994-05-04` 至 `2026-08-04` 零成本 combined `-36.29%`、MDD `-76.58%`、365 笔；buy-and-hold `+9,725.06%`。
- SMA5 substitution：保持 ATR7 和 V1 状态机不变时 combined `-11.73%`、MDD `-74.45%`；long-only `+498.76%`，short-only `-83.55%`；仍无长期绝对或超额收益。
- Overlap result：HYPE 日历重叠窗口 combined `+5.98%`，但 buy-and-hold `+132.77%`，额外延迟一 session 后 `-4.85%`。
- Stability：33 个逐年窗口仅 17 个为正；30 个滚动三年窗口仅 13 个为正，中位收益 `-4.92%`。
- Runner：无 live spec、无可交易 instrument、无 runner implementation。
- Blockers：长期绝对与超额收益失败；指数不可直接交易；成本/借券未指定；只有日线、无完整 phase/intraday path；V1 长仓首日无 hard stop；无 prospective OOS 或线上对账。
- Next gate：本 direct-transfer 家族保持冻结；用户后续要求的 SOX 专属 MA7 搜索已在独立的 [`SOX-1D-MA7-Asset-Specific-Search`](../1d-ma7-asset-specific-search/README.md) 家族记录。如研究 SOXX 或指定衍生品，仍须新建可交易家族并重新定义数据与执行合同。

## Version Rules

- 当前只是来源 V1 的 transfer diagnostic，不产生 `SOX-...-V1`。
- SOXX、期货、期权或其他代理是新的 instrument family；不得把指数指标静默迁移为可执行版本。
- 任何参数调整、成本设定或日内数据替换均产生新观察合同，不回写当前零调参结果。

## Version Table

| Observation | Status | Role / Core Idea | Key Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| SMA7 direct transfer | `explore / not promoted / not live-ready` | HYPE V1 原参数零调参迁移 | `-36.29%`，MDD `-76.58%` | [全历史诊断](diagnostics/sox-1d-ma7-v1-transfer-2026-08-05.md) | 长期绝对与超额失败 |
| SMA5 substitution | `explore / not promoted / not live-ready` | 只把 SMA7 改为 SMA5，ATR7 与状态机不变 | `-11.73%`，MDD `-74.45%`；`10 bps=-61.81%` | [SMA5 诊断](diagnostics/sox-1d-sma5-substitution-2026-08-05.md) | 有改善但仍失败，不登记 |

## Shared Assumptions

- Data：Yahoo `^SOX` raw OHLC，`8,117` sessions，数据质量 blocker 为 `0`。
- Cost：主结果零费用/滑点/借券/融资；`10 bps/fill` 仅为示意敏感性。
- Execution：收盘信号次 session open；日 open gap 与日 high/low 触发 stop；无 session 内先后顺序。
- Position：固定约 `1x`、单仓、非加仓；short 只是指数价格路径模拟。
- Evidence role：全部 SOX 历史已揭示，只是 cross-market diagnostic。

## Evidence Map

- [迁移合同](specs/sox-1d-ma7-v1-transfer-contract-2026-08-05.md)
- [全历史诊断](diagnostics/sox-1d-ma7-v1-transfer-2026-08-05.md)
- [SMA5 零调参替换诊断](diagnostics/sox-1d-sma5-substitution-2026-08-05.md)
- [后续 SOX 专属搜索](../1d-ma7-asset-specific-search/diagnostics/sox-1d-ma7-asset-specific-search-2026-08-05.md)
- [机器摘要](artifacts/sox_1d_ma7_v1_transfer_summary_2026-08-05.json)
- [复现脚本](scripts/research_sox_1d_ma7_v1_transfer.py)
- [决策记录](decision-log.md)
