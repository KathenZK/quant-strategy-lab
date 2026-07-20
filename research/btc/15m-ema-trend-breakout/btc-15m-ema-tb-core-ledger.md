# BTC-15M-EMA-Trend-Breakout Core Ledger

## Family Identity

- Full family name：`BTC-15M-EMA-Trend-Breakout`
- Alias：`BTC-15M-EMA-TB`
- Market / exchange / symbol / timeframe：Binance USD-M Futures，`BTCUSDT` perpetual，`15m`
- Mechanism summary：快慢 EMA 趋势背景配合价格突破的双向趋势研究；具体信号、过滤、退出与仓位规则尚未冻结。
- Boundary / collision warnings：本家族不继承 `HYPE-EMA-Trend-Breakout` 的版本、参数或实盘状态，也不属于 `BTC-1H-Adaptive-Regime`。

## Current State

- Current version(s)：无注册版本。
- Current status：`explore / not promoted / not live-ready`。
- Runner / dry-run / live status：无 runner handoff、无 dry-run、无 live。
- Research conclusion：V40 模板迁移的原始基线、Stage 1/2 搜索与唯一一次 holdout 揭示均未产生通过门禁的类似盈利策略；冻结项只是 `diagnostic_near_miss`，不是 candidate。
- Live-readiness blockers：成本后 train 与 holdout 亏损、双倍成本亏损、参数邻域正收益比例 `0%`、development WFO 仅 `6/15` 个正收益 fold、holdout 仅 `18` 笔；完整 promotion review 也未启动。
- Next decision gate：停止围绕 V40 模板扩搜，不登记 V1、不创建 `live spec`、不进入 runner 或 manifest。只有新的机制级假设与新冻结实验才可重开。

## Version Rules

- `V1`：只有在参数、信号、过滤、退出、执行成本与证据窗口全部冻结，并完成可复现基线报告后才可登记。
- `Vx.y`：仅用于不改变核心机制与执行合同的小幅冻结调整；必须有独立规格和证据。
- Observation / diagnostic rows：数据刷新、质量审计和探索结果不是版本，不获得裸版本号。
- New version trigger：信号机制、执行时序、风控结构、仓位模型或关键冻结参数发生身份级变化。

## Version Table

当前无注册版本。探索脚本或数据审计不得写入版本表冒充版本证据。

## Shared Assumptions

- Data：Binance USD-M `BTCUSDT` perpetual `15m`；本次使用 `2024-07-14T00:00:00Z` 起的已闭合 OHLCV 与官方历史 funding，DQ blocker 为 `0`。
- Cost：显式 fee `0.001`/fill、adverse slippage `4 bps`/fill，并检查 `2x` 成本压力。
- Execution timing：本次迁移按 K0 close 确认、等待完整 K1、K2 open 入场；`gap-open` 穿越 stop 按更差 open，bar 内 TP/SL 冲突按 `stop-first`。
- Position sizing：本次迁移固定 `1.0x` allocation，不沿用 HYPE V40 的 ATR risk sizing。
- Funding / carry：按经审计的官方历史 funding 逐事件计入，不默认为零。

## Evidence Map

- Specs：尚无。
- Diagnostics / ablations：[V40 模板迁移最终诊断](diagnostics/btc-15m-ema-tb-v40-transfer-2026-07-17.md)、[诊断入口](diagnostics/README.md)。
- Live specs：无；当前不允许 handoff。
- Runner tracking：无。
- Scripts / artifacts：[脚本说明](scripts/README.md)、[产物说明](artifacts/README.md)、[数据质量审计](artifacts/btc_binance_15m_data_quality_latest.json)、[冻结切分](artifacts/btc_15m_v40_frozen_splits_2026-07-17.json)、[搜索摘要](artifacts/btc_15m_v40_search_summary_2026-07-17.json)、[冻结选择](artifacts/btc_15m_v40_frozen_selection_2026-07-17.json)、[一次 holdout 揭示](artifacts/btc_15m_v40_holdout_reveal_2026-07-17.json)。
