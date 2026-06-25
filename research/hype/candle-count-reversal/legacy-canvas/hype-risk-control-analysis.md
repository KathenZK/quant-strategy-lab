# HYPE Risk Control Analysis

> 迁移说明：本文由 legacy Cursor Canvas `hype-risk-control-analysis.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：HYPE-CC legacy Canvas。

Current optimized strategy over Binance HYPE 15m data from 2025-05-30 to 2026-05-13.

### 关键指标

| 指标 | 数值 |
| --- | --- |
| Current net return | +138.05% |
| Current max drawdown | -92.65% |
| Current trades | 725 |
| Cost vs initial capital | 152.25% |

> **Root Cause**
> The worst drawdown is not a single bad stop. It is clustered losses and compounding exposure from 2025-09 to 2026-02, with January 2026 alone losing about 85.7% on the strategy equity curve.

## Candidate Controls

| Control | Return | Max DD | Trades | Interpretation |
| --- | --- | --- | --- | --- |
| 0.75x leverage only | +80.42% | -41.75% | 725 | Simplest, robust, but leaves trade frequency unchanged. |
| 1.5x + monthly -20% stop | +305.87% | -45.30% | 535 | Best balance in scan: lower leverage plus stop trading for the rest of a bad month. |
| 2.5x + account -20% DD breaker | +69.80% | -20.19% | 48 | Capital-preservation mode; cuts most exposure after the first large drawdown. |
| 3x + account -30% DD breaker | +69.67% | -30.06% | 50 | Keeps 3x sizing but uses a hard portfolio circuit breaker. |

## Recommended Stack

| Layer | Rule | Why |
| --- | --- | --- |
| Base sizing | Reduce default leverage from 3x to 1.5x or 2x | Most reliable way to reduce drawdown; no regime assumption. |
| Monthly breaker | If strategy equity loses 20% in a month, flatten until next month | Directly targets clustered losing regimes like Jan 2026. |
| Account breaker | If peak-to-trough drawdown exceeds 30%, flatten for at least 4 trading days | Prevents compounding into near-liquidation drawdowns. |
| Execution realism | Use mark price high/low and real taker/maker fee schedule | Current stop model is close-based and may understate intrabar risk. |

> **Data Needed For Production-Quality Risk**
> Better fee tier, maker/taker split, mark-price klines, liquidation/margin rules, and order-book depth would make the backtest much more realistic. Without those, the best risk controls are conservative sizing and account-level circuit breakers.
