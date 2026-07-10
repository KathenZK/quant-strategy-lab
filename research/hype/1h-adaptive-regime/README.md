# HYPE-1H-Adaptive-Regime

- Full family name：`HYPE-1H-Adaptive-Regime`（历史别名：`HYPE-1H-AR`）
- 市场/周期：Binance USD-M Futures `HYPEUSDT` perpetual `1h`
- 机制：自适应市场状态策略——只在闭合 K 可确认的 regime 中启用对应入场腿（趋势/突破/均值回归），入场即挂保护性 bracket；多指标广搜 + ensemble。
- 当前状态：V1-V4 已登记（V4 为 25 参数剪枝微调基线）；2026-07-10 精确联合状态机审计已 supersede 旧 V4 近似指标，K+2/8bps 压力仍失败；`NO-GO / not promoted / not live-ready`。

## 边界

- 独立于 `HYPE-15M-Multi-Indicator-Intraday`、`HYPE-EMA-Crossover`、`HYPE-EMA-Trend-Breakout`、`HYPE-5M-Pullback-Trail`、`HYPE-6H-RS4-Regime-Switch`；不得用裸版本号跨家族引用。

## 研究协议（冻结口径）

- 数据：合约首根到最新闭合 `1h` K，Binance FAPI raw evidence + normalized 数据湖分区 + 资金费历史 + 合约过滤器快照。
- 硬门槛：年化权益倍率 `>=10x`、胜率 `>=50%`、最大回撤 `<20%`；须通过 train/validation/locked holdout、成本压力、延迟、邻域和 live-executable 审计才可讨论 promotion。
- 执行：闭合 K 信号、下一根 open 市价成交、入场即挂 stop/TP、同 K stop-first、跳空按 open 成交。
- 成本：fee `0.001`/fill、slippage `4 bps`/fill、真实资金费。
- 搜索引擎：本家族是 `research/_shared-kernels/1h-adaptive-regime-search/` 的原始出处（grandfathered 原位引用）。

## 入口

- 主账（V1-V4 版本表、指标与证据链接）：`hype-1h-ar-core-ledger.md`
- 决策记录：`decision-log.md`
- 版本规格：`specs/`（V1 baseline、V2 clean、V3 baseline、V4 pruned tuned）
- 数据质量报告：`diagnostics/hype-binance-1h-data-quality-2026-07-01.md`
- 最终 not-promoted 审计：`diagnostics/hype-1h-adaptive-regime-boundary-audit-2026-07-01.md`
- V4 精确联合状态机与压力优化：`diagnostics/hype-1h-ar-v4-execution-pressure-optimization-2026-07-10.md`

脚本在 `scripts/`（fetch / search / refine / audit），被报告引用的产物在 `artifacts/`。逐版本演进结论以主账和 decision-log 为准。
