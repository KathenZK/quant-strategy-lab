# HYPE-5M-PBTR-V2.1A live-realistic 退出审计 2026-06-24

Family id：`HYPE-5M-PBTR`

本报告复核已经进入实盘/实盘 dry-run 的 `HYPE-5M-PBTR-V2.1A` 是否存在与 V3.3/V4 同类的锁仓期 stop 可执行性问题。

## V2.1A 参数

| 参数 | 值 |
| --- | ---: |
| `ema_fast` | `21` |
| `ema_slow` | `96` |
| `pullback_buffer` | `0.01` |
| `stop_atr` | `0.5` |
| `trail_atr` | `0.75` |
| `min_hold_bars` | `6` |
| `max_hold_bars` | `96` |
| `final_dir_htf_threshold` | `0.5` |

## 审计口径

- `原始实盘成本回测`：沿用既有 V2.1A 报告口径，锁仓期内不触发 stop，解锁后按回测 stop 价成交。
- `开仓即初始保护止损`：锁仓期只激活 `0.5 ATR` 初始 stop，不激活 trailing，用于模拟一开仓就挂紧保护止损。
- `live-realistic`：锁仓期不挂策略止损；解锁时若 `active_stop` 已被开盘价穿越，则按开盘市价退出，否则挂 reduce-only stop-market 并继续只收紧 trailing。

## 结果对比

| 口径 | 交易数 | 年化 | 胜率 | PF | payoff | 最大回撤 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `原始实盘成本回测` | `3146` | `352.15x` | `51.40%` | `2.79` | `2.64` | `-6.62%` |
| `开仓即初始保护止损` | `5358` | `0.00x` | `13.57%` | `0.46` | `2.92` | `-99.95%` |
| `live-realistic` | `3145` | `0.00x` | `37.71%` | `0.54` | `0.88` | `-99.85%` |

## 可执行性诊断

- 锁仓期内触及初始 `0.5 ATR` stop 的比例 `86.39%`；若开仓即挂初始保护止损，`86.24%` 的交易会在锁仓期内被保护止损打掉。
- live-realistic 口径下，解锁时可正常挂 dormant stop 的比例 `30.97%`；解锁即市价退出 `69.03%`；后续 stop-market `28.68%`；后续 gap 市价退出 `2.29%`。
- 锁仓期 MAE bps：P10 `-151.84`，P50 `-60.60`，P90 `-18.37`；解锁 active stop 距离 entry bps：P10 `5.74`，P50 `22.99`，P90 `86.29`。
- live-realistic 周切片：盈利周 `2/56`，中位周收益 `-10.16%`。

## 结论

`HYPE-5M-PBTR-V2.1A` 也存在同类结构性问题。它的 `min_hold_bars=6` 比 V3.3/V4 短，最终 HTF 过滤也降低了频率，但原始收益仍高度依赖一个不够实盘化的退出假设：解锁后 stop 已被价格穿越时，回测按 stop 价成交，而实盘只能按市价退出。

如果当前实盘 runner 是“前 6 根 K 不挂策略止损、解锁后才挂 trailing stop”，则历史回测指标不能作为真实预期，必须把 live-realistic 口径作为风险基线。如果当前 runner 开仓即挂 `0.5 ATR` 初始保护止损，则也与原始回测不等价，反事实回测已经坍缩为 PF 小于 1。

建议：不要立刻扩大 V2.1A 仓位。当前实盘可以作为极小资金监控样本继续跑，但验收应改为真实成交日志驱动：记录锁仓期 MAE、解锁即市价退出比例、实际 stop 滑点、订单失败率，以及前 300-500 笔的真实 PF/payoff。下一轮研究应重做退出路径，而不是继续基于当前 `min_hold_bars + trailing` 回测指标做版本升级。

## 产物

- 脚本：`research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v21a_live_realistic_audit.py`
- JSON：`artifacts/hype_5m_pbtr_v21a_live_realistic_audit.json`
- 汇总 CSV：`artifacts/hype_5m_pbtr_v21a_live_realistic_audit_summary.csv`
- 交易诊断 CSV：`artifacts/hype_5m_pbtr_v21a_live_realistic_audit_trade_diagnostics.csv`
- rolling CSV：`artifacts/hype_5m_pbtr_v21a_live_realistic_audit_rolling.csv`
- weekly CSV：`artifacts/hype_5m_pbtr_v21a_live_realistic_audit_weekly.csv`
