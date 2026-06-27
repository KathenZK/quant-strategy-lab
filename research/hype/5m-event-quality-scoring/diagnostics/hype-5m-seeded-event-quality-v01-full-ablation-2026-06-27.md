# HYPE-5M-Event-Quality-Scoring Seeded V0.1 Full Ablation

生成日期：`2026-06-27`

## 结论

- 诊断窗口：`2025-06-26 04:20:00+00:00` 到 `2026-06-26 04:20:00+00:00`。
- 消融维度：`6` 个事件源集合 × `7` 个打分公式 × `7` 个分位数门槛。
- 稳定性门槛排序首位：`no_wick_no_breakout__cfg_side_88_12__q80`，全年收益 `287.61%`，PF `1.425`，最大回撤 `-16.30%`。
- 目标精简版 `no_wick_no_breakout__current_70_20_10__q80`：全年收益 `238.78%`，PF `1.383`，最大回撤 `-16.75%`，gate `True`。

注意：这是固定 seed universe 的全参数消融，不是严格无前视 OOS。`2026-03-01` 之前的分段仍受 seed-selection 前视影响。

## 数据质量

- 数据范围：`2025-05-30 10:30:00+00:00` 到 `2026-06-26 04:15:00+00:00`。
- 行数：`112822`，缺口：`0`。
- raw/normalized 对齐：`True`。

## Top Candidates

| rank | candidate | trades | ret | PF | win | avg bps | DD | recent3m | neg months | gate |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | `no_wick_no_breakout__cfg_side_88_12__q80` | 549 | 287.61% | 1.425 | 59.02% | 26.33 | -16.30% | 24.59% | 1/13 | True |
| 2 | `no_wick_no_breakout__cfg_only__q80` | 547 | 272.16% | 1.411 | 58.87% | 25.69 | -16.15% | 24.82% | 1/13 | True |
| 3 | `no_wick_no_breakout__current_70_20_10__q80` | 545 | 238.78% | 1.383 | 59.08% | 24.05 | -16.75% | 25.33% | 2/13 | True |
| 4 | `no_wick_no_breakout__cfg_style_78_22__q80` | 553 | 234.36% | 1.372 | 58.59% | 23.49 | -16.75% | 25.33% | 2/13 | True |
| 5 | `core_bb_vwap_macd__cfg_side_88_12__q80` | 477 | 227.80% | 1.397 | 58.70% | 26.76 | -16.81% | 38.48% | 3/13 | True |
| 6 | `core_bb_vwap_macd__cfg_only__q80` | 473 | 217.97% | 1.388 | 58.14% | 26.36 | -16.81% | 38.67% | 3/13 | True |
| 7 | `bb_vwap_only__current_70_20_10__q85` | 347 | 194.31% | 1.489 | 61.38% | 33.06 | -10.79% | 34.77% | 1/13 | True |
| 8 | `bb_vwap_only__cfg_only__q80` | 422 | 188.39% | 1.396 | 59.72% | 26.97 | -19.64% | 37.53% | 4/13 | True |
| 9 | `core_bb_vwap_macd__cfg_only__q90` | 281 | 182.18% | 1.558 | 62.99% | 39.22 | -15.04% | 39.47% | 1/13 | True |
| 10 | `core_bb_vwap_macd__equal_weight__q85` | 405 | 181.11% | 1.403 | 60.25% | 27.46 | -16.46% | 62.18% | 4/13 | True |
| 11 | `core_bb_vwap_macd__current_70_20_10__q90` | 289 | 179.44% | 1.534 | 62.98% | 37.82 | -15.04% | 36.94% | 1/13 | True |
| 12 | `core_bb_vwap_macd__cfg_style_78_22__q90` | 291 | 177.99% | 1.527 | 62.89% | 37.39 | -15.04% | 38.97% | 1/13 | True |
| 13 | `no_wick__equal_weight__q85` | 479 | 177.59% | 1.364 | 58.66% | 22.96 | -16.18% | 35.77% | 4/13 | True |
| 14 | `bb_vwap_only__cfg_style_78_22__q85` | 333 | 176.38% | 1.467 | 61.56% | 32.56 | -10.79% | 36.63% | 1/13 | True |
| 15 | `core_bb_vwap_macd__cfg_side_88_12__q90` | 283 | 175.15% | 1.532 | 62.90% | 38.10 | -15.04% | 39.47% | 1/13 | True |
| 16 | `bb_vwap_only__cfg_side_88_12__q85` | 347 | 174.32% | 1.447 | 61.10% | 31.09 | -13.96% | 34.77% | 2/13 | True |
| 17 | `bb_vwap_only__cfg_side_88_12__q80` | 444 | 168.44% | 1.347 | 59.23% | 24.10 | -16.63% | 37.53% | 4/13 | True |
| 18 | `core_bb_vwap_macd__cfg_style_78_22__q80` | 469 | 163.49% | 1.323 | 57.36% | 22.58 | -17.98% | 31.64% | 2/13 | True |
| 19 | `bb_vwap_only__cfg_only__q85` | 341 | 156.17% | 1.423 | 60.70% | 29.59 | -13.96% | 36.63% | 2/13 | True |
| 20 | `no_wick_no_breakout__cfg_style_78_22__q90` | 356 | 149.04% | 1.410 | 59.55% | 27.54 | -13.62% | 17.36% | 3/13 | True |
| 21 | `bb_vwap_only__cfg_side_88_12__q90` | 249 | 148.77% | 1.547 | 63.05% | 38.85 | -10.19% | 24.63% | 2/13 | True |
| 22 | `no_wick_no_breakout__cfg_only__q90` | 362 | 148.22% | 1.397 | 59.39% | 27.05 | -13.62% | 26.87% | 4/13 | True |
| 23 | `no_wick__cfg_side_88_12__q80` | 572 | 145.42% | 1.262 | 56.29% | 17.32 | -14.77% | 17.42% | 4/13 | True |
| 24 | `no_wick_no_breakout__cfg_side_88_12__q90` | 358 | 140.87% | 1.387 | 59.22% | 26.50 | -14.60% | 26.87% | 3/13 | True |
| 25 | `bb_vwap_only__current_70_20_10__q90` | 247 | 139.64% | 1.525 | 62.75% | 37.64 | -13.03% | 24.63% | 3/13 | True |

