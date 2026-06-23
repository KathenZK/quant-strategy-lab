# HYPE AI Context

HYPE has multiple unrelated strategy families that reuse version numbers.

Do not read by bare version number. Read by family first.

## Family Map

| Family id | Directory | Core idea | Collision warning |
| --- | --- | --- | --- |
| `HYPE-CC` | `families/candle-count-reversal/` | 10-of-8 candle color reversal, ATR risk, early exit variants | `V35` here is not trend breakout `V35` |
| `HYPE-EMA-X` | `families/ema-crossover/` | EMA golden/death cross lineage, evolved through V14-era filters, exits, state machine, late re-entry, and effective-cross scoring | Do not merge this with later `HYPE-EMA-TB` just because both use EMA96/384 |
| `HYPE-EMA-TB` | `families/ema-trend-breakout/` | Later EMA trend breakout / chase-long-chase-short lineage, ADX/volume/1h confirmation, live-realistic execution | `V35` here is not candle-count `V35` or EMA-cross `V14` |
| `HYPE-5M-PBTR` | `families/5m-pullback-trail/` | Binance HYPE `5m` pullback/resume entries with ATR trailing-stop exits | Local `V1/V2` here are not legacy 15m `HYPE-EMA-TB` V1/V2 |

## Required Reading Order

1. `../STRATEGY_INDEX.md`
2. This file
3. The target family `README.md`
4. That family's `decision-log.md`
5. Only then open canonical specs or diagnostics.

For the newer Binance HYPE `5m` pullback + ATR trailing-stop research line, use:

1. `families/5m-pullback-trail/README.md`
2. `families/5m-pullback-trail/hype-5m-pullback-trail-core-ledger.md`
3. `families/5m-pullback-trail/hype-5m-pullback-trail-v2-live-spec.md`
4. `families/5m-pullback-trail/hype-5m-pullback-trail-v2-combo-test-2026-06-23.md`

Its local `HYPE-5M-PBTR-V1/V2` version numbers are independent from the legacy 15m `HYPE-EMA-TB` V1/V2/V35 sequence.

For `HYPE-EMA-X-V15`, `HYPE-EMA-X-V16`, `HYPE-EMA-X-V17`, and `HYPE-EMA-X-V17.1`, the repository Markdown ledger is:

1. `families/ema-crossover/hype-ema-x-core-ledger.md`
2. Repo rule mirrors:
   - `families/ema-crossover/v15-v16-promoted-strategy-specs.md`
   - `families/ema-crossover/v17-hybrid-ablation.md`

Legacy Cursor source material was migrated into repository Markdown. Markdown under `docs/research/` is the durable entrypoint.

## Hard Rules

- Never answer from `Vxx` alone.
- Always name the family id, for example `HYPE-CC-V21` or `HYPE-EMA-TB-V36`.
- Treat `HYPE-EMA-X` and `HYPE-EMA-TB` as separate core directions, not one EMA bucket.
- Treat `HYPE-5M-PBTR` as a separate 5m family, not as a subdocument of `HYPE-EMA-TB`.
- Durable HYPE research reports and ledgers must be repository-tracked Markdown under `docs/research/`.
- Cursor Canvas files are legacy/private research assets, not canonical storage for new reports. If a Canvas is used for temporary visualization, mirror the durable conclusion into the relevant Markdown file before finishing.
- Archived code under `archive/code/platform/` is historical unless the user asks for code archaeology.
- Active code under `src/strategy_lab/` is data/research infrastructure, not strategy truth.

## Archived Cursor Assets

Legacy Cursor canvas files are stored outside the repository in Cursor-managed project-private storage. The former repo-managed Canvas and agent artifact indexes have been archived under `../../../archive/docs/hype-cursor-artifacts/`. Treat them as migration evidence, not active research entrypoints.
