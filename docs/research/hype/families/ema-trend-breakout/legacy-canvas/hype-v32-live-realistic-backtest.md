# HYPE V32 Live-Realistic 回测

> 迁移说明：本文由 legacy Cursor Canvas `hype-v32-live-realistic-backtest.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：HYPE-EMA-TB legacy Canvas。

重新按更接近实盘的成交顺序回测 V32：保留信号逻辑，修正入场 ATR、指标退出、同 K 再入场。

## 成交口径

| 环节 | live-realistic 规则 | 目的 |
| --- | --- | --- |
| 入场 | K0 close 出信号，K2 open 入场 | 保留 V32 原始延迟入场逻辑 |
| ATR / 仓位 | 用上一根已完成 15m K 的 ATR | 避免 K2 open 时使用当前 K high/low |
| 止盈止损 | TP/SL 可在持仓 K 内触发 | 用 OHLC 判断触发；同根同时触发时按 stop 优先 |
| 指标退出 | 收盘确认，下一根 open 出场 | 不再用当前 K close 理想成交 |
| 再入场 | 平仓后最早下一根 K open 再入 | 禁止同一根 K 平仓后回到该 K open 再开仓 |

## 结论

| 问题 | 判断 | 依据 |
| --- | --- | --- |
| 还能不能做 | 能 | 三家交易所在 live-realistic 下仍为正收益 |
| 收益是否可信 | 旧 V32 明显偏乐观 | 去掉同 K 回到 open 再入场后，收益大幅下降 |
| 跨交易所稳定性 | Binance 最强，OKX 明显变弱 | live-realistic 对 OKX 打击最大 |
| 后续策略版本 | 应以 live-realistic 作为新基准 | 后续所有消融都应基于这个成交口径重跑 |

## Full Window

退出结构为 take profit / indicator exit / stop loss / timeout。

| 交易所 | 版本 | 收益 | 最大回撤 | Sharpe | 交易数 | 胜率 | 退出结构 | 同 K 再入 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Binance | current V32 | +4001.27% | -24.41% | 4.81 | 104 | 80.58% | 78 / 13 / 9 / 3 | - |
| Binance | live-realistic | +1650.74% | -27.49% | 4.03 | 96 | 77.89% | 68 / 15 / 10 / 2 | 0 |
| Hyperliquid | current V32 | +1393.48% | -31.21% | 4.04 | 85 | 76.47% | 63 / 10 / 8 / 4 | - |
| Hyperliquid | live-realistic | +653.18% | -32.82% | 3.23 | 78 | 73.08% | 55 / 11 / 8 / 4 | 0 |
| OKX | current V32 | +1492.68% | -27.15% | 3.69 | 109 | 72.48% | 74 / 21 / 10 / 4 | - |
| OKX | live-realistic | +456.03% | -29.18% | 2.53 | 100 | 67.00% | 63 / 23 / 11 / 3 | 0 |

## Aligned Window

对齐到 2025-08-13 至 2026-06-01，便于 Binance / Hyperliquid / OKX 横向比较。

| 交易所 | 版本 | 收益 | 最大回撤 | Sharpe | 交易数 | 胜率 | 退出结构 | 同 K 再入 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Binance | current V32 | +2926.83% | -24.41% | 5.09 | 92 | 81.32% | 70 / 10 / 8 / 3 | - |
| Binance | live-realistic | +1190.07% | -27.49% | 4.18 | 84 | 78.31% | 60 / 12 / 9 / 2 | 0 |
| Hyperliquid | current V32 | +1283.50% | -28.88% | 3.99 | 85 | 76.19% | 62 / 10 / 8 / 4 | - |
| Hyperliquid | live-realistic | +597.34% | -32.82% | 3.16 | 78 | 72.73% | 54 / 11 / 8 / 4 | 0 |
| OKX | current V32 | +1147.17% | -27.15% | 3.89 | 99 | 72.45% | 67 / 18 / 9 / 4 | - |
| OKX | live-realistic | +334.40% | -29.18% | 2.53 | 90 | 66.29% | 56 / 20 / 10 / 3 | 0 |
