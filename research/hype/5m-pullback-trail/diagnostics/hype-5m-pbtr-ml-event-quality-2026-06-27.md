# HYPE-5M-PBTR ML event quality rescue 2026-06-27

Family id：`HYPE-5M-PBTR`

本报告把 V3.3.1 原始 pullback 触发器降级为事件源，用 walk-forward 机器学习事件质量模型筛选入场。模型只使用信号 K 收盘时已知特征，训练标签来自严格 retry-arm 独立回放；最终结果仍用单仓 exact replay 复核。

## 数据集

- V3.3.1 事件数：`21451`；可 walk-forward 打分事件：`19737`。
- V1 strict executed 对照事件：`1357`；仅作标签分布参考，不用于筛选 V3.3.1。
- V3.3.1 独立标签 positive rate：`40.08%`；bad unlock/deadline rate：`61.63%`；trailing positive rate：`27.56%`。

## 模型

- 每个月只用该月之前的事件训练，不随机切分。
- 轻量模型为 `numpy` logistic/ridge：分别预测 `positive_net`、`bad_unlock`、`trailing_positive` 和 clipped `net_ret_1x`。
- 综合分数：`0.55 * P(positive) + 0.25 * P(trailing_positive) - 0.45 * P(bad_unlock) + 35 * E(net_ret)`。
- 逐月选择 top `5%/10%/20%/30%` 事件，再回放单仓 V3.3.1 retry-arm。

## Robust 聚合

| label | modes | min trades | min total | min PF | worst DD | min armed | max deadline |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `ml_top_20pct` | `4` | `549` | `-98.35%` | `0.585` | `-98.37%` | `42.24%` | `57.76%` |
| `ml_top_10pct` | `4` | `304` | `-89.39%` | `0.570` | `-89.81%` | `43.24%` | `56.76%` |
| `baseline_scored_events` | `4` | `2050` | `-100.00%` | `0.563` | `-100.00%` | `41.38%` | `58.62%` |
| `ml_top_30pct` | `4` | `796` | `-99.40%` | `0.543` | `-99.40%` | `43.27%` | `56.73%` |
| `ml_top_5pct` | `4` | `164` | `-77.64%` | `0.491` | `-78.67%` | `43.45%` | `56.55%` |

## Exact Replay 明细

