# HYPE-5M-PBTR-V3.3 retry-arm 近似回测 2026-06-26

Family id：`HYPE-5M-PBTR`

本报告复核线上新增的 stop-arm overlay：第 7 根 5m K 开始尝试挂 reduce-only `STOP_MARKET`；若当前价已穿越 stop，假设按 5 秒轮询继续尝试；第 9 根收盘后仍未挂上，则第 10 根处理周期市价平仓。

## 口径

- `5m_conservative`：只有 5m 收盘处理价未穿越时才允许挂单。
- `5m_optimistic`：若下一根 5m OHLC 显示价格曾回到可挂区，也认为 5 秒轮询能挂上。
- `1m_conservative`：使用本地 1m 数据，只用每根 1m open 作为重试采样点。
- `1m_optimistic`：使用本地 1m OHLC，只要 1m 区间曾回到可挂区就算挂上。
- 这些仍是近似口径，不是 tick/5s 级精确 replay。

本次使用 1m 数据：`True`。

## 结果

| 口径 | 交易数 | 年化 | 胜率 | PF | payoff | 最大回撤 | armed | deadline |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `old_stop_fill_baseline` | `8088` | `1435309257.24x` | `55.69%` | `4.164` | `3.314` | `-8.69%` | `n/a` | `n/a` |
| `5m_conservative` | `8344` | `0.00x` | `40.33%` | `0.583` | `0.862` | `-100.00%` | `41.69%` | `58.31%` |
| `5m_optimistic` | `8752` | `0.00x` | `39.41%` | `0.566` | `0.871` | `-100.00%` | `55.06%` | `44.94%` |
| `1m_conservative` | `8389` | `0.00x` | `40.04%` | `0.574` | `0.860` | `-100.00%` | `43.96%` | `56.04%` |
| `1m_optimistic` | `8426` | `0.00x` | `40.17%` | `0.580` | `0.863` | `-100.00%` | `45.10%` | `54.90%` |

## 诊断

- `1m_conservative`：armed `43.96%`，deadline `56.04%`，stop-market `41.14%`，gap 市价 `2.83%`，平均 retry `3.777`，平均 reject `1.895`。
- `1m_optimistic`：armed `45.10%`，deadline `54.90%`，stop-market `42.40%`，gap 市价 `2.69%`，平均 retry `3.690`，平均 reject `1.853`。
- `5m_conservative`：armed `41.69%`，deadline `58.31%`，stop-market `38.41%`，gap 市价 `3.28%`，平均 retry `1.969`，平均 reject `1.969`。
- `5m_optimistic`：armed `55.06%`，deadline `44.94%`，stop-market `54.34%`，gap 市价 `0.72%`，平均 retry `1.774`，平均 reject `1.492`。

## 结论

四个 retry-arm 近似口径全部低于 PF 1，且最大回撤均达到约 `-100%`。这说明 5 秒重试确实能提高部分交易的挂单成功率，但不能把旧 V3.3 的 crossed-stop 成交优势恢复为可实盘正 EV。

1m 数据没有改变结论：`1m_conservative` PF `0.574`，`1m_optimistic` PF `0.580`，只比 5m 保守略好，仍然是亏损结构。因此本次结果不支持把 V3.3 retry-arm overlay 提升为 paper/live 候选；它更适合作为线上小额审计和风控兜底机制。

## 产物

- 脚本：`research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v33_retry_arm.py`
- JSON：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v33_retry_arm_2026-06-26.json`
- 汇总 CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v33_retry_arm_summary_2026-06-26.csv`
- 交易 CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v33_retry_arm_trades_2026-06-26.csv`
- 诊断 CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v33_retry_arm_diagnostics_2026-06-26.csv`
