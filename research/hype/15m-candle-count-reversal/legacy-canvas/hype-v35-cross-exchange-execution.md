# HYPE V35 Cross-Exchange Execution

> 迁移说明：本文由 legacy Cursor Canvas `hype-v35-cross-exchange-execution.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：HYPE-CC legacy Canvas。

问题：用 Binance HYPE 永续 15m 作为信号源，在 Hyperliquid 上执行，是否会因为极端跨所价格不一致导致策略失效。

> **结论**
> 在共同数据窗口内，Binance 信号 + HL 执行没有崩：Full return +2683.46%，MDD -33.02%，Sharpe 4.26。HL 自己出信号才是主要问题，HL native 只有 +123.72%、MDD -46.91%。

### 关键指标

| 指标 | 数值 |
| --- | --- |
| Cross full return | +2683% |
| Cross max drawdown | -33.0% |
| Entry spread p99 abs | 0.173% |
| Max close spread event | 8.19% |

## Scenario Performance

Chart: X axis = backtest window, Y axis = cumulative return (%). Source: local data lake, aligned Binance/HL HYPE 15m, 2025-07-27 to 2026-06-01.

原 Canvas 使用图表展示；这里保留图表底层数据。

| 分类 | Binance native return | HL native return | Binance signal + HL execution return |
| --- | --- | --- | --- |
| Full | 3348.55 | 123.72 | 2683.46 |
| 180d | 923.01 | 171.2 | 722.01 |
| 90d | 508.82 | 97.34 | 368.76 |
| 30d | 44.44 | -18.32 | 23.48 |
| 7d | -19.38 | -20.86 | -19.35 |

Chart: X axis = backtest window, Y axis = max drawdown (%). Same aligned source and time range.

原 Canvas 使用图表展示；这里保留图表底层数据。

| 分类 | Binance native max drawdown | HL native max drawdown | Binance signal + HL execution max drawdown |
| --- | --- | --- | --- |
| Full | -33.26 | -46.91 | -33.02 |
| 180d | -28.87 | -41.06 | -28.83 |
| 90d | -25.2 | -37.8 | -25.47 |
| 30d | -24.31 | -36.4 | -19.79 |
| 7d | -23.76 | -23.23 | -23.75 |

| Scenario | Full return | Max DD | Sharpe | Entries | Stop / Take / Early | Avg alloc |
| --- | --- | --- | --- | --- | --- | --- |
| Binance native | +3348.55% | -33.26% | 4.48 | 284 | 95 / 155 / 34 | 0.78x |
| HL native | +123.72% | -46.91% | 1.43 | 288 | 107 / 139 / 42 | 0.74x |
| Binance signal + HL execution | +2683.46% | -33.02% | 4.26 | 288 | 98 / 157 / 33 | 0.76x |

## Window Breakdown

| Window | Binance ret | HL ret | Cross ret | Binance DD | HL DD | Cross DD |
| --- | --- | --- | --- | --- | --- | --- |
| Full | +3348.55% | +123.72% | +2683.46% | -33.26% | -46.91% | -33.02% |
| 180d | +923.01% | +171.20% | +722.01% | -28.87% | -41.06% | -28.83% |
| 90d | +508.82% | +97.34% | +368.76% | -25.20% | -37.80% | -25.47% |
| 30d | +44.44% | -18.32% | +23.48% | -24.31% | -36.40% | -19.79% |
| 7d | -19.38% | -20.86% | -19.35% | -23.76% | -23.23% | -23.75% |

## Price Divergence Risk

常态价差很小：close spread 的 p99 绝对值只有 0.173%，cross 入场时最大价差 0.202%。真正异常集中在 2025-10-10 的单次冲击，最大 close spread 8.19%，但补充检查显示这些最大价差点没有跨所持仓。

| Metric | Value | Read |
| --- | --- | --- |
| Close spread median | +0.012% | HL close / Binance close - 1 |
| Close spread p95 abs | 0.130% | normal tail |
| Close spread p99 abs | 0.173% | still below V35 cost+slippage buffer |
| Close spread p99.9 abs | 0.242% | rare but manageable |
| Close spread max abs | 8.187% | 2025-10-10 event, no open cross trade |
| Entry spread p99 abs | 0.173% | measured only on 288 cross trades |
| Entry spread max abs | 0.202% | no entry happened during the 8% anomaly |

| UTC time | Binance close | HL close | Close spread | Return diff | Cross position |
| --- | --- | --- | --- | --- | --- |
| 2025-10-10 21:15 | 34.813 | 37.663 | +8.187% | +8.535% | No open cross trade |
| 2025-10-10 21:45 | 41.973 | 40.589 | -3.297% | -4.201% | No open cross trade |
| 2025-10-10 22:00 | 40.940 | 39.898 | -2.545% | +0.759% | No open cross trade |
| 2025-07-29 14:15 | 43.384 | 44.093 | +1.634% | +1.446% | No open cross trade |
| 2025-07-29 14:30 | 43.401 | 43.956 | +1.279% | -0.350% | No open cross trade |

### Signal Agreement

| Check | Value | Note |
| --- | --- | --- |
| All aligned 15m bars | 29,641 | 2025-07-27 09:00 UTC to 2026-06-01 03:00 UTC |
| Binance signal bars | 2,567 | 10/8 candle-count raw signal |
| HL signal bars | 2,578 | same config on HL candles |
| Same direction, all bars | 97.76% | mostly both zero or same side |
| Same direction, when any signal | 77.11% | HL native drift explains weak HL-native result |
| Opposite nonzero bars | 0 | no direct long-vs-short conflict in aligned bars |

### Trade Path Differences

| Check | Value | Note |
| --- | --- | --- |
| Common entry trades | 284 / 284 | Binance-native entries all existed in cross replay |
| Cross-only entries | 4 | caused by slightly different HL exit/cooldown path |
| Changed exit timing/reason | 41 | mostly same stop/take reason but shifted by 15-60m |
| Common-trade median net delta | 0.000% | cross minus Binance, pct of equity allocation |
| Common-trade p05 / p95 delta | -0.004% / +0.022% | tail mostly tiny |
| Worst / best common-trade delta | -14.355% / +13.767% | reason/timing path outliers |

## Exit Mix

Table units: trade count by exit reason. Source: full aligned window replay.

| Scenario | Stop | Take | Early main | Counter opposite | Counter favorable |
| --- | --- | --- | --- | --- | --- |
| Binance native | 95 | 155 | 20 | 3 | 11 |
| HL native | 107 | 139 | 24 | 5 | 13 |
| Binance signal + HL execution | 98 | 157 | 20 | 3 | 10 |

> **Deployment guardrail**
> 可以跑，但建议实盘加跨所价差保护：开仓前要求 Binance/HL mid 或 close spread 小于 0.3%-0.5%；若 spread 超过 1% 持续多根，暂停新开仓并报警。这个保护主要防 2025-10-10 这类异常，不是为了修复常态滑点。

## 自动转换复核提示

以下数据数组包含 TypeScript 对象、表达式或 JSX，未必全部进入正文表格：

- `returnSeries`
- `drawdownSeries`
