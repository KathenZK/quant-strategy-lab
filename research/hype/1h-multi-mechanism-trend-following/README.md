# HYPE-1H-Multi-Mechanism-Trend-Following

- Full family name：`HYPE-1H-Multi-Mechanism-Trend-Following`（alias：`HYPE-1H-MMTF`）
- 市场/周期：Binance USD-M Futures `HYPEUSDT` perpetual `1h`
- 机制：独立纯趋势研究线；在闭合 `1h` K 上比较 breakout、momentum、EMA 与 volatility-expansion 趋势机制，下一根 open 执行，单净仓、最高 `3x`。
- 当前状态：V1-V3 `registered`；V3 locked OOS、压力与相位 `HARD-GATE-FAILED / NO-GO / not promoted / not live-ready`。

## 边界

本家族不继承 `HYPE-1H-Adaptive-Regime` 的身份、版本、参数或结论，也不属于 `HYPE-1H-Multi-Horizon-EMA-Forecast`。只复用仓库数据湖和通用质量检查基础设施。

## 入口

- 核心台账：[hype-1h-mmtf-core-ledger.md](hype-1h-mmtf-core-ledger.md)
- 决策记录：[decision-log.md](decision-log.md)
- 数据冻结与质量证据：[diagnostics/hype-1h-mmtf-data-freeze-2026-07-22.md](diagnostics/hype-1h-mmtf-data-freeze-2026-07-22.md)
- V1 广搜报告：[diagnostics/hype-1h-mmtf-v1-broad-search-2026-07-22.md](diagnostics/hype-1h-mmtf-v1-broad-search-2026-07-22.md)
- V1 冻结规格：[specs/hype-1h-mmtf-v1-original-baseline-spec.md](specs/hype-1h-mmtf-v1-original-baseline-spec.md)
- V1 消融：[ablations/hype-1h-mmtf-v1-full-ablation-2026-07-22.md](ablations/hype-1h-mmtf-v1-full-ablation-2026-07-22.md)
- V2/V3 clean tune：[diagnostics/hype-1h-mmtf-v2-clean-tune-2026-07-22.md](diagnostics/hype-1h-mmtf-v2-clean-tune-2026-07-22.md)
- V3 最终审计：[diagnostics/hype-1h-mmtf-v3-final-audit-2026-07-22.md](diagnostics/hype-1h-mmtf-v3-final-audit-2026-07-22.md)
- 目标验收矩阵：[diagnostics/hype-1h-mmtf-goal-completion-matrix-2026-07-22.md](diagnostics/hype-1h-mmtf-goal-completion-matrix-2026-07-22.md)
- 脚本：[scripts/](scripts/)
- 保留产物：[artifacts/](artifacts/)
