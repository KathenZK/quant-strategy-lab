# SOL-1H-Pullback-Bracket Core Ledger

## Family Identity

- Full family name：`SOL-1H-Pullback-Bracket`
- Alias：`SOL-1H-PB`
- Market / exchange / symbol / timeframe：Binance USD-M Futures / `SOLUSDT` perpetual / `1h`
- Mechanism summary：趋势持续、回踩 arm、恢复确认与即时 ATR bracket。
- Boundary：独立于 SOL-1H-AR，不继承版本号。

## Current State

- Current version(s)：无登记版本。
- Current status：`explore`
- Runner / dry-run / live status：无 runner；未进入 dry-run/live。
- Live-readiness blockers：hard pass `0`；收益低；fresh forward 为负；K+2 收益接近消失。
- Next decision gate：除非提出提高事件质量或频率的机制变化，否则不继续同参数面搜索。

## Version Rules

- `V1`：必须由用户明确登记，并具备足够 fresh forward 与 live-executable 证据。
- Observation：首轮最佳值不自动登记版本。
- New version trigger：prefit/validation 同正、reused audit 不崩、fresh forward 具备足够交易且 K+2/成本压力可接受。

## Version Table

当前无登记版本。

## Shared Assumptions

- Data：2026-07-13 刷新的最近两年闭合 SOL `1h` K。
- Cost：fee `0.001`/fill、slippage `4 bps`/fill。
- Execution timing：闭合 K confirm，下一根 open 入场；即时 bracket；stop-first；gap-open。
- Position sizing：fixed 或 ATR risk sizing，最大 `3x`。
- Funding / carry：逐笔计真实 Binance funding。

## Evidence Map

- Diagnostics：`diagnostics/sol-1h-pullback-bracket-search-2026-07-13.md`
- Scripts / artifacts：`scripts/research_sol_1h_pullback_bracket_search.py`、`artifacts/`

