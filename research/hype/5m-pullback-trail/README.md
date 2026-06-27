# HYPE-5M-PBTR 5m Pullback-Trail

Family id: `HYPE-5M-PBTR`

This family covers Binance HYPE USDT perpetual `5m` strategy research centered on pullback/resume entries and ATR trailing-stop exits.

It is independent from:

- `HYPE-EMA-TB`: the older 15m EMA96/384 trend-breakout / cross-exchange execution family.
- `HYPE-EMA-X`: the EMA golden/death cross and cross-quality family.
- `HYPE-CC`: the candle-count reversal family.

## Canonical Entrypoints

- `hype-5m-pullback-trail-core-ledger.md`: main ledger for promoted local `HYPE-5M-PBTR` versions, including `V1/V2/V6`.
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
- `diagnostics/hype-5m-pbtr-v6-live-executable-search-2026-06-25.md`: leakage-aware executable-first V6 search using closed-bar signals, next-open entry, immediate bracket orders, conservative TP/SL ordering, and train-ranked candidate refinement.
- `diagnostics/hype-5m-pbtr-v6-candidate-robustness-2026-06-25.md`: V6 neighborhood robustness check around the strongest executable base. Promotes a paper-only candidate built from EMA21/55 long pullback-reclaim, 16h momentum filter, fixed TP/SL, and a 36-bar time exit.
- `ablations/hype-5m-pbtr-v6-full-parameter-ablation-2026-06-25.md`: formally records the V6 strategy definition and ablates every active parameter under the same live-executable bracket/timeout model.
- `diagnostics/hype-5m-pbtr-v6-tp25-sizing-2026-06-27.md`: V6 sizing diagnostic for `TP=2.5ATR` with fixed and volatility-scaled leverage.
- `diagnostics/hype-5m-pbtr-v6-1-trade-paths-2026-06-27.md`: promotes `TP=2.5ATR + fixed 3x` as `HYPE-5M-PBTR-V6.1` paper sizing variant and links the per-trade K-line HTML.
- `diagnostics/hype-5m-pbtr-v6-1-tp-trigger-trailing-2026-06-27.md`: tests replacing V6.1 fixed TP with a trailing trigger. Fixed TP remains stronger than all tested trailing overlays.
- `diagnostics/hype-5m-pbtr-v6-1-short-combo-search-2026-06-27.md`: searches short-only executable bracket candidates and combines them with V6.1 long-only under a one-position constraint; source report for the later V6.2 promotion.
- `ablations/hype-5m-pbtr-v6-2-full-parameter-ablation-2026-06-28.md`: promotes `combo_short_rank2` to `HYPE-5M-PBTR-V6.2` after full parameter ablation; paper/live-dry-run candidate only, preferably 1x or tiny notional first.
- `ablations/hype-5m-pbtr-v6-2-tp4-htf0-combo-probe-2026-06-28.md`: tests combining `long_tp_atr=4.0` with `long_htf_threshold=0.0`; it passes robust gate but does not outperform V6.2.1 `TP=2.5ATR + htf_spread>=0`.
- `diagnostics/hype-5m-executable-broad-search-2026-06-25.md`: broad executable-only HYPE `5m` search across old indicator entry styles with entry-time bracket protection. Tests `13134` configurations against `>=20x` annualized, `>=50%` win rate, and `>-20%` drawdown. No configuration comes close; the best `>=100` trade row annualizes only about `1.05x`.
- `ablations/hype-5m-r05732-strategy-ablation-2026-06-23.md`: V1/R05732 full parameter explanation and ablation.
- `diagnostics/hype-5m-pbtr-v1-strict-live-audit-2026-06-27.md`: strict live-realistic audit for V1/R05732. Confirms the legacy stop-price fill backtest remains profitable, but V1 collapses under executable unlock stop/target handling and is not a rollback live candidate.
- `diagnostics/hype-5m-pbtr-ml-event-quality-2026-06-27.md`: V3.3.1 walk-forward ML event-quality rescue attempt. Slightly raises trailing-positive / armed quality but remains PF < 1 across exact replay modes.
- `diagnostics/hype-5m-pbtr-v3-3-1-armed-pyramiding-2026-06-27.md`: V3.3.1 armed-after pyramiding test. Adding leverage after stop-arm/trailing success does not improve PF; the add leg is still negative expectancy.
- `diagnostics/hype-5m-pbtr-v3-3-1-pb005-arm4-2026-06-27.md`: V3.3.1 `pullback_buffer=0.005` plus arm-from-4th-bar test. Earlier trailing increases armed rate but worsens PF across all replay modes.

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

