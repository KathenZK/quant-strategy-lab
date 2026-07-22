# BTC-30M-Trend-Continuation

- Alias：`BTC-30M-TC`
- 市场：Binance USD-M Futures `BTCUSDT` perpetual
- 周期：原生 `30m`；另用经审计原生 `15m` 聚合的偏移 `30m` 做相位审计。
- 机制：EMA 趋势背景下的低波动压缩、Donchian 或 Keltner 收盘突破，下一根开盘执行，ATR 止损与定时退出。
- 边界：这是独立的 `30m` 家族，不继承 [`BTC-15M-Trend-Continuation`](../15m-trend-continuation/README.md) 的版本、证据或 live-readiness。
- 当前状态：`explore / not promoted / not live-ready`
- 当前结论：没有通过完整门禁的策略；仅保留低频观察 `lvcb-08816b18771a`，它通过历史收益、双倍成本和偏移相位审计，但因开发期样本不足与收益集中而不构成研究候选。

## 入口

- [家族主账](btc-30m-trend-continuation-core-ledger.md)
- [决策日志](decision-log.md)
- [首轮趋势搜索诊断](diagnostics/btc-30m-trend-search-2026-07-21.md)
- [研究脚本](scripts/README.md)
- [机器产物](artifacts/README.md)
