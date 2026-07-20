# HYPE-30M-Keltner-Breakout-Retest

完整 family name：`HYPE-30M-Keltner-Breakout-Retest`

状态：`explore / not promoted / not live-ready`

市场与周期：Binance USDM 永续 `HYPEUSDT`；`30m` 信号、`1h` 趋势 regime。

机制：先确认 Keltner 通道突破，不立即追价；等待 1–3 根 `30m` K 线回踩突破轨但不破中轨，再以方向性收盘重新站回突破轨后于下一根 open 入场。

防串线警告：这是独立的 breakout→retest→reclaim 状态机，不是 [HYPE-30M-Keltner-Trend-Breakout](../30m-keltner-trend-breakout/README.md) 的已登记版本，也不继承其状态。

## 入口

- [hype-30m-keltner-breakout-retest-core-ledger.md](hype-30m-keltner-breakout-retest-core-ledger.md)
- [decision-log.md](decision-log.md)
- [diagnostics/hype-30m-keltner-breakout-retest-initial-search-2026-07-17.md](diagnostics/hype-30m-keltner-breakout-retest-initial-search-2026-07-17.md)

## 当前结论

首轮 864 组状态机搜索没有候选达到胜率、交易数、MDD和时间分离要求。最接近行仅 `38 笔 / 胜率 60.53% / Return +317.64% / MDD -22.15%`，明显弱于 parent V3 直接突破；不登记版本，停止当前 upper-retest→reclaim 定义。
