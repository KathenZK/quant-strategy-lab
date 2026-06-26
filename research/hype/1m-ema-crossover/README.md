# HYPE-1M-EMA-Crossover

Family name: `HYPE-1M-EMA-Crossover`

Historical alias: `HYPE-1M-EMA-X`

This family covers Binance HYPEUSDT `1m` EMA golden/death cross research with live-executable order timing. It is split out from the older `HYPE-EMA-Crossover` (`15m-ema-crossover`) family because the timeframe, signal frequency, execution cost sensitivity, and live-runner state machine are materially different.

Do not merge this with `HYPE-EMA-Crossover` just because both use EMA cross logic. The `15m` family is the long-running V14/V15/V16/V17 research lineage; this directory is the separate `1m` line.

## Core Status

- Current status: diagnostic / paper-live candidate only.
- Current preferred paper-live rule: `HYPE-1M-EMA-Crossover-TRAIL-144-1597`.
- Preferred trial sizing from the first search: `2x`.
- Hard cap from the first search: `3x`.
- Not live-approved until forward validation, funding/slippage audit, and live-runner restart/idempotency checks are complete.

## Evidence Surface

- `diagnostics/hype-1m-ema-crossover-live-search-2026-06-25.md`: first live-executable Binance HYPEUSDT `1m` EMA search report.
- `scripts/research_hype_1m_ema_crossover_live_search.py`: reproducible one-off downloader/search script for the first report.
- `artifacts/hype_1m_ema_crossover_live_search.json`: summary JSON for the first search.
- `artifacts/hype_1m_ema_crossover_live_search_ranking.csv`: top-ranked candidate table.
- `artifacts/hype_1m_ema_crossover_live_search_top_trades.csv`: trade path for the top search row.

## Data Lake

- Standard raw candles: `data/raw/ohlcv/exchange=binance/market_type=perp/timeframe=1m/date=*/symbol=hype_usdt_usdt.parquet`.
- Standard normalized candles: `data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=1m/date=*/symbol=hype_usdt_usdt.parquet`.
- Standard feature factors: `data/features/factor=*/version=hype_1m_ema_crossover_live_search_2026_06_25/exchange=binance/market_type=perp/symbol=hype_usdt_usdt/timeframe=1m/`.
- Current lake coverage after the `2026-06-26` refresh: `2026-03-25 00:00:00 UTC` to `2026-06-26 04:23:00 UTC`, `134,184` continuous `1m` bars.
- First search window: `2026-03-25 00:00:00 UTC` to `2026-06-25 08:46:00 UTC`, `133,007` continuous `1m` bars.
- The old `data/cache/hype_1m_ema_crossover_live_search/` parquet is retained only as the original downloader cache; new research should read the standard data lake paths above.

## Naming

Use names such as:

- `HYPE-1M-EMA-Crossover-TRAIL-144-1597`
- `HYPE-1M-EMA-Crossover-FIXED-233-1597`

Avoid names like bare `V1` or `EMA-X-V18` unless this family later gets a formal local version ledger.

## Storage Rules

- New reports stay under this directory, usually in `diagnostics/`, `ablations/`, or future `live-specs/`.
- One-off scripts for this research line stay in `scripts/`.
- Retained JSON/CSV/trade-path artifacts stay in `artifacts/`.
- Top-level `reports/` is only scratch cache and should not be cited as durable evidence.
