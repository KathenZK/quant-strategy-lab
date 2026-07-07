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
- `HYPE-EMA-TB-V37`：V35 + early-long 小仓位卫星影子观察版。
- `HYPE-EMA-TB-V38`：V35 + `mfe>=4.75` 锁 `4.25ATR` 的极窄 profit floor 保险观察版。

## 研究批次记录

- Binance HYPE `5m` pullback/trailing-stop 研究已迁移到 `../5m-pullback-trail/` 下独立的 `HYPE-5M-PBTR` 家族。不要把本 `HYPE-EMA-TB` 决策日志作为 `HYPE-5M-PBTR-V1/V2` 的事实来源。
- 2026-07-07：针对线上 `HYPE-EMA-TB-V35` 出现“接近 TP 后 ADX 变弱但指标退出被 MFE 禁用，利润回吐”的场景，测试分阶段 `profit floor`。结论：近期 `7d/1m` 有小幅改善，但全样本收益、Sharpe 和退出结构显著劣化，不建议直接合入 V35 主策略。报告见 `research-notes/hype-ema-tb-v35-profit-floor-diagnostic-2026-07-07.md`。
- 2026-07-07（第二轮）：13 变体窄口径扫描发现可用解：只在 `mfe_atr >= 4.75~4.9` 启动、锁 `4.25~4.4 ATR` 的极窄 profit floor 能把 full 收益保留在 base 的 84%~95%，maxDD 与 base 完全相同；启动线 `<= 4.5` 的档位、floor 后冷却、直接收紧 TP 全部否决。`floor_475_lock425` 与 `floor_49_lock44` 记为 diagnostic 观察候选，未 promotion。报告见 `research-notes/hype-ema-tb-v35-narrow-profit-floor-2026-07-07.md`。
- 2026-07-07（V38 登记）：按用户指定，将能覆盖 `4.86ATR` 峰值回吐场景的 `floor_475_lock425` 记录为 `HYPE-EMA-TB-V38`。Binance API 补充窗口显示 V38 `+7110.75% / -23.46% / Sharpe 4.60 / 108 笔`，相同窗口 V35 为 `+8360.80% / -23.46% / 4.75 / 108 笔`；V38 是收益让渡换近 TP 回吐保护，不是收益增强。叠加到 V37 后，`V37+V38` 为 `+8777.85% / -24.76% / Sharpe 4.71 / 150 笔`，低于纯 V37 复现 `+10316.90% / -24.76% / 4.85 / 150 笔`，因此不登记新 promotion 版本。报告见 `research-notes/hype-ema-tb-v38-v37-floor-backtest-2026-07-07.md`。

## 证据政策

优先使用家族文档。Archived Cursor indexes 和 archived scripts/code 仅用于迁移证据或复现考古。
