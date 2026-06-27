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
- `2026-06-27`: `research_hype_1m_ema_deviation_take_profit.py` tested the requested short-cycle EMA cross shape (`8/21`, `13/48`, `21/55`, `21/72`, `21/96`, `30/120`) with ATR-normalized fast-EMA deviation arming, high/low-water drawdown exits, exhaustion confirmation, and staged partial take-profit. Data quality passed on `134,184` continuous Binance HYPEUSDT `1m` bars from `2026-03-25 00:00:00 UTC` to `2026-06-26 04:23:00 UTC`, but `0` rows passed the paper gate.
- `2026-06-27`: `research_hype_1m_ema_v35_filter_overlay.py` translated `HYPE-EMA-Trend-Breakout-V35` strength filters onto the `1m` EMA cross + deviation take-profit shape: closed 15m EMA96/384 direction, 15m ADX28, 15m volume_surge, closed 1h confirmation, and relaxed/early-ADX variants. The overlay reduced noise dramatically versus the unfiltered short-cycle cross, but still produced `0` paper-gate rows. Best full-sample rows were only near flat to `+1.05%` and failed forward/recent slices; the `EMA21/96` positive rows had only `2` trades.

## Candidate Notes

- `HYPE-1M-EMA-Crossover-TRAIL-144-1597`: first preferred paper-live candidate. It uses EMA144/EMA1597 cross entries, ADX/ret60/ATR/cooldown filters, a `1.4%` hard stop, `1.4%` trailing activation, `1.8%` trail distance, and `1,440` bar max hold. The `2x` exposure version clears the requested `20x` annualized factor with lower drawdown than the `3x` search winner.
- `HYPE-1M-EMA-Crossover-FIXED-233-1597`: secondary fixed take-profit reference. It had fewer trades and required higher exposure to clear the return target, so it is less preferred than the trailing candidate.
- `HYPE-1M-EMA-Crossover-DEVIATION-TP-SHORT-CYCLE`: no-go diagnostic, not a candidate. The requested `EMA21/96` subset was materially negative even before leverage; its best tested row was approximately `-74%` full-sample return at `1x`, with forward and recent slices also negative. The result supports keeping deviation as an exit-state concept, but not using short-cycle EMA cross chasing as a standalone candidate under the current cost model.
- `HYPE-1M-EMA-Crossover-V35-FILTER-OVERLAY`: no-go diagnostic, not a candidate. V35-style 15m/1h trend-quality filters are useful for suppressing false 1m crosses, but the profitable mechanism in `HYPE-EMA-Trend-Breakout-V35` is still the 15m trend-breakout entry plus ATR bracket, not the 1m cross itself.

## Live Feasibility Gate

Before any promotion beyond paper-live:

- Add funding-rate accounting.
- Re-run on a later forward window without changing parameters.
- Re-run after `2026-06-25` closes so the final day is not partial.
- Audit real Binance account fee tier and live slippage from fills.
- Implement restart recovery, reduce-only protective orders, duplicate-order/idempotency handling, missing-data behavior, and an emergency flat/kill switch.
