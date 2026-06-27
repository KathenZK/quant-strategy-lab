# HYPE-5M-Event-Quality-Scoring Seeded V0.1 Style Prune

生成日期：`2026-06-27`

## 结论

- 诊断窗口：`2025-06-26 04:20:00+00:00` 到 `2026-06-26 04:20:00+00:00`。
- Base：`base_all__q80`，全年收益 `61.81%`，PF `1.128`，最大回撤 `-26.94%`。
- 精简排序首位：`no_wick_no_breakout__q80`，全年收益 `238.78%`，PF `1.383`，最大回撤 `-16.75%`。

注意：这是固定 seed universe 的 style-prune 诊断，不是严格无前视 OOS。`2026-03-01` 之前的分段仍受 seed-selection 前视影响。

## 数据质量

- 数据范围：`2025-05-30 10:30:00+00:00` 到 `2026-06-26 04:15:00+00:00`。
- 行数：`112822`，缺口：`0`。
- raw/normalized 对齐：`True`。

## Candidates

| rank | candidate | trades | ret | PF | win | avg bps | DD | recent3m | neg months | gate |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | `no_wick_no_breakout__q80` | 545 | 238.78% | 1.383 | 59.08% | 24.05 | -16.75% | 25.33% | 2/13 | True |
| 2 | `bb_vwap_only__q85` | 347 | 194.31% | 1.489 | 61.38% | 33.06 | -10.79% | 34.77% | 1/13 | True |
| 3 | `core_bb_vwap_macd__q90` | 289 | 179.44% | 1.534 | 62.98% | 37.82 | -15.04% | 36.94% | 1/13 | True |
| 4 | `bb_vwap_only__q90` | 247 | 139.64% | 1.525 | 62.75% | 37.64 | -13.03% | 24.63% | 3/13 | True |
| 5 | `no_wick_no_breakout__q90` | 355 | 139.12% | 1.390 | 58.87% | 26.47 | -14.60% | 17.36% | 2/13 | True |
| 6 | `no_wick__q90` | 366 | 136.23% | 1.379 | 59.02% | 25.35 | -18.11% | 25.20% | 1/13 | True |
| 7 | `core_bb_vwap_macd__q80` | 475 | 134.18% | 1.280 | 57.26% | 19.78 | -21.52% | 36.21% | 4/13 | True |
| 8 | `mean_revert_bb_vwap_rsi__q80` | 520 | 123.56% | 1.255 | 57.31% | 17.10 | -24.58% | 1.42% | 5/13 | True |
| 9 | `no_wick__q80` | 562 | 122.35% | 1.239 | 55.87% | 15.83 | -14.77% | 12.30% | 5/13 | True |
| 10 | `core_bb_vwap_macd__q85` | 392 | 118.64% | 1.295 | 57.91% | 22.05 | -17.30% | 54.31% | 5/13 | True |
| 11 | `bb_vwap_only__q80` | 443 | 115.56% | 1.267 | 58.69% | 19.20 | -17.71% | 32.07% | 5/13 | True |
| 12 | `mean_revert_bb_vwap_rsi__q95` | 207 | 107.43% | 1.503 | 57.97% | 37.64 | -12.03% | 15.69% | 3/13 | True |
| 13 | `no_wick_no_breakout__q95` | 220 | 106.61% | 1.458 | 57.73% | 35.49 | -11.85% | 32.57% | 2/13 | True |
| 14 | `no_wick_no_breakout__q85` | 463 | 91.23% | 1.225 | 56.80% | 15.78 | -19.80% | 14.70% | 4/13 | True |
| 15 | `no_wick__q95` | 235 | 89.24% | 1.366 | 56.60% | 29.69 | -11.64% | 30.77% | 3/13 | True |
| 16 | `mean_revert_bb_vwap_rsi__q90` | 329 | 73.36% | 1.251 | 56.53% | 18.68 | -13.14% | 6.74% | 4/13 | True |
| 17 | `core_bb_vwap_macd__q95` | 184 | 69.23% | 1.367 | 57.61% | 31.39 | -13.23% | 28.26% | 3/13 | True |
| 18 | `bb_vwap_only__q95` | 165 | 68.33% | 1.412 | 58.79% | 34.27 | -15.62% | 10.23% | 3/13 | True |
| 19 | `no_wick__q85` | 480 | 63.43% | 1.170 | 56.04% | 11.92 | -20.87% | 22.20% | 6/13 | True |
| 20 | `base_all__q95` | 331 | 47.65% | 1.167 | 48.64% | 14.11 | -24.27% | 4.38% | 5/13 | True |

## Top Windows: `no_wick_no_breakout__q80`

| window | trades | ret | PF | avg bps | DD |
| --- | ---: | ---: | ---: | ---: | ---: |
| `recent_1w` | 11 | 10.11% | 2.617 | 90.67 | -3.88% |
| `recent_1m` | 52 | 47.96% | 2.244 | 78.12 | -5.24% |
| `recent_3m` | 113 | 25.33% | 1.309 | 21.91 | -16.75% |
| `recent_6m` | 246 | 79.87% | 1.391 | 25.57 | -16.75% |
| `full_year` | 545 | 238.78% | 1.383 | 24.05 | -16.75% |

## Top Style Breakdown: `no_wick_no_breakout__q80`

| style | trades | ret | PF | avg bps | DD |
| --- | ---: | ---: | ---: | ---: | ---: |
| `bb_revert` | 78 | 57.89% | 2.306 | 60.09 | -7.65% |
| `vwap_revert` | 202 | 52.09% | 1.318 | 22.78 | -13.10% |
| `macd_flip` | 102 | 47.05% | 1.644 | 39.91 | -8.58% |
| `trend_rsi_snapback` | 163 | -4.06% | 0.974 | -1.54 | -22.41% |

## Top Monthly: `no_wick_no_breakout__q80`

| month | trades | ret | PF | avg bps | DD |
| --- | ---: | ---: | ---: | ---: | ---: |
| `2025_06_partial` | 8 | 3.10% | 2.136 | 38.98 | -1.79% |
| `2025_07` | 42 | 2.27% | 1.098 | 6.88 | -7.16% |
| `2025_08` | 58 | 7.19% | 1.226 | 13.02 | -10.66% |
| `2025_09` | 47 | 34.99% | 4.355 | 64.79 | -2.25% |
| `2025_10` | 55 | 9.67% | 1.237 | 19.28 | -13.05% |
| `2025_11` | 50 | 11.84% | 1.378 | 24.38 | -9.97% |
| `2025_12` | 44 | 2.36% | 1.095 | 7.15 | -15.27% |
| `2026_01` | 42 | 18.36% | 1.834 | 41.49 | -5.48% |
| `2026_02` | 42 | -2.90% | 0.936 | -5.25 | -13.72% |
| `2026_03` | 49 | 24.94% | 1.979 | 46.72 | -3.59% |
| `2026_04` | 25 | -9.99% | 0.514 | -40.80 | -10.13% |
| `2026_05` | 38 | 1.93% | 1.095 | 6.26 | -10.83% |
| `2026_06` | 45 | 34.24% | 1.944 | 68.48 | -5.24% |

## 产物

- JSON：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_seeded_event_quality_v01_style_prune_2026-06-27.json`
- Summary：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_seeded_event_quality_v01_style_prune_summary_2026-06-27.csv`
- Windows：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_seeded_event_quality_v01_style_prune_windows_2026-06-27.csv`
- Monthly：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_seeded_event_quality_v01_style_prune_monthly_2026-06-27.csv`
- Trades：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_seeded_event_quality_v01_style_prune_trades_2026-06-27.csv`
