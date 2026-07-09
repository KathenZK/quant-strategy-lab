# HYPE-EMA-Trend-Breakout

- Full family name：`HYPE-EMA-Trend-Breakout`（历史别名：`HYPE-EMA-TB`）
- 市场/周期：HYPE `15m`
- 机制：EMA96/EMA384 趋势突破 / 追多追空，带 ADX、成交量、1h 确认、live-realistic 执行检查与跨所执行变体。
- 当前状态：active 研究线。`HYPE-EMA-TB-V35` 为 `live`（独立 hype-trend live runner 运行，部署早于当前 handoff 约定，`runner-tracking/` 回流待补）；V36-V39.1 为 `registered / not promoted / not live-ready` 观察版本。

## 边界

- 不是更早的 `HYPE-EMA-Crossover`（`HYPE-EMA-X`）金叉/死叉家族。
- 这里的 `V35` 不是 `HYPE-CC-V35` 或 `HYPE-EMA-X-V14`；历史报告文件名（`hype_v30_*`、`hype_v35_*` 等）跨家族撞名，必须回链接文档确认身份。
- Binance HYPE `5m` 回踩研究已拆分到独立家族 `../5m-pullback-trail/`；本地 `HYPE-5M-PBTR-V1/V2` 与本家族版本无关。
- 引用用完整名：`HYPE-EMA-TB-V30`、`HYPE-EMA-TB-V35`、`HYPE-EMA-TB-V36`。

## 入口

- 主账：`hype-ema-tb-core-ledger.md`
- 决策记录：`decision-log.md`
- 研究侧版本规格：`specs/`（V2P、V30、V34、V35、V36 等）
- Runner handoff / live spec：`live-specs/`

脚本在 `scripts/`，被报告引用的产物在 `artifacts/`，`legacy-canvas/` 为冻结迁移历史，`experiments/` 为历史实验材料。
