# BIN-15M-AS6S V6 最新mark候选最终审计（2026-07-15）

对mark语义联合微调后的最新选择重做逐腿删除、scale邻域、抢占路由邻域和每腿其余稳健配置单替换。未来OOS未读取。

用户硬门槛保持不变；另外报告81%最低压力胜率、-18.5%回撤和1.01单/日频率研究缓冲。

| 路线 | 对拍 | 可删除腿 | scale硬通过率 | 路由硬通过率 | 单替换硬通过率 | 单替换全缓冲通过率 |
|---|---|---:|---:|---:|---:|---:|
| `nonpreemptive` | `PASS` | 0 | 100.00% | 不适用 | 40.00% | 20.00% |
| `strong_breakout_preemptive` | `PASS` | 0 | 100.00% | 57.14% | 67.62% | 42.86% |

## 逐腿删除结论

- `nonpreemptive`：可删除腿 `无`。
- `strong_breakout_preemptive`：可删除腿 `无`。

## 邻域薄弱点

- `nonpreemptive`最低全缓冲通过腿：
  - `cleanrsi15m:HYPEUSDT:rsi_reversal_w7_lo40_hi60:fixed_tp120p0_sl450p0_hold48`：硬门槛 0.00%，全部研究缓冲 0.00%。
  - `frontier15m:ETHUSDT:breakout:ETHUSDT_breakout_000439`：硬门槛 0.00%，全部研究缓冲 0.00%。
  - `frontier15m:ETHUSDT:trend_state:ETHUSDT_trend_state_001071`：硬门槛 0.00%，全部研究缓冲 0.00%。
  - `frontier15m:SOLUSDT:reversal:SOLUSDT_reversal_001041`：硬门槛 14.29%，全部研究缓冲 0.00%。
  - `legacy1h:BTCUSDT:keltner_break`：硬门槛 42.86%，全部研究缓冲 0.00%。
- `strong_breakout_preemptive`最低全缓冲通过腿：
  - `cleanrsi15m:HYPEUSDT:rsi_reversal_w7_lo40_hi60:fixed_tp120p0_sl450p0_hold48`：硬门槛 0.00%，全部研究缓冲 0.00%。
  - `frontier15m:HYPEUSDT:reversal:HYPEUSDT_reversal_000370`：硬门槛 71.43%，全部研究缓冲 0.00%。
  - `legacy1h:ETHUSDT:rsi_reversal`：硬门槛 42.86%，全部研究缓冲 0.00%。
  - `frontier15m:HYPEUSDT:breakout:HYPEUSDT_breakout_000423`：硬门槛 71.43%，全部研究缓冲 14.29%。
  - `frontier15m:SOLUSDT:reversal:SOLUSDT_reversal_001041`：硬门槛 28.57%，全部研究缓冲 14.29%。

结构化结果：[`binance_as6s_v6_mark_robust_candidate_audit_2026-07-15.json`](../artifacts/binance_as6s_v6_mark_robust_candidate_audit_2026-07-15.json)。
