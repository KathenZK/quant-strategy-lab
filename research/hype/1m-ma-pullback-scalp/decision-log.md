# HYPE-1M-MA-Pullback-Scalp Decision Log

Family id: `HYPE-1M-MA-Pullback-Scalp`

## Current Boundary

- This is a separate Binance HYPEUSDT perpetual `1m` family for moving-average pullback scalp research.
- It is not a version of `HYPE-1M-EMA-Crossover`, because the entry is pullback-end structure confirmation rather than EMA cross event timing.
- It is not a version of `HYPE-5M-Micro-Scalp`, because timeframe, signal mechanics, cost sensitivity, and holding-time assumptions are different.
- Research conclusions must be stored under this directory, with durable JSON/CSV evidence in `artifacts/`.
- No strategy from this family may be called live-ready until order timing, bracket maintenance, restart behavior, cost sensitivity, and paper/live-dry-run reconciliation are audited.

## Research Batches

- Initial scaffold: `scripts/research_hype_1m_ma_pullback_scalp.py` implements the two-MA pullback structure pattern with closed-bar signals, next-open entries, fixed TP/SL brackets, stop-first same-bar ordering, and max-hold timeout.
- `diagnostics/hype-1m-ma-pullback-scalp-search-2026-06-26.md`: first executable search. Tested `6,740` configs across `reclaim`, `platform_break`, and `engulf_reclaim` triggers on Binance HYPEUSDT perpetual `1m`; data quality passed with `134,184` continuous bars, raw/normalized OHLCV alignment mismatch counts all `0`, and no missing/duplicate/OHLCV hard violations. Result: `0` paper candidate passes. At `>=60` trades, `0` configs were profitable; at `>=1` trade/day, highest full-sample annualized multiple was `0.57x`. Best enough-sample score row was `HYPE_1M_MA_PBS_R03037`, `platform_break` long, EMA `13/89`, TP/SL/hold `260/130/30`, `72` trades, annualized `0.73x`, PF `0.769`, win `45.83%`, maxDD `-10.30%`, recent 30d `-2.62%`.

## Current Decision

- No-go for promoting this exact two-MA pullback scalp shape to paper-live or live.
- The strategy can be written and backtested, but current evidence does not support saying it is profitable or real-capital ready on the available HYPEUSDT `1m` sample.
