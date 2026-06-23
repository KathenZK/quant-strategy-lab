# Trend Confirmation Backtest

> 迁移说明：本文由 legacy Cursor Canvas `trend-confirmation-backtest.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：HYPE-EMA-TB legacy Canvas。

Binance USDT perpetuals · BTC/ETH/SOL · 1h bars · 2025-05-23 23:00 UTC to 2026-05-23 23:00 UTC

### 关键指标

| 指标 | 数值 |
| --- | --- |
| 1y Strategy Return | -58.12% |
| 1y BTC Buy/Hold | -28.49% |
| Aligned 1h Bars | 8,761 |
| Missing OI/Basis/Funding Cells | 0 |

## Return By Window

| Window | Return | Final Equity | Max Drawdown | Sharpe | BTC Buy/Hold | Active Bars |
| --- | --- | --- | --- | --- | --- | --- |
| 1w | -2.11% | $97,894.31 | -2.17% | -22.07 | -1.78% | 59 / 169 |
| 1m | -5.12% | $94,875.37 | -5.20% | -10.36 | -1.92% | 283 / 721 |
| 3m | -23.01% | $76,985.17 | -23.29% | -12.54 | +18.71% | 834 / 2,137 |
| 6m | -32.37% | $67,631.59 | -32.37% | -8.22 | -11.63% | 1,645 / 4,345 |
| 1y | -58.12% | $41,882.88 | -58.12% | -9.45 | -28.49% | 3,406 / 8,761 |

Source: Binance Data Vision archives. OI uses daily metrics resampled to 1h by last value in each hour. Fees/slippage: 5 bps + 2 bps. Starting cash: $100,000.

## Data Coverage

Each symbol loaded 8,881 OHLCV bars, 8,881 mark/index bars, 8,881 hourly OI observations, and 1,119 funding observations.

## Execution Assumptions

Max weight per symbol is 0.20, gross leverage cap is 1.0, and minimum dollar volume is $1,000,000.

## Important Caveat

Liquidation overlay is neutralized with zero risk features in this run because historical liquidation archives were not included.
