# BIN-15M-AS6S V5 参数盘点（2026-07-15）

本盘点只读取 `2026-07-14T09:00Z` 之前的数据与冻结配置；不读取未来OOS，也不修改V5。

## 结论

- 共核对 `15` 条腿、`6` 个币。
- 8条frontier 15m腿中发现 `46` 个按腿计数的代码无效字段实例；这些字段必须从后续clean配置表面移除。另1条15m腿是独立clean-RSI实现。
- 6条旧1h腿已从原始运行模块重新构造精确配置；旧家族消融只作先验，15条腿仍全部需要在当前联合账户语义下重新做精确消融。
- HYPE clean-RSI还包含两个未暴露在Config里的固定条件：MACD方向和ATR96上限，必须纳入消融。

## 逐腿状态

| 腿 | 币 | 周期来源 | 机制 | 代码无效字段数 | 是否需要当前账户精确消融 |
|---|---|---|---|---:|---|
| `cleanrsi15m:HYPEUSDT:rsi_reversal_w7_lo40_hi60:fixed_tp120p0_sl450p0_hold48` | `HYPEUSDT` | `asset_specific_clean_rsi_hf` | `clean_rsi_reversal` | 0 | 是 |
| `frontier15m:BNBUSDT:breakout:BNBUSDT_breakout_001075` | `BNBUSDT` | `prefit_frontier_asset_first` | `breakout` | 7 | 是 |
| `frontier15m:ETHUSDT:breakout:ETHUSDT_breakout_000439` | `ETHUSDT` | `prefit_frontier_asset_first` | `breakout` | 7 | 是 |
| `frontier15m:ETHUSDT:trend_state:ETHUSDT_trend_state_001071` | `ETHUSDT` | `prefit_frontier_asset_first` | `trend_state` | 4 | 是 |
| `frontier15m:HYPEUSDT:breakout:HYPEUSDT_breakout_000423` | `HYPEUSDT` | `prefit_frontier_asset_first` | `breakout` | 7 | 是 |
| `frontier15m:HYPEUSDT:reversal:HYPEUSDT_reversal_000370` | `HYPEUSDT` | `prefit_frontier_asset_first` | `reversal` | 5 | 是 |
| `frontier15m:SOLUSDT:breakout:SOLUSDT_breakout_000222` | `SOLUSDT` | `prefit_frontier_asset_first` | `breakout` | 7 | 是 |
| `frontier15m:SOLUSDT:reversal:SOLUSDT_reversal_001041` | `SOLUSDT` | `prefit_frontier_asset_first` | `reversal` | 5 | 是 |
| `frontier15m:SOLUSDT:trend_state:SOLUSDT_trend_state_001425` | `SOLUSDT` | `prefit_frontier_asset_first` | `trend_state` | 4 | 是 |
| `legacy1h:BNBUSDT:wick_reject` | `BNBUSDT` | `legacy_asset_specific_1h` | `wick_reject` | 0 | 是 |
| `legacy1h:BTCUSDT:keltner_break` | `BTCUSDT` | `legacy_asset_specific_1h` | `keltner_break` | 0 | 是 |
| `legacy1h:ETHUSDT:rsi_reversal` | `ETHUSDT` | `legacy_asset_specific_1h` | `rsi_reversal` | 0 | 是 |
| `legacy1h:HYPEUSDT:di_cross` | `HYPEUSDT` | `legacy_asset_specific_1h` | `di_cross` | 0 | 是 |
| `legacy1h:SOLUSDT:donchian_break` | `SOLUSDT` | `legacy_asset_specific_1h` | `donchian_break` | 0 | 是 |
| `legacy1h:TRXUSDT:macd_flip` | `TRXUSDT` | `legacy_asset_specific_1h` | `macd_flip` | 0 | 是 |

## 后续顺序

1. 单腿逐字段移除，先做交易路径等价与生效性审计。
2. 比较单腿 prefit、reused diagnostic、through-cutoff，并将每个变体替换回联合账户测边际。
3. 删除代码无效和可安全移除字段，形成clean参数接口。
4. 只在clean接口上做局部微调；随后复测8 bps、K+2、参数邻域与两种路由。
5. 新结果独立冻结，不使用V5正在积累的未来OOS选优。

结构化清单：[`binance_as6s_v5_parameter_inventory_2026-07-15.json`](../artifacts/binance_as6s_v5_parameter_inventory_2026-07-15.json)。
