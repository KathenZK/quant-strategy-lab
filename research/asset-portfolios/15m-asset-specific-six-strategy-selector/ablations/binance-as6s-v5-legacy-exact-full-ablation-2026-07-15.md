# BIN-15M-AS6S V5 六条旧1h腿精确配置全参数消融（2026-07-15）

本轮不是直接引用旧家族结论，而是从V5实际运行模块重建六条精确配置，在当前外部暴露与单仓状态语义下重新逐字段扰动。严格使用 `ts < 2026-07-14T09:00Z`。

- 腿：`6`
- 参数组：`204`
- 参数变体：`381`，每个均复测三执行场景。
- 所有扰动均三场景交易路径不变、可移出clean接口的参数组实例：`102`。
- `name/style/entry_delay_bars`为身份、机制和执行契约，不按普通Alpha参数删除；K+2已独立覆盖entry delay。

## 逐腿摘要

| 腿 | 参数组 | 可移除无作用组 |
|---|---:|---:|
| `legacy1h:BNBUSDT:wick_reject` | 34 | 14 |
| `legacy1h:BTCUSDT:keltner_break` | 34 | 18 |
| `legacy1h:ETHUSDT:rsi_reversal` | 34 | 15 |
| `legacy1h:HYPEUSDT:di_cross` | 34 | 19 |
| `legacy1h:SOLUSDT:donchian_break` | 34 | 17 |
| `legacy1h:TRXUSDT:macd_flip` | 34 | 19 |

字段只有在至少两个替代值、三个执行场景下完整交易路径均不变时才标记 `remove_noop`；其余保留为active_tunable，后续仅在clean表面做局部微调。

结构化结果：[`binance_as6s_v5_legacy_exact_full_ablation_2026-07-15.json`](../artifacts/binance_as6s_v5_legacy_exact_full_ablation_2026-07-15.json)。
