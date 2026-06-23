# HYPE-EMA-TB Reports Index

Reports are local artifacts under `reports/` and are ignored by git.

Use this file as the durable pointer layer:

- The migrated core ledger is `hype-ema-tb-core-ledger.md`.
- Trend-breakout reports often use filenames such as `hype_v30_*`, `hype_v34_*`, `hype_v35_*`, `hype_v36_*`, or `hype_ema_*`.
- Family identity must be checked from the target document or Cursor canvas.
- Do not infer family identity from `v35` alone.

Key report families observed historically:

- `hype_ema_*`
- `hype_5m_indicator_search*`
- `hype_5m_filter_refinement*`
- `hype_5m_ensemble_combo*`
- `hype_5m_ensemble_ablation*`
- `hype_5m_ensemble_forward_oos*`
- `hype_5m_positive_payoff_search*`
- `hype_5m_survival_frontier*`
- `hype_v30_*`
- `hype_v34_*`
- `hype_v35_*`
- `hype_v36_*`
- `hype_v15_effective_cross_*`

## Current 5m Indicator Ensemble Batch

- Research note: `hype-5m-indicator-ensemble-search.md`
- Forward OOS note: `hype-5m-ensemble-forward-oos-2026-06-23.md`
- Positive-payoff note: `hype-5m-positive-payoff-search-2026-06-23.md`
- Survival frontier note: `hype-5m-survival-frontier-2026-06-23.md`
- R05732 strategy and ablation note: `hype-5m-r05732-strategy-ablation-2026-06-23.md`
- Scripts:
  - `archive/scripts/research/research_hype_5m_indicator_search.py`
  - `archive/scripts/research/research_hype_5m_filter_refinement.py`
  - `archive/scripts/research/research_hype_5m_ensemble_combo.py`
  - `archive/scripts/research/research_hype_5m_ensemble_ablation.py`
  - `archive/scripts/research/research_hype_5m_ensemble_forward_oos.py`
  - `archive/scripts/research/research_hype_5m_positive_payoff_search.py`
  - `archive/scripts/research/analyze_hype_5m_survival_frontier.py`
  - `archive/scripts/research/ablate_hype_5m_r05732.py`
  - `archive/scripts/research/render_hype_5m_ensemble_specs.py`
- Main report files:
  - `reports/hype_5m_indicator_search.json`
  - `reports/hype_5m_filter_refinement.json`
  - `reports/hype_5m_ensemble_combo.json`
  - `reports/hype_5m_ensemble_ablation.json`
  - `reports/hype_5m_ensemble_forward_oos.json`
  - `reports/hype_5m_positive_payoff_search.json`
  - `reports/hype_5m_survival_frontier.json`
  - `reports/hype_5m_r05732_ablation.json`
- Live-code handoff specs:
  - `ensemble-specs/README.md`
  - `ensemble-specs/hype-ema-tb-5m-ensemble-s01-8l-4x-live-spec.md`
  - `ensemble-specs/hype-ema-tb-5m-ensemble-s02-16l-2p5x-live-spec.md`
  - `ensemble-specs/hype-ema-tb-5m-ensemble-s03-8l-3x-live-spec.md`
  - `ensemble-specs/hype-ema-tb-5m-ensemble-s04-12l-2p5x-live-spec.md`
  - `ensemble-specs/hype-ema-tb-5m-ensemble-s05-5l-3x-live-spec.md`
  - `ensemble-specs/hype-ema-tb-5m-ensemble-s06-16l-2x-live-spec.md`
  - `ensemble-specs/hype-ema-tb-5m-ensemble-s07-8l-2p5x-live-spec.md`
