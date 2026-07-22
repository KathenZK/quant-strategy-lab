# BTC-15M-Keltner-Trend-Breakout Core Ledger

## Family Identity

- Full family name：`BTC-15M-Keltner-Trend-Breakout`
- Alias：`BTC-15M-KTB`
- Market / exchange / symbol / timeframe：Binance USD-M Futures，`BTCUSDT` perpetual，`15m`
- Mechanism summary：`15m` Keltner 通道收盘突破，选择性叠加最后已闭合 `1h` EMA trend regime；下一根 `15m` open 入场，使用 midline、ATR trailing 或固定 ATR bracket 退出。
- Boundary / collision warnings：不继承 [`BTC-15M-EMA-Trend-Breakout`](../15m-ema-trend-breakout/btc-15m-ema-tb-core-ledger.md) 或 [`HYPE-30M-Keltner-Trend-Breakout`](../../hype/30m-keltner-trend-breakout/hype-30m-keltner-trend-breakout-core-ledger.md) 的版本、参数、指标或状态。

## Current State

- Current version(s)：无注册版本。
- Current status：`explore / not promoted / not live-ready`。
- Runner / dry-run / live status：无 runner handoff、无 dry-run、无 live。
- Research conclusion：首轮冻结搜索的 `630` 组配置中，validation 正收益项为 `0`；冻结近失项 validation `-10.47%`，一次诊断 holdout `-7.38%`，不构成研究候选。
- Live-readiness blockers：开发集无通过项、双倍成本亏损、邻域 train/validation 同正比例 `0%`、holdout PF `0.748`、最近 `1m/3m/6m/1y` 均亏损；相位、完整 promotion review 与 runner 可执行审计均未启动。
- Next decision gate：停止围绕本轮 Keltner cross + EMA regime + 三类退出继续扩搜。只有新的机制级假设与新冻结协议才可重开；若核心不再是 Keltner 趋势突破，应新建家族。

## Version Rules

- `V1`：只有参数、信号、过滤、退出、执行成本与证据窗口全部冻结，并至少产生 train/validation 同正、成本压力和邻域门禁通过项后才可登记。
- `Vx.y`：只用于不改变核心机制与执行合同的小幅冻结调整，且必须有独立规格和证据。
- Observation / diagnostic rows：数据审计、参数搜索、近失项和 holdout 诊断不是版本。
- New version trigger：信号事件、趋势 regime、退出状态机、执行时序、仓位模型或关键冻结参数发生身份级变化。

## Version Table

当前无注册版本。`BTC-15M-KTB-INITIAL-FROZEN-SEARCH-2026-07-20` 是失败诊断，不进入版本表。

## Shared Assumptions

- Data：Binance USD-M `BTCUSDT` perpetual 原生 `15m` 已闭合 OHLCV 与官方历史 funding；区间 `2024-07-14T00:00:00Z` 至 `2026-07-17T14:45:00Z`，DQ blocker 为 `0`。
- Cost：fee `0.001`/fill、adverse slippage `4 bps`/fill，并检查 `2x` 成本压力。
- Execution timing：信号 K 收盘确认，下一根 `15m` open 市价入场；gap 穿越 stop 按更差 open，bar 内 stop/TP 冲突按 `stop-first`，指标退出下一根 open 执行。
- Position sizing：固定 `1.0x` allocation，单仓、不加仓。
- Funding / carry：按经审计的官方历史 funding 逐事件计入。

## Evidence Map

- Specs：无。
- Diagnostics：[首轮冻结搜索最终诊断](diagnostics/btc-15m-keltner-trend-breakout-initial-search-2026-07-20.md)。
- Live specs / runner tracking：无。
- Scripts / artifacts：[脚本说明](scripts/README.md)、[产物说明](artifacts/README.md)、[搜索摘要](artifacts/btc_15m_keltner_search_summary_2026-07-20.json)、[冻结选择](artifacts/btc_15m_keltner_frozen_selection_2026-07-20.json)、[一次 holdout 揭示](artifacts/btc_15m_keltner_holdout_reveal_2026-07-20.json)。
