# HYPE-EMA-Crossover

- Full family name：`HYPE-EMA-Crossover`（历史别名：`HYPE-EMA-X`）
- 市场/周期：Binance `HYPEUSDT` `15m`
- 机制：EMA96/384 金叉/死叉研究线，经 V14 时代过滤、出场、状态机、late re-entry、effective-cross 打分演化。
- 当前状态：`HYPE-EMA-X-V18` 为 `dry-run / forward-test required`（quant-runner `hype_ema_x` 模拟盘运行中，forward 报告见 [forward-tracking/README.md](forward-tracking/README.md)）；V15-V17.1 保留为 `registered / not promoted / not live-ready`。

## 边界

- 不要与 `HYPE-EMA-Trend-Breakout`（`HYPE-EMA-TB`）混用，即使都用 EMA96/384。
- 引用用完整名：`HYPE-EMA-X-V17`、`HYPE-EMA-X-V18` 等。

## 入口

- 主账（版本演化、指标、实现状态）：[hype-ema-x-core-ledger.md](hype-ema-x-core-ledger.md)
- 决策记录：[decision-log.md](decision-log.md)
- V18 干净参数规格：[hype-ema-x-v18-baseline-spec.md](specs/hype-ema-x-v18-baseline-spec.md)
- V18 forward 跟踪：[forward-tracking/README.md](forward-tracking/README.md)

按需打开 `diagnostics/`（执行审计、可行性复审）、`ablations/`、`research-notes/`（历史规则镜像）；脚本在 `scripts/`，证据在 `artifacts/`，`legacy-canvas/` 为冻结迁移历史。
