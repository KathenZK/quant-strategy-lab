# HYPE-EMA-X EMA Crossover

Family id: `HYPE-EMA-X`

This family covers the HYPE EMA golden/death cross strategy line. It is the long-running EMA cross research path that evolved through V14-era filters, exits, state-machine variants, late re-entry, and effective-cross quality analysis.

Do not merge this with `HYPE-EMA-TB`. Both use EMA concepts, but `HYPE-EMA-X` is the earlier EMA cross lineage, while `HYPE-EMA-TB` is the later trend-breakout / chase-long-chase-short lineage.

## Core Ledger

- `hype-ema-x-core-ledger.md`: migrated Markdown ledger for HYPE-EMA-X version evolution, promoted V15/V16/V17/V17.1 candidates, ablations, and implementation status.
- `legacy-canvas/`: migrated historical Canvas reports for HYPE-EMA-X experiments and diagnostics.

## Evidence Surface

The main evidence is currently in repo Markdown and archived scripts:

- `research/hype/families/ema-crossover/scripts/research_hype_ema_cross_strategy.py`: base EMA cross research.
- `research/hype/families/ema-crossover/scripts/compare_hype_ema_v2_v4.py`: early EMA version comparison.
- `research/hype/families/ema-crossover/scripts/research_hype_ema_regime_hold_v5.py`: V5 regime-hold line.
- `research/hype/families/ema-crossover/scripts/research_hype_ema_volume_exhaustion_v7.py`: V7 volume exhaustion.
- `research/hype/families/ema-crossover/scripts/research_hype_ema_volume_overlay_v8.py`: V8 volume overlay.
- `research/hype/families/ema-crossover/scripts/research_hype_ema_htf_rsi_exit_v9.py`: V9 higher-timeframe RSI exit.
- `research/hype/families/ema-crossover/scripts/research_hype_ema_oscillator_top_exit_v10.py`: V10 oscillator top exit.
- `research/hype/families/ema-crossover/scripts/research_hype_trade_path_diagnostics_v11.py`: V11 trade-path diagnostics.
- `research/hype/families/ema-crossover/scripts/research_hype_state_machine_v12.py`: V12 state-machine line.
- `research/hype/families/ema-crossover/scripts/research_hype_v13_late_reentry.py`: V13 late re-entry line.
- `research/hype/families/ema-crossover/scripts/research_hype_v14_main_backfill.py`: V14 main backfill.
- `research/hype/families/ema-crossover/scripts/research_hype_v14_ablation.py`: V14 ablation.
- `research/hype/families/ema-crossover/scripts/research_hype_v14_atr_dynamic_entry.py`: V14 ATR dynamic entry.
- `research/hype/families/ema-crossover/scripts/research_hype_v14_slow_trend_entry.py`: V14 slow trend entry probe.
- `research/hype/families/ema-crossover/scripts/research_hype_v15_effective_cross.py`: post-V14 effective-cross quality probe.
- `research/hype/families/ema-crossover/scripts/research_hype_v16_indicator_expansion.py`: post-V14 RSI/KDJ-style late supplemental entry probe.
- `research/hype/families/ema-crossover/scripts/research_hype_v17_trend_state_search.py`: broad trend-state search across momentum, volatility, volume, structure, and oscillator indicators.
- `research/hype/families/ema-crossover/scripts/research_hype_v17_hybrid_ablation.py`: V17 V15/V16 hybrid full parameter ablation.
- `research/hype/families/ema-crossover/v16-v17-trend-state-search.md`: V16/V17 result note and next research direction.
- `research/hype/families/ema-crossover/v17-hybrid-ablation.md`: formal V17 hybrid definition, window metrics, and parameter ablation conclusions.
- `research/hype/families/ema-crossover/diagnostics/hype-ema-x-1m-binance-live-search-2026-06-25.md`: Binance HYPEUSDT `1m` live-executable EMA cross search; diagnostic / paper-live candidate only, not a live-approved promotion.
- `research/hype/families/ema-crossover/hype-ema-x-core-ledger.md`: main Markdown ledger for promoted HYPE-EMA-X versions.
- `research/hype/families/ema-crossover/v15-v16-promoted-strategy-specs.md`: full Chinese rule/parameter spec for promoted V15 and V16.

## Archived Cursor Source

The former Cursor canvas source for this family has been migrated. The canonical durable ledger is now `hype-ema-x-core-ledger.md`; migration evidence is archived under `../../../../../archive/docs/hype-cursor-artifacts/`.

## Naming

Use names such as `HYPE-EMA-X-V6`, `HYPE-EMA-X-V10`, `HYPE-EMA-X-V14`, `HYPE-EMA-X-V15`, `HYPE-EMA-X-V16`, `HYPE-EMA-X-V17`, or `HYPE-EMA-X-V17.1`.

Never call this only `EMA V14` or merge it into `HYPE-EMA-TB-V35`.

## Promoted Ledger Versions

- `HYPE-EMA-X-V15`: high-win-rate / low-drawdown candidate from V17 search.
- `HYPE-EMA-X-V16`: high-return candidate from V17 search.
- `HYPE-EMA-X-V17`: V15/V16 hybrid candidate. It keeps V15 high-quality signals and admits only V16 low-score satellite signals with `trend_score` 5-6, `dir_dist_ema96 <= 0.04`, and `atr_ratio96_672 <= 1.1`.
- `HYPE-EMA-X-V17.1`: V17 sizing-enhanced candidate. It keeps V17 signals unchanged and sets `hq_scale = 1.1`, `lq_scale = 1.0`.

The search and V17 ablation did not find a candidate that satisfies `50x return`, `<20% max drawdown`, and `>80% win rate` simultaneously on the current Binance HYPE 15m slice. V15, V16, V17, and V17.1 are therefore promoted research candidates, not live-approved production strategies.

## Local Report Artifacts

Retained report artifacts live under `artifacts/`. Use top-level `reports/` only for scratch runs; cite `artifacts/` when a JSON, CSV, or HTML file supports a durable report.

Key historical report filename families:

- `hype_ema_cross_research.json`
- `hype_ema_v2_v4_compare.json`
- `hype_ema_v5_data_lake_compare.json`
- `hype_ema_v6_*`
- `hype_ema_volume_exhaustion_v7*`
- `hype_ema_volume_overlay_v8*`
- `hype_ema_htf_rsi_exit_v9*`
- `hype_ema_oscillator_top_exit_v10*`
- `hype_trade_path_diagnostics_v11*`
- `hype_state_machine_v12*`
- `hype_v13_*`
- `hype_v14_*`
- `hype_v15_effective_cross*`
- `hype_v16_indicator_expansion*`
- `hype_v17_trend_state_search*`
- `hype_v17_hybrid_ablation*`

Migrated legacy Canvas reports live under `legacy-canvas/`.

Do not use these report names to infer `HYPE-EMA-TB`; this is the `HYPE-EMA-X` lineage unless a document explicitly says otherwise.

`hype_v15_*` and `hype_v16_*` report filenames are historical research batch names. The promoted main-ledger versions `HYPE-EMA-X-V15`, `HYPE-EMA-X-V16`, `HYPE-EMA-X-V17`, and `HYPE-EMA-X-V17.1` are recorded in `hype-ema-x-core-ledger.md`; supporting repo mirrors are `v15-v16-promoted-strategy-specs.md` and `v17-hybrid-ablation.md`.

`hype_v17_hybrid_ablation*` report files are generated by `research/hype/families/ema-crossover/scripts/research_hype_v17_hybrid_ablation.py` and cover the official V17 baseline plus 143 single-parameter/single-module ablation candidates.
