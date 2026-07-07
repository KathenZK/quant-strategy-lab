# HYPE V30 Lag Audit

> 迁移说明：本文由 legacy Cursor Canvas `hype-v30-lag-audit.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：HYPE-EMA-TB legacy Canvas。

审计 V30 中 `shift(1)+close[t]` legacy 回测口径和可执行 `bar close signal -> next open execution` 口径的差异。

Source: local Binance, Hyperliquid, OKX HYPE 15m data lake. Audit run: strict next-open execution.

## 处理结论

| 项目 | 判断 | 说明 |
| --- | --- | --- |
| 结论 | 质疑成立 | 旧口径 `shift(1)+close[t]` 不是未来函数，但会形成一根 K 的人为延迟路径，不能作为可执行主基准 |
| 处理方式 | 主基准改为 next-open | bar[t] close 生成信号，bar[t+1] open 成交 |
| 收益变化 | 千位数收益消失 | Binance full 从 legacy `+2188.01%` 降级为参考上限；严格 next-open 审计为 `+456.51%` |
| 文档修复 | 已更新 spec | `research/hype/15m-ema-trend-breakout/canonical-specs/hype-trend-strategy-v30-spec.md` 默认口径已改成 next-open |

## Lag 口径对照

| 交易所 | 口径 | 窗口 | 收益 | 最大回撤 | Sharpe | 交易数 | 胜率 | 止盈 / 指标或timeout / 止损 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Binance | 可执行 next-open | Full | +456.51% | -34.30% | 3.01 | 79 | 75.64% | 54 / 17 / 7 |
| Binance | Legacy shift+close | Full | +2188.01% | -16.36% | 5.37 | 82 | 83.95% | 64 / 14 / 2 / 1 |
| Binance | 可执行 next-open | Aligned | +277.12% | -34.30% | 2.77 | 69 | 75.00% | 46 / 15 / 7 |
| Binance | Legacy shift+close | Aligned | +1267.92% | -16.81% | 5.29 | 71 | 84.29% | 56 / 11 / 2 / 1 |
| Hyperliquid | 可执行 next-open | Aligned | +189.92% | -41.29% | 2.16 | 68 | 71.64% | 46 / 11 / 10 |
| Hyperliquid | Legacy shift+close | Aligned | +517.37% | -24.60% | 3.57 | 67 | 77.27% | 49 / 10 / 4 / 3 |
| OKX | 可执行 next-open | Full | +362.01% | -36.07% | 2.57 | 83 | 73.17% | 58 / 15 / 9 |
| OKX | Legacy shift+close | Full | +569.26% | -29.26% | 3.17 | 85 | 75.00% | 60 / 14 / 7 / 3 |

## Spec 修复点

| 项目 | 新口径 | 说明 |
| --- | --- | --- |
| Spec 默认执行 | next_bar_open | 同事复现时只使用这个口径 |
| Legacy 结果 | deprecated_reference_only | `+2188%` 只保留为研究上限，不参与实盘判断 |
| 信号计算 | bar[t] close | EMA/ADX/volume/ATR 使用第 t 根已收盘数据 |
| 入场成交 | open[t+1] | 避免上一根信号却在本根 close 成交的 lag=1 混搭 |
| 止盈止损 | entry ATR 固定 | 开仓时记录 signal bar ATR，止盈止损距离固定 |
