# HYPE-5M-PBTR live-realistic trailing 回测 2026-06-24

Family id：`HYPE-5M-PBTR`

本报告按更接近实盘订单时序的退出口径，复核 `HYPE-5M-PBTR-V3.3` 与 `HYPE-5M-PBTR-V4`：锁仓期不挂策略止损；锁仓结束时若 `active_stop` 已被当前价格穿越，则直接 reduce-only 市价平仓；否则挂 reduce-only stop-market，之后每根已收盘 K 线只收紧 trailing stop。

## 回测口径

- 入场仍为信号 K 收盘确认，下一根 5m K 开盘成交，并使用既有实盘成本：手续费 `4.1466 bps/turnover`、开仓滑点 `10.73 bps`、平仓滑点 `2.64 bps`。
- 锁仓期内不挂 `stop_atr` 或 trailing 策略止损；这里只复核策略退出，不额外模拟账户级 emergency stop。
- 解锁前的 trailing 参考峰谷只用已完成的锁仓 K 线；第一个可退出 K 开盘前计算 `active_stop`。
- 若 stop 价已被开盘价穿越，按该根 K 开盘市价退出；若未穿越，则在该根 K 期间按 stop-market 触发。

## 结果对比

| 版本 | 交易数 | 年化 | 胜率 | PF | payoff | 最大回撤 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `V3.3 原始回测` | `8027` | `1327928815.51x` | `55.66%` | `4.15` | `3.31` | `-8.69%` |
| `V3.3 live-realistic` | `8024` | `0.00x` | `38.43%` | `0.58` | `0.94` | `-100.00%` |
| `V4 原始回测` | `5053` | `28884173450807.53x` | `72.95%` | `19.92` | `7.39` | `-11.27%` |
| `V4 live-realistic` | `5053` | `0.00x` | `42.09%` | `0.67` | `0.92` | `-100.00%` |

## 订单可执行性诊断

- `V3.3 live-realistic` 解锁时可正常挂 dormant stop 的比例 `24.65%`；解锁即市价退出 `75.35%`；后续 stop-market `22.74%`；后续 gap 市价退出 `1.91%`。
- `V3.3 live-realistic` 锁仓期 MAE bps：P10 `-163.70`，P50 `-62.09`，P90 `-19.30`；解锁 active stop 距离 entry bps：P10 `5.16`，P50 `23.01`，P90 `105.31`。
- `V4 live-realistic` 解锁时可正常挂 dormant stop 的比例 `11.42%`；解锁即市价退出 `88.58%`；后续 stop-market `10.57%`；后续 gap 市价退出 `0.85%`。
- `V4 live-realistic` 锁仓期 MAE bps：P10 `-230.89`，P50 `-84.26`，P90 `-24.45`；解锁 active stop 距离 entry bps：P10 `5.64`，P50 `42.15`，P90 `185.38`。

## 时间切片摘要

- `V3.3 live-realistic` 周数 `56`，盈利周 `2/56`，中位周收益 `-23.71%`；月数 `14`，盈利月 `0/14`。
- `V4 live-realistic` 周数 `56`，盈利周 `1/56`，中位周收益 `-16.93%`；月数 `14`，盈利月 `0/14`。

## 结论

`live-realistic` 口径没有把策略变成固定持仓后直接平仓，而是保留 trailing stop 的状态机；但结果显示两个版本都从原始回测的高 PF 结构坍缩为亏损结构。主要原因是大量交易在解锁当刻 `active_stop` 已经被当前价格穿越，实盘只能市价退出，而不能按已经穿越的 stop 价成交。

因此，`HYPE-5M-PBTR-V3.3` 和 `HYPE-5M-PBTR-V4` 都不能按当前参数直接作为实盘交接版本。真正可执行的后续方向应重新设计退出：例如缩短或取消 `min_hold_bars`、解锁时重新初始化 trailing stop、或把锁仓期内的风险约束改为明确的宽 emergency stop 后重新搜索参数。

## 产物

- 脚本：`research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_live_realistic_trailing.py`
- JSON：`artifacts/hype_5m_pbtr_live_realistic_trailing.json`
- 汇总 CSV：`artifacts/hype_5m_pbtr_live_realistic_trailing_summary.csv`
- 交易诊断 CSV：`artifacts/hype_5m_pbtr_live_realistic_trailing_trade_diagnostics.csv`
- rolling CSV：`artifacts/hype_5m_pbtr_live_realistic_trailing_rolling.csv`
- weekly CSV：`artifacts/hype_5m_pbtr_live_realistic_trailing_weekly.csv`
- monthly CSV：`artifacts/hype_5m_pbtr_live_realistic_trailing_monthly.csv`
