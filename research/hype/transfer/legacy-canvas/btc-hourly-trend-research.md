# BTC 1h Trend Research

> 迁移说明：本文由 legacy Cursor Canvas `btc-hourly-trend-research.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：Cross-asset / transfer legacy Canvas。

Source: local Binance BTC/USDT perpetual 1h OHLCV, 2023-05-27 to 2026-05-27. Costs modeled as 8.5 bps per turnover.

## Return And Drawdown Comparison

原 Canvas 使用图表展示；这里保留图表底层数据。

| 分类 | BTC hourly trend | Buy and hold |
| --- | --- | --- |
| Return | 177.6 | 184.8 |
| Max drawdown | -29.9 | -50.1 |

Axis: percent return / drawdown. Drawdowns are shown as negative values.

### Selected Strategy

Rule: long when EMA48 is above EMA336, short when EMA48 is below EMA336.

Sizing: target 0.6% hourly ATR risk using ATR168, capped at 2x absolute exposure.

Implementation: btc_hourly_trend using factors ema_spread_48_336 and atr_pct_168 .

## Walk Forward Split Metrics

| Segment | Return | Max drawdown | Sharpe | Exposure |
| --- | --- | --- | --- | --- |
| Train to 2025-05-27 | +146.6% | -29.9% | 1.30 | 0.98 |
| Validation | +8.1% | -20.2% | 0.58 | 1.00 |
| Test from 2025-11-27 | +3.9% | -29.2% | 0.39 | 1.00 |
| Full sample | +177.6% | -29.9% | 1.04 | 0.99 |

## 自动转换复核提示

以下数据数组包含 TypeScript 对象、表达式或 JSX，未必全部进入正文表格：

- `summary`
