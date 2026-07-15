# BIN-15M-AS6S V6 mark稳健缓冲联合微调（2026-07-15）

在用户硬门槛之外，选择阶段额外要求：所有门禁窗口最低胜率>=81%、最低回撤>-18.5%、当前3m和六币全活跃期频率>=1.01单/日。未来OOS未读取。

| 路线 | hard pass | buffer pass | scale | 杠杆 | 年化倍数 | full胜率 | full回撤 | 当前3m收益 | 当前胜率 | 当前频率 | 最低压力胜率 | 最低压力回撤 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `nonpreemptive` | `True` | `True` | 0.75 | 2.25x | 29.950x | 87.14% | -17.84% | +169.43% | 85.87% | 1.011/日 | 82.02% | -18.23% |
| `strong_breakout_preemptive` | `True` | `True` | 0.72 | 2.16x | 27.976x | 86.59% | -16.37% | +165.01% | 86.02% | 1.022/日 | 82.22% | -17.95% |

本结果仍为开发样本观察，下一步必须对新选择重新做逐腿删除和完整邻域审计。

结构化结果：[`binance_as6s_v6_mark_robust_account_2026-07-15.json`](../artifacts/binance_as6s_v6_mark_robust_account_2026-07-15.json)；交易路径：[`binance_as6s_v6_mark_robust_account_trades_2026-07-15.csv`](../artifacts/binance_as6s_v6_mark_robust_account_trades_2026-07-15.csv)。
