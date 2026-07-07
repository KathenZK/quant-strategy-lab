# HYPE-Candle-Count-Reversal

- Full family name：`HYPE-Candle-Count-Reversal`（历史别名：`HYPE-CC`）
- 市场/周期：HYPE `15m`
- 机制：10 根 K 中 8 根同色的颜色计数反转 + ATR 风控，后续演化 early-exit 变体。
- 当前状态：archived/canonical specs；V35 曾实盘并出现 live underperformance，已降级为 execution-risk diagnostic（见下方诊断）。

## 边界

- 这里的 `V35` 不是 `HYPE-EMA-TB-V35`；不要凭 `v35` 文件名推断家族身份（历史报告文件名 `hype_v13_*`、`hype_v18_*`、`hype_v35_*` 等跨家族撞名，必须回链接文档确认）。
- 引用用完整名：`HYPE-CC-V13`、`HYPE-CC-V21`、`HYPE-CC-V35`。

## 入口

- 主账（milestone comparison ledger）：`hype-cc-15m-milestone-comparison.md`
- 决策记录：`decision-log.md`
- 版本规格：`canonical-specs/`（V13、V18 ATR672、V21 双向 early-exit、V35 复现参数等）
- V35 过拟合再诊断：`diagnostics/hype-cc-v35-parameter-overfit-rediagnosis-2026-06-29.md`
- V35 实盘表现不及回测复盘：`diagnostics/hype-cc-v35-live-underperformance-review-2026-06-29.md`

脚本在 `scripts/`，被报告引用的产物在 `artifacts/`，`legacy-canvas/` 为冻结迁移历史。
