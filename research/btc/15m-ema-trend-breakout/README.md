# BTC-15M-EMA-Trend-Breakout

- Full family name：`BTC-15M-EMA-Trend-Breakout`
- Alias：`BTC-15M-EMA-TB`
- 市场/周期：Binance USD-M Futures `BTCUSDT` perpetual `15m`
- 机制：快慢 EMA 趋势背景 + 价格突破，K0 close 确认后于 K2 open 执行；V40 模板迁移已完成一次冻结搜索与 holdout 揭示。
- 边界：不得与 `HYPE-EMA-Trend-Breakout` 或 BTC `1h` adaptive-regime 家族共用裸版本号或结论。
- 当前状态：`explore / not promoted / not live-ready`；V40 模板迁移未找到通过门禁的类似盈利策略，已停止扩搜。

## 入口

- [主账](btc-15m-ema-tb-core-ledger.md)：家族身份、状态、版本规则与证据地图。
- [决策记录](decision-log.md)：逐项记录研究决策。
- [V40 模板迁移最终诊断](diagnostics/btc-15m-ema-tb-v40-transfer-2026-07-17.md)：冻结搜索、一次 holdout 揭示与负结论。
- [脚本说明](scripts/README.md)：BTC `15m` 标准数据刷新与审计入口。
- [诊断说明](diagnostics/README.md)：长期诊断入口。
- [产物说明](artifacts/README.md)：机器可读审计报告及保留边界。

当前没有注册版本、研究侧版本规格或 runner handoff；V40 是迁移模板而非本家族版本，不得登记为 V1。
