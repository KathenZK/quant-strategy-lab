# HYPE-5M-PBTR-V5 Executable Search 2026-06-24

Family id: `HYPE-5M-PBTR`

This is the first executable-first V5 search after V3.3/V4 failed live-realistic trailing audits. The search rejects the old hidden lockout model and tests only states that can be placed as real orders.

## Executable Models

- `protected_entry`: enter after a closed pullback signal and activate a protective stop immediately.
- `observe_then_enter`: treat the pullback signal as an observation trigger, enter only after confirmation bars, and activate a protective stop immediately after entry.

Both models use observed live cost assumptions: fee `4.1466 bps/fill`, entry slippage `10.73 bps`, and exit slippage `2.64 bps`. Stop gaps and crossed stops are market exits, never fills at an already-crossed stop price.

## V5 Gate

- Full-sample trades `>=500`.
- Full-sample PF `>=1.30`.
- Worst validation-slice PF `>=1.05`.
- Payoff `>=1.20`.
- Average trade after costs `>0`.
- Max drawdown at 1x no worse than `-25%`.
- Profitable months at least `8/14`.

## Passing Candidates

No rows.

## Watchlist

Rows here do not pass V5 gate but are positive enough to inspect if no full candidate exists.

No rows.

## Best Overall By PF

| model | EMA | obs | fav | adv | stop | trail | time | htf | trades | PF | minPF | win | payoff | avg | DD | months |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `protected_entry` | `21/96` | `0` | `0` | `none` | `3` | `4` | `48` | `none` | `3732` | `0.69` | `0.62` | `30.68%` | `1.55` | `-0.21%` | `-99.97%` | `0/14` |
| `protected_entry` | `21/55` | `0` | `0` | `none` | `2` | `4` | `24` | `0.5` | `1773` | `0.68` | `0.61` | `32.54%` | `1.42` | `-0.20%` | `-97.67%` | `0/14` |
| `protected_entry` | `21/72` | `0` | `0` | `none` | `2` | `4` | `24` | `0.5` | `1811` | `0.68` | `0.62` | `32.91%` | `1.39` | `-0.20%` | `-97.90%` | `0/14` |
| `protected_entry` | `21/55` | `0` | `0` | `none` | `2` | `4` | `24` | `0.5` | `1796` | `0.68` | `0.59` | `31.90%` | `1.44` | `-0.21%` | `-98.04%` | `1/14` |
| `protected_entry` | `21/96` | `0` | `0` | `none` | `3` | `4` | `96` | `none` | `3367` | `0.67` | `0.58` | `30.29%` | `1.55` | `-0.21%` | `-99.95%` | `0/14` |
| `protected_entry` | `21/55` | `0` | `0` | `none` | `3` | `4` | `48` | `none` | `3879` | `0.67` | `0.59` | `30.57%` | `1.53` | `-0.22%` | `-99.99%` | `0/14` |
| `protected_entry` | `21/72` | `0` | `0` | `none` | `3` | `4` | `48` | `none` | `3819` | `0.67` | `0.59` | `30.56%` | `1.52` | `-0.22%` | `-99.99%` | `0/14` |
| `protected_entry` | `21/96` | `0` | `0` | `none` | `3` | `4` | `48` | `none` | `3776` | `0.67` | `0.61` | `30.56%` | `1.52` | `-0.22%` | `-99.98%` | `0/14` |
| `protected_entry` | `21/96` | `0` | `0` | `none` | `2` | `4` | `48` | `0.5` | `1478` | `0.67` | `0.55` | `26.12%` | `1.89` | `-0.22%` | `-96.92%` | `0/14` |
| `protected_entry` | `21/55` | `0` | `0` | `none` | `2` | `4` | `48` | `0.5` | `1397` | `0.67` | `0.54` | `26.49%` | `1.86` | `-0.22%` | `-96.11%` | `1/14` |
| `protected_entry` | `21/72` | `0` | `0` | `none` | `2` | `4` | `24` | `0.5` | `1838` | `0.67` | `0.60` | `32.32%` | `1.40` | `-0.21%` | `-98.33%` | `0/14` |
| `protected_entry` | `21/55` | `0` | `0` | `none` | `3` | `4` | `96` | `none` | `3504` | `0.67` | `0.57` | `29.97%` | `1.56` | `-0.22%` | `-99.97%` | `0/14` |
| `protected_entry` | `21/96` | `0` | `0` | `none` | `2` | `4` | `24` | `0.5` | `1877` | `0.67` | `0.60` | `32.45%` | `1.39` | `-0.21%` | `-98.44%` | `0/14` |
| `protected_entry` | `13/96` | `0` | `0` | `none` | `3` | `4` | `48` | `none` | `3925` | `0.67` | `0.60` | `30.52%` | `1.52` | `-0.22%` | `-99.99%` | `0/14` |
| `protected_entry` | `21/72` | `0` | `0` | `none` | `2` | `4` | `48` | `0.5` | `1423` | `0.67` | `0.56` | `26.35%` | `1.86` | `-0.22%` | `-96.42%` | `0/14` |
| `protected_entry` | `21/96` | `0` | `0` | `none` | `3` | `4` | `48` | `0.5` | `1268` | `0.67` | `0.54` | `30.76%` | `1.50` | `-0.25%` | `-96.75%` | `2/14` |
| `protected_entry` | `13/96` | `0` | `0` | `none` | `3` | `4` | `48` | `none` | `3929` | `0.67` | `0.60` | `30.52%` | `1.52` | `-0.22%` | `-99.99%` | `0/14` |
| `protected_entry` | `21/96` | `0` | `0` | `none` | `2` | `4` | `48` | `none` | `4463` | `0.67` | `0.61` | `26.01%` | `1.89` | `-0.19%` | `-99.99%` | `0/14` |
| `protected_entry` | `21/55` | `0` | `0` | `none` | `3` | `4` | `48` | `none` | `3913` | `0.66` | `0.58` | `30.44%` | `1.52` | `-0.22%` | `-99.99%` | `0/14` |
| `protected_entry` | `21/96` | `0` | `0` | `none` | `3` | `4` | `96` | `none` | `3407` | `0.66` | `0.58` | `30.11%` | `1.54` | `-0.23%` | `-99.97%` | `0/14` |

