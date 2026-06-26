# HYPE-5M-Micro-Scalp Decision Log

Family id: `HYPE-5M-Micro-Scalp`

Historical alias: `HYPE-5M-MS`

## Current Boundary

- This is a separate Binance HYPEUSDT perpetual `5m` family for high-frequency micro-scalp research.
- It is not a version of `HYPE-5M-Pullback-Trail`, even when it reuses EMA, RSI, MACD, Bollinger, Donchian, ATR, ADX, or volume features.
- Research conclusions must be stored under this directory, with durable JSON/CSV evidence in `artifacts/`.
- No strategy from this family may be called live-ready until order timing, bracket maintenance, restart behavior, cost sensitivity, and paper/live-dry-run reconciliation are audited.

## Research Batches

- `diagnostics/hype-5m-micro-scalp-search-2026-06-26.md`: first executable broad search for the user goal of `3-5` trades/day, high win rate, low drawdown, and small per-trade profits on Binance HYPEUSDT `5m`. Tested `12576` curated/random EMA/RSI/MACD/Bollinger/VWAP/Donchian/ATR/ADX/volume/candle-structure configs under closed-bar signal, next-open entry, immediate TP/SL bracket, stop-first same-bar ordering, next-open timeout, and observed Binance live cost. Result: `1595` configs hit the `3-5` trades/day frequency band, but `0` hit hard pass and `0` hit audit pass. The best frequency-band annualized multiple was only `0.23x`; the highest-win frequency-band rows reached about `85%` win rate but remained deeply negative because payoff and cost overwhelmed small wins.

## Current Decision

- `HYPE-5M-Micro-Scalp-search-2026-06-26`: no-go for live, paper-live, or dry-run candidate promotion.
- The current evidence says the requested high-frequency micro-profit shape is not viable under this executable model and observed Binance cost model on the available HYPEUSDT `5m` sample.
- Do not promote high-win rows from this search without explicitly noting their negative PF, negative annualized multiple, and deep drawdown.
