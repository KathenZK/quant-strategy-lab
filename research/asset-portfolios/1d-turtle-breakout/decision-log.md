# Binance-1D-Turtle-Breakout 决策日志

## 2026-06-27

- 启动跨资产日线 turtle breakout 诊断，覆盖 Binance USD-M Futures `BTCUSDT`、`ETHUSDT`、`HYPEUSDT`。
- 初始规则固定为 20 日突破入场、10 日跌破出场，信号与成交均按日线 close。
- 数据质量：`2025-06-27` 至 `2026-06-26` 共 365 根已收盘 UTC 日K，三标的均无缺失、重复、未收盘行或 OHLC 异常。
- 固定 1x 结果：净收益 `HYPEUSDT -26.04%`、`BTCUSDT -26.40%`、`ETHUSDT -45.61%`；买入持有净收益分别为 `HYPEUSDT 75.55%`、`BTCUSDT -43.95%`、`ETHUSDT -34.95%`。
- 动态仓位扩展：测试固定 1x、20 日波动率目标、前 10 日低点风险定仓、2%风险定仓、回撤降档、风险定仓+回撤降档。各标的最佳为风险定仓类低暴露模型：`HYPEUSDT -0.49%`（平均仓位 `1.28%`）、`BTCUSDT -3.31%`（平均仓位 `3.28%`）、`ETHUSDT -3.33%`（平均仓位 `2.44%`）。
- 决策：不提升为 paper-live/live candidate。原因是动态仓位只是通过大幅降低风险暴露减少亏损，未证明 20/10 日线突破信号在该一年窗口有正期望；同时 close-fill 口径尚未通过 next-open/next-bar 可执行审计，也未纳入资金费率和真实账户手续费等级。
