# BIN-15M-AS6S V6 HYPE clean-RSI mark账户参数面（2026-07-15）

把既有500个clean-RSI局部配置全部改用mark-price保护退出，并逐个替换回六币联合账户。未来OOS未读取。

| 路线 | 配置数 | 硬门槛通过 | 研究缓冲通过 | source OAT硬通过 | source OAT缓冲通过 | source年化 | preferred年化 | source最低胜率 | preferred最低胜率 | preferred当前频率 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `nonpreemptive` | 519 | 101 | 77 | 8/21 | 6/21 | 29.950x | 27.424x | 82.02% | 81.31% | 1.187/日 |
| `strong_breakout_preemptive` | 519 | 125 | 88 | 11/21 | 10/21 | 27.976x | 30.817x | 82.22% | 81.82% | 1.022/日 |

preferred仍须做OAT邻域和重新联合坐标搜索；本轮不登记版本。

结构化结果：[`binance_as6s_v6_mark_clean_rsi_account_surface_2026-07-15.json`](../artifacts/binance_as6s_v6_mark_clean_rsi_account_surface_2026-07-15.json)。
