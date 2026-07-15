# BIN-15M-AS6S V6 mark语义联合微调（2026-07-15）

以trade-OHLC V6选项为种子，把每条腿最多8个稳健候选全部换成mark保护退出后重新做联合账户坐标搜索。未来OOS未读取。

| 路线 | hard pass | scale | 有效最大杠杆 | 活跃腿 | full年化倍数 | full胜率 | full回撤 | 当前3m收益 | 当前3m胜率 | 当前频率 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `nonpreemptive` | `True` | 0.60 | 1.80x | 15 | 15.192x | 86.98% | -17.58% | +122.12% | 85.87% | 1.011/日 |
| `strong_breakout_preemptive` | `True` | 0.72 | 2.16x | 15 | 31.105x | 86.84% | -17.30% | +149.81% | 84.62% | 1.000/日 |

本结果仍是开发样本观察；需继续做mark候选账户消融、邻域复核、冻结清单与Runner逐笔对拍。

结构化结果：[`binance_as6s_v6_mark_microtuned_account_2026-07-15.json`](../artifacts/binance_as6s_v6_mark_microtuned_account_2026-07-15.json)；交易路径：[`binance_as6s_v6_mark_microtuned_account_trades_2026-07-15.csv`](../artifacts/binance_as6s_v6_mark_microtuned_account_trades_2026-07-15.csv)。
