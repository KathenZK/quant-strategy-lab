# HYPE-15M-Keltner-Trend-Breakout

- Full family name：`HYPE-15M-Keltner-Trend-Breakout`
- Alias：`HYPE-15M-KTB`
- 市场/周期：Binance HYPEUSDT 永续 `15m`
- 机制：只使用 `EMA96 ± 2.4 × ATR144` Keltner 通道测试外轨突破、压缩扩张和中轨回踩，不使用 ADX/DI、成交量或高周期确认。
- 当前状态：`explore / not promoted / not live-ready`；首轮纯突破及三条新机制均失败，未登记版本。

## 边界

- 这是独立的纯 Keltner 家族，不是 [HYPE-EMA-Trend-Breakout](../15m-ema-trend-breakout/README.md) V2P/V35 的版本。
- 也不是 [HYPE-30M-Keltner-Trend-Breakout](../30m-keltner-trend-breakout/README.md) 的时间周期变体；不继承其参数、证据或状态。

## 入口

- [hype-15m-keltner-trend-breakout-core-ledger.md](hype-15m-keltner-trend-breakout-core-ledger.md)
- [新机制假设诊断](diagnostics/hype-15m-keltner-mechanism-hypotheses-2026-07-21.md)
- [首轮精简回测诊断](diagnostics/hype-15m-keltner-only-initial-backtest-2026-07-20.md)
- [decision-log.md](decision-log.md)
- [scripts/](scripts/README.md)
- [artifacts/](artifacts/README.md)
