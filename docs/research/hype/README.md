# HYPE Research Index

Read `AI_CONTEXT.md` before opening any strategy document.

HYPE has multiple strategy families with overlapping version numbers. The main repository rule is simple: do not cite `V35`, `V36`, or any other version without a family id.

## Strategy Families

| Family id | Directory | Meaning |
| --- | --- | --- |
| `HYPE-CC` | `families/candle-count-reversal/` | 10-of-8 candle color reversal with ATR risk controls and early-exit variants |
| `HYPE-EMA-X` | `families/ema-crossover/` | EMA golden/death cross strategy line, iterated through V14-era regime, volume, oscillator, state-machine, and late-entry variants |
| `HYPE-EMA-TB` | `families/ema-trend-breakout/` | Later EMA trend breakout / chase-long-chase-short line with ADX, volume, 1h confirmation, and cross-exchange execution variants |

## Core Cursor Ledgers

Cursor canvas files still live in Cursor's project-private directory. The repo-managed indexes are:

- `cursor/canvas-catalog.md`: full canvas filename catalog.
- `cursor/canvas-groups/README.md`: canvas groups by research theme.
- `cursor/agent-artifacts.md`: transcript/tool artifact management rules.

Core canvas files:

- [HYPE Trend Strategy Research](/Users/ZK/.cursor/projects/Users-ZK-OpenCode-quant-strategy-lab/canvases/hype-trend-strategy-research.canvas.tsx)
- [HYPE 15m Strategy Milestone Comparison](/Users/ZK/.cursor/projects/Users-ZK-OpenCode-quant-strategy-lab/canvases/hype-strategy-milestone-comparison.canvas.tsx)

## Reading Rules

1. Start with `AI_CONTEXT.md`.
2. Choose a family.
3. Read that family's `README.md` and `decision-log.md`.
4. Only then open specs, diagnostics, reports indexes, or Canvas files.
