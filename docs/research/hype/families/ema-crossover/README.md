# HYPE-EMA-X EMA Crossover

Family id: `HYPE-EMA-X`

This family covers the HYPE EMA golden/death cross strategy line. It is the long-running EMA cross research path that evolved through V14-era filters, exits, state-machine variants, late re-entry, and effective-cross quality analysis.

Do not merge this with `HYPE-EMA-TB`. Both use EMA concepts, but `HYPE-EMA-X` is the earlier EMA cross lineage, while `HYPE-EMA-TB` is the later trend-breakout / chase-long-chase-short lineage.

## Evidence Surface

The main evidence is currently in archived scripts and Cursor Canvas:

- `archive/scripts/research/research_hype_ema_cross_strategy.py`: base EMA cross research.
- `archive/scripts/research/compare_hype_ema_v2_v4.py`: early EMA version comparison.
- `archive/scripts/research/research_hype_ema_regime_hold_v5.py`: V5 regime-hold line.
- `archive/scripts/research/research_hype_ema_volume_exhaustion_v7.py`: V7 volume exhaustion.
- `archive/scripts/research/research_hype_ema_volume_overlay_v8.py`: V8 volume overlay.
- `archive/scripts/research/research_hype_ema_htf_rsi_exit_v9.py`: V9 higher-timeframe RSI exit.
- `archive/scripts/research/research_hype_ema_oscillator_top_exit_v10.py`: V10 oscillator top exit.
- `archive/scripts/research/research_hype_trade_path_diagnostics_v11.py`: V11 trade-path diagnostics.
- `archive/scripts/research/research_hype_state_machine_v12.py`: V12 state-machine line.
- `archive/scripts/research/research_hype_v13_late_reentry.py`: V13 late re-entry line.
- `archive/scripts/research/research_hype_v14_main_backfill.py`: V14 main backfill.
- `archive/scripts/research/research_hype_v14_ablation.py`: V14 ablation.
- `archive/scripts/research/research_hype_v14_atr_dynamic_entry.py`: V14 ATR dynamic entry.
- `archive/scripts/research/research_hype_v14_slow_trend_entry.py`: V14 slow trend entry probe.
- `archive/scripts/research/research_hype_v15_effective_cross.py`: post-V14 effective-cross quality probe.
- `archive/scripts/research/research_hype_v16_indicator_expansion.py`: post-V14 RSI/KDJ-style late supplemental entry probe.
- `archive/scripts/research/research_hype_v17_trend_state_search.py`: broad trend-state search across momentum, volatility, volume, structure, and oscillator indicators.
- `docs/research/hype/families/ema-crossover/v16-v17-trend-state-search.md`: V16/V17 result note and next research direction.
- `/Users/ZK/.cursor/projects/Users-ZK-OpenCode-quant-strategy-lab/canvases/hype-ema-crossover-evolution.canvas.tsx`: Cursor main ledger for promoted HYPE-EMA-X versions.
- `docs/research/hype/families/ema-crossover/v15-v16-promoted-strategy-specs.md`: full Chinese rule/parameter spec for promoted V15 and V16.

## Cursor

- `hype-ema-crossover-evolution.canvas.tsx`

This Cursor canvas is the main ledger for `HYPE-EMA-X` promoted versions. The repo docs mirror and explain the rules, but do not replace the canvas ledger.

## Naming

Use names such as `HYPE-EMA-X-V6`, `HYPE-EMA-X-V10`, `HYPE-EMA-X-V14`, `HYPE-EMA-X-V15`, or `HYPE-EMA-X-V16`.

Never call this only `EMA V14` or merge it into `HYPE-EMA-TB-V35`.

## Promoted Ledger Versions

- `HYPE-EMA-X-V15`: high-win-rate / low-drawdown candidate from V17 search.
- `HYPE-EMA-X-V16`: high-return candidate from V17 search.

The search did not find a candidate that satisfies `50x return`, `<20% max drawdown`, and `>80% win rate` simultaneously on the current Binance HYPE 15m slice. V15 and V16 are therefore promoted research candidates, not live-approved production strategies.
