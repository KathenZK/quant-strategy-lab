# HYPE-5M-PBTR Ensemble 实盘规格文档索引

这些文档对应当前报告里全部 7 个 `target_pass=True` 的 one-position ensemble 组合。它们不是 7 个互不相关的策略家族，而是同一批精筛子腿在不同子腿数量和杠杆下的 7 个达标配置。

| 策略编号 | 文档 | 子腿数 | 杠杆 | 全样本年化 | 最大回撤 | 胜率 | 交易数 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `HYPE-5M-ENS-S01` | [hype-5m-ensemble-s01-8l-4x-live-spec.md](hype-5m-ensemble-s01-8l-4x-live-spec.md) | 8 | 4x | 121.31x | -19.22% | 85.79% | 570 |
| `HYPE-5M-ENS-S02` | [hype-5m-ensemble-s02-16l-2p5x-live-spec.md](hype-5m-ensemble-s02-16l-2p5x-live-spec.md) | 16 | 2.5x | 50.29x | -18.85% | 85.46% | 839 |
| `HYPE-5M-ENS-S03` | [hype-5m-ensemble-s03-8l-3x-live-spec.md](hype-5m-ensemble-s03-8l-3x-live-spec.md) | 8 | 3x | 37.65x | -14.49% | 85.79% | 570 |
| `HYPE-5M-ENS-S04` | [hype-5m-ensemble-s04-12l-2p5x-live-spec.md](hype-5m-ensemble-s04-12l-2p5x-live-spec.md) | 12 | 2.5x | 36.43x | -17.63% | 86.01% | 686 |
| `HYPE-5M-ENS-S05` | [hype-5m-ensemble-s05-5l-3x-live-spec.md](hype-5m-ensemble-s05-5l-3x-live-spec.md) | 5 | 3x | 25.22x | -16.67% | 87.06% | 456 |
| `HYPE-5M-ENS-S06` | [hype-5m-ensemble-s06-16l-2x-live-spec.md](hype-5m-ensemble-s06-16l-2x-live-spec.md) | 16 | 2x | 23.34x | -15.29% | 85.46% | 839 |
| `HYPE-5M-ENS-S07` | [hype-5m-ensemble-s07-8l-2p5x-live-spec.md](hype-5m-ensemble-s07-8l-2p5x-live-spec.md) | 8 | 2.5x | 20.82x | -12.18% | 85.79% | 570 |

复现来源：

- `artifacts/hype_5m_ensemble_combo_ranking.csv`
- `artifacts/hype_5m_ensemble_combo_legs.csv`
- `artifacts/hype_5m_ensemble_ablation_*.csv`
- `research/hype/families/5m-pullback-trail/scripts/research_hype_5m_ensemble_combo.py`
- `research/hype/families/5m-pullback-trail/scripts/research_hype_5m_ensemble_ablation.py`
