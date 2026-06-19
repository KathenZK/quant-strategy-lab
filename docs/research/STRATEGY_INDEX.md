# Strategy Index

This repository uses strategy-family identifiers to prevent version-number collisions.

## HYPE

Read `docs/research/hype/AI_CONTEXT.md` before reading any HYPE strategy document.

| Family id | Directory | Meaning | Current role |
| --- | --- | --- | --- |
| `HYPE-CC` | `hype/families/candle-count-reversal/` | 10-of-8 candle color reversal with ATR risk controls and early exits | Archived/canonical research specs |
| `HYPE-EMA-X` | `hype/families/ema-crossover/` | EMA golden/death cross family, evolved through V14-era regime, volume, oscillator, late-entry, and state-machine variants | Core historical research line |
| `HYPE-EMA-TB` | `hype/families/ema-trend-breakout/` | Later 15m EMA96/384 trend breakout / chase-long-chase-short family with ADX, volume, 1h confirmation, and cross-exchange execution variants | Archived/canonical research specs |

## Cross-Asset And Transfer Research

Cross-asset research is not a HYPE strategy family unless a document explicitly says it is a HYPE family variant.

- `MU-HYPE-XFER`: `docs/research/mu/README.md` and `docs/research/mu-v35-session-aware-ledger.md`
- Cursor canvas groups under `docs/research/hype/cursor/canvas-groups/cross-asset.md`

## Core Research Directions

The core research directions are:

1. `HYPE-CC`: HYPE candle-count technical reversal.
2. `HYPE-EMA-X`: HYPE EMA golden/death cross family, iterated through V14-era research.
3. `HYPE-EMA-TB`: HYPE EMA trend breakout / chase-long-chase-short family.
4. `MU-HYPE-XFER`: MU transfer research from HYPE trend kernels.

## Legacy / Shallow Research

These directions were explored but should not be treated as core research lines:

- `crowding_reversal`: archived under `archive/research/legacy-strategies/`.
- early platform examples such as spot CTA, CTA grid, generic MA crossover, momentum rotation, Donchian variants.

## Rules

- Never cite a bare `V35` without a family id.
- Prefer ids like `HYPE-CC-V35`, `HYPE-EMA-X-V14`, and `HYPE-EMA-TB-V35`.
- If a document path contains `families/candle-count-reversal`, use `HYPE-CC`.
- If a document path contains `families/ema-crossover`, use `HYPE-EMA-X`.
- If a document path contains `families/ema-trend-breakout`, use `HYPE-EMA-TB`.
- If a document lives under `archive/`, treat it as historical evidence, not the current entrypoint.
