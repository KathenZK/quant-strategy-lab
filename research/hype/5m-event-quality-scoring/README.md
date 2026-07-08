# HYPE-5M-Event-Quality-Scoring

- Full family name：`HYPE-5M-Event-Quality-Scoring`（历史别名：`HYPE-5M-EQS`）
- 市场/周期：Binance USD-M Futures `HYPEUSDT` perpetual `5m`
- 机制：事件质量打分——规则只生成候选事件（EMA 收复、VWAP/Bollinger 回归、影线拒绝、微突破、MACD 翻转、动量停顿），研究入场前上下文能否 walk-forward 排序出值得交易的子集；closed-bar 信号、next-open 入场、固定 bracket、stop-first。
- 当前状态：Seeded V1 在 strict seed-generation audit 中失败（严格滚动 seed 下 `-61.16%`）；`not promoted / not live-ready`，无 audit lead。

## 边界

- 不是 `HYPE-5M-Micro-Scalp`、`HYPE-5M-Pullback-Trail` 或 `HYPE-1M-EMA-Crossover` 的版本；不要用裸版本号引用。
- 如续做本家族，必须先做严格滚动 seed 的 V2 搜索；严格 OOS 出正结果前不得推进任何 promotion。

## 入口

- 主账（Base/精简版/审计边界）：`hype-5m-event-quality-scoring-core-ledger.md`
- 决策记录：`decision-log.md`
- 关键否决证据：`diagnostics/hype-5m-seeded-v1-strict-seed-audit-2026-06-27.md`
- 历史批次报告：`diagnostics/`（generic V0、seeded V0/V0.1、V1 live-feasibility 等）

脚本在 `scripts/`，被报告引用的 JSON/CSV 在 `artifacts/`。逐批结论以主账和 decision-log 为准。
