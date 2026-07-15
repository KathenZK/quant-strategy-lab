# BIN-15M-AS6S V5 八条frontier腿全组件消融（2026-07-15）

严格使用 `ts < 2026-07-14T09:00Z`；未读取未来OOS，未修改V5。每个变体均计算4bps/K+1、8bps/K+1、4bps/K+2及prefit/reused diagnostic/through-cutoff。

- 腿：`8`
- 含基线的变体评估：`138`
- 三场景精确无变化的有效条件移除：`48`
- `remove_stop_diagnostic` 与 `remove_max_hold_diagnostic` 只用于解释参数作用，明确不可promotion。

## 逐腿变体数

| 腿 | 机制 | 变体数 | 精确无变化变体数 |
|---|---|---:|---:|
| `frontier15m:BNBUSDT:breakout:BNBUSDT_breakout_001075` | `breakout` | 16 | 6 |
| `frontier15m:ETHUSDT:breakout:ETHUSDT_breakout_000439` | `breakout` | 16 | 5 |
| `frontier15m:ETHUSDT:trend_state:ETHUSDT_trend_state_001071` | `trend_state` | 22 | 7 |
| `frontier15m:HYPEUSDT:breakout:HYPEUSDT_breakout_000423` | `breakout` | 16 | 6 |
| `frontier15m:HYPEUSDT:reversal:HYPEUSDT_reversal_000370` | `reversal` | 15 | 5 |
| `frontier15m:SOLUSDT:breakout:SOLUSDT_breakout_000222` | `breakout` | 16 | 5 |
| `frontier15m:SOLUSDT:reversal:SOLUSDT_reversal_001041` | `reversal` | 15 | 4 |
| `frontier15m:SOLUSDT:trend_state:SOLUSDT_trend_state_001425` | `trend_state` | 22 | 10 |

本文件先保留完整事实，不在消融运行脚本里按单一标量自动删参数；clean接口决策还要结合账户替换边际，避免单腿看似改善却抢走更优交易。

结构化结果：[`binance_as6s_v5_frontier_full_ablation_2026-07-15.json`](../artifacts/binance_as6s_v5_frontier_full_ablation_2026-07-15.json)。
