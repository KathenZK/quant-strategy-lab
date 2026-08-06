# MU-1D-MA7-Separated-Trend-Transfer

- Full family name：`MU-1D-MA7-Separated-Trend-Transfer`
- Alias：`MU-1D-MA7-ST-XFER`
- Market：Binance USD-M `MUUSDT` `TRADIFI_PERPETUAL` 与 Nasdaq `MU` equity
- Timeframe：UTC 日 K / 美国 regular-session 日 K
- Mechanism：`HYPE-1D-MA7-Asymmetric-Body-Trend-V1` 的固定 SMA7 多空分离状态机零调参迁移
- Status：`explore / untrusted equity arm / not promoted / not live-ready`

两个 route 是同一底层公司的不同交易合同：Binance route 含真实 funding 与 24/7 日界线，Nasdaq route 是 Yahoo 来源的股票 regular-session raw 日线。指标不可跨 route 混用，结果也不是同一执行合同的重复测量。

## 入口

- [主账](mu-1d-ma7-st-xfer-core-ledger.md)
- [决策记录](decision-log.md)
- [零调参迁移合同](specs/mu-1d-ma7-v1-dual-market-transfer-contract-2026-08-05.md)
- [双市场诊断](diagnostics/mu-1d-ma7-dual-market-transfer-2026-08-05.md)
- [Binance 剔除周末诊断](diagnostics/mu-1d-ma7-binance-weekday-filter-2026-08-05.md)
- [产物说明](artifacts/README.md)
- [复现脚本](scripts/research_mu_1d_ma7_dual_market_transfer.py)
