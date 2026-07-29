# HYPE-15M-Sequential-Drift-State

- Full family name：`HYPE-15M-Sequential-Drift-State`（alias：`HYPE-15M-SDS`）
- 市场/周期：Binance USD-M Futures `HYPEUSDT` perpetual `15m`
- 机制：每根闭合 K 线更新方向证据，以顺序漂移、回归或 Kalman/CUSUM/结构确认驱动 `flat / armed / long / short` 迟滞状态机；状态变化后下一根 open 执行。
- 当前状态：`explore / not promoted / not live-ready`；四块初始机制均失败，尚无登记版本。

## 边界

这是独立的逐 K 趋势状态估计家族，不继承 `HYPE-EMA-TB`、`HYPE-EMA-X`、`HYPE-15M-MMTF` 或 `HYPE-15M-MHEF` 的版本、参数和结论。它不是价格突破后追单，也不是连续 EMA forecast 调仓。

## 入口

- 主账：[hype-15m-sds-core-ledger.md](hype-15m-sds-core-ledger.md)
- 决策记录：[decision-log.md](decision-log.md)
- 数据冻结：[hype-15m-sds-data-freeze-2026-07-28.md](diagnostics/hype-15m-sds-data-freeze-2026-07-28.md)
- 首轮基线与 prefit 搜索：[hype-15m-sds-baseline-and-prefit-search-2026-07-28.md](notes/hype-15m-sds-baseline-and-prefit-search-2026-07-28.md)
- Kalman + CUSUM + 结构确认：[hype-15m-sds-kalman-cusum-structure-2026-07-28.md](notes/hype-15m-sds-kalman-cusum-structure-2026-07-28.md)
- KCS 全参数消融：[hype-15m-sds-kcs-full-parameter-ablation-2026-07-28.md](ablations/hype-15m-sds-kcs-full-parameter-ablation-2026-07-28.md)
- 脚本：[scripts/](scripts/)
- 保留产物：[artifacts/](artifacts/)
