# HYPE-5M-Pullback-Trail

- Full family name：`HYPE-5M-Pullback-Trail`（历史别名：`HYPE-5M-PBTR`）
- 市场/周期：Binance USD-M Futures `HYPEUSDT` perpetual `5m`
- 机制：回踩/恢复入场 + ATR trailing-stop / 固定 bracket 出场；V5 起强制 executable-first（闭合 K 信号、下一根 open 入场、入场即挂 bracket）。
- 当前状态：`HYPE-5M-PBTR-V6.2.1` 为 `dry-run / forward-test required`（quant-runner 模拟盘运行中，runner 观察报告见 `runner-tracking/`）；早期 V1-V4 因 stale stop fill / 锁仓止损问题 `not promoted / not live-ready`。

## 边界

- 本地 `V1/V2` 版本号 local 于本家族，不要与 `HYPE-EMA-Trend-Breakout`、`HYPE-EMA-Crossover`、`HYPE-Candle-Count-Reversal` 的同名版本串联。
- 带点版本的文件命名：`V3.2` 在文件名中写 `v3-2`（不是 `v32`），避免与未来 `V32` 混淆。

## 入口

- 主账（版本表与全部批次证据索引）：`hype-5m-pullback-trail-core-ledger.md`
- 决策记录：`decision-log.md`
- 当前版本交接规格：`live-specs/hype-5m-pbtr-v6-2-1-live-spec.md`
- 当前版本实盘可行性审计：`diagnostics/hype-5m-pbtr-v6-2-1-live-feasibility-audit-2026-06-30.md`
- 当前版本全参数消融：`ablations/hype-5m-pbtr-v6-2-1-full-parameter-ablation-2026-06-29.md`
- 与 MII V1.3 共享账户组合诊断：`../cross-strategy-account/diagnostics/hype-pbtr-v6-2-1-mii-v1-3-shared-account-2026-07-02.md`

历史批次报告按性质存放于 `diagnostics/`、`ablations/`、`notes/`、`live-specs/`；脚本在 `scripts/`，被报告引用的产物在 `artifacts/`。逐批结论与文件清单以主账和 decision-log 为准，不在本 README 复述。
