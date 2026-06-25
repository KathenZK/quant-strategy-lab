# HYPE-5M-PBTR-V5.2 Walk-Forward Event Ranking 2026-06-24

Family id: `HYPE-5M-PBTR`

V5.2 keeps the V5.1 observation-confirmed trigger, but replaces fixed hand-picked thresholds with a live-feasible walk-forward ranker. Each monthly test segment is scored using only previous events. The acceptance threshold is the historical train-score quantile, so live execution does not need to know future event counts.

## Method

- Base state machine: `observe_then_enter`, EMA `21/96`, `observation_bars=3`, `min_favorable_bps=40`, `max_adverse_bps=100`, `stop_atr=2`, `trail_atr=3`, `time_exit_bars=24`.
- Ranking model: quantile-bin event scorer with shrinkage toward the training mean return.
- Train modes: expanding, trailing `180d`, trailing `120d`, trailing `90d`.
- Acceptance rates: historical train-score top `5%`, `8%`, `10%`, `12%`, `15%`, `20%`.
- Final evaluation: accepted events are converted back to signals and replayed through the exact executable state machine, including overlap blocking.

## V5.2 Gate

- Walk-forward trades `>=100`.
- Walk-forward PF `>=1.15`.
- Validation PF `>=1.05`.
- Forward PF `>=0.90`.
- Average trade `>0`, payoff `>1`, max drawdown no worse than `-25%`.
- Profitable months at least half of walk-forward months.

## Passing Rows

No rows.

## Watchlist

No rows.

## Top Rows

| label | events/trades | WF PF | VAL PF | FWD PF | win | payoff | avg | DD | months | accepted->trade |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `all_liquid_expanding_top0.05` | `176/165` | `0.88` | `0.83` | `2.73` | `32.12%` | `1.85` | `-0.05%` | `-14.61%` | `5/10` | `93.8%` |
| `trend_context_expanding_top0.08` | `238/223` | `0.88` | `0.79` | `2.09` | `30.94%` | `1.96` | `-0.05%` | `-25.96%` | `5/10` | `93.7%` |
| `trend_context_expanding_top0.12` | `351/317` | `0.84` | `0.80` | `1.30` | `31.23%` | `1.84` | `-0.07%` | `-32.97%` | `5/10` | `90.3%` |
| `v51_core_expanding_top0.05` | `198/194` | `0.93` | `0.91` | `1.04` | `34.54%` | `1.76` | `-0.03%` | `-22.80%` | `4/10` | `98.0%` |
| `all_liquid_expanding_top0.08` | `269/250` | `0.83` | `0.81` | `1.31` | `32.40%` | `1.74` | `-0.07%` | `-24.79%` | `4/10` | `92.9%` |
| `trend_context_expanding_top0.15` | `430/388` | `0.84` | `0.78` | `1.52` | `30.93%` | `1.87` | `-0.07%` | `-38.47%` | `3/10` | `90.2%` |
| `trend_context_expanding_top0.1` | `293/268` | `0.83` | `0.77` | `1.43` | `30.60%` | `1.87` | `-0.08%` | `-29.94%` | `4/10` | `91.5%` |
| `v51_core_expanding_top0.08` | `251/243` | `0.87` | `0.85` | `1.04` | `34.98%` | `1.62` | `-0.06%` | `-25.96%` | `3/10` | `96.8%` |
| `trend_context_expanding_top0.05` | `157/152` | `0.78` | `0.67` | `2.29` | `26.32%` | `2.19` | `-0.10%` | `-23.66%` | `5/10` | `96.8%` |
| `all_liquid_trailing_180d_top0.08` | `226/210` | `0.86` | `0.85` | `0.95` | `32.38%` | `1.79` | `-0.06%` | `-18.41%` | `3/10` | `92.9%` |
| `price_action_expanding_top0.1` | `301/289` | `0.81` | `0.80` | `1.00` | `32.18%` | `1.70` | `-0.09%` | `-37.93%` | `4/10` | `96.0%` |
| `trend_context_expanding_top0.2` | `573/508` | `0.75` | `0.71` | `1.62` | `30.31%` | `1.73` | `-0.11%` | `-55.62%` | `2/10` | `88.7%` |

## Fixed V5.1 Benchmark

This row uses the V5.1 fixed thresholds discovered with hindsight. It is not walk-forward-ranked, so it is a benchmark for edge decay rather than a deployable model-selection process.

| label | events/trades | WF PF | VAL PF | FWD PF | win | payoff | avg | DD | months |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `v5_1_static_threshold_oracle` | `183/137` | `1.22` | `1.24` | `1.06` | `34.31%` | `2.34` | `0.10%` | `-10.37%` | `6/10` |

## Best Row Monthly Breakdown

| month | trades | PF | return | DD | win | payoff | avg |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `2025-09` | `20` | `0.83` | `-1.29%` | `-4.17%` | `40.00%` | `1.25` | `-0.06%` |
| `2025-10` | `14` | `0.32` | `-5.04%` | `-5.11%` | `28.57%` | `0.80` | `-0.37%` |
| `2025-11` | `12` | `1.30` | `1.31%` | `-3.61%` | `25.00%` | `3.90` | `0.12%` |
| `2025-12` | `12` | `2.44` | `3.65%` | `-1.86%` | `50.00%` | `2.44` | `0.30%` |
| `2026-01` | `24` | `0.76` | `-2.45%` | `-5.15%` | `25.00%` | `2.29` | `-0.10%` |
| `2026-02` | `14` | `1.51` | `2.58%` | `-3.66%` | `35.71%` | `2.72` | `0.19%` |
| `2026-03` | `24` | `0.44` | `-5.76%` | `-7.15%` | `29.17%` | `1.06` | `-0.24%` |
| `2026-04` | `26` | `0.62` | `-3.46%` | `-6.82%` | `19.23%` | `2.60` | `-0.13%` |
| `2026-05` | `14` | `1.05` | `0.13%` | `-2.71%` | `42.86%` | `1.39` | `0.01%` |
| `2026-06` | `5` | `2.73` | `2.52%` | `-1.15%` | `60.00%` | `1.82` | `0.51%` |

## Paper Audit Output

The audit CSV logs every observation-confirmed event for the best row: `176` accepted, `165` paper trades opened, `11` accepted events blocked by an existing paper position, and `2780` rejected by score threshold.

Required live paper-audit fields are present: `signal_ts`, `side`, `segment`, `train_start`, `train_end`, `test_start`, `test_end`, `score`, `score_threshold`, `score_rank_pct_train`, `decision`, `reject_reason`, and `paper_order_status`.

## Decision

No row is strong enough for watchlist. V5.2 should not proceed to paper deployment without a different ranker or feature family.

The important diagnostic is the gap between the fixed V5.1 benchmark and walk-forward ranking. The hindsight fixed threshold still has walk-forward-period PF `1.22`, but every live-feasible ranker row is below PF `1` and has negative average trade. That means the current feature/scoring method cannot learn the V5.1 quality condition reliably from past events. Treat the fixed threshold as a suspicious research clue, not as a live deployable rule.

## Outputs

- Script: `research/hype/families/5m-pullback-trail/scripts/research_hype_5m_pbtr_v52_walk_forward_ranking.py`
- JSON: `artifacts/hype_5m_pbtr_v52_walk_forward_ranking.json`
- Summary CSV: `artifacts/hype_5m_pbtr_v52_walk_forward_ranking_summary.csv`
- Segment CSV: `artifacts/hype_5m_pbtr_v52_walk_forward_ranking_segments.csv`
- Paper audit CSV: `artifacts/hype_5m_pbtr_v52_paper_audit_events.csv`
