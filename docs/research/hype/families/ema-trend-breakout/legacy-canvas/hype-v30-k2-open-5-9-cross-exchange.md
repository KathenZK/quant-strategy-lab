# HYPE V30 K2 Open 5/9 Cross-Exchange

> 迁移说明：本文由 legacy Cursor Canvas `hype-v30-k2-open-5-9-cross-exchange.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：HYPE-EMA-TB legacy Canvas。

将 Binance 上筛出的最佳组合 5ATR 止盈 / 9ATR 止损，用相同 K2 open 执行口径复跑 Binance、Hyperliquid、OKX。

Source: local Binance, Hyperliquid, OKX HYPE 15m data lake. Existing 8.5bps cost and funding included.

## 结论

| 项目 | 判断 | 证据 |
| --- | --- | --- |
| 核心结论 | 5ATR take / 9ATR stop 的 K2 open 版本跨交易所可跑 | Binance +926.89%，HL +359.61%，OKX +470.21% |
| 风险 | OKX 回撤偏高 | OKX full maxDD -37.32%，HL -29.48%，Binance -28.60% |
| 稳定性 | 滚动窗口全部为正 | 三家 30天与 90天滚动窗口 positive 都是满格 |
| 交易所排序 | Binance 最强，OKX 次之，HL 最保守 | 但 HL/OKX 都没有失效，说明不是纯 Binance 孤点 |

## 主结果

| 交易所 | 窗口 | 收益 | 最大回撤 | Sharpe | 交易数 | 胜率 | 止盈 / 指标 / timeout / 止损 | 多 / 空 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Binance | Full | +926.89% | -28.60% | 3.74 | 75 | 79.73% | 54 / 11 / 2 / 7 | 54 / 21 |
| Binance | Aligned | +739.10% | -28.60% | 4.03 | 65 | 81.25% | 47 / 9 / 2 / 6 | 46 / 19 |
| Hyperliquid | Full/Aligned | +359.61% | -29.48% | 2.84 | 65 | 71.88% | 43 / 11 / 3 / 7 | 44 / 21 |
| OKX | Full | +470.21% | -37.32% | 2.85 | 79 | 71.79% | 51 / 14 / 4 / 9 | 56 / 23 |
| OKX | Aligned | +330.80% | -37.32% | 2.82 | 70 | 71.01% | 44 / 13 / 4 / 8 | 49 / 21 |

## 滚动窗口

| 交易所 | 窗口 | 样本数 | 正收益数 | 最低收益 | 中位收益 | 平均收益 | 最差回撤 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Binance | 30天 | 38 | 38 | +46.61% | +397.78% | +378.17% | -30.30% |
| Binance | 90天 | 29 | 29 | +103.26% | +443.21% | +469.77% | -30.30% |
| Hyperliquid | 30天 | 38 | 38 | +0.57% | +170.44% | +175.26% | -29.48% |
| Hyperliquid | 90天 | 29 | 29 | +63.82% | +210.22% | +221.31% | -29.48% |
| OKX | 30天 | 38 | 38 | +21.82% | +263.21% | +229.24% | -37.32% |
| OKX | 90天 | 29 | 29 | +82.18% | +302.74% | +288.76% | -37.32% |

## 数据口径

| 项目 | 说明 |
| --- | --- |
| 策略口径 | K0 close 信号，等待完整 K1，K2 open 入场 |
| 参数 | take_atr=5.0，stop_atr=9.0，固定 entry ATR；其他 V30 参数不变 |
| Binance data | HYPE/USDT perp 15m；funding 覆盖完整窗口 |
| Hyperliquid data | HYPE/USDC perp 15m；funding 覆盖 aligned/full 窗口 |
| OKX data | HYPE/USDT perp 15m；funding 仅 2026-03-02 后，前面缺失按 0 |
