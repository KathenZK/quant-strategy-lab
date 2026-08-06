# MU-1D-MA7-Separated-Trend-Transfer Core Ledger

## Family Identity

- Full family name：`MU-1D-MA7-Separated-Trend-Transfer`
- Alias：`MU-1D-MA7-ST-XFER`
- Market / symbol / timeframe：Binance USD-M `MUUSDT` `TRADIFI_PERPETUAL` UTC `1d`；Nasdaq `MU` equity regular-session `1d`
- Mechanism：`HYPE-1D-MA7-Asymmetric-Body-Trend-V1` 固定 SMA7、ATR7、多空独立 reclaim、迟滞与 ATR 保护的零调参迁移。
- Boundary：两个 route 的日界线、成本、funding、session 与可交易合同不同；不得把它们当成同一 K 线源。

## Current State

- Current version：无；本家族未登记 MU 版本。
- Current status：`explore / untrusted equity arm / not promoted / not live-ready`。
- Binance result：`2026-04-08` 至 `2026-07-20 UTC` combined `-12.30%`、MDD `-40.16%`、4 笔；long-only `+25.29%`，short-only `-15.82%`，buy-and-hold `+99.35%`。
- Binance weekday observation：仅工作日生成指标与主动信号、但保留周末 stop/funding 时，`0h` combined `+18.31%`、MDD `-33.88%`；`12h` 相位为 `-25.76%`，不登记。
- Nasdaq result：`2025-06-16` 至 `2026-06-16` 零成本 combined / long-only `+51.51%`、MDD `-14.49%`、6 笔；short-only 无信号，buy-and-hold `+833.45%`。
- Common overlap：`2026-04-08` 至 `2026-06-16`，Binance / Nasdaq combined 分别 `+15.44% / +47.36%`，但各自 buy-and-hold 为 `+158.15% / +164.90%`。
- Runner：无 live spec、无 quant-runner implementation、无 dry-run/live instance。
- Blockers：两 route 均无超额；样本分别只有 `103d/365d` 与 `4/6` 笔；Binance short-only 亏损，weekday 观察在 `0h/12h` 间由 `+18.31%` 翻为 `-25.76%`；Nasdaq 只触发多头且数据为 `raw_unaccepted`；股票成本、借券、分红与融资未冻结；Nasdaq 无日内 path/phase；来源 V1 长仓首日无 hard stop。
- Next gate：不基于已揭示 MU 历史调参；先完成 Nasdaq equity 数据接受与更长历史，再决定是否建立 long-only 新机制，当前不登记、不推进 runner。

## Version Rules

- 当前只是来源 V1 的 direct-transfer observation，不产生 `MU-...-V1`。
- 取消空头、改变日界线、SMA/ATR 参数、成本或保护规则均是新观察合同；不得回写本次零调参结果。
- Binance perpetual 与 Nasdaq equity 若后续进入版本研究，必须分别冻结 execution contract 和证据。

## Version Table

| Observation | Status | Role / Core Idea | Key Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| Binance direct transfer | `explore / not promoted / not live-ready` | V1 原参数 + Binance 成本与实际 funding | `-12.30%`，MDD `-40.16%`；long-only `+25.29%` | [双市场诊断](diagnostics/mu-1d-ma7-dual-market-transfer-2026-08-05.md) | 组合、空头和超额失败 |
| Binance weekday observation | `explore / not promoted / not live-ready` | 工作日指标/主动信号，周末保留 stop 与 funding | `0h +18.31%`，MDD `-33.88%`；`12h -25.76%` | [周末过滤诊断](diagnostics/mu-1d-ma7-binance-weekday-filter-2026-08-05.md) | 相位翻负、4 笔，不登记 |
| Nasdaq direct transfer | `explore / untrusted / not promoted / not live-ready` | V1 原参数 + regular-session raw 日线 | `+51.51%`，MDD `-14.49%`；6 笔且全为多头 | [双市场诊断](diagnostics/mu-1d-ma7-dual-market-transfer-2026-08-05.md) | 正绝对收益但无超额，数据未接受 |

## Shared Assumptions

- Indicator / position：固定 V1 `SMA7/ATR7` 与多空参数；约 `1x`、单仓、非加仓。
- Binance：15m accepted raw/normalized 聚合 `1h` 后组成完整 UTC 日 K；手续费 `0.001/fill`、滑点 `4 bps/fill`、实际 funding。
- Nasdaq：Yahoo 来源 raw OHLC；主结果零成本，另审计 `10 bps/fill`；借券、分红与融资未建模。
- Evidence role：MU 历史已揭示，只是 cross-market diagnostic，不是 clean prospective OOS。

## Evidence Map

- [零调参迁移合同](specs/mu-1d-ma7-v1-dual-market-transfer-contract-2026-08-05.md)
- [双市场诊断](diagnostics/mu-1d-ma7-dual-market-transfer-2026-08-05.md)
- [Binance 剔除周末诊断](diagnostics/mu-1d-ma7-binance-weekday-filter-2026-08-05.md)
- [机器摘要](artifacts/mu_1d_ma7_dual_market_transfer_summary_2026-08-05.json)
- [复现脚本](scripts/research_mu_1d_ma7_dual_market_transfer.py)
- [决策记录](decision-log.md)
