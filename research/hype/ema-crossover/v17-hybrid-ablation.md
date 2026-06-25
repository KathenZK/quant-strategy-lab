# HYPE-EMA-X V17 Hybrid And Full Parameter Ablation

Date: 2026-06-22

Canonical main ledger:

`hype-ema-x-core-ledger.md`

## Version Identity

`HYPE-EMA-X-V17` is the promoted V15/V16 hybrid candidate for the EMA crossover family.

`HYPE-EMA-X-V17.1` is the promoted sizing-enhanced version of V17: signals are unchanged, `hq_scale = 1.1`, and `lq_scale = 1.0`.

Do not confuse this with the earlier `research_hype_v17_trend_state_search.py` batch name. The batch found V15 and V16 frontier rows; this document records the later hybrid candidate and its ablation.

## V17 Rule Summary

V17 keeps the V15 high-quality signal as the main signal and admits a narrow subset of V16 lower-score signals as satellite entries.

High-quality main signal:

- Uses the V16 `atr18` base EMA-regime signal.
- Requires `trend_score >= 7`.
- This is the same high-quality idea as `HYPE-EMA-X-V15`.

Low-score satellite signal:

- Uses the same V16 `atr18` base EMA-regime signal.
- Requires `trend_score` between `5` and `6`.
- Requires `dir_dist_ema96 <= 0.04`.
- Requires `atr_ratio96_672 <= 1.1`.
- Does not require extra OBV, CMF, or hot-edge filters in the official version.

Exit and late-entry engine:

- Uses the V15 late re-entry and V12 state-machine exit engine.
- `late_max_age = 384`.
- `late_dist_ema96 = 0.075`.
- `cooldown_bars = 12`.
- `min_prev_pnl = -0.03`.
- `min_prev_mfe_atr = 3.0`.
- `stop_atr = 8.0`.
- `hard_exit_mode = swing96`.
- `warning_source = either`.
- `osc_min_score = 2`.
- `warning_exit_min_capture = 0.35`.
- `confirm_mode = ema21`.

Official allocation:

- `hq_scale = 1.0`.
- `lq_scale = 1.0`.

V17.1 allocation:

- `hq_scale = 1.1`.
- `lq_scale = 1.0`.

## Main Result

Backtest window: latest 365 days on Binance HYPEUSDT perpetual 15m normalized OHLCV.

| Version | 1Y Return | Final Equity | Max DD | Win Rate | Trades | Late Trades | Stop Loss |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `HYPE-EMA-X-V15` | `+2303.65%` | `24.04x` | `-17.79%` | `90.32%` | `31` | `7` | `0` |
| `HYPE-EMA-X-V16` | `+3202.92%` | `33.03x` | `-28.19%` | `86.84%` | `38` | `10` | `1` |
| `HYPE-EMA-X-V17` | `+2910.74%` | `30.11x` | `-17.79%` | `90.91%` | `33` | `7` | `0` |
| `HYPE-EMA-X-V17.1` | `+3861.48%` | `39.61x` | `-19.44%` | `90.91%` | `33` | `7` | `0` |

V17 did not reach the original `50x` return target, but it preserved the V15 drawdown while recovering much of the V16 return.

V17.1 improves return through sizing only. It is now recorded in the main ledger, but should be read as a risk-budget variant rather than a new signal detector.

## Window Backfill

| Window | Return | Max DD | Trades | Win Rate |
| --- | ---: | ---: | ---: | ---: |
| `1W` | `+0.00%` | `+0.00%` | `0` | `0.00%` |
| `1M` | `+136.84%` | `-17.79%` | `4` | `100.00%` |
| `3M` | `+305.21%` | `-17.79%` | `9` | `100.00%` |
| `6M` | `+840.11%` | `-17.79%` | `19` | `89.47%` |
| `1Y` | `+2910.74%` | `-17.79%` | `33` | `90.91%` |

V17.1 window backfill:

| Window | Return | Max DD | Trades | Win Rate |
| --- | ---: | ---: | ---: | ---: |
| `1W` | `+0.00%` | `+0.00%` | `0` | `0.00%` |
| `1M` | `+152.13%` | `-19.44%` | `4` | `100.00%` |
| `3M` | `+348.68%` | `-19.44%` | `9` | `100.00%` |
| `6M` | `+1021.61%` | `-19.44%` | `19` | `89.47%` |
| `1Y` | `+3861.48%` | `-19.44%` | `33` | `90.91%` |

## Trade Attribution