## Best Protected-Entry Rows

| model | EMA | obs | fav | adv | stop | trail | time | htf | trades | PF | minPF | win | payoff | avg | DD | months |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `protected_entry` | `21/96` | `0` | `0` | `none` | `3` | `4` | `48` | `none` | `3732` | `0.69` | `0.62` | `30.68%` | `1.55` | `-0.21%` | `-99.97%` | `0/14` |
| `protected_entry` | `21/55` | `0` | `0` | `none` | `2` | `4` | `24` | `0.5` | `1773` | `0.68` | `0.61` | `32.54%` | `1.42` | `-0.20%` | `-97.67%` | `0/14` |
| `protected_entry` | `21/72` | `0` | `0` | `none` | `2` | `4` | `24` | `0.5` | `1811` | `0.68` | `0.62` | `32.91%` | `1.39` | `-0.20%` | `-97.90%` | `0/14` |
| `protected_entry` | `21/55` | `0` | `0` | `none` | `2` | `4` | `24` | `0.5` | `1796` | `0.68` | `0.59` | `31.90%` | `1.44` | `-0.21%` | `-98.04%` | `1/14` |
| `protected_entry` | `21/96` | `0` | `0` | `none` | `3` | `4` | `96` | `none` | `3367` | `0.67` | `0.58` | `30.29%` | `1.55` | `-0.21%` | `-99.95%` | `0/14` |
| `protected_entry` | `21/55` | `0` | `0` | `none` | `3` | `4` | `48` | `none` | `3879` | `0.67` | `0.59` | `30.57%` | `1.53` | `-0.22%` | `-99.99%` | `0/14` |
| `protected_entry` | `21/72` | `0` | `0` | `none` | `3` | `4` | `48` | `none` | `3819` | `0.67` | `0.59` | `30.56%` | `1.52` | `-0.22%` | `-99.99%` | `0/14` |
| `protected_entry` | `21/96` | `0` | `0` | `none` | `3` | `4` | `48` | `none` | `3776` | `0.67` | `0.61` | `30.56%` | `1.52` | `-0.22%` | `-99.98%` | `0/14` |
| `protected_entry` | `21/96` | `0` | `0` | `none` | `2` | `4` | `48` | `0.5` | `1478` | `0.67` | `0.55` | `26.12%` | `1.89` | `-0.22%` | `-96.92%` | `0/14` |
| `protected_entry` | `21/55` | `0` | `0` | `none` | `2` | `4` | `48` | `0.5` | `1397` | `0.67` | `0.54` | `26.49%` | `1.86` | `-0.22%` | `-96.11%` | `1/14` |
| `protected_entry` | `21/72` | `0` | `0` | `none` | `2` | `4` | `24` | `0.5` | `1838` | `0.67` | `0.60` | `32.32%` | `1.40` | `-0.21%` | `-98.33%` | `0/14` |
| `protected_entry` | `21/55` | `0` | `0` | `none` | `3` | `4` | `96` | `none` | `3504` | `0.67` | `0.57` | `29.97%` | `1.56` | `-0.22%` | `-99.97%` | `0/14` |

## Best Observation-Then-Entry Rows

