# SOL-1H-Pullback-Bracket

- Full family name：`SOL-1H-Pullback-Bracket`
- Short id：`SOL-1H-PB`
- 市场/周期：Binance USD-M Futures `SOLUSDT` perpetual `1h`
- 机制：EMA 趋势持续 → 回踩 arm → 恢复并突破前 K 确认 → 下一根 open + 即时 ATR bracket。
- 当前状态：首轮 `1500` 候选 hard pass `0`；`explore / not promoted / not live-ready`。

## Family 边界

本 family 是显式回踩/恢复事件状态机与即时 bracket，不继承 `SOL-1H-Adaptive-Regime` 的版本号，也不把 AR 的 `ema_pullback` 单 K style 当作当前身份。

## 当前结论

- 最好观察 prefit annual `1.1576x`、DD `-9.56%`。
- reused holdout return `+2.95%`，但只有 `3` 笔。
- fresh forward 约 10 天 return `-2.01%`、2 笔。
- full annual `1.1382x`；K+2 annual `1.0255x`，收益接近消失。
- 机制回撤可控但收益不足；首轮 NO-GO，不登记版本。

## 入口

- 主账：`sol-1h-pb-core-ledger.md`
- 决策记录：`decision-log.md`
- 首轮报告：`diagnostics/sol-1h-pullback-bracket-search-2026-07-13.md`
- 搜索脚本：`scripts/research_sol_1h_pullback_bracket_search.py`
- 机器证据：`artifacts/`