| Bucket | Trades | Win Rate | Sum Trade PnL | Avg Trade | Median Trade | Worst Trade | Interpretation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `HQ` | `29` | `89.66%` | `+353.32%` | `+12.18%` | `+10.69%` | `-8.33%` | Main V15-like signal remains the return core. |
| `LQ satellite` | `4` | `100.00%` | `+38.11%` | `+9.53%` | `+8.42%` | `+2.90%` | The narrow V16 satellite subset added useful trades without adding stop-loss events in this slice. |

## Ablation Scope

Script:

`research/hype/families/ema-crossover/scripts/research_hype_v17_hybrid_ablation.py`

The run tested `144` candidates: the official baseline plus single-parameter or single-module changes across these groups:

- HQ/LQ signal enablement and score gates.
- LQ distance, ATR-ratio, hot-edge, OBV, and CMF filters.
- HQ and LQ allocation scales.
- Late re-entry age, EMA96 distance, cooldown, previous PnL, previous MFE, and pullback requirements.
- V12 warning source, confirmation mode, re-entry mode, MFE threshold, hard exit, warning capture, volume warning, stop ATR, and segment exit modules.

This is a full one-at-a-time parameter ablation, not a combinatorial grid over every parameter combination.

## Ablation Top Rows

| Candidate | 1Y Return | Max DD | Win Rate | Trades | Interpretation |
| --- | ---: | ---: | ---: | ---: | --- |
| `HYPE-EMA-X-V17` official | `+2910.74%` | `-17.79%` | `90.91%` | `33` | Official baseline. |
| `HYPE-EMA-X-V17.1` (`hq_scale = 1.1`) | `+3861.48%` | `-19.44%` | `90.91%` | `33` | Best return that still stays under 20% drawdown. Recorded as the V17.1 sizing-enhanced main-ledger version, not as a signal-quality breakthrough. |
| `lq_scale = 1.25` | `+3171.45%` | `-17.79%` | `90.91%` | `33` | LQ satellite trades can carry slightly more size, but sample count is only 4 trades. |
| `late_dist_ema96 = 0.06` | `+2965.72%` | `-17.49%` | `90.91%` | `33` | Slightly better risk metrics, but the effect is small. |
| `cooldown_bars = 8` | `+2952.14%` | `-17.79%` | `90.91%` | `33` | Small improvement only. |
| `hard_exit_mode = none` | `+3074.74%` | `-20.55%` | `93.94%` | `33` | Breaches the 20% drawdown boundary, so swing96 remains the official hard exit. |

## Parameter Sensitivity Conclusions

- `hq_scale` is the strongest return knob. `1.1` lifts return to `+3861.48%` with `-19.44%` drawdown; `0.75` cuts drawdown to `-13.56%` but drops return to `+1379.15%`.
- `lq_scale = 1.25` improves return to `+3171.45%` without worsening drawdown, but the evidence rests on only four LQ trades.
- Turning off LQ satellite entries drops the strategy back toward V15: `+2303.65% / -17.79% / 90.32%`.
- Relaxing `lq_max_atr_ratio` above `1.1` reintroduces V16-like risk: values from `1.2` to `1.8` push max drawdown to about `-28.29%`.
- Lowering `hq_min_score` to `6` increases trade count but raises drawdown to `-28.33%`; raising it to `9` avoids drawdown but loses too much return.
- Removing `swing96` hard exit raises return slightly but pushes max drawdown beyond 20%.
- Donchian-style warning confirmation and segment exits continue to cut trends too early.

## Decision

Record the official signal-layer version as `HYPE-EMA-X-V17` with baseline allocation scales.

Record `hq_scale = 1.1` as `HYPE-EMA-X-V17.1` in the main ledger, because it is the best return row that remains below the 20% drawdown ceiling. Treat it as a sizing/risk-budget version, not as proof that trend-start detection improved.

## Local Report Artifacts

Reports are ignored local artifacts under `artifacts/`:

- `artifacts/hype_v17_hybrid_ablation.json`
- `artifacts/hype_v17_hybrid_ablation_ranking.csv`
- `artifacts/hype_v17_hybrid_ablation_sensitivity.csv`
- `artifacts/hype_v17_hybrid_ablation_top_windows.csv`
- `artifacts/hype_v17_hybrid_ablation_trade_attribution.csv`
- `artifacts/hype_v17_hybrid_ablation_base_diagnostics_summary.csv`
- `artifacts/hype_v17_hybrid_ablation_best_diagnostics_summary.csv`
- `artifacts/hype_v17_hybrid_ablation_best_diagnostics_detail.csv`
