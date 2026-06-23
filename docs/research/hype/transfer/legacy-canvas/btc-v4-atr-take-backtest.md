# BTC V4 + ATR Take Backtest

> 迁移说明：本文由 legacy Cursor Canvas `btc-v4-atr-take-backtest.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：Cross-asset / transfer legacy Canvas。

将 HYPE 的 V4 + ATR止盈规则迁移到 BTCUSDT 永续。数据从 Binance Futures 临时拉取，手续费沿用 Hyperliquid taker 与 4bps 滑点口径。

### 关键指标

| 指标 | 数值 |
| --- | --- |
| BTC 一年收益 | -58.93% |
| BTC 一年最大回撤 | -73.41% |
| 一年开仓 | 174 |
| 一年平均有效仓位 | 2.18x |

## 回测结果

| 窗口 | 收益 | 最大回撤 | 开仓 | 止损 / 止盈 | 多 / 空 | 均仓 | 最大仓位 | 平均止盈 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1周 | -5.08% | -12.68% | 1 | 0 / 0 | 1 / 0 | 2.97x | 3.00x | 2.00% |
| 1月 | -7.37% | -26.85% | 14 | 5 / 8 | 6 / 8 | 2.44x | 3.00x | 2.01% |
| 1年 | -58.93% | -73.41% | 174 | 71 / 102 | 94 / 80 | 2.18x | 3.00x | 2.29% |

## 策略规则

| 模块 | 设置 |
| --- | --- |
| 信号 | 最近10根里阳线数量大于等于8做空；阴线数量大于等于8做多 |
| 动态仓位 | ATR96 动态降仓，max 3x，target ATR 0.4% |
| 趋势禁入 | 最近24小时涨跌超过6%时，不做逆势开仓 |
| 止损 | 固定3% |
| 止盈 | ATR192 乘以6，限制在2%到4% |

## 数据与费用口径

| 项目 | 值 | 说明 |
| --- | --- | --- |
| 数据来源 | Binance Futures API | 本地数据湖没有 BTC 15m 数据，已临时拉取 |
| 交易K线 | 15m BTCUSDT perpetual | close 进场，open/high/low/close 计算信号和ATR |
| Mark K线 | 15m mark price klines | mark high/low 触发止损止盈 |
| Funding | Binance fundingRate | 按15分钟对齐，持仓时计入资金费率 |
| 费用 | Hyperliquid taker 0.045% + 4bps slippage | 沿用 HYPE 回测口径 |

结论：这套参数明显是 HYPE 特征驱动，直接迁移到 BTC 不成立。BTC 的一年收益和回撤都很差， 不适合直接使用这组 HYPE 参数。
