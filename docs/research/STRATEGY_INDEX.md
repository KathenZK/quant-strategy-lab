# Strategy Index

This repository uses strategy-family identifiers to prevent version-number collisions.

## HYPE

Read `docs/research/hype/AI_CONTEXT.md` before reading any HYPE strategy document.

| Family id | Directory | Meaning | Current role |
| --- | --- | --- | --- |
| `HYPE-CC` | `hype/families/candle-count-reversal/` | 10-of-8 candle color reversal with ATR risk controls and early exits | Archived/canonical research specs |
| `HYPE-EMA-TB` | `hype/families/ema-trend-breakout/` | 15m EMA96/384 trend breakout with ADX, volume, 1h confirmation, and cross-exchange execution variants | Archived/canonical research specs |

## Cross-Asset And Transfer Research

Cross-asset research is not a HYPE strategy family unless a document explicitly says it is a HYPE family variant.

- `docs/research/mu-v35-session-aware-ledger.md`
- Cursor canvas groups under `docs/research/hype/cursor/canvas-groups/cross-asset.md`

## Rules

- Never cite a bare `V35` without a family id.
- Prefer ids like `HYPE-CC-V35` and `HYPE-EMA-TB-V35`.
- If a document path contains `families/candle-count-reversal`, use `HYPE-CC`.
- If a document path contains `families/ema-trend-breakout`, use `HYPE-EMA-TB`.
- If a document lives under `archive/`, treat it as historical evidence, not the current entrypoint.
