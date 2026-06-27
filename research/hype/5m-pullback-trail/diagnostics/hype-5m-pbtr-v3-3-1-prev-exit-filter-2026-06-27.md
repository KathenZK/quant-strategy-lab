# HYPE-5M-PBTR-V3.3.1 prev-exit filter 回测 2026-06-27

Family id：`HYPE-5M-PBTR`

`HYPE-5M-PBTR-V3.3.1` 记录当前 V3.3 retry-arm overlay：第 7 根 5m K 开始尝试挂 reduce-only stop-market，穿越时按 retry 近似，第 10 根处理周期市价兜底。本报告测试一个额外入场过滤：若上一笔交易已有平仓价，则新多头开仓成交价必须高于上一笔平仓价，新空头开仓成交价必须低于上一笔平仓价；第一笔无上一笔，默认允许入场。

## 回测口径

- `5m_conservative` / `5m_optimistic`：沿用 V3.3.1 的 5m 悲观/乐观 retry-arm 近似。
- `1m_conservative` / `1m_optimistic`：使用本地 1m 数据的悲观/乐观 retry-arm 近似。
- `*_base` 是 V3.3.1 无新增开仓过滤；`*_prev_exit_filter` 是本次新增条件。
- 本次使用 1m 数据：`True`。

## 结果

| 口径 | 交易数 | 年化 | 胜率 | PF | payoff | 最大回撤 | armed | deadline | filter reject |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `5m_conservative_base` | `8344` | `0.00x` | `40.33%` | `0.583` | `0.862` | `-100.00%` | `41.69%` | `58.31%` | `0.00%` |
| `5m_conservative_prev_exit_filter` | `6587` | `0.00x` | `40.06%` | `0.581` | `0.869` | `-100.00%` | `41.60%` | `58.40%` | `39.09%` |
| `5m_optimistic_base` | `8752` | `0.00x` | `39.41%` | `0.566` | `0.871` | `-100.00%` | `55.06%` | `44.94%` | `0.00%` |
| `5m_optimistic_prev_exit_filter` | `6758` | `0.00x` | `38.86%` | `0.560` | `0.881` | `-100.00%` | `54.20%` | `45.80%` | `40.35%` |
| `1m_conservative_base` | `8389` | `0.00x` | `40.04%` | `0.574` | `0.860` | `-100.00%` | `43.96%` | `56.04%` | `0.00%` |
| `1m_conservative_prev_exit_filter` | `6613` | `0.00x` | `39.69%` | `0.568` | `0.863` | `-100.00%` | `43.75%` | `56.25%` | `39.10%` |
| `1m_optimistic_base` | `8426` | `0.00x` | `40.17%` | `0.580` | `0.863` | `-100.00%` | `45.10%` | `54.90%` | `0.00%` |
| `1m_optimistic_prev_exit_filter` | `6612` | `0.00x` | `39.75%` | `0.571` | `0.866` | `-100.00%` | `44.60%` | `55.40%` | `39.57%` |

## 诊断

- `1m_conservative_base`：armed `43.96%`，deadline `56.04%`，stop-market `41.14%`，gap 市价 `2.83%`，平均 retry `3.777`。
- `1m_conservative_prev_exit_filter`：armed `43.75%`，deadline `56.25%`，stop-market `41.00%`，gap 市价 `2.75%`，平均 retry `3.792`。
- `1m_optimistic_base`：armed `45.10%`，deadline `54.90%`，stop-market `42.40%`，gap 市价 `2.69%`，平均 retry `3.690`。
- `1m_optimistic_prev_exit_filter`：armed `44.60%`，deadline `55.40%`，stop-market `42.01%`，gap 市价 `2.59%`，平均 retry `3.709`。
- `5m_conservative_base`：armed `41.69%`，deadline `58.31%`，stop-market `38.41%`，gap 市价 `3.28%`，平均 retry `1.969`。
- `5m_conservative_prev_exit_filter`：armed `41.60%`，deadline `58.40%`，stop-market `38.36%`，gap 市价 `3.23%`，平均 retry `1.980`。
- `5m_optimistic_base`：armed `55.06%`，deadline `44.94%`，stop-market `54.34%`，gap 市价 `0.72%`，平均 retry `1.774`。
- `5m_optimistic_prev_exit_filter`：armed `54.20%`，deadline `45.80%`，stop-market `53.55%`，gap 市价 `0.65%`，平均 retry `1.799`。

## 结论

上一单平仓价过滤会明显降低频率：四个口径的 filter reject rate 约 `39%-40%`，交易数从约 `8.3k-8.8k` 降到约 `6.6k-6.8k`。

但过滤没有改善收益结构：5m 悲观/乐观过滤后 PF 分别为 `0.581`、`0.560`；1m 悲观/乐观过滤后 PF 分别为 `0.568`、`0.571`，均低于各自无过滤基准，也远低于 `1`。最大回撤仍约 `-100%`，说明该开仓条件不能修复 V3.3.1 的 retry-arm 负期望。

## 产物

- 脚本：`research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v3-3-1_prev_exit_filter.py`
- JSON：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v3-3-1_prev_exit_filter_2026-06-27.json`
- 汇总 CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v3-3-1_prev_exit_filter_summary_2026-06-27.csv`
- 交易 CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v3-3-1_prev_exit_filter_trades_2026-06-27.csv`
- 诊断 CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v3-3-1_prev_exit_filter_diagnostics_2026-06-27.csv`
