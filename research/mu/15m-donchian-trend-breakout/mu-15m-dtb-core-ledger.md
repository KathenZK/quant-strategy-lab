# MU-15M-Donchian-Trend-Breakout Core Ledger

## Family Identity

- Full family name：`MU-15M-Donchian-Trend-Breakout`
- Alias：`MU-15M-DTB`
- Market / exchange / symbol / timeframe：Binance USD-M Futures `TRADIFI_PERPETUAL` / `MUUSDT` / `15m`
- Mechanism summary：长期 EMA regime 下做前序 Donchian 高点收盘突破；下一根 open 入场，以 ATR 初始止损、已完成 K 线 trailing stop 和 Donchian 低点退出。
- Boundary / collision warnings：独立于 [`MU-HYPE-XFER`](../mu-hype-xfer-session-aware-ledger.md)；不使用 HYPE/V14 的“V6”身份，不跨家族继承指标。

## Current State

- Current version(s)：无已登记版本；`dtb-5e79abef48cf` 为未登记搜索观察。
- Current status：`explore / not promoted / not live-ready`
- Runner / dry-run / live status：无 runner 实现、无 dry-run、无 live。
- Live-readiness blockers：Final audit `-4.13%` 且仅 2 笔；ALL 无 buy-and-hold 超额收益；Binance 历史约 104 天；缺长期多 regime、正式 CPCV、Monte Carlo、1m 相位、强平/盘口和 runner parity 证据。
- Next decision gate：停止当前机制扩搜；只允许从 2026-07-20 07:15 UTC 之后积累新的 prospective 数据，用冻结观察参数复审。

## Version Rules

- Registration / freeze：只有用户明确要求登记 `Vx` 才进入 `registered`；搜索候选哈希不占版本号。
- `V1`：必须有冻结参数、一次 final audit 和明确登记请求；登记不表示 promotion。
- `Vx.y`：只允许同一信号与退出状态机内的小范围参数观察。
- Observation / diagnostic rows：未登记候选使用策略哈希或日期，不使用裸版本号。
- New version trigger：方向、EMA regime、突破定义、退出/止损状态机、成本或执行时序发生实质变化。

## Version Table

| Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision / Live Readiness |
| --- | --- | --- | --- | --- | --- |
| `dtb-5e79abef48cf`（未登记观察） | `explore / not promoted / not live-ready` | EMA regime + Donchian192/96 + 3ATR trailing，固定 1x long-only | train `+19.42%/-10.28%`；validation `+3.76%/-2.99%`；final `-4.13%/-4.93%`，2 笔；ALL `+9.51%` vs B&H `+90.15%` | [冻结搜索诊断](diagnostics/mu-15m-dtb-frozen-search-2026-07-20.md) | `sample_insufficient / final gate failed`；不登记、停止扩搜 |

## Shared Assumptions

- Data：Binance `MUUSDT` closed `15m`，UTC，数据质量 blocker 必须为 0。
- Cost：每次成交 fee `0.001` + adverse slippage `4 bps`，并做 2×成本压力。
- Execution timing：收盘确认信号，下一根 open 成交；gap stop 使用更差 open；同 K 冲突 stop-first。
- Position sizing：单仓、固定 `1.0x`，不叠仓；杠杆不参与搜索。
- Funding / carry：逐事件计入 Binance funding；同一 15m K 多事件求和。

## Evidence Map

- Specs：无已登记版本，暂无 spec。
- Diagnostics / ablations：[冻结搜索与 final audit](diagnostics/mu-15m-dtb-frozen-search-2026-07-20.md)
- Live specs：无。
- Runner tracking：无。
- Scripts / artifacts：[脚本入口](scripts/README.md) · [产物索引](artifacts/README.md)
