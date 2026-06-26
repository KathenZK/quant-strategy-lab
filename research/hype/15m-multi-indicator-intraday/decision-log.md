# HYPE-15M-MII Decision Log

This is the family-level reading path for Binance HYPEUSDT `15m` multi-indicator intraday research.

## Current Boundary

- This is a new exploratory research family, not a promoted live strategy.
- It exists because the requested search allows broad indicator combinations rather than a pure EMA crossover, trend-breakout, or candle-count rule.
- Any candidate must be judged after live-realistic order timing, stop/target feasibility, fees, slippage, time-slice stability, and restart/state-machine reproducibility checks.

## Decisions

- `2026-06-25`: create a separate family `HYPE-15M-Multi-Indicator-Intraday` (`HYPE-15M-MII`) rather than overloading existing 15m EMA or candle-count families.
- `2026-06-25`: first broad Binance HYPEUSDT `15m` multi-indicator intraday search is negative. Best combined candidate reached `+141.92%` annual return, `-18.88%` max drawdown, `76.90%` win rate, and `0.94` trades/day, but failed the `>= 2000%` annual return target and degraded to `-5.26%` annualized in the last `90d`. Do not promote.
- `2026-06-26`: full parameter ablation and expanded time-slice backtests confirmed the same negative boundary. The baseline reproduced exactly, but `0/55` baseline/variant rows met the full gate; the only higher annualized rows either breached drawdown, failed recent stability, or reduced frequency. Data quality checks on `data/cache/hypeusdt_15m_fapi.csv` found no gaps/duplicates/OHLC errors, but the input is still cache-only and lacks `quote_volume/trade_count/vwap/source/is_closed`, so it is not a standard data-lake promotion dataset. Do not promote.
- `2026-06-26`: combining surface-improvement ablation parameters did not produce an optimized strategy. The grid evaluated `594` non-baseline combinations; `0` achieved both higher annualized return and no-worse max drawdown while also passing trade-shape and recent-stability gates. Highest-return combo improved annualized return to `+174.81%` but worsened max drawdown to `-23.24%`; the best compromise reached `+153.01%` with `-19.94%` max drawdown. Do not promote; do not treat higher leverage or TP widening as optimization.

## Evidence Policy

- Prefer this family README, durable Markdown reports, and artifacts over scratch outputs.
- Top-level `reports/` is not durable evidence for this family.
- Negative findings should be written here or in a durable diagnostic note instead of hidden by additional parameter search.