| label | mode | events | trades | total | PF | win | payoff | DD | bad_unlock | trail+ | armed | deadline |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `ml_top_10pct` | `5m_conservative` | `1978` | `1198` | `-85.90%` | `0.659` | `41.40%` | `0.933` | `-86.22%` | `61.07%` | `28.41%` | `43.24%` | `56.76%` |
| `ml_top_30pct` | `5m_conservative` | `5923` | `3060` | `-99.06%` | `0.655` | `41.73%` | `0.914` | `-99.06%` | `60.54%` | `28.52%` | `43.27%` | `56.73%` |
| `ml_top_20pct` | `5m_conservative` | `3950` | `2166` | `-97.57%` | `0.625` | `40.30%` | `0.926` | `-97.60%` | `61.59%` | `27.59%` | `42.24%` | `57.76%` |
| `ml_top_30pct` | `5m_optimistic` | `5923` | `3144` | `-99.40%` | `0.622` | `39.95%` | `0.935` | `-99.40%` | `60.54%` | `28.52%` | `56.33%` | `43.67%` |
| `ml_top_5pct` | `5m_conservative` | `993` | `649` | `-73.44%` | `0.610` | `39.60%` | `0.930` | `-74.58%` | `60.32%` | `29.61%` | `43.45%` | `56.55%` |
| `ml_top_20pct` | `1m_conservative` | `1001` | `549` | `-61.07%` | `0.608` | `37.16%` | `1.029` | `-61.57%` | `61.59%` | `27.59%` | `50.27%` | `49.73%` |
| `ml_top_10pct` | `5m_optimistic` | `1978` | `1217` | `-89.39%` | `0.603` | `40.51%` | `0.886` | `-89.81%` | `61.07%` | `28.41%` | `57.85%` | `42.15%` |
| `ml_top_20pct` | `1m_optimistic` | `1001` | `553` | `-61.57%` | `0.603` | `37.25%` | `1.016` | `-62.06%` | `61.59%` | `27.59%` | `54.97%` | `45.03%` |
| `baseline_scored_events` | `1m_optimistic` | `5117` | `2087` | `-96.21%` | `0.589` | `38.38%` | `0.946` | `-96.31%` | `62.04%` | `27.35%` | `54.53%` | `45.47%` |
| `baseline_scored_events` | `5m_conservative` | `19737` | `7677` | `-100.00%` | `0.586` | `40.38%` | `0.865` | `-100.00%` | `62.04%` | `27.35%` | `41.38%` | `58.62%` |
| `ml_top_20pct` | `5m_optimistic` | `3950` | `2216` | `-98.35%` | `0.585` | `38.94%` | `0.917` | `-98.37%` | `61.59%` | `27.59%` | `55.91%` | `44.09%` |
| `ml_top_10pct` | `1m_conservative` | `499` | `304` | `-44.42%` | `0.583` | `40.13%` | `0.869` | `-45.30%` | `61.07%` | `28.41%` | `50.33%` | `49.67%` |
| `ml_top_10pct` | `1m_optimistic` | `499` | `305` | `-45.33%` | `0.570` | `40.33%` | `0.844` | `-47.15%` | `61.07%` | `28.41%` | `54.43%` | `45.57%` |
| `baseline_scored_events` | `5m_optimistic` | `19737` | `8048` | `-100.00%` | `0.570` | `39.43%` | `0.876` | `-100.00%` | `62.04%` | `27.35%` | `54.65%` | `45.35%` |
| `baseline_scored_events` | `1m_conservative` | `5117` | `2050` | `-97.03%` | `0.563` | `37.80%` | `0.926` | `-97.07%` | `62.04%` | `27.35%` | `50.05%` | `49.95%` |
| `ml_top_30pct` | `1m_optimistic` | `1507` | `803` | `-77.60%` | `0.555` | `37.48%` | `0.926` | `-77.62%` | `60.54%` | `28.52%` | `53.67%` | `46.33%` |
| `ml_top_5pct` | `5m_optimistic` | `993` | `659` | `-77.64%` | `0.551` | `39.45%` | `0.846` | `-78.67%` | `60.32%` | `29.61%` | `57.06%` | `42.94%` |
| `ml_top_30pct` | `1m_conservative` | `1507` | `796` | `-78.72%` | `0.543` | `37.19%` | `0.917` | `-78.75%` | `60.54%` | `28.52%` | `49.87%` | `50.13%` |
| `ml_top_5pct` | `1m_conservative` | `246` | `164` | `-33.71%` | `0.522` | `37.20%` | `0.881` | `-36.17%` | `60.32%` | `29.61%` | `50.00%` | `50.00%` |
| `ml_top_5pct` | `1m_optimistic` | `246` | `164` | `-35.05%` | `0.491` | `37.80%` | `0.808` | `-37.66%` | `60.32%` | `29.61%` | `53.05%` | `46.95%` |

## 结论

本轮最强 robust 行为 `ml_top_20pct`，四口径 min PF `0.585`，min total `-98.35%`，最少交易 `549`。

明确结论：这套轻量 ML 事件质量选择器没有救回 V3.3.1。相比 baseline scored events，ML top 分位能把部分口径的 PF 从约 `0.56-0.59` 抬到最高 `0.659`，也能把独立标签里的 trailing-positive rate 从 `27.35%` 小幅提高到最高 `29.61%`，但 bad unlock/deadline 仍约 `60%-62%`，exact replay 的 deadline 仍约 `43%-58%`。也就是说，模型确实学到了一点“更容易进入 trailing/target”的事件质量，但幅度不够，不能把原始高频双向 V3.3.1 变成正期望。

因此，不能把“提高 trailing/armed 概率”作为上线标准。后续若继续 ML，只应转向更低频的事件质量路线，例如 deep pullback long-only、强 16h 动量和 EMA spread 约束，再做 walk-forward/paper audit；不要在全量 V3.3.1 上继续叠模型阈值。

## 产物

- 脚本：`research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_ml_event_quality.py`
- JSON：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_ml_event_quality_2026-06-27.json`
- events CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_ml_event_quality_events_2026-06-27.csv`
- scores CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_ml_event_quality_scores_2026-06-27.csv`
- exact CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_ml_event_quality_exact_2026-06-27.csv`
- V1 对照 CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_ml_event_quality_v1_events_2026-06-27.csv`
