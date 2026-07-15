# BIN-15M-AS6S V6 六条旧1h腿clean微调（2026-07-15）

只组合消融后仍活跃的字段；每腿最多300个OAT及2-5字段局部组合，当前三个月只作负收益/回撤惩罚，shortlist复测8 bps和K+2。

- 腿：`6`
- 生成配置：`1800`
- preferred不同于V5基线：`4`

| 腿 | 是否变化 | base prefit年化 | base当前3m收益 | 8bps当前3m收益 | K+2当前3m收益 |
|---|---|---:|---:|---:|---:|
| `legacy1h:BNBUSDT:wick_reject` | 是 | 1.150x | -0.01% | -0.20% | -0.02% |
| `legacy1h:BTCUSDT:keltner_break` | 是 | 1.369x | +13.25% | +12.72% | +15.33% |
| `legacy1h:ETHUSDT:rsi_reversal` | 是 | 1.988x | +1.85% | +1.69% | +3.91% |
| `legacy1h:HYPEUSDT:di_cross` | 否 | 4.645x | +40.96% | +32.58% | +17.46% |
| `legacy1h:SOLUSDT:donchian_break` | 是 | 1.641x | +4.89% | -0.54% | -1.74% |
| `legacy1h:TRXUSDT:macd_flip` | 否 | 1.538x | +8.55% | +7.60% | -4.03% |

preferred只进入联合账户替换池；旧腿内部杠杆字段已外置，最终暴露继续由账户合同限制在3x以内。

结构化结果：[`binance_as6s_v6_legacy_microtune_2026-07-15.json`](../artifacts/binance_as6s_v6_legacy_microtune_2026-07-15.json)。
