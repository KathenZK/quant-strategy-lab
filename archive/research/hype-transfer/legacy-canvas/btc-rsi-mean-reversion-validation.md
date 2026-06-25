# BTC RSI Mean Reversion Validation

> 迁移说明：本文由 legacy Cursor Canvas `btc-rsi-mean-reversion-validation.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：Cross-asset / transfer legacy Canvas。

Validation run for BTCUSDT 15m using Binance spot klines. Signal is computed on bar close and executed on the next bar.

### 关键指标

| 指标 | 数值 |
| --- | --- |
| Claimed +204.6% annualized | Not reproduced |
| RSI14 long 20/65, 1y, 7 bps | -15.57% |
| Same strategy, 1y, no costs | -10.08% |
| Long entries in last 365d | 45 |

> **Conclusion**
> Under the clean no-lookahead execution model, the quoted +204.6% annualized return does not validate on the available recent BTCUSDT 15m data.

## Main Checks

| Variant | Window | Costs | Annualized | Max DD | Entries | Active |
| --- | --- | --- | --- | --- | --- | --- |
| RSI14 long, 20/65 | 2025-05-07 to 2026-05-07 | 7 bps | -15.57% | -31.72% | 45 | 12.07% |
| RSI14 long, 20/65 | 2025-05-07 to 2026-05-07 | 0 bps | -10.08% | -29.39% | 45 | 12.07% |
| RSI20 long, 20/65 | 2025-05-07 to 2026-05-07 | 7 bps | -20.24% | -32.10% | 12 | 8.30% |
| RSI20 instant long/short | 2025-05-07 to 2026-05-07 | 7 bps | -48.61% | -48.87% | 552 | 6.06% |
| RSI20 instant long/short | 2025-05-07 to 2026-05-07 | 0 bps | +11.22% | -9.04% | 552 | 6.06% |
| Buy and hold | 2025-05-07 to 2026-05-07 | 0 bps | -15.98% | n/a | 1 | 100.00% |

## Window Sensitivity

| Window | Dates | Variant | Annualized | Max DD | Entries |
| --- | --- | --- | --- | --- | --- |
| 2025 to now | 2025-01-01 to 2026-05-07 | RSI14 long 20/65, 7 bps | -20.78% | -35.70% | 59 |
| Last 365d | 2025-05-07 to 2026-05-07 | RSI14 long 20/65, 7 bps | -15.57% | -31.72% | 45 |
| Last 180d | 2025-11-08 to 2026-05-07 | RSI14 long 20/65, 7 bps | -34.65% | -30.22% | 23 |
| Last 90d | 2026-02-06 to 2026-05-07 | RSI14 long 20/65, 7 bps | +12.09% | -4.94% | 8 |

## Assumptions

Market: Binance spot BTCUSDT 15 minute klines.

RSI: Wilder/EWM calculation matching the repository's `RSIFactor` implementation.

Primary rule: long when RSI is at or below 20, exit when RSI is at or above 65.

Execution: one-bar delay from close signal to tradable position; costs tested at 0 bps and 7 bps round-turn assumptions per rebalance side.
