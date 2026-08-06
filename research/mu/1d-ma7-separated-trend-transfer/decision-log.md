# Decision Log

## 2026-08-05 — Binance / Nasdaq 双市场零调参迁移

决定：将 `HYPE-1D-MA7-Asymmetric-Body-Trend-V1` 原参数分别迁移至 Binance `MUUSDT` perpetual 与 Nasdaq `MU` equity；Binance combined 全期 `-12.30%`，Nasdaq combined 虽为 `+51.51%` 但只触发多头、远逊于 buy-and-hold，且股票数据仍为 `raw_unaccepted`。因此只建立 `explore / untrusted equity arm / not promoted / not live-ready` 家族，不登记版本、不在已揭示 MU 历史上调参。证据：[双市场诊断](diagnostics/mu-1d-ma7-dual-market-transfer-2026-08-05.md) · [机器摘要](artifacts/mu_1d_ma7_dual_market_transfer_summary_2026-08-05.json)。

## 2026-08-05 — Binance 剔除周末

决定：完全删除周末 K 的 combined 为 `+20.09%`，但该口径忽略真实周末 stop/funding；保留周末风险、只允许工作日指标与主动信号的可执行口径为 `+18.31%`、MDD `-33.88%`。由于 `12h` 相位转为 `-25.76%`、仅 4 笔且 short-only 仍亏损，不登记该观察、不晋升、不继续搜索日界线。证据：[周末过滤诊断](diagnostics/mu-1d-ma7-binance-weekday-filter-2026-08-05.md)。
