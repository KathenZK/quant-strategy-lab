# HYPE-5M-Event-Quality-Scoring Seeded V0

生成日期：`2026-06-27`

## 结论

- Seeded V0 找到 `3` 个 paper-audit 级别候选。
- 当前最佳：`seeded_source_mean_q80`。
- OOS：`184` 笔，`1.57` 笔/天，收益 `28.89%`，PF `1.222`，最大回撤 `-15.38%`。

注意：这是 seeded diagnostic。种子配置来自 `HYPE-5M-Micro-Scalp` 的历史搜索产物，
本脚本只用 2026-03-01 前的 train 指标筛选 seed，但 config universe 本身仍来自既有研究，
所以当前结论最多是 paper-audit 候选，不是 live-ready。

## 数据质量

- 数据范围：`2025-05-30 10:30:00+00:00` 到 `2026-06-26 04:15:00+00:00`。
- 行数：`112822`，缺口：`0`。
- raw/normalized 对齐：`True`。
- raw/normalized 最大差异：`{'open': 0.0, 'high': 0.0, 'low': 0.0, 'close': 0.0, 'volume': 0.0, 'quote_volume': 0.0, 'trade_count': 0.0, 'vwap': 0.0}`。

## 方法

- Seed source：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_relaxed_rounds_summary_2026-06-26.csv`。
- Seed configs：从 relaxed summary 里仅按 `train_2025_05_30_to_2026_03_01` 指标选前 `100` 个。
- Seed 条件：train trades >= 40、train return > 0、train PF >= 1.15、train maxDD >= -25%。
- OOS 起点：`2026-03-01 00:00:00+00:00`。
- 每月 walk-forward：用测试月之前的 seed 事件收益估计 cfg/style/side source mean score。
- 执行：闭合 K 信号、下一根 open 入场、固定 TP/SL、stop-first、open 穿越按 open 成交。

## Seed 事件池

- 事件数：`23464`。
- unique signal bars：`11945`。
- 平均独立事件收益：`5.04 bps`。

## Ranking 结果

| rank | candidate | trades | t/day | ret | PF | win | avg bps | DD | recent30 | gate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | `seeded_source_mean_q80` | 184 | 1.57 | 28.89% | 1.222 | 52.72% | 15.47 | -15.38% | 27.18% | True |
| 2 | `seeded_source_mean_q85` | 156 | 1.33 | 25.83% | 1.240 | 55.13% | 16.48 | -15.75% | 27.29% | True |
| 3 | `seeded_source_mean_q95` | 87 | 0.74 | 13.11% | 1.220 | 52.87% | 16.07 | -12.16% | 15.67% | True |
| 4 | `seeded_source_mean_q50` | 267 | 2.28 | 11.27% | 1.078 | 52.81% | 5.61 | -23.65% | 7.94% | False |
| 5 | `seeded_source_mean_q90` | 119 | 1.02 | 4.16% | 1.068 | 51.26% | 5.25 | -14.63% | 11.35% | False |
| 6 | `seeded_source_mean_q60` | 237 | 2.02 | -15.54% | 0.929 | 48.52% | -5.47 | -34.43% | -6.85% | False |
| 7 | `seeded_source_mean_q70` | 221 | 1.89 | -18.90% | 0.901 | 49.32% | -7.84 | -38.96% | 8.30% | False |

## 最佳候选月度

| month | trades | ret | PF | win | avg bps | DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `2026_03` | 50 | 12.90% | 1.480 | 62.00% | 25.42 | -8.93% |
| `2026_04` | 37 | -11.57% | 0.622 | 37.84% | -31.90 | -12.63% |
| `2026_05` | 51 | 1.97% | 1.076 | 50.98% | 5.12 | -10.13% |
| `2026_06` | 46 | 26.60% | 1.695 | 56.52% | 54.23 | -7.74% |

## 保留产物

- JSON：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_seeded_event_quality_v0_2026-06-27.json`
- Summary：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_seeded_event_quality_v0_summary_2026-06-27.csv`
- Monthly：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_seeded_event_quality_v0_monthly_2026-06-27.csv`
- Events：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_seeded_event_quality_v0_events_2026-06-27.csv`
- Top trades：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_seeded_event_quality_v0_top_trades_2026-06-27.csv`
