# HYPE-1M-EMA-Crossover Decision Log

Family name: `HYPE-1M-EMA-Crossover`

Historical alias: `HYPE-1M-EMA-X`

## Current Boundary

- This is a separate HYPE strategy family for Binance HYPEUSDT `1m` EMA cross research.
- It is not a sub-version of `HYPE-EMA-Crossover` / `15m-ema-crossover`.
- It is not a live-approved strategy line yet.
- Its first candidate must be treated as paper-live only until forward validation and live execution audits are complete.

## Research Batch Notes

- `research_hype_1m_ema_crossover_live_search.py`: first Binance HYPEUSDT `1m` EMA cross search over `2026-03-25` to `2026-06-25`. It tested live-executable next-bar entries, fixed take-profit, trailing take-profit, hard stops, conservative same-candle stop priority, cost assumptions, and common filters.
- `2026-06-26`: promote the first `1m` dataset from downloader cache into the standard data lake, then refresh it through `2026-06-26 04:23:00 UTC`: raw and normalized candles under `data/raw|normalized/ohlcv/exchange=binance/market_type=perp/timeframe=1m/date=*/symbol=hype_usdt_usdt.parquet`, plus search feature factors under `data/features/factor=*/version=hype_1m_ema_crossover_live_search_2026_06_25/...`.

## Candidate Notes

- `HYPE-1M-EMA-Crossover-TRAIL-144-1597`: first preferred paper-live candidate. It uses EMA144/EMA1597 cross entries, ADX/ret60/ATR/cooldown filters, a `1.4%` hard stop, `1.4%` trailing activation, `1.8%` trail distance, and `1,440` bar max hold. The `2x` exposure version clears the requested `20x` annualized factor with lower drawdown than the `3x` search winner.
- `HYPE-1M-EMA-Crossover-FIXED-233-1597`: secondary fixed take-profit reference. It had fewer trades and required higher exposure to clear the return target, so it is less preferred than the trailing candidate.

## Live Feasibility Gate

Before any promotion beyond paper-live:

- Add funding-rate accounting.
- Re-run on a later forward window without changing parameters.
- Re-run after `2026-06-25` closes so the final day is not partial.
- Audit real Binance account fee tier and live slippage from fills.
- Implement restart recovery, reduce-only protective orders, duplicate-order/idempotency handling, missing-data behavior, and an emergency flat/kill switch.
