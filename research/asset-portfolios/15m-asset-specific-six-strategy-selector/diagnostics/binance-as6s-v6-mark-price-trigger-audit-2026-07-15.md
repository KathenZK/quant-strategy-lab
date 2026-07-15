# BIN-15M-AS6S V6 mark-price保护触发审计（2026-07-15）

六币mark-price 15m数据与trade OHLC完整对齐。下表仅审计固定止损/止盈的触发时序；移动止损与真实市价成交仍需dry-run。

| 路线 | 固定保护交易 | 同K触发 | mark更早 | 截至trade退出仍未触发 |
|---|---:|---:|---:|---:|
| `nonpreemptive` | 510 | 90.00% | 0.20% | 9.80% |
| `strong_breakout_preemptive` | 500 | 89.80% | 0.00% | 10.20% |

此结果是离线触发诊断，不是mark-price完整收益回测；任何时序分歧都必须在连续dry-run中核对实际保护成交与后续账户仲裁。

结构化结果：[`binance_as6s_v6_mark_price_trigger_audit_2026-07-15.json`](../artifacts/binance_as6s_v6_mark_price_trigger_audit_2026-07-15.json)；逐笔明细：[`binance_as6s_v6_mark_price_trigger_details_2026-07-15.csv`](../artifacts/binance_as6s_v6_mark_price_trigger_details_2026-07-15.csv)。
