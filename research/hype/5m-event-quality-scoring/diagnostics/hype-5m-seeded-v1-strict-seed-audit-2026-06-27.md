# HYPE-5M-Event-Quality-Scoring Seeded V1 Strict Seed Audit

生成日期：`2026-06-27`

## 结论

- 配置宇宙：使用 relaxed-rounds 的固定随机生成器，禁用 previous-summary seeds；每轮 `2000` 个、共 `6000` 个无数据配置。
- 严格 OOS 窗口：`2025-08-01 00:00:00+00:00` 到 `2026-06-26 04:20:00+00:00`；因数据从 `2025-05-30 10:30:00+00:00` 开始，先保留 `60` 天最小训练期。
- 每个测试月只使用该月之前的数据筛 seed，再生成该月事件并用 `cfg_side_88_12 + q80` 交易。
- 严格 seed 审计结果：`493` 笔，收益 `-61.16%`，PF `0.843`，单笔 `-16.58 bps`，最大回撤 `-65.94%`。

结论：严格 seed 审计没有支持 V1 当前表现，V1 的固定 seed-universe 结果很可能包含显著 config-universe selection bias。

## 数据质量

- 数据范围：`2025-05-30 10:30:00+00:00` 到 `2026-06-26 04:15:00+00:00`。
- 行数：`112822`，缺口：`0`。
- raw/normalized 对齐：`True`。

## Monthly

| month | selected seeds | trades | ret | PF | avg bps | DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `2025_08` | 33 | 78 | 4.18% | 1.085 | 7.54 | -9.69% |
| `2025_09` | 30 | 49 | -11.14% | 0.744 | -22.51 | -13.98% |
| `2025_10` | 43 | 75 | -7.60% | 0.934 | -7.22 | -32.39% |
| `2025_11` | 51 | 50 | 1.17% | 1.052 | 6.37 | -21.77% |
| `2025_12` | 49 | 44 | -9.96% | 0.841 | -20.26 | -15.20% |
| `2026_01` | 52 | 50 | -32.35% | 0.403 | -76.02 | -33.42% |
| `2026_02` | 59 | 43 | -10.41% | 0.771 | -23.33 | -16.63% |
| `2026_03` | 52 | 26 | 20.07% | 2.209 | 72.69 | -3.88% |
| `2026_04` | 55 | 20 | -7.03% | 0.550 | -35.41 | -7.18% |
| `2026_05` | 51 | 19 | -11.28% | 0.499 | -60.87 | -13.73% |
| `2026_06` | 66 | 39 | -16.96% | 0.628 | -45.27 | -19.37% |

## 与固定 seed-universe V1 的差异

- 固定 seed-universe V1：`549` 笔，`287.61%` 收益，`1.425` PF，`26.33 bps` 单笔，`-16.30%` 最大回撤。
- 本报告禁用了历史 summary seed，并每月滚动重新筛 seed。若表现显著下降，应视为 V1 live promotion blocker，而不是参数搜索问题。

## 产物

- JSON：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_seeded_v1_strict_seed_audit_2026-06-27.json`
- Summary：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_seeded_v1_strict_seed_audit_summary_2026-06-27.csv`
- Monthly：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_seeded_v1_strict_seed_audit_monthly_2026-06-27.csv`
- Trades：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_seeded_v1_strict_seed_audit_trades_2026-06-27.csv`
- Selected seeds：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_seeded_v1_strict_seed_audit_selected_seeds_2026-06-27.csv`
