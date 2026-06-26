# HYPE-5M-MA-Pullback-Scalp Decision Log

Family id: `HYPE-5M-MA-Pullback-Scalp`

## Current Boundary

- This is a separate Binance HYPEUSDT perpetual `5m` family for moving-average pullback scalp research.
- It is not a version of `HYPE-5M-Micro-Scalp`, because the entry mechanism is specifically slow/fast MA pullback-end structure confirmation rather than a broad indicator search.
- It is not a version of `HYPE-5M-Pullback-Trail`, because exits are fixed TP/SL brackets rather than ATR trailing-stop state machines.
- Research conclusions must be stored under this directory, with durable JSON/CSV evidence in `artifacts/`.
- No strategy from this family may be called live-ready until order timing, bracket maintenance, restart behavior, cost sensitivity, and paper/live-dry-run reconciliation are audited.

## Research Batches

- Initial scaffold: `scripts/research_hype_5m_ma_pullback_scalp.py` implements the two-MA pullback structure pattern with closed-bar signals, next-open entries, fixed TP/SL brackets, stop-first same-bar ordering, and max-hold timeout.
- `diagnostics/hype-5m-ma-pullback-scalp-search-2026-06-26.md`: first executable search. Tested `6,740` configs across `reclaim`, `platform_break`, and `engulf_reclaim` triggers on Binance HYPEUSDT perpetual `5m`; data quality passed with `112,822` continuous bars, raw/normalized OHLCV alignment mismatch counts all `0`, and no missing/duplicate/OHLCV hard violations. Result: `2` paper candidate passes. Best sample-size candidate is `HYPE_5M_MA_PBS_R03072`: `reclaim`, both sides, EMA `21/144`, TP/SL/hold `180/160/45`, `138` trades, annualized `1.13x`, PF `1.158`, win `52.90%`, maxDD `-12.64%`, recent 30d `0.90%`.
- `diagnostics/hype-5m-ma-pullback-scalp-robustness-2026-06-26.md`: local parameter-neighborhood robustness around the two paper candidate rows. Tested `840` neighborhood configs; `14` passed robust gate and `9` passed robust + monthly gate. Top-scoring monthly-pass neighbor is `HYPE_5M_MA_PBS_R03072__nb_0370`: `reclaim`, both sides, EMA `13/89`, TP/SL/hold `260/160/45`, `76` trades, annualized `1.12x`, PF `1.233`, win `50.00%`, maxDD `-13.59%`, recent 30d `6.39%`.

## Current Decision

- This family has paper-audit candidates, but no live-ready strategy.
- Prefer `HYPE_5M_MA_PBS_R03072__base` as the first paper-audit starting point because it has the higher sample count (`138` trades) and survived neighborhood testing; use `HYPE_5M_MA_PBS_R03072__nb_0370` as the higher-scoring neighbor for comparison.
- Do not call this high-frequency scalp: frequency is only about `0.15-0.35` trades/day for the surviving candidates.
- Do not promote without per-trade path review, order-maintenance audit, restart/idempotency checks, and paper/live-dry-run reconciliation.
