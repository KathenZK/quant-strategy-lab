# HYPE-15M-Multi-Mechanism-Trend-Following

- Full family name：`HYPE-15M-Multi-Mechanism-Trend-Following`（alias：`HYPE-15M-MMTF`）
- 市场/周期：Binance USD-M Futures `HYPEUSDT` perpetual `15m`
- 机制：独立纯趋势研究线；比较 breakout、momentum、EMA continuation、volatility expansion 等机制，闭合 K 线决策、下一根 open 执行、单净仓、最高 `3x`。
- 当前状态：V1-V3 `registered`；V3 `HARD-GATE-FAILED / not promoted / not live-ready`。

## 边界

本家族是 `15m` 多机制纯趋势搜索与消融线，不继承 `HYPE-EMA-Trend-Breakout`、`HYPE-EMA-Crossover`、`HYPE-15M-Keltner-Trend-Breakout`、`HYPE-15M-MII` 或 `HYPE-1H-MMTF` 的版本、参数、指标或结论；只复用标准数据湖和通用研究方法。

## 入口

- 核心台账：[hype-15m-mmtf-core-ledger.md](hype-15m-mmtf-core-ledger.md)
- 决策记录：[decision-log.md](decision-log.md)
- 数据冻结：[diagnostics/hype-15m-mmtf-data-freeze-2026-07-22.md](diagnostics/hype-15m-mmtf-data-freeze-2026-07-22.md)
- V1 广搜：[diagnostics/hype-15m-mmtf-v1-broad-search-2026-07-22.md](diagnostics/hype-15m-mmtf-v1-broad-search-2026-07-22.md)
- V1 规格：[specs/hype-15m-mmtf-v1-original-baseline-spec.md](specs/hype-15m-mmtf-v1-original-baseline-spec.md)
- V1 消融：[ablations/hype-15m-mmtf-v1-full-ablation-2026-07-22.md](ablations/hype-15m-mmtf-v1-full-ablation-2026-07-22.md)
- V2/V3 clean tune：[diagnostics/hype-15m-mmtf-v2-clean-tune-2026-07-22.md](diagnostics/hype-15m-mmtf-v2-clean-tune-2026-07-22.md)
- V3 最终审计：[diagnostics/hype-15m-mmtf-v3-final-audit-2026-07-22.md](diagnostics/hype-15m-mmtf-v3-final-audit-2026-07-22.md)
- 目标验收矩阵：[diagnostics/hype-15m-mmtf-goal-completion-matrix-2026-07-22.md](diagnostics/hype-15m-mmtf-goal-completion-matrix-2026-07-22.md)
- 脚本：[scripts/](scripts/)
- 保留产物：[artifacts/](artifacts/)
