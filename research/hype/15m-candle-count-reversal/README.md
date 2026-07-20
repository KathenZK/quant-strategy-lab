# HYPE-Candle-Count-Reversal

- Full family name：`HYPE-Candle-Count-Reversal`（历史别名：`HYPE-CC`）
- 市场/周期：HYPE `15m`
- 机制：10 根 K 中 8 根同色的颜色计数反转 + ATR 风控，后续演化 early-exit 变体。
- 当前状态：`HYPE-CC-V35` 为 `dry-run / forward-test required`（quant-runner `hype_candle_count` 模拟盘运行中，runner 观察报告见 [runner-tracking/README.md](runner-tracking/README.md)）；V35 曾 live underperformance 的诊断仍作为 execution-risk 历史证据保留。

## 边界

- 这里的 `V35` 不是 `HYPE-EMA-TB-V35`；不要凭 `v35` 文件名推断家族身份（历史报告文件名 `hype_v13_*`、`hype_v18_*`、`hype_v35_*` 等跨家族撞名，必须回链接文档确认）。
- 引用用完整名：`HYPE-CC-V13`、`HYPE-CC-V21`、`HYPE-CC-V35`。

## 入口

- 正式主账：[hype-cc-core-ledger.md](hype-cc-core-ledger.md)
- 历史里程碑明细：[hype-cc-15m-milestone-comparison.md](hype-cc-15m-milestone-comparison.md)
- 决策记录：[decision-log.md](decision-log.md)
- 版本规格：[specs/](specs/)（V13、V18 ATR672、V21 双向 early-exit、V35 复现参数等）
- V35 过拟合再诊断：[hype-cc-v35-parameter-overfit-rediagnosis-2026-06-29.md](diagnostics/hype-cc-v35-parameter-overfit-rediagnosis-2026-06-29.md)
- V35 实盘表现不及回测复盘：[hype-cc-v35-live-underperformance-review-2026-06-29.md](diagnostics/hype-cc-v35-live-underperformance-review-2026-06-29.md)
- V35 forward 跟踪：[runner-tracking/README.md](runner-tracking/README.md)

脚本在 `scripts/`，被报告引用的产物在 `artifacts/`，`legacy-canvas/` 为冻结迁移历史。