Retained report artifacts live under `artifacts/`. Top-level `reports/` is retired; cite `artifacts/` when a JSON, CSV, or HTML file supports a durable report.

Scripts:

- `research/hype/5m-pullback-trail/scripts/research_hype_5m_indicator_search.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_filter_refinement.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_ensemble_combo.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_ensemble_ablation.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_ensemble_forward_oos.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_positive_payoff_search.py`
- `research/hype/5m-pullback-trail/scripts/analyze_hype_5m_survival_frontier.py`
- `research/hype/5m-pullback-trail/scripts/ablate_hype_5m_r05732.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v1_strict_live_audit.py`
- `research/hype/5m-pullback-trail/scripts/test_hype_5m_r05732_v2_combos.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v2_ablation_slices.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v2_live_cost_ablation_slices.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v21_live_cost_variants.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v21a_live_realistic_audit.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v21a_fixed_hold_exit.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v1_v2_slice_compare.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v3-3_minimal.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v3-3_full_ablation.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v33_reinit_trailing.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v3-4_combo_candidates.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v4_live_viability_audit.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_live_realistic_trailing.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_fixed_bracket_search.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_reset_bracket_search.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_reset_bracket_maxhold48.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v5_executable_search.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v51_event_quality.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v51_candidate_ablation.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v52_walk_forward_ranking.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v6_live_executable_search.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v6_candidate_robustness.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v6_full_ablation.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v6_tp25_sizing.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v6_1_trade_paths.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v6_1_tp_trigger_trailing.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v6_1_short_combo_search.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v6_2_full_ablation.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v6_2_tp4_htf0_combo_probe.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_ml_event_quality.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v3-3-1_armed_pyramiding.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v3-3-1_pb005_arm4.py`
- `research/hype/5m-pullback-trail/scripts/render_hype_5m_ensemble_specs.py`

Report files:

