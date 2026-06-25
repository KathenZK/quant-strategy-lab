# HYPE-5M-PBTR-V2.1A immediate TP 审计 2026-06-25

Family id：`HYPE-5M-PBTR`

本报告测试一个补救想法：开仓后立即挂 `1 * ATR14` 固定止盈，不挂初始止损；前 `6` 根 K 只允许止盈，`min_hold_bars` 结束后再启用原始 ATR trailing stop。

## 口径

- `1 * ATR14` 使用信号 K 上已经闭合可见的 `ATR14`。
- 止盈从入场成交后立即生效，方向为多头 `entry + ATR14`、空头 `entry - ATR14`。
- `旧 stop 价成交`：第 6 根后沿用原始回测，stop 被触发时按计算出的 stop price 成交。
- `live-realistic`：第 6 根后如果 stop 已经被开盘价穿越，按开盘市价退出；否则再按 stop-market 管理。

## 结果

| 口径 | 交易数 | 年化 | 总收益 | 胜率 | PF | payoff | 最大回撤 | 前6根止盈率 | 总止盈率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `原始旧口径，无即时 TP` | `3146` | `352.15x` | `51249.39%` | `51.40%` | `2.79` | `2.64` | `-6.62%` | `n/a` | `n/a` |
| `live-realistic，无即时 TP` | `3145` | `0.00x` | `-99.84%` | `37.71%` | `0.54` | `0.88` | `-99.85%` | `0.00%` | `0.00%` |
| `即时 1ATR TP + 旧 stop 价成交` | `3667` | `27.71x` | `3330.66%` | `51.54%` | `1.86` | `1.74` | `-7.01%` | `42.87%` | `45.87%` |
| `即时 1ATR TP + live-realistic stop` | `3666` | `0.00x` | `-99.89%` | `48.01%` | `0.53` | `0.58` | `-99.89%` | `42.85%` | `45.85%` |

## 退出原因

- 旧 stop 价成交口径：`{'stop_old_price': 1985, 'target_first_6': 1572, 'target_after_unlock': 110}`
- live-realistic 口径：`{'gap_or_unlock_market_exit': 1673, 'target_first_6': 1571, 'stop_market': 312, 'target_after_unlock': 110}`

## 结论

即时 `1 * ATR14` 止盈确实能让约 `42.85%` 的交易在前 6 根 K 先止盈，明显减少一部分锁仓期风险。

但它没有修复核心问题：剩余交易在第 6 根后仍大量落入 stop 已穿越/必须市价退出的路径。旧 stop 价成交口径下 PF 仍有 `1.86`，但 live-realistic 口径 PF 只有 `0.53`，总收益约 `-99.89%`。因此，入场即挂 1ATR 止盈不能把 V2.1A 修成可实盘策略。

## 产物

- 脚本：`research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v21a_immediate_tp_audit.py`
- JSON：`artifacts/hype_5m_pbtr_v21a_immediate_tp_audit.json`
- 汇总 CSV：`artifacts/hype_5m_pbtr_v21a_immediate_tp_audit_summary.csv`
