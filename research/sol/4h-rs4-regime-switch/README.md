# SOL-4H-RS4-Regime-Switch

- Full family name：`SOL-4H-RS4-Regime-Switch`
- Short id：`SOL-4H-RS4`
- 市场/周期：Binance USD-M Futures `SOLUSDT` perpetual；`1h` 标准数据聚合为 `4h`
- 机制：压缩 regime 的 MACD 双向 v10 leg + 扩张/高效率 regime 的 Donchian melt leg。
- 当前状态：首轮 `401` 规格 base-gate `0`；`explore / not promoted / not live-ready`。

## Family 边界

本 family 是 HYPE RS4 机制向 SOL `4h` 的独立迁移，不继承 HYPE-RS4 或 SOL-1H-AR 的版本号。它使用显式压缩/扩张 router，不属于 Adaptive-Regime 的 style ensemble。

## 当前结论

- 最好的失败观察 prefit annual `1.2045x`、DD `-26.58%`。
- reused holdout return `-23.04%`、DD `-34.13%`。
- current full annual `1.0312x`、DD `-47.97%`。
- fresh forward 约 10 天 `+2.24%`、3 笔，不足以改变中期失败。
- 当前 position-return 模型没有交易所驻留的 intrabar protection stop，构成 live-executable blocker。

## 入口

- 主账：`sol-4h-rs4-core-ledger.md`
- 决策记录：`decision-log.md`
- 首轮报告：`diagnostics/sol-4h-rs4-search-2026-07-13.md`
- 搜索脚本：`scripts/research_sol_4h_rs4_search.py`
- 机器证据：`artifacts/`

