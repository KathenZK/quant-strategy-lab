# MU-15M-Donchian-Trend-Breakout

- Alias：`MU-15M-DTB`
- 市场：Binance USD-M Futures `MUUSDT` `TRADIFI_PERPETUAL`
- 周期：`15m`
- 机制：EMA 长期趋势背景下的 Donchian 收盘突破，下一根 open 入场，以 ATR 初始止损和只用已完成 K 线更新的 trailing / Donchian exit 捕捉趋势。
- 边界：不是 [`MU-HYPE-XFER`](../README.md) 的 HYPE/V14 迁移线，不继承其“V6”标签、参数或证据。
- 当前状态：`explore / not promoted / not live-ready`；18 组冻结搜索仅 1 个开发候选，final audit `-4.13%` 且仅 2 笔，停止当前机制扩搜。

## 入口

- [家族主账](mu-15m-dtb-core-ledger.md)
- [决策日志](decision-log.md)
- [冻结搜索与 final audit](diagnostics/mu-15m-dtb-frozen-search-2026-07-20.md)
- [研究脚本](scripts/README.md)
- [机器产物](artifacts/README.md)
