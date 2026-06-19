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

## Cursor

- `hype-ema-crossover-evolution.canvas.tsx`

## Naming

Use names such as `HYPE-EMA-X-V6`, `HYPE-EMA-X-V10`, `HYPE-EMA-X-V14`, or `HYPE-EMA-X-effective-cross`.

Never call this only `EMA V14` or merge it into `HYPE-EMA-TB-V35`.
