# US-Indexes-1D-MA7-Shared-Parameter-Transfer Core Ledger

## Family Identity

- Full family name：`US-Indexes-1D-MA7-Shared-Parameter-Transfer`
- Alias：`USI-1D-MA7-SP-XFER`
- Market / source / timeframe：Yahoo `^GSPC`、`^IXIC` price indexes，America/New_York session `1d`
- Mechanism：BTC/ETH 共享 `SMA7/ATR7` 多空参数的零调参跨市场迁移。
- Boundary：指数不可直接交易；不是 SPY、QQQ、期货、期权或 total-return series。

## Current State

- Current version：无；本次只产生 transfer observations。
- Current status：`explore / not promoted / not live-ready`。
- S&P 500：full combined `+18.77%`、MDD `-41.43%`、年化约 `0.53%`；`10 bps/fill=-48.26%`，buy-and-hold `+1,584.31%`。
- Nasdaq Composite：full combined `+91.43%`、MDD `-52.06%`、年化约 `2.03%`；`10 bps/fill=-12.38%`，buy-and-hold `+3,428.37%`。
- Legs：S&P / Nasdaq long-only 为 `+59.86%/+255.55%`，short-only 为 `-34.30%/-41.22%`。
- Recent：combined 最近一年 S&P `-11.89%`、Nasdaq `-7.25%`。
- Runner：无 live spec、无可交易 instrument、无 runner implementation。
- Blockers：无长期超额；成本后均失败；short 长期负 edge；指数不可交易；没有真实代理成本/借券/分红；只有日线、无完整 phase/intraday path。
- Next gate：不登记、不调参；如研究 SPY、QQQ 或期货，建立新的可交易 instrument family 和独立执行合同。

## Version Rules

- 本次迁移不产生 `V1`。
- 更改参数、MA/ATR、数据窗口、指数或成本模型均产生新 observation。
- 可交易 ETF、期货或期权属于新 family，不继承本指数证据。

## Version Table

| Observation | Status | Role / Core Idea | Key Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| Shared → S&P 500 | `explore / not promoted / not live-ready` | BTC/ETH shared 零调参应用于 `^GSPC` | full `+18.77%`，MDD `-41.43%`；`10 bps=-48.26%` | [诊断](diagnostics/us-indexes-1d-ma7-shared-parameter-transfer-2026-08-05.md) | 成本与超额失败 |
| Shared → Nasdaq Composite | `explore / not promoted / not live-ready` | BTC/ETH shared 零调参应用于 `^IXIC` | full `+91.43%`，MDD `-52.06%`；`10 bps=-12.38%` | [诊断](diagnostics/us-indexes-1d-ma7-shared-parameter-transfer-2026-08-05.md) | 比标普好但仍失败 |

## Shared Assumptions

- Data：Yahoo raw OHLC，两个指数共同 `1994-05-04` 至 `2026-08-04`、各 `8,117` sessions，质量 blocker 为 `0`。
- Cost：主结果零费用/滑点/借券/融资且不含分红；`10 bps/fill` 仅为示意。
- Execution：收盘信号次 session open；open gap 与日 high/low 触发 stop。
- Position：固定约 `1x`、单仓、非加仓；short 只是指数路径模拟。

## Evidence Map

- [迁移合同](specs/us-indexes-1d-ma7-shared-parameter-transfer-contract-2026-08-05.md)
- [诊断报告](diagnostics/us-indexes-1d-ma7-shared-parameter-transfer-2026-08-05.md)
- [机器摘要](artifacts/us_indexes_1d_ma7_shared_parameter_transfer_summary_2026-08-05.json)
- [复现脚本](scripts/audit_us_indexes_1d_ma7_shared_params.py)
- [决策记录](decision-log.md)
