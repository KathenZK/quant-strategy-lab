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
- `HYPE-EMA-TB-V39`：V35 温和消融改进版，`long_vol_min=0.35`、`short_target_atr_pct=0.022`，移除冗余空头 1h EMA 确认，保留 timeout 兜底。

## 研究批次记录

- Binance HYPE `5m` pullback/trailing-stop 研究已迁移到 `../5m-pullback-trail/` 下独立的 `HYPE-5M-PBTR` 家族。不要把本 `HYPE-EMA-TB` 决策日志作为 `HYPE-5M-PBTR-V1/V2` 的事实来源。
- 2026-07-07：针对线上 `HYPE-EMA-TB-V35` 出现“接近 TP 后 ADX 变弱但指标退出被 MFE 禁用，利润回吐”的场景，测试分阶段 `profit floor`。结论：近期 `7d/1m` 有小幅改善，但全样本收益、Sharpe 和退出结构显著劣化，不建议直接合入 V35 主策略。报告见 `research-notes/hype-ema-tb-v35-profit-floor-diagnostic-2026-07-07.md`。
- 2026-07-07（第二轮）：13 变体窄口径扫描发现可用解：只在 `mfe_atr >= 4.75~4.9` 启动、锁 `4.25~4.4 ATR` 的极窄 profit floor 能把 full 收益保留在 base 的 84%~95%，maxDD 与 base 完全相同；启动线 `<= 4.5` 的档位、floor 后冷却、直接收紧 TP 全部否决。`floor_475_lock425` 与 `floor_49_lock44` 记为 diagnostic 观察候选，未 promotion。报告见 `research-notes/hype-ema-tb-v35-narrow-profit-floor-2026-07-07.md`。
- 2026-07-07（V38 登记）：按用户指定，将能覆盖 `4.86ATR` 峰值回吐场景的 `floor_475_lock425` 记录为 `HYPE-EMA-TB-V38`。Binance API 补充窗口显示 V38 `+7110.75% / -23.46% / Sharpe 4.60 / 108 笔`，相同窗口 V35 为 `+8360.80% / -23.46% / 4.75 / 108 笔`；V38 是收益让渡换近 TP 回吐保护，不是收益增强。叠加到 V37 后，`V37+V38` 为 `+8777.85% / -24.76% / Sharpe 4.71 / 150 笔`，低于纯 V37 复现 `+10316.90% / -24.76% / 4.85 / 150 笔`，因此不登记新 promotion 版本。报告见 `research-notes/hype-ema-tb-v38-v37-floor-backtest-2026-07-07.md`。
- 2026-07-08：已将数据湖 Binance HYPEUSDT 永续 `15m` 更新到 `2026-07-08 05:30 UTC`，质量检查 0 blocker。最近 90 天 median ATR% 从前 90 天 `0.71%` 降到 `0.68%`，但 V35 最近 90 天仍有 TP 26 / SL 7 / indicator 2，收益 `+215.41%`、maxDD `-21.90%`；结论是不支持“波动率变小导致 TP/SL 失效”，更像趋势质量下降和低 ATR 下仓位更容易打满 3x。报告见 `research-notes/hype-ema-tb-recent-3m-volatility-audit-2026-07-08.md`。
- 2026-07-08（V35 overlay 回测）：测试低 ATR 降仓、严格入场、低 ADX 降仓和 V38 叠加。结论：低 ATR 降仓未改善最近 90 天 maxDD，严格入场显著劣化；最平衡的是 `low_adx35_cap25`，即 V35 信号触发时若 `ADX28 < 35` 则本笔 cap 从 `3.0x` 降到 `2.5x`。该变体 full `+6725.98% / -23.46% / Sharpe 4.74`，最近 90 天 `+195.10% / -19.79%`，相较 V35 最近 90 天 `+215.41% / -21.90%` 小幅牺牲收益换回撤缓和。记录为 defensive overlay 观察候选，未 promotion。报告见 `research-notes/hype-ema-tb-v35-low-atr-overlay-backtest-2026-07-08.md`。
- 2026-07-08（V35 全参数消融与微调 / V39 登记）：62 变体逐项消融 + 66 组微调网格（最近 90/30 天参与选参，已声明）。无效参数：timeout 384 根（0 触发）与空头 1h EMA 确认（与空头 ema_spread<0 互为备份），单独移除结果逐字节一致；尖峰参数（不能动）：adx_window 28、long_adx_min 28、adx_exit 22、hard_stop 7ATR、atr_window 672、disable_after_mfe 1.5。按用户指定，将候选 A 登记为 `HYPE-EMA-TB-V39`：`long_vol_min=0.35`、`short_target_atr_pct=0.022`、移除冗余空头 1h EMA 确认，实盘保留 `max_hold_bars=384` 兜底。V39 full `+9969.45% / -23.46% / Sharpe 4.81`，90d `+217.53% / -21.90% / 胜率 77.14%`，所有标准窗口不劣于 V35；登记为观察候选，未 live-ready。另一个候选 `v35_tuned_recent3m` 最近 90 天 `+254.77% / -19.79% / 胜率 82.35%` 三项全优于 V35，但 full 降至 `+6223.29% / -25.68%`，只作 regime 适配影子观察。报告见 `research-notes/hype-ema-tb-v35-full-ablation-recent-tune-2026-07-08.md`。
- 2026-07-08（空头放宽扫描）：针对"空单太少"（full 108 笔仅 24 笔空单），在候选 A 基线上扫描 `short_adx_min 32~36 × short_vol_min off/0.25/0.35/0.50` 共 19 个放宽组合。结论：全部否决，没有免费的放宽空间。每放宽一档 ADX，空单均笔收益从 +5.59% 掉到 +1.5~1.9%，胜率从 79% 掉到 55~58%；ADX<35 档位把 full maxDD 打到 -38%~-47%。空单少是该机制在 HYPE 上的生存方式（高门槛挡 squeeze），候选 A 空头参数维持 `short_adx_min=36`、`short_vol_min=0.50` 不变。报告见 `research-notes/hype-ema-tb-v35-short-relaxation-scan-2026-07-08.md`。
- 2026-07-08（V39 只做多诊断）：按 V39 参数关闭空头后，full 收益从 `+9969.45%` 降到 `+3231.34%`，Sharpe 从 `4.81` 降到 `4.21`，maxDD 仍为 `-23.46%`；最近 90 天几乎不变（`+217.53%` vs `+215.77%`）。V39 full 只有 24 笔空单，但空单胜率 `79.17%`、均笔 `+5.59%`，高于多单均笔 `+4.81%`。结论：空单少但质量高，不建议把 V39 改成 long-only。报告见 `research-notes/hype-ema-tb-v39-long-only-diagnostic-2026-07-08.md`。
- 2026-07-08（V39 空头结构微调）：针对"明显下跌不开空"，归因显示 96 个 24h 跌幅 <= -10% 区间中 82% 被 `ADX28>=36` 卡住，慢速 EMA96/384 过滤单独挡下 0 个；急跌段 ADX 上不来是机制生存方式，不是缺陷。24 变体结构扫描（快速 EMA24/96 / DI / 组合 / 增量路径 × ADX 32/34/36 × vol 0.35/0.50）：降 ADX 档位全灭（maxDD -38%~-47%）；唯一改善是空头趋势过滤换成 EMA24/96（`fast_adx36_v05` full `+11581.22% / -23.46% / Sharpe 4.94`），但与 V39 空单集合仅差 2 笔，证据太薄，仅记录为观察候选，不登记版本。V39 空头参数维持不变。报告见 `research-notes/hype-ema-tb-v39-short-structure-tune-2026-07-08.md`。
- 2026-07-08（V39 + V37 卫星叠加）：把 V37 early-long 卫星原样叠加到 V39 主仓。`V39+sat_v025` full `+12322.33% / -24.76% / Sharpe 4.91 / 149 笔`，所有分片优于纯 V39（`+9969.45% / -23.46% / 4.81`）与 V37 复现（`+10316.90% / -24.76% / 4.85`）；代价与 V37 同构：maxDD 加深约 1.3pp、组合胜率 79.44% -> 73.15%。卫星量能维持 canonical 0.25；用卫星补 V39 量能缺口（`sat_gap`）被否决（maxDD -25.98%，反向验证 V39 量能改动）。卫星 standalone 仅 42 笔，组合记录为叠加诊断影子观察，未登记版本、未 promotion；待 V39 跨所迁移与 walk-forward 通过后再评估正式登记。报告见 `research-notes/hype-ema-tb-v39-v37-satellite-2026-07-08.md`。

## 证据政策

优先使用家族文档。Archived Cursor indexes 和 archived scripts/code 仅用于迁移证据或复现考古。
