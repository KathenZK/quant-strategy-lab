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
- 2026-07-07：针对线上 `HYPE-EMA-TB-V35` 出现“接近 TP 后 ADX 变弱但指标退出被 MFE 禁用，利润回吐”的场景，测试分阶段 `profit floor`。结论：近期 `7d/1m` 有小幅改善，但全样本收益、Sharpe 和退出结构显著劣化，不建议直接合入 V35 主策略。报告见 `research-notes/hype-ema-tb-v35-profit-floor-diagnostic-2026-07-07.md`。
- 2026-07-07（第二轮）：13 变体窄口径扫描发现可用解：只在 `mfe_atr >= 4.75~4.9` 启动、锁 `4.25~4.4 ATR` 的极窄 profit floor 能把 full 收益保留在 base 的 84%~95%，maxDD 与 base 完全相同；启动线 `<= 4.5` 的档位、floor 后冷却、直接收紧 TP 全部否决。`floor_475_lock425` 与 `floor_49_lock44` 记为 diagnostic 观察候选，未 promotion。报告见 `research-notes/hype-ema-tb-v35-narrow-profit-floor-2026-07-07.md`。

## 证据政策

优先使用家族文档。Archived Cursor indexes 和 archived scripts/code 仅用于迁移证据或复现考古。
