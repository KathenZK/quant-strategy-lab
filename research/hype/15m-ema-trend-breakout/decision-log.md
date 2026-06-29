# HYPE-EMA-TB 决策日志

这是 HYPE EMA trend-breakout 研究的家族级阅读路径。

## 当前边界

- 本家族属于研究与规格材料。
- Active package code 只包含数据和研究数据集基础设施。
- 需要时使用 canonical specs 加当前数据湖重新生成回测。

## 版本记录

- `HYPE-EMA-TB-V2P`：早期 15m trend breakout with 1h confirmation。
- `HYPE-EMA-TB-V30`：baseline aligned trend-family checkpoint。
- `HYPE-EMA-TB-V34`：high-return low-drawdown candidate。
- `HYPE-EMA-TB-V35`：timeout-relaxed candidate。
- `HYPE-EMA-TB-V36`：Binance signal、Hyperliquid execution variant。

## 研究批次记录

- Binance HYPE `5m` pullback/trailing-stop 研究已迁移到 `../5m-pullback-trail/` 下独立的 `HYPE-5M-PBTR` 家族。不要把本 `HYPE-EMA-TB` 决策日志作为 `HYPE-5M-PBTR-V1/V2` 的事实来源。

## 证据政策

优先使用家族文档。Archived Cursor indexes 和 archived scripts/code 仅用于迁移证据或复现考古。
