# BIN-15M-AS6S V6 frontier局部微调（2026-07-15）

每条腿先生成300个基线邻域组合；排序只使用train/validation/prefit，当前三个月只作负收益与回撤惩罚，前18名再复测8 bps和K+2。未读取未来OOS，未修改V5。

- 腿：`8`
- 生成配置：`2400`
- preferred不同于V5基线：`8`

| 腿 | preferred是否变化 | base prefit年化倍数 | base当前3m收益 | 8bps当前3m收益 | K+2当前3m收益 |
|---|---|---:|---:|---:|---:|
| `frontier15m:BNBUSDT:breakout:BNBUSDT_breakout_001075` | 是 | 1.572x | +12.77% | +12.44% | +11.79% |
| `frontier15m:ETHUSDT:breakout:ETHUSDT_breakout_000439` | 是 | 1.274x | +4.27% | +4.19% | +4.26% |
| `frontier15m:ETHUSDT:trend_state:ETHUSDT_trend_state_001071` | 是 | 1.283x | +12.76% | +12.25% | +15.89% |
| `frontier15m:HYPEUSDT:breakout:HYPEUSDT_breakout_000423` | 是 | 3.479x | +35.90% | +34.97% | +35.39% |
| `frontier15m:HYPEUSDT:reversal:HYPEUSDT_reversal_000370` | 是 | 2.193x | -2.25% | -2.97% | -3.73% |
| `frontier15m:SOLUSDT:breakout:SOLUSDT_breakout_000222` | 是 | 2.250x | +19.39% | +7.27% | +15.88% |
| `frontier15m:SOLUSDT:reversal:SOLUSDT_reversal_001041` | 是 | 1.066x | +1.06% | +0.99% | +1.06% |
| `frontier15m:SOLUSDT:trend_state:SOLUSDT_trend_state_001425` | 是 | 2.157x | +4.29% | +2.24% | +6.04% |

preferred仍只是账户重组候选；只有替换回六币联合状态后仍满足整体胜率、回撤、频率和成本门禁才会保留。

结构化结果：[`binance_as6s_v6_frontier_microtune_2026-07-15.json`](../artifacts/binance_as6s_v6_frontier_microtune_2026-07-15.json)。
