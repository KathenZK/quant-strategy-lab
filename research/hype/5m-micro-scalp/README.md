# HYPE-5M-Micro-Scalp

- Full family name：`HYPE-5M-Micro-Scalp`（历史别名：`HYPE-5M-MS`）
- 市场/周期：Binance USD-M Futures `HYPEUSDT` perpetual `5m`
- 机制：高频高胜率小单笔利润 scalp 搜索；closed-bar 信号、next-open 入场、入场即固定 TP/SL bracket、同 K 冲突 stop-first。
- 当前状态：原始 `3-5` 笔/天形态 `not promoted / not live-ready`；放宽频率后 V1-V1.3 已登记，均为 `registered / not promoted / not live-ready`。

## 边界

- 不是 `HYPE-5M-Pullback-Trail`、`HYPE-1M-EMA-Crossover` 或 `HYPE-15M-Multi-Indicator-Intraday` 的版本。
- 不要引用裸版本号；使用 `HYPE-5M-Micro-Scalp-V1.2` 这类完整名称。

## 入口

- 主账（V1/V1.1/V1.2/V1.3 版本表）：`hype-5m-micro-scalp-core-ledger.md`
- 决策记录（全部搜索/消融/微调批次）：`decision-log.md`
- 当前 canonical 规格：`canonical-specs/hype-5m-micro-scalp-v1-3-baseline-spec.md`（18 个有效参数，与 V1.2 逐笔等价）
- 首次广搜（原始形态 not-promoted 证据）：`diagnostics/hype-5m-micro-scalp-search-2026-06-26.md`

研究脚本在 `scripts/`，被报告引用的 JSON/CSV 在 `artifacts/`；搜索报告与审计在 `diagnostics/`，探索笔记在 `research-notes/`。逐批结论以主账和 decision-log 为准。
