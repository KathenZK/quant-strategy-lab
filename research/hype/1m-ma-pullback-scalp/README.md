# HYPE-1M-MA-Pullback-Scalp

Family id: `HYPE-1M-MA-Pullback-Scalp`

Historical alias: none.

This family covers Binance HYPEUSDT perpetual `1m` moving-average pullback scalp research. It translates the common discretionary scalp pattern into executable rules:

- slow moving average defines the main trend;
- fast moving average defines the current wave / pullback line;
- market structure requires higher highs and higher lows for longs, or lower lows and lower highs for shorts;
- entry happens only after a closed-bar pullback reclaim/rejection, then fills at the next bar open;
- the position immediately has fixed TP/SL protection and a hard max-hold timeout.

It is independent from:

- `HYPE-1M-EMA-Crossover`: crossover-event research, not pullback-end structure scalp.
- `HYPE-5M-Micro-Scalp`: `5m` broad micro-profit search, not `1m` two-MA pullback structure.
- `HYPE-5M-Pullback-Trail`: `5m` pullback/resume with ATR trailing-stop exits.

## Current Scope

- Data: Binance HYPEUSDT perpetual `1m` normalized OHLCV under the repository data lake, with raw OHLCV alignment checks.
- Execution model: closed-bar signal, next-bar open entry, immediate fixed TP/SL bracket, stop-first same-bar ordering, next-open timeout.
- Cost model: conservative taker-style cost constants embedded in the script and reported with each run.
- Current status: first executable search completed; no paper-live or live candidate.

## Canonical Entrypoints

- `decision-log.md`: family decision history.
- `scripts/research_hype_1m_ma_pullback_scalp.py`: reproducible one-off search script.
- `diagnostics/hype-1m-ma-pullback-scalp-search-2026-06-26.md`: first executable search report.
- `diagnostics/`: generated search reports.
- `artifacts/`: generated JSON/CSV evidence.

## Current Finding

The first 2026-06-26 executable search tested `6,740` configs across:

- `reclaim`, `platform_break`, and `engulf_reclaim` pullback-end triggers;
- fast/slow EMA pairs;
- HH/HL or LL/LH structure windows;
- platform windows, MA slope filters, ATR/RVOL/ADX filters;
- fixed TP/SL brackets and hard max-hold exits.

Data passed the required local quality checks: `134,184` continuous `1m` bars from `2026-03-25 00:00:00 UTC` to `2026-06-26 04:23:00 UTC`, no missing bars, no duplicates, no OHLC/VWAP/volume hard violations, and raw/normalized OHLCV alignment mismatches all `0`.

Result: `0` configs passed the paper candidate gate. At `>=60` full-sample trades, `0` configs were profitable. At `>=1` trade/day, the highest full-sample annualized multiple was only `0.57x`, and frequency pressure worsened the result.

The current conclusion is no-go for this exact two-MA pullback scalp shape under the executable model and cost model used here.

## Live Boundary

No row from this family may be called live-ready until it passes all of:

- data quality and raw/normalized alignment checks;
- out-of-sample and recent-window profitability checks;
- per-trade path audit for bracket validity;
- parameter-neighborhood robustness;
- paper/live-dry-run reconciliation;
- restart/idempotency and exchange-order maintenance audit.

The initial search did not identify a paper-audit candidate.
