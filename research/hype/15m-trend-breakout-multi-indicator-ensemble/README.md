# HYPE-15M-Trend-Breakout-Multi-Indicator-Ensemble

Alias：`HYPE-15M-TB-MII-ENS`

Created：2026-07-07

## 边界

本目录研究 Binance HYPEUSDT 永续 `15m` 上把两个既有家族版本组合成一个新策略：

- 趋势腿：`HYPE-EMA-Trend-Breakout-V35`（EMA96/384 趋势突破 + ADX/成交量/1h 确认，K+2 open 入场，5ATR 止盈 / 7ATR 硬止损 / ADX22 delayed3 / 384 根 timeout，ATR 动态仓位上限 3x）。
- 反转腿：`HYPE-15M-Multi-Indicator-Intraday-V1.3`（RSI(7) 40/60 反转 + MACD 方向 + ATR96 0.75%-2.80% + RVOL96>=1.0，K+1 open 入场，ATR96 bracket TP=1.25x / SL=5.0x / hold=24，固定 2.5x 暴露）。

本目录不修改两个母家族的版本定义；母版本口径以各自主账为准：

- `../15m-ema-trend-breakout/hype-ema-tb-core-ledger.md`
- `../15m-multi-indicator-intraday/hype-15m-mii-core-ledger.md`

## 当前状态

- 当前状态：`first combination diagnostic / NO-GO / not live-ready`。
- 首次组合回测结论见 `research-notes/hype-15m-tb-mii-ensemble-first-combination-backtest-2026-07-07.md`。
- 家族主账：`hype-15m-tb-mii-ens-core-ledger.md`。

## 阅读顺序

1. `../../README.md`
2. `../README.md`
3. 本文件
4. `hype-15m-tb-mii-ens-core-ledger.md`
5. `decision-log.md`
6. `research-notes/` 内具体报告
