# HYPE-1D-Pyramiding-Trend Core Ledger

## Family Identity

- Full family name：`HYPE-1D-Pyramiding-Trend`
- Alias：`HYPE-1D-PT`
- Market / exchange / symbol / timeframe：Binance USD-M Futures，`HYPEUSDT` perpetual，UTC `1d`
- Mechanism summary：日线趋势突破/动量 campaign，`1x` 初始仓位，仅在浮盈后按 ATR 台阶最多加到 `3x`。
- Boundary / collision warnings：不是连续 forecast 的 `HYPE-1D-MHEF`，不继承任何 intraday HYPE 家族身份或证据。

## Current State

- Current version(s)：无；当前为未编号广搜。
- Current status：`explore / not promoted / not live-ready`
- Runner / dry-run / live status：无。
- Live-readiness blockers：`398,456` 个配置无三项硬目标同时命中；冻结 shortlist 最佳生存 observation 仅 `2.4818x / 76.47% / -19.62%`，且 `K+2` 回撤 `-32.08%`；无 registered version 或 runner 实现。
- Next decision gate：等待新增日线历史后重验，或由用户明确修改目标/时间周期；当前不登记版本、不推进 runner。

## Version Rules

- Registration / freeze：仅在用户明确要求登记时创建 `V1`，默认进入 `registered`，不表示 promotion。
- `V1`：首个由用户要求登记、参数与证据完整冻结的日线浮盈加仓 campaign。
- `Vx.y`：信号身份不变，只做可逐路径对账的执行修正。
- Observation / diagnostic rows：未编号搜索保持 `explore`。
- New version trigger：机制族、方向、加仓结构、最大杠杆或核心退出状态机发生身份级变化。

## Version Table

当前无 registered version。

## Shared Assumptions

- Data：标准 Binance `HYPEUSDT` perpetual `1h` 数据聚合完整 UTC 日 K；实际 funding。
- Cost：手续费 `0.001/fill`，基础不利滑点 `4 bps/fill`，并审计 `8 bps/fill`。
- Execution timing：日 K 收盘计算，下一日 open 执行；同时审计 `K+2`。
- Position sizing：`1x` 初始 + 两个各 `1x` 浮盈加仓层，绝对上限 `3x`。
- Funding / carry：按上一持仓在下一次 open 调仓前结算。

## Evidence Map

- Specs：[搜索契约](specs/hype-1d-pt-search-contract-2026-07-22.md)
- Diagnostics / ablations：[2026-07-22 硬目标广搜](diagnostics/hype-1d-pt-hard-target-search-2026-07-22.md)
- Live specs：无。
- Runner tracking：无。
- Scripts / artifacts：[scripts/README.md](scripts/README.md) · [artifacts/README.md](artifacts/README.md)
