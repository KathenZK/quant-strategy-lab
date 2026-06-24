# HYPE-5M-PBTR 5m Pullback-Trail

Family id: `HYPE-5M-PBTR`

This family covers Binance HYPE USDT perpetual `5m` strategy research centered on pullback/resume entries and ATR trailing-stop exits.

It is independent from:

- `HYPE-EMA-TB`: the older 15m EMA96/384 trend-breakout / cross-exchange execution family.
- `HYPE-EMA-X`: the EMA golden/death cross and cross-quality family.
- `HYPE-CC`: the candle-count reversal family.

## Canonical Entrypoints

- `hype-5m-pullback-trail-core-ledger.md`: main ledger for `HYPE-5M-PBTR-V1/V2`.
- `research-notes/hype-5m-pullback-trail-v2-combo-test-2026-06-23.md`: synchronous parameter test that promoted V2.
- `live-specs/hype-5m-pullback-trail-v2-live-spec.md`: detailed V2 reproduction and small live dry-run handoff spec.
- `ablations/hype-5m-pullback-trail-v2-ablation-slices-2026-06-23.md`: V2 full ablation, weekly slices, and rolling 1w/1m/3m/6m/full performance.
- `ablations/hype-5m-pullback-trail-v2-live-cost-ablation-slices-2026-06-23.md`: V2 full ablation and time-slice performance rerun with observed live fee/slippage.
- `ablations/hype-5m-pullback-trail-v21-live-cost-variants-2026-06-23.md`: V2.1 parameter simplification and V2.1A/B/C candidate tests under observed live costs.
- `live-specs/hype-5m-pbtr-v3-3-live-spec.md`: minimal V3.3 reproduction spec after removing V3.2 compatibility/disabled/protection parameters.
- `ablations/hype-5m-r05732-strategy-ablation-2026-06-23.md`: V1/R05732 full parameter explanation and ablation.

## Supporting Research

- `research-notes/hype-5m-indicator-ensemble-search.md`: original 5m indicator/ensemble search.
- `research-notes/hype-5m-ensemble-forward-oos-2026-06-23.md`: forward OOS check for the initial ensemble batch.
- `research-notes/hype-5m-positive-payoff-search-2026-06-23.md`: positive-payoff search after rejecting high-win small-profit paths.
- `research-notes/hype-5m-survival-frontier-2026-06-23.md`: survival frontier that selected R05732 for deeper research.
- `live-specs/ensemble-specs/`: historical live-code handoff specs for the initial one-position ensemble batch.

## Version Scope

`HYPE-5M-PBTR-V1/V2` are local to this family. Never merge or compare them by bare version number with `HYPE-EMA-TB-V35`, `HYPE-EMA-X-V17`, or `HYPE-CC-V35`.

File naming rule for dotted versions: for newly created files, preserve the dot as a hyphen in file names. For example, `HYPE-5M-PBTR-V3.2` should use `v3-2` in Markdown/script/report file names, not `v32`, to avoid confusion with a future `V32`.

## Local Report Artifacts

Reports are local artifacts under `reports/` and are ignored by git. Use this README as the durable pointer layer for HYPE Binance `5m` research.

Scripts:

- `archive/scripts/research/research_hype_5m_indicator_search.py`
- `archive/scripts/research/research_hype_5m_filter_refinement.py`
- `archive/scripts/research/research_hype_5m_ensemble_combo.py`
- `archive/scripts/research/research_hype_5m_ensemble_ablation.py`
- `archive/scripts/research/research_hype_5m_ensemble_forward_oos.py`
- `archive/scripts/research/research_hype_5m_positive_payoff_search.py`
- `archive/scripts/research/analyze_hype_5m_survival_frontier.py`
- `archive/scripts/research/ablate_hype_5m_r05732.py`
- `archive/scripts/research/test_hype_5m_r05732_v2_combos.py`
- `archive/scripts/research/research_hype_5m_pbtr_v2_ablation_slices.py`
- `archive/scripts/research/research_hype_5m_pbtr_v2_live_cost_ablation_slices.py`
- `archive/scripts/research/research_hype_5m_pbtr_v21_live_cost_variants.py`
- `archive/scripts/research/research_hype_5m_pbtr_v1_v2_slice_compare.py`
- `archive/scripts/research/research_hype_5m_pbtr_v3-3_minimal.py`
- `archive/scripts/research/render_hype_5m_ensemble_specs.py`

Report files:

- `reports/hype_5m_indicator_search.json`
- `reports/hype_5m_filter_refinement.json`
- `reports/hype_5m_ensemble_combo.json`
- `reports/hype_5m_ensemble_ablation.json`
- `reports/hype_5m_ensemble_forward_oos.json`
- `reports/hype_5m_positive_payoff_search.json`
- `reports/hype_5m_survival_frontier.json`
- `reports/hype_5m_r05732_ablation.json`
- `reports/hype_5m_r05732_v2_combo_test.json`
- `reports/hype_5m_r05732_v2_combo_test_ranking.csv`
- `reports/hype_5m_r05732_v2_combo_test_slices.csv`
- `reports/hype_5m_pbtr_v1_weekly_slices.csv`
- `reports/hype_5m_pbtr_v1_rolling_windows.csv`
- `reports/hype_5m_pbtr_v1_v2_rolling_compare.csv`
- `reports/hype_5m_pbtr_v1_v2_weekly_compare.csv`
- `reports/hype_5m_pbtr_v1_v2_slice_compare.json`
- `reports/hype_5m_pbtr_v2_ablation_summary.csv`
- `reports/hype_5m_pbtr_v2_ablation_validation_slices.csv`
- `reports/hype_5m_pbtr_v2_weekly_slices.csv`
- `reports/hype_5m_pbtr_v2_rolling_windows.csv`
- `reports/hype_5m_pbtr_v2_live_cost_ablation_slices.json`
- `reports/hype_5m_pbtr_v2_live_cost_ablation_summary.csv`
- `reports/hype_5m_pbtr_v2_live_cost_ablation_validation_slices.csv`
- `reports/hype_5m_pbtr_v2_live_cost_weekly_slices.csv`
- `reports/hype_5m_pbtr_v2_live_cost_rolling_windows.csv`
- `reports/hype_5m_pbtr_v21_live_cost_variants.json`
- `reports/hype_5m_pbtr_v21_live_cost_variant_summary.csv`
- `reports/hype_5m_pbtr_v21_live_cost_variant_rolling_windows.csv`
- `reports/hype_5m_pbtr_v21_live_cost_variant_weekly_slices.csv`
- `reports/hype_5m_pbtr_v3-3_minimal.json`
