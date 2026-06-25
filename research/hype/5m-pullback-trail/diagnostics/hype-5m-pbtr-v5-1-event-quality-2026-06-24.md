# HYPE-5M-PBTR-V5.1 Event Quality Search 2026-06-24

Family id: `HYPE-5M-PBTR`

V5.1 keeps the existing pullback signal trigger as an event generator and adds a separate quality-selection layer. The final evaluation still replays executable orders after filtering, so overlapping signals, immediate protective stops, market exits on crossed stops, observed fees, and observed slippage remain in the result.

## Why This Exists

V5 showed that `trigger -> enter` is negative under live-realistic execution. The trigger is still useful because it generates many candidate events. The question here is whether event-time features can select a smaller set of signals with positive executable expectancy.

## Baselines Before Filtering

| baseline | model | trigger | signal/events | trades | PF | win | payoff | avg | DD |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `protected_entry_ema21_96_pb0.01_sl3_tr4_tx48_htfnone_obs0_fav0_advnone` | `protected_entry` | `21289` | `21289` | `3732` | `0.69` | `30.68%` | `1.55` | `-0.21%` | `-99.97%` |
| `protected_entry_ema21_96_pb0.01_sl2_tr4_tx48_htfnone_obs0_fav0_advnone` | `protected_entry` | `21289` | `21289` | `4463` | `0.67` | `26.01%` | `1.89` | `-0.19%` | `-99.99%` |
| `protected_entry_ema21_55_pb0.01_sl2_tr4_tx24_htf0.5_obs0_fav0_advnone` | `protected_entry` | `6664` | `6664` | `1773` | `0.68` | `32.54%` | `1.42` | `-0.20%` | `-97.67%` |
| `observe_then_enter_ema21_96_pb0.01_sl2_tr3_tx24_htfnone_obs3_fav40_adv100` | `observe_then_enter` | `21289` | `3913` | `2431` | `0.64` | `29.45%` | `1.53` | `-0.21%` | `-99.52%` |
| `observe_then_enter_ema21_96_pb0.01_sl2_tr3_tx24_htfnone_obs3_fav0_adv100` | `observe_then_enter` | `21289` | `10366` | `4265` | `0.62` | `28.98%` | `1.52` | `-0.19%` | `-99.98%` |

## Gate

- Candidate: full trades `>=180`, IS trades `>=80`, validation trades `>=30`, forward trades `>=8`, full PF `>=1.25`, IS PF `>=1.15`, validation PF `>=1.05`, average trade `>0`, payoff `>1`, max drawdown no worse than `-25%`.
- Watchlist: full trades `>=50`, IS trades `>=30`, validation trades `>=10`, full PF `>=1.50`, IS PF `>=1.30`, validation PF `>=1.05`, average trade `>0`, max drawdown no worse than `-20%`.

The search mines conjunction rules on the IS period only using independent event outcomes, then each mined rule is replayed exactly as a live executable strategy.

## Passing Candidates

| baseline | rule | trades | PF | IS PF | VAL PF | FWD PF | win | payoff | avg | DD | freq/mo |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `observe_then_enter_ema21_96_pb0.01_sl2_tr3_tx24_htfnone_obs3_fav40_adv100` | `opp_wick_atr <= 0 & abs_ema_spread_bps <= 92.9084` | `180` | `1.25` | `1.27` | `1.29` | `1.06` | `35.56%` | `2.27` | `0.11%` | `-10.37%` | `14.1` |
| `observe_then_enter_ema21_96_pb0.01_sl2_tr3_tx24_htfnone_obs3_fav40_adv100` | `opp_wick_atr <= 0 & ema_spread_bps <= 92.9084` | `180` | `1.25` | `1.27` | `1.29` | `1.06` | `35.56%` | `2.27` | `0.11%` | `-10.37%` | `14.1` |

## Watchlist

