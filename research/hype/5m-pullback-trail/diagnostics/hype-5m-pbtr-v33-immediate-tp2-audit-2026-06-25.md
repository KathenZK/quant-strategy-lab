# HYPE-5M-PBTR-V3.3 immediate 2ATR TP 审计 2026-06-25

Family id：`HYPE-5M-PBTR`

本报告测试 `HYPE-5M-PBTR-V3.3` 的开仓即时 `2 * ATR14` 固定止盈：锁仓期 `min_hold_bars=9` 内只允许止盈，不挂策略止损；解锁后再启用原 ATR trailing stop。

## 结果

| 口径 | 交易数 | 年化 | 总收益 | 胜率 | PF | payoff | 最大回撤 | 锁仓期止盈率 | 总止盈率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `V3.3 原始旧口径，无即时 TP` | `8027` | `1327928815.51x` | `512839871573.17%` | `55.66%` | `4.15` | `3.31` | `-8.69%` | `n/a` | `n/a` |
| `V3.3 live-realistic，无即时 TP` | `8024` | `0.00x` | `-100.00%` | `38.43%` | `0.58` | `0.94` | `-100.00%` | `0.00%` | `0.00%` |
| `即时 2ATR TP + 旧 stop 价成交` | `8701` | `31096442.62x` | `9432904960.68%` | `55.80%` | `3.40` | `2.69` | `-8.69%` | `25.76%` | `28.36%` |
| `即时 2ATR TP + live-realistic stop` | `8699` | `0.00x` | `-100.00%` | `41.76%` | `0.60` | `0.84` | `-100.00%` | `25.76%` | `28.37%` |

## 退出原因

- 旧 stop 价成交口径：`{'stop_old_price': 6232, 'target_lockout': 2241, 'target_after_unlock': 227, 'time': 1}`
- live-realistic 口径：`{'gap_or_unlock_market_exit': 5180, 'target_lockout': 2241, 'stop_market': 1051, 'target_after_unlock': 227}`

## 结论

即时 `2 * ATR14` 止盈比 `1 * ATR14` 更远，锁仓期止盈率降至约 `25.76%`。它保留了更多交易进入解锁后的 trailing stop 阶段。

旧 stop 价成交口径仍然非常赚钱，PF `3.40`；但 live-realistic 口径 PF 只有 `0.60`，总收益仍约 `-100%`。这说明扩大即时止盈到 2ATR 没有修复 V3.3 的可执行性问题，只是把一部分早期止盈换成更多解锁后市价退出/stop-market 亏损。

## 产物

- 脚本：`research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v33_immediate_tp2_audit.py`
- JSON：`artifacts/hype_5m_pbtr_v33_immediate_tp2_audit.json`
- 汇总 CSV：`artifacts/hype_5m_pbtr_v33_immediate_tp2_audit_summary.csv`
