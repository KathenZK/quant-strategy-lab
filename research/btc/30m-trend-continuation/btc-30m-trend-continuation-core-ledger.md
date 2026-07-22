# BTC-30M-Trend-Continuation Core Ledger

## Family Identity

- Full name：`BTC-30M-Trend-Continuation`
- Alias：`BTC-30M-TC`
- Market：Binance USD-M Futures `BTCUSDT` perpetual
- Timeframe：原生 `30m`
- Mechanism：EMA 趋势背景 + 低波动压缩、Donchian 或 Keltner 收盘突破 + ATR 止损与定时退出。
- Collision warning：与 [`BTC-15M-Trend-Continuation`](../15m-trend-continuation/README.md)、[`BTC-15M-Keltner-Trend-Breakout`](../15m-keltner-trend-breakout/README.md) 和 [`BTC-1H-Adaptive-Regime`](../1h-adaptive-regime/README.md) 是不同家族；版本和证据不得互相继承。

## Current State

- Current version(s)：无已登记版本。
- Current status：`explore / not promoted / not live-ready`
- Runner / dry-run / live：无 runner 实现、无 dry-run、无 live。
- Current observation：`lvcb-08816b18771a` 仅为未登记低频观察，不是合格 research candidate。
- Live-readiness blockers：开发期交易样本不足且收益集中；没有 untouched OOS；经典 Donchian/Keltner 与扩展压缩搜索在 `2024+`、双倍成本或偏移相位审计失败；未做 CPCV、trade-block bootstrap 和 runner 状态机审计。
- Next decision gate：停止本轮历史扩搜；只有独立新机制或 `2026-07-21 07:00 UTC` 后至少 `30` 笔可归因的新 prospective 交易，才重开研究。

## Version Rules

- 只有冻结信号、过滤、退出、成本、数据范围和执行时序后，才可命名 `Vx`。
- 参数、周期、方向、退出状态机或执行时序的实质变化需要新版本；诊断观察不占版本号。
- 登记仅固定身份，不代表 promotion、handoff 或 live-ready。

## Version Table

| Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision / Live Readiness |
| --- | --- | --- | --- | --- | --- |
| `lvcb-08816b18771a`（未登记观察） | `explore / not promoted / not live-ready` | 低波动压缩 + EMA48/192 + Donchian48，只做多，`5 ATR` 止损，最多 `192` 根 | Train `+32.83%` / `7` 笔；validation `+33.09%` / `22` 笔；reused diagnostic `+18.96%`，2x 成本 `+5.36%`；偏移相位 diagnostic `+20.37%`，2x `+9.81%` | [首轮诊断](diagnostics/btc-30m-trend-search-2026-07-21.md) | 样本与集中度门禁失败；只保留观察，不登记、不晋升 |

## Shared Assumptions

- 数据：原生 Binance `30m`，`2020-01-01 00:00 UTC` 至 `2026-07-21 07:00 UTC`；偏移相位用经审计原生 `15m` 聚合。
- 成本：每次成交 fee `0.001` + adverse slippage `4 bps`；另审计双倍成本；计入官方 funding。
- 时序：信号仅使用已收盘 K 线，下一根开盘成交；止损从入场 K 线起有效并按 gap-aware adverse fill 处理。
- 仓位：单方向、全额名义配置，不叠仓。

## Evidence Map

- Diagnostics：[首轮趋势搜索](diagnostics/btc-30m-trend-search-2026-07-21.md)
- Scripts / artifacts：[脚本入口](scripts/README.md) · [产物索引](artifacts/README.md)
- Live specs / runner tracking：无。
