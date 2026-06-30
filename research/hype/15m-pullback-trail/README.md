# HYPE-15M-Pullback-Trail

Family id: `HYPE-15M-Pullback-Trail`

This family is a separate Binance HYPEUSDT `15m` research line for testing whether the `HYPE-5M-Pullback-Trail` V3.3 pullback/trailing idea improves when migrated from `5m` to `15m`.

It is independent from:

- `HYPE-5M-Pullback-Trail`: the original `5m` family where V3.3 was defined.
- `HYPE-15M-Multi-Indicator-Intraday`: broad multi-indicator search on `15m`.
- `HYPE-EMA-Crossover`, `HYPE-EMA-Trend-Breakout`, and `HYPE-Candle-Count-Reversal`.

## Canonical Entrypoints

- `diagnostics/hype-15m-pullback-trail-v3-3-migration-2026-06-30.md`: first 15m migration diagnostic for the V3.3 mechanism.
- `decision-log.md`: durable decision notes for this family.

## Current Status

Diagnostic only. No paper-live, dry-run, handoff, or live candidate has been promoted from this family.

## Scripts

- `scripts/research_hype_15m_pbtr_v33_migration.py`: resamples local Binance HYPE `5m` data into strict closed `15m` bars, reproduces the V3.3 pullback/trailing logic, compares legacy stop-price fills against live-realistic trailing execution, and runs a small 15m neighborhood grid.

## Artifacts

- `artifacts/hype_15m_pbtr_v33_migration_2026-06-30.json`
- `artifacts/hype_15m_pbtr_v33_migration_summary_2026-06-30.csv`
- `artifacts/hype_15m_pbtr_v33_migration_slices_2026-06-30.csv`
- `artifacts/hype_15m_pbtr_v33_migration_trades_2026-06-30.csv`
- `artifacts/hype_15m_pbtr_v33_migration_diag_2026-06-30.csv`

## Naming Notes

Do not cite a bare `V3.3` in this directory. Use `HYPE-15M-Pullback-Trail V3.3 migration diagnostic` or explicitly mention that it is a 15m transplant of `HYPE-5M-Pullback-Trail-V3.3`.
