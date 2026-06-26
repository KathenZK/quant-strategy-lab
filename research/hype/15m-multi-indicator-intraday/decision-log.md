# HYPE-15M-MII Decision Log

This is the family-level reading path for Binance HYPEUSDT `15m` multi-indicator intraday research.

## Current Boundary

- This is a new exploratory research family, not a promoted live strategy.
- It exists because the requested search allows broad indicator combinations rather than a pure EMA crossover, trend-breakout, or candle-count rule.
- Any candidate must be judged after live-realistic order timing, stop/target feasibility, fees, slippage, time-slice stability, and restart/state-machine reproducibility checks.

## Decisions

- `2026-06-25`: create a separate family `HYPE-15M-Multi-Indicator-Intraday` (`HYPE-15M-MII`) rather than overloading existing 15m EMA or candle-count families.
- `2026-06-25`: first broad Binance HYPEUSDT `15m` multi-indicator intraday search is negative. Best combined candidate reached `+141.92%` annual return, `-18.88%` max drawdown, `76.90%` win rate, and `0.94` trades/day, but failed the `>= 2000%` annual return target and degraded to `-5.26%` annualized in the last `90d`. Do not promote.

## Evidence Policy

- Prefer this family README, durable Markdown reports, and artifacts over scratch outputs.
- Top-level `reports/` is not durable evidence for this family.
- Negative findings should be written here or in a durable diagnostic note instead of hidden by additional parameter search.
