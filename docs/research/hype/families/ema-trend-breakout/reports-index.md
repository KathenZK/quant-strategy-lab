# HYPE-EMA-TB Reports Index

Reports are local artifacts under `reports/` and are ignored by git.

Use this file as the durable pointer layer:

- Trend-breakout reports often use filenames such as `hype_v30_*`, `hype_v34_*`, `hype_v35_*`, `hype_v36_*`, or `hype_ema_*`.
- Family identity must be checked from the target document or Cursor canvas.
- Do not infer family identity from `v35` alone.

Key report families observed historically:

- `hype_ema_*`
- `hype_5m_indicator_search*`
- `hype_5m_filter_refinement*`
- `hype_5m_ensemble_combo*`
- `hype_5m_ensemble_ablation*`
- `hype_v30_*`
- `hype_v34_*`
- `hype_v35_*`
- `hype_v36_*`
- `hype_v15_effective_cross_*`

## Current 5m Indicator Ensemble Batch

- Research note: `hype-5m-indicator-ensemble-search.md`
- Scripts:
  - `archive/scripts/research/research_hype_5m_indicator_search.py`
  - `archive/scripts/research/research_hype_5m_filter_refinement.py`
  - `archive/scripts/research/research_hype_5m_ensemble_combo.py`
  - `archive/scripts/research/research_hype_5m_ensemble_ablation.py`
  - `archive/scripts/research/render_hype_5m_ensemble_specs.py`
- Main report files:
  - `reports/hype_5m_indicator_search.json`
  - `reports/hype_5m_filter_refinement.json`
  - `reports/hype_5m_ensemble_combo.json`
  - `reports/hype_5m_ensemble_ablation.json`
- Live-code handoff specs:
  - `ensemble-specs/README.md`
  - `ensemble-specs/hype-ema-tb-5m-ensemble-s01-8l-4x-live-spec.md`
  - `ensemble-specs/hype-ema-tb-5m-ensemble-s02-16l-2p5x-live-spec.md`
  - `ensemble-specs/hype-ema-tb-5m-ensemble-s03-8l-3x-live-spec.md`
  - `ensemble-specs/hype-ema-tb-5m-ensemble-s04-12l-2p5x-live-spec.md`
  - `ensemble-specs/hype-ema-tb-5m-ensemble-s05-5l-3x-live-spec.md`
  - `ensemble-specs/hype-ema-tb-5m-ensemble-s06-16l-2x-live-spec.md`
  - `ensemble-specs/hype-ema-tb-5m-ensemble-s07-8l-2p5x-live-spec.md`