| baseline | rule | trades | PF | IS PF | VAL PF | FWD PF | win | payoff | avg | DD | freq/mo |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `protected_entry_ema21_96_pb0.01_sl2_tr4_tx48_htfnone_obs0_fav0_advnone` | `day_of_week <= 1 & hour <= 1 & atr_ratio_14_96 <= 0.962276` | `76` | `1.98` | `2.01` | `2.41` | `0.15` | `36.84%` | `3.39` | `0.43%` | `-7.72%` | `6.0` |
| `protected_entry_ema21_96_pb0.01_sl2_tr4_tx48_htfnone_obs0_fav0_advnone` | `hour <= 1 & regime_age >= 110 & day_of_week <= 2` | `69` | `2.07` | `2.24` | `1.24` | `2.15` | `43.48%` | `2.69` | `0.51%` | `-9.98%` | `5.4` |
| `protected_entry_ema21_96_pb0.01_sl2_tr4_tx48_htfnone_obs0_fav0_advnone` | `day_of_week <= 1 & hour <= 1 & regime_age >= 94` | `53` | `2.19` | `2.32` | `1.63` | `0.00` | `45.28%` | `2.65` | `0.57%` | `-5.10%` | `4.2` |
| `protected_entry_ema21_96_pb0.01_sl2_tr4_tx48_htfnone_obs0_fav0_advnone` | `dir_roc48_bps >= 449.027 & regime_age >= 94 & atr_bps <= 84.177` | `52` | `1.88` | `1.97` | `1.89` | `0.00` | `38.46%` | `3.01` | `0.63%` | `-9.55%` | `4.1` |
| `protected_entry_ema21_96_pb0.01_sl3_tr4_tx48_htfnone_obs0_fav0_advnone` | `day_of_week <= 1 & hour <= 2 & atr_bps <= 38.5125` | `79` | `2.32` | `2.95` | `1.38` | `0.00` | `44.30%` | `2.92` | `0.49%` | `-5.53%` | `6.2` |
| `protected_entry_ema21_96_pb0.01_sl2_tr4_tx48_htfnone_obs0_fav0_advnone` | `day_of_week <= 1 & hour <= 2 & regime_age >= 110` | `51` | `2.24` | `2.46` | `1.42` | `0.00` | `45.10%` | `2.72` | `0.56%` | `-5.41%` | `4.0` |
| `protected_entry_ema21_96_pb0.01_sl2_tr4_tx48_htfnone_obs0_fav0_advnone` | `dir_roc192_bps >= 819.831 & hour >= 19` | `57` | `1.58` | `1.63` | `2.34` | `0.48` | `38.60%` | `2.51` | `0.45%` | `-18.52%` | `4.5` |
| `protected_entry_ema21_96_pb0.01_sl3_tr4_tx48_htfnone_obs0_fav0_advnone` | `dir_roc192_bps >= 819.831 & hour >= 19` | `54` | `1.61` | `1.73` | `1.98` | `0.47` | `42.59%` | `2.17` | `0.52%` | `-17.09%` | `4.2` |
| `protected_entry_ema21_96_pb0.01_sl2_tr4_tx48_htfnone_obs0_fav0_advnone` | `dir_roc192_bps >= 819.831 & dir_roc48_bps >= 449.027 & atr_bps <= 84.177` | `52` | `2.05` | `2.62` | `1.19` | `0.00` | `44.23%` | `2.59` | `0.70%` | `-7.48%` | `4.1` |
| `protected_entry_ema21_96_pb0.01_sl3_tr4_tx48_htfnone_obs0_fav0_advnone` | `day_of_week <= 1 & hour <= 1 & atr_ratio_14_96 <= 0.962276` | `70` | `1.83` | `1.88` | `1.81` | `0.26` | `41.43%` | `2.58` | `0.42%` | `-8.11%` | `5.5` |
| `protected_entry_ema21_96_pb0.01_sl3_tr4_tx48_htfnone_obs0_fav0_advnone` | `regime_age >= 210 & dir_roc192_bps >= 819.831` | `56` | `1.75` | `1.96` | `1.79` | `0.25` | `46.43%` | `2.02` | `0.48%` | `-7.83%` | `4.4` |
| `observe_then_enter_ema21_96_pb0.01_sl2_tr3_tx24_htfnone_obs3_fav0_adv100` | `hour <= 3 & regime_age >= 112 & day_of_week <= 2 & range_atr >= 0.767951` | `72` | `1.63` | `1.72` | `1.73` | `0.52` | `45.83%` | `1.93` | `0.26%` | `-6.00%` | `5.6` |

## Best Exact Replays

