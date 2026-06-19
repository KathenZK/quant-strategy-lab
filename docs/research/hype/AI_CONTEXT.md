# HYPE AI Context

HYPE has multiple unrelated strategy families that reuse version numbers.

Do not read by bare version number. Read by family first.

## Family Map

| Family id | Directory | Core idea | Collision warning |
| --- | --- | --- | --- |
| `HYPE-CC` | `families/candle-count-reversal/` | 10-of-8 candle color reversal, ATR risk, early exit variants | `V35` here is not trend breakout `V35` |
| `HYPE-EMA-TB` | `families/ema-trend-breakout/` | EMA96/EMA384 trend breakout, ADX/volume/1h confirmation, live-realistic execution | `V35` here is not candle-count `V35` |

## Required Reading Order

1. `../STRATEGY_INDEX.md`
2. This file
3. The target family `README.md`
4. That family's `decision-log.md`
5. Only then open canonical specs or diagnostics.

## Hard Rules

- Never answer from `Vxx` alone.
- Always name the family id, for example `HYPE-CC-V21` or `HYPE-EMA-TB-V36`.
- Cursor Canvas files are supporting ledgers, not the only source of truth.
- Archived code under `archive/code/platform/` is historical unless the user asks for code archaeology.
- Active code under `src/strategy_lab/` is data/research infrastructure, not strategy truth.

## Cursor Assets

Cursor stores canvas files outside the repo at:

`/Users/ZK/.cursor/projects/Users-ZK-OpenCode-quant-strategy-lab/canvases/`

Use `cursor/canvas-catalog.md` and `cursor/canvas-groups/` as the managed repo index for those hidden files.
