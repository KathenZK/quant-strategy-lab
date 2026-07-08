# HYPE-EMA-X-V17.1 严格口径实盘可执行性审计 2026-07-01

Family id：`HYPE-EMA-X`

审计对象：`HYPE-EMA-X-V17.1`。信号与 `HYPE-EMA-X-V17` 完全相同，仅 `hq_scale = 1.1`、`lq_scale = 1.0`。

数据切片：与主台账一致，截断到 `2026-06-01T03:00:00+00:00` 后再取最近 365 天 1Y 窗口。

执行成本沿用研究脚本默认值：滑点 `0.0005`、单次成交成本 `0.00085`（与主台账一致，未改用 Binance 默认 `0.001 fee + 4bps` 压力口径）。

## 结论

未发现明确未来函数，也未发现 `HYPE-5M-PBTR` 那类 lockout 后按 stale stop 价补成交的问题。信号在第 `t` 根 15m K 收盘确认，最早第 `t+1` 根 open 入场；1h 指标经 `shift(1)` 对齐；`swing96` 结构破坏使用 `shift(1)` 的前高/前低；收盘类退出在下一根 open 成交。

但 `V17.1` 仍不能直接视为 live-ready：1Y 仅 `33` 笔交易、无生产 runner、无重启恢复/保护单审计；硬止损在 baseline 中按 high/low 触发后仍以 stop price 成交，属于 stop-market 乐观上界；本次样本 baseline 虽 `0` 笔 stop_loss，但路径上仍有触及止损价的持仓段，必须用压力口径重估。

## 数据与未来函数检查

- 数据范围：`2025-05-30T10:30:00+00:00` 到 `2026-06-01T03:00:00+00:00`，`35203` 根 15m K。
- 缺口/重复/非法 OHLC：missing `0`，duplicate `0`，invalid OHLC `0`。
- 关键字段空值：`{"close": 0, "high": 0, "low": 0, "open": 0, "volume": 0}`。
- 截断重算因果性检查：`126` 个 feature-point 对比，失败 `0` 个。

检查方式：对多个历史索引只保留该索引及以前的数据，重新计算 EMA/ADX/ATR/1h/trend_score/swing96 等特征，再与全量计算在同一索引的值比较。

## Baseline 复现（1Y 窗口）

- 收益：`3861.48%`（台账 `+3861.48%`，一致）
- 最大回撤：`-19.44%`（台账 `-19.44%`，一致）
- 胜率：`90.91%`（台账 `90.91%`，一致）
- 交易数：`33`（台账 `33`，一致）
- 退出分布：`{"hard_swing96": 4, "warning_confirm_osc": 10, "warning_confirm_volume": 19}`

## 严格执行口径对比

| 口径 | 交易数 | 1Y收益 | 最大回撤 | Sharpe | 退出分布 |
| --- | ---: | ---: | ---: | ---: | --- |
| `baseline` | `33` | `3861.48%` | `-19.44%` | `4.77` | `{"hard_swing96": 4, "warning_confirm_osc": 10, "warning_confirm_volume": 19}` |
| `stop_gap_open` | `33` | `3861.48%` | `-19.44%` | `4.77` | `{"hard_swing96": 4, "warning_confirm_osc": 10, "warning_confirm_volume": 19}` |
| `stop_delay_1bar` | `33` | `3861.48%` | `-19.44%` | `4.77` | `{"hard_swing96": 4, "warning_confirm_osc": 10, "warning_confirm_volume": 19}` |
| `stop_market_extra_slip` | `33` | `3861.48%` | `-19.44%` | `4.77` | `{"hard_swing96": 4, "warning_confirm_osc": 10, "warning_confirm_volume": 19}` |

口径说明：

- `baseline`：当前研究脚本默认。硬止损 intrabar 触发后按 stop price + 滑点成交；结构/预警/反向交叉收盘确认后下一根 open 出场。
- `stop_gap_open`：若开盘已穿越止损，则按 open 市价退出，不再假设拿到 stop price。
- `stop_delay_1bar`：入场当根不检查止损，模拟 bracket 晚一根 15m 才生效。
- `stop_market_extra_slip`：仍按 stop price 触发，但额外加 `4bps` 穿越滑点。

## 价格穿越与同 K 风险

- 信号时序异常：`0` 笔（应为 `0`）。
- 持仓路径上曾触及止损价的交易：`0` 笔；baseline 实际 `stop_loss` 为 `0` 笔。
- 入场当根触及止损：`0` 笔；其中开盘穿越止损：`0` 笔。
- `stop_gap_open` 相对 baseline 收益变化：`0.00%`，回撤变化：`0.00%`。
- `stop_delay_1bar` 相对 baseline 收益变化：`0.00%`，回撤变化：`0.00%`。
- `stop_market_extra_slip` 相对 baseline 收益变化：`0.00%`，回撤变化：`0.00%`。

## 代码级时序审计

- `research_hype_v13_late_reentry.py`：bar `i` 收盘生成 signal → 设置 `pending_entry`；bar `i+1` open 成交。
- `entry_atr` 使用 `atr672[i-1]`（入场 bar 的前一根已完成 K）。
- `research_hype_ema_cross_strategy.add_htf_features()`：`htf.shift(1)` 后再对齐到 15m，避免 1h 未来数据。
- `hard_trend_invalidated(swing96)`：`low96/high96` 使用 `shift(1)`，收盘破位后下一根 open 出场。
- 不存在 `HYPE-5M-PBTR` V3/V4 那种 trailing stop 更新后仍按旧 stop 价补成交的逻辑；止损价自入场 ATR 固定。

## 当前决策

本审计当时仅支持 `registered / not live-ready`，不升级为 live。2026-07-08 后续确认 V18（V17.1 的干净参数规格）已进入 quant-runner `dry-run / forward-test required`，以家族主账和 [../forward-tracking/README.md](../forward-tracking/README.md) 为准。
`+3861.48% / -19.44%` 应继续按 1Y 研究切片 + baseline 执行上界阅读。
若使用截至当前 data lake 全量末端（例如 `2026-06-26`）的 rolling 1Y 窗口，收益会降到约 `+3365.62%`；这不代表执行口径错误，而是研究切片末端漂移。
若要做 promotion，下一步必须补：stop-market 实盘日志、保护单延迟/重启恢复、以及 `0.001 fee + 4bps` 的统一 Binance 压力复跑。

## 产物

- 脚本：`research/hype/15m-ema-crossover/scripts/research_hype_ema_x_v17_1_strict_live_audit.py`
- Markdown：`research/hype/15m-ema-crossover/diagnostics/hype-ema-x-v17-1-strict-live-audit-2026-07-01.md`
- summary：`research/hype/15m-ema-crossover/artifacts/hype_ema_x_v17_1_strict_live_audit_summary_2026-07-01.csv`
- trades：`research/hype/15m-ema-crossover/artifacts/hype_ema_x_v17_1_strict_live_audit_trades_2026-07-01.csv`
- causality：`research/hype/15m-ema-crossover/artifacts/hype_ema_x_v17_1_strict_feature_causality_2026-07-01.csv`
- timing：`research/hype/15m-ema-crossover/artifacts/hype_ema_x_v17_1_strict_signal_timing_2026-07-01.csv`
- JSON：`research/hype/15m-ema-crossover/artifacts/hype_ema_x_v17_1_strict_live_audit_2026-07-01.json`
