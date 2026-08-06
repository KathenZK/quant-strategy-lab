# Binance-1D-MA7-Separated-Trend-Transfer Core Ledger

## Family Identity

- Full family name：`Binance-1D-MA7-Separated-Trend-Transfer`
- Alias：`BIN-1D-MA7-ST-XFER`
- Market / symbols / timeframe：Binance USD-M `BTCUSDT`、`ETHUSDT` perpetual，UTC `1d`
- Mechanism：HYPE 第 `041` 组固定 `SMA7` 多空独立 reclaim、迟滞退出与 ATR 保护参数的零调参跨资产迁移。
- Boundary：不是无订单的 `BIN-1D-MA7DC`，也不是 MA7/MA30 加仓迁移；目标资产历史不用于再搜索。

## Current State

- Current version：无；用户未要求登记版本。
- Current status：`explore / not promoted / not live-ready`。
- Combined transfer：BTC 完整/共同窗口 `-0.68% / -12.09%`；ETH `+40.73% / -15.34%`，ETH MDD `-49.13%` 且额外延迟一天转为 `-15.10%`。
- Component observation：short-only 的 BTC/ETH 完整窗口为 `+14.70% / +32.93%`，共同窗口为 `+24.16% / +21.91%`；但 `12h` 相位分别转为 `-6.51% / -16.28%`。
- Runner：无 live spec、无 quant-runner implementation、无 dry-run/live instance。
- Blockers：组合共同窗口亏损；long-only 失败；short-only 相位符号翻转且仅 `17/15` 笔；长仓首日无 hard stop；无 clean prospective OOS、runner parity 或线上对账。
- Next gate：本零调参家族不在已揭示 BTC/ETH 历史上改参；用户后续明确要求的分资产搜索已隔离到 [`BIN-1D-MA7-AS-SEARCH`](../1d-ma7-asset-specific-search/README.md)，不能回写本迁移结论。

## Version Rules

- 本家族的版本身份必须同时固定资产集合、日界、完整多空规则、成本、funding 和成交时序。
- 改为 short-only、修改 MA/ATR 长度、保护参数或资产集合均是 materially new branch，不能继承当前 combined-transfer 指标。
- “登记/冻结 Vx”只固定身份，默认 `registered`，不自动晋升。

## Version Table

当前无 registered version。

## Shared Assumptions

- Data：标准数据湖 `1h` closed candles 聚合完整日 K；`2024-07-31` 至 `2026-07-30 UTC`，数据质量 blocker 为 `0`。
- Cost：手续费 `0.001/fill`、基准滑点 `4 bps/fill`、实际 funding timestamp/rate；压力滑点 `8 bps/fill`。
- Execution：收盘信号次日 open；stop 用 `1h` 路径且跳空穿越按小时 open；固定约 `1x`、单仓、非加仓。
- Evidence role：目标资产零调参 direct transfer，但 BTC/ETH 历史已被研究者查看，不是 clean prospective OOS。

## Evidence Map

- [冻结迁移合同](specs/binance-1d-ma7-separated-trend-transfer-contract-2026-08-05.md)
- [BTC/ETH 迁移诊断](diagnostics/binance-1d-ma7-separated-trend-transfer-2026-08-05.md)
- [后续分资产搜索诊断（独立家族）](../1d-ma7-asset-specific-search/diagnostics/binance-btc-eth-1d-ma7-asset-specific-search-2026-08-05.md)
- [机器摘要](artifacts/binance_1d_ma7_separated_trend_transfer_summary_2026-08-05.json)
- [研究脚本](scripts/research_binance_1d_ma7_separated_trend_transfer.py)
- [决策记录](decision-log.md)
