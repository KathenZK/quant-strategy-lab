# SOL-4H-RS4-Regime-Switch Core Ledger

## Family Identity

- Full family name：`SOL-4H-RS4-Regime-Switch`
- Alias：`SOL-4H-RS4`
- Market / exchange / symbol / timeframe：Binance USD-M Futures / `SOLUSDT` perpetual / `4h`
- Mechanism summary：压缩 MACD v10 leg 与扩张 Donchian melt leg 的显式 regime switch。
- Boundary：独立于 HYPE-RS4 与 SOL-1H-AR，不继承版本号。

## Current State

- Current version(s)：无登记版本。
- Current status：`explore`
- Runner / dry-run / live status：无 runner；未进入 dry-run/live。
- Live-readiness blockers：base-gate `0`；reused holdout 和 full 大幅回撤；成本翻倍失败；缺少 intrabar protection stop。
- Next decision gate：首轮已构成 NO-GO；除非机制改写为带即时保护 stop 的可执行状态机，否则不继续参数搜索。

## Version Rules

- `V1`：只有在用户明确登记且主账能记录完整证据、fresh forward 和 live-readiness 结论时创建。
- Observation：搜索最佳失败值不自动登记版本。
- New version trigger：必须先解决 protection stop blocker，并重新完成 prefit/holdout/fresh-forward 审计。

## Version Table

当前无登记版本。

## Shared Assumptions

- Data：2026-07-13 最近两年 SOL `1h` 标准数据聚合为完整 `4h` K。
- Cost：fee `0.001`/fill、slippage `4 bps`/fill。
- Execution timing：闭合 `4h` K 决策，下一根 `4h` open 生效。
- Position sizing：v10 `1x`；melt weight `0.5x/1x`；组合最大名义 exposure `2x`。
- Funding / carry：按持仓方向逐 `4h` bar 计真实 Binance funding。

## Evidence Map

- Specs：无。
- Diagnostics：`diagnostics/sol-4h-rs4-search-2026-07-13.md`
- Live specs：无。
- Runner tracking：无。
- Scripts / artifacts：`scripts/research_sol_4h_rs4_search.py`、`artifacts/`

