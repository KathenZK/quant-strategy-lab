# Scripts

- [research_hype_1d_pyramiding_trend.py](research_hype_1d_pyramiding_trend.py)：审计标准数据湖、聚合完整 UTC 日 K、执行 prefit 广搜、冻结 shortlist、一次性揭示最近 90 天 OOS，并输出压力/延迟审计。

复现：

```bash
uv run python research/hype/1d-pyramiding-trend/scripts/research_hype_1d_pyramiding_trend.py --seed 20260722 --stage1 250000 --stage2 150000 --shortlist 120 --run-date 2026-07-22
```