| baseline | rule | trades | PF | IS PF | VAL PF | FWD PF | win | payoff | avg | DD | freq/mo |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `protected_entry_ema21_96_pb0.01_sl2_tr4_tx48_htfnone_obs0_fav0_advnone` | `dir_roc192_bps >= 819.831 & hour >= 20` | `41` | `1.96` | `1.62` | `3.43` | `∞` | `43.90%` | `2.50` | `0.66%` | `-19.79%` | `3.2` |
| `protected_entry_ema21_96_pb0.01_sl2_tr4_tx48_htfnone_obs0_fav0_advnone` | `dir_roc192_bps >= 819.831 & day_of_week <= 1 & dir_roc48_bps >= 306.178 & regime_age >= 94` | `35` | `2.15` | `2.12` | `9.49` | `1.52` | `40.00%` | `3.23` | `0.77%` | `-9.60%` | `2.7` |
| `protected_entry_ema21_96_pb0.01_sl3_tr4_tx48_htfnone_obs0_fav0_advnone` | `htf_spread_bps >= 358.134 & dir_roc48_bps >= 267.639 & day_of_week <= 1` | `36` | `1.89` | `1.72` | `7.95` | `9.35` | `41.67%` | `2.64` | `0.69%` | `-16.98%` | `2.8` |
| `protected_entry_ema21_96_pb0.01_sl2_tr4_tx48_htfnone_obs0_fav0_advnone` | `dir_roc192_bps >= 819.831 & day_of_week <= 2 & hour >= 16` | `39` | `2.41` | `2.36` | `9.15` | `0.00` | `46.15%` | `2.81` | `0.79%` | `-6.81%` | `3.1` |
| `protected_entry_ema21_96_pb0.01_sl3_tr4_tx48_htfnone_obs0_fav0_advnone` | `day_of_week <= 1 & dir_roc192_bps >= 819.831 & dir_roc48_bps >= 306.178 & regime_age >= 94` | `34` | `2.04` | `2.00` | `9.49` | `1.52` | `41.18%` | `2.91` | `0.75%` | `-10.51%` | `2.7` |
| `protected_entry_ema21_96_pb0.01_sl3_tr4_tx48_htfnone_obs0_fav0_advnone` | `dir_roc192_bps >= 819.831 & day_of_week <= 2 & hour >= 16` | `37` | `2.29` | `2.45` | `6.50` | `0.00` | `48.65%` | `2.42` | `0.81%` | `-7.14%` | `2.9` |
| `protected_entry_ema21_96_pb0.01_sl2_tr4_tx48_htfnone_obs0_fav0_advnone` | `dir_roc192_bps >= 819.831 & hour >= 17 & side >= 1` | `42` | `2.22` | `2.26` | `2.07` | `∞` | `42.86%` | `2.97` | `0.79%` | `-10.30%` | `3.3` |
| `protected_entry_ema21_96_pb0.01_sl3_tr4_tx48_htfnone_obs0_fav0_advnone` | `dir_roc192_bps >= 819.831 & hour >= 20` | `40` | `1.82` | `1.53` | `2.84` | `∞` | `45.00%` | `2.22` | `0.62%` | `-18.36%` | `3.1` |
| `protected_entry_ema21_96_pb0.01_sl2_tr4_tx48_htfnone_obs0_fav0_advnone` | `htf_spread_bps >= 358.134 & dir_roc48_bps >= 267.639 & day_of_week <= 1` | `40` | `1.73` | `1.57` | `7.95` | `9.35` | `37.50%` | `2.89` | `0.56%` | `-18.11%` | `3.1` |
| `protected_entry_ema21_55_pb0.01_sl2_tr4_tx24_htf0.5_obs0_fav0_advnone` | `dir_roc384_bps >= 1517.16 & day_of_week <= 2` | `45` | `1.71` | `1.61` | `∞` | `2.71` | `51.11%` | `1.64` | `0.47%` | `-9.77%` | `3.5` |
| `protected_entry_ema21_96_pb0.01_sl3_tr4_tx48_htfnone_obs0_fav0_advnone` | `dir_roc192_bps >= 819.831 & side >= 1 & hour >= 17` | `41` | `1.91` | `1.95` | `1.75` | `∞` | `43.90%` | `2.44` | `0.70%` | `-12.45%` | `3.2` |
| `protected_entry_ema21_96_pb0.01_sl2_tr4_tx48_htfnone_obs0_fav0_advnone` | `htf_spread_bps >= 358.134 & dir_roc48_bps >= 306.178 & day_of_week <= 2` | `45` | `1.61` | `1.55` | `19.79` | `1.25` | `37.78%` | `2.66` | `0.46%` | `-15.41%` | `3.5` |

## Higher-Frequency Rows

Rows with at least `180` full-sample trades. These are closer to the desired validation cadence, but must still pass validation stability.

