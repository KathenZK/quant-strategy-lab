# BIN-15M-AS6S V6 HYPE clean-RSI扩面后联合微调（2026-07-15）

将mark参数面中通过研究缓冲的clean-RSI前沿与OAT邻居放回15条腿联合坐标搜索。未来OOS未读取。

| 路线 | hard pass | buffer pass | scale | 杠杆 | 年化倍数 | full胜率 | full回撤 | 当前3m收益 | 当前胜率 | 当前频率 | 最低压力胜率 | 最低压力回撤 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `nonpreemptive` | `True` | `True` | 0.75 | 2.25x | 31.078x | 85.65% | -17.99% | +132.15% | 83.50% | 1.132/日 | 81.25% | -18.38% |
| `strong_breakout_preemptive` | `True` | `True` | 0.75 | 2.25x | 30.817x | 85.21% | -17.04% | +190.22% | 86.02% | 1.022/日 | 81.82% | -18.33% |

本结果仍须重新做账户逐腿删除、scale/路由和扩展clean参数邻域审计。

结构化结果：[`binance_as6s_v6_mark_clean_rsi_joint_refine_2026-07-15.json`](../artifacts/binance_as6s_v6_mark_clean_rsi_joint_refine_2026-07-15.json)；交易路径：[`binance_as6s_v6_mark_clean_rsi_joint_refine_trades_2026-07-15.csv`](../artifacts/binance_as6s_v6_mark_clean_rsi_joint_refine_trades_2026-07-15.csv)。
