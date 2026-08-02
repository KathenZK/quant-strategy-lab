# HYPE-15M-MA7-MA30-Pyramiding Core Ledger

## Family Identity

- Full family name：`HYPE-15M-MA7-MA30-Pyramiding`
- Alias：`HYPE-15M-MA-PT`
- Market / exchange / symbol / timeframe：Binance USD-M Futures，`HYPEUSDT` perpetual，`15m`
- Mechanism summary：EMA7/EMA30 双向 reclaim，初始 `0.5x`，浮盈后目标重置 `3x`，ATR 保护与均线退出。
- Boundary / collision warnings：不是 `HYPE-1D-PT` 的版本，也不是 `HYPE-EMA-X`、`HYPE-EMA-TB`、`HYPE-15M-MMTF` 或 `HYPE-15M-MHEF` 的变体。

## Current State

- Current version(s)：无；当前为未编号的两种退出 observation。
- Current status：`explore / not promoted / not live-ready`
- Runner / dry-run / live status：无。
- Live-readiness blockers：full 样本中 opposite-cross 控制组净值仅 `0.000000237x`、MDD `-99.99998%`；close-through-MA7 组更低至 `0.0000000267x`、MDD `-99.999998%`。MA7 退出把 campaign 从 `1,686` 增至 `2,801`、胜率从 `27.28%` 降至 `12.50%`；零成本仍分别损失 `98.65%`、`98.16%`。
- Next decision gate：本轮固定参数与 MA7 退出均判失败；不得继续在已揭示结果上微调。如果继续 15m 研究，需冻结 materially new entry/holding mechanism 与新验证边界。

## Version Rules

- 本次对照不登记版本。
- 只有用户明确要求登记时才创建本家族 `V1`；登记不表示 promotion。
- 入场身份、加仓结构、周期或核心退出状态机变化属于新 observation 或新版本，不继承 1D 证据。

## Version Table

当前无 registered version。

## Shared Assumptions

- Data：Binance USD-M 已收盘原生 `15m` K；实际 funding。
- Cost：手续费 `0.001/fill`、基础不利滑点 `4 bps/fill`；另审计 `8 bps/fill`。
- Execution timing：收盘确认，下一根 open 执行；另审计 `K+2`。
- Position sizing：初始 `0.5x`，浮盈条件满足后目标重置 `3x`；实际成交之间数量固定。

## Evidence Map

- Specs：[冻结对照契约](specs/hype-15m-ma7-exit-comparison-contract-2026-07-30.md)
- Diagnostics：[MA7 退出对照](diagnostics/hype-15m-ma7-exit-comparison-2026-07-30.md)
- Scripts / artifacts：[scripts/README.md](scripts/README.md) · [artifacts/README.md](artifacts/README.md)