| model | EMA | obs | fav | adv | stop | trail | time | htf | trades | PF | minPF | win | payoff | avg | DD | months |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `observe_then_enter` | `21/96` | `3` | `40` | `100` | `2` | `3` | `24` | `none` | `2431` | `0.64` | `0.57` | `29.45%` | `1.53` | `-0.21%` | `-99.52%` | `0/14` |
| `observe_then_enter` | `21/96` | `3` | `40` | `200` | `2` | `3` | `24` | `none` | `2436` | `0.64` | `0.57` | `29.52%` | `1.52` | `-0.21%` | `-99.54%` | `0/14` |
| `observe_then_enter` | `21/55` | `3` | `40` | `100` | `2` | `3` | `24` | `0.5` | `846` | `0.63` | `0.40` | `29.08%` | `1.54` | `-0.24%` | `-88.25%` | `2/14` |
| `observe_then_enter` | `21/55` | `3` | `40` | `200` | `2` | `3` | `24` | `0.5` | `848` | `0.63` | `0.40` | `29.13%` | `1.54` | `-0.24%` | `-88.34%` | `2/14` |
| `observe_then_enter` | `21/55` | `3` | `40` | `100` | `2` | `3` | `24` | `none` | `2556` | `0.63` | `0.54` | `29.34%` | `1.52` | `-0.21%` | `-99.68%` | `0/14` |
| `observe_then_enter` | `21/55` | `3` | `40` | `200` | `2` | `3` | `24` | `none` | `2561` | `0.63` | `0.53` | `29.44%` | `1.51` | `-0.22%` | `-99.69%` | `0/14` |
| `observe_then_enter` | `21/55` | `1` | `40` | `100` | `2` | `3` | `24` | `none` | `1432` | `0.62` | `0.51` | `30.24%` | `1.43` | `-0.24%` | `-97.52%` | `1/14` |
| `observe_then_enter` | `21/55` | `12` | `0` | `200` | `2` | `3` | `24` | `0.5` | `1017` | `0.62` | `0.46` | `29.30%` | `1.50` | `-0.22%` | `-89.73%` | `2/14` |
| `observe_then_enter` | `21/96` | `3` | `0` | `100` | `2` | `3` | `24` | `none` | `4265` | `0.62` | `0.55` | `28.98%` | `1.52` | `-0.19%` | `-99.98%` | `0/14` |
| `observe_then_enter` | `21/96` | `3` | `40` | `100` | `2` | `3` | `24` | `0.5` | `899` | `0.62` | `0.44` | `28.81%` | `1.53` | `-0.25%` | `-90.25%` | `1/14` |
| `observe_then_enter` | `21/96` | `3` | `40` | `200` | `2` | `3` | `24` | `0.5` | `901` | `0.62` | `0.45` | `28.86%` | `1.53` | `-0.25%` | `-90.33%` | `1/14` |
| `observe_then_enter` | `21/96` | `3` | `20` | `100` | `2` | `3` | `24` | `none` | `3420` | `0.62` | `0.53` | `28.83%` | `1.53` | `-0.21%` | `-99.94%` | `0/14` |

## Decision

No row is positive enough for a watchlist. Under executable order semantics, the current pullback-trailing family still does not have a live-tradable edge.

## Event-Quality Probe

After the executable search, I also ran a small single-feature event-quality probe on the two least-bad executable baselines:

- `protected_entry_ema21_96_pb0.01_sl3_tr4_tx48_htfnone`
- `observe_then_enter_ema21_96_pb0.01_sl2_tr3_tx24_htfnone_obs3_fav40_adv100`

The probe filtered events by one feature at a time, using event-time values such as `ema_spread_bps`, `dir_roc12/24/48/96`, `CHOP14`, `ATR bps`, `range_atr`, `body_bps`, `dist_ema_bps`, and `dir_htf`.

Best observed rows:

| Base | Filter | Trades | PF | Min slice PF | Avg trade | Max DD |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `observe_then_enter` | `ema_spread_bps <= 26.78` | `381` | `0.83` | `0.59` | `-0.08%` | `-42.51%` |
| `observe_then_enter` | `CHOP14 <= 34.53` | `346` | `0.82` | `0.53` | `-0.09%` | `-39.69%` |
| `observe_then_enter` | `dir_roc96_bps <= 62.76` | `338` | `0.82` | `0.66` | `-0.09%` | `-41.44%` |
| `protected_entry` | `dir_roc96_bps <= -7.18` | `946` | `0.82` | `0.60` | `-0.11%` | `-81.36%` |

No single-feature filter reached PF `1`, and no subset had positive average trade after observed live costs. This does not prove that a richer event-quality model can never work, but it does show that the obvious one-dimensional quality filters are not enough.

## Decision

No V5 direct-rule candidate is live handoff ready. Under executable order semantics, the current pullback-trailing family still does not have a live-tradable edge.

Recommendation: do not keep widening stops or adding simple filters around this same rule. The next research step, if any, must be a proper event-quality dataset with leakage-safe time splits, or this 5m pullback-trailing line should be abandoned.

## Outputs

- Script: `archive/scripts/research/research_hype_5m_pbtr_v5_executable_search.py`
- JSON: `reports/hype_5m_pbtr_v5_executable_search.json`
- Summary CSV: `reports/hype_5m_pbtr_v5_executable_search_summary.csv`
- Slice CSV: `reports/hype_5m_pbtr_v5_executable_search_slices.csv`
