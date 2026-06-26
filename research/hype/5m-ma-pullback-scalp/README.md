# HYPE-5M-MA-Pullback-Scalp

Family id: `HYPE-5M-MA-Pullback-Scalp`

Historical alias: none.

This family covers Binance HYPEUSDT perpetual `5m` moving-average pullback scalp research. It tests the two-moving-average discretionary scalp pattern on `5m` bars:

- slow moving average defines the main trend;
- fast moving average defines the active wave / pullback line;
- HH/HL confirms long structure and LL/LH confirms short structure;
- entry happens only after a closed-bar pullback-end trigger, then fills at the next bar open;
- the position immediately has fixed TP/SL protection and a hard max-hold timeout.

It is independent from:

- `HYPE-5M-Micro-Scalp`: broad indicator micro-scalp search, not this specific two-MA pullback structure.
- `HYPE-5M-Pullback-Trail`: pullback/resume entries with ATR trailing-stop exits.
- `HYPE-1M-MA-Pullback-Scalp`: same mechanism family concept but different timeframe, frequency, and cost sensitivity.

## Current Scope

- Data: Binance HYPEUSDT perpetual `5m` normalized OHLCV under the repository data lake, with raw OHLCV alignment checks.
- Execution model: closed-bar signal, next-bar open entry, immediate fixed TP/SL bracket, stop-first same-bar ordering, next-open timeout.
- Cost model: observed Binance live cost constants copied into the search script and reported with each run.
- Current status: first executable search and parameter-neighborhood robustness completed; paper-audit candidates found, not live-approved.

## Canonical Entrypoints

- `decision-log.md`: family decision history.
- `scripts/research_hype_5m_ma_pullback_scalp.py`: reproducible one-off search script.
- `scripts/research_hype_5m_ma_pullback_scalp_robustness.py`: local parameter-neighborhood robustness script.
- `diagnostics/hype-5m-ma-pullback-scalp-search-2026-06-26.md`: first executable search report.
- `diagnostics/hype-5m-ma-pullback-scalp-robustness-2026-06-26.md`: parameter-neighborhood robustness report.
- `diagnostics/`: generated search reports.
- `artifacts/`: generated JSON/CSV evidence.

## Current Finding

The first 2026-06-26 executable search tested `6,740` configs across `reclaim`, `platform_break`, and `engulf_reclaim` pullback-end triggers.

Data passed local quality checks: `112,822` continuous `5m` bars from `2025-05-30 10:30:00 UTC` to `2026-06-26 04:15:00 UTC`, no missing bars, no duplicates, no OHLC/VWAP/volume hard violations, and raw/normalized OHLCV alignment mismatches all `0`.

The search found `2` paper candidate rows. The more usable starting point is:

- `HYPE_5M_MA_PBS_R03072__base`: `reclaim`, both sides, EMA `21/144`, TP/SL/hold `180/160/45`, `138` trades, `0.35` trades/day, annualized `1.13x`, win `52.90%`, PF `1.158`, average trade `10.89 bps`, maxDD `-12.64%`, VAL PF `1.134`, FWD PF `1.768`, recent 30d `0.90%`, `4` negative months.

Neighborhood robustness tested `840` configs around the two paper candidates. `14` passed the robust gate and `9` also passed the monthly gate. The top-scoring monthly-pass neighbor is:

- `HYPE_5M_MA_PBS_R03072__nb_0370`: `reclaim`, both sides, EMA `13/89`, TP/SL/hold `260/160/45`, `76` trades, `0.19` trades/day, annualized `1.12x`, win `50.00%`, PF `1.233`, average trade `17.81 bps`, maxDD `-13.59%`, VAL PF `2.230`, FWD PF `4.285`, recent 30d `6.39%`, `4` negative months.

Both remain paper-audit candidates only. Frequency is low for a classic high-frequency scalp, and live readiness still requires per-trade path audit, order-maintenance audit, restart/idempotency checks, and paper/live-dry-run reconciliation.

## Live Boundary

No row from this family may be called live-ready until it passes all of:

- data quality and raw/normalized alignment checks;
- out-of-sample and recent-window profitability checks;
- per-trade path audit for bracket validity;
- parameter-neighborhood robustness;
- paper/live-dry-run reconciliation;
- restart/idempotency and exchange-order maintenance audit.

The current search identified paper-audit candidates only.
