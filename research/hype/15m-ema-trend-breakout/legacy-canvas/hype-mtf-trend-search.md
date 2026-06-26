# HYPE Multi-Timeframe Trend Search

> 迁移说明：本文由 legacy Cursor Canvas `hype-mtf-trend-search.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：HYPE-EMA-TB legacy Canvas。

Search over 15m execution, 1h breakout signals, and 4h trend filters. Pure trend here means breakout/EMA continuation, not the V1 pullback entry.

Source: local Binance HYPE perpetual data lake · 15m execution validation · includes 8.5 bps turnover cost · research output from scripts/hype_multi_timeframe_trend_search.py.

### 关键指标

| 指标 | 数值 |
| --- | --- |
| Best overall return | +160.94% |
| Best overall drawdown | -12.77% |
| Best pure-trend return | +87.67% |
| Low-DD pure trend | -10.98% |

> **Main Finding**
> The best pure trend strategy is profitable, but it does not beat the V1 trend-pullback strategy on the return/drawdown frontier. HYPE rewards buying pullbacks inside a trend more than chasing clean breakouts.

## Return vs Drawdown

Y-axis: percent. X-axis: strategy candidate. Return and max drawdown are full-sample metrics on local HYPE data.

> 图表数据未能完全自动解析，请按源 Canvas 复核。

## Trade Count

Y-axis: entries. X-axis: strategy candidate. Fewer trades generally means lower turnover sensitivity.

> 图表数据未能完全自动解析，请按源 Canvas 复核。

## Candidate Summary

> 表格数据未能完全自动解析，请按源 Canvas 复核。

## 自动转换复核提示

以下数据数组包含 TypeScript 对象、表达式或 JSX，未必全部进入正文表格：

- `candidates`

以下组件存在降级转换提示，建议人工抽查源 Canvas：

- `chart`
- `table`
