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
- `diagnostics/hype-5m-pbtr-v21a-live-realistic-audit-2026-06-24.md`: strict live-realistic exit audit for V2.1A, showing the original live-cost result fails when crossed unlock stops are executed as market exits.
- `diagnostics/hype-5m-pbtr-v21a-unlock-exit-audit-2026-06-24.md`: V2.1A dry-run observation audit; confirms most original exits are 7th-bar trailing stops, but the edge disappears if the exit is filled at executable open/market/close prices instead of the stale stop level.
- `diagnostics/hype-5m-pbtr-v21a-fixed-hold-exit-2026-06-24.md`: V2.1A fixed-hold supplement; confirms pure 6-bar fixed holding is not profitable and quantifies how often bar-7 stops are already crossed at the bar open.
- `diagnostics/hype-5m-pbtr-v21a-dryrun-ledger-audit-2026-06-24.md`: audit of `/Users/ZK/OpenCode/hype-pullback` paper-live dry-run SQLite data; the 13 closed trades are profitable only under stop-price ledger fills, while most stops were already crossed when computed.
- `diagnostics/hype-5m-pbtr-v21a-immediate-tp-audit-2026-06-25.md`: V2.1A test with an immediate `1 * ATR14` take-profit and delayed stop; early targets help only under stale stop-price fills, while live-realistic PF remains about `0.53`.
- `live-specs/hype-5m-pbtr-v3-3-live-spec.md`: minimal V3.3 reproduction spec after removing V3.2 compatibility/disabled/protection parameters.
- `ablations/hype-5m-pbtr-v3-3-full-parameter-ablation-2026-06-24.md`: V3.3 six-parameter ablation under observed live costs.
- `diagnostics/hype-5m-pbtr-v33-reinit-trailing-2026-06-24.md`: V3.3 scheme-2 test that observes during lockout and reinitializes trailing at unlock; execution is feasible but the original V3.3 parameters still fail.
- `diagnostics/hype-5m-pbtr-v33-immediate-tp-audit-2026-06-25.md`: V3.3 test with an immediate `1 * ATR14` take-profit and delayed stop; about half of trades hit the early target, but live-realistic PF remains about `0.55`.
- `diagnostics/hype-5m-pbtr-v33-immediate-tp2-audit-2026-06-25.md`: V3.3 test with an immediate `2 * ATR14` take-profit and delayed stop; live-realistic PF improves only to about `0.60`, still not viable.
- `diagnostics/hype-5m-pbtr-v33-immediate-tp-grid-2026-06-25.md`: V3.3 immediate TP ATR grid from `0.25` to `12`; best live-realistic value is `2.5ATR` with PF about `0.615`, so no TP multiplier fixes the strategy.
- `diagnostics/hype-5m-pbtr-v3-4-combo-candidates-2026-06-24.md`: source combo test that promoted the V3.3 improvement candidate to V4.
- `diagnostics/hype-5m-pbtr-v4-live-viability-audit-2026-06-24.md`: V4 live-viability audit covering cost stress, stop execution, and lockout risk.
- `diagnostics/hype-5m-pbtr-live-realistic-trailing-2026-06-24.md`: strict live-realistic trailing audit for V3.3 and V4, showing both fail when crossed unlock stops are executed as market exits.
- `diagnostics/hype-5m-pbtr-fixed-bracket-search-2026-06-24.md`: fixed ATR bracket search for V3.3/V4 signals, showing immediately placed TP/SL orders do not rescue the strategies.
- `diagnostics/hype-5m-pbtr-reset-bracket-search-2026-06-24.md`: dynamic 5m reset ATR bracket search for V3.3/V4 signals; apparent V3.3 PF improvement comes from very few ultra-long holds and is not live-ready.
- `diagnostics/hype-5m-pbtr-reset-bracket-maxhold48-2026-06-24.md`: reset bracket rerun with max hold capped at 48 bars, showing the ultra-long-hold improvement disappears.
- `diagnostics/hype-5m-pbtr-live-repair-plan-2026-06-24.md`: repair proposal after V3.3/V4 failure; recommends executable-first V5 search with protected-from-entry or observation-then-entry state machines.
- `diagnostics/hype-5m-pbtr-v5-executable-search-2026-06-24.md`: first executable-first V5 search. No protected-entry, observation-then-entry, or simple single-feature event-quality filter produced a positive live-ready candidate.
- `diagnostics/hype-5m-pbtr-v5-1-event-quality-2026-06-24.md`: keeps the existing trigger as a high-volume event source and tests event-quality filters under exact executable replay. Finds one narrow observation-confirmed candidate that barely passes the mechanical gate.
- `diagnostics/hype-5m-pbtr-v5-1-candidate-ablation-2026-06-24.md`: ablates the V5.1 candidate and nearby parameters. The edge depends strongly on `opp_wick_atr <= 0`; monthly stability is not live-ready, so V5.1 remains a paper/audit candidate only.
- `diagnostics/hype-5m-pbtr-v5-2-walk-forward-ranking-2026-06-24.md`: converts V5.1 into a live-feasible walk-forward event-ranker and paper-audit log. All `96` ranking configs fail; no paper deployment candidate.
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
- `archive/scripts/research/research_hype_5m_pbtr_v21a_live_realistic_audit.py`
- `archive/scripts/research/research_hype_5m_pbtr_v21a_fixed_hold_exit.py`
- `archive/scripts/research/research_hype_5m_pbtr_v1_v2_slice_compare.py`
- `archive/scripts/research/research_hype_5m_pbtr_v3-3_minimal.py`
- `archive/scripts/research/research_hype_5m_pbtr_v3-3_full_ablation.py`
- `archive/scripts/research/research_hype_5m_pbtr_v33_reinit_trailing.py`
- `archive/scripts/research/research_hype_5m_pbtr_v3-4_combo_candidates.py`
- `archive/scripts/research/research_hype_5m_pbtr_v4_live_viability_audit.py`
- `archive/scripts/research/research_hype_5m_pbtr_live_realistic_trailing.py`
- `archive/scripts/research/research_hype_5m_pbtr_fixed_bracket_search.py`
- `archive/scripts/research/research_hype_5m_pbtr_reset_bracket_search.py`
- `archive/scripts/research/research_hype_5m_pbtr_reset_bracket_maxhold48.py`
- `archive/scripts/research/research_hype_5m_pbtr_v5_executable_search.py`
- `archive/scripts/research/research_hype_5m_pbtr_v51_event_quality.py`
- `archive/scripts/research/research_hype_5m_pbtr_v51_candidate_ablation.py`
- `archive/scripts/research/research_hype_5m_pbtr_v52_walk_forward_ranking.py`
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
- `reports/hype_5m_pbtr_v21a_live_realistic_audit.json`
- `reports/hype_5m_pbtr_v21_live_cost_variant_summary.csv`
- `reports/hype_5m_pbtr_v21_live_cost_variant_rolling_windows.csv`
- `reports/hype_5m_pbtr_v21_live_cost_variant_weekly_slices.csv`
- `reports/hype_5m_pbtr_v21a_fixed_hold_exit.json`
- `reports/hype_5m_pbtr_v21a_fixed_hold_exit_summary.csv`
- `reports/hype_5m_pbtr_v21a_fixed_hold_exit_slices.csv`
- `reports/hype_5m_pbtr_v21a_fixed_hold_exit_monthly.csv`
- `reports/hype_5m_pbtr_v21a_fixed_hold_exit_recent_trades.csv`
- `reports/hype_5m_pbtr_v3-3_minimal.json`
- `reports/hype_5m_pbtr_v3-3_full_ablation.json`
- `reports/hype_5m_pbtr_v33_reinit_trailing.json`
- `reports/hype_5m_pbtr_v3-4_combo_candidates.json`
- `reports/hype_5m_pbtr_v4_live_viability_audit.json`
- `reports/hype_5m_pbtr_live_realistic_trailing.json`
- `reports/hype_5m_pbtr_fixed_bracket_search.json`
- `reports/hype_5m_pbtr_reset_bracket_search.json`
- `reports/hype_5m_pbtr_reset_bracket_maxhold48.json`
- `reports/hype_5m_pbtr_v5_executable_search.json`
- `reports/hype_5m_pbtr_v5_executable_search_summary.csv`
- `reports/hype_5m_pbtr_v5_executable_search_slices.csv`
- `reports/hype_5m_pbtr_v51_event_quality.json`
- `reports/hype_5m_pbtr_v51_event_quality_summary.csv`
- `reports/hype_5m_pbtr_v51_event_quality_exact_rules.csv`
- `reports/hype_5m_pbtr_v51_candidate_ablation.json`
- `reports/hype_5m_pbtr_v51_candidate_ablation_summary.csv`
- `reports/hype_5m_pbtr_v52_walk_forward_ranking.json`
- `reports/hype_5m_pbtr_v52_walk_forward_ranking_summary.csv`
- `reports/hype_5m_pbtr_v52_walk_forward_ranking_segments.csv`
- `reports/hype_5m_pbtr_v52_paper_audit_events.csv`
