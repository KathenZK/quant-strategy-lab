# Cursor Canvas Migration Plan

This repository now treats Markdown under `research/` as the durable research surface. Cursor Canvas files are legacy/private assets and should be migrated into repo-tracked Markdown when their content is still useful.

## Goals

1. Preserve research conclusions in files that are versioned with the repository.
2. Keep strategy-family identity explicit, especially for HYPE versions that reuse bare numbers such as `V13`, `V21`, `V35`, and `V36`.
3. Avoid new durable research reports in Cursor-private directories.

## Source Location

Legacy Canvas files currently live outside the repo:

`/Users/ZK/.cursor/projects/Users-ZK-OpenCode-quant-strategy-lab/canvases/`

The former repo indexes are now archived at:

- `archive/docs/hype-cursor-artifacts/canvas-catalog.md`
- `archive/docs/hype-cursor-artifacts/canvas-groups/`

Treat those indexes as migration inventories, not canonical research entrypoints.

## Target Directories

Use these targets when converting Canvas reports to Markdown:

| Canvas group | Markdown target |
| --- | --- |
| HYPE EMA golden/death cross | `research/hype/ema-crossover/` |
| HYPE EMA trend breakout | `research/hype/ema-trend-breakout/` |
| HYPE candle-count reversal | `research/hype/candle-count-reversal/` |
| MU transfer research | `research/mu/` |
| Cross-asset HYPE transfer checks | `research/hype/transfer/` or the relevant promoted asset family if one exists |
| External or abandoned strategy research | `archive/research/legacy-strategies/` |
| Platform or workflow experiments | `archive/research/platform-experiments/` |

When a Canvas mixes multiple families, split it into separate Markdown files rather than preserving the Canvas boundary.

## Conversion Priority

1. Core ledgers and promoted candidates:
   - `hype-ema-crossover-evolution.canvas.tsx` -> `hype/ema-crossover/hype-ema-x-core-ledger.md`
   - `hype-trend-strategy-research.canvas.tsx` -> `hype/ema-trend-breakout/hype-ema-tb-core-ledger.md`
   - `hype-strategy-milestone-comparison.canvas.tsx` -> `hype/candle-count-reversal/hype-cc-15m-milestone-comparison.md`
2. Family decision material that affects canonical specs or live candidates:
   - migrated under each family `legacy-canvas/` directory.
3. Diagnostics, ablations, and robustness checks referenced by existing family `README.md` files:
   - migrated under each family `legacy-canvas/` directory.
4. Cross-asset transfer research:
   - migrated under `hype/transfer/legacy-canvas/` and `mu/legacy-canvas/`.
5. Abandoned platform or external-strategy experiments:
   - migrated under `archive/research/legacy-strategies/legacy-canvas/` or `archive/research/platform-experiments/legacy-canvas/`.

The full migration mapping is recorded in `legacy-canvas-migration-manifest.md`.

## Conversion Rules

- Convert rendered content, not TSX source. `H1/H2/H3` become Markdown headings, `Text` becomes paragraphs, `Callout` becomes a blockquote with a bold title, and `Table` becomes a Markdown table.
- Write generated research reports in Chinese by default unless the user explicitly requests another language.
- Preserve original Canvas filename in a short source note near the top of each migrated file.
- Do not cite bare version numbers in migrated filenames or headings when a family id is known. Prefer forms such as `HYPE-EMA-X-V17`, `HYPE-EMA-TB-V35`, and `HYPE-CC-V21`.
- If the Canvas contains charts, preserve the underlying chart data as a table and add a short note that the original rendering was visual.
- After migrating a report, update the relevant family `README.md` or `decision-log.md`.
- Do not delete legacy Canvas files until the Markdown migration has been reviewed.

## Automation Boundary

Most existing Canvas files are TSX documents built from arrays plus Cursor UI components, so an automated converter can produce a first Markdown draft. Manual review is still required for:

- charts and derived visual summaries,
- Canvas files with custom React logic,
- reports whose family identity is ambiguous,
- reports that should be split across multiple strategy families.

The safe workflow is: generate Markdown drafts, review the core ledgers first, update family indexes, then decide whether legacy Canvas files can be ignored or archived.
