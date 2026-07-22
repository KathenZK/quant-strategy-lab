# BTC-15M-Trend-Continuation

- Alias：`BTC-15M-TC`
- 市场：Binance USD-M Futures `BTCUSDT` perpetual
- 周期：`15m`
- 机制：低波动压缩后顺长期 EMA 趋势做 Donchian 收盘突破，只做多，并用 ATR 保护止损与定时退出捕捉延续。
- 边界：不同于 [`BTC-15M-EMA-Trend-Breakout`](../15m-ema-trend-breakout/README.md) 的一般 EMA 突破模板，也不同于 [`BTC-15M-Keltner-Trend-Breakout`](../15m-keltner-trend-breakout/README.md) 的 Keltner 通道突破。
- 当前状态：`explore / not promoted / not live-ready`
- 当前角色：`lvcb-913f4ff89386` 为 long-only 全历史研究候选，不是已登记版本；六轮多头迭代无采纳项，空头专属 `804` 配置搜索也无门禁通过项，停止历史扩搜，只有 `2026-07-20 07:30 UTC` 之后的数据可形成多头 prospective 证据。

## 入口

- [家族主账](btc-15m-trend-continuation-core-ledger.md)
- [决策日志](decision-log.md)
- [长历史搜索诊断](diagnostics/btc-15m-trend-continuation-long-history-search-2026-07-20.md)
- [六轮迭代诊断](diagnostics/btc-15m-lvcb-iteration-rounds-2026-07-20.md)
- [空头专属搜索诊断](diagnostics/btc-15m-lvcb-short-search-2026-07-21.md)
- [研究脚本](scripts/README.md)
- [机器产物](artifacts/README.md)
