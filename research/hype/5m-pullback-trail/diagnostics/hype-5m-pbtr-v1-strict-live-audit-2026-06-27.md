# HYPE-5M-PBTR-V1 strict live audit 2026-06-27

Family id：`HYPE-5M-PBTR`

本报告复核 `HYPE-5M-PBTR-V1` 是否在严格可实盘成交口径下仍赚钱，避免用后续 V2/V3 修改结果倒推 V1。

数据区间：`2025-05-30 10:30:00+00:00` 到 `2026-06-26 04:15:00+00:00`；过滤后信号数 `2125`。

## V1 参数

| 参数 | 值 |
| --- | ---: |
| `ema_fast / ema_slow` | `21/96` |
| `pullback_buffer` | `0.0025` |
| `stop_atr` | `0.75` |
| `tp_atr` | `1.875` |
| `trail_atr` | `0.75` |
| `min_hold_bars` | `6` |
| `final_filter dir_htf >=` | `0.688442` |

## 审计口径

- `legacy stop-price fill`：旧回测口径，前 6 根不触发 stop/target，第 7 根后若 bar 内触及 stop/target，按 stop/target 价成交。
- `live-realistic`：前 6 根不挂策略 stop/target；第 7 根解锁时，如果 active stop 已被 open 穿越，则按 open 市价平；如果 target 已变成 marketable，也按 open 平；之后 stop-market / target-limit 只按从当时开始可挂的订单成交。
- `entry protective stop`：反事实保护口径，开仓即挂 `0.75 ATR` 初始保护止损；不代表 V1 原始策略，只用于看加保护后是否还赚钱。

## 结果

| 口径 | 交易数 | 总收益 | 年化 | 胜率 | PF | payoff | 最大回撤 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `legacy stop-price fill` | `1358` | `1713.55%` | `14.91x` | `54.20%` | `2.806` | `2.372` | `-7.77%` |
| `live-realistic` | `1357` | `-87.29%` | `0.15x` | `39.50%` | `0.637` | `0.976` | `-88.27%` |
| `entry protective stop` | `1852` | `-94.87%` | `0.06x` | `21.00%` | `0.510` | `1.918` | `-94.98%` |

## 可执行性诊断

- live-realistic 下，解锁时 stop 可正常挂上的比例 `31.47%`；解锁即 stop 市价退出 `68.53%`；后续 stop-market `19.97%`；target-limit `4.20%`。
- 锁仓期曾触及初始 stop 的比例 `73.54%`；锁仓期曾触及 target 但无订单可成交的比例 `20.56%`；若开仓即保护，保护止损/跳空保护止损退出比例 `74.46%`。
- 锁仓期 MAE bps：P10 `-143.395`，P50 `-59.813`，P90 `-18.621`；解锁 active stop 距离 entry bps：P10 `5.311`，P50 `27.260`，P90 `92.845`。
- live-realistic 周切片：盈利周 `10/57`，中位周收益 `-3.26%`；盈利月 `0/14`，中位月收益 `-12.58%`。

## 结论

`HYPE-5M-PBTR-V1` 的旧口径确实赚钱，但严格 live-realistic 口径不赚钱。问题不是后续简单“改坏了”，而是 V1 已经依赖同一类不可实盘化假设：锁仓期结束后，旧回测允许按已经被价格穿越的 stop/target 价成交；实盘只能从解锁时开始挂单或市价退出。

因此 V1 不能作为回退上线版本。后续 V2/V3 的确把交易频率和样本内收益推高，放大了这个缺陷；但缺陷在 V1 机制里已经存在。若要恢复这条线，应从 executable-first 状态机重新设计，而不是退回 V1 参数。

## 产物

- 脚本：`research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v1_strict_live_audit.py`
- JSON：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v1_strict_live_audit_2026-06-27.json`
- summary CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v1_strict_live_audit_summary_2026-06-27.csv`
- trade diagnostics CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v1_strict_live_audit_trade_diag_2026-06-27.csv`
- rolling CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v1_strict_live_audit_rolling_2026-06-27.csv`
- weekly CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v1_strict_live_audit_weekly_2026-06-27.csv`
- monthly CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v1_strict_live_audit_monthly_2026-06-27.csv`
