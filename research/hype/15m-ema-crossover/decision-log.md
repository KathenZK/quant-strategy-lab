# HYPE-EMA-X Decision Log

This is the family-level reading path for HYPE EMA golden/death cross research.

## Current Boundary

- This is one of the four core research directions in this repository.
- It is preserved through repository Markdown ledgers and archived scripts rather than polished canonical specs.
- It should not be treated as a failed shallow attempt.
- It should not be collapsed into `HYPE-EMA-TB`.

## Version Notes

- `HYPE-EMA-X-V2/V4`: early EMA cross comparisons.
- `HYPE-EMA-X-V5`: regime-hold variant.
- `HYPE-EMA-X-V7`: volume exhaustion.
- `HYPE-EMA-X-V8`: volume overlay.
- `HYPE-EMA-X-V9`: higher-timeframe RSI exit.
- `HYPE-EMA-X-V10`: oscillator top exit.
- `HYPE-EMA-X-V11`: trade-path diagnostics.
- `HYPE-EMA-X-V12`: state-machine variants.
- `HYPE-EMA-X-V13`: late re-entry and missed-trend diagnostics.
- `HYPE-EMA-X-V14`: main late-entry/backfill/ablation checkpoint.
- `HYPE-EMA-X-V15`: promoted high-win-rate / low-drawdown candidate. Source search row: `V17_atr18_trend7_base_age384_d075_pnlm03_either2_stop8`. Metrics: `+2303.65% / -17.79% / 90.32% / 31 trades`.
- `HYPE-EMA-X-V16`: promoted high-return candidate. Source search row: `V17_atr18_base_age384_pnlm03_either2_stop8`. Metrics: `+3202.92% / -28.19% / 86.84% / 38 trades`.
- `HYPE-EMA-X-V17`: promoted V15/V16 hybrid candidate. Source row: `HYBRID_score5_dist04_atr11` / `HYPE_EMA_X_V17`. Metrics: `+2910.74% / -17.79% / 90.91% / 33 trades`.
- `HYPE-EMA-X-V17.1`: promoted V17 sizing-enhanced candidate. Source row: `HYPE_EMA_X_V17__hq_scale=1p1`. Metrics: `+3861.48% / -19.44% / 90.91% / 33 trades`.

The canonical main ledger for these promoted versions is `hype-ema-x-core-ledger.md`. The old Cursor canvas is retained only as a legacy source.

## Research Batch Notes

- `research_hype_v15_effective_cross.py`: effective-cross quality probe; evidence only, not the promoted `HYPE-EMA-X-V15`.
- `research_hype_v16_indicator_expansion.py`: indicator-expansion probe. Early indicator entries increased trade count but diluted V14 quality; OKX did not confirm enough stability.
- `research_hype_v17_trend_state_search.py`: broad trend-state search across common indicator families. No candidate satisfied `50x return`, `<20% max drawdown`, and `>80% win rate` simultaneously. Its best low-drawdown and high-return rows are now promoted as `HYPE-EMA-X-V15` and `HYPE-EMA-X-V16`.
- `research_hype_v17_hybrid_ablation.py`: full single-parameter/single-module ablation around `HYPE-EMA-X-V17`. Baseline V17 remains the signal-layer official version; the best ablation row is `hq_scale=1.1` at `+3861.48% / -19.44% / 90.91% / 33 trades`, now recorded as `HYPE-EMA-X-V17.1`.

## Evidence Policy

Use `hype-ema-x-core-ledger.md`, `legacy-canvas/`, and the archived script names to reconstruct the lineage. If a polished spec is needed later, create it under `canonical-specs/` from these evidence files.
