# Binance-15M-Multi-Indicator-Intraday-Transfer

本目录记录 Binance USD-M Futures `BTCUSDT`、`ETHUSDT` 的 `15m` multi-indicator intraday 跨资产迁移诊断。当前目标不是创建可实盘策略，而是检验 `HYPE-15M-MII-V1.1` 的 RSI/MACD/ATR/RVOL/固定 TP-SL 机制，是否能通过受约束参数缩放适配 BTC/ETH 更小的波动结构。

## 当前状态

- Family：`Binance-15M-Multi-Indicator-Intraday-Transfer`
- 数据：Binance futures kline API 直接拉取，`2025-05-30T10:30:00+00:00` 到 `2026-06-26T04:00:00+00:00`。
- 成本：手续费 `0.1000%`/fill，滑点 `0.0400%`/fill，round-trip `0.2800%`；资金费未计入。
- 状态：`explore / not promoted / not live-ready`。

## 当前结论

- BTC 可以找到 K+1/K+2 同时为正的微调版本，但全样本收益很低：代表版 `btceth_mii_rsi9_35_60_long_atrmin35_rvol1_tp90_sl240_hold8_x1`，K+1 总收益 `2.99%`、K+2 总收益 `2.24%`，交易 `31` 笔。
- ETH 可以找到 K+1-only 赚钱版本：代表版 `btceth_mii_rsi9_40_60_short_atrmin45_rvol1_tp75_sl240_hold24_x1`，K+1 总收益 `6.63%`、胜率 `82.81%`；但 K+2 总收益 `-11.11%`，不通过延迟稳健性。
- 结论：参数微调确实比直接套 HYPE V1.1 更适配 BTC/ETH 波动，但目前没有出现可提升的 BTC/ETH 稳健版本。

## 阅读顺序

1. `diagnostics/binance-15m-mii-btc-eth-constrained-search-2026-06-30.md`
2. `decision-log.md`

## 证据规则

- 研究脚本放在 `scripts/`。
- 被诊断报告引用的 JSON/CSV 放在 `artifacts/`。
- 本目录不继承 HYPE 版本号；BTC/ETH 参数不得称为 `HYPE-15M-MII-V1.x`。
