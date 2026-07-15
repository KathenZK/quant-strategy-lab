# BIN-15M-AS6S V6 clean参数表面（2026-07-15）

这是V5之外的新研究线，只定义消融后的微调接口，不是候选、不是登记版本，也不修改V5未来OOS。

- 腿：`15`
- 删除字段实例：`242`
- 保留字段实例：`213`
- 允许微调字段实例：`169`
- 灾难止损、最长持仓和K+1执行即便历史未触发也不会因消融而删除。
- 旧1h腿内部杠杆/风险仓位字段全部外置，由联合账户不超过3x的暴露合同统一控制。

## 逐腿clean表面

| 腿 | 删除 | 保留 | 可微调 |
|---|---:|---:|---:|
| `frontier15m:BNBUSDT:breakout:BNBUSDT_breakout_001075` | 15 | 12 | 8 |
| `frontier15m:ETHUSDT:breakout:ETHUSDT_breakout_000439` | 13 | 14 | 11 |
| `frontier15m:ETHUSDT:trend_state:ETHUSDT_trend_state_001071` | 9 | 16 | 13 |
| `frontier15m:HYPEUSDT:breakout:HYPEUSDT_breakout_000423` | 15 | 12 | 9 |
| `frontier15m:HYPEUSDT:reversal:HYPEUSDT_reversal_000370` | 9 | 16 | 13 |
| `frontier15m:SOLUSDT:breakout:SOLUSDT_breakout_000222` | 14 | 13 | 10 |
| `frontier15m:SOLUSDT:reversal:SOLUSDT_reversal_001041` | 9 | 16 | 13 |
| `frontier15m:SOLUSDT:trend_state:SOLUSDT_trend_state_001425` | 14 | 14 | 10 |
| `cleanrsi15m:HYPEUSDT:rsi_reversal_w7_lo40_hi60:fixed_tp120p0_sl450p0_hold48` | 4 | 7 | 7 |
| `legacy1h:BNBUSDT:wick_reject` | 23 | 16 | 13 |
| `legacy1h:BTCUSDT:keltner_break` | 25 | 14 | 11 |
| `legacy1h:ETHUSDT:rsi_reversal` | 19 | 20 | 17 |
| `legacy1h:HYPEUSDT:di_cross` | 26 | 13 | 10 |
| `legacy1h:SOLUSDT:donchian_break` | 22 | 17 | 14 |
| `legacy1h:TRXUSDT:macd_flip` | 25 | 13 | 10 |

完整字段清单：[`binance_as6s_v6_clean_surface_2026-07-15.json`](../artifacts/binance_as6s_v6_clean_surface_2026-07-15.json)。
