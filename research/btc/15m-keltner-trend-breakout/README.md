# BTC-15M-Keltner-Trend-Breakout

- Full family name：`BTC-15M-Keltner-Trend-Breakout`
- Alias：`BTC-15M-KTB`
- 市场/周期：Binance USD-M Futures `BTCUSDT` perpetual `15m`
- 机制：`15m` Keltner 通道收盘突破，选择性叠加已闭合 `1h` EMA trend regime；下一根 `15m` open 入场，测试 midline、ATR trailing 与固定 ATR bracket 退出。
- 边界：本家族不是 [`BTC-15M-EMA-Trend-Breakout`](../15m-ema-trend-breakout/README.md)，也不继承 HYPE `30m` Keltner 家族的参数、版本或结论。
- 当前状态：`explore / not promoted / not live-ready`；首轮 `630` 组冻结搜索没有任何 validation 正收益项，冻结近失项 holdout 继续亏损，停止围绕本轮机制扩搜。

## 入口

- [主账](btc-15m-keltner-trend-breakout-core-ledger.md)
- [决策记录](decision-log.md)
- [首轮冻结搜索最终诊断](diagnostics/btc-15m-keltner-trend-breakout-initial-search-2026-07-20.md)
- [脚本说明](scripts/README.md)
- [产物说明](artifacts/README.md)

当前没有注册版本、research spec、live spec、runner handoff、dry-run 或 live 实例。
