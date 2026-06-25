# HYPE-5M-PBTR-V3.3 immediate TP 审计 2026-06-25

Family id：`HYPE-5M-PBTR`

本报告把 V2.1A 的即时止盈补救想法迁移到 `HYPE-5M-PBTR-V3.3`：开仓后立即挂 `1 * ATR14` 固定止盈，不挂初始止损；锁仓期只允许止盈，`min_hold_bars` 结束后再启用原始 ATR trailing stop。

## V3.3 参数

- `ema_fast=21`，`ema_slow=96`，`pullback_buffer=0.01`
- `stop_atr=0.5`，`trail_atr=0.75`，`min_hold_bars=9`
- `1 * ATR14` 使用信号 K 上已经闭合可见的 `ATR14`。

## 结果

| 口径 | 交易数 | 年化 | 总收益 | 胜率 | PF | payoff | 最大回撤 | 锁仓期止盈率 | 总止盈率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `V3.3 原始旧口径，无即时 TP` | `8027` | `1327928815.51x` | `512839871573.17%` | `55.66%` | `4.15` | `3.31` | `-8.69%` | `n/a` | `n/a` |
| `V3.3 live-realistic，无即时 TP` | `8024` | `0.00x` | `-100.00%` | `38.43%` | `0.58` | `0.94` | `-100.00%` | `0.00%` | `0.00%` |
| `即时 1ATR TP + 旧 stop 价成交` | `10112` | `99649.13x` | `20891790.66%` | `56.80%` | `2.38` | `1.81` | `-8.65%` | `50.19%` | `51.96%` |
| `即时 1ATR TP + live-realistic stop` | `10107` | `0.00x` | `-100.00%` | `53.46%` | `0.55` | `0.48` | `-100.00%` | `50.19%` | `52.00%` |

## 退出原因

- 旧 stop 价成交口径：`{'target_lockout': 5075, 'stop_old_price': 4857, 'target_after_unlock': 179, 'time': 1}`
- live-realistic 口径：`{'target_lockout': 5073, 'gap_or_unlock_market_exit': 4296, 'stop_market': 555, 'target_after_unlock': 183}`

## 结论

即时 `1 * ATR14` 止盈在 V3.3 上比 V2.1A 更频繁触发，约 `50.19%` 的交易在锁仓期内先止盈。

但它仍没有修复核心问题：剩余交易解锁后大量进入 stop 已穿越/市价退出路径。旧 stop 价成交口径仍显著赚钱，但 live-realistic 口径 PF 只有约 `0.55`，仍是亏损结构。因此，V3.3 也不能靠入场即挂 1ATR 止盈修复。

## 产物

- 脚本：`research/hype/families/5m-pullback-trail/scripts/research_hype_5m_pbtr_v33_immediate_tp_audit.py`
- JSON：`artifacts/hype_5m_pbtr_v33_immediate_tp_audit.json`
- 汇总 CSV：`artifacts/hype_5m_pbtr_v33_immediate_tp_audit_summary.csv`