- `artifacts/hype_5m_indicator_search.json`
- `artifacts/hype_5m_filter_refinement.json`
- `artifacts/hype_5m_ensemble_combo.json`
- `artifacts/hype_5m_ensemble_ablation.json`
- `artifacts/hype_5m_ensemble_forward_oos.json`
- `artifacts/hype_5m_positive_payoff_search.json`
- `artifacts/hype_5m_survival_frontier.json`
- `artifacts/hype_5m_r05732_ablation.json`
- `artifacts/hype_5m_pbtr_v1_strict_live_audit_2026-06-27.json`
- `artifacts/hype_5m_pbtr_v1_strict_live_audit_summary_2026-06-27.csv`
- `artifacts/hype_5m_pbtr_v1_strict_live_audit_trade_diag_2026-06-27.csv`
- `artifacts/hype_5m_pbtr_v1_strict_live_audit_rolling_2026-06-27.csv`
- `artifacts/hype_5m_pbtr_v1_strict_live_audit_weekly_2026-06-27.csv`
- `artifacts/hype_5m_pbtr_v1_strict_live_audit_monthly_2026-06-27.csv`
- `artifacts/hype_5m_r05732_v2_combo_test.json`
- `artifacts/hype_5m_r05732_v2_combo_test_ranking.csv`
- `artifacts/hype_5m_r05732_v2_combo_test_slices.csv`
- `artifacts/hype_5m_pbtr_v1_weekly_slices.csv`
- `artifacts/hype_5m_pbtr_v1_rolling_windows.csv`
- `artifacts/hype_5m_pbtr_v1_v2_rolling_compare.csv`
- `artifacts/hype_5m_pbtr_v1_v2_weekly_compare.csv`
- `artifacts/hype_5m_pbtr_v1_v2_slice_compare.json`
- `artifacts/hype_5m_pbtr_v2_ablation_summary.csv`
- `artifacts/hype_5m_pbtr_v2_ablation_validation_slices.csv`
- `artifacts/hype_5m_pbtr_v2_weekly_slices.csv`
- `artifacts/hype_5m_pbtr_v2_rolling_windows.csv`
- `artifacts/hype_5m_pbtr_v2_live_cost_ablation_slices.json`
- `artifacts/hype_5m_pbtr_v2_live_cost_ablation_summary.csv`
- `artifacts/hype_5m_pbtr_v2_live_cost_ablation_validation_slices.csv`
- `artifacts/hype_5m_pbtr_v2_live_cost_weekly_slices.csv`
- `artifacts/hype_5m_pbtr_v2_live_cost_rolling_windows.csv`
- `artifacts/hype_5m_pbtr_v21_live_cost_variants.json`
- `artifacts/hype_5m_pbtr_v21a_live_realistic_audit.json`
- `artifacts/hype_5m_pbtr_v21_live_cost_variant_summary.csv`
- `artifacts/hype_5m_pbtr_v21_live_cost_variant_rolling_windows.csv`
- `artifacts/hype_5m_pbtr_v21_live_cost_variant_weekly_slices.csv`
- `artifacts/hype_5m_pbtr_v21a_fixed_hold_exit.json`
- `artifacts/hype_5m_pbtr_v21a_fixed_hold_exit_summary.csv`
- `artifacts/hype_5m_pbtr_v21a_fixed_hold_exit_slices.csv`
- `artifacts/hype_5m_pbtr_v21a_fixed_hold_exit_monthly.csv`
- `artifacts/hype_5m_pbtr_v21a_fixed_hold_exit_recent_trades.csv`
- `artifacts/hype_5m_pbtr_v3-3_minimal.json`
- `artifacts/hype_5m_pbtr_v3-3_full_ablation.json`
- `artifacts/hype_5m_pbtr_v33_reinit_trailing.json`
- `artifacts/hype_5m_pbtr_v3-4_combo_candidates.json`
- `artifacts/hype_5m_pbtr_v4_live_viability_audit.json`
- `artifacts/hype_5m_pbtr_live_realistic_trailing.json`
- `artifacts/hype_5m_pbtr_fixed_bracket_search.json`
- `artifacts/hype_5m_pbtr_reset_bracket_search.json`
- `artifacts/hype_5m_pbtr_reset_bracket_maxhold48.json`
- `artifacts/hype_5m_pbtr_v5_executable_search.json`
- `artifacts/hype_5m_pbtr_v5_executable_search_summary.csv`
- `artifacts/hype_5m_pbtr_v5_executable_search_slices.csv`
- `artifacts/hype_5m_pbtr_v51_event_quality.json`
- `artifacts/hype_5m_pbtr_v51_event_quality_summary.csv`
- `artifacts/hype_5m_pbtr_v51_event_quality_exact_rules.csv`
- `artifacts/hype_5m_pbtr_v51_candidate_ablation.json`
- `artifacts/hype_5m_pbtr_v51_candidate_ablation_summary.csv`
- `artifacts/hype_5m_pbtr_v52_walk_forward_ranking.json`
- `artifacts/hype_5m_pbtr_v52_walk_forward_ranking_summary.csv`
- `artifacts/hype_5m_pbtr_v52_walk_forward_ranking_segments.csv`
- `artifacts/hype_5m_pbtr_v52_paper_audit_events.csv`
- `artifacts/hype_5m_pbtr_v6_live_executable_search.json`
- `artifacts/hype_5m_pbtr_v6_live_executable_prescreen.csv`
- `artifacts/hype_5m_pbtr_v6_live_executable_candidates.csv`
- `artifacts/hype_5m_pbtr_v6_live_executable_slices.csv`
- `artifacts/hype_5m_pbtr_v6_live_executable_monthly.csv`
- `artifacts/hype_5m_pbtr_v6_candidate_robustness.csv`
- `artifacts/hype_5m_pbtr_v6_candidate_robustness_monthly.csv`
- `artifacts/hype_5m_pbtr_v6_full_ablation.json`
- `artifacts/hype_5m_pbtr_v6_full_ablation_summary.csv`
- `artifacts/hype_5m_pbtr_v6_full_ablation_validation_slices.csv`
- `artifacts/hype_5m_pbtr_v6_full_ablation_rolling.csv`
- `artifacts/hype_5m_pbtr_v6_full_ablation_weekly.csv`
- `artifacts/hype_5m_pbtr_v6_full_ablation_monthly.csv`
- `artifacts/hype_5m_pbtr_v6_tp25_sizing_2026-06-27.json`
- `artifacts/hype_5m_pbtr_v6_tp25_sizing_summary_2026-06-27.csv`
- `artifacts/hype_5m_pbtr_v6_tp25_sizing_trades_2026-06-27.csv`
- `artifacts/hype_5m_pbtr_v6-1_2026-06-27.json`
- `artifacts/hype_5m_pbtr_v6-1_summary_2026-06-27.csv`
- `artifacts/hype_5m_pbtr_v6-1_trades_2026-06-27.csv`
- `artifacts/hype_5m_pbtr_v6-1_trade_paths_2026-06-27.html`
- `artifacts/hype_5m_pbtr_v6-1_tp_trigger_trailing_2026-06-27.json`
- `artifacts/hype_5m_pbtr_v6-1_tp_trigger_trailing_summary_2026-06-27.csv`
- `artifacts/hype_5m_pbtr_v6-1_tp_trigger_trailing_trades_2026-06-27.csv`
- `artifacts/hype_5m_pbtr_v6-1_short_search_summary_2026-06-27.csv`
- `artifacts/hype_5m_pbtr_v6-1_short_combo_extended_summary_2026-06-27.csv`
- `artifacts/hype_5m_pbtr_v6-1_short_combo_side_breakdown_2026-06-27.csv`
- `artifacts/hype_5m_pbtr_v6-1_short_combo_slice_breakdown_2026-06-27.csv`
- `artifacts/hype_5m_pbtr_v6-2_full_ablation_2026-06-28.json`
- `artifacts/hype_5m_pbtr_v6-2_full_ablation_summary_2026-06-28.csv`
- `artifacts/hype_5m_pbtr_v6-2_baseline_trades_2026-06-28.csv`
- `artifacts/hype_5m_pbtr_ml_event_quality_2026-06-27.json`
- `artifacts/hype_5m_pbtr_ml_event_quality_events_2026-06-27.csv`
- `artifacts/hype_5m_pbtr_ml_event_quality_scores_2026-06-27.csv`
- `artifacts/hype_5m_pbtr_ml_event_quality_exact_2026-06-27.csv`
- `artifacts/hype_5m_pbtr_ml_event_quality_v1_events_2026-06-27.csv`
- `artifacts/hype_5m_pbtr_v3-3-1_armed_pyramiding_2026-06-27.json`
- `artifacts/hype_5m_pbtr_v3-3-1_armed_pyramiding_summary_2026-06-27.csv`
- `artifacts/hype_5m_pbtr_v3-3-1_armed_pyramiding_robust_2026-06-27.csv`
- `artifacts/hype_5m_pbtr_v3-3-1_armed_pyramiding_diag_2026-06-27.csv`
- `artifacts/hype_5m_pbtr_v3-3-1_pb005_arm4_2026-06-27.json`
- `artifacts/hype_5m_pbtr_v3-3-1_pb005_arm4_summary_2026-06-27.csv`
- `artifacts/hype_5m_pbtr_v3-3-1_pb005_arm4_diag_2026-06-27.csv`
