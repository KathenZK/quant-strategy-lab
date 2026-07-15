# BIN-15M-AS6S V6 mark-price完整账户重放（2026-07-15）

信号和入场使用trade OHLC；保护单由15m mark OHLC触发，退出按trade价格代理成交并重新运行联合账户仲裁。未来OOS未读取。

| 路线 | 原scale | 原scale hard pass | mark最佳scale | mark hard pass | full年化倍数 | full胜率 | full回撤 | 当前3m收益 | 当前3m胜率 | 当前频率 |
|---|---:|---|---:|---|---:|---:|---:|---:|---:|---:|
| `nonpreemptive` | 0.57 | `False` | 0.57 | `False` | 12.748x | 85.66% | -17.89% | +119.43% | 85.39% | 0.978/日 |
| `strong_breakout_preemptive` | 0.66 | `True` | 0.63 | `True` | 13.670x | 85.34% | -16.87% | +127.35% | 85.87% | 1.011/日 |

这是15m OHLC可支持的完整离线mark重放；真实触发后的逐笔成交价仍需testnet/dry-run核对，但退出时序与后续账户占用已重新计算。

结构化结果：[`binance_as6s_v6_mark_price_account_2026-07-15.json`](../artifacts/binance_as6s_v6_mark_price_account_2026-07-15.json)；交易路径：[`binance_as6s_v6_mark_price_account_trades_2026-07-15.csv`](../artifacts/binance_as6s_v6_mark_price_account_trades_2026-07-15.csv)。
