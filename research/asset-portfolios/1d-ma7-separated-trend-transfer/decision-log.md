# Decision Log

## 2026-08-05

决定：把 HYPE 第 `041` 组 MA7 多空分离参数零调参迁移至 BTC/ETH；组合在共同 `425d` 均亏损，ETH 完整窗口收益又对延迟和日界敏感，因此判定 direct transfer 失败。short-only 虽在 UTC 日界下两个资产均盈利，但 `12h` 相位同时翻负且样本低，只保留 diagnostic observation；不登记版本、不晋升、不继续在已揭示历史上调参。证据：[迁移诊断](diagnostics/binance-1d-ma7-separated-trend-transfer-2026-08-05.md) · [冻结合同](specs/binance-1d-ma7-separated-trend-transfer-contract-2026-08-05.md) · [机器摘要](artifacts/binance_1d_ma7_separated_trend_transfer_summary_2026-08-05.json)。

## 2026-08-05 — 分资产搜索隔离

决定：用户明确要求在 BTC/ETH 上重新搜索固定 MA7 参数；该工作建立为独立 `BIN-1D-MA7-AS-SEARCH` 家族，不修改本零调参迁移合同或失败结论。证据：[分资产搜索诊断](../1d-ma7-asset-specific-search/diagnostics/binance-btc-eth-1d-ma7-asset-specific-search-2026-08-05.md)。

## 2026-08-10 — HYPE V6 BTC/ETH零调参迁移失败

决定：按用户要求把 exact `HYPE-1D-MA7-ABT-V6` / `PEHC_294` 在 BTC/ETH 上回测；BTC full 小亏且共同窗口亏损，ETH full 虽正但共同窗口、最近一年、额外延迟和相位均否定稳定性。因此本轮只保留 `diagnostic-only`，不登记 BTC/ETH V6，不修改 HYPE V6，不推进 runner。证据：[V6迁移诊断](diagnostics/binance-1d-ma7-abt-v6-transfer-btc-eth-2026-08-10.md) · [机器摘要](artifacts/binance_1d_ma7_abt_v6_transfer_btc_eth_2026-08-10.json)。