## Best By Style Set

| style_set | best candidate | trades | ret | PF | avg bps | DD | recent3m | gate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `base_all` | `base_all__cfg_only__q60` | 818 | 179.93% | 1.206 | 14.32 | -30.50% | -6.39% | False |
| `bb_vwap_only` | `bb_vwap_only__current_70_20_10__q85` | 347 | 194.31% | 1.489 | 33.06 | -10.79% | 34.77% | True |
| `core_bb_vwap_macd` | `core_bb_vwap_macd__cfg_side_88_12__q80` | 477 | 227.80% | 1.397 | 26.76 | -16.81% | 38.48% | True |
| `mean_revert_bb_vwap_rsi` | `mean_revert_bb_vwap_rsi__cfg_side_88_12__q90` | 321 | 124.41% | 1.386 | 27.17 | -10.54% | 20.49% | True |
| `no_wick` | `no_wick__equal_weight__q85` | 479 | 177.59% | 1.364 | 22.96 | -16.18% | 35.77% | True |
| `no_wick_no_breakout` | `no_wick_no_breakout__cfg_side_88_12__q80` | 549 | 287.61% | 1.425 | 26.33 | -16.30% | 24.59% | True |

## Best By Score Variant

| variant | best candidate | trades | ret | PF | avg bps | DD | recent3m | gate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `cfg_only` | `no_wick_no_breakout__cfg_only__q80` | 547 | 272.16% | 1.411 | 25.69 | -16.15% | 24.82% | True |
| `cfg_side_88_12` | `no_wick_no_breakout__cfg_side_88_12__q80` | 549 | 287.61% | 1.425 | 26.33 | -16.30% | 24.59% | True |
| `cfg_style_78_22` | `no_wick_no_breakout__cfg_style_78_22__q80` | 553 | 234.36% | 1.372 | 23.49 | -16.75% | 25.33% | True |
| `current_70_20_10` | `no_wick_no_breakout__current_70_20_10__q80` | 545 | 238.78% | 1.383 | 24.05 | -16.75% | 25.33% | True |
| `equal_weight` | `core_bb_vwap_macd__equal_weight__q85` | 405 | 181.11% | 1.403 | 27.46 | -16.46% | 62.18% | True |
| `side_only` | `mean_revert_bb_vwap_rsi__side_only__q80` | 598 | 41.67% | 1.113 | 7.00 | -33.83% | -15.35% | False |
| `style_only` | `base_all__style_only__q70` | 723 | 71.81% | 1.149 | 8.63 | -24.49% | -7.78% | False |

## Top Windows: `no_wick_no_breakout__cfg_side_88_12__q80`

| window | trades | ret | PF | avg bps | DD |
| --- | ---: | ---: | ---: | ---: | ---: |
| `recent_1w` | 11 | 10.11% | 2.617 | 90.67 | -3.88% |
| `recent_1m` | 51 | 46.29% | 2.209 | 77.41 | -5.24% |
| `recent_3m` | 112 | 24.59% | 1.303 | 21.56 | -16.30% |
| `recent_6m` | 248 | 87.01% | 1.422 | 26.90 | -16.30% |
| `full_year` | 549 | 287.61% | 1.425 | 26.33 | -16.30% |

## Top Monthly: `no_wick_no_breakout__cfg_side_88_12__q80`

| month | trades | ret | PF | avg bps | DD |
| --- | ---: | ---: | ---: | ---: | ---: |
| `2025_06_partial` | 8 | 2.49% | 1.915 | 31.38 | -1.79% |
| `2025_07` | 44 | 11.39% | 1.442 | 25.97 | -4.66% |
| `2025_08` | 58 | 7.19% | 1.226 | 13.02 | -10.66% |
| `2025_09` | 49 | 23.12% | 2.334 | 43.46 | -6.00% |
| `2025_10` | 53 | 22.20% | 1.515 | 40.60 | -13.22% |
| `2025_11` | 50 | 11.84% | 1.378 | 24.38 | -9.97% |
| `2025_12` | 44 | 2.36% | 1.095 | 7.15 | -15.27% |
| `2026_01` | 42 | 18.36% | 1.834 | 41.49 | -5.48% |
| `2026_02` | 47 | 1.08% | 1.052 | 3.91 | -9.73% |
| `2026_03` | 47 | 25.52% | 2.161 | 49.54 | -3.33% |
| `2026_04` | 25 | -9.99% | 0.514 | -40.80 | -10.13% |
| `2026_05` | 37 | 1.34% | 1.072 | 4.77 | -10.99% |
| `2026_06` | 45 | 34.24% | 1.944 | 68.48 | -5.24% |

## 产物

- JSON：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_seeded_event_quality_v01_full_ablation_2026-06-27.json`
- Summary：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_seeded_event_quality_v01_full_ablation_summary_2026-06-27.csv`
- Windows：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_seeded_event_quality_v01_full_ablation_windows_2026-06-27.csv`
- Monthly：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_seeded_event_quality_v01_full_ablation_monthly_2026-06-27.csv`
- Trades：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_seeded_event_quality_v01_full_ablation_trades_2026-06-27.csv`
