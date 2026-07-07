# HYPE-EMA-Crossover

- Full family name：`HYPE-EMA-Crossover`（历史别名：`HYPE-EMA-X`）
- 市场/周期：Binance `HYPEUSDT` `15m`
- 机制：EMA96/384 金叉/死叉研究线，经 V14 时代过滤、出场、状态机、late re-entry、effective-cross 打分演化。
- 当前状态：V15-V17.1 为 promoted research candidates（信号层主候选 V17），`V18` 是 V17.1 的干净参数规格，供 live spec / handoff 使用；均**非** live-approved。

## 边界

- 不要与 `HYPE-EMA-Trend-Breakout`（`HYPE-EMA-TB`）混用，即使都用 EMA96/384。
- 引用用完整名：`HYPE-EMA-X-V17`、`HYPE-EMA-X-V18` 等。

## 入口

- 主账（版本演化、指标、实现状态）：`hype-ema-x-core-ledger.md`
- 决策记录：`decision-log.md`
- V18 干净参数规格：`canonical-specs/hype-ema-x-v18-baseline-spec.md`

按需打开 `diagnostics/`（执行审计、可行性复审）、`ablations/`、`research-notes/`（历史规则镜像）；脚本在 `scripts/`，证据在 `artifacts/`，`legacy-canvas/` 为冻结迁移历史。
