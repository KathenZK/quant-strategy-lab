# HYPE Research Index

HYPE has multiple unrelated strategy families that reuse version numbers. Do not read by bare version number: choose the family first, and always prefer the complete family name with historical aliases only as secondary labels.

## Required Reading Order

1. `../README.md`
2. This file
3. The target family `README.md`
4. That family's `decision-log.md`
5. Only then open canonical specs, diagnostics, reports indexes, or retained artifacts.

For the newer Binance HYPE `5m` pullback + ATR trailing-stop research line, use:

1. `5m-pullback-trail/README.md`
2. `5m-pullback-trail/hype-5m-pullback-trail-core-ledger.md`
3. `5m-pullback-trail/ablations/hype-5m-pbtr-v6-full-parameter-ablation-2026-06-25.md`
4. `5m-pullback-trail/live-specs/hype-5m-pullback-trail-v2-live-spec.md`
5. `5m-pullback-trail/research-notes/hype-5m-pullback-trail-v2-combo-test-2026-06-23.md`

For `HYPE-EMA-Crossover-V15`, `HYPE-EMA-Crossover-V16`, `HYPE-EMA-Crossover-V17`, and `HYPE-EMA-Crossover-V17.1`, start from `15m-ema-crossover/hype-ema-x-core-ledger.md`, then use the repo rule mirrors `15m-ema-crossover/v15-v16-promoted-strategy-specs.md` and `15m-ema-crossover/v17-hybrid-ablation.md` when needed.

For the Binance HYPEUSDT `1m` EMA cross research line, use:

1. `1m-ema-crossover/README.md`
2. `1m-ema-crossover/decision-log.md`
3. `1m-ema-crossover/diagnostics/hype-1m-ema-crossover-live-search-2026-06-25.md`

## Strategy Families

| Full family name | Historical alias | Directory | Core idea | Collision warning |
| --- | --- | --- | --- | --- |
| `HYPE-Candle-Count-Reversal` | `HYPE-CC` | `15m-candle-count-reversal/` | 10-of-8 candle color reversal with ATR risk controls and early-exit variants | `V35` here is not trend breakout `V35` |
| `HYPE-EMA-Crossover` | `HYPE-EMA-X` | `15m-ema-crossover/` | EMA golden/death cross lineage, evolved through V14-era filters, exits, state machine, late re-entry, and effective-cross scoring | Do not merge this with later `HYPE-EMA-Trend-Breakout` just because both use EMA96/384 |
| `HYPE-15M-Multi-Indicator-Intraday` | `HYPE-15M-MII` | `15m-multi-indicator-intraday/` | Binance HYPEUSDT `15m` broad RSI/MACD/EMA/ADX/ATR/volume/structure intraday search | Do not relabel broad indicator-search results as existing EMA-X, EMA-TB, or candle-count versions |
| `HYPE-1M-EMA-Crossover` | `HYPE-1M-EMA-X` | `1m-ema-crossover/` | Binance HYPEUSDT `1m` EMA cross lineage with live-executable next-bar entries, fixed TP, and trailing TP | Do not merge this with `15m-ema-crossover` just because both are EMA cross research |
| `HYPE-EMA-Trend-Breakout` | `HYPE-EMA-TB` | `15m-ema-trend-breakout/` | Later EMA trend breakout / chase-long-chase-short lineage with ADX, volume, 1h confirmation, and cross-exchange execution variants | `V35` here is not candle-count `V35` or EMA-cross `V14` |
| `HYPE-5M-Pullback-Trail` | `HYPE-5M-PBTR` | `5m-pullback-trail/` | Binance HYPE `5m` pullback/resume entries with ATR trailing-stop exits | Local `V1/V2` here are not legacy 15m `HYPE-EMA-Trend-Breakout` V1/V2 |

## Core Markdown Ledgers

- `15m-ema-crossover/hype-ema-x-core-ledger.md`: `HYPE-EMA-Crossover` promoted-candidate and version-evolution ledger.
- `15m-multi-indicator-intraday/README.md`: `HYPE-15M-Multi-Indicator-Intraday` exploratory broad-indicator `15m` intraday search entry.
- `1m-ema-crossover/diagnostics/hype-1m-ema-crossover-live-search-2026-06-25.md`: `HYPE-1M-EMA-Crossover` first diagnostic / paper-live search report.
- `15m-ema-trend-breakout/hype-ema-tb-core-ledger.md`: `HYPE-EMA-Trend-Breakout` trend strategy research ledger.
- `15m-candle-count-reversal/hype-cc-15m-milestone-comparison.md`: `HYPE-Candle-Count-Reversal` 15m milestone comparison ledger.
- `5m-pullback-trail/hype-5m-pullback-trail-core-ledger.md`: `HYPE-5M-Pullback-Trail` active `5m` pullback-trail ledger.

## Hard Rules

- Never answer from `Vxx` alone.
- Always name the full family name, for example `HYPE-Candle-Count-Reversal-V21` or `HYPE-EMA-Trend-Breakout-V36`.
- Treat `HYPE-EMA-Crossover` and `HYPE-EMA-Trend-Breakout` as separate core directions, not one EMA bucket.
- Treat `HYPE-15M-Multi-Indicator-Intraday` as a broad indicator-search family, not a version of `HYPE-EMA-Crossover`, `HYPE-EMA-Trend-Breakout`, or `HYPE-Candle-Count-Reversal`.
- Treat `HYPE-1M-EMA-Crossover` as a separate `1m` family, not as a subdocument or version of `HYPE-EMA-Crossover`.
- Treat `HYPE-5M-Pullback-Trail` as a separate `5m` family, not as a subdocument of `HYPE-EMA-Trend-Breakout`.
- Durable HYPE research reports and ledgers must be repository-tracked Markdown under `research/`.
- Cursor Canvas files are legacy/private research assets, not canonical storage for new reports. If Canvas is used for temporary visualization, mirror the durable conclusion into the relevant Markdown file before finishing.
- Archived code under `archive/code/platform/` is limited to historical strategy source snapshots cited by research docs; it is not strategy truth or runnable platform code.
- Active code under `src/strategy_lab/` is data/research infrastructure, not strategy truth.

## Transfer Notes

- Legacy cross-asset checks that applied HYPE kernels to BTC, XMR, XAU, TradFi perpetuals, or broad CMC universes have been archived under `../../archive/research/hype-transfer/`.
- New promoted transfer research should get an explicit direction or asset family, as `MU-HYPE-Transfer` does under `../mu/`（historical alias: `MU-HYPE-XFER`）.

## Archived Cursor Assets

Legacy Cursor Canvas files are stored outside the repository in Cursor-managed project-private storage. The former repo-managed Canvas and agent artifact indexes have been archived under `../../archive/docs/hype-cursor-artifacts/`. Treat them as migration evidence, not active research entrypoints.
