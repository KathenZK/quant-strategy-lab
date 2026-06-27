# HYPE 15m Strategy Optimization

> 迁移说明：本文由 legacy Cursor Canvas `hype-15m-optimization.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：HYPE-CC legacy Canvas。

Window: 2026-02-13 06:15 UTC to 2026-05-13 06:15 UTC. Strategy remains 3x long/short and uses close-based stop/take-profit exits.

### 关键指标

| 指标 | 数值 |
| --- | --- |
| Optimized net return | +476.99% |
| Max drawdown | -36.94% |
| Trades after optimization | 155 |
| HYPE buy and hold | +31.21% |

> **Main Pattern**
> The three-month alpha improves when entries are less frequent and stops are wider. Raising the trigger from 7/10 to 8/10 candles reduces noisy crowding signals, while 3% stop and 3% take-profit lets the position survive normal 15m noise.

## Before vs After

| Rule Set | Net Return | Max DD | Trades | Cost Sum | No-Cost Return |
| --- | --- | --- | --- | --- | --- |
| Original 7/10, 1% SL, 2% TP | -52.92% | -78.67% | 647 | 135.87% | +84.18% |
| Optimized 8/10, 3% SL, 3% TP | +476.99% | -36.94% | 155 | 32.55% | +698.30% |

## Implemented Defaults

| Parameter | New Default | Reason |
| --- | --- | --- |
| min_count | 8 | Requires a stronger 10-bar candle-color imbalance before entering. |
| stop_loss_pct | 3% | Avoids repeated exits from normal 15m noise. |
| take_profit_pct | 3% | Captures mean-reversion moves without waiting for rare large swings. |
| cooldown_bars | 8 | Pauses for about 2 hours after an exit. |
| entry_mode | signal_start | Avoids re-entering the same crowding segment repeatedly. |
| opposite_signal_gap_bars | 8 | Skips entries when the opposite crowding signal appeared recently. |

## Optimized Backtest Detail

### 关键指标

| 指标 | 数值 |
| --- | --- |
| 15m bars | 8545 |
| Bars in position | 5825 |
| Sharpe | 4.97 |

> **Sanity Check**
> On the full available Binance sample from 2025-05-30, the optimized defaults are still positive at +138.05%, but max drawdown is -92.65%. This is a high-risk, recent-regime-sensitive rule, not a production-ready system.

Report: ../artifacts/runs/candle_count_short_binance_perp_15m_3m_optimized/20260513T070113646054Z/backtest_report.md