| baseline | rule | trades | PF | IS PF | VAL PF | FWD PF | win | payoff | avg | DD | freq/mo |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `observe_then_enter_ema21_96_pb0.01_sl2_tr3_tx24_htfnone_obs3_fav40_adv100` | `opp_wick_atr <= 0 & abs_ema_spread_bps <= 92.9084` | `180` | `1.25` | `1.27` | `1.29` | `1.06` | `35.56%` | `2.27` | `0.11%` | `-10.37%` | `14.1` |
| `observe_then_enter_ema21_96_pb0.01_sl2_tr3_tx24_htfnone_obs3_fav40_adv100` | `opp_wick_atr <= 0 & ema_spread_bps <= 92.9084` | `180` | `1.25` | `1.27` | `1.29` | `1.06` | `35.56%` | `2.27` | `0.11%` | `-10.37%` | `14.1` |
| `observe_then_enter_ema21_96_pb0.01_sl2_tr3_tx24_htfnone_obs3_fav40_adv100` | `opp_wick_atr <= 0 & ema_spread_bps <= 102.193` | `190` | `1.24` | `1.28` | `1.22` | `1.02` | `35.79%` | `2.23` | `0.10%` | `-11.32%` | `14.9` |
| `observe_then_enter_ema21_96_pb0.01_sl2_tr3_tx24_htfnone_obs3_fav40_adv100` | `opp_wick_atr <= 0 & abs_ema_spread_bps <= 102.193` | `190` | `1.24` | `1.28` | `1.22` | `1.02` | `35.79%` | `2.23` | `0.10%` | `-11.32%` | `14.9` |
| `observe_then_enter_ema21_96_pb0.01_sl2_tr3_tx24_htfnone_obs3_fav40_adv100` | `opp_wick_atr <= 0 & abs_ema_spread_bps <= 112.688` | `198` | `1.12` | `1.15` | `1.15` | `0.89` | `34.85%` | `2.10` | `0.06%` | `-12.64%` | `15.5` |
| `observe_then_enter_ema21_96_pb0.01_sl2_tr3_tx24_htfnone_obs3_fav40_adv100` | `opp_wick_atr <= 0 & ema_spread_bps <= 112.688` | `198` | `1.12` | `1.15` | `1.15` | `0.89` | `34.85%` | `2.10` | `0.06%` | `-12.64%` | `15.5` |
| `observe_then_enter_ema21_96_pb0.01_sl2_tr3_tx24_htfnone_obs3_fav0_adv100` | `opp_wick_atr >= 0.682263 & atr_ratio_14_96 >= 0.994477` | `192` | `1.06` | `1.19` | `0.89` | `0.40` | `38.54%` | `1.69` | `0.03%` | `-22.43%` | `15.1` |
| `observe_then_enter_ema21_96_pb0.01_sl2_tr3_tx24_htfnone_obs3_fav40_adv100` | `abs_ema_spread_bps <= 68.2164 & opp_wick_atr <= 0.0133374` | `194` | `1.06` | `1.13` | `0.83` | `0.85` | `32.99%` | `2.15` | `0.03%` | `-13.52%` | `15.2` |
| `observe_then_enter_ema21_96_pb0.01_sl2_tr3_tx24_htfnone_obs3_fav40_adv100` | `ema_spread_bps <= 68.2164 & opp_wick_atr <= 0.0133374` | `194` | `1.06` | `1.13` | `0.83` | `0.85` | `32.99%` | `2.15` | `0.03%` | `-13.52%` | `15.2` |
| `observe_then_enter_ema21_96_pb0.01_sl2_tr3_tx24_htfnone_obs3_fav40_adv100` | `hour >= 21 & opp_wick_atr >= 0.190384` | `183` | `1.02` | `1.25` | `0.66` | `0.26` | `37.16%` | `1.73` | `0.01%` | `-18.81%` | `14.4` |
| `observe_then_enter_ema21_96_pb0.01_sl2_tr3_tx24_htfnone_obs3_fav0_adv100` | `day_of_week <= 1 & hour <= 3` | `222` | `1.02` | `1.09` | `0.53` | `2.26` | `38.29%` | `1.65` | `0.01%` | `-16.96%` | `17.4` |
| `observe_then_enter_ema21_96_pb0.01_sl2_tr3_tx24_htfnone_obs3_fav0_adv100` | `opp_wick_atr >= 0.682263 & dir_roc6_bps >= 63.3222` | `208` | `1.01` | `1.12` | `0.63` | `0.53` | `35.58%` | `1.84` | `0.01%` | `-22.18%` | `16.3` |

## Interpretation

`opp_wick_atr <= 0 & abs_ema_spread_bps <= 92.9084` is the first V5.1 event-quality candidate that passes the mechanical gate. It should not be promoted directly to live until ablation, rolling-window diagnostics, and side-specific replay are finished.

## Decision

Do not draft a V5.1 live spec yet. The useful discovery is narrower: quality filtering can flip expectancy only after converting the original trigger into an observation-confirmed event stream and rejecting weak-quality candles. The first higher-frequency candidate barely clears the mechanical gate, so it must be treated as a research candidate rather than a live strategy.

Recommended next step: V5.2 should model signal quality as a walk-forward event-ranking problem. The live candidate should trade only if the same feature family keeps positive validation PF while maintaining a minimum trade cadence, rather than hand-picking a sparse high-PF subset.

## Outputs

- Script: `research/hype/families/5m-pullback-trail/scripts/research_hype_5m_pbtr_v51_event_quality.py`
- JSON: `artifacts/hype_5m_pbtr_v51_event_quality.json`
- Baseline CSV: `artifacts/hype_5m_pbtr_v51_event_quality_summary.csv`
- Exact rule CSV: `artifacts/hype_5m_pbtr_v51_event_quality_exact_rules.csv`
