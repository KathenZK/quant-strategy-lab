# BTC Research Index

本目录存放 Bitcoin 单资产策略家族。任何版本号都必须和市场、周期、机制一起引用；状态词定义见 [strategy-status-glossary.md](../../docs/research-governance/strategy-status-glossary.md)。

## 当前研究线

- `BTC-1H-Adaptive-Regime`（`BTC-1H-AR`）：[1h-adaptive-regime/](1h-adaptive-regime/README.md)。Binance USD-M Futures `BTCUSDT` perpetual `1h` 多指标自适应 regime 家族；V1-V4 已登记；V4 参数邻域已判定局部耗尽，VWAP short-only、wick transition-only、MACD replace-Keltner 三条结构优化路线均为 `0` 严格 gate 命中，未产生 V5；当前 `registered / not promoted / not live-ready`。主账：[btc-1h-ar-core-ledger.md](1h-adaptive-regime/btc-1h-ar-core-ledger.md)。
- `BTC-15M-EMA-Trend-Breakout`（`BTC-15M-EMA-TB`）：[15m-ema-trend-breakout/](15m-ema-trend-breakout/README.md)。Binance USD-M Futures `BTCUSDT` perpetual `15m` 快慢 EMA 趋势背景 + 价格突破家族；V40 模板迁移未找到通过门禁的类似盈利策略，停止扩搜；`explore / not promoted / not live-ready`。主账：[btc-15m-ema-tb-core-ledger.md](15m-ema-trend-breakout/btc-15m-ema-tb-core-ledger.md)。
- `BTC-15M-Keltner-Trend-Breakout`（`BTC-15M-KTB`）：[15m-keltner-trend-breakout/](15m-keltner-trend-breakout/README.md)。Binance USD-M Futures `BTCUSDT` perpetual `15m` Keltner 收盘突破 + 可选 `1h` EMA trend regime；首轮 `630` 组冻结搜索 validation 正收益项为 `0`，停止本轮机制扩搜；`explore / not promoted / not live-ready`。主账：[btc-15m-keltner-trend-breakout-core-ledger.md](15m-keltner-trend-breakout/btc-15m-keltner-trend-breakout-core-ledger.md)。
- `BTC-15M-Trend-Continuation`（`BTC-15M-TC`）：[15m-trend-continuation/](15m-trend-continuation/README.md)。Binance USD-M Futures `BTCUSDT` perpetual `15m` 低波动压缩 + EMA 趋势 + Donchian 突破延续；多头六轮迭代无采纳项，空头专属 `804` 配置无门禁通过项，停止历史扩搜，仅保留 long-only prospective 观察；`explore / not promoted / not live-ready`。主账：[btc-15m-trend-continuation-core-ledger.md](15m-trend-continuation/btc-15m-trend-continuation-core-ledger.md)。
- `BTC-30M-Trend-Continuation`（`BTC-30M-TC`）：[30m-trend-continuation/](30m-trend-continuation/README.md)。Binance USD-M Futures `BTCUSDT` perpetual 原生 `30m` EMA 趋势 + 压缩/Donchian/Keltner 突破；低频结构通过历史成本与相位审计但样本门禁失败，高频路线在 `2024+` 与近期失效，停止本轮扩搜；`explore / not promoted / not live-ready`。主账：[btc-30m-trend-continuation-core-ledger.md](30m-trend-continuation/btc-30m-trend-continuation-core-ledger.md)。
