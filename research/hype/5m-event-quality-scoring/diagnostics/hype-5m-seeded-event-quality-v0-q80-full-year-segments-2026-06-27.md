# HYPE-5M-Event-Quality-Scoring Seeded V0 Q80 Full-Year Segments

生成日期：`2026-06-27`

## 结论

- 诊断窗口：`2025-06-26 04:20:00+00:00` 到 `2026-06-26 04:20:00+00:00`。
- 使用固定 seed universe 与 `seeded_source_mean_q80` 规则，选中事件 `2580` 个，回放交易 `633` 笔。
- 过去一年分段回放总收益：`61.81%`，年化 `61.81%`，PF `1.128`，最大回撤 `-26.94%`。

注意：这是固定 seed universe 的回溯分段诊断，不是严格无前视 OOS。seed configs 仍来自 `HYPE-5M-Micro-Scalp` relaxed summary，并按 `train_2025_05_30_to_2026_03_01` 指标筛选；因此 `2026-03-01` 之前的分段会受到 seed 选择前视影响。

## 数据质量

- 数据范围：`2025-05-30 10:30:00+00:00` 到 `2026-06-26 04:15:00+00:00`。
- 行数：`112822`，缺口：`0`。
- raw/normalized 对齐：`True`。
- raw/normalized 最大差异：`{'open': 0.0, 'high': 0.0, 'low': 0.0, 'close': 0.0, 'volume': 0.0, 'quote_volume': 0.0, 'trade_count': 0.0, 'vwap': 0.0}`。

## 滚动窗口

| window | trades | total return | annualized | PF | win | avg bps | max DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `recent_1w` | 11 | 14.67% | 126028.57% | 3.827 | 72.73% | 127.73 | -2.31% |
| `recent_1m` | 56 | 27.18% | 1763.74% | 1.587 | 57.14% | 45.65 | -10.54% |
| `recent_3m` | 139 | 13.63% | 67.91% | 1.148 | 49.64% | 11.01 | -14.55% |
| `recent_6m` | 296 | 21.12% | 46.54% | 1.110 | 52.36% | 8.16 | -18.26% |
| `recent_12m` | 633 | 61.81% | 61.81% | 1.128 | 53.40% | 9.30 | -26.94% |
| `full_year` | 633 | 61.81% | 61.81% | 1.128 | 53.40% | 9.30 | -26.94% |

## 月度分段

| month | trades | total return | PF | win | avg bps | max DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `2025_06_partial` | 9 | -0.99% | 0.835 | 44.44% | -10.24 | -3.90% |
| `2025_07` | 58 | -15.79% | 0.649 | 43.10% | -28.33 | -18.43% |
| `2025_08` | 60 | -1.24% | 0.988 | 55.00% | -0.87 | -14.83% |
| `2025_09` | 55 | 47.53% | 3.356 | 69.09% | 72.31 | -4.21% |
| `2025_10` | 59 | 1.52% | 1.055 | 47.46% | 4.90 | -11.55% |
| `2025_11` | 52 | 10.86% | 1.283 | 59.62% | 22.13 | -9.95% |
| `2025_12` | 53 | -2.31% | 0.961 | 54.72% | -2.87 | -15.48% |
| `2026_01` | 57 | -8.51% | 0.845 | 50.88% | -13.81 | -18.04% |
| `2026_02` | 46 | 7.55% | 1.234 | 54.35% | 17.68 | -10.67% |
| `2026_03` | 50 | 7.86% | 1.288 | 60.00% | 16.22 | -8.93% |
| `2026_04` | 37 | -11.57% | 0.622 | 37.84% | -31.90 | -12.63% |
| `2026_05` | 51 | 1.97% | 1.076 | 50.98% | 5.12 | -10.13% |
| `2026_06` | 46 | 26.60% | 1.695 | 56.52% | 54.23 | -7.74% |

## 产物

- JSON：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_seeded_event_quality_v0_q80_full_year_segments_2026-06-27.json`
- Summary：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_seeded_event_quality_v0_q80_full_year_segments_summary_2026-06-27.csv`
- Monthly：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_seeded_event_quality_v0_q80_full_year_segments_monthly_2026-06-27.csv`
- Trades：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_seeded_event_quality_v0_q80_full_year_segments_trades_2026-06-27.csv`
