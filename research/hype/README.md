# HYPE Research Index

Read `AI_CONTEXT.md` before opening any strategy document.

HYPE has multiple strategy families with overlapping version numbers. The main repository rule is simple: do not cite `V35`, `V36`, or any other version without a family id.

## Strategy Families

| Family id | Directory | Meaning |
| --- | --- | --- |
| `HYPE-CC` | `candle-count-reversal/` | 10-of-8 candle color reversal with ATR risk controls and early-exit variants |
| `HYPE-EMA-X` | `ema-crossover/` | EMA golden/death cross strategy line, iterated through V14-era regime, volume, oscillator, state-machine, and late-entry variants |
| `HYPE-EMA-TB` | `ema-trend-breakout/` | Later EMA trend breakout / chase-long-chase-short line with ADX, volume, 1h confirmation, and cross-exchange execution variants |
| `HYPE-5M-PBTR` | `5m-pullback-trail/` | Binance HYPE `5m` pullback/resume entries with ATR trailing-stop exits |

## Core Markdown Ledgers

- `ema-crossover/hype-ema-x-core-ledger.md`: HYPE-EMA-X promoted-candidate and version-evolution ledger.
- `ema-trend-breakout/hype-ema-tb-core-ledger.md`: HYPE-EMA-TB trend strategy research ledger.
- `candle-count-reversal/hype-cc-15m-milestone-comparison.md`: HYPE-CC 15m milestone comparison ledger.
- `5m-pullback-trail/hype-5m-pullback-trail-core-ledger.md`: HYPE-5M-PBTR active `5m` pullback-trail ledger.

## Transfer Notes

- `transfer/`: legacy cross-asset checks that apply HYPE kernels to BTC, XMR, XAU, TradFi perpetuals, or broad CMC universes. This directory is currently retained for review and should not be treated as a fourth HYPE strategy family.
- New promoted transfer research should get an explicit direction or asset family, as `MU-HYPE-XFER` does under `../mu/`.

## Archived Cursor Indexes

Historical Cursor Canvas and agent artifact indexes have been archived under `../../archive/docs/hype-cursor-artifacts/`. They are migration evidence, not active research entrypoints.

## Reading Rules

1. Start with `AI_CONTEXT.md`.
2. Choose a family.
3. Read that family's `README.md` and `decision-log.md`.
4. Only then open specs, diagnostics, or reports indexes.

New HYPE research reports and durable conclusions must be saved as Markdown under the relevant strategy directory. Canvas may only be used as a temporary visualization surface when explicitly requested.
